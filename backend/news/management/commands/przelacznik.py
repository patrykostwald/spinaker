"""Przełączniki v3 bez restartu (kill switch, cisza wyborcza) - docs/RUNBOOK_KILL_SWITCH.md.

python manage.py przelacznik lista
python manage.py przelacznik ustaw POSITION_PAIRS_ENABLED off --kto <login> [--uwaga "..."]
python manage.py przelacznik ustaw ELECTION_SILENCE on --od 2027-10-09T00:00:00+02:00 --do 2027-10-10T21:00:00+02:00 --kto <login>
python manage.py przelacznik usun POSITION_PAIRS_ENABLED --kto <login>     (wraca wartość z env)
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class Command(BaseCommand):
    help = 'Przełączniki v3 w bazie (bez restartu), każdy zapis w dzienniku SiteFlagChange.'

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', required=True)
        sub.add_parser('lista')
        put = sub.add_parser('ustaw')
        put.add_argument('key')
        put.add_argument('value', choices=['on', 'off'])
        put.add_argument('--od', default=None)
        put.add_argument('--do', default=None)
        put.add_argument('--kto', required=True)
        put.add_argument('--uwaga', default='')
        rm = sub.add_parser('usun')
        rm.add_argument('key')
        rm.add_argument('--kto', required=True)

    def handle(self, *args, **opts):
        from news.clinic_models import SiteFlag, SiteFlagChange
        from news.v3_flags import KNOWN, flag, silence
        if opts['action'] == 'lista':
            rows = {r.key: r for r in SiteFlag.objects.all()}
            for key in KNOWN:
                row = rows.get(key)
                where = f'baza: {row.value} od {row.active_from} do {row.active_until}' if row else 'env'
                self.stdout.write(f'{key}\tteraz={flag(key)}\t{where}')
            self.stdout.write(f'cisza wyborcza teraz: {silence()}')
            return
        key = opts['key'].strip().upper()
        if key not in KNOWN:
            raise CommandError('Nieznany przełącznik. Dozwolone: ' + ', '.join(KNOWN))
        user = get_user_model().objects.filter(username=opts['kto'], is_staff=True).first()
        if user is None:
            raise CommandError('Przełącza członek personelu (is_staff).')
        row = SiteFlag.objects.filter(key=key).first()
        before = {'value': row.value, 'from': str(row.active_from), 'until': str(row.active_until)} if row else {}
        if opts['action'] == 'usun':
            if row:
                row.delete()
            SiteFlagChange.objects.create(key=key, before=before, after={'deleted': True}, changed_by=user)
            self.stdout.write(f'{key}: usunięto, obowiązuje env ({flag(key)})')
            return
        dates = []
        for name in ('od', 'do'):
            value = opts[name]
            parsed = parse_datetime(value) if value else None
            if value and parsed is None:
                raise CommandError(f'--{name}: data w formacie ISO 8601, np. 2027-10-09T00:00:00+02:00')
            dates.append(parsed)
        row, _ = SiteFlag.objects.update_or_create(key=key, defaults={
            'value': opts['value'] == 'on', 'active_from': dates[0], 'active_until': dates[1], 'note': opts['uwaga'][:300],
            'changed_by': user, 'changed_at': timezone.now()})
        SiteFlagChange.objects.create(key=key, before=before, changed_by=user,
                                      after={'value': row.value, 'from': str(row.active_from), 'until': str(row.active_until)})
        self.stdout.write(f'{key}: {row.value} (teraz={flag(key)})')
