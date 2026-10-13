"""Pilotaż v3 (docs/PILOTAZ_V3.md). Nic nie publikuje; flagi zostają wyłączone.

python manage.py pilotaz par --n 50 [--generuj --temat "podatek od nieruchomości" --temat "CPK"] [--max-wywolan 60] [--dry-run] [--wyjscie DIR]
python manage.py pilotaz lancuch --dni 20 [--generuj] [--max-wywolan 160] [--dry-run] [--wyjscie DIR]
python manage.py pilotaz raport --plik <arkusz.csv> [--rodzaj par|lancuch]
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Pilotaż par „Wcześniej i teraz” i ciągów przyczyn: arkusze do przeglądu, metryki, próg akceptacji.'

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', required=True)
        pairs = sub.add_parser('par')
        pairs.add_argument('--n', type=int, default=50)
        pairs.add_argument('--generuj', action='store_true', help='Także generator tematów (wywołania darmowych modeli).')
        pairs.add_argument('--temat', action='append', default=[])
        pairs.add_argument('--max-wywolan', type=int, default=60)
        pairs.add_argument('--dry-run', action='store_true', help='Bez nowych kandydatów i wywołań modeli; tylko arkusz.')
        pairs.add_argument('--wyjscie', default=None)
        chains = sub.add_parser('lancuch')
        chains.add_argument('--dni', type=int, default=20)
        chains.add_argument('--generuj', action='store_true')
        chains.add_argument('--max-wywolan', type=int, default=160)
        chains.add_argument('--dry-run', action='store_true')
        chains.add_argument('--wyjscie', default=None)
        rep = sub.add_parser('raport')
        rep.add_argument('--plik', required=True)
        rep.add_argument('--rodzaj', choices=['par', 'lancuch'], default='par')

    def handle(self, *args, **opts):
        from news import pilotaz
        if opts['action'] == 'par':
            if opts['generuj'] and not opts['temat']:
                raise CommandError('Generator wymaga co najmniej jednego --temat.')
            result = pilotaz.pairs(opts['n'], generate=opts['generuj'], topics=opts['temat'], max_calls=opts['max_wywolan'],
                                   dry_run=opts['dry_run'], path=opts['wyjscie'])
        elif opts['action'] == 'lancuch':
            result = pilotaz.chains(opts['dni'], generate=opts['generuj'], max_calls=opts['max_wywolan'],
                                    dry_run=opts['dry_run'], path=opts['wyjscie'])
        else:
            try:
                result = pilotaz.report(opts['plik'], opts['rodzaj'])
            except pilotaz.ReportError as error:
                raise CommandError(f'Błąd arkusza: {error}') from None
        self.stdout.write(json.dumps(result, ensure_ascii=False, default=str, indent=2))
