"""Revisit one already imported Sejm vote to detect an official correction."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from news.models import OfficialRecord
from scraper.official import import_voting


class Command(BaseCommand):
    help = 'Ponownie sprawdza istniejące głosowanie Sejmu; bez --apply nie pobiera danych.'

    def add_arguments(self, parser):
        parser.add_argument('--sitting', type=int, required=True)
        parser.add_argument('--vote', type=int, required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        sitting, vote = options['sitting'], options['vote']
        if sitting < 1 or vote < 1:
            raise CommandError('--sitting i --vote muszą być dodatnimi liczbami.')
        if connection.vendor != 'postgresql':
            raise CommandError('Ponowna kontrola pilota wymaga PostgreSQL.')
        external_id = f'vote/10/{sitting}/{vote}'
        record = OfficialRecord.objects.filter(provider='sejm', external_id=external_id).first()
        if not record:
            raise CommandError('Nie ma jeszcze lokalnego rekordu tego głosowania; użyj najpierw run_sejm_vote_pilot.')
        if not options['apply']:
            self.stdout.write(self.style.SUCCESS(
                f'GOTOWY: ponowna kontrola {external_id} wykryje wyłącznie różnicę względem zachowanego rekordu.'))
            return

        before = record.revisions.count()
        import_voting(10, sitting, vote)
        record.refresh_from_db()
        revisions = record.revisions.count()
        if revisions > before:
            self.stdout.write(self.style.WARNING(
                f'KOREKTA: {external_id}; zapisano poprzednią wersję jako dowód.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'BEZ_ZMIAN: {external_id}.'))
