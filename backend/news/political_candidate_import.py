"""Preview-only CSV import for editorial political account candidates."""
import csv
import io

from django.core.exceptions import ValidationError
from django.db.models.functions import Lower

from news.political_models import PoliticalAccountCandidate

REQUIRED_COLUMNS = {'handle', 'display_name', 'classification', 'confirmation_url', 'confirmation_note'}
OPTIONAL_COLUMNS = {'proposed_camp'}
MAX_ROWS = 500


def validate_candidate_csv(uploaded_file):
    try:
        text = uploaded_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return [], ['Plik CSV musi być zapisany w kodowaniu UTF-8.']
    reader = csv.DictReader(io.StringIO(text))
    columns = set(reader.fieldnames or [])
    if REQUIRED_COLUMNS - columns:
        return [], [f'Brak wymaganych kolumn: {", ".join(sorted(REQUIRED_COLUMNS - columns))}.']
    if columns - REQUIRED_COLUMNS - OPTIONAL_COLUMNS:
        return [], [f'Nieznane kolumny: {", ".join(sorted(columns - REQUIRED_COLUMNS - OPTIONAL_COLUMNS))}.']
    raw_rows = list(reader)
    if not raw_rows or len(raw_rows) > MAX_ROWS:
        return [], ['Plik musi zawierać od 1 do 500 wierszy.']
    handles = [(row.get('handle') or '').strip().lower() for row in raw_rows]
    existing = set(PoliticalAccountCandidate.objects.annotate(handle_lower=Lower('handle')).filter(
        handle_lower__in=handles).values_list('handle_lower', flat=True))
    seen, preview = set(), []
    for line, raw in enumerate(raw_rows, 2):
        values = {key: (raw.get(key) or '').strip() for key in REQUIRED_COLUMNS | OPTIONAL_COLUMNS}
        errors = []
        if values['handle'].lower() in seen or values['handle'].lower() in existing:
            errors.append('Taki handle jest już na liście kandydatów.')
        seen.add(values['handle'].lower())
        if not errors:
            item = PoliticalAccountCandidate(**values)
            try:
                item.full_clean()
            except ValidationError as exc:
                errors.extend(exc.messages)
        preview.append({'line': line, **values, 'errors': errors})
    return preview, []


def create_candidates_from_preview(rows):
    if any(row['errors'] for row in rows):
        raise ValidationError('Podgląd zawiera błędy; popraw plik przed importem.')
    created = []
    for row in rows:
        item = PoliticalAccountCandidate(**{key: row[key] for key in REQUIRED_COLUMNS | OPTIONAL_COLUMNS})
        item.full_clean(); item.save(); created.append(item)
    return created
