"""Import review-only public-figure organisation candidates from curated CSV."""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.political_models import PublicFigure, PublicFigureOrganisationRelation, RegisteredOrganisation


REQUIRED_HEADERS = {
    'public_figure_id', 'organisation_name', 'krs_number', 'kind', 'official_register_url',
    'public_role', 'relation_status', 'evidence_url',
}
FORBIDDEN_HEADERS = {'pesel', 'date_of_birth', 'birth_date', 'data_urodzenia'}
KINDS = {choice[0] for choice in RegisteredOrganisation._meta.get_field('kind').choices}
STATUSES = {choice[0] for choice in PublicFigureOrganisationRelation._meta.get_field('relation_status').choices}


def normalized(row, key):
    return (row.get(key) or '').strip()


class Command(BaseCommand):
    help = ('Wczytuje wyłącznie kandydatury relacji osoba publiczna–podmiot. '
            'Wymaga publicznego dowodu i nigdy nie przyjmuje PESEL ani daty urodzenia.')

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--apply', action='store_true', help='Zapisz kandydatury po pomyślnym podglądzie.')

    def handle(self, *args, **options):
        path = Path(options['csv_path'])
        if not path.is_file():
            raise CommandError(f'Nie znaleziono pliku: {path}')
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = REQUIRED_HEADERS - headers
            forbidden = FORBIDDEN_HEADERS & headers
            if forbidden:
                raise CommandError('Plik zawiera niedozwolone dane identyfikacyjne: ' + ', '.join(sorted(forbidden)))
            if missing:
                raise CommandError(f'Brakuje kolumn: {", ".join(sorted(missing))}')
            rows = list(reader)

        prepared, errors = [], []
        for line_number, row in enumerate(rows, start=2):
            figure_id = normalized(row, 'public_figure_id')
            krs = normalized(row, 'krs_number')
            kind = normalized(row, 'kind')
            relation_status = normalized(row, 'relation_status')
            missing_values = [key for key in REQUIRED_HEADERS if not normalized(row, key)]
            if missing_values:
                errors.append(f'Wiersz {line_number}: brak wartości: {", ".join(sorted(missing_values))}')
                continue
            figure = PublicFigure.objects.filter(pk=figure_id, archived=False).first() if figure_id.isdigit() else None
            if not figure:
                errors.append(f'Wiersz {line_number}: nie ma aktywnej osoby publicznej o wskazanym public_figure_id')
                continue
            if not (len(krs) == 10 and krs.isdigit()):
                errors.append(f'Wiersz {line_number}: KRS musi mieć 10 cyfr')
                continue
            if kind not in KINDS or relation_status not in STATUSES:
                errors.append(f'Wiersz {line_number}: nieznany rodzaj podmiotu albo status relacji')
                continue
            prepared.append((line_number, row, figure))

        if errors:
            for error in errors:
                self.stderr.write(error)
            raise CommandError(f'Nie zapisano danych; błędnych wierszy: {len(errors)}.')

        mode = 'Zapisano' if options['apply'] else 'Podgląd'
        if not options['apply']:
            self.stdout.write(f'{mode}: {len(prepared)} kandydatur. Bez zapisu; każda wymaga dowodu i decyzji redakcji.')
            return

        created = updated = 0
        with transaction.atomic():
            for _, row, figure in prepared:
                organisation, org_created = RegisteredOrganisation.objects.update_or_create(
                    krs_number=normalized(row, 'krs_number'),
                    defaults={
                        'name': normalized(row, 'organisation_name'),
                        'kind': normalized(row, 'kind'),
                        'official_register_url': normalized(row, 'official_register_url'),
                        'source_checked_at': timezone.now(),
                        'archived': False,
                    },
                )
                relation, relation_created = PublicFigureOrganisationRelation.objects.update_or_create(
                    public_figure=figure,
                    organisation=organisation,
                    public_role=normalized(row, 'public_role'),
                    relation_status=normalized(row, 'relation_status'),
                    defaults={
                        'evidence_url': normalized(row, 'evidence_url'),
                        'evidence_note': normalized(row, 'evidence_note'),
                        'verification_status': 'pending_review',
                        'verified_by': None,
                        'verified_at': None,
                    },
                )
                created += int(org_created or relation_created)
                updated += int(not org_created and not relation_created)
        self.stdout.write(f'{mode}: {len(prepared)} kandydatur; nowe {created}; zaktualizowane {updated}. Wszystkie są w kolejce redakcyjnej.')
