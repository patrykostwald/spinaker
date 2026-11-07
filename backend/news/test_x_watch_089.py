"""All source and model calls are synthetic; run with offline_test_guard."""
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from news import clinic, tasks, x_watch, account_warden
from news.clinic_models import SpinDiagnosis
from news.models import ImportState
from news.notification_models import NotificationEvent
from news.political_models import PoliticalAccount, PoliticalPost, PoliticalRead
from news.political_polling import configuration, political_poll_cycle, PoliticalReadError, fetch_x_timeline
from news.test_political_intake import account, staff, config, item, page, due
from news.test_followed_posts_088 import figure, reader

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def offline_clock(monkeypatch, settings):
    settings.ACCOUNTS_ENABLED = True
    cache.clear()
    monkeypatch.setenv('X_POLL_MODE', 'batched')
    with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 3, 12, tzinfo=dt_timezone.utc)):
        yield
    cache.clear()


def other(staff, number=9999, **extra):
    result = PoliticalAccount.objects.create(user_id=str(number), handle=f'Fixture{number}', display_name='Fixture',
        camp='opposition', enabled=True, confirmation_url='https://example.org/fixture', **extra)
    result.confirm(staff)
    return result


def force_due():
    PoliticalAccount.objects.update(last_polled_at=timezone.now() - timedelta(hours=1),
        next_poll_at=timezone.now() - timedelta(seconds=1))


def stored(account, number, **extra):
    return PoliticalPost.objects.create(account=account, post_id=str(number), text='Synthetic text',
        published_at=extra.pop('published_at', timezone.now() - timedelta(minutes=2)),
        camp_at_collection=account.camp, **extra)


@pytest.mark.parametrize('count', [1, 100, 400, 600])
def test_queries_fit_self_serve_and_cover_each_account_once(count):
    accounts = [SimpleNamespace(handle=f'Account{i:08}', include_replies=i % 2 == 0) for i in range(count)]
    groups = x_watch.build_queries(accounts)
    assert [a for batch, _ in groups for a in batch] == accounts
    assert all(len(query) <= 512 and query.endswith(' -is:retweet') for _, query in groups)
    for index in range(len(groups) - 1):
        assert len(x_watch.query_for([*groups[index][0], groups[index + 1][0][0]])) > 512


def test_query_rejects_injected_handle():
    with pytest.raises(PoliticalReadError):
        x_watch.build_queries([SimpleNamespace(handle='a OR cat', include_replies=True)])


@pytest.mark.parametrize('mode', ['timeline', 'batched'])
def test_official_requests_never_expand_profiles(account, config, mode):
    response = Mock(status_code=200, headers={})
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = [page([])]
    recent = str((int(datetime(2026, 10, 2, tzinfo=dt_timezone.utc).timestamp() * 1000) - 1288834974657) << 22)
    window = {'page_size': 10, 'start_time': '2026-10-02T12:00:00Z', 'end_time': '2026-10-03T11:59:50Z',
        'query': '(from:FixtureOnly) -is:retweet', 'since_id': recent, 'pagination_token': 'NEXT'}
    with patch('news.political_polling.requests.get', return_value=response) as get:
        (fetch_x_timeline(account, window, config) if mode == 'timeline' else x_watch.fetch_x_search(window, config))
    params = get.call_args.kwargs['params']
    assert params['expansions'] == 'attachments.media_keys' and 'user.fields' not in params
    assert 'author_id' in params['post.fields'] and 'public_metrics' in params['post.fields']
    assert 'start_time' not in params and params['since_id'] == recent
    assert params['next_token' if mode == 'batched' else 'pagination_token'] == 'NEXT'
    assert get.call_args.kwargs['allow_redirects'] is False
    assert get.call_args.args[0] == ('https://api.x.com/2/tweets/search/recent' if mode == 'batched'
        else 'https://api.x.com/2/users/12345/tweets')


def test_batch_pagination_then_cursor_pays_each_post_once(account, staff, config):
    b = other(staff)
    windows = []
    def fetch(window, _):
        windows.append(dict(window))
        return [page([item(120), item(119, author_id=b.user_id)], 'NEXT'), page([item(118)]),
            page([item(121, created_at=(timezone.now() - timedelta(seconds=30)).isoformat())])][len(windows) - 1]
    with patch('news.x_watch.fetch_x_search', side_effect=fetch):
        result = political_poll_cycle()
        assert result['new_posts'] == 3 and result['pages'] == 2
        account.refresh_from_db(); b.refresh_from_db()
        assert account.poll_cursor['since_id'] == b.poll_cursor['since_id'] == '120'
        # Activity tier can split groups on the next cycle, with the same boundary.
        force_due()
        with patch('news.x_watch.activity_counts', return_value={}):
            assert political_poll_cycle()['new_posts'] == 1
    assert windows[0]['query'] == windows[1]['query']
    assert windows[0]['since_id'] == windows[1]['since_id'] == ''
    assert windows[0]['end_time'] == windows[1]['end_time']
    assert windows[1]['pagination_token'] == 'NEXT' and windows[2]['since_id'] == '120'
    assert len(windows) == 3 and PoliticalPost.objects.count() == 4
    assert Decimal(ImportState.objects.get(name='political-x-budget').cursor['spent_upper_usd']) == Decimal('.020')
    assert all(read.response_body is None for read in PoliticalRead.objects.all())


def test_different_group_cursors_and_new_account_do_not_replay(account, staff, config):
    account.poll_cursor = {'since_id': '100'}; account.save()
    b = other(staff, poll_cursor={'since_id': '200'})
    with patch('news.x_watch.fetch_x_search', return_value=page([])) as fetch:
        political_poll_cycle()
        assert {call.args[0]['since_id'] for call in fetch.call_args_list} == {'100', '200'}
        assert all(not ('FixtureOnly' in call.args[0]['query'] and b.handle in call.args[0]['query'])
            for call in fetch.call_args_list)
        c = other(staff, 8888)
        political_poll_cycle()
        assert fetch.call_count == 3 and fetch.call_args.args[0]['since_id'] == ''
        assert c.handle in fetch.call_args.args[0]['query'] and account.handle not in fetch.call_args.args[0]['query']
        force_due()
        political_poll_cycle()
        assert fetch.call_count == 4  # converged to one common coverage watermark
        assert fetch.call_args.args[0]['since_id'] == '200'
        assert all(a.handle in fetch.call_args.args[0]['query'] for a in (account, b, c))


def test_followed_first_then_active_then_slow(account, staff, config, reader):
    active, slow = other(staff), other(staff, 8888)
    stored(active, 300)
    with patch('news.x_watch.fetch_x_search', return_value=page([])) as fetch:
        assert political_poll_cycle()['pages'] == 3
        queries = [call.args[0]['query'] for call in fetch.call_args_list]
        assert [account.handle in queries[0], active.handle in queries[1], slow.handle in queries[2]] == [True] * 3
        assert political_poll_cycle()['pages'] == 0
    for a, seconds in [(account, 60), (active, 60), (slow, 900)]:
        a.refresh_from_db()
        assert a.next_poll_at == timezone.now() + timedelta(seconds=seconds)


def test_cycle_uses_one_coverage_time_even_when_http_takes_seconds(account, staff, config):
    account.poll_cursor = {'since_id': '100'}; account.save()
    other(staff, poll_cursor={'since_id': '200'})
    clock = [timezone.now()]
    windows = []
    def fetch(window, cfg):
        windows.append(window)
        clock[0] += timedelta(seconds=2)
        return page([])
    with patch('django.utils.timezone.now', side_effect=lambda: clock[0]), \
            patch('news.x_watch.fetch_x_search', side_effect=fetch):
        assert political_poll_cycle()['pages'] == 2
        force_due()
        assert political_poll_cycle()['pages'] == 1
    assert windows[0]['end_time'] == windows[1]['end_time']
    assert windows[2]['since_id'] == '200'


@pytest.mark.parametrize('variable,value', [('X_POLITICAL_DAILY_REQUEST_LIMIT', '1'),
    ('X_POLITICAL_DAILY_POST_LIMIT', '10'), ('X_POLITICAL_MONTHLY_USD_LIMIT', '.05')])
def test_budget_reservation_prioritizes_followed_and_stops(account, staff, config, reader, monkeypatch, variable, value):
    other(staff)
    monkeypatch.setenv(variable, value)
    with patch('news.x_watch.fetch_x_search', side_effect=PoliticalReadError('timeout')) as fetch:
        assert political_poll_cycle()['status'] == 'error'
        assert account.handle in fetch.call_args.args[0]['query']
        force_due()
        assert political_poll_cycle()['status'] == 'budget_limit'
        assert fetch.call_count == 1
    budget = ImportState.objects.get(name='political-x-budget').cursor
    assert budget['daily_requests'] == 1 and budget['daily_posts'] == 10
    assert Decimal(budget['spent_upper_usd']) == Decimal('.05')


def test_empty_response_releases_posts_and_dollars_but_not_request(account, config):
    with patch('news.x_watch.fetch_x_search', return_value=page([])) as fetch:
        assert political_poll_cycle()['pages'] == 1
        assert fetch.call_count == 1
    budget = ImportState.objects.get(name='political-x-budget').cursor
    assert budget['daily_requests'] == 1 and budget['daily_posts'] == 0
    assert Decimal(budget['spent_upper_usd']) == 0


def test_small_remaining_budget_shrinks_page_without_going_below_api_minimum(account, config, monkeypatch):
    monkeypatch.setenv('X_POLITICAL_PAGE_SIZE', '100')
    monkeypatch.setenv('X_POLITICAL_MONTHLY_USD_LIMIT', '.055')
    with patch('news.x_watch.fetch_x_search', return_value=page([item(100)])) as fetch:
        political_poll_cycle()
    assert fetch.call_args.args[0]['page_size'] == 11


def test_db_failure_replays_local_response_without_second_purchase(account, config):
    with patch('news.x_watch.fetch_x_search', return_value=page([item(100)])) as fetch:
        with patch.object(PoliticalPost.objects, 'update_or_create', side_effect=ValueError('database failure')):
            assert political_poll_cycle()['status'] == 'error'
        force_due()
        assert political_poll_cycle()['new_posts'] == 1
        assert fetch.call_count == 1
    assert PoliticalRead.objects.count() == 1 and PoliticalRead.objects.get().status == 'ok'
    assert ImportState.objects.get(name='political-x-budget').cursor['daily_requests'] == 1


def test_global_lease_blocks_concurrent_worker(account, config):
    def fetch(window, cfg):
        assert political_poll_cycle()['pages'] == 0
        return page([item(100)])
    with patch('news.x_watch.fetch_x_search', side_effect=fetch) as transport:
        assert political_poll_cycle()['new_posts'] == 1
    assert transport.call_count == PoliticalRead.objects.count() == 1


def test_mode_switch_finishes_original_pagination_before_using_new_endpoint(account, config, monkeypatch):
    monkeypatch.setenv('X_POLITICAL_DAILY_REQUEST_LIMIT', '1')
    with patch('news.x_watch.fetch_x_search', return_value=page([item(101)], 'NEXT')):
        assert political_poll_cycle()['status'] == 'budget_limit'
    monkeypatch.setenv('X_POLL_MODE', 'timeline')
    monkeypatch.setenv('X_POLITICAL_DAILY_REQUEST_LIMIT', '100')
    with patch('news.x_watch.fetch_x_search', return_value=page([item(100)])) as search, \
            patch('news.political_polling.fetch_x_timeline') as timeline:
        assert political_poll_cycle()['new_posts'] == 1
        assert search.call_args.args[0]['pagination_token'] == 'NEXT'
        timeline.assert_not_called()
    force_due()
    with patch('news.political_polling.fetch_x_timeline', return_value=page([])) as timeline:
        political_poll_cycle()
        assert timeline.call_args.args[1]['since_id'] == '101'


def test_changed_identity_during_read_does_not_store_posts(account, config):
    def fetch(window, cfg):
        PoliticalAccount.objects.filter(pk=account.pk).update(enabled=False)
        return page([item(100)])
    with patch('news.x_watch.fetch_x_search', side_effect=fetch):
        assert political_poll_cycle()['reason'] == 'x_account_changed_during_read'
    assert not PoliticalPost.objects.exists()


def test_saved_response_recovery_across_month_does_not_refund_new_month(account, config):
    with patch('news.x_watch.fetch_x_search', return_value=page([item(100)])) as fetch:
        with patch.object(PoliticalPost.objects, 'update_or_create', side_effect=ValueError('database failure')):
            political_poll_cycle()
        with patch('django.utils.timezone.now', return_value=datetime(2026, 11, 1, 12, tzinfo=dt_timezone.utc)):
            force_due()
            assert political_poll_cycle()['new_posts'] == 1
        fetch.assert_called_once()
    budget = ImportState.objects.get(name='political-x-budget').cursor
    assert budget['month'] == '2026-11' and Decimal(budget['spent_upper_usd']) == 0
    assert budget['daily_requests'] == budget['daily_posts'] == 0


def test_duplicate_in_response_is_rejected_before_any_post_is_saved(account, config):
    with patch('news.x_watch.fetch_x_search', return_value=page([item(100), item(100)])):
        assert political_poll_cycle()['reason'] == 'x_post_author_or_duplicate'
    assert PoliticalPost.objects.count() == 0


def test_bad_author_or_profiles_are_rejected(account, config):
    window = {'page_size': 10, 'start_time': '2026-10-02T00:00:00Z', 'end_time': '2026-10-03T12:00:00Z'}
    with pytest.raises(PoliticalReadError):
        x_watch.parse_search_page(page([item(100, author_id='4567')]), [account], window)
    with pytest.raises(PoliticalReadError):
        x_watch.parse_search_page(page([], includes={'users': [{'id': '12345'}]}), [account], window)


def test_immediate_screening_is_after_commit_and_notifications_still_created(account, config, reader,
        django_capture_on_commit_callbacks):
    with patch('news.x_watch.fetch_x_search', return_value=page([item(100,
            created_at=(timezone.now() - timedelta(minutes=1)).isoformat())])), \
            patch.object(tasks.clinic_screen_task, 'apply_async') as enqueue:
        with django_capture_on_commit_callbacks(execute=True):
            political_poll_cycle()
            enqueue.assert_not_called()
        enqueue.assert_called_once_with(kwargs={'post_ids': [PoliticalPost.objects.get().pk]}, priority=0)
    assert NotificationEvent.objects.filter(kind='post').exists()


@pytest.mark.parametrize('score,status,dispatched', [(80, 'queued', True), (50, 'flagged', False), (10, 'not_applicable', False)])
def test_targeted_screen_uses_same_thresholds_and_dispatches_diagnosis(account, score, status, dispatched):
    selected, untouched = stored(account, 100, watch_priority=True), stored(account, 101)
    with patch('news.clinic_ai.screen', return_value={'score': score, 'provider': 'groq', 'model': 'synthetic'}), \
            patch('news.clinic.send_review_alert', return_value='nothing'), \
            patch.object(tasks.clinic_diagnose_task, 'apply_async') as diagnose:
        tasks.clinic_screen_task(post_ids=[selected.pk])
    assert SpinDiagnosis.objects.get().status == status
    assert not SpinDiagnosis.objects.filter(post=untouched).exists()
    assert diagnose.called == dispatched
    if dispatched:
        diagnose.assert_called_once_with(priority=0)


def test_mode_defaults_and_schedule_clamps(config, monkeypatch):
    from news.daily_schedule import beat_entries
    monkeypatch.delenv('X_POLL_MODE')
    assert configuration()['mode'] == 'timeline'
    assert not isinstance(beat_entries()['political-x-minute']['schedule'], timedelta)
    monkeypatch.setenv('X_POLL_MODE', 'batched'); monkeypatch.setenv('X_WATCH_SECONDS', '1')
    assert configuration()['watch_seconds'] == 30
    assert beat_entries()['political-x-minute']['schedule'] == timedelta(seconds=30)
    monkeypatch.setenv('X_POLL_MODE', 'unknown')
    assert political_poll_cycle()['status'] == 'disabled'


def test_mode_switch_preserves_since_id(account, config, monkeypatch):
    monkeypatch.setenv('X_POLL_MODE', 'timeline')
    with patch('news.political_polling.fetch_x_timeline', return_value=page([item(100)])):
        assert political_poll_cycle()['new_posts'] == 1
    force_due(); monkeypatch.setenv('X_POLL_MODE', 'batched')
    with patch('news.x_watch.fetch_x_search', return_value=page([item(101)])) as fetch:
        assert political_poll_cycle()['new_posts'] == 1
        assert fetch.call_args.args[0]['since_id'] == '100'
    force_due(); monkeypatch.setenv('X_POLL_MODE', 'timeline')
    with patch('news.political_polling.fetch_x_timeline', return_value=page([])) as fetch:
        political_poll_cycle()
        assert fetch.call_args.args[1]['since_id'] == '101'


def test_profile_refresh_is_at_most_weekly_even_on_partial_response(account, monkeypatch):
    monkeypatch.setenv('ACCOUNT_WARDEN_VERIFY_DAYS', '2')
    assert account_warden.verify_days() == 7
    with patch('news.account_warden.x_lookup', return_value={'errors': []}) as lookup:
        for _ in range(2):
            account_warden.verify_accounts({'lookups': 0, 'events': []}, 100)
    assert lookup.call_count == 1
    account.refresh_from_db()
    assert account.last_profile_read_at == timezone.now() and account.last_verified_at is None


def test_estimate_and_latency_use_local_data_and_exclude_old_posts(account, staff):
    from news.management.commands.x_watch_estimate import estimate
    other(staff)
    p = stored(account, 100, fetched_at=timezone.now() - timedelta(minutes=1))
    stored(account, 101, fetched_at=timezone.now() - timedelta(seconds=30))
    stored(account, 102, published_at=timezone.now() - timedelta(days=15))
    SpinDiagnosis.objects.create(post=p, status='approved', diagnosed_at=timezone.now())
    metrics = x_watch.latency_metrics()
    assert metrics == {'ingestion_seconds': 75, 'diagnosis_seconds': 120, 'posts': 2, 'diagnoses': 1}
    data = estimate()
    assert data['accounts'] == 2 and data['stored_posts'] == 2
    assert Decimal(data['batched_usd']) == x_watch.monthly_cost(Decimal(2) / 14)
    assert Decimal(data['former_usd']) == x_watch.monthly_cost(Decimal(2) / 14, Decimal(2) / 14)
    assert data['per_account'][1]['posts'] == 0
    out = StringIO(); call_command('x_watch_estimate', '--json', stdout=out)
    assert json.loads(out.getvalue())['stored_posts'] == 2


def test_new_watch_post_has_diagnosis_priority_without_bypassing_guards(account, monkeypatch):
    older, new = stored(account, 100), stored(account, 101, watch_priority=True)
    SpinDiagnosis.objects.create(post=older, status='queued', screen_score=99)
    SpinDiagnosis.objects.create(post=new, status='queued', screen_score=80)
    monkeypatch.setenv('CLINIC_DAILY_LIMIT', '8')
    with patch('news.clinic_ai.enabled', return_value=True), patch('news.clinic.diagnosis_reserve', return_value=.25), \
            patch('news.clinic.budget_left', return_value=5), patch('news.clinic.failures_today', return_value=0), \
            patch('news.clinic.paced_target', return_value=1), patch('news.clinic.diagnose') as diagnose, \
            patch('news.clinic.send_review_alert'):
        assert clinic.run_diagnoses()['status'] == 'ok'
        assert diagnose.call_args.args[0].post_id == new.pk
        diagnose.reset_mock()
        with patch('news.clinic.budget_left', return_value=0):
            assert clinic.run_diagnoses()['status'] == 'budget'
            diagnose.assert_not_called()


def test_admin_latency_context_is_staff_only(account, staff, client, rf):
    from django.contrib import admin
    from news.political_admin import PoliticalAccountAdmin
    stored(account, 100)
    url = '/admin/news/politicalaccount/'
    assert client.get(url).status_code == 302
    staff.is_superuser = True; staff.save()
    request = rf.get(url); request.user = staff
    response = PoliticalAccountAdmin(PoliticalAccount, admin.site).changelist_view(request)
    assert response.status_code == 200
    assert response.context_data['x_watch_latency']['posts'] == 1


@pytest.mark.parametrize('accounts,posts,usd', [(100, 2, 30), (400, 4, 240), (600, 6, 540)])
def test_cost_formula(accounts, posts, usd):
    assert x_watch.monthly_cost(accounts * posts) == Decimal(usd)
    assert x_watch.monthly_cost(accounts * posts, accounts * posts) == Decimal(usd * 3)


def test_release_stale_refunds_hanging_reservations(staff):
    from news.political_polling import release_stale
    acct = other(staff, 7771)
    now = timezone.now()
    ImportState.objects.create(name='political-x-budget', cursor={'day': now.date().isoformat(), 'month': now.strftime('%Y-%m'),
        'daily_posts': 1210, 'spent_upper_usd': '10', 'lease': 'x', 'lease_until': (now - timedelta(minutes=5)).isoformat()})
    old = PoliticalRead.objects.create(account=acct, started_at=now - timedelta(minutes=30), reserved_posts=100, reserved_usd=Decimal('0.5'))
    fresh = PoliticalRead.objects.create(account=acct, started_at=now - timedelta(minutes=1), reserved_posts=100, reserved_usd=Decimal('0.5'))
    assert release_stale(now) == 1
    old.refresh_from_db(); fresh.refresh_from_db()
    assert old.status == 'abandoned' and fresh.status == 'reserved'
    budget = ImportState.objects.get(name='political-x-budget').cursor
    assert budget['daily_posts'] == 1110 and Decimal(budget['spent_upper_usd']) == Decimal('9.5') and budget['lease_until'] == ''


def test_long_x_error_detail_fits_last_error(staff, config):
    # 6.10: opis błędu X dłuższy niż pole last_error (200) wywracał zapis i zostawiał rezerwację na zawsze
    from news.political_polling import PoliticalReadError
    import news.political_polling as pp
    acct = other(staff, 7772)
    err = PoliticalReadError('x_http_400', 400, 300)
    err.detail = 'x' * 300
    with patch('news.x_watch.fetch_x_search', side_effect=err), patch('news.political_polling.fetch_x_timeline', side_effect=err):
        pp.political_poll_cycle()
    state = ImportState.objects.get(name='political-x-budget')
    assert len(state.last_error) <= 200 and not PoliticalRead.objects.filter(status='reserved').exists()


def test_search_never_mixes_since_id_with_time_window():
    # 6.10: X odrzucał zapytanie (400), gdy obok since_id szło end_time
    from news.x_watch import fetch_x_search
    sent = {}
    def fake(url, params, config):
        sent.update(params)
        return b'{}'
    with patch('news.x_watch.request_x', side_effect=fake):
        recent = str((int(datetime(2026, 10, 2, tzinfo=dt_timezone.utc).timestamp() * 1000) - 1288834974657) << 22)
        fetch_x_search({'query': 'from:a', 'page_size': 10, 'since_id': recent, 'start_time': 's', 'end_time': 'e'}, {})
        assert 'since_id' in sent and 'end_time' not in sent and 'start_time' not in sent
        sent.clear()
        fetch_x_search({'query': 'from:a', 'page_size': 10, 'since_id': '', 'start_time': '2026-10-02T00:00:00Z', 'end_time': 'e'}, {})
        assert sent['start_time'] == '2026-10-02T00:00:00Z' and sent['end_time'] == 'e' and 'since_id' not in sent


def test_search_drops_since_id_older_than_seven_days():
    # 6.10: X odrzucał since_id starszy niż 7 dni (400); wtedy pytamy o okno czasowe od granicy 7 dni
    from news.x_watch import fetch_x_search
    sent = {}
    old_id = str((int(datetime(2026, 9, 20, tzinfo=dt_timezone.utc).timestamp() * 1000) - 1288834974657) << 22)
    with patch('news.x_watch.request_x', side_effect=lambda u, p, c: sent.update(p) or b'{}'):
        fetch_x_search({'query': 'from:a', 'page_size': 10, 'since_id': old_id, 'start_time': '2026-09-01T00:00:00Z', 'end_time': '2026-10-03T11:59:00Z'}, {})
    assert 'since_id' not in sent and sent['end_time'] == '2026-10-03T11:59:00Z' and sent['start_time'] > '2026-09-26'
