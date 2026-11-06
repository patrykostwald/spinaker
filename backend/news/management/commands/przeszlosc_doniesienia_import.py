"""Wczytuje doniesienia medialne o podmiotach osób publicznych do kolejki przeglądu (nigdy od razu publicznie).

CSV (UTF-8, nagłówki): public_figure_id, krs_number, category, source_url, source_title, source_outlet, published_on, quote, match_basis.
category: mention | alleged | denied | other; match_basis: identifier | name_only. Podmiot musi być w bazie (krs_number).
Bez --apply tylko sprawdza i liczy. Zakazane kolumny: PESEL, data urodzenia. Pozycje trafiają ze statusem „do przeglądu”.
"""
import csv
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from news.political_models import (MEDIA_MENTION_CATEGORIES, MEDIA_MENTION_MATCH, MEDIA_QUOTE_LIMIT, PublicFigure,
                                   PublicFigureMediaMention, RegisteredOrganisation)

REQUIRED = {'public_figure_id', 'krs_number', 'category', 'source_url', 'source_title'}
FORBIDDEN = {'pesel', 'date_of_birth', 'birth_date', 'data_urodzenia'}
CATEGORIES = {k for k, _ in MEDIA_MENTION_CATEGORIES}
MATCHES = {k for k, _ in MEDIA_MENTION_MATCH}


class Command(BaseCommand):
    help = 'Wczytuje doniesienia medialne do kolejki przeglądu (bez --apply tylko sprawdza).'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        path = Path(options['csv_path'])
        if not path.is_file():
            raise CommandError('Nie ma takiego pliku.')
        with path.open(encoding='utf-8-sig', newline='') as fh:
            reader = csv.DictReader(fh)
            headers = {h.strip() for h in (reader.fieldnames or [])}
            if headers & FORBIDDEN:
                raise CommandError('Plik zawiera zakazane kolumny danych osobowych.')
            if not REQUIRED <= headers:
                raise CommandError(f'Brakuje kolumn: {", ".join(sorted(REQUIRED - headers))}')
            rows = list(reader)
        added = skipped = 0
        errors = []
        for n, row in enumerate(rows, start=2):
            get = lambda k: (row.get(k) or '').strip()   # noqa: E731
            figure = PublicFigure.objects.filter(pk=int(get('public_figure_id')), archived=False).first() if get('public_figure_id').isdigit() else None
            org = RegisteredOrganisation.objects.filter(krs_number=get('krs_number').zfill(10), archived=False).first()
            category, basis = get('category'), get('match_basis') or 'name_only'
            quote = get('quote')
            problem = ('nie ma takiej osoby' if figure is None else 'nie ma podmiotu w bazie' if org is None
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
            if PublicFigureMediaMention.objects.filter(public_figure=figure, organisation=org, source_url=get('source_url')).exists():
                skipped += 1
                continue
            mention = PublicFigureMediaMention(public_figure=figure, organisation=org, category=category, match_basis=basis,
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
