"""Read-only diagnosis with exactly one bounded API request, no raw errors."""
from datetime import date
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import timezone
from news.models import ImportState, ParliamentaryVoting
from news.political_models import ParliamentaryRosterEntry
from scraper.official import fetch_json


class Command(BaseCommand):
    help = 'Stan danych bieżącej kadencji Sejmu i ELI. Jedno zapytanie o posiedzenia.'

    def handle(self, *args, **options):
        term = settings.SEJM_TERM
        votes = ParliamentaryVoting.objects.filter(term=term)
        last = votes.aggregate(last=Max('article__published_date'))['last']
        active = ParliamentaryRosterEntry.objects.filter(source='sejm', term=term, active=True).count()
        self.stdout.write(f'Kadencja: {term}; głosowania w bazie: {votes.count()}; aktywni posłowie: {active}')
        self.stdout.write(f'Ostatnie głosowanie w bazie: {last.isoformat() if last else "brak"}')
        try:
            proceedings = fetch_json(f'/sejm/term{term}/proceedings')
            past = [(date.fromisoformat(day), row['number']) for row in proceedings for day in row['dates']
                    if date.fromisoformat(day) <= timezone.localdate()]
            day, number = max(past)
            self.stdout.write(f'Ostatnie posiedzenie według API: {number}; data: {day.isoformat()}')
            self.stdout.write('Daty posiedzeń nie potwierdzają kompletności wszystkich głosowań.')
        except Exception as exc:
            # Never print exception text, payloads, state cursors or credentials.
            self.stdout.write(f'Posiedzenia API: niedostępne ({type(exc).__name__})')
        names = ['official:votings', 'official:prints', 'official:eli', f'official-backfill:votings:{term}']
        states = {row.name: row for row in ImportState.objects.filter(name__in=names)}
        for name in names:
            row = states.get(name)
            if row is None:
                self.stdout.write(f'{name}: brak stanu')
                continue
            error = row.last_error
            if error.startswith('host_rate_limited:'):
                status = 'odroczony przez limit'
            elif error:
                status = 'błąd (szczegóły w panelu)'
            else:
                status = 'partia w toku' if row.cursor and name == 'official:eli' else 'bez błędu'
            self.stdout.write(f'{name}: {status}; start: {row.last_started}; sukces: {row.last_success}; rekordy: {row.imported}')
