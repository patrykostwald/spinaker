from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def test_loop_rejects_unbounded_runtime():
    with pytest.raises(CommandError, match='max-hours'):
        call_command('backfill_archives_loop', source_id=[1], max_hours=25)


def test_loop_never_calls_current_scheduler():
    with patch('scraper.management.commands.backfill_archives_loop.run_backfill',
               return_value={'completed': 0, 'status': 'ok', 'metrics': {}}), \
            patch('scraper.archive.archive_cycle') as current, \
            patch('scraper.management.commands.backfill_archives_loop.ArchiveJob.objects.filter') as jobs:
        jobs.return_value.exists.return_value = False
        call_command('backfill_archives_loop', source_id=[1], max_hours=.1)
    current.assert_not_called()
