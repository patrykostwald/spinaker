"""Inception Labs (Mercury 2.5, model dyfuzyjny) - darmowy dostawca do zadań pobocznych (7.10.2026).

Po co: przesiewanie wpisów X (strażnik), ocena odpowiedzi w „Jak spin zadziałał” i pętle agentów zjadały dzienne limity
członków Konsylium (6.10: 1233 wpisy na gpt-oss-20b odebrały głosy diagnozom). Mercury bierze te zadania pierwszy, gdy jest
klucz; bez klucza, po wyczerpaniu puli albo przy błędzie - dotychczasowy łańcuch bez zmian.

Zasady:
1. API zgodne z OpenAI: https://api.inceptionlabs.ai/v1/chat/completions, klucz INCEPTION_API_KEY (Bearer),
   model INCEPTION_MODEL (domyślnie mercury-2.5; zamiennik nazwy zapisuje Mechanik).
2. Tylko darmowa pula: liczymy tokeny z odpowiedzi (usage.total_tokens) w bazie (ImportState „inception-tokens”).
   Stop przy INCEPTION_STOP_SHARE (90%) z INCEPTION_FREE_TOKENS (100 mln) - nigdy płatnych tokenów,
   chyba że właściciel ustawi INCEPTION_ALLOW_PAID=true. Do tego pułap dzienny i miesięczny (rozłożenie puli w czasie).
   Odpowiedź 402 / account_error zatrzymuje dostawcę do zmiany klucza.
3. Do Konsylium nie wchodzi z konfiguracji: jest kandydatem Rekrutera (egzamin, głosowanie, Karta - te same zasady
   co dla każdego modelu). Diagnozy tylko po przyjęciu przez Rekrutera.
4. Regulamin Inception (stan 7.10.2026): dane z zapytań mogą trenować modele, o ile w ustawieniach konta platformy
   nie wyłączono „Improve the model for everyone”. Zadania z danymi osób prywatnych (odpowiedzi z X) idą do Inception
   tylko przy INCEPTION_NO_TRAINING=true (właściciel potwierdza, że wyłączył tę opcję).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import timedelta

import requests
from django.db import transaction
from django.utils import timezone

from news.clinic_ai import ClinicAIError

logger = logging.getLogger(__name__)

SERVICE = 'inception'
COMPANY = 'Inception Labs'
URL = 'https://api.inceptionlabs.ai/v1/chat/completions'
DEFAULT_MODEL = 'mercury-2.5'
STATE = 'inception-tokens'
RETRY_STATUS = {429, 500, 502, 503, 504}
STOP_STATUS = {401, 402, 403}
STOP_TEXT = re.compile(r'account_error|insufficient|quota|billing|invalid_api_key|payment', re.I)
EFFORTS = ('instant', 'low', 'medium', 'high')


class InceptionError(ClinicAIError):
    """Odmowa budżetu albo błąd dostawcy; ten sam typ co błędy Konsylium (kody inception_*)."""


def _int(name: str, default: int, low: int = 0) -> int:
    try:
        return max(low, int(str(os.environ.get(name, '') or default).replace('_', '')))
    except ValueError:
        return default


def key() -> str:
    return os.environ.get('INCEPTION_API_KEY', '').strip()


def configured() -> bool:
    return bool(key())


def url() -> str:
    custom = os.environ.get('INCEPTION_API_URL', '').strip()
    return custom if custom.startswith('https://') else URL


def base_model() -> str:
    return os.environ.get('INCEPTION_MODEL', '').strip() or DEFAULT_MODEL


def model() -> str:
    """Model do wywołania: zamiennik zapisany przez Mechanika (model przemianowany u dostawcy) albo ustawiony."""
    name = base_model()
    try:
        return (_state().cursor or {}).get('alias', {}).get(name, name)
    except Exception:  # noqa: BLE001 - baza niedostępna: nazwa z ustawień
        return name


def member() -> tuple[str, str]:
    return (SERVICE, base_model())


def allow_paid() -> bool:
    return os.environ.get('INCEPTION_ALLOW_PAID', '').strip().lower() in ('1', 'true', 'yes')


def no_training() -> bool:
    """Właściciel potwierdził wyłączenie trenowania na danych z API (ustawienie konta „Improve the model for everyone”)."""
    return os.environ.get('INCEPTION_NO_TRAINING', '').strip().lower() in ('1', 'true', 'yes')


def free_tokens() -> int:
    return _int('INCEPTION_FREE_TOKENS', 100_000_000, 1)


def stop_share() -> float:
    try:
        return min(1.0, max(0.1, float(os.environ.get('INCEPTION_STOP_SHARE', '') or 0.9)))
    except ValueError:
        return 0.9


def stop_at() -> int:
    return int(free_tokens() * stop_share())


def daily_tokens() -> int:
    return _int('INCEPTION_DAILY_TOKENS', 2_000_000, 1)


def monthly_tokens() -> int:
    return _int('INCEPTION_MONTHLY_TOKENS', 25_000_000, 1)


def _fingerprint() -> str:
    return hashlib.sha256(key().encode()).hexdigest()[:12] if key() else ''


def _state(lock: bool = False):
    from news.models import ImportState
    manager = ImportState.objects.select_for_update() if lock else ImportState.objects
    state = manager.filter(name=STATE).first()
    if state is None:
        state, _ = ImportState.objects.get_or_create(name=STATE)
    return state


def _periods(now=None):
    local = timezone.localtime(now or timezone.now())
    return local.date().isoformat(), local.strftime('%Y-%m')


def usage(now=None) -> dict:
    """Zużycie tokenów: dziś, w miesiącu, łącznie; ile zostało z darmowej puli do progu stopu."""
    day, month = _periods(now)
    try:
        data = dict(_state().cursor or {})
    except Exception:  # noqa: BLE001
        data = {}
    total = int(data.get('total', 0))
    halted = data.get('halted') if data.get('halted_key') == _fingerprint() else None
    return {'today': int((data.get('days') or {}).get(day, 0)), 'month': int((data.get('months') or {}).get(month, 0)),
            'total': total, 'free': free_tokens(), 'stop_at': stop_at(), 'free_left': max(0, stop_at() - total),
            'calls_today': int((data.get('calls') or {}).get(day, 0)), 'halted': halted,
            'last_error': data.get('last_error', ''), 'health': data.get('health') or {}}


def estimate(system: str, user: str, max_tokens: int) -> int:
    """Ostrożny szacunek przed zapytaniem: ~3 znaki na token w polszczyźnie plus pełny limit odpowiedzi."""
    return (len(system) + len(user)) // 3 + max_tokens


def refusal(tokens: int = 0, now=None) -> str:
    """Powód odmowy ('' = wolno). Darmowa pula do 90%, pułap dzienny i miesięczny, zatrzymanie po 402."""
    if not configured():
        return 'inception_key_missing'
    info = usage(now)
    if info['halted']:
        return 'inception_halted'
    if not allow_paid() and info['total'] + tokens > info['stop_at']:
        return 'inception_free_budget'
    if info['today'] + tokens > daily_tokens():
        return 'inception_daily_limit'
    if info['month'] + tokens > monthly_tokens():
        return 'inception_monthly_limit'
    return ''


def ready(tokens: int = 4000) -> bool:
    return not refusal(tokens)


def record(tokens: int, now=None) -> None:
    """Dopisuje zużyte tokeny (atomowo, w bazie - przetrwa restart i czyszczenie cache)."""
    day, month = _periods(now)
    with transaction.atomic():
        state = _state(lock=True)
        data = dict(state.cursor or {})
        days = {k: v for k, v in (data.get('days') or {}).items() if k >= (timezone.localtime(now or timezone.now()).date() - timedelta(days=40)).isoformat()}
        days[day] = int(days.get(day, 0)) + int(tokens)
        months = dict(data.get('months') or {})
        months[month] = int(months.get(month, 0)) + int(tokens)
        calls = {k: v for k, v in (data.get('calls') or {}).items() if k in days}
        calls[day] = int(calls.get(day, 0)) + 1
        data.update(total=int(data.get('total', 0)) + int(tokens), days=days, months=months, calls=calls)
        state.cursor = data
        state.save(update_fields=['cursor'])


def _note_error(code: str, halt: bool = False) -> None:
    try:
        with transaction.atomic():
            state = _state(lock=True)
            data = dict(state.cursor or {})
            data['last_error'] = code[:160]
            if halt:
                data.update(halted=code[:160], halted_key=_fingerprint(), halted_at=timezone.now().isoformat(timespec='minutes'))
            state.cursor = data
            state.save(update_fields=['cursor'])
    except Exception as error:  # noqa: BLE001 - zapis błędu nie może przerwać łańcucha zapasowego
        logger.debug('inception note skipped: %s', error)


def _json(text: str) -> dict:
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S)
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end == -1:
        raise InceptionError('inception_invalid_json')
    try:
        result = json.loads(text[start:end + 1], strict=False)
    except ValueError:
        try:
            result, _ = json.JSONDecoder(strict=False).raw_decode(text[start:])
        except ValueError:
            raise InceptionError('inception_invalid_json') from None
    if not isinstance(result, dict):
        raise InceptionError('inception_invalid_json')
    return result


def body(system: str, user: str, schema: dict | None, max_tokens: int, temperature: float = 0, model_name: str = '') -> dict:
    """Kształt zapytania (OpenAI-zgodny). Schemat w poleceniu i w response_format (bez strict - nasze schematy nie mają
    additionalProperties). max_completion_tokens zastępuje przestarzałe max_tokens (dokumentacja Inception)."""
    effort = os.environ.get('INCEPTION_REASONING_EFFORT', '').strip().lower() or 'low'
    payload = {'model': model_name or model(), 'temperature': temperature, 'max_completion_tokens': int(max_tokens),
               'reasoning_effort': effort if effort in EFFORTS else 'low',
               'messages': [{'role': 'system', 'content': system + (
                   '\nOdpowiedz wyłącznie obiektem JSON. Schemat:\n' + json.dumps(schema, ensure_ascii=False) if schema else '')},
                   {'role': 'user', 'content': user[:24000]}]}
    if schema:
        payload['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'result', 'strict': False, 'schema': schema}}
    return payload


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def chat(system: str, user: str, schema: dict | None = None, *, max_tokens: int = 1500, temperature: float = 0,
         model_name: str = '') -> tuple[dict, str]:
    """Jedno zapytanie JSON. Zwraca (dane, model). InceptionError z kodem przy odmowie budżetu albo błędzie."""
    need = estimate(system, user, max_tokens)
    reason = refusal(need)
    if reason:
        raise InceptionError(reason)
    payload = body(system, user, schema, max_tokens, temperature, model_name)
    retries = _int('INCEPTION_RETRIES', 2)
    headers = {'Authorization': f'Bearer {key()}', 'Content-Type': 'application/json'}
    for attempt in range(retries + 1):
        try:
            response = requests.post(url(), json=payload, headers=headers, timeout=(5, 60), allow_redirects=False)
        except (requests.Timeout, requests.ConnectionError) as error:
            if attempt < retries:
                _sleep(2 ** attempt)
                continue
            _note_error(f'inception: {type(error).__name__}')
            raise InceptionError(f'inception: {type(error).__name__}') from None
        except requests.RequestException as error:
            raise InceptionError(f'inception: {type(error).__name__}') from None
        status = response.status_code
        if status in RETRY_STATUS and attempt < retries:
            try:
                wait = float(response.headers.get('Retry-After') or 0)
            except (TypeError, ValueError):
                wait = 0
            _sleep(min(10.0, max(wait, 2 ** attempt)))
            continue
        if status >= 400:
            text = (response.text or '')[:300]
            code = f'inception: http_{status}'
            # 402, odrzucony klucz, wyczerpane konto: stop do zmiany klucza (nigdy nie przechodzimy w płatne)
            halt = status in STOP_STATUS or (status != 429 and bool(STOP_TEXT.search(text)))
            _note_error(code + (' model_not_found' if 'model_not_found' in text else ''), halt=halt)
            raise InceptionError(code + (' model_not_found' if 'model_not_found' in text else ''))
        try:
            data = response.json()
        except ValueError:
            record(need)
            raise InceptionError('inception_invalid_json') from None
        tokens = ((data.get('usage') or {}).get('total_tokens')) if isinstance(data, dict) else None
        record(int(tokens) if isinstance(tokens, (int, float)) and tokens > 0 else need)
        try:
            content = data['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise InceptionError('inception_empty') from None
        return _json(content), str(data.get('model') or payload['model'])
    raise InceptionError('inception_unavailable')  # pragma: no cover - pętla zawsze kończy się wyżej


# --- strażnik i zadania poboczne -------------------------------------------------------------------------------------

def side_json(system: str, user: str, schema: dict, *, max_tokens: int = 1500, private_data: bool = False):
    """Zadanie poboczne: (dane, model) albo None, gdy Inception nie może teraz wziąć zadania (wtedy łańcuch zapasowy).
    private_data=True (np. odpowiedzi osób prywatnych z X) wymaga INCEPTION_NO_TRAINING=true."""
    if private_data and not no_training():
        return None
    if not ready(estimate(system, user, max_tokens)):
        return None
    try:
        return chat(system, user, schema, max_tokens=max_tokens)
    except InceptionError as error:
        logger.info('inception side job: %s', error.code)
        return None


# --- Mechanik: kontrola zdrowia --------------------------------------------------------------------------------------

def health(now=None) -> dict | None:
    """Darmowa lista modeli dostawcy (bez tokenów): czy model jest na liście; gdy zniknął - następca z tej samej rodziny
    (jak u członków Konsylium) zapisany jako zamiennik. None, gdy brak klucza."""
    if not configured():
        return None
    from news.mechanik import successor
    now = now or timezone.now()
    try:
        response = requests.get(url().replace('/chat/completions', '/models'), timeout=20,
                                headers={'Authorization': f'Bearer {key()}'}, allow_redirects=False)
        if response.status_code >= 400:
            result = {'ok': False, 'error': f'http_{response.status_code}'}
            if response.status_code in STOP_STATUS:
                _note_error(f'inception: http_{response.status_code}', halt=True)
        else:
            listed = {m['id'] for m in response.json().get('data', []) if isinstance(m, dict) and m.get('id')}
            name = base_model()
            current = model()
            if current in listed:
                result = {'ok': True, 'model': current}
            else:
                new = successor(SERVICE, name, {m for m in listed if not re.search(r'edit|voice|coder', m, re.I)})
                result = {'ok': bool(new), 'model': new or name, 'replaced': bool(new),
                          **({} if new else {'error': 'model_missing'})}
                if new:
                    with transaction.atomic():
                        state = _state(lock=True)
                        data = dict(state.cursor or {})
                        data['alias'] = {**(data.get('alias') or {}), name: new}
                        state.cursor = data
                        state.save(update_fields=['cursor'])
    except (requests.RequestException, ValueError, KeyError, TypeError) as error:
        result = {'ok': False, 'error': type(error).__name__}
    result['at'] = now.isoformat(timespec='minutes')
    try:
        with transaction.atomic():
            state = _state(lock=True)
            state.cursor = {**(state.cursor or {}), 'health': result}
            state.save(update_fields=['cursor'])
    except Exception as error:  # noqa: BLE001
        logger.debug('inception health note skipped: %s', error)
    return result


# --- Raport pętli ----------------------------------------------------------------------------------------------------

def _mln(value: int) -> str:
    return f'{value / 1_000_000:.2f} mln'.replace('.', ',')


def report_line(now=None) -> str:
    if not configured():
        return 'Inception (Mercury): brak klucza INCEPTION_API_KEY - zadania poboczne na dotychczasowych modelach.'
    info = usage(now)
    state = 'ZATRZYMANY (' + info['halted'] + ')' if info['halted'] else (
        'stop - pula darmowa do 90% zużyta' if not allow_paid() and info['free_left'] <= 0 else 'działa')
    paid = ', płatne WŁĄCZONE (INCEPTION_ALLOW_PAID)' if allow_paid() else ''
    return (f"Inception (Mercury): dziś {_mln(info['today'])} tokenów ({info['calls_today']} zapytań, pułap {_mln(daily_tokens())}), "
            f"miesiąc {_mln(info['month'])}/{_mln(monthly_tokens())}, łącznie {_mln(info['total'])}; "
            f"zostało darmowych {_mln(info['free_left'])} do progu {round(stop_share() * 100)}%; {state}{paid}.")
