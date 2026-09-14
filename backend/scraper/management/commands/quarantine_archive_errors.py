from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from news.models import ArchiveJob
from scraper.archive import MAX_ARCHIVE_ATTEMPTS, TERMINAL_ERRORS


TRANSIENT_ERROR_MARKERS = ('timeout', 'connection', '429', 'http 5', 'http_5')


class Command(BaseCommand):
    help = 'Preview or apply a bounded quarantine of existing terminal archive errors.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=1000)
        parser.add_argument('--apply', action='store_true', dest='apply_changes')

    def handle(self, *args, **options):
        limit = options['limit']
        if not 1 <= limit <= 10000:
            raise CommandError('--limit must be between 1 and 10000')
        terminal = Q(last_error__in=sorted(TERMINAL_ERRORS))
        exhausted_transient = Q(attempts__gte=MAX_ARCHIVE_ATTEMPTS)
        marker_query = Q()
        for marker in TRANSIENT_ERROR_MARKERS:
            marker_query |= Q(last_error__icontains=marker)
        ids = list(ArchiveJob.objects.filter(status='error').filter(
            terminal | (exhausted_transient & marker_query)
        ).order_by('pk').values_list('pk', flat=True)[:limit])
        mode = 'apply' if options['apply_changes'] else 'dry-run'
        changed = ArchiveJob.objects.filter(pk__in=ids, status='error').update(status='quarantined') if options['apply_changes'] else 0
        self.stdout.write(f'{mode}: matched={len(ids)} changed={changed} limit={limit}')
