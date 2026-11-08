"""Dodatkowe kontrole Dyżurnego (właściciel 5.10: „Dyżurny musi sprawdzać wszystko, jak najczęściej”).

Tylko baza i cache, bez wywołań modeli. Każda kontrola zwraca listę alarmów w formacie duty.alarm().
Nowe alarmy krytyczne idą mailem do właściciela od razu, a otwarte przypominają się co 6 godzin (notify_owner)."""
import os
from collections import Counter
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

WARSAW = ZoneInfo('Europe/Warsaw')
REMIND = timedelta(hours=6)


def _alarm(*args, **kwargs):
    from news.duty import alarm
    return alarm(*args, **kwargs)


def _on(name, default='false'):
    return os.environ.get(name, default).strip().lower() == 'true'


def check_x_collector(ctx):
    """Zbieracz wpisów z X: brak nowych wpisów albo wyczerpany limit zapytań lub budżetu."""
    from news.models import ImportState
    from news.political_models import PoliticalPost
    local = ctx.now.astimezone(WARSAW)
    if not 7 <= local.hour < 23:
        return []
    last = PoliticalPost.objects.order_by('-fetched_at').values_list('fetched_at', flat=True).first()
    if not last or ctx.now - last < timedelta(hours=2):
        return []
    state = ImportState.objects.filter(name='political-x-budget').first()
    budget = dict(state.cursor) if state else {}
    limits = {'daily_requests': int(os.environ.get('X_POLITICAL_DAILY_REQUEST_LIMIT', '100') or 100),
              'daily_posts': int(os.environ.get('X_POLITICAL_DAILY_POST_LIMIT', '100') or 100),
              'monthly_usd': os.environ.get('X_POLITICAL_MONTHLY_USD_LIMIT', '5')}
    hit = [k for k in ('daily_requests', 'daily_posts') if budget.get(k, 0) >= limits[k]]
    hours = round((ctx.now - last).total_seconds() / 3600, 1)
    return [_alarm('x:collector', 'critical', 'Zbieracz X: brak nowych wpisów' + (' (wyczerpany limit)' if hit else ''),
        {'hours': hours, 'limits_hit': hit, 'used': {k: budget.get(k) for k in ('daily_requests', 'daily_posts', 'spent_upper_usd')},
         'limits': limits}, last,
        'Podnieś X_POLITICAL_DAILY_REQUEST_LIMIT (zapytania nie kosztują, płacimy za wpisy) albo sprawdź klucz i saldo API X.'
        if hit else 'Sprawdź klucz i saldo API X oraz zadanie political_poll w panelu.')]


def check_model_providers(ctx):
    """Dostawcy modeli: brak środków (402), wycofane modele (404), seria limitów (429) w ostatnich 3 godzinach."""
    from news.clinic_models import CouncilCall
    rows = list(CouncilCall.objects.filter(created_at__gte=ctx.now - timedelta(hours=3)).values_list('provider', 'model', 'outcome'))
    alarms = []
    billing = Counter(p for p, _, o in rows if o == '402')
    for provider, n in billing.items():
        if n >= 3:
            alarms.append(_alarm(f'provider:402:{provider}', 'critical', f'Brak środków u dostawcy modeli: {provider}',
                {'provider': provider, 'errors_3h': n}, ctx.now - timedelta(hours=3),
                f'Doładuj konto {provider} albo wyłącz go w składzie Konsylium; Rekruter dobierze zastępstwo.'))
    gone = Counter((p, m) for p, m, o in rows if o == '404')
    for (provider, model), n in gone.items():
        if n >= 3:
            alarms.append(_alarm(f'provider:404:{provider}:{model}'[:180], 'warning', f'Model wycofany u dostawcy: {model}',
                {'provider': provider, 'model': model, 'errors_3h': n}, ctx.now - timedelta(hours=3),
                'Kontrola zdrowia Konsylium zawiesi model; sprawdź, czy skład ma zastępstwo.'))
    if len(rows) >= 20:
        ok = sum(o == 'ok' for _, _, o in rows) / len(rows)
        if ok < .3:
            alarms.append(_alarm('provider:capacity', 'critical', 'Konsylium: mniej niż 30% udanych odpowiedzi',
                {'calls_3h': len(rows), 'ok_share': round(ok, 2), 'errors': dict(Counter(o for _, _, o in rows if o != 'ok'))},
                ctx.now - timedelta(hours=3), 'Sprawdź limity i saldo darmowych dostawców; rozważ chwilowe podniesienie budżetu.'))
    return alarms


def check_diagnoses_today(ctx):
    """Dzień bez diagnoz mimo kolejki - także gdy powodem jest wyczerpany budżet (wtedy dawna kontrola milczała)."""
    from news.clinic_models import SpinDiagnosis
    local = ctx.now.astimezone(WARSAW)
    if local.hour < 13:
        return []
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    done = SpinDiagnosis.objects.filter(diagnosed_at__gte=start).count()
    queue = SpinDiagnosis.objects.filter(status__in=['queued', 'flagged'], hidden_at__isnull=True).count()
    if done or not queue:
        return []
    try:
        from news.clinic import budget_left
        left = round(float(budget_left()), 2)
    except Exception:  # noqa: BLE001 - brak danych o budżecie nie może wyłączyć alarmu
        left = None
    return [_alarm('diagnoses:none-today', 'critical', 'Diagnozy: dziś żadnej, mimo kolejki',
        {'queue': queue, 'budget_left_usd': left}, start,
        'Sprawdź budżet dzienny (CLINIC_DAILY_BUDGET_USD) i alarmy dostawców modeli.')]


def check_public_threads(ctx):
    """Spinki Dr. Spina są w bazie, ale główna jest pusta."""
    from news.features import threads_enabled
    if not threads_enabled():
        return []
    from news.account_models import PersonalContextThread
    from news.community import public_threads
    drafted = PersonalContextThread.objects.filter(owner__isnull=True).count()
    if not drafted or public_threads().exists():
        return []
    from news.thread_review_models import ThreadReview
    return [_alarm('threads:empty', 'critical', 'Spinki: główna jest pusta',
        {'dr_spin_threads': drafted, 'reviews': dict(Counter(ThreadReview.objects.values_list('status', flat=True)))},
        ctx.now, 'Uruchom drspin_review_threads --retry-rejected i sprawdź powody odrzuceń.')]


def check_daily_products(ctx):
    """Wywiad dnia i przekaz dnia za wczoraj gotowe o rozsądnej porze."""
    from news.clinic_models import ClinicInterview
    local = ctx.now.astimezone(WARSAW)
    yesterday = (local - timedelta(days=1)).date()
    alarms = []
    if local.hour >= 14 and _on('CLINIC_INTERVIEW_ENABLED') and not ClinicInterview.objects.filter(
            day=yesterday, status='approved', hidden_at__isnull=True).exists():
        alarms.append(_alarm(f'interview:{yesterday}', 'warning', 'Wywiad dnia: brak gotowej diagnozy za wczoraj',
            {'day': str(yesterday), 'statuses': list(ClinicInterview.objects.filter(day=yesterday).values_list('status', flat=True))},
            local.replace(hour=14, minute=0, second=0, microsecond=0), 'Sprawdź kolejkę wywiadów i portfel Gemini.'))
    from news.clinic_models import ClinicDailyMessage as Message
    if local.hour >= 10 and not Message.objects.filter(day=yesterday).exclude(status='failed').exists():
        alarms.append(_alarm(f'messages:{yesterday}', 'warning', 'Przekaz dnia: brak za wczoraj',
            {'day': str(yesterday)}, local.replace(hour=10, minute=0, second=0, microsecond=0), 'Sprawdź zadanie przekazu dnia.'))
    return alarms


from news import petle_bezpieczniki  # noqa: E402 - bezpieczniki pętli agentów (audyt pętli 5.10)
from news.kopia_zapasowa import check_backup  # noqa: E402 - kopia poza serwer (Z2): brak kopii > 26 h = krytyczny
from news.terminy_zewnetrzne import check_terminy  # noqa: E402 - domena, TLS, DNS, salda, token (Z3)
from news.poczta_kontrola import check_poczta  # noqa: E402 - IMAP skrzynki projektów > 2 h: najpierw ponowienie, potem alarm

CHECKS = (check_x_collector, check_model_providers, check_diagnoses_today, check_public_threads, check_daily_products,
          *petle_bezpieczniki.CHECKS, check_backup, check_terminy, check_poczta)


def notify_owner(now):
    """Jeden mail na bieg: nowe alarmy krytyczne od razu, otwarte co 6 godzin. Poczta nie zatrzymuje Dyżurnego."""
    from news.models import DutyAlarm
    due = [row for row in DutyAlarm.objects.filter(status='open', severity='critical')
           if row.last_dispatch_at is None or now - row.last_dispatch_at >= REMIND]
    if not due:
        return 0
    lines = []
    for row in due:
        lines.append(f'- {row.title} (od {row.since.astimezone(WARSAW):%d.%m %H:%M})\n  Co zrobić: {row.instruction}\n  Szczegóły: {row.details}')
    body = 'Dyżurny spin.clinic wykrył problem:\n\n' + '\n\n'.join(lines) + '\n\nPanel: https://spin.clinic/panel'
    try:
        from news.council_recruiter import _owner_email
        from news.social_publish import _mail
        sent = _mail(_owner_email(), f'spin.clinic · Dyżurny: {due[0].title}' + (f' (+{len(due) - 1})' if len(due) > 1 else ''), body)
    except Exception:  # noqa: BLE001
        sent = False
    if sent:
        DutyAlarm.objects.filter(pk__in=[row.pk for row in due]).update(last_dispatch_at=now)
    return len(due) if sent else 0
