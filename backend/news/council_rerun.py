"""Powtórka diagnoz wystawionych bez kworum Konsylium (komenda konsylium_powtorz, zadanie nocne 2:40).

Diagnoza opublikowana w niepełnym składzie (mniej niż COUNCIL_QUORUM_MIN odpowiedzi albo za mało stałego rdzenia)
jest diagnozowana ponownie, gdy kworum jest możliwe. Stary wynik nigdy nie znika: trafia do usage['history'];
gdy werdykt albo siła się zmienią, diagnoza pokazuje notkę „Zaktualizowano po pełnym składzie Konsylium”.
Idempotentnie: każda diagnoza najwyżej raz (usage['rerun']), powtórka bez kworum zostawia stary wynik.
Domyślnie tylko w cichych godzinach (2:00-7:00, po resecie limitów, przed dniem diagnoz) i w ramach budżetu.
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from news import council_quorum as quorum

logger = logging.getLogger(__name__)
WARSAW = ZoneInfo('Europe/Warsaw')
STATE_KEY = 'konsylium-powtorz'
QUIET_HOURS = (2, 7)
NOTE = 'Zaktualizowano po pełnym składzie Konsylium'
VERDICT_WORDS = {'spin': 'spin', 'partial': 'częściowy spin', 'no_spin': 'bez spinu', 'unclear': 'nie da się ocenić'}


def quiet(now=None):
    hour = (now or timezone.now()).astimezone(WARSAW).hour
    return QUIET_HOURS[0] <= hour < QUIET_HOURS[1]


def members_of(row):
    return (((row.usage or {}).get('council') or {}).get('members')) or []


def broken(row, core=None):
    """Opublikowana diagnoza Konsylium bez kworum (diagnozy Claude'a i Gemini bez Konsylium nie podlegają)."""
    records = members_of(row)
    return bool(records) and not quorum.check(records, core)['met']


def candidates(since, core=None):
    from news.clinic_models import SpinDiagnosis
    rows = (SpinDiagnosis.objects.filter(status='approved', provider='anthropic', diagnosed_at__gte=since,
                                         hidden_at__isnull=True, withdrawn_at__isnull=True)
            .select_related('post__account').order_by('diagnosed_at'))
    core = quorum.active_core() if core is None else core
    return [row for row in rows if not (row.usage or {}).get('rerun') and broken(row, core)]


def note(previous):
    return (f"{NOTE} (wcześniej: {VERDICT_WORDS.get(previous.get('verdict'), previous.get('verdict') or '')}, "
            f"siła {previous.get('intensity')}/100, {previous.get('members')} modeli).")


def _previous(row):
    records = members_of(row)
    return {'at': row.diagnosed_at.isoformat() if row.diagnosed_at else '', 'verdict': row.verdict, 'intensity': row.intensity,
            'headline': row.headline, 'summary': row.summary, 'analysis': row.analysis, 'limitations': row.limitations,
            'techniques': row.techniques, 'claims': row.claims, 'plain': row.plain, 'model_name': row.model_name,
            'prompt_version': row.prompt_version, 'members': len(quorum.answered(records)), 'council': records,
            'reason': quorum.check(records)['reason'] or 'niepełny skład Konsylium'}


def rerun(row, figure=None, now=None):
    """Jedna powtórka. Zwraca 'updated', 'same', 'waiting' (bez kworum - stary wynik zostaje) albo 'failed'."""
    from news import clinic, clinic_ai
    now = now or timezone.now()
    try:
        result = dict(clinic_ai.diagnose(clinic._post_context(row.post, figure)))
    except clinic_ai.ClinicAIError as error:
        code = str(error.code)[:200]
        attempts = {**((row.usage or {}).get('rerun_attempts') or {})}
        attempts.update(count=int(attempts.get('count', 0)) + 1, last_at=now.isoformat(), last_error=code)
        row.usage = {**(row.usage or {}), 'rerun_attempts': attempts}
        type(row).objects.filter(pk=row.pk).update(usage=row.usage)
        if code.startswith('council_quorum'):
            quorum.block((getattr(error, 'council', None) or {}).get('members') or [], code, now)
            return 'waiting'
        logger.warning('council rerun %s failed: %s', row.pk, code)
        return 'failed'
    previous = _previous(row)
    if 'lab' not in result:
        from news.clinic_lab import run_lab
        result['lab'] = run_lab(row.post.text, result.get('claims', []), result.get('loaded_words'))
    usage = result.pop('usage', {}) or {}
    usage['loaded_words'] = result.pop('loaded_words', [])
    result.setdefault('plain', {})
    changed = result.get('verdict') != row.verdict or result.get('intensity') != row.intensity
    for field, value in result.items():
        setattr(row, field, value)
    if changed:
        row.limitations = (note(previous) + '\n' + str(row.limitations or '')).strip()[:1500]
    old_usage = row.usage or {}
    keep = {key: old_usage[key] for key in ('videos', 'scan_synthesis') if key in old_usage}
    row.usage = {**keep, **usage, 'history': [*(old_usage.get('history') or []), previous],
                 'rerun': {'at': now.isoformat(), 'reason': previous['reason'], 'changed': changed,
                           'previous': {'verdict': previous['verdict'], 'intensity': previous['intensity']}}}
    row.model_name = (usage.get('model') or row.model_name)[:64]
    row.prompt_version = clinic_ai.PROMPT_VERSION
    row.error = ''
    with transaction.atomic():
        row.save()  # status, data diagnozy i zatwierdzenie bez zmian: to ta sama diagnoza, nowy skład
    if not row.x_posted_at:
        clinic.ensure_x_thread(row)
    return 'updated' if changed else 'same'


def _record(result, now):
    from news.models import RepairerState
    try:
        state, _ = RepairerState.objects.get_or_create(key=STATE_KEY)
        runs = [{'at': now.isoformat(), **{k: result.get(k, 0) for k in ('done', 'updated', 'same', 'waiting', 'failed')}},
                *(state.data or {}).get('runs', [])][:30]
        state.data = {'runs': runs}
        state.save(update_fields=['data'])
    except Exception:  # noqa: BLE001 - telemetria nie może zatrzymać powtórek
        pass


def done_since(since):
    """Powtórki wykonane od chwili since (Raport pętli) i czas ostatniej."""
    from news.models import RepairerState
    runs = (RepairerState.objects.filter(key=STATE_KEY).values_list('data', flat=True).first() or {}).get('runs', [])
    stamps = [(datetime.fromisoformat(r['at']), r.get('done', 0)) for r in runs if r.get('at')]
    last = max((at for at, _ in stamps), default=None)  # ostatnia kontrola (pętla żyje także bez powtórek)
    return sum(done for at, done in stamps if at >= since), last


def run(since, *, limit=8, dry_run=False, anytime=False, now=None):
    from news import clinic, clinic_ai
    now = now or timezone.now()
    rows = candidates(since)
    result = {'status': 'ok', 'candidates': len(rows), 'done': 0, 'updated': 0, 'same': 0, 'waiting': 0, 'failed': 0,
              'rows': [{'id': r.pk, 'verdict': r.verdict, 'intensity': r.intensity, 'members': len(quorum.answered(members_of(r))),
                        'reason': quorum.check(members_of(r))['reason']} for r in rows[:limit]]}
    if dry_run:
        result['status'] = 'dry_run'
        return result
    if not rows:
        result['status'] = 'idle'
        _record(result, now)
        return result
    if not anytime and not quiet(now):
        result['status'] = 'deferred'
        result['note'] = 'poza cichymi godzinami (2:00-7:00) - zrobi to zadanie nocne o 2:40'
        return result
    if not clinic_ai.enabled():
        result['status'] = 'disabled'
        return result
    wait = quorum.waiting()
    state = None if wait else quorum.possible()
    if wait or not state['met']:
        result.update(status='quorum', reason=(wait or {}).get('reason') or state['reason'])
        _record(result, now)
        return result
    figures = clinic.figures_by_account({row.post.account_id for row in rows[:limit]})
    for row in rows[:limit]:
        if clinic.budget_left() < clinic.diagnosis_reserve():
            result['status'] = 'budget'
            break
        outcome = rerun(row, figures.get(row.post.account_id), now)
        result[outcome] += 1
        if outcome in ('updated', 'same'):
            result['done'] += 1
        if outcome == 'waiting':
            break  # bez kworum kolejne powtórki też by czekały
    result['produced'] = result['done']
    _record(result, now)
    return result


def default_since(now=None):
    return (now or timezone.now()) - timedelta(days=7)
