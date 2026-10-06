from copy import deepcopy
from unittest.mock import Mock

import pytest
from django.core.cache import cache

from news import clinic_plain as plain, clinic_council as council, plain_reader
from news.clinic_models import SpinDiagnosis
from news.techniques import CANONICAL_TECHNIQUES, PLAIN_NAMES
from news.test_clinic import account, post
from news.test_social_texts import sample
from news.x_share import build, weight

GOOD = 'Poseł wylicza błędy ministrów i przypisuje im złe zamiary. Winę pojedynczych osób rozciąga na całą koalicję.'
BAD = ('Wpis stanowi zestawienie jednostronnych zarzutów wobec przedstawicieli instytucji publicznych i rządu, '
       'ujętych w formę listy przewinień. Zastosowana narracja opiera się na wybiórczym doborze faktów.')
POST = 'Ministrowie chcą zaszkodzić Polsce. Cała koalicja jest winna.'


def candidate(**changes):
    return {'title': 'Poseł o błędach ministrów', 'gist': GOOD, 'top': [
        {'name': 'Sugerowanie złych zamiarów', 'quote': 'chcą zaszkodzić Polsce'},
        {'name': 'Obwinianie całej grupy', 'quote': 'Cała koalicja jest winna'}], **changes}


def diagnosis():
    return {'summary': GOOD, 'analysis': GOOD, 'claims': [{'assessment': 'unverified'}], 'techniques': [
        {'category': 'Przypisywanie intencji', 'quote': 'Ministrowie chcą zaszkodzić Polsce.'},
        {'category': 'Nadmierne uogólnienie', 'quote': 'Cała koalicja jest winna.'}]}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('Zakaz sieci')))


def test_owner_examples():
    assert plain.measure_plain(candidate()) == []
    assert plain.measure_plain(candidate(gist=BAD))
    assert plain.guard_plain(candidate(), diagnosis(), POST) == []
    assert plain.measure_plain(candidate(gist='Poseł opisuje stanowisko rządu. Brakuje danych.')) == []


@pytest.mark.parametrize('term', plain.BANNED)
def test_every_banned_phrase(term):
    assert plain.measure_plain(candidate(gist=f'Poseł {term} temat. Brakuje danych.'))
    assert plain.measure_plain(candidate(gist='Poseł pisze o podatkach. Brakuje danych.')) == []


@pytest.mark.parametrize('field,limit', [('title', 8), ('gist', 25)])
def test_total_word_boundaries(field, limit):
    def text(count):
        return ' '.join(['kot'] * count) if field == 'title' else ' '.join(['kot'] * 13) + '. ' + ' '.join(['pies'] * (count - 13)) + '.'
    assert plain.measure_plain(candidate(**{field: text(limit)})) == []
    assert plain.measure_plain(candidate(**{field: text(limit + 1)}))


def test_sentence_word_boundary():
    assert plain.measure_plain(candidate(gist=' '.join(['kot'] * 15) + '. Pies śpi.')) == []
    assert plain.measure_plain(candidate(gist=' '.join(['kot'] * 16) + '. Pies śpi.'))


@pytest.mark.parametrize('gist,valid', [
    ('Poseł mówi o podatkach.', False), ('Poseł mówi. Kot śpi. Pies je.', False),
    ('Poseł mówi. Kot śpi', False), ('Poseł mówi. Kot śpi.', True),
    ('Poseł pisze o podatkach. Podatki wzrosły.', False),
    ('Poseł pisze o podatkach. Ceny rosną.', True),
    ('Poseł mówi — cicho. Kot śpi.', False), ('Poseł mówi - cicho. Kot śpi.', True),
    ('Pomijanie faktów szkodzi. Poseł pisze.', False), ('Twierdzenie budzi spór. Kot śpi.', False),
    ('Poseł pomija fakty. Kot śpi.', True),
])
def test_sentence_rules(gist, valid):
    assert (not plain.measure_plain(candidate(gist=gist))) == valid


def test_quote_limit_and_label_exception():
    for count in (10, 11):
        value = candidate()
        value['top'][0] = {'name': 'Atak na osobę zamiast na argument', 'quote': ' '.join(['kot'] * count)}
        assert (not plain.measure_plain(value)) == (count == 10)
    assert set(PLAIN_NAMES) == set(CANONICAL_TECHNIQUES)
    assert all(len(plain.words(name)) <= 4 for key, name in PLAIN_NAMES.items() if key != 'Atak na osobę')


@pytest.mark.parametrize('value', [None, {}, [], {'title': 4}, candidate(top=[]), candidate(top=[{}, {}])])
def test_invalid_shape(value):
    assert plain.measure_plain(value)
    assert plain.guard_plain(value, diagnosis(), POST)


def test_title_without_motive():
    assert plain.measure_plain(candidate(title='Poseł chce zaszkodzić rządowi'))
    assert plain.measure_plain(candidate(title='Poseł krytykuje rząd')) == []


def test_literal_quotes_and_technique_provenance():
    value = candidate()
    value['top'][0]['quote'] = 'chcą szkodzić Polsce'
    assert plain.guard_plain(value, diagnosis(), POST)
    value = candidate()
    value['top'][0]['name'] = 'Granie na emocjach'
    assert plain.guard_plain(value, diagnosis(), POST)
    assert plain.guard_plain(candidate(), diagnosis(), POST.replace(' ', '\n')) == []
    value = candidate()
    value['top'][1] = {**value['top'][0], 'quote': 'chcą zaszkodzić'}
    assert plain.guard_plain(value, diagnosis(), POST)


@pytest.mark.parametrize('word', ['kłamie', 'fałszuje', 'oszukuje'])
@pytest.mark.parametrize('assessment,valid', [('unverified', False), ('supported', False), ('refuted', True), ('contradicted', True)])
def test_falsehood_requires_refuted(word, assessment, valid):
    value = candidate(gist=f'Poseł {word}. Brakuje danych.')
    full = diagnosis()
    full.update(summary=value['gist'], claims=[{'assessment': assessment}])
    assert (not plain.guard_plain(value, full, POST)) == valid


def test_new_accusation_rejected():
    value = candidate(gist='Poseł kradnie. Brakuje danych.')
    assert plain.guard_plain(value, diagnosis(), POST)
    full = diagnosis()
    full['summary'] = value['gist']
    assert plain.guard_plain(value, full, POST) == []


@pytest.mark.parametrize('attempts,expected', [([candidate()], True), ([{}, candidate()], True), ([{}, {}], False)])
def test_editor_retries(monkeypatch, attempts, expected):
    ask = Mock(side_effect=[(deepcopy(value), 'test') for value in attempts])
    monkeypatch.setattr(council, 'ask_role', ask)
    assert bool(plain.edit_plain(diagnosis(), POST)) == expected
    assert ask.call_count == len(attempts)
    if len(attempts) == 2:
        assert 'uwagi' in ask.call_args.args[3]


def test_editor_retries_fidelity_failure(monkeypatch):
    bad = candidate(gist='Poseł kłamie. Brakuje danych.')
    ask = Mock(side_effect=[(bad, 'test'), (candidate(), 'test')])
    monkeypatch.setattr(council, 'ask_role', ask)
    assert plain.edit_plain(diagnosis(), POST) == candidate()
    assert ask.call_count == 2


def test_editor_unavailable(monkeypatch):
    monkeypatch.setattr(council, 'ask_role', Mock(side_effect=council.ClinicAIError('unavailable')))
    assert plain.edit_plain(diagnosis(), POST) == {}


def test_paid_guard_and_bielik_first(monkeypatch):
    def ask(role, defaults, *args):
        assert defaults.startswith('hf:speakleash/Bielik')
        guard = plain.registry.reservation_guard.get()
        for member in [('gemini', 'gemini-flash'), ('openrouter', 'paid'), ('hf', 'paid'), ('anthropic', 'claude')]:
            assert not guard(member, 1)
        assert guard(('hf', 'speakleash/Bielik-11B-v3.0-Instruct:publicai'), 1)
        assert guard(('groq', 'qwen'), 1)
        return candidate(), 'test'
    monkeypatch.setattr(council, 'ask_role', ask)
    assert plain.edit_plain(diagnosis(), POST)
    assert plain.registry.reservation_guard.get() is None


@pytest.mark.django_db
def test_old_diagnosis_and_plain_roundtrip():
    from news.clinic import detail_data
    row = SpinDiagnosis.objects.create(post=post(account()), status='approved')
    assert row.plain == {}
    assert detail_data(row)['plain'] == {}
    row.plain = candidate()
    row.save()
    row.refresh_from_db()
    assert detail_data(row)['plain'] == candidate()


@pytest.mark.parametrize('is_account', [False, True])
def test_x_plain_replaces_first_post_and_preserves_limits(is_account):
    data = sample()
    old = deepcopy(data['x_thread'])
    data['plain'] = candidate(gist='Poseł pomija fakty. Brakuje danych.')
    result = build(data, account=is_account)
    assert result and data['plain']['gist'] in result[0]
    assert old[0] not in result[0]
    assert all(weight(text) <= 280 for text in result)
    assert data['x_thread'] == old
    data['plain'] = {}
    assert old[0] in build(data, account=is_account)[0]


def test_x_plain_without_thread_for_manual_share():
    data = sample()
    data.update(plain=candidate(gist='Poseł pomija fakty. Brakuje danych.'), x_thread=[])
    assert build(data)
    assert build(data, account=True) == []


def test_reader_disabled_by_default(monkeypatch):
    monkeypatch.delenv('PLAIN_READER_ENABLED', raising=False)
    ask = Mock()
    monkeypatch.setattr(plain_reader, 'ask_plain_role', ask)
    assert plain_reader.run() == {'status': 'disabled'}
    ask.assert_not_called()


@pytest.mark.parametrize('answer,valid', [('Poseł obwinia grupę.', True), ('Dwa zdania. Są tutaj.', False), ('', False)])
def test_reader_one_sentence(monkeypatch, answer, valid):
    monkeypatch.setattr(plain_reader, 'ask_plain_role', Mock(return_value=({'understood': answer}, 'test')))
    if valid:
        assert plain_reader.read_plain(candidate()) == (answer, 'test')
    else:
        with pytest.raises(council.ClinicAIError):
            plain_reader.read_plain(candidate())


@pytest.mark.django_db
def test_reader_samples_twenty_and_reports_without_mail(monkeypatch):
    from news.agent_models import AgentNote
    monkeypatch.setenv('PLAIN_READER_ENABLED', 'true')
    monkeypatch.setattr('django.core.mail.send_mail', Mock(side_effect=AssertionError('Zakaz maili')))
    acc = account()
    for i in range(23):
        SpinDiagnosis.objects.create(post=post(acc, post_id=str(i)), status='approved', plain=candidate())
    SpinDiagnosis.objects.create(post=post(acc, post_id='old'), status='approved')
    SpinDiagnosis.objects.create(post=post(acc, post_id='hidden'), status='pending_review', plain=candidate())
    read = Mock(return_value=('Poseł obwinia grupę.', 'test'))
    monkeypatch.setattr(plain_reader, 'read_plain', read)
    assert plain_reader.run() == {'status': 'ok', 'completed': 20, 'failed': 0}
    notes = AgentNote.objects.filter(agent='strateg', kind='report')
    assert notes.count() == 20
    assert len({n.scores['diagnosis_id'] for n in notes}) == 20
    assert all(n.cost_usd == 0 for n in notes)


def test_reader_beat_and_registry():
    from config.celery import app
    from news.agent_registry import REGISTRY
    from news.tasks import plain_reader_task
    entry = app.conf.beat_schedule['plain-reader-weekly']
    assert entry['task'] == plain_reader_task.name
    assert entry['schedule'].day_of_week == {1}
    assert all(key in REGISTRY for key in ('plain-editor', 'plain-meter', 'plain-guard', 'plain-reader'))
    cache.clear()


def test_council_calls_editor_after_polish(monkeypatch):
    order = []
    opinions = [{'model': 'model', 'provider': 'groq', 'claims': [], 'verdict': 'spin', 'intensity': 70}] * 3
    combined = {'verdict': 'spin', 'intensity': 70, 'agreement': '3/3', 'techniques': [
        {**t, 'name': t['category'], 'explanation': 'Opis.'} for t in diagnosis()['techniques']]}
    monkeypatch.setattr(council, 'consult', lambda *a: opinions)
    # Kworum (6.10) ma własne testy (test_council_quorum); tu sprawdzamy kolejność redaktorów, więc kworum jest spełnione.
    monkeypatch.setattr('news.council_quorum.active_core', lambda *a: [])
    monkeypatch.setattr('news.council_quorum.check', lambda *a, **k: {'met': True, 'reason': '', 'members': 3, 'need_members': 3,
                                                                        'core': 0, 'need_core': 0, 'missing_core': []})
    monkeypatch.setattr('news.council_quorum.member_biases', lambda *a, **k: {})
    monkeypatch.setattr(council.registry, 'diversity', lambda *a: {'sufficient': True, 'polish': True})
    monkeypatch.setattr(council, '_members', lambda *a: [])
    monkeypatch.setattr(council, 'combine', lambda *a: combined)
    monkeypatch.setattr(council, 'check_claims', lambda *a: ([], {}))
    monkeypatch.setattr('news.clinic_lab.run_lab', lambda *a: {})
    monkeypatch.setattr(council, 'write', lambda *a: ({'summary': 'Przed korektą.'}, 'writer'))
    monkeypatch.setattr(council, 'review', lambda *a: {'ok': True, 'issues': []})
    def polish(text):
        order.append('polish')
        return {**text, 'summary': GOOD}, 'linguist'
    def edit(full, text):
        order.append('edit')
        assert full['summary'] == GOOD and text == POST
        assert full['claims'] == [] and len(full['techniques']) == 2
        return candidate()
    monkeypatch.setattr(council, 'polish', polish)
    monkeypatch.setattr(plain, 'edit_plain', edit)
    assert council.diagnose({'text': POST}, POST)['plain'] == candidate()
    assert order == ['polish', 'edit']


@pytest.mark.django_db
def test_diagnose_persists_plain_and_clears_it_for_old_provider(monkeypatch):
    from news import clinic, clinic_ai
    from news.test_clinic import fake_diagnosis
    row = SpinDiagnosis.objects.create(post=post(account()))
    result = {**fake_diagnosis(), 'lab': {}, 'plain': candidate()}
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda *a: deepcopy(result))
    monkeypatch.setattr(clinic, 'ensure_x_thread', lambda *a: None)
    monkeypatch.setattr('news.clinic_lab.queue_archive', lambda *a: None)
    clinic.diagnose(row)
    row.refresh_from_db()
    assert row.plain == candidate()
    del result['plain']
    clinic.diagnose(row)
    row.refresh_from_db()
    assert row.plain == {}


@pytest.mark.django_db
def test_reader_failure_reaches_heartbeat_without_fake_note(monkeypatch):
    from news.agent_models import AgentNote
    monkeypatch.setenv('PLAIN_READER_ENABLED', 'true')
    SpinDiagnosis.objects.create(post=post(account()), status='approved', plain=candidate())
    monkeypatch.setattr(plain_reader, 'read_plain', Mock(side_effect=council.ClinicAIError('unavailable')))
    assert plain_reader.run() == {'status': 'ok', 'completed': 0, 'failed': 1}
    assert not AgentNote.objects.exists()
