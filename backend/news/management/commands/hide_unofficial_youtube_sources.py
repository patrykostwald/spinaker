"""Ukrywa kanały YouTube dodane dawnym otwartym wyszukiwaniem (nie z potwierdzonych oficjalnych kanałów).

Nic nie usuwa: źródło dostaje is_active=False i etap „excluded”, materiały zostają w bazie, a decyzję
można cofnąć. Kanały potwierdzone jako oficjalne (OfficialVideoChannel, status confirmed) są pomijane,
tak jak kanały podane w --keep. Bez --apply tylko wypisuje listę.
"""
from django.core.management.base import BaseCommand

from news.models import Article, Source
from news.political_models import OfficialVideoChannel

PREFIX = 'https://www.youtube.com/channel/'


class Command(BaseCommand):
    help = 'Ukrywa (bez usuwania) kanały YouTube spoza potwierdzonych oficjalnych kanałów. Bez --apply: tylko lista.'

    def add_arguments(self, parser):
        parser.add_argument('--keep', nargs='*', default=[], help='Identyfikatory kanałów UC… do zostawienia.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, keep, apply, **options):
        confirmed = set(OfficialVideoChannel.objects.filter(status='confirmed').exclude(channel_id='')
                        .values_list('channel_id', flat=True))
        rows = Source.objects.filter(url__startswith=PREFIX, is_active=True).exclude(catalog_stage='excluded').order_by('name')
        hidden = 0
        for source in rows:
            channel = source.url[len(PREFIX):].strip('/')
            if channel in confirmed or channel in keep:
                self.stdout.write(f'ZOSTAJE  {channel}  {source.name}')
                continue
            videos = Article.objects.filter(source=source).count()
            self.stdout.write(f'{"UKRYTO" if apply else "UKRYJE"}  {channel}  {source.name}  ({videos} filmów)')
            if apply:
                source.is_active, source.catalog_stage = False, 'excluded'
                source.catalog_notes = (source.catalog_notes + '\n' if source.catalog_notes else '') + \
                    'Ukryte: kanał dodany otwartym wyszukiwaniem YouTube, nie potwierdzony jako oficjalny.'
                source.save(update_fields=['is_active', 'catalog_stage', 'catalog_notes'])
            hidden += 1
        self.stdout.write(f'{"Ukryto" if apply else "Do ukrycia"}: {hidden}' + ('' if apply else ' — uruchom z --apply, żeby wykonać.'))
