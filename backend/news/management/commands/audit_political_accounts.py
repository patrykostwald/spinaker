"""Przegląd kont X czytanych w Klinice nowymi zasadami tożsamości (news/.../link_official_x_accounts.identity_problem).

  python manage.py audit_political_accounts            # tylko raport
  python manage.py audit_political_accounts --disable  # podejrzane konta wyłącza z czytania (nic nie usuwa)

Dwa–trzy zapytania do API X (po 100 kont). Sprawdza: czy konto istnieje, czy nazwisko osoby z rejestru jest
w nazwie konta (całe słowo), czy konto nie jest świeże z małym zasięgiem (zajęta stara nazwa — przypadek @AgaBak).
"""
import os

import requests
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Sprawdza, czy konta X w Klinice należą do właściwych osób; --disable wyłącza podejrzane.'

    def add_arguments(self, parser):
        parser.add_argument('--disable', action='store_true')
        parser.add_argument('--all', action='store_true', help='Także konta już wyłączone.')

    def handle(self, *args, disable=False, all=False, **options):
        from django.utils import timezone
        from news.clinic import figures_by_account
        from news.management.commands.link_official_x_accounts import USER_FIELDS, identity_problem
        from news.political_models import PoliticalAccount
        token = os.environ.get('X_POLITICAL_BEARER_TOKEN', '').strip()
        if not token:
            raise CommandError('Brak X_POLITICAL_BEARER_TOKEN.')
        accounts = list(PoliticalAccount.objects.all() if all else PoliticalAccount.objects.filter(enabled=True))
        figures = figures_by_account([account.pk for account in accounts])
        users, missing = {}, set()
        ids = [account.user_id for account in accounts if account.user_id]
        for start in range(0, len(ids), 100):
            response = requests.get('https://api.x.com/2/users', timeout=30, headers={'Authorization': f'Bearer {token}'},
                                    params={'ids': ','.join(ids[start:start + 100]), 'user.fields': USER_FIELDS})
            if response.status_code != 200:
                raise CommandError(f'X odrzucił zapytanie (HTTP {response.status_code}): {response.text[:200]}')
            payload = response.json()
            users.update({row['id']: row for row in payload.get('data', [])})
            missing.update(str(row.get('resource_id') or row.get('value')) for row in payload.get('errors', []))
        flagged = 0
        for account in accounts:
            data = users.get(account.user_id)
            figure = figures.get(account.pk)
            if data is None:
                problem = 'konto usunięte, zawieszone albo niedostępne' if account.user_id in missing else 'brak danych z X'
            else:
                # Konta partii i instytucji (bez osoby w rejestrze) — tylko sprawdzenie świeżości i parodii.
                name = figure.canonical_name if figure else data.get('name', '')
                problem = identity_problem(data, name)
                if not problem and data.get('username', '').lower() != account.handle.lower():
                    problem = f'nazwa konta zmieniła się na @{data.get("username")}'
            if not problem:
                continue
            flagged += 1
            who = figure.canonical_name if figure else account.display_name
            self.stdout.write(f'PODEJRZANE  @{account.handle} ({who}): {problem}')
            if disable and account.enabled:
                account.enabled = False
                note = f'{timezone.localdate():%d.%m.%Y}: wyłączone przez audit_political_accounts — {problem}.'
                account.confirmation_note = f'{account.confirmation_note}\n{note}'.strip()
                account.save(update_fields=['enabled', 'confirmation_note'])
                self.stdout.write('            → wyłączone z czytania')
        self.stdout.write(self.style.SUCCESS(f'Sprawdzonych kont: {len(accounts)}, podejrzanych: {flagged}'
                                             + ('' if disable else ' (nic nie zmieniono — dodaj --disable, żeby wyłączyć)')))
