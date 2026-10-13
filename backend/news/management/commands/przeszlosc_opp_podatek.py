from datetime import date
from decimal import InvalidOperation
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

import requests
from django.core.management.base import BaseCommand, CommandError
from news import opp_podatek as opp


class Command(BaseCommand):
    help = 'Import wykazu MF OPP, osobno od dotacji. Lata oznaczają lata wpłaty, nie podatkowe.'

    def add_arguments(self, parser):
        parser.add_argument('--plik', help='Lokalny XLSX; wymaga --lata (jeden rok wpłaty) i --data-pliku.')
        parser.add_argument('--dry-run', action='store_true', help='Parsowanie i archiwum, bez zapisu do bazy.')
        parser.add_argument('--archiwum', help='Katalog kopii; domyślnie OPP_ARCHIWUM_DIR albo reports/opp.')
        parser.add_argument('--lata', help='Lata wpłaty, np. 2024,2025,2026; domyślnie najnowszy wykaz.')
        parser.add_argument('--data-pliku', help='Stan lokalnego pliku YYYY-MM-DD, nie data pobrania.')
        parser.add_argument('--rok-podatkowy', type=int, help='Dla lokalnego pliku; domyślnie rok wpłaty minus 1.')
        parser.add_argument('--resource-url', help='Adres źródłowego XLSX z api.dane.gov.pl dla lokalnej kopii.')

    def handle(self, *args, **options):
        try:
            years = [int(y.strip()) for y in options['lata'].split(',')] if options['lata'] else None
            if years and any(y < 2000 or y > 2099 for y in years):
                raise ValueError('Nieprawidłowy rok wpłaty.')
            if options['plik']:
                if not years or len(years) != 1 or not options['data_pliku']:
                    raise ValueError('--plik wymaga --lata z jednym rokiem wpłaty oraz --data-pliku YYYY-MM-DD.')
                tax = options['rok_podatkowy'] if options['rok_podatkowy'] is not None else years[0] - 1
                if not 1999 <= tax < years[0]:
                    raise ValueError('Nieprawidłowy rok podatkowy.')
                selected = [dict(payment_year=years[0], tax_year=tax,
                                 file_date=date.fromisoformat(options['data_pliku']).isoformat(),
                                 resource_url=opp.official_url(options['resource_url']) if options['resource_url'] else '')]
            else:
                if any(options[k] for k in ('data_pliku', 'rok_podatkowy', 'resource_url')):
                    raise ValueError('Metadane lokalne wymagają --plik.')
                selected = opp.resources(years)
            for resource in selected:
                if options['plik']:
                    with Path(options['plik']).open('rb') as stream:
                        raw = stream.read(opp.MAX_BYTES + 1)
                else:
                    raw, final_url = opp.download(resource['resource_url'])
                    resource = {**resource, 'resource_url': final_url}
                records, stats = opp.parse_xlsx(raw, resource)
                archived = opp.archive_file(raw, resource, options['archiwum'])
                self.stdout.write(f"Rok wpłaty: {resource['payment_year']}; rok podatkowy: {resource['tax_year']}; "
                                  f"stan: {resource['file_date']}; rekordy: {len(records)}; "
                                  f"pominięte błędne: {stats['bledne']}; duplikaty: {stats['duplikaty']}")
                self.stdout.write(f'Archiwum: {archived}')
                if options['dry_run']:
                    self.stdout.write('Dry-run: bez zapisu do bazy.')
                    continue
                if stats['bledne']:
                    self.stdout.write('Błędne wiersze: usuwanie nieobecnych rekordów wyłączone.')
                counts = opp.save_records(records, remove_stale=not stats['bledne'])
                self.stdout.write(f"Utworzone: {counts['created']}; zaktualizowane: {counts['updated']}; "
                                  f"bez zmian: {counts['unchanged']}; usunięte: {counts['removed']}")
        except (OSError, ValueError, KeyError, IndexError, TypeError, OverflowError, BadZipFile, ParseError,
                InvalidOperation, requests.RequestException) as exc:
            raise CommandError(str(exc)) from exc
