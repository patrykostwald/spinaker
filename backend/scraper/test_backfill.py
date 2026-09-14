from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from news.models import ArchiveJob, ImportState, Source
from scraper.archive import ArchiveCutoff
from scraper.backfill import parse_cutoff, prepare_source


def test_cutoff_requires_timezone():
    with pytest.raises(ValueError):
        parse_cutoff('2026-09-14T23:59:59')


@pytest.mark.django_db
def test_prepare_source_freezes_cutoff_and_does_not_rewrite_it(monkeypatch):
    source = Source.objects.create(name='Pilot', url='https://example.org')
    monkeypatch.setattr('scraper.backfill.verified_maps', lambda current: ['https://example.org/sitemap.xml'])
    first = parse_cutoff('2026-09-14T23:59:59+02:00')
    second = parse_cutoff('2026-09-13T23:59:59+02:00')
    prepare_source(source, first)
    with pytest.raises(ValueError, match='cutoff'):
        prepare_source(source, second)
    assert ImportState.objects.get(name=f'archive-backfill:{source.pk}').cursor['cutoff_at'] == first.isoformat()
    assert ArchiveJob.objects.count() == 1


@pytest.mark.django_db
def test_command_never_calls_current_scheduler(monkeypatch):
    monkeypatch.setattr('scraper.backfill.run_backfill', lambda *args, **kwargs: {'status': 'ok'})
    with patch('scraper.archive.archive_cycle') as current:
        call_command('backfill_archives', source_id=[999999], workers=2, limit_per_source=2)
    current.assert_not_called()


def test_command_rejects_naive_cutoff():
    with pytest.raises(CommandError):
        call_command('backfill_archives', source_id=[1], cutoff_at='2026-09-14T23:59:59')


def test_command_rejects_different_aware_cutoff():
    with pytest.raises(CommandError, match='exactly'):
        call_command('backfill_archives', source_id=[1], cutoff_at='2026-09-13T23:59:59+02:00')


def test_cutoff_exception_is_explicit():
    assert issubclass(ArchiveCutoff, Exception)