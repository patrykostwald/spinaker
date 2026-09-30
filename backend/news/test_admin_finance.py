from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from news import admin_finance as finance
from news.clinic_models import ClinicDailyMessage, ClinicInterview, CouncilSeat, SpinDiagnosis
from news.models import AIResearchCall, ImportState
from news.political_models import PoliticalAccount, PoliticalPost, PoliticalRead
from news.wallet_models import WalletBalance

NOW = datetime(2026, 9, 30, 14, 0, tzinfo=ZoneInfo('Europe/Warsaw'))


@pytest.fixture(autouse=True)
def isolated_cache_and_network():
    cache.clear()
    with patch.dict('os.environ', {'OPENROUTER_API_KEY': ''}), patch('requests.get', side_effect=AssertionError('No network in tests')):
        yield
    cache.clear()


@pytest.fixture
def staff(db):
    client = APIClient()
    client.force_authenticate(get_user_model().objects.create_user('finance049', is_staff=True))
    return client


def diagnosis(stamp, usage, identifier='491'):
    account, _ = PoliticalAccount.objects.get_or_create(user_id='49', defaults={'handle': 'test049'})
    post = PoliticalPost.objects.create(account=account, post_id=identifier, published_at=stamp, fetched_at=stamp)
    return SpinDiagnosis.objects.create(post=post, diagnosed_at=stamp, usage=usage)


@pytest.mark.django_db
def test_wallet_permissions_validation_and_csrf(staff):
    data = {'provider': 'gemini', 'amount': '20', 'currency': 'USD', 'recorded_at': (NOW - timedelta(days=1)).isoformat()}
    anonymous = APIClient()
    assert anonymous.post('/api/admin/wallets/', data, format='json').status_code == 403
    anonymous.force_authenticate(get_user_model().objects.create_user('regular049'))
    assert anonymous.post('/api/admin/wallets/', data, format='json').status_code == 403
    for change in ({'amount': '-1'}, {'amount': 'NaN'}, {'provider': 'invalid'}, {'currency': 'BTC'}, {'recorded_at': '2999-01-01T12:00:00Z'}):
        assert staff.post('/api/admin/wallets/', {**data, **change}, format='json').status_code == 400
    user = get_user_model().objects.create_user('session049', is_staff=True)
    session = APIClient(enforce_csrf_checks=True)
    session.force_login(user)
    assert session.post('/api/admin/wallets/', data, format='json').status_code == 403
    response = session.get('/api/auth/csrf/')
    token = response.json().get('csrfToken') or response.json().get('csrf_token') or session.cookies['csrftoken'].value
    assert session.post('/api/admin/wallets/', data, format='json', HTTP_X_CSRFTOKEN=token).status_code == 201


@pytest.mark.django_db
def test_wallet_saved_and_cost_subtracted_only_since_balance(staff):
    usage = {'model': 'claude-sonnet-4', 'input_tokens': 1_000_000, 'output_tokens': 0, 'web_search_requests': 0}
    diagnosis(NOW - timedelta(days=3), usage, '491')
    diagnosis(NOW - timedelta(hours=1), usage, '492')
    with patch('news.admin_status.timezone.now', return_value=NOW):
        saved = staff.post('/api/admin/wallets/', {'provider': 'anthropic', 'amount': '10', 'currency': 'USD',
            'recorded_at': (NOW - timedelta(days=2)).isoformat()}, format='json')
        assert saved.status_code == 201
        response = staff.get('/api/admin/status/')
    wallet = next(w for w in response.data['wallets'] if w['provider'] == 'anthropic')
    assert WalletBalance.objects.get(pk=saved.data['id']).amount == Decimal('10')
    assert wallet['spent_since'] == 3
    assert wallet['estimated_balance'] == 7
    assert wallet['days_remaining'] == 8.2  # seven-day average includes earlier use
    assert wallet['actual_balance'] == 'unknown'
    assert response.data['generated_at'].endswith('+02:00')


@pytest.mark.django_db
def test_x_upper_reservations_currency_and_no_usage_runway():
    account = PoliticalAccount.objects.create(user_id='490', handle='x049')
    PoliticalRead.objects.create(account=account, started_at=NOW - timedelta(days=1), reserved_usd='2.5', reserved_posts=100, status='error')
    usd = WalletBalance.objects.create(provider='x', amount=10, currency='USD', recorded_at=NOW - timedelta(days=2))
    events = finance.recorded_events(NOW - timedelta(days=7), NOW)
    wallets = finance.wallet_snapshot({'x': usd}, events, NOW, {'balance': 'unknown', 'checked_at': 'unknown'})
    x = wallets[0]
    assert x['estimated_balance'] == 7.5
    assert x['days_remaining'] == 21
    usd.currency = 'PLN'
    x = finance.wallet_snapshot({'x': usd}, events, NOW, {'balance': 'unknown', 'checked_at': 'unknown'})[0]
    assert x['estimated_balance'] == x['days_remaining'] == 'unknown'
    usd.currency = 'USD'
    x = finance.wallet_snapshot({'x': usd}, [], NOW, {'balance': 'unknown', 'checked_at': 'unknown'})[0]
    assert x['estimated_balance'] == 10 and x['days_remaining'] == 'unknown'


@pytest.mark.django_db
def test_attribution_uses_usage_not_legacy_provider_and_unknown_is_not_zero():
    row = diagnosis(NOW, {'model': 'gemini-2.5-pro', 'input_tokens': 1_000_000, 'output_tokens': 0})
    row.provider = 'anthropic'  # legacy code writes this even on Gemini fallback
    row.save()
    ClinicInterview.objects.create(day=NOW.date(), video_id='abcdefghijk', created_at=NOW, diagnosed_at=NOW,
        usage={'gemini': {'model': 'gemini-2.5-flash', 'input_tokens': 1_000_000, 'output_tokens': 0},
               'claude': {'model': 'claude-sonnet-4', 'input_tokens': 1_000_000, 'output_tokens': 0}})
    AIResearchCall.objects.create(started_at=NOW, mode='verify', model='gpt-5', input_tokens=1, output_tokens=1)
    events = finance.recorded_events(NOW - timedelta(days=1), NOW)
    end = NOW + timedelta(seconds=1)
    assert finance.total(events, 'gemini', NOW, end) == 1
    assert finance.total(events, 'anthropic', NOW, end) == 3
    assert finance.total(events, 'gemini', NOW, end, 3) == 'unknown'  # transcript chunks
    assert finance.total(events, 'openai', NOW, end) == 'unknown'
    assert finance.total(events, None, NOW, end) == 'unknown'
    assert finance.usage_event(NOW, {'model': 'konsylium: gemini, claude', 'input_tokens': 50, 'output_tokens': 10})[2] is None


@pytest.mark.django_db
def test_free_messages_do_not_poison_paid_wallets_and_council_gemini_is_priced():
    ClinicDailyMessage.objects.create(day=NOW.date(), camp='government', message='Test', created_at=NOW,
                                      usage={'model': 'openai/gpt-oss-120b'})
    diagnosis(NOW, {'model': 'konsylium: model-a, model-b', 'council': {'escalated': False},
                    'input_tokens': 1_000_000, 'output_tokens': 0})
    events = finance.recorded_events(NOW - timedelta(days=1), NOW)
    assert len(events) == 1 and events[0][1:3] == ('gemini', .5)


@pytest.mark.django_db
def test_krs_spending_and_history_limit_remain_explicit():
    WalletBalance.objects.create(provider='gemini', amount=10, currency='USD', recorded_at=NOW - timedelta(hours=1))
    cache.set('krs-agent-spent:2026-09-30', .5)
    snapshot = finance.finance_snapshot(NOW, NOW.replace(hour=0))
    gemini = next(w for w in snapshot['wallets'] if w['provider'] == 'gemini')
    assert gemini['estimated_balance'] == 'unknown'  # cannot split today's KRS cost by hour
    assert snapshot['kpi']['today'] == .5
    with patch.object(finance, 'recorded_events', side_effect=finance.HistoryLimit):
        snapshot = finance.finance_snapshot(NOW, NOW.replace(hour=0))
    assert [w['provider'] for w in snapshot['wallets']] == ['x', 'gemini', 'anthropic']
    assert all(w['estimated_balance'] == 'unknown' for w in snapshot['wallets'])
    assert all(p['value'] == 'unknown' for p in snapshot['series']['points'])


def test_openrouter_cached_success_and_error_never_echo_secrets():
    response = MagicMock(status_code=200)
    response.__enter__.return_value = response
    response.json.return_value = {'data': {'total_credits': 25, 'total_usage': 7.25}}
    with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'secret-test-key'}), patch.object(finance.requests, 'get', return_value=response) as get:
        result = finance.refresh_openrouter()
        assert result['balance'] == 17.75
        assert finance.openrouter_balance() == result
        assert get.call_count == 1
        assert get.call_args.kwargs['allow_redirects'] is False
    with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'secret-test-key'}), patch.object(finance.requests, 'get', side_effect=RuntimeError('secret-test-key')):
        assert finance.refresh_openrouter()['balance'] == 'unknown'
        assert 'secret-test-key' not in str(finance.openrouter_balance())


def test_openrouter_cold_cache_does_not_wait_for_network():
    with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-secret'}), patch.object(finance.threading, 'Thread') as thread:
        assert finance.openrouter_balance()['balance'] == 'unknown'
        assert finance.openrouter_balance()['balance'] == 'unknown'
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()


@pytest.mark.django_db
def test_status_redacts_persisted_error_secrets(staff):
    secret = 'sk-private-example-secret'
    diagnosis(NOW, {}, '494').__class__.objects.filter(post__post_id='494').update(error='402 Authorization: Bearer ' + secret)
    ImportState.objects.create(name='safe-import', last_error='https://example.org/?api_key=' + secret)
    CouncilSeat.objects.create(provider='gemini', model='safe-model', status='suspended', last_error='402 token=' + secret)
    with patch('news.admin_status.timezone.now', return_value=NOW):
        response = staff.get('/api/admin/status/')
    assert response.status_code == 200
    assert secret.encode() not in response.content
    assert b'Authorization' not in response.content
    assert any('Doładuj gemini' in action['title'] for action in response.data['actions'])


@pytest.mark.django_db
def test_gemini_402_marks_wallet_without_manual_entry():
    from news.clinic_models import CouncilSeat
    CouncilSeat.objects.create(provider='gemini', model='gemini-3.8-flash', last_error='gemini: http_402')
    wallets = {w['provider']: w for w in finance.wallet_snapshot({}, [], NOW, {'balance': 'unknown', 'checked_at': 'unknown'},
                                                                  signals=finance.provider_signals(NOW))}
    assert wallets['gemini']['status'] == 'error' and '402' in wallets['gemini']['signal']
    assert wallets['x']['status'] == 'unknown'
