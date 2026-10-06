"""Kworum i stała miara Konsylium (właściciel 6.10: „ta sama miara dla wszystkich”).

Spadek siły spinu 2-5.10 nie wynikał ze zmiany kryteriów, tylko ze składu: po przesianiu zaległych wpisów X części
stałych członków (Qwen, Bielik, gpt-oss) skończyły się dzienne limity, a modele różnią się typową surowością.
Wynik zależał więc od tego, KTO odpowiedział, a nie tylko od wpisu.

1. Kworum: diagnoza ukazuje się tylko, gdy odpowiedziało co najmniej COUNCIL_QUORUM_MIN członków (domyślnie 4),
   w tym co najmniej COUNCIL_CORE_MIN (domyślnie 3) ze stałego rdzenia COUNCIL_CORE (5 modeli, które wyznaczają miarę).
   Bez kworum wpis czeka w kolejce (status queued, powód w error) - ponowienie po resecie limitów (2:00) albo po
   naprawie modelu przez Mechanika. Ta sama reguła dla każdej partii.
2. Stała miara (COUNCIL_STABLE_MEASURE, domyślnie włączona): gdy brakuje kogoś z rdzenia, mediana siły jest
   przesuwana o różnicę typowej surowości obecnego składu i pełnego składu. Typowa surowość członka = mediana jego
   odchyleń od mediany Konsylium w ostatnich diagnozach. Przy pełnym rdzeniu przesunięcie wynosi dokładnie 0, więc
   wyniki pełnego składu są identyczne jak dotąd (porównywalność z historią).
"""
import os
import statistics
from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone

WARSAW = ZoneInfo('Europe/Warsaw')
CORE_DEFAULT = ('groq:openai/gpt-oss-20b,groq:qwen/qwen3.8-27b,nim:nvidia/nemotron-3-super-120b-a12b,'
                'gemini:gemini-3.8-flash,hf:speakleash/Bielik-11B-v3.0-Instruct:publicai')
ANSWERED = 'odpowiedział'
WAIT_KEY = 'council:quorum:wait'
BIAS_KEY = 'council:quorum:biases'
BIAS_WINDOW = 120   # ostatnie diagnozy, z których liczymy typową surowość członka
BIAS_MIN_SAMPLES = 8
BIAS_CLIP = 15
MAX_WAIT_HOURS = 72  # dłużej wpis nie czeka na kworum: zostaje oznaczony jako nieudany z powodem
RESET_HOUR = 2       # darmowe limity liczone według daty UTC - reset o 2:00 czasu polskiego
LIMIT_NOTES = ('_daily_limit', 'http_429', 'http_402', '_content_reserve')

# Tekst do /metodologia (jawność metody); ten sam w MethodologyDocument.tsx.
METHOD_TEXT = ('Kworum i stała miara: diagnoza ukazuje się tylko wtedy, gdy odpowiedziały co najmniej 4 modele, '
               'w tym co najmniej 3 z 5 stałych członków Konsylium. Gdy części modeli skończą się dzienne limity, wpis '
               'czeka na pełniejszy skład (zwykle do następnego dnia) zamiast ukazać się z oceną mniejszego grona. '
               'Modele różnią się surowością, więc dla każdego liczymy jego typowe odchylenie od mediany Konsylium '
               'w ostatnich diagnozach. Gdy brakuje stałego członka, medianę przesuwamy o różnicę między typową '
               'surowością obecnego i pełnego składu; przy pełnym składzie wynik się nie zmienia. Ta sama reguła '
               'obowiązuje dla każdej partii, a diagnozy wystawione w niepełnym składzie powtarzamy i pokazujemy '
               'poprzedni wynik.')


def _int(name, default):
    try:
        return max(1, int(os.environ.get(name, '') or default))
    except ValueError:
        return default


def min_members():
    from news.clinic_council import MIN_MEMBERS
    return max(MIN_MEMBERS, _int('COUNCIL_QUORUM_MIN', 4))


def core_min():
    return _int('COUNCIL_CORE_MIN', 3)


def stable_enabled():
    return os.environ.get('COUNCIL_STABLE_MEASURE', 'true').strip().lower() in ('1', 'true', 'yes')


def _parse(raw):
    return [tuple(part.strip() for part in item.split(':', 1)) for item in raw.split(',') if ':' in item]


def core_members():
    return _parse(os.environ.get('COUNCIL_CORE', '').strip() or CORE_DEFAULT)


def roster():
    """Skład z konfiguracji bez zawieszonych przez Rekrutera (ławka za chwilowe limity NIE zmniejsza rdzenia)."""
    from news.clinic_council import DEFAULT_COUNCIL
    from news.council_recruiter import adjust
    return adjust('CLINIC_COUNCIL', _parse(os.environ.get('CLINIC_COUNCIL', '').strip() or DEFAULT_COUNCIL))


def active_core(members=None):
    """Rdzeń, który realnie może głosować: w składzie i ze skonfigurowanym kluczem (zawieszony model nie blokuje miary)."""
    from news import council_registry as registry
    members = roster() if members is None else members
    return [m for m in core_members() if m in members and registry.configured(m)]


def is_core(member):
    return tuple(member) in core_members()


def answered(records):
    return [r for r in records or [] if r.get('status') == ANSWERED
            or (not r.get('status') and isinstance(r.get('intensity'), int))]


def seats():
    """Ilu członków może w ogóle głosować (skład ze skonfigurowanym kluczem)."""
    from news import council_registry as registry
    return sum(1 for m in roster() if registry.configured(m))


def check(records, core=None, size=None):
    """Czy zapisane odpowiedzi członków spełniają kworum. core - lista (usługa, model) rdzenia; domyślnie aktywny rdzeń.
    size - liczba miejsc w składzie: przy mniejszym składzie (np. własne CLINIC_COUNCIL) kworum to cały skład, ale
    nigdy mniej niż MIN_MEMBERS (3)."""
    from news.clinic_council import MIN_MEMBERS
    core = active_core() if core is None else core
    models = [r.get('model') for r in answered(records)]
    core_models = {m[1] for m in core}
    got_core = len(set(models) & core_models)
    need_core = min(core_min(), len(core_models))
    size = seats() if size is None else size
    need = max(MIN_MEMBERS, min(min_members(), size))
    met = len(models) >= need and got_core >= need_core
    reason = '' if met else f'council_quorum: {len(models)}/{need} członków, stałych {got_core}/{need_core}'
    return {'met': met, 'members': len(models), 'need_members': need, 'core': got_core, 'need_core': need_core,
            'missing_core': sorted(core_models - set(models)), 'reason': reason}


def possible():
    """Sprawdzenie przed zapytaniami (bez kosztów): czy wolnych członków starczy na kworum."""
    from news import council_registry as registry
    from news.council_health import bench_key
    members = roster()
    free = [m for m in members if registry.available(m) and not cache.get(bench_key(m))]
    return check([{'model': m[1], 'status': ANSWERED} for m in free], active_core(members))


def next_reset(now=None):
    now = (now or timezone.now()).astimezone(WARSAW)
    reset = datetime.combine(now.date(), time(RESET_HOUR), tzinfo=WARSAW)
    return reset if reset > now else reset + timedelta(days=1)


def waiting():
    state = cache.get(WAIT_KEY)
    return state if state and state.get('until', '') > timezone.now().isoformat() else None


def block(records, reason, now=None):
    """Po nieudanym kworum: przerwa do resetu limitów, gdy brakujący stali członkowie mają limit; inaczej godzina."""
    now = now or timezone.now()
    core = {m[1] for m in core_members()}
    missing = [r for r in records or [] if r.get('model') in core and r.get('status') != ANSWERED]
    limited = bool(missing) and all(any(n in str(r.get('note', '')) for n in LIMIT_NOTES) for r in missing)
    until = next_reset(now) if limited else now + timedelta(hours=1)
    state = {'until': until.astimezone(dt_timezone.utc).isoformat(), 'reason': reason[:200], 'at': now.isoformat(), 'limits': limited}
    cache.set(WAIT_KEY, state, max(60, int((until - now).total_seconds())))
    return state


def release(source=''):
    """Mechanik przywrócił model albo minął reset - kolejka spróbuje od razu."""
    cache.delete(WAIT_KEY)
    return source


# --- stała miara -------------------------------------------------------------------------------------------------

def deviations(rows):
    """{model: [odchylenia od mediany Konsylium]} z zapisanych składów (lista list rekordów członków)."""
    out = {}
    for records in rows:
        scores = [(r['model'], r['intensity']) for r in answered(records) if isinstance(r.get('intensity'), int)]
        if len(scores) < 3:
            continue
        median = statistics.median(score for _, score in scores)
        for model, score in scores:
            out.setdefault(model, []).append(score - median)
    return out


def biases_from(rows):
    return {model: max(-BIAS_CLIP, min(BIAS_CLIP, statistics.median(values)))
            for model, values in deviations(rows).items() if len(values) >= BIAS_MIN_SAMPLES}


def member_biases(refresh=False):
    """Typowa surowość członków z ostatnich BIAS_WINDOW opublikowanych diagnoz (cache 6 h)."""
    cached = None if refresh else cache.get(BIAS_KEY)
    if cached is not None:
        return cached
    from news.clinic_models import SpinDiagnosis
    rows = []
    try:
        usages = list(SpinDiagnosis.objects.filter(status='approved', provider='anthropic').exclude(diagnosed_at__isnull=True)
                      .order_by('-diagnosed_at').values_list('usage', flat=True)[:BIAS_WINDOW])
    except Exception:  # noqa: BLE001 - bez bazy: bez korekty (przesunięcie 0), diagnoza nie staje
        return {}
    for usage in usages:
        records = ((usage or {}).get('council') or {}).get('members')
        if records:
            rows.append(records)
    biases = biases_from(rows)
    cache.set(BIAS_KEY, biases, 6 * 3600)
    return biases


def offset(answered_models, core_models, biases):
    """Przesunięcie mediany: typowa surowość obecnych minus typowa surowość pełnego składu (obecni + brakujący rdzeń).
    0, gdy cały rdzeń odpowiedział."""
    present = list(dict.fromkeys(answered_models))
    reference = present + [m for m in core_models if m not in present]
    if not present or len(reference) == len(present):
        return 0.0

    def mean(models):
        return sum(biases.get(m, 0.0) for m in models) / len(models)
    return round(mean(present) - mean(reference), 2)


def stable_intensity(raw, answered_models, core_models, biases):
    shift = offset(answered_models, core_models, biases)
    return max(0, min(100, int(raw - shift))), shift  # jak dotąd: część całkowita mediany
