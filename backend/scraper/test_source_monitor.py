from datetime import timedelta
from django.utils import timezone
import pytest
from news.models import Source, ImportState
from scraper.source_monitor import due_sources
from scraper.source_probe import source_signature


@pytest.mark.django_db
def test_source_monitor_rechecks_changes_and_expiry_but_not_running_or_excluded():
    now = timezone.now()
    source = Source.objects.create(name='Publisher', url='https://example.com', catalog_stage='candidate')
    state = ImportState.objects.create(name=f'source-check:{source.pk}', last_started=now, last_success=now,
        cursor={'audit_status': 'completed', 'signature': source_signature(source)})
    assert due_sources(now) == []
    source.rss_url = 'https://example.com/rss'
    source.save()
    assert [s.pk for s in due_sources(now)] == [source.pk]
    state.cursor['audit_status'] = 'running'
    state.save()
    assert due_sources(now) == []
    state.cursor.update(audit_status='completed', signature=source_signature(source))
    state.last_success = now - timedelta(days=8)
    state.save()
    assert [s.pk for s in due_sources(now)] == [source.pk]
    source.catalog_stage = 'excluded'
    source.save()
    assert due_sources(now) == []
