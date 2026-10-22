"""Puls z zewnątrz (Z3): ping do healthchecks.io.

python manage.py puls_zewnetrzny          - stan ostatniego pingu
python manage.py puls_zewnetrzny --raz    - jeden ping teraz (jak zadanie co 5 minut: /start, potem sukces albo /fail)"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Puls z zewnątrz: stan albo jeden ping teraz.'

    def add_arguments(self, parser):
        parser.add_argument('--raz', action='store_true')

    def handle(self, *args, **options):
        from news import puls_zewnetrzny
        if options['raz']:
            result = puls_zewnetrzny.run()
            self.stdout.write(f"Ping: {result['status']}" + (f" - {result['error']}" if result.get('error') else '')
                              + (' (dostarczony)' if result.get('delivered') else ''))
        self.stdout.write(puls_zewnetrzny.report_line())
