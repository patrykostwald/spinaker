"""Wyłączenie spinek zachowuje dane i nie wpływa na zapis diagnozy."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.mark.parametrize('enabled', [False, True])
def test_settings_are_the_only_source(settings, monkeypatch, enabled):
    from news.features import threads_enabled, preview_active
    settings.THREADS_ENABLED = enabled
    monkeypatch.setenv('THREADS_ENABLED', str(not enabled).lower())
    token = preview_active.set(True)
    try:
        assert threads_enabled() is enabled
    finally:
        preview_active.reset(token)


@pytest.mark.django_db
@pytest.mark.parametrize('enabled', [False, True])
def test_diagnosis_save(settings, enabled):
    from news.test_diagnosis_threads import diagnosis
    from news.account_models import PersonalContextThread
    settings.THREADS_ENABLED = enabled
    row = diagnosis()
    row.refresh_from_db()
    assert row.status == 'approved'
    assert PersonalContextThread.objects.filter(diagnosis=row).exists() is enabled


@pytest.mark.parametrize('name,target', [
    ('narrative_thread_task', 'news.narrative_threads.build_narratives'),
    ('signal_threads_task', 'news.signal_threads.build_lobbying'),
    ('thread_reviews_task', 'news.thread_review.backfill_queue'),
    ('dr_spin_thread_task', 'news.dr_spin_threads.build_daily_thread'),
])
@pytest.mark.parametrize('enabled', [False, True])
def test_tasks(settings, monkeypatch, name, target, enabled):
    from news import tasks
    settings.THREADS_ENABLED = enabled
    work = Mock(return_value={})
    monkeypatch.setattr(target, work)
    monkeypatch.setattr('news.signal_threads.build_new_narratives', Mock(return_value={}))
    monkeypatch.setattr('news.thread_review.run_queue', Mock(return_value={}))
    monkeypatch.setattr('news.tasks.cache.add', Mock(return_value=True))
    monkeypatch.setattr('news.tasks.cache.delete', Mock())
    result = getattr(tasks, name)()
    assert work.called is enabled
    if not enabled:
        assert result == {'status': 'disabled'}


@pytest.mark.django_db
def test_disabled_entrypoints(settings):
    from news.diagnosis_threads import sync_diagnosis_thread
    from news.narrative_threads import sync_message
    from news.signal_threads import save_signal
    from news.thread_review import enqueue, review_one, run_queue, backfill_queue
    from news.push_events import deliver_event
    from news.push import send_to_topic
    settings.THREADS_ENABLED = False
    settings.PUSH_ENABLED = True
    assert sync_diagnosis_thread(999) is None
    assert sync_message(999) is None
    assert save_signal('', '', '', '', [], {}, {}) is None
    assert enqueue(None, {}) is None
    assert review_one(999) == 'disabled'
    assert run_queue() == {}
    assert backfill_queue() is None
    assert deliver_event('test', 'nitki-dr-spina', {}) == 0
    assert send_to_topic('nitki-dr-spina', {}) == 0


@pytest.mark.django_db
@pytest.mark.parametrize('method,path', [
    ('get', '/api/threads/'), ('get', '/api/threads/example/'),
    ('get', '/api/threads/example/opinions/'), ('post', '/api/threads/example/opinions/'),
    ('get', '/api/community/threads/'), ('get', '/api/community/threads/1/'),
    ('get', '/api/community/threads/1/card.png'), ('get', '/api/community/threads/1/opinions/'),
    ('post', '/api/community/threads/1/report/'), ('post', '/api/community/threads/1/comments/'),
    ('get', '/api/community/reports/1/'), ('get', '/api/account/favorites/'),
    ('post', '/api/account/favorites/'), ('delete', '/api/account/favorites/1/'),
    ('get', '/api/account/context-threads/'), ('post', '/api/account/context-threads/'),
    ('post', '/api/editor/draft-thread/'), ('post', '/api/editor/threads/'),
])
def test_api_returns_404(settings, method, path):
    settings.THREADS_ENABLED = False
    settings.ACCOUNTS_ENABLED = True
    assert getattr(APIClient(), method)(path).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize('enabled', [False, True])
def test_lists_restore(settings, enabled):
    settings.THREADS_ENABLED = enabled
    client = APIClient()
    for path in ('/api/threads/', '/api/community/threads/'):
        assert client.get(path).status_code == (200 if enabled else 404)


def test_disabled_guards_ignore_environment(settings, monkeypatch):
    from news.duty_extra import check_public_threads
    from news.daily_schedule import check_thread, check_narrative
    settings.THREADS_ENABLED = False
    monkeypatch.setenv('THREADS_ENABLED', 'true')
    monkeypatch.setenv('DR_SPIN_THREADS_ENABLED', 'true')
    now = timezone.now()
    assert check_public_threads(SimpleNamespace(now=now)) == []
    assert check_thread(now)[0] == 'na'
    assert check_narrative(now)[0] == 'na'


@pytest.mark.parametrize('enabled', [False, True])
def test_task_health_uses_global_flag(settings, monkeypatch, enabled):
    from news.agent_registry import task_enabled
    settings.THREADS_ENABLED = enabled
    monkeypatch.setenv('THREADS_ENABLED', 'false')
    monkeypatch.setenv('DR_SPIN_THREADS_ENABLED', 'true')
    for task in ('narrative_thread_task', 'signal_threads_task', 'thread_reviews_task', 'dr_spin_thread_task'):
        assert task_enabled('news.tasks.' + task) is enabled


@pytest.mark.django_db
def test_thread_outbox_waits_until_reenabled(settings, monkeypatch):
    from news.notification_models import NotificationEvent
    from news.notification_tasks import process_notification_events
    settings.ACCOUNTS_ENABLED = True
    settings.THREADS_ENABLED = False
    event = NotificationEvent.objects.create(kind='thread', target_id=999)
    deliver = Mock()
    monkeypatch.setattr('news.notification_tasks._deliver_event', deliver)
    monkeypatch.setattr('news.followed_posts.flush_post_pushes', Mock())
    assert process_notification_events() == 0
    event.refresh_from_db()
    assert event.processed_at is None
    deliver.assert_not_called()
    settings.THREADS_ENABLED = True
    assert process_notification_events() == 1
    deliver.assert_called_once()


@pytest.mark.django_db
def test_follow_other_user_still_works(settings):
    from django.contrib.auth import get_user_model
    settings.ACCOUNTS_ENABLED = True
    settings.THREADS_ENABLED = False
    owner = get_user_model().objects.create_user('owner')
    other = get_user_model().objects.create_user('other')
    client = APIClient()
    client.force_authenticate(owner)
    assert client.post('/api/account/follows/', {'kind': 'thread', 'target_id': 1}).status_code == 404
    assert client.post('/api/account/follows/', {'kind': 'user', 'target_id': other.pk}).status_code == 201
    assert len(client.get('/api/account/follows/').data) == 1


@pytest.mark.django_db
def test_reenable_preserves_existing_thread(settings):
    from news.test_diagnosis_threads import diagnosis
    from news.account_models import PersonalContextThread
    settings.THREADS_ENABLED = True
    row = diagnosis()
    thread = PersonalContextThread.objects.get(diagnosis=row)
    settings.THREADS_ENABLED = False
    row.headline = 'Nowy tytuł diagnozy'
    row.save()
    assert PersonalContextThread.objects.get(pk=thread.pk).title == thread.title
    settings.THREADS_ENABLED = True
    row.save()
    assert PersonalContextThread.objects.get(diagnosis=row).pk == thread.pk


@pytest.mark.django_db
@pytest.mark.parametrize('enabled', [False, True])
def test_clinic_discussions_remain_available(settings, enabled):
    from news.test_diagnosis_threads import diagnosis
    from news.clinic_models import ClinicInterview
    settings.THREADS_ENABLED = enabled
    settings.ACCOUNTS_ENABLED = True
    spin = diagnosis()
    interview = ClinicInterview.objects.create(day=timezone.localdate(), video_id='abcdefghijk', status='approved')
    client = APIClient()
    for kind, pk in [('spins', spin.pk), ('interviews', interview.pk)]:
        assert client.get(f'/api/clinic/{kind}/{pk}/comments/').status_code == 200


@pytest.mark.django_db
def test_disabled_review_command_preserves_queue(settings):
    from io import StringIO
    from django.core.management import call_command
    from news.account_models import PersonalContextThread
    from news.thread_review_models import ThreadReview
    settings.THREADS_ENABLED = False
    thread = PersonalContextThread.objects.create(title='Istniejący szkic', signal_kind='lobbying', signal_key='test-disabled')
    review = ThreadReview.objects.create(thread=thread, status='rejected', payload={}, working_texts={})
    call_command('drspin_review_threads', retry_rejected=True, stdout=StringIO())
    review.refresh_from_db()
    assert review.status == 'rejected'
