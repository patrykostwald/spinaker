"""Isolated synthetic accounts/posts. Never sends a paid X request."""
from datetime import timedelta
from decimal import Decimal
import json
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from news.models import Article, Thread, ImportState
from news.political_models import PoliticalAccount, PoliticalPost, PoliticalDraft, PoliticalRead
from news.political_polling import (configuration, political_poll_cycle, fetch_x_timeline,
    PoliticalReadError, reserve)

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff():
    return get_user_model().objects.create_user(username='political-editor-fixture', is_staff=True)


@pytest.fixture
def account(staff):
    item = PoliticalAccount.objects.create(user_id='12345', handle='FixtureOnly', display_name='Synthetic account',
        camp='government', enabled=True, confirmation_url='https://example.org/public-account-fixture')
    item.confirm(staff)
    return item


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv('X_POLITICAL_POLLING_ENABLED', 'true')
    monkeypatch.setenv('X_POLITICAL_BEARER_TOKEN', 'synthetic-key-never-sent')
    monkeypatch.setenv('X_POLITICAL_PAGE_SIZE', '5')
    monkeypatch.setenv('X_POLITICAL_DAILY_POST_LIMIT', '100')
    monkeypatch.setenv('X_POLITICAL_DAILY_REQUEST_LIMIT', '100')
    monkeypatch.setenv('X_POLITICAL_MONTHLY_USD_LIMIT', '5')
    monkeypatch.setenv('X_POLITICAL_INITIAL_LOOKBACK_HOURS', '24')
    return configuration()


def item(post_id, **extra):
    return {'id': str(post_id), 'author_id': '12345', 'text': 'Synthetic source text; not a political analysis.',
        'created_at': (timezone.now() - timedelta(hours=2)).isoformat(), **extra}


def page(rows, token=None, **extra):
    payload = {'data': rows, 'meta': {'result_count': len(rows)},
        'includes': {'users': [{'id': '12345', 'username': 'FixtureOnly', 'name': 'API display name',
            'profile_image_url': 'https://pbs.twimg.com/profile_images/fixture.jpg', 'protected': False}] if rows else []}}
    if token:
        payload['meta']['next_token'] = token
    payload.update(extra)
    return json.dumps(payload).encode()


def due(account):
    PoliticalAccount.objects.filter(pk=account.pk).update(next_poll_at=timezone.now() - timedelta(seconds=1))
    account.refresh_from_db()


def test_disabled_without_key_creates_no_paid_reservation(account, monkeypatch):
    monkeypatch.setenv('X_POLITICAL_POLLING_ENABLED', 'true')
    monkeypatch.delenv('X_POLITICAL_BEARER_TOKEN', raising=False)
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: pytest.fail('paid call'))
    assert political_poll_cycle() == {'status': 'disabled', 'reason': 'x_not_configured', 'new_posts': 0}
    assert not PoliticalRead.objects.exists() and not PoliticalPost.objects.exists()


def test_changed_or_unconfirmed_account_never_polls(account, config, monkeypatch):
    account.camp = 'opposition'; account.save(update_fields=['camp'])
    assert not account.is_confirmed()
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: pytest.fail('paid call'))
    assert political_poll_cycle()['status'] == 'idle'
    assert not PoliticalRead.objects.exists()


def test_confirmation_requires_staff_and_evidence(account, staff):
    user = get_user_model().objects.create_user(username='ordinary-fixture')
    with pytest.raises(ValidationError):
        account.confirm(user)
    account.confirmation_url = ''
    with pytest.raises(ValidationError):
        account.confirm(staff)


def test_paginated_window_does_not_advance_since_id_early(account, config, monkeypatch):
    requests = []
    def fetch(current, window, cfg):
        requests.append(dict(window))
        if len(requests) == 1:
            return page([item(12), item(11)], 'PAGE2')
        if len(requests) == 2:
            return page([item(10)])
        return page([item(13)])
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', fetch)
    assert political_poll_cycle()['more_pages']
    due(account)
    assert not account.poll_cursor.get('since_id')
    assert account.poll_cursor['window']['newest_id'] == '12'
    assert political_poll_cycle()['new_posts'] == 1
    due(account)
    assert account.poll_cursor['since_id'] == '12' and 'window' not in account.poll_cursor
    assert political_poll_cycle()['new_posts'] == 1
    assert requests[0]['end_time'] == requests[1]['end_time']
    assert requests[1]['pagination_token'] == 'PAGE2' and requests[2]['since_id'] == '12'
    assert PoliticalPost.objects.count() == 4
    assert not Article.objects.exists() and not Thread.objects.exists() and not PoliticalDraft.objects.exists()


def test_source_text_and_matching_media_are_preserved(account, config, monkeypatch):
    row = item(11, note_post={'text': 'Full long source text, kept verbatim.'}, attachments={'media_keys': ['valid']})
    payload = json.loads(page([row]))
    payload['includes']['media'] = [
        {'media_key': 'valid', 'type': 'photo', 'url': 'https://pbs.twimg.com/media/fixture.jpg'},
        {'media_key': 'unrelated', 'type': 'photo', 'url': 'https://pbs.twimg.com/media/foreign.jpg'}]
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: json.dumps(payload).encode())
    assert political_poll_cycle()['new_posts'] == 1
    saved = PoliticalPost.objects.get()
    assert saved.text == row['note_post']['text'] and saved.source_data == row
    assert saved.author_data['name'] == 'API display name' and saved.camp_at_collection == 'government'
    assert saved.media == [{'media_key': 'valid', 'type': 'photo', 'thumbnail_url': 'https://pbs.twimg.com/media/fixture.jpg'}]
    assert saved.url == 'https://x.com/FixtureOnly/status/11' and len(saved.response_sha256) == 64
    budget = ImportState.objects.get(name='political-x-budget').cursor
    assert Decimal(budget['spent_upper_usd']) == Decimal('0.015')  # one Post + one user, no dedup discount
    assert budget['daily_posts'] == 1 and budget['daily_requests'] == 1


@pytest.mark.parametrize('bad', [item(11, author_id='99999'), item(11, created_at='invalid'),
    item(11, created_at='2026-09-09T00:00:00'), item(11, text='')])
def test_invalid_source_identity_text_or_date_does_not_advance(account, config, monkeypatch, bad):
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: page([bad]))
    assert political_poll_cycle()['status'] == 'error'
    account.refresh_from_db()
    assert not account.poll_cursor.get('since_id') and not PoliticalPost.objects.exists()
    assert Decimal(ImportState.objects.get(name='political-x-budget').cursor['spent_upper_usd']) == Decimal('0.035')


def test_source_disabled_during_read_prevents_posts(account, config, monkeypatch):
    def fetch(*args):
        PoliticalAccount.objects.filter(pk=account.pk).update(enabled=False)
        return page([item(11)])
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', fetch)
    assert political_poll_cycle()['reason'] == 'x_account_changed_during_read'
    assert not PoliticalPost.objects.exists()


def test_transient_failure_retains_exact_window_for_retry(account, config, monkeypatch):
    windows = []
    def fetch(current, window, cfg):
        windows.append(dict(window))
        if len(windows) == 1:
            raise TimeoutError('synthetic timeout')
        return page([item(11)])
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', fetch)
    assert political_poll_cycle()['status'] == 'error'
    due(account)
    assert political_poll_cycle()['new_posts'] == 1
    assert windows[0] == windows[1]
    assert PoliticalRead.objects.count() == 2


def test_budget_limit_and_active_global_lease_prevent_paid_calls(account, config, monkeypatch):
    monkeypatch.setenv('X_POLITICAL_MONTHLY_USD_LIMIT', '0.01')
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: pytest.fail('paid call'))
    assert political_poll_cycle()['status'] == 'budget_limit'
    assert not PoliticalRead.objects.exists()
    monkeypatch.setenv('X_POLITICAL_MONTHLY_USD_LIMIT', '5')
    reservation, status = reserve(account.pk, configuration())
    assert status == 'reserved'
    due(account)
    assert political_poll_cycle()['status'] == 'deferred'
    assert PoliticalRead.objects.count() == 1


def test_429_pauses_all_accounts_and_keeps_unknown_charge_reserved(account, config, monkeypatch):
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', Mock(side_effect=PoliticalReadError('x_http_429', 429, 1800)))
    assert political_poll_cycle()['status'] == 'error'
    budget = ImportState.objects.get(name='political-x-budget').cursor
    assert budget['blocked_until'] > timezone.now().isoformat()
    due(account)
    assert political_poll_cycle()['status'] == 'deferred'
    assert PoliticalRead.objects.count() == 1


def test_fetch_only_uses_official_host_and_refuses_redirect(account, config, monkeypatch):
    response = Mock(status_code=302, headers={})
    response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
    get = Mock(return_value=response)
    monkeypatch.setattr('news.political_polling.requests.get', get)
    window = {'page_size': 5, 'end_time': '2026-09-09T00:00:00Z', 'start_time': '2026-09-08T00:00:00Z'}
    with pytest.raises(PoliticalReadError, match='x_http_302'):
        fetch_x_timeline(account, window, config)
    assert get.call_args.args == ('https://api.x.com/2/users/12345/tweets',)
    assert get.call_args.kwargs['allow_redirects'] is False
    assert get.call_args.kwargs['params']['post.fields'].find('note_post') >= 0


@override_settings(ROOT_URLCONF='news.political_urls')
def test_staff_api_rejects_ordinary_users_and_does_not_expose_token(account, staff, config):
    client = APIClient()
    for route in ('/accounts/', '/posts/', '/drafts/', '/status/'):
        assert client.get(route).status_code in (401, 403)
    ordinary = get_user_model().objects.create_user(username='not-editor-fixture')
    client.force_authenticate(ordinary)
    assert client.get('/accounts/').status_code == 403
    client.force_authenticate(staff)
    assert client.get('/accounts/').status_code == 200
    assert 'synthetic-key' not in client.get('/status/').content.decode()


@override_settings(ROOT_URLCONF='news.political_urls')
def test_draft_packet_and_approval_do_not_publish_thread(account, staff, config, monkeypatch):
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: page([item(11)]))
    political_poll_cycle()
    client = APIClient(); client.force_authenticate(staff)
    saved = PoliticalPost.objects.get()
    response = client.post('/drafts/', {'camp': 'government', 'day': timezone.localdate().isoformat(),
        'title': 'Synthetic editorial intake', 'posts': [saved.pk], 'origin': 'ai_proposal', 'status': 'approved'}, format='json')
    assert response.status_code == 201, response.data
    draft = PoliticalDraft.objects.get()
    assert draft.origin == 'editorial_selection' and draft.status == 'pending_review'
    packet = client.get(f'/drafts/{draft.pk}/packet/').json()
    assert packet['ai_status'] == 'not_requested' and packet['sources'][0]['text'] == saved.text
    result = client.post(f'/drafts/{draft.pk}/review/', {'decision': 'approved'}, format='json')
    assert result.status_code == 200 and result.data['published_threads'] == 0
    draft.refresh_from_db()
    assert draft.reviewed_by == staff and draft.status == 'approved'
    assert not Thread.objects.exists() and not Article.objects.exists()


@override_settings(ROOT_URLCONF='news.political_urls')
def test_drafts_reject_duplicate_wrong_camp_and_unavailable_posts(account, staff, config, monkeypatch):
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: page([item(11)]))
    political_poll_cycle()
    post = PoliticalPost.objects.get(); client = APIClient(); client.force_authenticate(staff)
    base = {'camp': 'government', 'day': timezone.localdate().isoformat(), 'title': 'Fixture', 'posts': [post.pk]}
    assert client.post('/drafts/', {**base, 'posts': [post.pk, post.pk]}, format='json').status_code == 400
    assert client.post('/drafts/', {**base, 'camp': 'opposition'}, format='json').status_code == 400
    post.available = False; post.save(update_fields=['available'])
    assert client.post('/drafts/', base, format='json').status_code == 400


def test_account_with_history_cannot_change_its_stable_user_id(account):
    account.poll_cursor = {'since_id': '123'}; account.save(update_fields=['poll_cursor'])
    account.user_id = '67890'
    with pytest.raises(ValidationError):
        account.full_clean()


def test_post_write_failure_rolls_back_whole_page_and_since_cursor(account, config, monkeypatch):
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: page([item(12), item(11)]))
    original = PoliticalPost.objects.update_or_create
    calls = 0
    def write(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError('synthetic write failure')
        return original(**kwargs)
    with patch('news.political_polling.PoliticalPost.objects.update_or_create', side_effect=write):
        assert political_poll_cycle()['status'] == 'error'
    account.refresh_from_db()
    assert not PoliticalPost.objects.exists() and not account.poll_cursor.get('since_id')
    due(account)
    assert political_poll_cycle()['new_posts'] == 2


def test_staff_withdrawal_clears_post_and_invalidates_draft(account, staff, config, monkeypatch):
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', lambda *args: page([item(11)]))
    political_poll_cycle()
    saved = PoliticalPost.objects.get()
    draft = PoliticalDraft.objects.create(camp='government', day=timezone.localdate(), title='Synthetic draft',
        status='approved', reviewed_by=staff, notes='Synthetic working note')
    draft.posts.add(saved)
    from news.political_admin import PoliticalPostAdmin
    PoliticalPostAdmin(PoliticalPost, None).remove_unavailable_content(Mock(user=staff), PoliticalPost.objects.filter(pk=saved.pk))
    saved.refresh_from_db(); draft.refresh_from_db()
    assert not saved.available and saved.text == '' and saved.source_data == {} and saved.media == []
    assert draft.status == 'pending_review' and draft.reviewed_by is None
    # Replay after a cursor repair must not resurrect the withdrawn source content.
    PoliticalAccount.objects.filter(pk=account.pk).update(poll_cursor={}, next_poll_at=timezone.now())
    political_poll_cycle()
    saved.refresh_from_db()
    assert not saved.available and saved.text == ''


def test_empty_window_preserves_boundary_and_does_not_invent_post(account, config, monkeypatch):
    windows = []
    def empty(current, window, cfg):
        windows.append(dict(window))
        return page([])
    monkeypatch.setattr('news.political_polling.fetch_x_timeline', empty)
    assert political_poll_cycle()['new_posts'] == 0
    due(account)
    previous_end = account.poll_cursor['completed_until']
    assert account.poll_cursor['since_id'] == ''
    political_poll_cycle()
    assert windows[1]['start_time'] == previous_end
    assert Decimal(ImportState.objects.get(name='political-x-budget').cursor['spent_upper_usd']) == 0
    assert not PoliticalPost.objects.exists()
