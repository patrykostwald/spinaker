"""Integracje testowane wyłącznie atrapami; każde niezaplanowane połączenie jest błędem."""
import json
from io import StringIO
from unittest.mock import Mock

import pytest
import requests
from celery.exceptions import Retry
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

from news import clinic_council as council, clinic_lab as lab, council_registry as registry
from news.clinic_ai import ClinicAIError
from news.clinic_models import CouncilCharterAcceptance, SpinDiagnosis
from news.council_charter import charter

NEW = [
    ('mistral', 'mistral-small-latest', 'https://api.mistral.ai/v1/chat/completions'),
    ('openrouter', 'meta-llama/llama-3.3-70b-instruct:free', 'https://openrouter.ai/api/v1/chat/completions'),
    ('cloudflare', '@cf/meta/llama-3.3-70b-instruct-fp8-fast', 'https://api.cloudflare.com/client/v4/accounts/account/ai/v1/chat/completions'),
    ('hf', 'speakleash/Bielik-11B-v3.0-Instruct:publicai', 'https://router.huggingface.co/v1/chat/completions'),
    ('pllum', 'CYFRAGOVPL/PLLuM-12B-chat-2512', 'https://pllum.example/v1/chat/completions'),
]


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    cache.clear()
    for key in [*registry.KEYS.values(), 'FACTCHECK_API_KEY', 'FIRECRAWL_API_KEY', 'GUS_BDL_KEY',
                'IA_S3_ACCESS', 'IA_S3_SECRET', 'CLOUDFLARE_ACCOUNT_ID', 'PLLUM_API_URL',
                'CLINIC_COUNCIL', 'CLINIC_ESCALATE']:
        monkeypatch.delenv(key, raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('Prawdziwa sieć jest zabroniona w testach')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    yield
    cache.clear()


def configure(monkeypatch, service):
    monkeypatch.setenv(registry.KEYS[service], 'test-key')
    monkeypatch.setenv('CLOUDFLARE_ACCOUNT_ID', 'account')
    monkeypatch.setenv('PLLUM_API_URL', 'https://pllum.example/v1/chat/completions')


def response(data, status=200):
    result = Mock(status_code=status)
    result.json.return_value = data
    result.raise_for_status.side_effect = requests.HTTPError() if status >= 400 else None
    return result


@pytest.mark.parametrize('service,model,url', NEW)
def test_provider_wire_protocol(monkeypatch, service, model, url):
    configure(monkeypatch, service)
    post = Mock(return_value=response({'choices': [{'message': {'content': '```json\n{"ok": true}\n```'}}]}))
    monkeypatch.setattr(council.requests, 'post', post)
    assert council.ask((service, model), 'system', 'user', {}) == {'ok': True}
    args, kw = post.call_args
    assert args == (url,)
    assert kw['headers']['Authorization'] == 'Bearer test-key'
    assert kw['json']['model'] == model
    assert kw['timeout'] == (5, 90)
    assert registry.CHARTER_SUMMARY in kw['json']['messages'][0]['content']
    if service == 'openrouter':
        assert kw['headers']['HTTP-Referer'] == 'https://spin.clinic'
        assert kw['headers']['X-Title'] == 'spin.clinic'


@pytest.mark.parametrize('service,model,url', NEW)
def test_missing_key_skips_without_network(service, model, url):
    assert not registry.available((service, model))
    assert registry.select_members([(service, model)]) == []
    with pytest.raises(ClinicAIError):
        council.ask((service, model), '', '', {})


@pytest.mark.parametrize('service,model,url', NEW)
def test_provider_invalid_json_and_timeout(monkeypatch, service, model, url):
    configure(monkeypatch, service)
    post = Mock(return_value=response({'choices': [{'message': {'content': '{invalid}'}}]}))
    monkeypatch.setattr(council.requests, 'post', post)
    with pytest.raises(ClinicAIError):
        council.ask((service, model), '', '', {})
    post.side_effect = requests.Timeout()
    with pytest.raises(ClinicAIError):
        council.ask((service, model), '', '', {})


@pytest.mark.parametrize('service,model,url', NEW)
@pytest.mark.parametrize('status', [429, 500])
def test_http_failure_is_not_a_zero_vote(monkeypatch, service, model, url, status):
    configure(monkeypatch, service)
    post = Mock(return_value=response({}, status))
    monkeypatch.setattr(council.requests, 'post', post)
    opinion = council._opinion((service, model), 'tekst', '')
    assert opinion['status'] == 'brak odpowiedzi'
    assert 'intensity' not in opinion and 'verdict' not in opinion
    assert post.call_count == 1


@pytest.mark.parametrize('raw', [{}, {'intensity': 'błąd'}, {'choices': []}])
def test_malformed_answer_is_not_zero(monkeypatch, raw):
    monkeypatch.setattr(council, 'ask', lambda *a, **kw: raw)
    assert council._opinion(('mistral', 'mistral-small-latest'), '', '')['status'] == 'brak odpowiedzi'


def test_diverse_selection_and_daily_limit(monkeypatch):
    for service in registry.KEYS:
        configure(monkeypatch, service)
    candidates = council._members('CLINIC_COUNCIL', council.DEFAULT_COUNCIL)
    selected = registry.select_members(candidates)
    assert len(selected) == 4
    assert registry.diversity(selected)['companies'] >= 3
    assert any(registry.is_polish(m) for m in selected)
    assert all(m[0] != 'openrouter' for m in selected)
    polish = next(m for m in selected if m[0] == 'hf')
    monkeypatch.setenv('CLINIC_HF_DAILY_LIMIT', '1')
    assert registry.reserve(polish)
    assert not registry.available(polish)
    # PLLuM zniknął z Hugging Face (30.09.2026): po limicie Bielika skład działa dalej, bez modelu polskiego
    fallback = registry.select_members(candidates)
    assert len(fallback) >= 3 and not any(registry.is_polish(m) for m in fallback)
    assert registry.metadata(('cloudflare', '@cf/meta/llama-3.3'))['company'] == registry.metadata(('openrouter', 'meta-llama/llama-3.3:free'))['company']


def test_cloudflare_and_pllum_require_complete_configuration(monkeypatch):
    monkeypatch.setenv('CLOUDFLARE_AI_TOKEN', 'test')
    monkeypatch.setenv('PLLUM_API_KEY', 'test')
    assert not registry.configured(('cloudflare', 'llama'))
    assert not registry.configured(('pllum', 'PLLuM'))


def test_openrouter_rejects_paid_model(monkeypatch):
    configure(monkeypatch, 'openrouter')
    assert not registry.configured(('openrouter', 'meta-llama/llama-3.3'))


def test_consult_replaces_failure_and_keeps_record(monkeypatch):
    for service in registry.KEYS:
        configure(monkeypatch, service)
    def fake(member, *a, **kw):
        if member[0] == 'groq':
            raise ClinicAIError('http_429')
        return {'verdict': 'partial', 'intensity': 50, 'techniques': [], 'claims': []}
    monkeypatch.setattr(council, 'ask', fake)
    rows = council.consult('tekst', '')
    assert any(r['status'] == 'brak odpowiedzi' for r in rows)
    good = [(r['provider'], r['model']) for r in rows if r['status'] == 'odpowiedział']
    assert registry.diversity(good)['sufficient']
    assert council.combine(rows)['intensity'] == 50


@pytest.mark.parametrize('kind', ['sentiment', 'hate_speech'])
def test_hf_classification_and_cache(monkeypatch, kind):
    monkeypatch.setenv('HF_TOKEN', 'test')
    request = Mock(return_value=response([[{'label': 'negative', 'score': .91}, {'label': 'neutral', 'score': .09}]]))
    monkeypatch.setattr(lab.requests, 'request', request)
    result = lab.classify('tekst', kind)
    assert result['label'] == 'negative' and result['confidence'] == .91
    assert request.call_args.args == ('POST', 'https://router.huggingface.co/hf-inference/models/' + lab.HF_MODELS[kind])
    assert request.call_args.kwargs['headers'] == {'Authorization': 'Bearer test'}
    assert lab.classify('tekst', kind) == result
    assert request.call_count == 1


def test_classification_scope_is_explicit(monkeypatch):
    monkeypatch.setenv('HF_TOKEN', 'test')
    request = Mock(return_value=response([{'label': 'positive', 'score': .8}]))
    monkeypatch.setattr(lab.requests, 'request', request)
    result = lab.classify('Długi tekst. ' * 100, 'sentiment')
    assert result['truncated'] is True
    assert len(request.call_args.kwargs['json']['inputs'].encode()) <= 480
    assert result['analyzed_chars'] == len(request.call_args.kwargs['json']['inputs'])


def test_lab_timeout_and_missing_keys_do_not_block(monkeypatch):
    monkeypatch.setenv('HF_TOKEN', 'test')
    monkeypatch.setattr(lab.requests, 'request', Mock(side_effect=requests.Timeout()))
    result = lab.run_lab('Tragedia!', [{'claim': 'W Polsce w 2020 r. było 5 mln osób.', 'sources': []}])
    assert result['sentiment']['status'] == 'brak odpowiedzi'
    assert result['hate_speech']['status'] == 'brak odpowiedzi'
    assert result['loaded_words']['count'] > 0
    assert result['factcheck:0'] == [] and result['gus:0'] == []


def test_fact_checks_join_sources_without_claiming_confirmation(monkeypatch):
    monkeypatch.setenv('FACTCHECK_API_KEY', 'test')
    request = Mock(return_value=response({'claims': [{'text': 'Podobne twierdzenie', 'claimReview': [
        {'publisher': {'name': 'Demagog'}, 'textualRating': 'Fałsz', 'url': 'https://demagog.org.pl/fact', 'title': 'Ocena'}]}]}))
    monkeypatch.setattr(lab.requests, 'request', request)
    claims = [{'claim': 'Twierdzenie', 'assessment': 'unverified', 'sources': []}]
    result = lab.run_lab('tekst', claims)
    assert result['factcheck:0'][0]['publisher'] == 'Demagog'
    assert claims[0]['sources'][0]['type'] == 'istniejący fact-check'
    assert claims[0]['assessment'] == 'unverified'
    assert request.call_args.kwargs['params']['languageCode'] == 'pl'


def test_firecrawl_only_quotes_and_three_requests(monkeypatch):
    monkeypatch.setenv('FIRECRAWL_API_KEY', 'test')
    request = Mock(return_value=response({'success': True, 'data': {'markdown': 'Dokładny cytat ze źródła'}}))
    monkeypatch.setattr(lab.requests, 'request', request)
    claims = [{'claim': 'test', 'sources': [{'url': f'https://example.org/{i}', 'quote': 'Dokładny cytat ze źródła'} for i in range(5)]}]
    result = lab.run_lab('tekst', claims)
    assert request.call_count == 3
    assert result['quote:0']['quote_found'] is True
    assert request.call_args.kwargs['json']['formats'] == ['markdown']
    assert lab.scrape_quote('http://127.0.0.1/a', 'quote')['status'] == 'pominięto'


def test_firecrawl_monthly_budget(monkeypatch):
    from django.utils import timezone
    monkeypatch.setenv('FIRECRAWL_API_KEY', 'test')
    cache.set(f'clinic-lab:firecrawl:{timezone.now():%Y-%m}', 1000)
    assert lab.scrape_quote('https://example.org/', 'quote')['status'] == 'limit'


def test_checked_sources_keep_quotes_only_for_search_results():
    url = 'https://example.org/source'
    result = council._checked({'claims': [{'claim': 'Twierdzenie', 'assessment': 'supported', 'sources': [
        {'url': url, 'quote': 'Cytat do sprawdzenia'}, {'url': 'https://invented.example/', 'quote': 'Fałszywy cytat'}]}]}, {url: 'Źródło'})
    assert result[0]['sources'] == [{'url': url, 'title': 'Źródło', 'quote': 'Cytat do sprawdzenia'}]


def test_gus_exact_metric_country_and_year(monkeypatch):
    monkeypatch.setenv('GUS_BDL_KEY', 'test')
    request = Mock(side_effect=[response({'results': [{'id': 123, 'n1': 'stopa bezrobocia rejestrowanego', 'n2': 'ogółem'}]}),
                               response({'results': [{'name': 'POLSKA', 'values': [{'year': 2024, 'val': 5.1}]}]})])
    monkeypatch.setattr(lab.requests, 'request', request)
    found = lab.gus_sources('W Polsce stopa bezrobocia rejestrowanego wynosiła 5,1% w 2024 roku.')
    assert found[0]['value'] == 5.1 and found[0]['year'] == 2024
    assert request.call_args.kwargs['headers'] == {'X-ClientId': 'test'}
    assert lab.gus_sources('Stopa bezrobocia w Krakowie wynosiła 5%.') == []


def test_gus_ambiguous_variables_produce_no_evidence(monkeypatch):
    monkeypatch.setenv('GUS_BDL_KEY', 'test')
    request = Mock(return_value=response({'results': [{'id': i, 'n1': 'stopa bezrobocia rejestrowanego'} for i in (1, 2)]}))
    monkeypatch.setattr(lab.requests, 'request', request)
    assert lab.gus_sources('W Polsce stopa bezrobocia rejestrowanego w 2024 r. to 5%.') == []
    assert request.call_count == 1


@pytest.mark.django_db
def test_wayback_job_poll_and_archive_field(monkeypatch):
    from news.tasks import clinic_archive_task
    from news.test_clinic import account, post
    row = post(account())
    monkeypatch.setenv('IA_S3_ACCESS', 'access')
    monkeypatch.setenv('IA_S3_SECRET', 'secret')
    request = Mock(return_value=response({'job_id': 'spn-test'}))
    monkeypatch.setattr(lab.requests, 'request', request)
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(clinic_archive_task, 'retry', retry)
    with pytest.raises(Retry):
        clinic_archive_task.run(row.pk)
    assert retry.call_args.kwargs['args'] == [row.pk, 'spn-test']
    assert request.call_args.kwargs['headers']['Authorization'] == 'LOW access:secret'
    assert request.call_args.kwargs['data']['url'] == row.url
    cache.delete('clinic-archive:spacing')
    request.return_value = response({'status': 'success', 'timestamp': '20260929120000'})
    clinic_archive_task.run(row.pk, 'spn-test')
    row.refresh_from_db()
    assert row.archive_url == 'https://web.archive.org/web/20260929120000/' + row.url
    assert request.call_args.args[1].endswith('/save/status/spn-test')
    clinic_archive_task.run(row.pk)
    assert request.call_count == 2


@pytest.mark.django_db
def test_wayback_spacing_retries_without_request(monkeypatch):
    from news.tasks import clinic_archive_task
    from news.test_clinic import account, post
    row = post(account())
    cache.set('clinic-archive:spacing', 1)
    monkeypatch.setattr(clinic_archive_task, 'retry', Mock(side_effect=Retry()))
    with pytest.raises(Retry):
        clinic_archive_task.run(row.pk)


@pytest.mark.django_db
def test_archive_queue_deduplicates_and_broker_failure_is_optional(monkeypatch):
    from news.tasks import clinic_archive_task
    from news.test_clinic import account, post
    row = post(account())
    monkeypatch.setenv('IA_S3_ACCESS', 'access')
    monkeypatch.setenv('IA_S3_SECRET', 'secret')
    send = Mock(side_effect=OSError('broker unavailable'))
    monkeypatch.setattr(clinic_archive_task, 'apply_async', send)
    lab.queue_archive(row)
    send.side_effect = None
    lab.queue_archive(row)
    lab.queue_archive(row)
    assert send.call_count == 2
    assert send.call_args.kwargs == {'args': [row.pk], 'queue': 'clinic_archive'}


@pytest.mark.django_db
def test_charter_dry_run_has_no_writes_or_api(monkeypatch):
    configure(monkeypatch, 'hf')
    out = StringIO()
    call_command('council_charter', dry_run=True, stdout=out)
    assert 'Bielik' in out.getvalue()
    assert CouncilCharterAcceptance.objects.count() == 0
    assert len(registry.CHARTER_SUMMARY) <= 600


@pytest.mark.django_db
def test_charter_acceptance_and_public_endpoint(monkeypatch):
    from news.management.commands import council_charter as command
    configure(monkeypatch, 'hf')
    answer = {'accepts': True, 'statement': 'Przyjmuję wszystkie zasady Karty.'}
    ask = Mock(return_value=answer)
    monkeypatch.setattr(command, 'ask', ask)
    call_command('council_charter', stdout=StringIO())
    assert ask.call_args.args[2] == charter()[0]
    saved = CouncilCharterAcceptance.objects.get(model__icontains='bielik')
    assert saved.response == answer and saved.company == 'SpeakLeash / Cyfronet'
    data = APIClient().get('/api/clinic/council/').json()
    member = next(m for m in data['members'] if 'bielik' in m['model'].lower())
    assert member['charter']['accepts'] is True
    assert 'językoznawca' in member['roles']
    saved.charter_hash = 'old'
    saved.save()
    data = APIClient().get('/api/clinic/council/').json()
    assert next(m for m in data['members'] if 'bielik' in m['model'].lower())['charter'] is None


@pytest.mark.django_db
def test_lab_persistence_and_scan(monkeypatch):
    from news import clinic, clinic_ai
    from news.clinic_scan import scan_data
    from news.test_clinic import account, post, fake_diagnosis
    row = SpinDiagnosis.objects.create(post=post(account()))
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda *a: {**fake_diagnosis(), 'lab': {'sentiment': {'label': 'neutral'}}})
    monkeypatch.setattr(clinic, 'ensure_x_thread', lambda *a: None)
    clinic.diagnose(row)
    row.refresh_from_db()
    assert scan_data(row)['lab'] == row.lab == {'sentiment': {'label': 'neutral'}}


@pytest.mark.django_db
def test_failed_diagnosis_keeps_unanswered_members(monkeypatch):
    from news import clinic, clinic_ai
    from news.test_clinic import account, post
    row = SpinDiagnosis.objects.create(post=post(account()))
    failed = {**registry.metadata(('mistral', 'mistral-small-latest')), 'status': 'brak odpowiedzi'}
    monkeypatch.setattr(council, 'consult', lambda *a: [failed])
    monkeypatch.setattr(clinic_ai, 'diagnose', lambda *a: council.diagnose({'text': 'tekst'}, 'tekst'))
    clinic.diagnose(row)
    row.refresh_from_db()
    assert row.status == 'failed'
    assert row.usage['council']['members'] == [failed]


def test_scan_ignores_unanswered_member_scores():
    from types import SimpleNamespace
    from news.clinic_scan import scan_data
    row = SimpleNamespace(techniques=[], claims=[], x_thread=[], pk=1, diagnosed_at=None, verdict='partial',
                          post=SimpleNamespace(text='', media=[], account=SimpleNamespace(display_name='', handle='test')),
                          usage={'council': {'members': [{'model': 'mistral', 'status': 'brak odpowiedzi'},
                                                        {'model': 'bielik', 'verdict': 'partial', 'intensity': 50}]}})
    result = scan_data(row)['council']
    assert result['verdict_agreement'] == '1/1' and result['range'] == [50, 50]


def test_fact_check_falls_back_to_claude_when_gemini_fails(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'x')

    def no_money(*args, **kwargs):
        raise council.ClinicAIError('gemini_402: brak środków')

    monkeypatch.setattr(council.clinic_ai, '_call_gemini', no_money)
    monkeypatch.setattr(council, 'claude_check', lambda claims: ([{'claim': claims[0], 'assessment': 'true', 'sources': []}], {'model': 'claude'}))
    claims, usage = council.check_claims(['PKB wzrósł o 3%'])
    assert usage == {'model': 'claude'} and claims[0]['assessment'] == 'true'
    monkeypatch.setattr(council, 'claude_check', lambda claims: None)
    claims, usage = council.check_claims(['PKB wzrósł o 3%'])
    assert usage == {} and claims[0]['assessment'] == 'unverified'


def test_escalation_needs_flag_but_fallback_does_not(monkeypatch):
    monkeypatch.delenv('CLINIC_ESCALATE', raising=False)
    monkeypatch.setattr(council, 'claude_check', lambda claims: ([], {'model': 'claude'}))
    assert council.escalate_claims(['x']) is None
    monkeypatch.setenv('CLINIC_ESCALATE', 'claude')
    assert council.escalate_claims(['x']) == ([], {'model': 'claude'})


def test_council_usage_is_priced_by_fact_check_model_not_opus():
    from news.clinic_ai import cost_usd
    tokens = {'input_tokens': 10000, 'output_tokens': 2000, 'web_search_requests': 1}
    old = cost_usd({**tokens, 'model': 'konsylium: gpt-oss-20b, qwen3.8-27b, Bielik-11B', 'council': {'escalated': False}})
    assert old == cost_usd({**tokens, 'model': 'gemini-3.8-flash'})
    claude = cost_usd({**tokens, 'model': 'konsylium: gpt-oss-20b', 'check_model': 'claude-sonnet-5'})
    assert claude == cost_usd({**tokens, 'model': 'claude-sonnet-5'}) < cost_usd({**tokens, 'model': 'claude-opus'})


def test_free_fact_check_uses_only_search_result_sources(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'g')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    cache.clear()
    content = json.dumps({'claims': [{'claim': 'PKB wzrósł o 3%', 'assessment': 'supported', 'explanation': 'GUS.',
                                      'sources': [{'url': 'https://stat.gov.pl/pkb', 'title': 'GUS'},
                                                  {'url': 'https://zmyslone.pl/x', 'title': 'x'}]}]})
    payload = {'choices': [{'message': {'content': content, 'executed_tools': [
        {'type': 'search', 'search_results': {'results': [{'title': 'GUS — PKB', 'url': 'https://stat.gov.pl/pkb'}]}}]}}],
        'usage': {'total_tokens': 900}}
    monkeypatch.setattr(council.requests, 'post', lambda *a, **k: Mock(status_code=200, json=lambda: payload))
    monkeypatch.setattr(council, 'claude_check', lambda claims: (_ for _ in ()).throw(AssertionError('paid path')))
    claims, usage = council.check_claims(['PKB wzrósł o 3%'])
    assert claims[0]['assessment'] == 'supported' and [s['url'] for s in claims[0]['sources']] == ['https://stat.gov.pl/pkb']
    assert usage['free'] is True and usage['input_tokens'] == 0


def test_free_fact_check_without_sources_falls_through(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'g')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    cache.clear()
    payload = {'choices': [{'message': {'content': json.dumps({'claims': [{'claim': 'x', 'assessment': 'true', 'sources': []}]})}}]}
    monkeypatch.setattr(council.requests, 'post', lambda *a, **k: Mock(status_code=200, json=lambda: payload))
    monkeypatch.setattr(council, 'claude_check', lambda claims: ([{'claim': 'x', 'assessment': 'false', 'sources': []}], {'model': 'claude'}))
    assert council.check_claims(['x'])[1] == {'model': 'claude'}


def test_json_answer_with_trailing_text_is_read():
    assert council._json('Oto ocena: {"verdict": "spin", "intensity": 60} Uwaga: {dodatkowy komentarz}') == {'verdict': 'spin', 'intensity': 60}


def test_json_answer_with_literal_newlines_in_strings_is_read():
    raw = '{"headline": "Tytuł", "analysis": "Pierwszy akapit.\nDrugi akapit."}'
    assert council._json(raw)['analysis'] == 'Pierwszy akapit.\nDrugi akapit.'
