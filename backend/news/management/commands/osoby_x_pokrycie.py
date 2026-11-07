"""Kontrola: ile osób publicznych ma konto X, ile nie, kto i od kiedy czeka.

  python manage.py osoby_x_pokrycie           # osoby z bazy; gdy baza pusta — z danych w repo
  python manage.py osoby_x_pokrycie --repo    # osoby z danych w repo (tylko plik osoby_x.csv)
  python manage.py osoby_x_pokrycie --bez-listy
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from news import osoby_x
from news.management.commands.osoby_x_zbierz import people


def day(value):
    return value.date().isoformat() if value else 'nigdy'


class Command(BaseCommand):
    help = 'Pokrycie kont X osób publicznych (plik osoby_x.csv; na bazie także konta czytane i kolejka Strażnika).'

    def add_arguments(self, parser):
        parser.add_argument('--repo', action='store_true')
        parser.add_argument('--plik', default=str(osoby_x.CSV_PATH))
        parser.add_argument('--bez-listy', action='store_true', help='Tylko liczby, bez listy braków.')

    def handle(self, *args, **options):
        found, origin = people(options['repo'])
        result = osoby_x.coverage(found, osoby_x.read_rows(Path(options['plik'])))
        self.stdout.write(f"Osoby publiczne ({origin}): {result['osoby']}; z kontem X w osoby_x.csv: {result['z_kontem']}; "
                          f"bez konta: {result['bez_konta']}.")
        if origin == 'baza':
            self.database(options['bez_listy'])
        elif not options['bez_listy']:
            self.stdout.write('Braki:')
            for person in result['braki']:
                self.stdout.write(f"- {person.name} · {person.osoba_id} · {'; '.join(person.roles[:2])}")

    def database(self, quiet):
        from news.account_warden import CONFLICT, conflicts_for_report, cost_projection
        from news.political_models import PoliticalAccountCandidate, PublicFigure
        from news.public_figures import figures_with_verified_x
        figures = list(PublicFigure.objects.filter(archived=False, status='current').exclude(role_category='party'))
        shown = figures_with_verified_x(figures)
        waiting = sorted((f for f in figures if f.pk not in shown), key=lambda f: f.created_at)
        self.stdout.write(f'Konto X czytane i widoczne na stronach: {len(shown)} z {len(figures)} osób z aktualną funkcją.')
        if waiting:
            never = sum(1 for f in waiting if not f.account_discovery_at)
            self.stdout.write(f'Czeka na konto X: {len(waiting)} osób; najdłużej od {day(waiting[0].created_at)} '
                              f'(w rejestrze); jeszcze nie sprawdzane przez Strażnika: {never}.')
        queue = PoliticalAccountCandidate.objects.filter(resolved_account__isnull=True, resolution_error__startswith='Strażnik:')
        conflicts = queue.filter(resolution_error__startswith='Strażnik: ' + CONFLICT)
        oldest = queue.order_by('created_at').first()
        reported = conflicts_for_report()
        self.stdout.write(f'Kolejka Strażnika: {queue.count()} kandydatów (konflikty do decyzji: {conflicts.count() + len(reported)}); '
                          f'najstarszy od {day(oldest.created_at if oldest else None)}.')
        cost = cost_projection(len(waiting))
        self.stdout.write(f"Gdyby wszystkie brakujące osoby dostały konto: ok. +{cost['usd_month']} USD/miesiąc "
                          f"({cost['usd_per_account_month']} USD na konto; limit X_POLITICAL_MONTHLY_USD_LIMIT "
                          f"{cost['monthly_limit_usd']} USD).")
        if quiet:
            return
        self.stdout.write('Czekają (od kiedy w rejestrze · ostatnie sprawdzenie):')
        for figure in waiting:
            self.stdout.write(f'- {figure.canonical_name} · {figure.role_title} · {day(figure.created_at)} · '
                              f'{day(figure.account_discovery_at)}')
        for row in reported:
            self.stdout.write(f"- do decyzji: @{row['handle']} ({row['name']}): {row['reason']} Propozycja: {row['proposal']}")
        for candidate in queue.order_by('created_at'):
            self.stdout.write(f'- kolejka: @{candidate.handle} ({candidate.display_name}) od {day(candidate.created_at)}: '
                              f'{candidate.resolution_error.removeprefix("Strażnik: ")}')
