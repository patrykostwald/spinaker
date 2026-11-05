"""Raport pętli agentów (audyt 5.10). Tylko odczyt, bez sekretów i bez modeli.

python manage.py raport_petli            - tekst raportu (ten sam, który idzie mailem o 7:05)
python manage.py raport_petli --json     - dane raportu (jak w panelu)
python manage.py raport_petli --wyslij   - wysyła raport teraz (adres: LOOP_REPORT_EMAIL, potem COUNCIL_RECRUITER_EMAIL, X_POST_ALERT_EMAIL)
python manage.py raport_petli --wyslij --raz - wysyła tylko, gdy dziś jeszcze nie wyszedł (skrypty wdrożenia)"""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Raport pętli agentów: czy działają, co wyprodukowały, co czeka na odbiorcę ponad termin.'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true')
        parser.add_argument('--wyslij', action='store_true', help='wyślij mailem (także drugi raz tego samego dnia)')
        parser.add_argument('--raz', action='store_true', help='z --wyslij: pomiń, gdy raport dziś już wyszedł')

    def handle(self, *args, **options):
        from news import raport_petli
        if options['wyslij']:
            result = raport_petli.send(force=not options['raz'])
            self.stdout.write(f"Wysyłka: {result['status']} (adres: {'ustawiony' if raport_petli.recipient() else 'brak - ustaw LOOP_REPORT_EMAIL'})")
            return
        report = raport_petli.build()
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) if options['json'] else raport_petli.text(report))
