"""Głosy Rady (E0 „dane od dziś”): każdy głos członka Rady to jedna linia JSON w dopisywanym pliku poza bazą,
a decyzja człowieka (ukrycie, wycofanie) ma kod powodu z zamkniętej listy.

To przyszły zbiór do pomiaru jakości Rady i - dopiero po zgodzie Prawnika - do uczenia własnego modelu
(dlatego w każdym rekordzie training_allowed=false). Zapis NIGDY nie przerywa diagnozy: błąd jest logowany i połykany.

1. Pliki miesięczne w COUNCIL_VOTES_DIR (domyślnie /app/media/glosy w kontenerze, poza nim backend/var/glosy):
   glosy-RRRR-MM.jsonl (rekordy vote) i decyzje-RRRR-MM.jsonl (rekordy human_decision, dłuższa retencja).
2. Przed zapisem rekord przechodzi przez filtr: klucze API, nagłówki Authorization i tokeny Bearer znikają ze wszystkich pól,
   adresy e-mail i numery telefonów - z pól raw, techniques, claims, loaded_words, note i comment (zamiana na [usunięto]).
3. Katalog 700, plik 600 (tam, gdzie system to obsługuje); linia JSON z ensure_ascii (U+2028 psuje czytniki), blokada pliku flock.
4. Przebieg Rady (run) ustawia clinic.diagnose i council_rerun.rerun; bez przebiegu (np. egzamin Rekrutera, porównanie modeli)
   nic się nie zapisuje. Wyłącznik: COUNCIL_VOTES_ENABLED=false. Retencja: komenda glosy_porzadek (bez harmonogramu).
"""
import contextlib
import contextvars
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: bez blokady pliku
    fcntl = None

logger = logging.getLogger(__name__)

SCHEMA = 'glosy/1'
REDACTED = '[usunięto]'
VOTES_PREFIX, DECISIONS_PREFIX = 'glosy', 'decyzje'
DEFAULT_VOTES_DAYS, DEFAULT_DECISIONS_DAYS = 730, 1095

# Kod powodu decyzji człowieka - tylko z tej listy (wolny tekst idzie do pola comment).
REASON_LABELS = {
    'APPROVE': 'Zgoda z oceną Rady',
    'INSUFFICIENT_EVIDENCE': 'Za mało dowodów',
    'WRONG_FACT': 'Błędny fakt',
    'WRONG_RUBRIC': 'Błędna miara (niewłaściwe kryterium)',
    'PRIVACY': 'Prywatność',
    'LEGAL': 'Powód prawny',
    'OUT_OF_SCOPE': 'Poza zakresem',
    'OTHER': 'Inny powód',
}
REASON_CODES = tuple(REASON_LABELS)
REASON_CHOICES = [(code, label) for code, label in REASON_LABELS.items()]
ACTIONS = ('hide', 'withdraw')

_SECRETS = [re.compile(pattern) for pattern in (
    r'(?i)\b(?:proxy-)?authorization\b\s*[:=]\s*(?:(?:bearer|basic|token)\s+)?\S+',
    r'(?i)\b(?:x-api-key|x-goog-api-key|api[_-]?key|access[_-]?token)\b\s*[:=]\s*\S+',
    r'(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}',
    r'\bsk-[A-Za-z0-9_-]{8,}', r'\bgsk_[A-Za-z0-9]{8,}', r'\bnvapi-[A-Za-z0-9_-]{8,}', r'\bAIza[0-9A-Za-z_-]{10,}',
    r'\bhf_[A-Za-z0-9]{10,}', r'\bgh[pousr]_[A-Za-z0-9]{20,}', r'\bxox[abprs]-[A-Za-z0-9-]{10,}', r'\bAKIA[0-9A-Z]{16}\b',
    r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}',
)]
_PERSONAL = [re.compile(pattern) for pattern in (
    r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+',                                  # e-mail
    r'(?<![\w])(?:\+|00)\d{1,3}[\s.-]?(?:\d[\s.-]?){7,11}\d(?!\d)',   # +48 123 456 789
    r'(?<!\d)\d{3}[\s.-]\d{3}[\s.-]\d{3}(?!\d)',                       # 123-456-789
    r'(?<![\d.,])\d{9}(?![\d])',                                       # 123456789
    r'(?<!\d)\(?\d{2}\)?[\s-]\d{3}[\s-]\d{2}[\s-]\d{2}(?!\d)',          # 22 123 45 67
)]
PERSONAL_FIELDS = frozenset({'raw', 'techniques', 'claims', 'loaded_words', 'note', 'comment'})


def enabled() -> bool:
    return os.environ.get('COUNCIL_VOTES_ENABLED', 'true').strip().lower() not in ('0', 'false', 'no', 'off')


def log_dir() -> Path:
    """COUNCIL_VOTES_DIR; domyślnie jak SOCIAL_MEDIA_DIR: wolumen /app/media w kontenerze, poza nim backend/var (jak rcl_files)."""
    configured = os.environ.get('COUNCIL_VOTES_DIR', '').strip()
    if configured:
        return Path(configured)
    if Path('/app/media').is_dir():
        return Path('/app/media/glosy')
    from django.conf import settings
    return Path(settings.BASE_DIR) / 'var' / 'glosy'


def log_path(kind: str = 'vote', now: datetime | None = None) -> Path:
    """Plik miesięczny: glosy-RRRR-MM.jsonl dla głosów, decyzje-RRRR-MM.jsonl dla decyzji człowieka."""
    now = now or datetime.now(timezone.utc)
    prefix = DECISIONS_PREFIX if kind == 'human_decision' else VOTES_PREFIX
    return log_dir() / f'{prefix}-{now:%Y-%m}.jsonl'


# --- filtr przed zapisem ---------------------------------------------------------------------------------------------

def scrub_text(text: str, personal: bool = False) -> str:
    for pattern in _SECRETS:
        text = pattern.sub(REDACTED, text)
    if personal:
        for pattern in _PERSONAL:
            text = pattern.sub(REDACTED, text)
    return text


def scrub(value, personal: bool = False):
    """Rekurencyjnie: sekrety znikają zawsze, e-mail i telefon - w polach z PERSONAL_FIELDS."""
    if isinstance(value, str):
        return scrub_text(value, personal)
    if isinstance(value, dict):
        return {str(k): scrub(v, personal) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v, personal) for v in value]
    return value


def clean_record(record: dict) -> dict:
    return {str(key): scrub(value, key in PERSONAL_FIELDS) for key, value in record.items()}


# --- zapis -----------------------------------------------------------------------------------------------------------

def _append(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_BINARY', 0), 0o600)
    try:
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, ('\n'.join(lines) + '\n').encode('ascii'))
    finally:
        try:
            if fcntl:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def write(records) -> int:
    """Dopisuje rekordy (po jednej linii JSON do pliku miesięcznego swojego typu). Zwraca liczbę zapisanych linii.
    Każdy błąd jest logowany i połykany: zapis nie może przerwać diagnozy."""
    if not enabled():
        return 0
    now, by_file, written = datetime.now(timezone.utc), {}, 0
    for record in records or []:
        try:
            line = json.dumps(clean_record(record), ensure_ascii=True, sort_keys=True, default=str)
            by_file.setdefault(log_path(record.get('type', 'vote'), now), []).append(line)
        except Exception as error:  # noqa: BLE001 - zapis nie może przerwać diagnozy
            logger.warning('council votes: record skipped: %s', type(error).__name__)
    for path, lines in by_file.items():
        try:
            _append(path, lines)
            written += len(lines)
        except Exception as error:  # noqa: BLE001
            logger.warning('council votes: write failed: %s: %s', type(error).__name__, str(error)[:120])
    return written


# --- głosy -----------------------------------------------------------------------------------------------------------

def prompt_sha256() -> str:
    """Skrót polecenia członka dokładnie tak, jak idzie do modelu: system + karta + schemat (clinic_council._ask)."""
    from news import clinic_council, council_registry
    text = (clinic_council.MEMBER_SYSTEM + council_registry.CHARTER_SUMMARY + '\nSchemat JSON odpowiedzi:\n'
            + json.dumps(clinic_council.MEMBER_SCHEMA, ensure_ascii=False))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def vote_record(opinion: dict, *, run_id: str, post_id, diagnosis_id, outcome: str, prompt_hash: str = '',
                prompt_version: str = '') -> dict:
    """Rekord vote z opinii członka (wynik clinic_council._opinion razem z prywatnym kluczem _raw)."""
    captured = opinion.get('_raw') or {}
    valid = opinion.get('status') == 'odpowiedział'
    record = {
        'schema': SCHEMA, 'type': 'vote', 'at': _now(), 'run_id': run_id, 'post_id': post_id, 'diagnosis_id': diagnosis_id,
        'outcome': outcome, 'member': captured.get('member') or opinion.get('model') or '',
        'company': opinion.get('company'), 'role': opinion.get('role'), 'status': opinion.get('status'),
        'note': str(opinion['note'])[:120] if opinion.get('note') else None, 'seconds': opinion.get('seconds'),
        'model_served': captured.get('model_served'), 'tokens': captured.get('tokens'),
        'prompt_sha256': prompt_hash, 'prompt_version': prompt_version, 'raw': captured.get('raw'),
        'verdict': opinion.get('verdict') if valid else None, 'intensity': opinion.get('intensity') if valid else None,
        'techniques': captured.get('techniques_all') or [], 'claims': (opinion.get('claims') or []) if valid else [],
        'loaded_words': (opinion.get('loaded_words') or []) if valid else [],
        'valid': valid, 'training_allowed': False,
    }
    if opinion.get('twin_of'):
        record['twin_of'], record['served_by'] = opinion['twin_of'], opinion.get('served_by')
    return record


class Run:
    """Jeden przebieg Rady dla jednego wpisu: głosy zbiera _diagnose (stage), a zapisuje wyjście z bloku run()."""

    def __init__(self, post_id, diagnosis_id=None):
        self.run_id, self.post_id, self.diagnosis_id = str(uuid.uuid4()), post_id, diagnosis_id
        self.staged: list[dict] = []

    def flush(self, outcome: str) -> int:
        if not self.staged or not enabled():
            return 0
        try:
            from news import clinic_ai
            hashed = prompt_sha256()
            records = [vote_record(op, run_id=self.run_id, post_id=self.post_id, diagnosis_id=self.diagnosis_id,
                                   outcome=outcome, prompt_hash=hashed, prompt_version=clinic_ai.PROMPT_VERSION)
                       for op in self.staged]
            return write(records)
        except Exception as error:  # noqa: BLE001 - zapis nie może przerwać ani zasłonić wyniku diagnozy
            logger.warning('council votes: records not saved: %s', type(error).__name__)
            return 0


_RUN = contextvars.ContextVar('council_votes_run', default=None)


@contextlib.contextmanager
def run(post_id, diagnosis_id=None):
    """Przebieg Rady wpisu. Wynik: bez wyjątku - diagnosed; błąd council_quorum* - quorum_deferred; inny błąd - failed."""
    current = Run(post_id, diagnosis_id)
    token = _RUN.set(current)
    outcome = 'diagnosed'
    try:
        yield current
    except BaseException as error:
        outcome = 'quorum_deferred' if str(getattr(error, 'code', '')).startswith('council_quorum') else 'failed'
        raise
    finally:
        _RUN.reset(token)
        current.flush(outcome)


def stage(opinions: list[dict]) -> None:
    """Wywołuje clinic_council._diagnose po konsultacji: opinie wszystkich członków (także tych, którzy zawiedli)."""
    current = _RUN.get()
    if current is not None:
        current.staged = list(opinions)


# --- decyzje człowieka -----------------------------------------------------------------------------------------------

def check_reason_code(code) -> str:
    if code not in REASON_CODES:
        raise ValueError('Nieznany kod powodu.')
    return code


def decision_record(diagnosis, action: str, reason_code: str, comment: str, staff, at: str | None = None) -> dict:
    return {'schema': SCHEMA, 'type': 'human_decision', 'at': at or _now(), 'diagnosis_id': diagnosis.pk,
            'post_id': diagnosis.post_id, 'action': action, 'reason_code': reason_code, 'comment': comment,
            'staff_id': getattr(staff, 'pk', None), 'training_allowed': False}


# --- retencja --------------------------------------------------------------------------------------------------------

_FILE = re.compile(rf'^({VOTES_PREFIX}|{DECISIONS_PREFIX})-(\d{{4}})-(0[1-9]|1[0-2])\.jsonl$')


def _days(name: str, default: int, given: int | None) -> int:
    if given is not None:
        return given
    try:
        return max(0, int(os.environ.get(name, '').strip() or default))
    except ValueError:
        return default


def cleanup(keep_votes: int | None = None, keep_decisions: int | None = None, dry_run: bool = False,
            today: date | None = None) -> list[dict]:
    """Usuwa pliki miesięczne, których cały miesiąc jest starszy niż okres (głosy 730 dni, decyzje 1095 dni).
    Tylko pliki pasujące do wzorca glosy-RRRR-MM.jsonl i decyzje-RRRR-MM.jsonl. Zwraca listę {file, kind, removed}."""
    today = today or datetime.now(timezone.utc).date()
    limits = {VOTES_PREFIX: _days('COUNCIL_VOTES_RETENTION_DAYS', DEFAULT_VOTES_DAYS, keep_votes),
              DECISIONS_PREFIX: _days('COUNCIL_DECISIONS_RETENTION_DAYS', DEFAULT_DECISIONS_DAYS, keep_decisions)}
    directory, result = log_dir(), []
    if not directory.is_dir():
        return result
    for path in sorted(directory.iterdir()):
        match = _FILE.match(path.name)
        if not match or not path.is_file():
            continue
        prefix, year, month = match.group(1), int(match.group(2)), int(match.group(3))
        month_end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
        if (today - month_end).days <= limits[prefix]:
            continue
        removed = False
        if not dry_run:
            try:
                path.unlink()
                removed = True
            except OSError as error:
                logger.warning('council votes cleanup: %s: %s', path.name, type(error).__name__)
        result.append({'file': path.name, 'kind': 'vote' if prefix == VOTES_PREFIX else 'human_decision', 'removed': removed})
    return result
