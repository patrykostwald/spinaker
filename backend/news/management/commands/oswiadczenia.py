"""Oświadczenia majątkowe posłów (news/asset_declarations.py; flaga ASSETS_DECLARATIONS_ENABLED).

python manage.py oswiadczenia synchronizuj                 (indeks ze zbieracza public_records/assets -> AssetDeclaration)
python manage.py oswiadczenia metadane [--limit 20] [--opoznienie 5]   (grzeczne pobranie: suma kontrolna, rozmiar, strony)
python manage.py oswiadczenia lista [--posel 123]
Zbieracz indeksu: scraper public_records, źródło `assets` (env PUBLIC_RECORDS_ASSETS_ENABLED=true).
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Oświadczenia majątkowe posłów: indeks, metadane PDF (bez przechowywania PDF), lista.'

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', required=True)
        sub.add_parser('synchronizuj')
        meta = sub.add_parser('metadane')
        meta.add_argument('--limit', type=int, default=20)
        meta.add_argument('--opoznienie', type=float, default=None)
        listing = sub.add_parser('lista')
        listing.add_argument('--posel', type=int, default=None)

    def handle(self, *args, **opts):
        from news import asset_declarations as ad
        from news.clinic_models import AssetDeclaration
        if opts['action'] != 'lista' and not ad.enabled():
            raise CommandError('ASSETS_DECLARATIONS_ENABLED jest wyłączona (env albo przelacznik).')
        if opts['action'] == 'synchronizuj':
            self.stdout.write(json.dumps(ad.sync(), ensure_ascii=False))
        elif opts['action'] == 'metadane':
            if opts['limit'] > 200:
                raise CommandError('Najwyżej 200 dokumentów na przebieg (grzeczność wobec serwera Sejmu).')
            self.stdout.write(json.dumps(ad.fetch_metadata(limit=opts['limit'], delay=opts['opoznienie']), ensure_ascii=False))
        else:
            rows = AssetDeclaration.objects.all()
            if opts['posel']:
                rows = rows.filter(mp_id=opts['posel'])
            for d in rows.order_by('mp_id', '-year')[:500]:
                self.stdout.write(f'{d.mp_id}\t{d.name}\t{d.year}\t{d.kind}\t{d.published_on}\t{d.sha256[:12]}\t{d.url}')
