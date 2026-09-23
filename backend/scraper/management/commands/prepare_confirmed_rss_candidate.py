"""Stage one RSS URL found by bounded explicit-channel discovery for a fresh audit."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from news.models import ImportState, Source


class Command(BaseCommand):
    help = ('Zapisuje do ponownego audytu wyłącznie działający RSS znaleziony w jawnej nawigacji źródła. '
            'Nie aktywuje źródła i nie tworzy karty dostępu.')

    def add_arguments(self, parser):
        parser.add_argument('--source-id', type=int, required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        with transaction.atomic():
            source = Source.objects.select_for_update().filter(pk=options['source_id']).first()
            if source is None:
                raise CommandError('Nie znaleziono źródła.')
            if source.is_active or source.scrape_enabled or source.catalog_stage != 'candidate':
                raise CommandError('Źródło nie jest nieaktywnym kandydatem.')
            state = ImportState.objects.filter(name=f'source-check:{source.pk}').first()
            result = (state.cursor if state else {}).get('legal_channel_discovery') or {}
            if result.get('status') != 'working_channel_requires_editorial_card_review':
                raise CommandError('Brak działającego kanału potwierdzonego w jawnej nawigacji źródła.')
            feeds = [item.get('url') for item in result.get('channels', []) if item.get('status') == 'working']
            if len(feeds) != 1:
                raise CommandError('Wymagany jest dokładnie jeden działający kanał do ponownego audytu.')
            feed_url = feeds[0]
            if not options['apply']:
                self.stdout.write(f'PLAN: {source.name}; RSS {feed_url}; pozostaje nieaktywny do audytu i karty.')
                return
            source.rss_url = feed_url
            source.full_clean()
            source.save(update_fields=['rss_url', 'updated_at'])
        self.stdout.write(self.style.SUCCESS(
            f'GOTOWE: {source.pk} {source.name}; RSS zapisany do świeżego audytu, źródło nadal nieaktywne.'
        ))
