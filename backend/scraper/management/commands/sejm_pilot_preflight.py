"""Read-only readiness check for the first Sejm voting pilot.

It intentionally makes no network requests and never creates a Source or an
access card.  Its output is a concrete checklist for an editor before the
pilot is allowed to start.
"""
from django.core.management.base import BaseCommand
from django.db import connection

from news.models import Source, SourceAccessInstruction
from scraper.access_gate import approved_instruction
from scraper.official import API


SOURCE_URL = API + '/sejm'
ENDPOINT = API + '/sejm/term10/votings'
PILOT_URLS = (
    ENDPOINT + '/search',
    ENDPOINT + '/1/1',
)


class Command(BaseCommand):
    help = 'Sprawdza bez zapisu gotowość pilota głosowań Sejmu (API kadencji 10).'

    def handle(self, *args, **options):
        blockers = []
        checks = []
        source = Source.objects.filter(url=SOURCE_URL).first()
        if not source:
            blockers.append('Brak skonfigurowanego źródła API Sejmu.')
        elif not (source.is_active and source.scrape_enabled and source.catalog_stage == 'configured'):
            blockers.append('Źródło API Sejmu nie jest aktywne i skonfigurowane.')
        else:
            checks.append('Źródło API Sejmu jest aktywne.')

        card = approved_instruction(source, SourceAccessInstruction.Channel.API, ENDPOINT) if source else None
        if not card:
            blockers.append('Brak aktualnej zatwierdzonej karty API dla głosowań kadencji 10.')
        else:
            if card.allowed_scope != SourceAccessInstruction.Scope.CONTENT:
                blockers.append('Karta API Sejmu nie ma zakresu content.')
            else:
                checks.append(f'Karta dostępu v{card.version} obejmuje zakres content.')
            uncovered = [url for url in PILOT_URLS
                         if approved_instruction(source, SourceAccessInstruction.Channel.API, url) is None]
            if uncovered:
                blockers.append('Karta nie obejmuje wszystkich endpointów pilota: ' + ', '.join(uncovered))
            else:
                checks.append('Karta obejmuje wyszukiwanie i szczegóły głosowania.')

        if connection.vendor != 'postgresql':
            blockers.append('Testy wyścigów przed pilotem wymagają PostgreSQL; bieżąca baza to ' + connection.vendor + '.')
        else:
            checks.append('Baza PostgreSQL jest dostępna dla testów współbieżności.')

        for item in checks:
            self.stdout.write(self.style.SUCCESS('OK: ' + item))
        for item in blockers:
            self.stdout.write(self.style.WARNING('BLOKER: ' + item))
        self.stdout.write('WYNIK: ' + ('GOTOWY_DO_PILOTA' if not blockers else 'NIE_GOTOWY_DO_PILOTA'))
