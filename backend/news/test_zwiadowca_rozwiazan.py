"""Zwiadowca rozwiązań: obserwatorzy bez sieci (fixtures), linia bazowa i sygnały, zwiad tygodnia z dowodami, odbiorcy
(Rekruter, Dyrygent, Mechanik, Architekt, Prawnik), bezpiecznik i naprawa, plan startowy, Raport pętli."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
import requests
from django.core.cache import cache
from django.core.management import call_command

from news import agents_common, council_recruiter, dyrygent, mechanik, petle_bezpieczniki as fuses, petle_naprawy, pracownia_osint, raport_petli
from news import zwiadowca_rozwiazan as zwiad
from news.agent_models import AgentNote
from news.clinic_models import CouncilRecruitment

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 7, 6, tzinfo=ZoneInfo('Europe/Warsaw'))
FIX = Path(__file__).parent / 'fixtures' / 'zwiadowca'


class Response:
    def __init__(self, data=None, content=b''):
        self._data, self.content, self.status_code = data, content, 200

    def json(self):
        if self._data is None:
            raise ValueError('no json')
        return self._data

    def raise_for_status(self):
        pass


def fixture(name):
    return json.loads((FIX / name).read_text(encoding='utf-8'))


def fake_get(openrouter='openrouter_models.json'):
    def get(url, timeout=None, headers=None, allow_redirects=True, params=None):
        if 'openrouter.ai' in url:
            return Response(fixture(openrouter))
        if 'router.huggingface.co' in url:
            return Response(fixture('hf_router_models.json'))
        if 'huggingface.co/api/models' in url:
            return Response(fixture('hf_trending.json'))
        if 'api.github.com' in url:
            return Response(fixture('github_search.json'))
        if 'dane.gov.pl' in url:
            return Response(fixture('dane_gov.json'))
        if 'data.europa.eu' in url:
            return Response(fixture('eu_search.json'))
        if 'cloudflare.com/changelog' in url:
            return Response(content=(FIX / 'feed.atom').read_bytes())
        raise requests.ConnectionError('offline: ' + url)
    return get


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    for name in ('OPENROUTER_API_KEY', 'GROQ_API_KEY', 'NIM_API_KEY', 'HF_TOKEN', 'INCEPTION_API_KEY', 'GITHUB_TOKEN', 'ZWIADOWCA_FEEDS',
                 'CLINIC_COUNCIL', 'LOOP_REPORT_EMAIL', 'COUNCIL_RECRUITER_EMAIL'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('AGENTS_ENABLED', 'true')
    monkeypatch.setenv('SEBA_ENABLED', 'false')
    monkeypatch.setenv('LOOP_AUTOREPAIR', 'true')
    with patch('django.utils.timezone.now', return_value=NOW), \
         patch('requests.sessions.Session.request', side_effect=AssertionError('Prawdziwa sieć jest zabroniona w testach')), \
         patch('news.social_publish._mail', return_value=True) as mail:
        yield SimpleNamespace(mail=mail)
    cache.clear()


# --- 1. obserwatorzy i sygnały ------------------------------------------------------------------------------------------

def test_watchers_read_public_catalogs_offline(monkeypatch):
    monkeypatch.setattr(zwiad.requests, 'get', fake_get())
    items = {name: watcher() for name, watcher in zwiad.WATCHERS}
    openrouter = {i['id']: i for i in items['openrouter']}
    assert 'openrouter:meta-llama/llama-4-scout:free' in openrouter and openrouter['openrouter:meta-llama/llama-4-scout:free']['free']
    assert 'openrouter:openai/gpt-oss-120b' in openrouter and openrouter['openrouter:openai/gpt-oss-120b']['cheap']  # 0,05 USD/1M
    assert 'openrouter:anthropic/claude-sonnet-4' not in openrouter and 'openrouter:openai/whisper-large-v3' not in openrouter
    assert {i['provider'] for i in items['huggingface'] if i['kind'] == 'provider'} == {'cerebras', 'groq', 'sambanova'}
    assert any(i['id'] == 'hf-trending:speakleash/Bielik-11B-v3-Instruct' for i in items['huggingface'])
    assert [i['url'] for i in items['feeds']] == ['https://developers.cloudflare.com/changelog/2026-10-05-workers-ai/']  # tylko https
    assert {i['id'] for i in items['github']} == {'github:opensanctions/yente', 'github:example/factcheck-tool'}
    assert [i['id'] for i in items['dane-gov']] == ['dane-gov:4711'] and items['dane-gov'][0]['url'] == 'https://dane.gov.pl/pl/datasets/4711'
    assert [i['id'] for i in items['eu-open-data']] == ['eu:eu-lobby-2026']


def test_first_run_is_baseline_then_new_free_model_signals_recruiter_or_owner(monkeypatch):
    monkeypatch.setattr(zwiad.requests, 'get', fake_get())
    first = zwiad.run_watchers(NOW)
    assert first['baseline'] and first['signals'] == 0 and first['new'] > 0
    assert not AgentNote.objects.filter(agent='rozwiazania').exists()
    assert 'openrouter:meta-llama/llama-4-scout:free' in zwiad.load()['known']
    # dzień później: dwa nowe darmowe modele; mamy klucz OpenRouter -> Rekruter, bez maila
    monkeypatch.setenv('OPENROUTER_API_KEY', 'x')
    monkeypatch.setattr(zwiad.requests, 'get', fake_get('openrouter_models_new.json'))
    later = NOW + timedelta(days=1)
    with patch('django.utils.timezone.now', return_value=later):
        second = zwiad.run_watchers(later)
    assert not second['baseline'] and second['signals'] == 2
    signals = AgentNote.objects.filter(agent='rozwiazania', kind='signal').order_by('pk')
    assert {s.scores['consumer'] for s in signals} == {'rekruter'} and all(s.status == 'new' for s in signals)
    assert any('mercury-2.5' in s.title for s in signals)
    # bez klucza dostawcy sygnał idzie do właściciela (tylko on zakłada konta) i wychodzi mailem
    monkeypatch.delenv('OPENROUTER_API_KEY')
    item = {'kind': 'model', 'provider': 'openrouter', 'model': 'zhipu/glm-5:free', 'free': True, 'json': True, 'context': 64000, 'url': 'https://openrouter.ai/zhipu/glm-5'}
    signal = zwiad.signal_for(item)
    assert signal['consumer'] == 'właściciel' and 'OPENROUTER_API_KEY' in signal['why']
    monkeypatch.setattr(agents_common, 'notify', lambda note: True)
    note = zwiad.emit_signal(item, signal, later)
    assert note.scores['level'] == 'owner'
    # drugi przebieg tego samego dnia nie powtarza sygnałów (pozycje już znane)
    with patch('django.utils.timezone.now', return_value=later):
        again = zwiad.run_watchers(later)
    assert again['signals'] == 0 and again['new'] == 0


def test_signal_skips_known_models_small_context_and_non_json():
    assert zwiad.signal_for({'kind': 'model', 'provider': 'openrouter', 'model': 'a:free', 'free': True, 'json': False, 'context': 128000}) is None
    assert zwiad.signal_for({'kind': 'model', 'provider': 'openrouter', 'model': 'a:free', 'free': True, 'json': True, 'context': 8000}) is None
    assert zwiad.signal_for({'kind': 'model', 'provider': 'openrouter', 'model': 'a', 'free': False, 'json': True, 'context': 128000}) is None
    CouncilRecruitment.objects.create(kind='candidate', provider='openrouter', model='known/model:free', decision='rejected')
    assert zwiad.signal_for({'kind': 'model', 'provider': 'openrouter', 'model': 'known/model:free', 'free': True, 'json': True, 'context': 128000}) is None
    hf = zwiad.signal_for({'kind': 'provider', 'id': 'hf-provider:cerebras', 'provider': 'cerebras', 'summary': '3 modele'})
    assert hf['consumer'] == 'mechanik' and hf['level'] == 'info'


def test_watcher_failure_does_not_stop_others(monkeypatch):
    def get(url, **kwargs):
        if 'openrouter.ai' in url:
            raise requests.ConnectionError('down')
        return fake_get()(url, **kwargs)
    monkeypatch.setattr(zwiad.requests, 'get', get)
    result = zwiad.run_watchers(NOW)
    assert result['errors'] == {'openrouter': 'ConnectionError'} and result['items'] > 0


# --- 2. zwiad tygodnia -----------------------------------------------------------------------------------------------------

def seed_recent(monkeypatch):
    monkeypatch.setattr(zwiad.requests, 'get', fake_get('openrouter_models_new.json'))
    zwiad.run_watchers(NOW)


def test_scout_grounds_evidence_dedupes_and_routes(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'x')
    seed_recent(monkeypatch)
    AgentNote.objects.create(agent='rozwiazania', kind='finding', title='stare', body='b',
                             scores={'findings': [{'title': 'Workers AI: darmowa pula dla Llama 4'}]})
    answer = {'summary': 'Trzy rzeczy warte podłączenia.', 'findings': [
        {'title': 'Qwen3 235B za darmo na OpenRouter', 'kind': 'model', 'provider': 'openrouter', 'model': 'qwen/qwen3-235b-a22b:free',
         'unlocks': 'kontekst 40k, zdejmuje limit 50 zapytań OpenRouter w przesiewaniu', 'saving': 'ok. 300 zapytań dziennie', 'legality': 'dozwolone',
         'tos_training': 'nieznane', 'political_content_ok': True, 'effort': 'S', 'hard_rules_ok': True, 'score': 85,
         'evidence_urls': ['https://openrouter.ai/qwen/qwen3-235b-a22b'], 'action': 'rekruter'},
        {'title': 'Workers AI: darmowa pula dla Llama 4', 'kind': 'provider', 'provider': 'cloudflare', 'unlocks': 'x', 'saving': 'y', 'legality': 'dozwolone',
         'tos_training': 'nie trenuje', 'political_content_ok': True, 'effort': 'S', 'hard_rules_ok': True, 'score': 70,
         'evidence_urls': ['https://developers.cloudflare.com/changelog/2026-10-05-workers-ai/'], 'action': 'dyrygent'},  # powtórka previous
        {'title': 'yente do sankcji i PEP', 'kind': 'tool', 'unlocks': 'dopasowanie podmiotów do list sankcyjnych', 'saving': 'bez licencji OpenSanctions API',
         'legality': 'warunkowo', 'tos_training': 'nieznane', 'political_content_ok': True, 'effort': 'M', 'hard_rules_ok': True, 'score': 60,
         'evidence_urls': ['https://github.com/opensanctions/yente'], 'action': 'architekt'},
        {'title': 'Zmyślony dostawca', 'kind': 'provider', 'unlocks': 'x', 'saving': 'y', 'legality': 'dozwolone', 'tos_training': 'nieznane',
         'political_content_ok': True, 'effort': 'S', 'hard_rules_ok': True, 'score': 99, 'evidence_urls': ['https://nie-ma.example/'], 'action': 'dyrygent'},
        {'title': 'Model łamiący zasady', 'kind': 'model', 'provider': 'openrouter', 'model': 'x:free', 'unlocks': 'x', 'saving': 'y', 'legality': 'dozwolone',
         'tos_training': 'nieznane', 'political_content_ok': False, 'effort': 'S', 'hard_rules_ok': False, 'score': 90,
         'evidence_urls': ['https://openrouter.ai/qwen/qwen3-235b-a22b'], 'action': 'rekruter'},
        {'title': 'Rejestr korzyści posłów z dane.gov.pl', 'kind': 'source', 'unlocks': 'korzyści posłów przy profilu', 'saving': 'nowe dane za darmo',
         'legality': 'dozwolone', 'tos_training': 'nieznane', 'political_content_ok': True, 'effort': 'S', 'hard_rules_ok': True, 'score': 75,
         'evidence_urls': ['https://dane.gov.pl/pl/datasets/4711'], 'action': 'architekt'},
    ]}
    monkeypatch.setattr(agents_common, 'ask_any', lambda prompt, data, schema, force=False, exclude=(): (answer, ('inception', 'mercury-2.5')))
    note = zwiad.scout()
    findings = note.scores['findings']
    titles = [f['title'] for f in findings]
    assert 'Zmyślony dostawca' not in titles and 'Workers AI: darmowa pula dla Llama 4' not in titles
    assert titles[0] == 'Qwen3 235B za darmo na OpenRouter' and findings[0]['score'] == 85
    bad = next(f for f in findings if f['title'] == 'Model łamiący zasady')
    assert bad['score'] == 0 and bad['legal_risk']
    yente = next(f for f in findings if f['title'].startswith('yente'))
    assert yente['legal_risk'] and yente['action'] == 'architekt'
    assert note.scores['routed']['rekruter'] == 1 and note.scores['authors'] == ['inception:mercury-2.5']
    assert 'Nowe możliwości tygodnia' in note.title and 'https://openrouter.ai/qwen/qwen3-235b-a22b' in note.sources
    # odbiorcy
    assert zwiad.recruiter_candidates() == [{'provider': 'openrouter', 'model': 'qwen/qwen3-235b-a22b:free', 'context': 0, 'scout': True}]
    monkeypatch.delenv('OPENROUTER_API_KEY')
    assert zwiad.recruiter_candidates() == []  # bez klucza Rekruter nie egzaminuje
    assert zwiad.capacity_lines() == []  # nic dla Dyrygenta: model łamiący zasady (wynik 0) nie trafia do żadnego odbiorcy


def test_scout_waits_without_items():
    with pytest.raises(agents_common.WindowClosed):
        zwiad.scout()


def test_recruiter_discover_takes_scout_queue_as_watched(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'x')
    zwiad.save({'recruiter_queue': [{'provider': 'openrouter', 'model': 'meta-llama/llama-4-scout:free', 'added': '2026-10-06'}]})
    monkeypatch.setattr(council_recruiter, '_get', lambda url, **kwargs: (_ for _ in ()).throw(requests.ConnectionError('offline')))
    found = council_recruiter.discover()
    assert found == [{'provider': 'openrouter', 'model': 'meta-llama/llama-4-scout:free', 'context': 0, 'scout': True}]
    candidates = council_recruiter.sieve(found)
    assert candidates and candidates[0]['watched'] and candidates[0]['company'] == 'Meta'


def test_prawnik_reads_risky_findings_and_architekt_gets_solutions(monkeypatch):
    AgentNote.objects.create(agent='rozwiazania', kind='finding', title='Nowe możliwości', body='b', scores={'findings': [
        {'title': 'Bluesky Jetstream', 'unlocks': 'wpisy polityków bez kosztu X', 'legality': 'warunkowo', 'tos_training': 'nieznane', 'legal_risk': True, 'action': 'architekt'},
        {'title': 'Zwykłe narzędzie', 'unlocks': 'x', 'legality': 'dozwolone', 'tos_training': 'nie trenuje', 'legal_risk': False, 'action': 'architekt'}]})
    assert pracownia_osint.due('prawnik')
    asked = {}

    def ask(prompt, data, schema, force=False, checker=False):
        asked.update(data)
        if 'proposals' in data:
            return {'verdicts': [{'n': 0, 'verdict': 'warunkowo', 'why': 'tylko konta publiczne', 'conditions': 'lista kont'}]}
        return {'summary': 'plan', 'items': []}
    monkeypatch.setattr(pracownia_osint, '_ask', ask)
    review = pracownia_osint.prawnik()
    assert [p['what'][:26] for p in asked['proposals']] == ['Rozwiązanie: Bluesky Jetst']
    assert review.scores['verdicts'][0]['verdict'] == 'warunkowo'
    pracownia_osint.architekt()
    assert asked['solutions']['findings'][0]['title'] == 'Bluesky Jetstream' and 'authors' not in asked['solutions']


def test_mechanik_notes_scout_fallbacks_and_dyrygent_plan_lists_capacity(monkeypatch):
    zwiad.save({'recent': [{'kind': 'model', 'provider': 'hf', 'model': 'openai/gpt-oss-120b:cerebras', 'url': 'u', 'seen': '2026-10-06'}],
                'capacity': [{'title': 'Cerebras Cloud', 'provider': 'cerebras', 'saving': '1 mln tokenów dziennie', 'unlocks': 'x', 'configured': False,
                              'added': '2026-10-06', 'url': 'https://cerebras.ai'}]})
    assert zwiad.fallbacks('groq', 'openai/gpt-oss-120b') == ['hf:openai/gpt-oss-120b:cerebras']
    assert zwiad.fallbacks('hf', 'openai/gpt-oss-120b:cerebras') == []
    monkeypatch.setenv('GROQ_API_KEY', 'x')
    from news.clinic_models import CouncilSeat
    CouncilSeat.objects.create(provider='groq', model='openai/gpt-oss-120b', last_error='groq: http_404')
    monkeypatch.setattr(mechanik, 'provider_models', lambda s: {'llama-3.3-70b-versatile'})
    assert mechanik.step()['results'] == [('openai/gpt-oss-120b', 'brak następcy')]
    from news.models import ImportState
    assert 'zamienniki Zwiadowcy: hf:openai/gpt-oss-120b:cerebras' in ImportState.objects.get(name=mechanik.LOG).cursor['rows'][0]['wynik']
    plan = dyrygent.plan(force=True)
    assert 'Wolne moce poza Konsylium (Zwiadowca rozwiązań):' in plan.body and 'Cerebras Cloud: 1 mln tokenów dziennie (bez klucza)' in plan.body


# --- 3. bezpiecznik, naprawa, raport ---------------------------------------------------------------------------------------

def signal(consumer, model, hours, **item):
    row = AgentNote.objects.create(agent='rozwiazania', kind='signal', title=f'Nowy darmowy model: {model}', body='b',
                                   scores={'consumer': consumer, 'level': 'info', 'consumed': '', 'item': {'provider': 'openrouter', 'model': model, **item}})
    AgentNote.objects.filter(pk=row.pk).update(created_at=NOW - timedelta(hours=hours))
    return AgentNote.objects.get(pk=row.pk)


def test_fuse_fires_after_sla_and_repair_closes_consumed_then_retries_recruiter(monkeypatch):
    taken = signal('rekruter', 'a/b:free', hours=100)
    waiting = signal('rekruter', 'c/d:free', hours=100)
    fresh = signal('rekruter', 'e/f:free', hours=10)
    owner = signal('właściciel', 'g/h:free', hours=100)
    CouncilRecruitment.objects.create(kind='candidate', provider='openrouter', model='a/b:free', decision='would_reject')
    assert fuses.scout_signals(NOW)[0]['details'] == {'signals': 3, 'hours': 72, 'consumers': ['rekruter', 'właściciel']}
    sent = []
    with patch('config.celery.app.send_task', side_effect=lambda *a, **k: sent.append(a[0])):
        result = petle_naprawy.remedy('check_scout_signals', NOW)
    assert result == {'petle:scout-signals': 'retried'} and sent == ['news.tasks.council_recruiter_task']
    taken.refresh_from_db(), waiting.refresh_from_db(), fresh.refresh_from_db(), owner.refresh_from_db()
    assert taken.status == 'done' and taken.scores['consumed'] == 'rekruter'
    assert waiting.status == 'new' and fresh.status == 'new' and owner.status == 'new'
    assert fuses.scout_signals(NOW)[0]['details']['signals'] == 2
    # naprawa w toku wstrzymuje alarm Dyżurnego; drugi raz tego dnia Rekruter nie jest ponawiany
    assert petle_naprawy.suppressed('petle:scout-signals', NOW)
    with patch('config.celery.app.send_task', side_effect=AssertionError('tylko raz na dobę')):
        assert petle_naprawy.remedy('check_scout_signals', NOW)['petle:scout-signals'] == 'retried-again'
    # klucz dodany: sygnał dla właściciela zamyka się sam
    monkeypatch.setenv('OPENROUTER_API_KEY', 'x')
    assert zwiad.mark_consumed(NOW) == 1 and AgentNote.objects.get(pk=owner.pk).scores['consumed'] == 'właściciel (klucz dodany)'


def test_fuse_registered_and_contract_consistent():
    assert fuses.check_scout_signals in fuses.CHECKS
    c = raport_petli.BY_KEY['rozwiazania']
    assert c['consumer'] == 'agent:architekt' and c['agents'] == ('rozwiazania',) and c['category'] == 'agenci'
    from news.daily_schedule import BEAT_PLAN
    assert BEAT_PLAN['zwiadowca-daily'] == ('zwiadowca_rozwiazan_task', {'hour': 5, 'minute': 40})
    assert BEAT_PLAN['zwiadowca-weekly'][0] == 'zwiadowca_zwiad_task' and dyrygent.AI_TASKS['zwiadowca_zwiad_task'] == 'rozwój'


def test_raport_petli_section_new_opportunities():
    AgentNote.objects.create(agent='rozwiazania', kind='finding', title='Nowe możliwości tygodnia: 1', body='b', scores={'findings': [
        {'title': 'Cerebras za darmo', 'score': 88, 'action': 'właściciel', 'saving': '1 mln tokenów dziennie', 'evidence_urls': ['https://cerebras.ai/']}]})
    signal('rekruter', 'x/y:free', hours=1)
    text = raport_petli.text(raport_petli.build(NOW))
    assert '== Nowe możliwości tygodnia (Zwiadowca rozwiązań) ==' in text
    assert '- 88/100 -> właściciel: Cerebras za darmo (1 mln tokenów dziennie) https://cerebras.ai/' in text
    assert '- SYGNAŁ czeka na: rekruter: Nowy darmowy model: x/y:free' in text
    assert raport_petli.loop_state(raport_petli.BY_KEY['rozwiazania'], NOW)['outputs_24h'] == 2


def test_finding_consumed_when_architekt_plans_after_it():
    note = AgentNote.objects.create(agent='rozwiazania', kind='finding', title='f', body='b', scores={'findings': []})
    AgentNote.objects.filter(pk=note.pk).update(created_at=NOW - timedelta(days=2))
    assert zwiad.mark_consumed(NOW) == 0
    AgentNote.objects.create(agent='architekt', kind='report', title='Plan', body='b')
    assert zwiad.mark_consumed(NOW) == 1 and AgentNote.objects.get(pk=note.pk).scores['consumed'] == 'architekt'


# --- 4. plan startowy i zadania -------------------------------------------------------------------------------------------

def test_plan_offline_shows_gap_between_used_and_known_free(monkeypatch, capsys):
    monkeypatch.setenv('GROQ_API_KEY', 'x')
    plan = zwiad.plan()
    by = {r['service']: r['status'] for r in plan['providers']}
    assert by['groq'] == 'podłączone' and by['openrouter'] == 'w kodzie, bez klucza' and by['cerebras'] == 'nie używamy'
    assert {g['service'] for g in plan['gaps']} >= {'cerebras', 'sambanova', 'openrouter'}
    assert any(d['name'].startswith('GUS BDL') for d in plan['data_gaps'])
    call_command('zwiadowca_start', '--plan')
    out = capsys.readouterr().out
    assert 'linia bazowa (bez sieci' in out and '[podłączone] Groq' in out and 'Cerebras Cloud (CEREBRAS_API_KEY)' in out
    assert 'GITHUB_TOKEN' in out and 'Inception Labs' in out


def test_tasks_gate_on_agents_flag_and_report_produced(monkeypatch):
    from news import tasks
    monkeypatch.setenv('AGENTS_ENABLED', 'false')
    assert tasks.zwiadowca_rozwiazan_task() == {'status': 'disabled'} and tasks.zwiadowca_zwiad_task() == {'status': 'disabled'}
    monkeypatch.setenv('AGENTS_ENABLED', 'true')
    monkeypatch.setattr(zwiad.requests, 'get', fake_get())
    result = tasks.zwiadowca_rozwiazan_task()
    assert result['status'] == 'ok' and result['produced'] == 0 and result['baseline'] and result['errors'] == 0
    monkeypatch.setattr(agents_common, 'ask_any', lambda *a, **k: ({'summary': 'nic nowego', 'findings': []}, ('inception', 'mercury-2.5')))
    weekly = tasks.zwiadowca_zwiad_task()  # pozycje z linii bazowej są materiałem zwiadu
    assert weekly['status'] == 'ok' and weekly['produced'] == 1 and weekly['findings'] == 0
