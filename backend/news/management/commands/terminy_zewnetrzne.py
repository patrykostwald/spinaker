"""Terminy zewnętrzne (Z3): domeny, TLS, DNS, salda API, token GitHub, Codex.

python manage.py terminy_zewnetrzne            - tabela z ostatniej kontroli (bez sieci)
python manage.py terminy_zewnetrzne --sprawdz  - kontrola teraz (sieć), potem tabela
python manage.py terminy_zewnetrzne --raport   - linie jak w Raporcie pętli"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Strażnik terminów zewnętrznych: tabela, kontrola teraz, linie raportu.'

    def add_arguments(self, parser):
        parser.add_argument('--sprawdz', action='store_true')
        parser.add_argument('--raport', action='store_true')

    def handle(self, *args, **options):
        from news import terminy_zewnetrzne as tz
        if options['sprawdz']:
            result = tz.run()
            self.stdout.write(f"Sprawdzono {result['items']} pozycji: krytyczne {result['critical']}, uwaga {result['warning']}, "
                              f"niesprawdzone {result['unknown']}, maile {result['mails']}")
        if options['raport']:
            self.stdout.write('\n'.join(tz.report_lines()))
            return
        self.stdout.write(tz.table())
