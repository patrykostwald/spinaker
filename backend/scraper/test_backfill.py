from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ValidationError

from news.models import ArchiveJob, ImportState, Source, SourceAccessInstruction
from scraper.archive import ArchiveCutoff
from scraper.backfill import approved_source_ids, parse_cutoff, prepare_source


def test_cutoff_requires_timezone():
    with pytest.raises(ValueError):
        parse_cutoff('2026-09-14T23:59:59')


@pytest.mark.django_db
def test_prepare_source_freezes_cutoff_and_does_not_rewrite_it(monkeypatch):
    source = Source.objects.create(name='Pilot', url='https://example.org')
    monkeypatch.setattr('scraper.backfill.verified_maps',
        lambda current, require_archive_approval=False: ['https://example.org/sitemap.xml'])
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


@pytest.mark.django_db
def test_dynamic_source_pool_reloads_additions_and_removals_between_cycles(monkeypatch):
    first = Source.objects.create(name='First', url='https://first.example',
        is_active=True, scrape_enabled=True, catalog_stage='configured')
    second = Source.objects.create(name='Second', url='https://second.example',
        is_active=True, scrape_enabled=True, catalog_stage='configured')
    pools = iter([[first.pk], [second.pk]])
    calls = []

    monkeypatch.setattr(
        'scraper.management.commands.backfill_archives_loop.approved_source_ids',
        lambda: next(pools))
    monkeypatch.setattr(
        'scraper.management.commands.backfill_archives_loop.run_backfill',
        lambda source_ids, *args, **kwargs: calls.append(list(source_ids)) or {
            'status': 'ok', 'completed': 0})
    ticks = iter([0, 0, 1, 999999])
    monkeypatch.setattr(
        'scraper.management.commands.backfill_archives_loop.time.monotonic',
        lambda: next(ticks))
    monkeypatch.setattr(
        'scraper.management.commands.backfill_archives_loop.time.sleep', lambda _: None)

    call_command('backfill_archives_loop', dynamic_sources=True, max_hours=0.1)

    assert calls == [[first.pk], [second.pk]]


@pytest.mark.django_db
def test_dynamic_source_pool_refuses_unapproved_or_unconfigured_sources(monkeypatch):
    approved = Source.objects.create(name='Approved', url='https://approved.example',
        is_active=True, scrape_enabled=True, catalog_stage='configured')
    unapproved = Source.objects.create(name='Unapproved', url='https://no.example',
        is_active=True, scrape_enabled=True, catalog_stage='configured')
    Source.objects.create(name='Inactive', url='https://inactive.example',
        is_active=False, scrape_enabled=True, catalog_stage='configured')
    Source.objects.create(name='Candidate', url='https://candidate.example',
        is_active=True, scrape_enabled=True, catalog_stage='candidate')
    monkeypatch.setattr('scraper.backfill.verified_maps',
        lambda source, require_archive_approval=False: (
            ['https://approved.example/sitemap.xml'] if source.pk == approved.pk
            and require_archive_approval else []))

    SourceAccessInstruction.objects.create(
        source=approved, version=1, status='approved', channel='sitemap',
        allowed_scope='metadata', endpoint='https://approved.example/sitemap.xml',
        terms_url='https://approved.example/terms', evidence={'basis': 'test'},
        reviewed_at=__import__('django.utils.timezone', fromlist=['now']).now(),
        reviewed_by='test', minimum_interval_seconds=3)

    assert approved_source_ids() == [approved.pk]
    assert unapproved.pk not in approved_source_ids()


@pytest.mark.django_db
def test_approved_access_instruction_requires_terms_evidence_and_review():
    source = Source.objects.create(name='Guarded', url='https://guarded.example')
    instruction = SourceAccessInstruction(source=source, status='approved', channel='sitemap',
        endpoint='https://guarded.example/sitemap.xml', minimum_interval_seconds=3)
    with pytest.raises(ValidationError):
        instruction.full_clean()


def test_loop_requires_static_ids_unless_dynamic_mode_is_explicit():
    with pytest.raises(CommandError, match='source-id'):
        call_command('backfill_archives_loop', max_hours=0.1)
