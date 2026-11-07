"""Głosy Rady (E0): zapis linii JSON poza bazą, filtr sekretów, kody powodu decyzji człowieka, porządek plików."""
import json
import os
import sys
from datetime import date
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

from news import clinic, clinic_ai, council_rerun, council_votes as votes, clinic_council as council, council_registry as registry
from news.clinic_ai import ClinicAIError
from news.clinic_models import SpinDiagnosis
from news.test_clinic import POST_TEXT, account, post, staff

QUOTE = 'Tylko my obronimy Polaków!'
GROQ = ('groq', 'openai/gpt-oss-20b')
MEMBERS = [GROQ, ('nim', 'nvidia/nemotron-3-super-120b-a12b'), ('mistral', 'mistral-small-latest'),
           ('claude', 'claude-haiku-5-5')]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    cache.clear()
    monkeypatch.setenv('COUNCIL_VOTES_DIR', str(tmp_path / 'glosy'))
    monkeypatch.delenv('COUNCIL_VOTES_ENABLED', raising=False)
    monkeypatch.setattr('requests.sessions.Session.request', lambda *a, **kw: pytest.fail('Prawdziwa sieć jest zabroniona'))
    yield
    cache.clear()


def lines(kind='vote'):
    path = votes.log_path(kind)
    return [json.loads(line) for line in path.read_text(encoding='ascii').splitlines()] if path.exists() else []


def answer(**extra):
    return {'verdict': 'spin', 'intensity': 70, 'claims': ['Rząd podniósł podatki o 50 procent, pytaj: jan.kowalski@example.com'],
            'techniques': [{'id': 'falszywa_alternatywa', 'name': 'x', 'category': 'logika', 'quote': QUOTE, 'explanation': 'e'},
                           {'id': 'insynuacja', 'name': 'y', 'category': 'logika', 'quote': 'cytat, którego nie ma w poście', 'explanation': 'e'}],
            **extra}


def fake_ask(failing=()):
    def ask(member, system, user, schema, max_tokens=3000):
        if member in failing:
            raise ClinicAIError('http_429 Bearer SECRET-DO-NOT-LOG')
        return answer()
    return ask


@pytest.fixture
def council_flow(monkeypatch):
    """Cały przebieg Rady na atrapach: członkowie odpowiadają z fake_ask, reszta kroków (fakty, przewodniczący…) uproszczona."""
    def setup(failing=(), members=MEMBERS, met=True):
        monkeypatch.setenv('CLINIC_AUTO_PUBLISH', 'false')
        monkeypatch.setattr(clinic_ai, 'provider', lambda: 'council')
        monkeypatch.setattr(council, 'ask', fake_ask(failing))
        monkeypatch.setattr(council, 'consult', lambda text, lines: [council._opinion(m, text, lines) for m in members])
        monkeypatch.setattr(council, 'check_claims', lambda claims: ([], {}))
        monkeypatch.setattr(council, 'write', lambda *a, **kw: ({'headline': 'Nagłówek', 'summary': 'S', 'analysis': 'A', 'limitations': ''}, 'chair'))
        monkeypatch.setattr(council, 'review', lambda *a, **kw: {'ok': True, 'issues': [], 'model': 'r'})
        monkeypatch.setattr(council, 'polish', lambda text: (text, 'ling'))
        monkeypatch.setattr('news.clinic_lab.run_lab', lambda *a, **kw: {})
        monkeypatch.setattr('news.clinic_plain.edit_plain', lambda *a, **kw: {})
        state = {'met': met, 'members': 3, 'need_members': 3, 'core': 0, 'need_core': 0, 'missing_core': [],
                 'reason': '' if met else 'council_quorum: test'}
        monkeypatch.setattr('news.council_quorum.check', lambda *a, **kw: state)
    return setup


def queued():
    return SpinDiagnosis.objects.create(post=post(account()), status='queued')


# --- zapis ------------------------------------------------------------------------------------------------------------

def test_write_is_one_ascii_line_per_record_and_appends():
    record = {'schema': 'glosy/1', 'type': 'vote', 'raw': {'t': 'zażółć gęślą\njaźń'}, 'b': 1, 'a': 2}
    assert votes.write([record]) == 1 and votes.write([record, record]) == 2
    text = votes.log_path().read_text(encoding='ascii')  # ensure_ascii: plik czysto ASCII
    assert text.count('\n') == 3 and ' ' not in text
    assert text.splitlines()[0].index('"a"') < text.splitlines()[0].index('"b"')  # sort_keys
    assert json.loads(text.splitlines()[0])['raw']['t'] == 'zażółć gęślą\njaźń'
    assert votes.log_path().name.startswith('glosy-') and votes.log_path().name.endswith('.jsonl')


def test_decisions_go_to_their_own_monthly_file():
    votes.write([{'type': 'human_decision', 'reason_code': 'OTHER'}, {'type': 'vote'}])
    assert votes.log_path('human_decision').name.startswith('decyzje-') and len(lines('human_decision')) == 1
    assert len(lines('vote')) == 1


def test_switch_off_writes_nothing(monkeypatch):
    monkeypatch.setenv('COUNCIL_VOTES_ENABLED', 'false')
    assert votes.write([{'type': 'vote'}]) == 0
    assert not votes.log_dir().exists()


def test_write_failure_is_swallowed(monkeypatch, tmp_path):
    blocker = tmp_path / 'plik'
    blocker.write_text('x')
    monkeypatch.setenv('COUNCIL_VOTES_DIR', str(blocker / 'glosy'))  # katalog nie do utworzenia
    assert votes.write([{'type': 'vote'}]) == 0
    monkeypatch.setattr(votes, '_append', Mock(side_effect=OSError('Dysk pełny')))
    assert votes.write([{'type': 'vote'}]) == 0


@pytest.mark.skipif(sys.platform == 'win32', reason='uprawnienia 600/700 dotyczą systemów POSIX')
def test_file_and_directory_permissions():
    votes.write([{'type': 'vote'}])
    assert oct(os.stat(votes.log_path()).st_mode & 0o777) == '0o600'
    assert oct(os.stat(votes.log_dir()).st_mode & 0o777) == '0o700'


def test_secrets_and_personal_data_are_removed_before_writing():
    secrets = ['sk-ant-api03-abcdefghijklmnop', 'gsk_abcdefghij1234567890', 'nvapi-abcdefghij1234567890',
               'AIzaSyA-abcdefghij1234567890', 'Bearer abcdef123456', 'Authorization: Basic dXNlcjpwYXNz']
    record = {'type': 'vote', 'note': 'http_402 ' + ' '.join(secrets), 'run_id': 'bez zmian',
              'raw': {'claims': ['Pisz: jan.kowalski@example.com albo +48 600 700 800, 600-700-800, 600700800, 22 123 45 67'],
                      'x': {'k': 'klucz sk-proj-abcdefghijkl'}},
              'techniques': [{'quote': 'zadzwoń 601 602 603'}], 'prompt_sha256': 'a' * 64}
    assert votes.write([record]) == 1
    saved = votes.log_path().read_text(encoding='ascii')
    for secret in secrets + ['example.com', '600 700 800', '600-700-800', '600700800', '123 45 67', '601 602 603', 'proj-abc']:
        assert secret.split(': ')[-1] not in saved
    line = lines()[0]
    assert line['run_id'] == 'bez zmian' and line['prompt_sha256'] == 'a' * 64
    assert 'Rząd' not in saved and votes.REDACTED in line['raw']['claims'][0]
    assert 'Basic' not in line['note'] and 'Bearer' not in line['note']


# --- przechwycenie odpowiedzi członka -----------------------------------------------------------------------------------

def response(data, status=200):
    result = Mock(status_code=status)
    result.json.return_value = data
    return result


def test_openai_compatible_member_keeps_raw_model_and_tokens(monkeypatch):
    monkeypatch.setenv(registry.KEYS['groq'], 'test-key')
    body = {'model': 'openai/gpt-oss-20b-0925', 'usage': {'prompt_tokens': 812, 'completion_tokens': 190},
            'choices': [{'message': {'content': json.dumps(answer())}}]}
    monkeypatch.setattr(council.requests, 'post', Mock(return_value=response(body)))
    opinion = council._opinion(GROQ, POST_TEXT, '')
    captured = opinion['_raw']
    assert captured['model_served'] == 'openai/gpt-oss-20b-0925' and captured['tokens'] == {'input': 812, 'output': 190}
    assert captured['raw'] == answer() and captured['member'] == 'groq:openai/gpt-oss-20b'
    flags = {t['id']: (t['quote_ok'], t['accepted']) for t in captured['techniques_all']}
    assert flags == {'falszywa_alternatywa': (True, True), 'insynuacja': (False, False)}  # odrzucona zostaje w zapisie
    assert [t['id'] for t in opinion['techniques']] == ['falszywa_alternatywa']


def test_gemini_and_claude_members_keep_version_and_tokens(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    gemini = {'modelVersion': 'gemini-2.5-flash-002', 'usageMetadata': {'promptTokenCount': 500, 'candidatesTokenCount': 80},
              'candidates': [{'content': {'parts': [{'text': json.dumps(answer())}]}}]}
    monkeypatch.setattr(clinic_ai, 'gemini_post', lambda *a, **kw: response(gemini))
    monkeypatch.setattr(registry, 'reserve', lambda member: True)
    raw = council._opinion(('gemini', 'gemini-2.5-flash'), POST_TEXT, '')['_raw']
    assert (raw['model_served'], raw['tokens']) == ('gemini-2.5-flash-002', {'input': 500, 'output': 80})
    message = SimpleNamespace(content=[SimpleNamespace(type='text', text=json.dumps(answer()))], model='claude-haiku-5-5-20260101',
                              usage=SimpleNamespace(input_tokens=11, output_tokens=7))
    monkeypatch.setattr(clinic_ai, '_client', lambda: SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: message)))
    raw = council._opinion(('claude', 'claude-haiku-5-5'), POST_TEXT, '')['_raw']
    assert (raw['model_served'], raw['tokens']) == ('claude-haiku-5-5-20260101', {'input': 11, 'output': 7})


def test_failed_member_has_no_raw_and_ask_role_is_untouched(monkeypatch):
    monkeypatch.setattr(council, 'ask', fake_ask(failing=[GROQ]))
    opinion = council._opinion(GROQ, POST_TEXT, '')
    assert opinion['status'] == 'brak odpowiedzi' and opinion['_raw']['raw'] is None and opinion['_raw']['tokens'] is None
    monkeypatch.setattr(council, 'ask', lambda *a, **kw: {'ok': True})
    monkeypatch.setattr(council, '_members', lambda name, default: [GROQ])
    monkeypatch.setattr(registry, 'available', lambda member: True)
    assert council.ask_role('X', '', 's', 'u', {}) == ({'ok': True}, 'openai/gpt-oss-20b')


# --- przebieg Rady zapisuje głosy ---------------------------------------------------------------------------------------

@pytest.mark.django_db
def test_diagnosis_logs_every_vote_and_keeps_raw_out_of_the_database(council_flow):
    council_flow(failing=[MEMBERS[1]])
    row = clinic.diagnose(queued())
    assert row.status == 'pending_review'
    records = lines()
    assert len(records) == 4 and len({r['run_id'] for r in records}) == 1
    assert {r['outcome'] for r in records} == {'diagnosed'} and {r['diagnosis_id'] for r in records} == {row.pk}
    assert {r['post_id'] for r in records} == {row.post_id} and all(r['training_allowed'] is False for r in records)
    good = next(r for r in records if r['member'] == 'groq:openai/gpt-oss-20b')
    assert good['valid'] is True and good['verdict'] == 'spin' and good['intensity'] == 70 and good['raw']['techniques'] == answer()['techniques']
    assert good['raw']['claims'] == ['Rząd podniósł podatki o 50 procent, pytaj: [usunięto]'] and good['claims'] == good['raw']['claims']
    assert good['schema'] == 'glosy/1' and good['prompt_version'] == clinic_ai.PROMPT_VERSION and len(good['prompt_sha256']) == 64
    assert [t['quote_ok'] for t in good['techniques']] == [True, False]
    bad = next(r for r in records if r['status'] == 'brak odpowiedzi')
    assert bad['valid'] is False and bad['raw'] is None and bad['verdict'] is None and 'SECRET' not in json.dumps(bad)
    assert len(bad['note']) <= 120
    saved = SpinDiagnosis.objects.get(pk=row.pk)
    assert '_raw' not in json.dumps(saved.usage) and 'raw' not in saved.usage['council']['members'][0]
    assert set(saved.usage['council']['members'][0]) <= {'model', 'company', 'provider', 'role', 'status', 'note', 'verdict', 'intensity', 'seconds'}
    assert '_raw' not in json.dumps(clinic.detail_data(saved), default=str)


@pytest.mark.django_db
def test_quorum_deferred_votes_are_logged_too(council_flow):
    council_flow(members=MEMBERS[:2], met=False)
    row = clinic.diagnose(queued())
    assert row.status == 'queued' and row.error.startswith('council_quorum')
    records = lines()
    assert len(records) == 2 and {r['outcome'] for r in records} == {'quorum_deferred'}
    assert '_raw' not in json.dumps(SpinDiagnosis.objects.get(pk=row.pk).usage)


@pytest.mark.django_db
def test_failure_after_votes_is_logged_as_failed(council_flow, monkeypatch):
    council_flow()
    monkeypatch.setattr(council, 'write', Mock(side_effect=ClinicAIError('council_writer_not_polish')))
    row = clinic.diagnose(queued())
    assert row.status == 'failed' and {r['outcome'] for r in lines()} == {'failed'}


@pytest.mark.django_db
def test_write_error_never_stops_the_diagnosis(council_flow, monkeypatch):
    council_flow()
    monkeypatch.setattr(votes, '_append', Mock(side_effect=OSError('brak miejsca')))
    assert clinic.diagnose(queued()).status == 'pending_review'
    monkeypatch.setattr(votes, 'write', Mock(side_effect=RuntimeError('błąd w zapisie')))
    second = SpinDiagnosis.objects.create(post=post(account(handle='drugi', user_id='102'), '9002'), status='queued')
    assert clinic.diagnose(second).status == 'pending_review'


@pytest.mark.django_db
def test_switch_off_diagnosis_writes_no_file(council_flow, monkeypatch):
    monkeypatch.setenv('COUNCIL_VOTES_ENABLED', 'false')
    council_flow()
    assert clinic.diagnose(queued()).status == 'pending_review' and not votes.log_dir().exists()


@pytest.mark.django_db
def test_rerun_logs_votes_with_the_diagnosis_id(council_flow):
    council_flow()
    row = SpinDiagnosis.objects.create(post=post(account()), status='approved', verdict='spin', intensity=50,
                                       diagnosed_at=clinic.timezone.now(), provider='anthropic',
                                       usage={'council': {'members': [{'model': 'a', 'status': 'odpowiedział'}]}})
    assert council_rerun.rerun(row) in ('updated', 'same')
    records = lines()
    assert len(records) == 4 and {r['diagnosis_id'] for r in records} == {row.pk} and {r['outcome'] for r in records} == {'diagnosed'}
    assert '_raw' not in json.dumps(SpinDiagnosis.objects.get(pk=row.pk).usage)


def test_no_run_means_no_votes_and_exam_is_not_logged(monkeypatch):
    monkeypatch.setattr(council, 'ask', fake_ask())
    opinion = council._opinion(GROQ, POST_TEXT, '')
    votes.stage([opinion])  # bez przebiegu: brak skutków
    assert not votes.log_dir().exists()


# --- kod powodu decyzji człowieka ---------------------------------------------------------------------------------------

def approved(**extra):
    return SpinDiagnosis.objects.create(post=post(account()), status='approved', verdict='spin', intensity=60,
                                        diagnosed_at=clinic.timezone.now(), **extra)


@pytest.mark.django_db
def test_withdraw_records_reason_code_in_usage_and_file(django_capture_on_commit_callbacks):
    row, operator = approved(usage={'model': 'm'}), staff()
    with django_capture_on_commit_callbacks(execute=True):
        clinic.withdraw(row, operator, 'Źródło nie potwierdza wniosku, pisz: a@b.pl', 'WRONG_FACT')
    row.refresh_from_db()
    decision = row.usage['human_decisions'][0]
    assert row.usage['model'] == 'm' and decision['action'] == 'withdraw' and decision['reason_code'] == 'WRONG_FACT'
    assert decision['staff_id'] == operator.pk and decision['comment'].startswith('Źródło')
    line = lines('human_decision')[0]
    assert (line['type'], line['action'], line['reason_code'], line['diagnosis_id'], line['post_id']) == (
        'human_decision', 'withdraw', 'WRONG_FACT', row.pk, row.post_id)
    assert line['training_allowed'] is False and 'a@b.pl' not in json.dumps(line)


@pytest.mark.django_db
def test_withdraw_without_code_defaults_to_other_and_bad_code_is_refused(django_capture_on_commit_callbacks):
    row, operator = approved(), staff()
    with pytest.raises(ValueError):
        clinic.withdraw(row, operator, 'Powód', 'DOWOLNY TEKST')
    assert SpinDiagnosis.objects.get(pk=row.pk).status == 'approved'
    with django_capture_on_commit_callbacks(execute=True):
        clinic.withdraw(row, operator, 'Powód')
    assert SpinDiagnosis.objects.get(pk=row.pk).usage['human_decisions'][0]['reason_code'] == 'OTHER'
    assert lines('human_decision')[0]['reason_code'] == 'OTHER'


@pytest.mark.django_db
def test_hide_api_reason_code_default_valid_and_invalid(django_capture_on_commit_callbacks):
    row, operator = approved(usage={'council': {'members': []}}), staff()
    client = APIClient()
    client.force_authenticate(operator)
    url = f'/api/staff/clinic/diagnoses/{row.pk}/hide/'
    assert client.post(url, {'reason': 'Zgłoszenie prawne', 'reason_code': 'WRONG'}, format='json').status_code == 400
    assert client.post(url, {'reason': 'Zgłoszenie prawne', 'reason_code': 'wrong_fact'}, format='json').status_code == 400
    row.refresh_from_db()
    assert row.hidden_at is None and not (row.usage or {}).get('human_decisions')
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(url, {'reason': 'Zgłoszenie prawne'}, format='json').status_code == 200
        assert client.post(url, {'reason': 'Dane osobowe', 'reason_code': 'PRIVACY'}, format='json').status_code == 200
    row.refresh_from_db()
    assert row.usage['council'] == {'members': []}
    assert [(d['action'], d['reason_code']) for d in row.usage['human_decisions']] == [('hide', 'OTHER'), ('hide', 'PRIVACY')]
    assert [d['reason_code'] for d in lines('human_decision')] == ['OTHER', 'PRIVACY']


def test_reason_codes_are_the_closed_list_with_polish_labels():
    assert votes.REASON_CODES == ('APPROVE', 'INSUFFICIENT_EVIDENCE', 'WRONG_FACT', 'WRONG_RUBRIC', 'PRIVACY', 'LEGAL',
                                  'OUT_OF_SCOPE', 'OTHER')
    assert all(votes.REASON_LABELS[code] for code in votes.REASON_CODES)


@pytest.mark.django_db
def test_admin_withdrawal_form_offers_reason_codes():
    from news.clinic_admin import WithdrawalForm
    form = WithdrawalForm({'reason': 'Powód', 'reason_code': 'LEGAL'})
    assert form.is_valid() and form.cleaned_data['reason_code'] == 'LEGAL'
    assert not WithdrawalForm({'reason': 'Powód', 'reason_code': 'INNY'}).is_valid()
    assert WithdrawalForm().fields['reason_code'].initial == 'OTHER'


# --- porządek plików ---------------------------------------------------------------------------------------------------

def make_files(names):
    votes.log_dir().mkdir(parents=True)
    for name in names:
        (votes.log_dir() / name).write_text('{}\n')


def test_cleanup_keeps_separate_periods_and_only_matching_files():
    names = ['glosy-2020-01.jsonl', 'glosy-2024-06.jsonl', 'glosy-2024-12.jsonl', 'glosy-2026-10.jsonl',
             'decyzje-2020-01.jsonl', 'decyzje-2023-06.jsonl', 'decyzje-2024-12.jsonl', 'notatki.txt', 'glosy-2020-13.jsonl',
             'glosy-2020-01.jsonl.bak', 'inne-2020-01.jsonl']
    make_files(names)
    today = date(2026, 10, 25)
    dry = votes.cleanup(today=today, dry_run=True)
    assert sorted(r['file'] for r in dry) == ['decyzje-2020-01.jsonl', 'decyzje-2023-06.jsonl', 'glosy-2020-01.jsonl', 'glosy-2024-06.jsonl']
    assert all(not r['removed'] for r in dry) and all((votes.log_dir() / n).exists() for n in names)
    done = votes.cleanup(today=today)
    assert all(r['removed'] for r in done)
    assert sorted(p.name for p in votes.log_dir().iterdir()) == sorted(
        set(names) - {'decyzje-2020-01.jsonl', 'decyzje-2023-06.jsonl', 'glosy-2020-01.jsonl', 'glosy-2024-06.jsonl'})


def test_cleanup_periods_from_env_and_options(monkeypatch):
    make_files(['glosy-2026-01.jsonl', 'decyzje-2026-01.jsonl'])
    today = date(2026, 10, 25)
    monkeypatch.setenv('COUNCIL_VOTES_RETENTION_DAYS', '30')
    monkeypatch.setenv('COUNCIL_DECISIONS_RETENTION_DAYS', 'nie liczba')
    assert [r['file'] for r in votes.cleanup(today=today, dry_run=True)] == ['glosy-2026-01.jsonl']
    assert [r['file'] for r in votes.cleanup(keep_votes=1000, keep_decisions=30, today=today, dry_run=True)] == ['decyzje-2026-01.jsonl']


def test_cleanup_command_dry_run_and_real_run():
    make_files(['glosy-2001-01.jsonl'])
    out = StringIO()
    call_command('glosy_porzadek', '--keep-days', '730', '--dry-run', stdout=out)
    assert 'do usunięcia: glosy-2001-01.jsonl' in out.getvalue() and (votes.log_dir() / 'glosy-2001-01.jsonl').exists()
    call_command('glosy_porzadek', '--keep-days', '730', stdout=StringIO())
    assert not (votes.log_dir() / 'glosy-2001-01.jsonl').exists()
    call_command('glosy_porzadek', stdout=StringIO())  # bez katalogu i bez plików: bez błędu


# --- usuwanie wpisów jednej osoby (glosy_usun) --------------------------------------------------------------------------

def vote_line(post_id, diagnosis_id, kind='vote'):
    return json.dumps({'type': kind, 'post_id': post_id, 'diagnosis_id': diagnosis_id, 'schema': 'glosy/1'}, sort_keys=True)


def make_log():
    votes.log_dir().mkdir(parents=True)
    files = {
        'glosy-2026-10.jsonl': [vote_line(1, 10), vote_line(2, 20), '{nie json', vote_line(3, 10), vote_line(4, None)],
        'glosy-2026-09.jsonl': [vote_line(2, 20), vote_line(2, 21)],
        'decyzje-2026-10.jsonl': [vote_line(1, 10, 'human_decision'), vote_line(5, 50, 'human_decision')],
        'decyzje-2026-11.jsonl': [vote_line(7, 70, 'human_decision')],
    }
    for name, content in files.items():
        (votes.log_dir() / name).write_bytes(('\n'.join(content) + '\n').encode('ascii'))
    return files


def test_erase_dry_run_counts_and_changes_nothing():
    files = make_log()
    before = {n: (votes.log_dir() / n).read_bytes() for n in files}
    rows = votes.erase(post_ids=[1], diagnosis_ids=[20], dry_run=True)
    assert {r['file']: (r['removed'], r['kept'], r['unparsable']) for r in rows} == {
        'glosy-2026-10.jsonl': (2, 2, 1), 'glosy-2026-09.jsonl': (1, 1, 0), 'decyzje-2026-10.jsonl': (1, 1, 0)}
    assert {n: (votes.log_dir() / n).read_bytes() for n in files} == before


def test_erase_rewrites_without_matching_lines_and_keeps_the_rest_verbatim():
    files = make_log()
    untouched = (votes.log_dir() / 'decyzje-2026-11.jsonl').read_bytes()
    rows = votes.erase(post_ids=[1], diagnosis_ids=[20])
    assert sum(r['removed'] for r in rows) == 4
    assert (votes.log_dir() / 'glosy-2026-10.jsonl').read_text('ascii').splitlines() == [
        files['glosy-2026-10.jsonl'][2], files['glosy-2026-10.jsonl'][3], files['glosy-2026-10.jsonl'][4]]  # nieparsowalna i obce zostają
    assert (votes.log_dir() / 'glosy-2026-09.jsonl').read_text('ascii').splitlines() == [vote_line(2, 21)]
    assert (votes.log_dir() / 'decyzje-2026-10.jsonl').read_text('ascii').splitlines() == [vote_line(5, 50, 'human_decision')]
    assert (votes.log_dir() / 'decyzje-2026-11.jsonl').read_bytes() == untouched
    assert not [p for p in votes.log_dir().iterdir() if p.name.endswith('.tmp')]
    assert votes.erase(post_ids=[1], diagnosis_ids=[20]) == []  # drugi przebieg nie ma już czego usuwać
    votes.write([{'type': 'vote', 'post_id': 99}])  # dopisywanie po przepisaniu nadal działa
    assert any('"post_id": 99' in line for line in votes.log_path().read_text('ascii').splitlines())


@pytest.mark.skipif(sys.platform == 'win32', reason='uprawnienia 600 dotyczą systemów POSIX')
def test_erase_keeps_file_permissions():
    make_log()
    os.chmod(votes.log_dir() / 'glosy-2026-10.jsonl', 0o600)
    votes.erase(post_ids=[1])
    assert oct(os.stat(votes.log_dir() / 'glosy-2026-10.jsonl').st_mode & 0o777) == '0o600'


def test_erase_needs_an_id_and_ignores_foreign_files():
    make_log()
    (votes.log_dir() / 'notatki.txt').write_text(vote_line(1, 10))
    assert votes.erase() == []
    votes.erase(post_ids=[1])
    assert json.loads((votes.log_dir() / 'notatki.txt').read_text())['post_id'] == 1


def test_append_and_erase_share_one_lock(monkeypatch):
    fake = Mock(LOCK_EX=2, LOCK_UN=8)
    monkeypatch.setattr(votes, 'fcntl', fake)
    make_log()
    votes.write([{'type': 'vote', 'post_id': 1}])
    votes.erase(post_ids=[1])
    assert fake.flock.call_count == 4 and [c.args[1] for c in fake.flock.call_args_list] == [2, 8, 2, 8]
    assert (votes.log_dir() / votes.LOCK_NAME).exists()
    assert votes.cleanup(keep_votes=0, keep_decisions=0, today=date(2030, 1, 1))  # plik blokady nie pasuje do wzorca
    assert (votes.log_dir() / votes.LOCK_NAME).exists()


def test_erase_command_dry_run_output_and_real_run():
    make_log()
    out = StringIO()
    call_command('glosy_usun', '--post-id', '1', '--post-id', '3', '--diagnosis-id', '21', '--dry-run', stdout=out)
    text = out.getvalue()
    assert 'glosy-2026-10.jsonl: do usunięcia linii: 2, zostaje: 2, nieparsowalnych (bez zmian): 1' in text
    assert 'glosy-2026-09.jsonl: do usunięcia linii: 1' in text and 'Do usunięcia linii: 4 w plikach: 3' in text
    assert len((votes.log_dir() / 'glosy-2026-10.jsonl').read_text('ascii').splitlines()) == 5
    out = StringIO()
    call_command('glosy_usun', '--post-id', '1', '--post-id', '3', '--diagnosis-id', '21', stdout=out)
    assert 'Usunięto linii: 4 w plikach: 3' in out.getvalue()
    assert len((votes.log_dir() / 'glosy-2026-10.jsonl').read_text('ascii').splitlines()) == 3
    from django.core.management.base import CommandError
    with pytest.raises(CommandError):
        call_command('glosy_usun', stdout=StringIO())


# --- zadanie miesięczne -------------------------------------------------------------------------------------------------

def test_monthly_task_runs_cleanup_and_is_scheduled_without_alarms():
    from config.celery import app
    from news import agent_registry, task_heartbeat, tasks
    make_files(['glosy-2001-01.jsonl', 'decyzje-2001-01.jsonl', 'glosy-2999-01.jsonl'])
    assert tasks.glosy_porzadek_task() == {'status': 'ok', 'removed': 2}
    assert [p.name for p in votes.log_dir().iterdir()] == ['glosy-2999-01.jsonl']
    entry = app.conf.beat_schedule['glosy-porzadek-monthly']
    assert entry['task'] == 'news.tasks.glosy_porzadek_task'
    assert (entry['schedule'].day_of_month, entry['schedule'].hour, entry['schedule'].minute) == ({1}, {4}, {20})
    assert entry['task'] in {spec['task'] for spec in agent_registry.REGISTRY.values()}
    assert task_heartbeat.cadence(entry['schedule']) is None  # miesięczne: kontrola „brak pulsu” z rytmem nie ma czego porównywać
    assert agent_registry.schedule_label(entry['schedule']) == 'co miesiąc, dzień: 1, godz. 4:20'
    assert task_heartbeat.summary({'status': 'ok', 'removed': 2}) == 'OK; removed: 2'
