import pytest
from django.core.cache import cache
from rest_framework.test import APIRequestFactory, force_authenticate
from types import SimpleNamespace
from news.ai_research import AIResearchView, ResearchError, validate_result, reserve_attempt
from news.models import Source, Article, ArchiveJob

@pytest.fixture
def source(db):
    cache.clear()
    return Source.objects.create(name='Test publisher', url='https://example.org', is_active=True)

@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('DR_SPIN_RESEARCH_ENABLED', 'true')
    monkeypatch.setenv('DR_SPIN_RESEARCH_MODEL', 'test-model')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key-never-used')

def request(data):
    req = APIRequestFactory().post('/api/ai/research/', data, format='json')
    if data.get('mode') == 'verify':
        force_authenticate(req, user=SimpleNamespace(is_authenticated=True, is_staff=True, pk=1))
    return AIResearchView.as_view()(req)

def provider_result(url='https://example.org/a'):
    return {'status':'completed', 'output':[
        {'type':'web_search_call','action':{'sources':[{'url':url}]}},
        {'type':'message','content':[{'type':'output_text','text':'Fakt [1]', 'annotations':[
            {'type':'url_citation','url':url,'title':'Source title','start_index':5,'end_index':8}]}]}]}

def test_disabled_never_calls_provider(source, monkeypatch):
    monkeypatch.delenv('DR_SPIN_RESEARCH_ENABLED', raising=False)
    monkeypatch.setattr('news.ai_research.research', lambda *args: pytest.fail('paid call'))
    assert request({'query':'temat', 'mode':'context'}).status_code == 503

def test_citations_must_be_consulted_and_allowed(source):
    sources = {'example.org':source}
    assert len(validate_result(provider_result(), sources)['sources']) == 1
    result = provider_result()
    result['output'][0]['action']['sources'] = []
    with pytest.raises(ResearchError): validate_result(result,sources)
    with pytest.raises(ResearchError): validate_result(provider_result('https://example.org.evil.test/a'),sources)
    result = provider_result()
    result['output'][1]['content'][0]['annotations'][0]['end_index'] = 99
    with pytest.raises(ResearchError): validate_result(result,sources)

def test_only_urls_enter_archive_not_generated_facts(source, configured, monkeypatch):
    monkeypatch.setattr('news.ai_research.research', lambda *args: validate_result(provider_result(), {'example.org':source}))
    response = request({'query':'temat', 'mode':'context'})
    assert response.status_code == 200
    assert response.data['requires_review'] is True
    assert response.data['sources'][0]['published_date'] is None
    assert Article.objects.count() == 0
    assert ArchiveJob.objects.get().url == 'https://example.org/a'

def test_durable_limit_and_failed_requests_consume_attempt(source, configured, monkeypatch):
    monkeypatch.setenv('DR_SPIN_RESEARCH_DAILY_LIMIT','1')
    assert reserve_attempt()
    cache.clear()
    assert not reserve_attempt()

def test_verify_needs_quote_politician_and_statement_url(source, configured, monkeypatch):
    monkeypatch.setattr('news.ai_research.research', lambda *args: pytest.fail('paid call'))
    assert request({'query':'co z gospodarką', 'mode':'verify'}).status_code == 400
    assert request({'query':'https://x.com/test/status/123', 'mode':'verify','speaker':'Polityk'}).status_code == 400
    assert request({'query':'https://x.com/test', 'mode':'verify','speaker':'Polityk','statement':'To jest test wypowiedzi.'}).status_code == 400

def test_x_url_is_reference_only_in_verify(source, configured, monkeypatch):
    calls=[]
    def fake(query, mode, sources):
        calls.append(query)
        return validate_result(provider_result(),sources)
    monkeypatch.setattr('news.ai_research.research',fake)
    response = request({'query':'https://x.com/test/status/123', 'mode':'verify','speaker':'Polityk','statement':'To jest test wypowiedzi.'})
    assert response.status_code == 200
    assert 'statement_provided_by_user_not_authenticated' in calls[0]
    assert not ArchiveJob.objects.filter(url__contains='x.com').exists()
    assert request({'query':'https://x.com/test/status/123', 'mode':'context'}).status_code == 400

def test_provider_payload_is_bounded_and_no_redirects(source, configured, monkeypatch):
    import json
    from news.ai_research import research
    seen = {}
    class MockResponse:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, *args): yield json.dumps(provider_result()).encode()
    def post(url, **kwargs):
        seen.update(kwargs)
        assert url == 'https://api.openai.com/v1/responses'
        return MockResponse()
    monkeypatch.setattr('news.ai_research.requests.post', post)
    research('topic', 'context', {'example.org':source})
    assert seen['allow_redirects'] is False
    assert seen['json']['max_output_tokens'] == 4000
    assert seen['json']['max_tool_calls'] == 4
    assert seen['json']['tools'][0]['filters']['allowed_domains'] == ['example.org']
    assert seen['json']['store'] is False


def test_no_sources_and_incomplete_response_fail_closed(source):
    with pytest.raises(ResearchError): validate_result({'status':'incomplete'}, {'example.org':source})
    with pytest.raises(ResearchError): validate_result({'status':'completed','output':[]}, {'example.org':source})

def test_timeline_uses_only_stored_publisher_metadata(source, configured, monkeypatch):
    from datetime import datetime, timezone
    article = Article.objects.create(source=source, url='https://example.org/a', title='Publisher title',
        published_date=datetime(2020, 1, 2, 12, tzinfo=timezone.utc), category='article')
    result = validate_result(provider_result(), {'example.org':source})
    result['sections'][0]['text'] = 'Model suggests 2026-09-09 (not trusted metadata)'
    monkeypatch.setattr('news.ai_research.research', lambda *args: result)
    response = request({'query':'topic', 'mode':'context'})
    card = response.data['archive_timeline']['2020-01-02'][0]
    assert card['id'] == article.pk
    assert card['title'] == 'Publisher title'
    article.refresh_from_db()
    assert article.published_date.year == 2020
    assert Article.objects.count() == 1


def test_status_polling_does_not_use_research_throttle(configured):
    factory = APIRequestFactory()
    for _ in range(15):
        assert AIResearchView.as_view()(factory.get('/api/ai/research/')).status_code == 200


def test_verify_nonstaff_denied_before_budget_or_provider(configured, source, monkeypatch):
    from news.models import ImportState, AIResearchCall
    monkeypatch.setattr('news.ai_research.research', lambda *args: pytest.fail('paid call'))
    for user in (None, SimpleNamespace(is_authenticated=True, is_staff=False, pk=2)):
        req = APIRequestFactory().post('/api/ai/research/', {'mode':'verify', 'query':'https://x.com/test/status/123',
            'speaker':'Polityk','statement':'Publiczna wypowiedź do sprawdzenia.'}, format='json')
        if user is not None:
            force_authenticate(req, user=user)
        assert AIResearchView.as_view()(req).status_code == 403
    assert not ImportState.objects.filter(name='web-ai-daily-budget').exists()
    assert AIResearchCall.objects.count() == 0
