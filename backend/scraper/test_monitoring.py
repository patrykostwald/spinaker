import pytest
from django.utils import timezone
from news.models import ImportState, Source
from scraper.management.commands.run_local_jobs import run_monitored, rss_cycle


@pytest.mark.django_db
def test_restart_keeps_daily_backup_deadline_but_retries_failed_backup(monkeypatch):
    from datetime import timedelta
    from scraper.management.commands.run_local_jobs import backup_delay
    now = timezone.now()
    monkeypatch.setattr('scraper.management.commands.run_local_jobs.timezone.now', lambda: now)
    assert backup_delay(86400) == 0
    state = ImportState.objects.create(name='local:backup', last_started=now-timedelta(hours=2),
        last_success=now-timedelta(hours=2)+timedelta(seconds=20))
    assert backup_delay(86400) == 22*3600
    state.last_started = now-timedelta(minutes=1); state.save()
    assert backup_delay(86400) == 0  # Latest attempt did not complete successfully.
    state.last_started = now-timedelta(days=2); state.last_success = now-timedelta(days=2)+timedelta(seconds=20); state.save()
    assert backup_delay(86400) == 0
    state.last_started = now+timedelta(hours=1); state.last_success = now+timedelta(hours=2); state.save()
    assert backup_delay(86400) == 0

@pytest.mark.django_db(transaction=True)
def test_partial_and_idle_do_not_fabricate_success():
    previous = timezone.now()
    ImportState.objects.create(name='local:rss', last_success=previous)
    run_monitored('rss', lambda: {'status': 'partial', 'failed_source_ids': [1]})
    state = ImportState.objects.get(name='local:rss')
    assert state.last_success == previous and state.last_error
    assert state.cursor['failed_source_ids'] == [1]
    run_monitored('rss', lambda: {'status': 'idle'})
    state.refresh_from_db()
    assert state.last_success == previous and state.last_error
    run_monitored('rss', lambda: {'status': 'ok'})
    state.refresh_from_db()
    assert state.last_success > previous and state.last_error == ''

@pytest.mark.django_db
def test_rss_reports_incomplete_write_as_failure(monkeypatch):
    source = Source.objects.create(name='Test', url='https://example.org', rss_url='https://example.org/rss')
    def incomplete():
        Source.objects.filter(pk=source.pk).update(last_attempted=timezone.now())
        return 0
    monkeypatch.setattr('scraper.management.commands.run_local_jobs.scrape_rss_sources.__wrapped__', incomplete)
    result = rss_cycle()
    assert result['status'] == 'partial'
    assert result['failed_source_ids'] == [source.pk]
