"""Audit the next small batch of inactive official candidates without importing."""
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from news.models import ImportState, Source
from scraper.management.commands.audit_sources import is_recent_attempt


class Command(BaseCommand):
    help = 'Audytuje małą, wznawialną paczkę kandydatów bez aktywacji ani importu.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=24)
        parser.add_argument('--workers', type=int, default=3)
        parser.add_argument('--max-age-hours', type=int, default=168)
        parser.add_argument('--output-prefix', default='reports/source-candidate-audit-current')
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 48:
            raise CommandError('limit musi wynosić 1–48.')
        if not 1 <= options['workers'] <= 6:
            raise CommandError('workers musi wynosić 1–6.')
        candidates = list(Source.objects.filter(
            catalog_stage='candidate', is_active=False, scrape_enabled=False,
        ).filter(Q(url__startswith='http://') | Q(url__startswith='https://')).order_by('pk'))
        states = {state.name: state.cursor for state in ImportState.objects.filter(
            name__in=[f'source-check:{source.pk}' for source in candidates])}
        if not options['force']:
            candidates = [source for source in candidates if not is_recent_attempt(
                source, states.get(f'source-check:{source.pk}', {}), options['max_age_hours'])]
        selected = candidates[:options['limit']]
        if not selected:
            self.stdout.write('Brak kandydatów wymagających kontroli w wybranym okresie.')
            return
        prefix = Path(options['output_prefix'])
        suffix = timezone.now().strftime('%Y%m%dT%H%M%SZ')
        report_prefix = str(prefix.parent / f'{prefix.name}-{suffix}')
        args = [part for source in selected for part in ('--source-id', str(source.pk))]
        args += ['--workers', str(options['workers']), '--max-age-hours', str(options['max_age_hours']),
                 '--output-prefix', report_prefix]
        if options['force']:
            args.append('--force')
        self.stdout.write('Audyt: ' + ', '.join(f'{source.pk}:{source.name}' for source in selected))
        call_command('audit_sources', *args)
        self.stdout.write(self.style.SUCCESS(
            f'Zakończono kontrolę {len(selected)} kandydatów. Raport: {report_prefix}.json/.csv/.md'))
