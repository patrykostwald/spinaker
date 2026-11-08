"""Wczytuje doniesienia medialne o podmiotach osób publicznych do kolejki przeglądu (nigdy od razu publicznie).

CSV (UTF-8, nagłówki): public_figure_id (albo public_figure_name = dokładna nazwa osoby w bazie), krs_number, category, source_url, source_title,
source_outlet, published_on, quote, match_basis; opcjonalnie organisation_name i city (potrzebne z --dodaj-podmioty).
category: mention | alleged | denied | other; match_basis: identifier | name_only. Podmiot musi być w bazie (krs_number) albo, z --dodaj-podmioty,
zostaje dodany z oficjalnego odpisu KRS, jeśli nazwa i miejscowość siedziby z pliku zgadzają się z odpisem (bez modelu AI, bez kosztów).
Podmiot BEZ KRS (jednoosobowa działalność, fundusz, gmina): puste krs_number oraz kolumny organisation_name, entity_register_url (https, link do właściwego
rejestru, np. CEIDG) i opcjonalnie entity_identifier (np. „NIP 1234563218”).
Bez --apply tylko sprawdza i liczy. Zakazane kolumny: PESEL, data urodzenia. Pozycje trafiają ze statusem „do przeglądu”.
"""
import csv
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from news.political_models import (MEDIA_MENTION_CATEGORIES, MEDIA_MENTION_MATCH, MEDIA_QUOTE_LIMIT, PublicFigure,
                                   PublicFigureMediaMention, RegisteredOrganisation)

REQUIRED = {'category', 'source_url', 'source_title'}
FORBIDDEN = {'pesel', 'date_of_birth', 'birth_date', 'data_urodzenia'}
CATEGORIES = {k for k, _ in MEDIA_MENTION_CATEGORIES}
MATCHES = {k for k, _ in MEDIA_MENTION_MATCH}


class Command(BaseCommand):
    help = 'Wczytuje doniesienia medialne do kolejki przeglądu (bez --apply tylko sprawdza).'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--dodaj-podmioty', action='store_true', help='Dodaj brakujące podmioty z urzędowego odpisu KRS (po zgodności nazwy i miejscowości).')

    def handle(self, *args, **options):
        path = Path(options['csv_path'])
        if not path.is_file():
            raise CommandError('Nie ma takiego pliku.')
        with path.open(encoding='utf-8-sig', newline='') as fh:
            reader = csv.DictReader(fh)
            headers = {h.strip() for h in (reader.fieldnames or [])}
            if headers & FORBIDDEN:
                raise CommandError('Plik zawiera zakazane kolumny danych osobowych.')
            if not REQUIRED <= headers or not ({'public_figure_id', 'public_figure_name'} & headers):
                raise CommandError(f'Brakuje kolumn: {", ".join(sorted(REQUIRED - headers))} oraz public_figure_id albo public_figure_name')
            rows = list(reader)
        added = skipped = 0
        errors = []
        for n, row in enumerate(rows, start=2):
            get = lambda k: (row.get(k) or '').strip()   # noqa: E731
            if get('public_figure_id').isdigit():
                figure = PublicFigure.objects.filter(pk=int(get('public_figure_id')), archived=False).first()
            elif get('public_figure_name'):
                found = list(PublicFigure.objects.filter(canonical_name__iexact=get('public_figure_name'), archived=False)[:2])
                figure = found[0] if len(found) == 1 else None      # niejednoznaczna nazwa = błąd, nie zgadujemy
            else:
                figure = None
            no_krs = not get('krs_number')
            org = None if no_krs else RegisteredOrganisation.objects.filter(krs_number=get('krs_number').zfill(10), archived=False).first()
            new_extract = None
            if org is None and not no_krs and options['dodaj_podmioty']:
                new_extract, why = self.verified_extract(get('krs_number'), get('organisation_name'), get('city'))
                if new_extract is None:
                    errors.append(f'wiersz {n}: nie dodano podmiotu ({why})')
                    continue
            category, basis = get('category'), get('match_basis') or 'name_only'
            quote = get('quote')
            problem = ('nie ma takiej osoby (albo nazwa niejednoznaczna)' if figure is None
                       else 'podmiot bez KRS wymaga organisation_name i entity_register_url (https)' if no_krs and not (get('organisation_name') and get('entity_register_url').startswith('https://'))
                       else 'nie ma podmiotu w bazie' if org is None and not no_krs and new_extract is None
                       else 'zła kategoria' if category not in CATEGORIES else 'zła podstawa dopasowania' if basis not in MATCHES
                       else f'cytat dłuższy niż {MEDIA_QUOTE_LIMIT} znaków' if len(quote) > MEDIA_QUOTE_LIMIT else '')
            published_on = None
            if not problem and get('published_on'):
                try:
                    published_on = date.fromisoformat(get('published_on'))
                except ValueError:
                    problem = 'zła data (RRRR-MM-DD)'
            if problem:
                errors.append(f'wiersz {n}: {problem}')
                continue
            if no_krs:
                duplicate = PublicFigureMediaMention.objects.filter(public_figure=figure, organisation__isnull=True, entity_name=get('organisation_name'), source_url=get('source_url')).exists()
            else:
                duplicate = org is not None and PublicFigureMediaMention.objects.filter(public_figure=figure, organisation=org, source_url=get('source_url')).exists()
            if duplicate:
                skipped += 1
                continue
            if org is None and not no_krs:
                if not options['apply']:
                    added += 1                     # raport: podmiot do dodania z odpisu KRS, pozycja do kolejki
                    self.stdout.write(f'  nowy podmiot z KRS: {new_extract.name} ({new_extract.krs}, {new_extract.seat_city})')
                    continue
                from news import krs_pokrycie
                org = krs_pokrycie.save_extract(new_extract)
            entity = {'entity_name': get('organisation_name')[:300], 'entity_identifier': get('entity_identifier')[:40],
                      'entity_register_url': get('entity_register_url')} if no_krs else {}
            mention = PublicFigureMediaMention(public_figure=figure, organisation=org, category=category, match_basis=basis, **entity,
                source_url=get('source_url'), source_title=get('source_title')[:300], source_outlet=get('source_outlet')[:120],
                published_on=published_on, quote=quote, collected_by='import')
            try:
                mention.full_clean(exclude=['reviewed_by'])
            except Exception as exc:   # noqa: BLE001 - komunikat walidacji dla człowieka
                errors.append(f'wiersz {n}: {exc}')
                continue
            if options['apply']:
                mention.save()
            added += 1
        self.stdout.write(f'{"DODANO" if options["apply"] else "Do dodania"}: {added}, pominięto (już są): {skipped}, błędy: {len(errors)}')
        for e in errors[:20]:
            self.stdout.write(f'  {e}')

    @staticmethod
    def verified_extract(number, claimed_name, city):
        """(odpis, powód): oficjalny odpis KRS przyjmujemy tylko, gdy nazwa z pliku zgadza się z odpisem ORAZ miejscowość siedziby też."""
        from news import krs
        from news.doniesienia_badacz import _fold, strict_name_match
        if not claimed_name or not city:
            return None, 'wymagane kolumny organisation_name i city'
        extract, status = krs.fetch_status(number, full=True)
        if extract is None:
            return None, f'KRS: {status}'
        if not any(strict_name_match(claimed_name, known) for known in [extract.name, *getattr(extract, 'former_names', [])]):
            return None, f'nazwa niezgodna z odpisem: {extract.name}'
        if _fold(city) != _fold(extract.seat_city):
            return None, f'miejscowość niezgodna z odpisem: {extract.seat_city}'
        return extract, 'ok'
