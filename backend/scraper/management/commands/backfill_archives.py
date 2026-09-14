from django.core.management.base import BaseCommand, CommandError

from scraper.backfill import PILOT_CUTOFF_AT, parse_cutoff, run_backfill


class Command(BaseCommand):
    help = 'Run a bounded local archive backfill with a frozen cutoff; never runs current-feed monitoring.'

    def add_arguments(self, parser):
        parser.add_argument('--source-id', action='append', type=int, required=True)
        parser.add_argument('--cutoff-at', default='2026-09-14T23:59:59+02:00')
        parser.add_argument('--workers', type=int, default=2)
        parser.add_argument('--limit-per-source', type=int, default=20)

    def handle(self, *args, **options):
        if not 1 <= options['workers'] <= 32:
            raise CommandError('workers must be 1..32')
        if not 1 <= options['limit_per_source'] <= 100:
            raise CommandError('limit-per-source must be 1..100')
        try:
            cutoff = parse_cutoff(options['cutoff_at'])
            if options['cutoff_at'] != PILOT_CUTOFF_AT:
                raise ValueError(f'cutoff_at must be exactly {PILOT_CUTOFF_AT}')
            result = run_backfill(options['source_id'], cutoff,
                workers=options['workers'], per_source_limit=options['limit_per_source'])
        except (ValueError, OverflowError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(str(result))