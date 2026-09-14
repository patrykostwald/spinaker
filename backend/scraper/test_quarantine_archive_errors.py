import pytest
from django.core.management import call_command

from news.models import ArchiveJob, Source


@pytest.mark.django_db
def test_quarantine_command_is_dry_run_by_default_and_bounded(capsys):
    source = Source.objects.create(name='Publisher', url='https://example.org')
    first = ArchiveJob.objects.create(source=source, url='https://example.org/one', kind='page',
        status='error', last_error='robots_disallowed')
    second = ArchiveJob.objects.create(source=source, url='https://example.org/two', kind='page',
        status='error', last_error='Timeout', attempts=5)
    call_command('quarantine_archive_errors', limit=1)
    first.refresh_from_db(); second.refresh_from_db()
    assert first.status == second.status == 'error'
    assert 'dry-run: matched=1 changed=0 limit=1' in capsys.readouterr().out


@pytest.mark.django_db
def test_quarantine_command_applies_only_safe_historical_classes():
    source = Source.objects.create(name='Publisher', url='https://example.org')
    terminal = ArchiveJob.objects.create(source=source, url='https://example.org/terminal', kind='page',
        status='error', last_error='empty_directory')
    drift = ArchiveJob.objects.create(source=source, url='https://example.org/drift', kind='page',
        status='error', last_error='unclassified_page', attempts=99)
    call_command('quarantine_archive_errors', apply_changes=True)
    terminal.refresh_from_db(); drift.refresh_from_db()
    assert terminal.status == 'quarantined'
    assert drift.status == 'error'
