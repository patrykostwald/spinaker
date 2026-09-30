"""Treści dopuszczone do publikacji społecznościowej."""
from news.clinic_council import UNCHECKED, check_failed, is_tool_failure


def checked_claims(claims):
    if check_failed(claims or []):
        return []
    return [c for c in claims or []
            if c.get('assessment') in ('supported', 'contradicted', 'misleading')
            and c.get('explanation') != UNCHECKED and not is_tool_failure(c.get('explanation', ''))
            and any(s.get('url', '').startswith(('https://', 'http://')) for s in c.get('sources') or [])]


def prepare(diagnosis, save=True):
    from news.clinic import detail_data, ensure_x_thread
    # Starsze syntezy mogły zawierać niesprawdzone twierdzenia; odtwarzamy je z filtrowanego wejścia.
    claims = diagnosis.claims or []
    if len(checked_claims(claims)) != len(claims):
        diagnosis.x_thread = []
    if not diagnosis.x_thread:
        ensure_x_thread(diagnosis, save=save)
    data = detail_data(diagnosis)
    data['claims'] = checked_claims(data.get('claims'))
    return data
