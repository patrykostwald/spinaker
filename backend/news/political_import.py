"""Validation for staff CSV imports of political accounts.

Imports deliberately never call X and always create disabled, unconfirmed rows.
"""
from __future__ import annotations

import csv
import io

from django.core.exceptions import ValidationError
from django.db.models.functions import Lower

from news.political_models import PoliticalAccount


REQUIRED_COLUMNS = {
    'user_id', 'handle', 'display_name', 'camp', 'confirmation_url', 'confirmation_note',
}
OPTIONAL_COLUMNS = {'poll_interval_minutes'}
MAX_ROWS = 500


def validate_csv(uploaded_file):
    """Return serialisable preview rows and errors without writing or calling X."""
    try:
        text = uploaded_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return [], ['Plik CSV musi być zapisany w kodowaniu UTF-8.']

    reader = csv.DictReader(io.StringIO(text))
    columns = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - columns
    unknown = columns - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
    if missing:
        return [], [f'Brak wymaganych kolumn: {", ".join(sorted(missing))}.']
    if unknown:
        return [], [f'Nieznane kolumny: {", ".join(sorted(unknown))}.']

    raw_rows = list(reader)
    if not raw_rows:
        return [], ['Plik nie zawiera żadnego konta.']
    if len(raw_rows) > MAX_ROWS:
        return [], [f'Jednorazowo można zaimportować najwyżej {MAX_ROWS} kont.']

    seen_ids, seen_handles, preview = set(), set(), []
    existing_ids = set(PoliticalAccount.objects.filter(
        user_id__in=[(row.get('user_id') or '').strip() for row in raw_rows]
    ).values_list('user_id', flat=True))
    input_handles = [(row.get('handle') or '').strip().lower() for row in raw_rows]
    existing_handles = set(PoliticalAccount.objects.annotate(handle_lower=Lower('handle')).filter(
        handle_lower__in=input_handles
    ).values_list('handle_lower', flat=True))

    for line, raw in enumerate(raw_rows, start=2):
        values = {key: (raw.get(key) or '').strip() for key in REQUIRED_COLUMNS | OPTIONAL_COLUMNS}
        values['poll_interval_minutes'] = values['poll_interval_minutes'] or '15'
        errors = []
        try:
            values['poll_interval_minutes'] = int(values['poll_interval_minutes'])
        except ValueError:
            errors.append('Interwał musi być liczbą całkowitą.')

        user_id, handle = values['user_id'], values['handle']
        if user_id in seen_ids:
            errors.append('Powtórzony user_id w pliku.')
        if handle.lower() in seen_handles:
            errors.append('Powtórzony handle w pliku.')
        seen_ids.add(user_id)
        seen_handles.add(handle.lower())
        if user_id in existing_ids:
            errors.append('Takie user_id jest już w bazie.')
        if handle.lower() in existing_handles:
            errors.append('Taki handle jest już w bazie.')

        if not errors:
            account = PoliticalAccount(
                user_id=user_id, handle=handle, display_name=values['display_name'],
                camp=values['camp'], confirmation_url=values['confirmation_url'],
                confirmation_note=values['confirmation_note'],
                poll_interval_minutes=values['poll_interval_minutes'], enabled=False,
            )
            try:
                account.full_clean()
            except ValidationError as exc:
                errors.extend(exc.messages)

        preview.append({'line': line, **values, 'errors': errors})
    return preview, []


def create_from_preview(rows):
    """Create only rows that passed preview validation, still disabled/unconfirmed."""
    created = []
    for row in rows:
        if row['errors']:
            raise ValidationError('Podgląd zawiera błędy; popraw plik przed importem.')
        account = PoliticalAccount(
            user_id=row['user_id'], handle=row['handle'], display_name=row['display_name'],
            camp=row['camp'], confirmation_url=row['confirmation_url'],
            confirmation_note=row['confirmation_note'],
            poll_interval_minutes=row['poll_interval_minutes'], enabled=False,
        )
        account.full_clean()
        account.save()
        created.append(account)
    return created
