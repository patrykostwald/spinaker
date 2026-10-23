"""manage.py korektor [--dni N] [--napraw] [--wyslij] [--json] - strażnik spójności osób i urzędów (news/korektor.py)."""
import json

from django.core.management.base import BaseCommand

from news import korektor


class Command(BaseCommand):
    help = ('Korektor: urzędy i osoby w treściach z ostatnich N dni, konta X z listy zweryfikowanej, puste sekcje profili. '
            '--napraw: tylko bezpieczne poprawki (metadane gościa, wstrzymanie i ponowne wygenerowanie, przypięcie kont X).')

    def add_arguments(self, parser):
        parser.add_argument('--dni', type=int, default=2)
        parser.add_argument('--napraw', action='store_true')
        parser.add_argument('--wyslij', action='store_true', help='Wyślij raport mailem na LOOP_REPORT_EMAIL.')
        parser.add_argument('--profile', type=int, default=0, help='Najwyżej tyle profili (0 = wszystkie).')
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        report = korektor.run(dni=options['dni'], napraw=options['napraw'], profile_limit=options['profile'] or None)
        if options['wyslij']:
            report['mail'] = korektor.send(report)
        if options['json']:
            self.stdout.write(json.dumps(report, ensure_ascii=False, default=str, indent=1))
        else:
            self.stdout.write(korektor.text(report))
            if 'mail' in report:
                self.stdout.write(f"Mail: {report['mail']['status']}")
