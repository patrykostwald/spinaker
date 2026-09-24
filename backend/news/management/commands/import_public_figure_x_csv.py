"""Import reviewed public X-link evidence without matching people by name."""
import csv
from pathlib import Path
from urllib.parse import urlsplit

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from news.political_models import HANDLE_VALIDATOR, PublicFigure, SocialHandleEvidence


REQUIRED_HEADERS = {
    'official_roster_source', 'official_roster_external_id', 'public_figure_name',
    'role_category', 'role_title', 'proposed_x_handle', 'official_evidence_url',
    'direct_x_url', 'verification_status', 'note',
}
FORBIDDEN_HEADERS = {'pesel', 'date_of_birth', 'birth_date', 'data_urodzenia', 'address'}
CONFIRMED_STATUS = 'confirmed_by_official_link'
X_HOSTS = {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}


def cell(row, key):
    return (row.get(key) or '').strip()


def is_https(value):
    parsed = urlsplit(value)
    return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password


def is_x_url(value):
    return is_https(value) and (urlsplit(value).hostname or '').lower() in X_HOSTS


def exact_figure_for_row(row, evidence_url):
    """Resolve only a direct URL or a standalone official European Parliament id.

    The latter is an exact primary key from the official PE open-data record.
    Combined CSV identifiers are intentionally not used: they document an
    editorial lead across rosters and can otherwise hide a name-based match.
    """
    figures = list(PublicFigure.objects.filter(archived=False).filter(
        models_q(evidence_url)
    ).order_by('pk'))
    if len(figures) == 1:
        return figures[0]
    source = cell(row, 'official_roster_source')
    external_id = cell(row, 'official_roster_external_id')
    if (source == 'europarl open data (show-current, PL)'
            and external_id.isdigit()
            and (urlsplit(evidence_url).hostname or '').lower() == 'data.europarl.europa.eu'):
        return PublicFigure.objects.filter(
            import_key=f'parliamentary:ep:{external_id}', archived=False,
        ).order_by('pk').first()
    return None


class Command(BaseCommand):
    help = ('Wczytuje dowody linków X z ręcznie przygotowanego CSV. Zapisuje wyłącznie dowody z bezpośrednim '
            'oficjalnym URL-em i jednym dokładnie rozpoznanym profilem; nie dopasowuje osób po nazwisku, '
            'nie pyta API X i nie uruchamia pobierania.')

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        path = Path(options['csv_path'])
        if not path.is_file():
            raise CommandError(f'Nie znaleziono pliku: {path}')
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            forbidden = headers & FORBIDDEN_HEADERS
            missing = REQUIRED_HEADERS - headers
            if forbidden:
                raise CommandError('Plik zawiera niedozwolone dane: ' + ', '.join(sorted(forbidden)))
            if missing:
                raise CommandError('Brakuje kolumn: ' + ', '.join(sorted(missing)))
            rows = list(reader)

        accepted, unresolved, invalid = [], [], []
        for line, row in enumerate(rows, start=2):
            if cell(row, 'verification_status') != CONFIRMED_STATUS:
                continue
            handle = cell(row, 'proposed_x_handle').lstrip('@')
            evidence_url, x_url = cell(row, 'official_evidence_url'), cell(row, 'direct_x_url')
            if not handle or not is_https(evidence_url) or not is_x_url(x_url):
                invalid.append(f'Wiersz {line}: niepełny albo nieprawidłowy dowód URL.')
                continue
            try:
                HANDLE_VALIDATOR(handle)
            except ValidationError as exc:
                invalid.append(f'Wiersz {line}: nieprawidłowy handle ({"; ".join(exc.messages)}).')
                continue
            # Direct URL identity and the official PE primary key are the only
            # automatic connections permitted.
            figure = exact_figure_for_row(row, evidence_url)
            if figure is None:
                unresolved.append({
                    'line': line, 'name': cell(row, 'public_figure_name'), 'handle': handle,
                    'evidence_url': evidence_url, 'reason': 'brak_jednoznacznego_profilu_po_url',
                })
                continue
            try:
                SocialHandleEvidence(
                    subject_content_type=ContentType.objects.get_for_model(PublicFigure),
                    subject_object_id=figure.pk, handle=handle,
                    evidence_url=evidence_url, extracted_url=x_url,
                ).full_clean()
            except ValidationError as exc:
                invalid.append(f'Wiersz {line}: nieprawidłowy dowód ({"; ".join(exc.messages)}).')
                continue
            accepted.append((line, row, figure))

        existing = 0
        for _, row, figure in accepted:
            if SocialHandleEvidence.objects.filter(
                subject_content_type=ContentType.objects.get_for_model(PublicFigure),
                subject_object_id=figure.pk, platform='x', handle=cell(row, 'proposed_x_handle').lstrip('@'),
            ).exists():
                existing += 1
        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                f'PODGLĄD: potwierdzone linki {len(accepted)}; już zapisane {existing}; '
                f'wymagające ręcznego połączenia {len(unresolved)}; pominięte błędne {len(invalid)}. '
                'Bez zapisu, bez API X.'
            ))
            for problem in invalid:
                self.stdout.write(self.style.WARNING('POMINIĘTO: ' + problem))
            return

        content_type = ContentType.objects.get_for_model(PublicFigure)
        created = 0
        with transaction.atomic():
            for _, row, figure in accepted:
                _, was_created = SocialHandleEvidence.objects.get_or_create(
                    subject_content_type=content_type,
                    subject_object_id=figure.pk,
                    platform='x',
                    handle=cell(row, 'proposed_x_handle').lstrip('@'),
                    defaults={
                        'evidence_url': cell(row, 'official_evidence_url'),
                        'extracted_url': cell(row, 'direct_x_url'),
                        'status': 'pending_review',
                    },
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f'Zapisano dowody X: nowe {created}; już istniejące {existing}; '
            f'wymagające ręcznego połączenia {len(unresolved)}; pominięte błędne {len(invalid)}. '
            'Nie utworzono kont X ani nie wykonano zapytania do X.'
        ))
        for problem in invalid:
            self.stdout.write(self.style.WARNING('POMINIĘTO: ' + problem))
        for item in unresolved:
            self.stdout.write(f'NIEPOŁĄCZONE wiersz {item["line"]}: {item["name"]} @{item["handle"]} — {item["reason"]}')


def models_q(evidence_url):
    """Kept separate to make the exact, URL-only identity rule auditable."""
    from django.db.models import Q
    return Q(official_profile_url=evidence_url) | Q(evidence_url=evidence_url)
