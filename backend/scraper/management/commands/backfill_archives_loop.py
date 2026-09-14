import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.models import ArchiveJob
from scraper.backfill import PILOT_CUTOFF_AT, parse_cutoff, run_backfill


class Command(BaseCommand):
    help = 'Continuously drain only the approved archive backfill queue for a bounded time.'

    def add_arguments(self, parser):
        parser.add_argument('--source-id', action='append', type=int, required=True)
        parser.add_argument('--cutoff-at', default=PILOT_CUTOFF_AT)
        parser.add_argument('--workers', type=int, default=2)
        parser.add_argument('--limit-per-source', type=int, default=20)
        parser.add_argument('--interval-seconds', type=int, default=10)
        parser.add_argument('--max-hours', type=float, default=10)

    def handle(self, *args, **options):
        workers = options['workers']
        limit = options['limit_per_source']
        interval = options['interval_seconds']
        max_hours = options['max_hours']
        if not 1 <= workers <= 32:
            raise CommandError('workers must be 1..32')
        if not 1 <= limit <= 100:
            raise CommandError('limit-per-source must be 1..100')
        if not 3 <= interval <= 300:
            raise CommandError('interval-seconds must be 3..300')
        if not 0.1 <= max_hours <= 24:
            raise CommandError('max-hours must be 0.1..24')
        if options['cutoff_at'] != PILOT_CUTOFF_AT:
            raise CommandError(f'cutoff_at must be exactly {PILOT_CUTOFF_AT}')
        cutoff = parse_cutoff(options['cutoff_at'])
        source_ids = list(dict.fromkeys(options['source_id']))
        deadline = time.monotonic() + max_hours * 3600
        cycles = completed = 0
        while time.monotonic() < deadline:
            result = run_backfill(source_ids, cutoff, workers=workers, per_source_limit=limit)
            cycles += 1
            completed += result['completed']
            self.stdout.write(str({'at': timezone.now().isoformat(), 'cycle': cycles,
                'completed_total': completed, **result}))
            pending_now = ArchiveJob.objects.filter(source_id__in=source_ids,
                status__in=['pending', 'error', 'running'], available_at__lte=timezone.now()).exists()
            future_retry = ArchiveJob.objects.filter(source_id__in=source_ids,
                status__in=['pending', 'error', 'running']).exists()
            if not pending_now and not future_retry:
                self.stdout.write('Archive queue drained.')
                return
            time.sleep(interval)
        self.stdout.write(f'Bounded runtime reached after {cycles} cycles and {completed} completed jobs.')
