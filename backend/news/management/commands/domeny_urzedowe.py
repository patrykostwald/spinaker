"""Lista domen urzędowych i partyjnych (news/official_domains.py).

python manage.py domeny_urzedowe lista
python manage.py domeny_urzedowe dodaj example.gov.pl --rodzaj urzad --zrodlo "https://..." --uwaga "..." --kto <login>
python manage.py domeny_urzedowe usun example.pl --uwaga "powód" --kto <login>
python manage.py domeny_urzedowe sprawdz [domena]     (DNS i MX, bez wysyłania wiadomości)
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Domeny urzędowe i partyjne do ścieżki osoby w zgłoszeniach par (lista, dodaj, usun, sprawdz).'

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', required=True)
        sub.add_parser('lista')
        add = sub.add_parser('dodaj')
        add.add_argument('domena')
        add.add_argument('--rodzaj', default='urzad', choices=['urzad', 'parlament', 'partia', 'klub'])
        add.add_argument('--zrodlo', required=True)
        add.add_argument('--uwaga', default='')
        add.add_argument('--kto', required=True)
        rm = sub.add_parser('usun')
        rm.add_argument('domena')
        rm.add_argument('--uwaga', required=True)
        rm.add_argument('--kto', required=True)
        chk = sub.add_parser('sprawdz')
        chk.add_argument('domena', nargs='?')

    def handle(self, *args, **opts):
        from news import official_domains as od
        action = opts['action']
        if action == 'lista':
            for row in od.entries():
                self.stdout.write(f"{row['domain']}\t{row.get('kind', '')}\t{row.get('status', '')}\t{row.get('origin')}\t"
                                  f"{row.get('checked', '')}\t{row.get('source', '')[:80]}")
            return
        if action == 'sprawdz':
            targets = [od.normalize(opts['domena'])] if opts['domena'] else od.domains()
            for domain in targets:
                r = od.check(domain)
                mx = {True: 'MX tak', False: 'MX brak', None: 'MX nie sprawdzono (brak dnspython)'}[r['mx']]
                self.stdout.write(f"{domain}\t{'DNS tak' if r['dns'] else 'DNS BRAK'}\t{mx}")
            return
        try:
            if action == 'dodaj':
                od.change(opts['domena'], 'add', kind=opts['rodzaj'], source=opts['zrodlo'], note=opts['uwaga'], by=opts['kto'])
            else:
                od.change(opts['domena'], 'remove', note=opts['uwaga'], by=opts['kto'])
        except ValueError as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f"{action}: {od.normalize(opts['domena'])} (domen na liście: {len(od.domains())})")
