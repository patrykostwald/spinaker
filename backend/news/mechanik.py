"""Mechanik (właściciel 5.10: „napisz agenta, który będzie naprawiał połączenia”).

Co godzinę bierze modele Konsylium z twardym błędem (404, 400, nie znaleziono) albo zawieszone przez kontrolę zdrowia:
1. pyta dostawcę o aktualną listę modeli (darmowe zapytanie),
2. gdy model nadal jest na liście: jedno próbne pytanie; udane przywraca miejsce w składzie,
3. gdy modelu nie ma: szuka następcy pod nową nazwą (ta sama rodzina, najdłuższy wspólny początek nazwy), testuje go
   i zapisuje zamiennik; odtąd zapytania do starej nazwy idą do nowej (jawnie, w dzienniku Mechanika).
Nie naprawia 402 (brak środków: zgłasza Dyżurny) ani 429 (dzienny limit mija sam). Nie zmienia ról ani składu.
Przy okazji sprawdza dostawcę zadań pobocznych Inception (Mercury): czy model jest na liście, a gdy zniknął - zamiennik.
"""
import logging
import os
import re

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)
ALIASES = 'council-model-aliases'
LOG = 'mechanik-log'
HARD = re.compile(r'(^|\D)(404|400)(\D|$)|not.?found|does not exist|decommission', re.I)
# Znane zmiany nazw u dostawców (najpierw sprawdzane); reszta z listy modeli dostawcy.
KNOWN = {('groq', 'groq/compound'): ['groq/compound-mini', 'compound-beta', 'compound-beta-mini'],
         ('groq', 'compound-beta'): ['groq/compound', 'groq/compound-mini']}


def _state(name):
    from news.models import ImportState
    state, _ = ImportState.objects.get_or_create(name=name)
    return state


def aliases():
    return dict(_state(ALIASES).cursor or {})


def alias(service, model):
    """Model do wywołania: zamiennik zapisany przez Mechanika albo ten sam."""
    try:
        return aliases().get(f'{service}|{model}', model)
    except Exception:  # noqa: BLE001 - baza niedostępna nie może zatrzymać diagnozy
        return model


def _note(entry):
    state = _state(LOG)
    rows = list((state.cursor or {}).get('rows', []))
    rows.insert(0, {'at': timezone.now().isoformat(timespec='minutes'), **entry})
    state.cursor = {'rows': rows[:60]}
    state.save(update_fields=['cursor'])
    logger.info('mechanik: %s', entry)


def provider_models(service):
    """Lista nazw modeli u dostawcy albo None (dostawca bez listy, brak klucza, błąd sieci)."""
    from news import council_registry as registry
    key = registry.credentials(service)
    if not key:
        return None
    try:
        if service == 'gemini':
            response = requests.get('https://generativelanguage.googleapis.com/v1beta/models', params={'key': key, 'pageSize': 200}, timeout=20)
            response.raise_for_status()
            return {m['name'].split('/', 1)[-1] for m in response.json().get('models', [])}
        if service not in registry.URLS and service != 'nim':
            return None
        url = registry.endpoint(service).replace('/chat/completions', '/models')
        response = requests.get(url, headers={'Authorization': f'Bearer {key}'}, timeout=20)
        response.raise_for_status()
        return {m['id'] for m in response.json().get('data', []) if isinstance(m, dict) and m.get('id')}
    except (requests.RequestException, ValueError, KeyError):
        return None


def successor(service, model, listed):
    """Następca w tej samej rodzinie: najpierw znane zmiany nazw, potem najdłuższy wspólny początek (min. 60% nazwy)."""
    for name in KNOWN.get((service, model), []):
        if name in listed:
            return name
    base = re.sub(r'([-_:.](\d{4}-?\d{2}(-?\d{2})?|v?\d+(\.\d+)*|latest|preview|beta|free))+$', '', model.lower())
    best, score = None, 0
    for name in listed:
        lower = name.lower()
        if lower == model.lower() or (service == 'openrouter' and not lower.endswith(':free')):
            continue
        common = len(os.path.commonprefix([base, lower]))
        if common >= max(6, int(len(base) * 0.6)) and common > score:
            best, score = name, common
    return best


def probe(service, model):
    """Jedno małe pytanie; True, gdy model odpowiada poprawnym JSON."""
    from news.clinic_ai import ClinicAIError
    from news.clinic_council import _ask
    try:
        answer = _ask((service, model), 'Odpowiedz wyłącznie JSON.', 'Napisz {"ok": true}.',
                      {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']}, max_tokens=50)
        return bool(answer.get('ok')), ''
    except ClinicAIError as error:
        return False, str(getattr(error, 'code', error))[:120]


def step():
    from news import council_registry as registry
    from news.clinic_models import CouncilSeat
    seats = [s for s in CouncilSeat.objects.all() if s.status == 'suspended' or HARD.search(s.last_error or '')]
    done = []
    lists = {}
    for seat in seats:
        member = (seat.provider, seat.model)
        if '402' in (seat.last_error or '') or not registry.configured(member):
            continue
        if seat.provider not in lists:
            lists[seat.provider] = provider_models(seat.provider)
        listed = lists[seat.provider]
        current = alias(*member)
        if listed is not None and current not in listed:
            new = successor(seat.provider, seat.model, listed)
            if not new:
                _note({'model': seat.model, 'wynik': 'brak u dostawcy, nie znaleziono następcy'})
                done.append((seat.model, 'brak następcy'))
                continue
            ok, error = probe(seat.provider, new)
            if ok:
                state = _state(ALIASES)
                state.cursor = {**(state.cursor or {}), f'{seat.provider}|{seat.model}': new}
                state.save(update_fields=['cursor'])
                CouncilSeat.objects.filter(pk=seat.pk).update(status='active', first_fail_at=None, last_error='', last_ok_at=timezone.now())
                _note({'model': seat.model, 'wynik': f'zamiennik: {new}'})
                done.append((seat.model, f'zamiennik {new}'))
            else:
                _note({'model': seat.model, 'wynik': f'następca {new} nie odpowiada ({error})'})
                done.append((seat.model, 'następca nie odpowiada'))
            continue
        ok, error = probe(seat.provider, current)
        if ok:
            CouncilSeat.objects.filter(pk=seat.pk).update(status='active', first_fail_at=None, last_error='', last_ok_at=timezone.now())
            _note({'model': seat.model, 'wynik': 'działa ponownie, przywrócony'})
            done.append((seat.model, 'przywrócony'))
        else:
            _note({'model': seat.model, 'wynik': f'nadal nie działa ({error})'})
            done.append((seat.model, error or 'błąd'))
    if any(result == 'przywrócony' or result.startswith('zamiennik') for _, result in done):
        from news.council_quorum import release
        release('mechanik')  # wpisy czekające na kworum Konsylium próbują od razu, nie dopiero po resecie limitów
    result = {'status': 'ok', 'checked': len(seats), 'results': done}
    # Inception (Mercury, zadania poboczne): darmowa lista modeli, bez tokenów; zniknięty model -> zamiennik z rodziny.
    from news import inception
    check = inception.health()
    if check is not None:
        result['inception'] = check
        if check.get('replaced'):
            _note({'model': inception.base_model(), 'wynik': f"Inception - zamiennik: {check['model']}"})
    return result
