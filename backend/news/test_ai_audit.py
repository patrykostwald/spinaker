"""All provider interactions are mocked; no real credentials or paid requests."""
import json
from io import StringIO
import pytest
import requests
from django.core.management import call_command
from news.ai_research import research, ResearchError
from news.models import AIResearchCall, Source, ImportState
from news.test_ai_research import provider_result

@pytest.fixture
def configured(db, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','sk-private-test-only')
    monkeypatch.setenv('DR_SPIN_RESEARCH_MODEL','test-model')
    monkeypatch.setenv('DR_SPIN_RESEARCH_ENABLED','true')
    source=Source.objects.create(name='Test source',url='https://example.org')
    return {'example.org':source}

def mock_response(monkeypatch, result, status=200):
    class Response:
        status_code=status
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def iter_content(self,*args): yield json.dumps(result).encode('utf-8')
    monkeypatch.setattr('news.ai_research.requests.post',lambda *args,**kwargs:Response())

def test_audit_observed_metrics_not_request_limits(configured, monkeypatch):
    result=provider_result()
    result.update(model='test-model-version',usage={'input_tokens':71,'output_tokens':23})
    mock_response(monkeypatch,result)
    research('private topic','context',configured)
    audit=AIResearchCall.objects.get()
    assert (audit.input_tokens,audit.output_tokens,audit.web_search_calls)==(71,23,1)
    assert audit.model=='test-model' and audit.response_model=='test-model-version'
    assert audit.status=='completed' and audit.provider_status=='completed'
    assert audit.started_at <= audit.finished_at
    assert 'private topic' not in str(AIResearchCall.objects.values().get())
    assert 'sk-private' not in str(AIResearchCall.objects.values().get())

def test_missing_metrics_and_transport_errors_remain_unknown(configured,monkeypatch):
    mock_response(monkeypatch,provider_result())
    research('private','context',configured)
    audit=AIResearchCall.objects.get()
    assert audit.input_tokens is None and audit.output_tokens is None
    def failure(*args,**kwargs): raise requests.Timeout('sk-private-test-only private topic')
    monkeypatch.setattr('news.ai_research.requests.post',failure)
    with pytest.raises(ResearchError): research('private topic','verify',configured)
    audit=AIResearchCall.objects.first()
    assert audit.status=='transport_error'
    assert audit.input_tokens is None and audit.output_tokens is None and audit.web_search_calls is None
    assert 'private' not in str(AIResearchCall.objects.values().first())

@pytest.mark.parametrize('provider_status,http_status,expected',[('incomplete',200,'invalid_response'),('failed',500,'http_error')])
def test_failed_response_is_audited(configured,monkeypatch,provider_status,http_status,expected):
    result={'status':provider_status,'usage':{'input_tokens':15,'output_tokens':0}}
    mock_response(monkeypatch,result,http_status)
    with pytest.raises(ResearchError): research('private','context',configured)
    audit=AIResearchCall.objects.get()
    assert audit.status==expected and audit.http_status==http_status
    assert audit.web_search_calls is None
    if http_status==200:
        assert audit.input_tokens==15 and audit.output_tokens==0
    else:
        assert audit.input_tokens is None

def test_preflight_read_only_no_secrets_no_provider(configured,monkeypatch):
    monkeypatch.setenv('DR_SPIN_MODEL','private-model-value')
    monkeypatch.setattr('requests.post',lambda *args,**kwargs:pytest.fail('network'))
    AIResearchCall.objects.create(model='test',mode='context',status='completed',input_tokens=15,output_tokens=0,web_search_calls=1)
    AIResearchCall.objects.create(model='test',mode='context',status='transport_error')
    before=(ImportState.objects.count(),AIResearchCall.objects.count())
    output=StringIO()
    call_command('ai_preflight',stdout=output)
    raw=output.getvalue(); data=json.loads(raw)
    assert 'sk-private-test-only' not in raw and 'private-model-value' not in raw
    assert data['configuration']['OPENAI_API_KEY']=='present'
    assert data['allowed_domain_count']==1
    assert data['local_configuration_ready']=={'context':True,'verify':True,'editorial_draft':True}
    usage=data['research_audit_today_utc']
    assert usage['observed_totals']=={'input_tokens':15,'output_tokens':0,'web_search_calls':1}
    assert usage['unknown_metrics']=={'input_tokens':1,'output_tokens':1,'web_search_calls':1}
    assert before==(ImportState.objects.count(),AIResearchCall.objects.count())

def test_preflight_missing_configuration_is_not_ready(db,monkeypatch):
    for name in ('OPENAI_API_KEY','DR_SPIN_RESEARCH_MODEL','DR_SPIN_MODEL','DR_SPIN_RESEARCH_ENABLED'):
        monkeypatch.delenv(name,raising=False)
    output=StringIO();call_command('ai_preflight',stdout=output)
    data=json.loads(output.getvalue())
    assert not any(data['local_configuration_ready'].values())
    assert data['research_audit_today_utc']['observed_totals']['input_tokens'] is None

def test_malformed_metrics_are_unknown_but_observed_zero_is_zero(configured,monkeypatch):
    result={'status':'incomplete','output':[],'usage':{'input_tokens':True,'output_tokens':-1}}
    mock_response(monkeypatch,result)
    with pytest.raises(ResearchError): research('private','context',configured)
    audit=AIResearchCall.objects.get()
    assert audit.input_tokens is None and audit.output_tokens is None
    assert audit.web_search_calls == 0
