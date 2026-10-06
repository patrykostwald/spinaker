"""Kopia poza serwer (Z2): szyfrowana kopia do Backblaze B2, kontrola, test odtworzenia. Hasło i klucze tylko ze środowiska.

python manage.py kopia_zapasowa --z-stdin --nazwa spin_clinic-20261007-0330.sql.gz   - szyfruje stdin i wysyła (deploy/backup.sh)
python manage.py kopia_zapasowa --z-stdin --nazwa media-20261007.tar.gz --rodzaj media
python manage.py kopia_zapasowa --kontrola          - to, co zadanie 4:30: świeżość, retencja, rozmiar
python manage.py kopia_zapasowa --test-odtworzenia  - pobranie ostatniej kopii, odszyfrowanie, spójność zrzutu
python manage.py kopia_zapasowa --lista             - obiekty w koszyku
python manage.py kopia_zapasowa                     - stan (bez sieci)"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Kopia poza serwer: wysyłka ze stdin, kontrola, test odtworzenia, lista, stan.'

    def add_arguments(self, parser):
        parser.add_argument('--z-stdin', action='store_true', help='czytaj kopię ze standardowego wejścia')
        parser.add_argument('--nazwa', default='', help='nazwa pliku kopii (klucz w B2: <rodzaj>/<nazwa>.enc)')
        parser.add_argument('--rodzaj', default='pg', choices=['pg', 'media'])
        parser.add_argument('--kontrola', action='store_true')
        parser.add_argument('--test-odtworzenia', action='store_true')
        parser.add_argument('--lista', action='store_true')

    def handle(self, *args, **options):
        from news import kopia_zapasowa as kz
        out = self.stdout.write
        if options['z_stdin']:
            if not options['nazwa'].strip():
                raise CommandError('Podaj --nazwa <plik>.')
            result = kz.backup(options['nazwa'].strip(), sys.stdin.buffer, options['rodzaj'])
            out(json.dumps(result, ensure_ascii=False))
            if result['status'] == 'ok':
                out(f"KOPIA OK: {result['key']} {kz._human(result['bytes'])} (surowe {kz._human(result['raw_bytes'])}); "
                    f"koszyk {kz._human(result['remote_total_bytes'])}, {result['remote_count']} plików, usunięto {result['deleted']}"
                    + (' - UWAGA: ponad 8 GB' if result.get('size_guard') else ''))
                return
            raise CommandError(f"Kopia nie wysłana: {result.get('error', result['status'])}")
        if options['kontrola']:
            out(json.dumps(kz.daily_check(), ensure_ascii=False))
            return
        if options['test_odtworzenia']:
            if not kz.enabled():
                raise CommandError('Brak konfiguracji B2.')
            result = kz.restore_test()
            out(json.dumps(result, ensure_ascii=False))
            if result['status'] != 'ok':
                raise CommandError('Test odtworzenia nie przeszedł: ' + result.get('detail', ''))
            return
        if options['lista']:
            if not kz.enabled():
                raise CommandError('Brak konfiguracji B2.')
            for obj in sorted(kz.S3().list_objects(''), key=lambda o: o['key']):
                out(f"{obj['modified'].isoformat() if obj['modified'] else '?':<32} {kz._human(obj['size']):>10}  {obj['key']}")
            return
        out(kz.report_line())
        out(json.dumps(kz.snapshot(), ensure_ascii=False, indent=2))
