"""Run one explicitly named Sejm voting through the audited pilot path."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from time import sleep

from news.models import SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.official import API, fetch_json, import_voting, official_source
from scraper.utils import HostRateLimited


class Command(BaseCommand):
    help = 'Wykonuje jeden kontrolowany import głosowania Sejmu; bez --apply nic nie pobiera.'

    def add_arguments(self, parser):
        parser.add_argument('--sitting', type=int, required=True)
        parser.add_argument('--vote', type=int, required=True)
        parser.add_argument('--apply', action='store_true',
            help='Dopiero ta flaga wykonuje jedno pobranie przez bramkę audytu.')

    def handle(self, *args, **options):
        sitting, vote = options['sitting'], options['vote']
        if sitting < 1 or vote < 1:
            raise CommandError('--sitting i --vote muszą być dodatnimi liczbami.')
        if connection.vendor != 'postgresql':
            raise CommandError('Pilot wymaga PostgreSQL; SQLite służy tylko do istniejącego archiwum.')

        source = official_source('sejm')
        base = f'{API}/sejm/term10/votings/{sitting}'
        urls = (base, f'{base}/{vote}')
        if not all(approved_instruction(source, SourceAccessInstruction.Channel.API, url) for url in urls):
            raise CommandError('Brak zatwierdzonej karty obejmującej listę i szczegół wskazanego głosowania.')

        if not options['apply']:
            self.stdout.write(self.style.SUCCESS(
                f'GOTOWY: pilotaż pobierze wyłącznie głosowanie 10/{sitting}/{vote} po użyciu --apply.'))
            return

        rows = fetch_json(f'/sejm/term10/votings/{sitting}')
        if not isinstance(rows, list) or not any(
                isinstance(row, dict)
                and (row.get('term'), row.get('sitting'), row.get('votingNumber')) == (10, sitting, vote)
                for row in rows):
            raise CommandError('Lista posiedzenia nie potwierdziła wskazanego głosowania; szczegół nie został pobrany.')
        try:
            created = import_voting(10, sitting, vote)
        except HostRateLimited as exc:
            # This is a deliberately tiny, interactive pilot command. A
            # production worker would defer the job; here a single bounded
            # wait proves the list → detail sequence respects HostGateway.
            delay = min(5.0, max(0.0, exc.retry_after_seconds))
            self.stdout.write(f'BRAMKA: oczekiwanie {delay:.2f}s przed szczegółem.')
            sleep(delay)
            created = import_voting(10, sitting, vote)
        self.stdout.write(self.style.SUCCESS(
            f'ZAKOŃCZONO: głosowanie 10/{sitting}/{vote}; nowy rekord: {bool(created)}.'))
