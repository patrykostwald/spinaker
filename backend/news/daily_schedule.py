"""Harmonogram, terminy i odczyt wyników. Bez wywołań sieciowych."""
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo('Europe/Warsaw')

# Ten sam plan zasila beat, panel i dokumentację terminów.
BEAT_PLAN = {
    'institutional-reports-night': ('institutional_reports_task', {'hour': '2-5', 'minute': '*/5'}),
    'signal-threads-daily': ('signal_threads_task', {'hour': 22, 'minute': 20}),
    'thread-reviews-20m': ('thread_reviews_task', {'minute': '*/20'}),
    'ekspert-ai-daily': ('ekspert_ai_task', {'hour': 3, 'minute': 40}),
    'mechanik-1h': ('mechanik_task', {'minute': 23}),
    'recenzent-2h': ('recenzent_task', {'minute': 41, 'hour': '*/2'}),  # właściciel 5.10: recenzuje wszystko, co trafia na stronę
    'projektant-daily': ('projektant_task', {'hour': 4, 'minute': 20}),  # tydzień: stan wiedzy UX/UI i przegląd wszystkich stron  # właściciel 5.10: agent naprawiający połączenia z modelami
    'narrative-thread-daily': ('narrative_thread_task', {'hour': 21, 'minute': 45}),
    'narrative-thread-retry': ('narrative_thread_task', {'hour': 22, 'minute': '0,15'}),
    'duty-15m': ('duty_task', {'minute': '*/5'}),  # właściciel 5.10: jak najczęściej
    'political-x-minute': ('political_poll_task', {'minute': '*'}),
    'clinic-screen-5m': ('clinic_screen_task', {'minute': '*/5'}),
    'clinic-diagnoses-day': ('clinic_diagnose_task', {'minute': '*/10', 'hour': '7-22'}),
    'clinic-interview-10m': ('clinic_interview_task', {'minute': '*/10'}),
    'clinic-interview-pick': ('clinic_interview_pick_task', {'hour': '7,10,13,16,19', 'minute': 5}),
    'clinic-interview-candidates': ('clinic_interview_candidates_task', {'hour': '0,6,12,18,23', 'minute': 0}),
    'clinic-daily-messages-day': ('clinic_daily_messages_task', {'hour': '9,12,15,18', 'minute': 0}),
    'clinic-daily-messages-evening': ('clinic_daily_messages_task', {'hour': 21, 'minute': 30}),
    'x-publish-day': ('x_publish_task', {'minute': '15,45', 'hour': '8-21'}),
    'social-publish-day': ('social_publish_task', {'minute': '25,55', 'hour': '8-21'}),
    'dr-spin-thread-daily': ('dr_spin_thread_task', {'hour': 19, 'minute': 30}),
    'weekly-report-sunday': ('weekly_report_task', {'day_of_week': 'sun', 'hour': 20, 'minute': 0}),
    'schedule-health-6h': ('schedule_health_task', {'hour': '*/6', 'minute': 5}),
}


def beat_entries():
    from celery.schedules import crontab
    import os
    entries = {key: {'task': 'news.tasks.' + task, 'schedule': crontab(**plan)}
            for key, (task, plan) in BEAT_PLAN.items()}
    if os.environ.get('X_POLL_MODE', 'timeline') == 'batched':
        try:
            seconds = max(30, int(os.environ.get('X_WATCH_SECONDS', '60')))
        except ValueError:
            seconds = 60
        entries['political-x-minute']['schedule'] = timedelta(seconds=seconds)
    return entries


def bounds(now):
    start = now.astimezone(WARSAW).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def at(now, hour, minute=0):
    return bounds(now)[0].replace(hour=hour, minute=minute)


def result(status, detail, completed=None):
    return status, {'detail': detail, 'completed_at': completed.isoformat() if completed else None}


def missing(now, deadline, detail, running=False):
    return result('late' if now >= deadline else 'running' if running else 'waiting', detail)


def pulse(name):
    from news.models import RepairerState
    row = RepairerState.objects.filter(key='pulse:' + name).first()
    return row.data if row else {}


def check_poll(now):
    from news.repairer import flag, stamp
    if not flag('X_POLITICAL_POLLING_ENABLED', False):
        return result('na', 'Zbieranie X jest wyłączone.')
    data = pulse('political-x-minute')
    last = stamp(data.get('last_success'))
    age = timedelta(minutes=10) if 7 <= now.astimezone(WARSAW).hour < 23 else timedelta(hours=2)
    if last and timedelta(0) <= now - last <= age:
        return result('done', 'Ostatni udany przebieg zbieracza, także w cichych godzinach.', last)
    return result('late', 'Brak aktualnego udanego pulsu zbieracza X.')


def check_screen(now):
    from django.db.models import Q
    from news.clinic import CAMPS
    from news.political_models import PoliticalPost
    rows = PoliticalPost.objects.filter(available=True, account__enabled=True, camp_at_collection__in=CAMPS,
                                       fetched_at__lte=now)
    if not rows.exists():
        return result('na', 'Brak wpisów do oceny.')
    count = rows.filter(fetched_at__lt=now - timedelta(minutes=30)).filter(
        Q(spin_diagnosis__isnull=True) | Q(spin_diagnosis__status='flagged', spin_diagnosis__screen_score__isnull=True,
                                          spin_diagnosis__diagnosed_at__isnull=True)).count()
    if count:
        return result('late', f'Wpisy bez oceny od ponad 30 min: {count}.')
    return result('done', 'Brak zaległych ocen.', now)


def check_diagnoses(now):
    from django.db.models import Q
    from news import clinic
    from news.clinic_models import SpinDiagnosis
    start, end = bounds(now)
    done = (SpinDiagnosis.objects.filter(diagnosed_at__gte=start, diagnosed_at__lte=now,
            status__in=['approved', 'pending_review', 'rejected']).exclude(verdict='')
            .order_by('diagnosed_at').first())
    if done:
        return result('done', 'Pierwsza diagnoza dnia gotowa.', done.diagnosed_at)
    eligible = Q(status__in=['queued', 'failed'])
    if clinic.auto_publish():
        eligible |= Q(status='flagged', screen_score__isnull=False)
    candidates = SpinDiagnosis.objects.filter(eligible, hidden_at__isnull=True,
        withdrawn_at__isnull=True, post__available=True, post__published_at__gte=now - timedelta(hours=24),
        post__published_at__lte=now)
    if not candidates.exists():
        return result('na', 'Brak świeżych kandydatów po strażniku.')
    if clinic.budget_left() < clinic.diagnosis_reserve():
        return result('budget', 'Budżet diagnoz nie wystarcza na kolejną analizę.')
    return missing(now, at(now, 10), 'Kandydaci czekają na pierwszą diagnozę.', True)


def check_interview(now):
    from news.clinic_models import ClinicInterview
    from news.repairer import flag
    if not flag('CLINIC_INTERVIEW_ENABLED', False):
        return result('na', 'Wywiady są wyłączone.')
    rows = ClinicInterview.objects.filter(day=bounds(now)[0].date() - timedelta(days=1), hidden_at__isnull=True)
    done = rows.filter(status__in=['approved', 'pending_review']).order_by('diagnosed_at').first()
    if done:
        return result('done', 'Opublikowany.' if done.status == 'approved' else 'Czeka na decyzję zespołu.',
                      done.diagnosed_at or done.created_at)
    chosen = rows.filter(status__in=['queued', 'flagged']).exists()
    return missing(now, at(now, 18) if chosen else at(now, 8),
                   'Wybrany, trwa opracowanie.' if chosen else 'Brak wybranego wywiadu z wczoraj.', chosen)


def check_message(camp, now):
    from news.clinic import message_posts, MIN_MESSAGE_ACCOUNTS
    from news.clinic_models import ClinicDailyMessage
    day = bounds(now)[0].date()
    done = ClinicDailyMessage.objects.filter(day=day, camp=camp, status__in=['approved', 'pending_review']).exclude(message='').first()
    if done:
        return result('done', 'Przekaz dnia zapisany.', done.created_at)
    posts = message_posts(day, camp)
    if len({p.account_id for p in posts}) < MIN_MESSAGE_ACCOUNTS:
        return result('na', 'Wpisy z mniej niż 3 kont tej strony.')
    detail = 'Brak przekazu mimo wpisów z co najmniej 3 kont.'
    if now >= at(now, 22, 15):
        detail = 'Kontrola końcowa 22:15: ' + detail
    return missing(now, at(now, 12, 30), detail)


def check_publication(now):
    import os
    from news.clinic import published_diagnoses
    from news.clinic_models import SpinDiagnosis
    start, end = bounds(now)
    posted = SpinDiagnosis.objects.filter(x_posted_at__gte=start, x_posted_at__lte=now).order_by('x_posted_at').first()
    if posted:
        return result('done', 'Wpis Dr. Spina jest na X.', posted.x_posted_at)
    candidates = published_diagnoses().filter(diagnosed_at__gte=start, diagnosed_at__lte=now,
        verdict='spin', intensity__gte=int(os.environ.get('X_POST_MIN_INTENSITY', '55')))
    if not candidates.exists():
        return result('na', 'Brak dzisiejszych zatwierdzonych diagnoz do publikacji.')
    return missing(now, at(now, 21, 30), 'Gotowa diagnoza czeka na publikację X.')


def check_thread(now):
    from news import clinic
    from news.models import Thread
    from news.repairer import flag
    row = Thread.objects.filter(slug=f'dr-spin-kontekst-{bounds(now)[0].date()}', published=True).first()
    if row:
        return result('done', 'Spinka z kontekstem jest opublikowana.', row.created_at)
    if not flag('DR_SPIN_THREADS_ENABLED', False):
        return result('na', 'Spinki są wyłączone.')
    daily = clinic.spin_of_day_by_camp()
    spin = daily['spins'].get(daily['order'][0]) if daily.get('order') else None
    if not spin:
        return result('na', 'Brak spinu dnia do opracowania.')
    from news.dr_spin_threads import _candidates
    if len(_candidates(spin)) < 3:
        return result('na', 'Mniej niż 3 materiały do kontekstu.')
    return missing(now, at(now, 20, 30), 'Spinka z kontekstem nie powstała.')


def check_narrative(now):
    from news.clinic_models import ClinicDailyMessage
    from news.narrative_threads import candidates
    from news.features import threads_enabled
    if not threads_enabled():
        return result('na', 'Spinki są wyłączone.')
    messages = list(ClinicDailyMessage.objects.filter(day=bounds(now)[0].date(), status='approved',
        camp__in=['government', 'opposition']))
    eligible = [message for message in messages if candidates(message)]
    if not eligible:
        if now < at(now, 21, 45):
            return result('waiting', 'Czekamy na ostatni przekaz dnia.')
        return result('na', 'Brak wątku z 3 wpisami od 2 autorów i przypisanym tonem lub techniką.')
    from news.account_models import PersonalContextThread
    completed = PersonalContextThread.objects.filter(narrative_message__in=eligible, is_public=True, hidden_at__isnull=True)
    if completed.count() == len(eligible):
        return result('done', 'Spinki narracji gotowe dla kwalifikujących się stron.', completed.latest('updated_at').updated_at)
    return missing(now, at(now, 22, 30), 'Spinka narracji czeka na opracowanie.')


def check_weekly(now):
    from news.clinic_models import WeeklyReport
    day = bounds(now)[0].date()
    if day.weekday() != 6:
        return result('na', 'Raport powstaje w niedzielę.')
    row = WeeklyReport.objects.filter(week_end=day).exclude(summary='').first()
    if row:
        return result('done', 'Raport tygodnia gotowy.', row.created_at)
    return missing(now, at(now, 21), 'Brak pełnego raportu tygodnia.')


@dataclass(frozen=True)
class Milestone:
    key: str
    name: str
    description: str
    planned: str
    deadline: str
    check: object
    remedies: tuple
    not_applicable: str


def check_institutional_reports(now):
    from django.conf import settings
    from news.report_models import InstitutionalReport, ReportDailyBudget
    from news.raportysta import window_open
    if not settings.REPORTS_ENABLED:
        return result('na', 'Przygotowanie raportów jest wyłączone.')
    pending = InstitutionalReport.objects.filter(status__in=['queued', 'working'])
    if not pending.exists():
        return result('done', 'Brak raportów oczekujących na recenzję.', now)
    if ReportDailyBudget.objects.filter(day=now.date(), calls__gte=settings.REPORTS_DAILY_CALLS).exists():
        return result('budget', 'Dzienny limit raportów wykorzystany. Ciąg dalszy w kolejnym oknie.')
    return result('running' if window_open(now) else 'waiting',
                  'Recenzje w oknie 02:00-06:00 po resecie limitów i zakończeniu diagnoz.')


MILESTONES = (
    Milestone('institutional-reports', 'Raporty dla instytucji', 'Recenzje analiz i pliki do zatwierdzenia.',
              '02:00-06:00 co 5 min', 'W granicach osobnego budżetu', check_institutional_reports,
              (), 'Przygotowanie raportów wyłączone.'),
    Milestone('narrative', 'Spinka narracji', 'Wątek przekazu dnia według wspólnego kryterium dla obu stron.',
              '21:45', '22:30', check_narrative, ('narrative',) * 3, 'Brak kwalifikującego się wątku.'),
    Milestone('poll', 'Zbieranie wpisów z X', 'Sprawdzamy udany puls zadania, także bez nowych wpisów.',
              'co minutę', '10 min w godz. 7-23, 2 h w nocy', check_poll, ('poll',) * 3, 'Zbieranie wyłączone.'),
    Milestone('screen', 'Strażnik wpisów', 'Każdy dostępny wpis otrzymuje ocenę.',
              'co 5 min', '30 min od pobrania', check_screen, ('screen',) * 3, 'Brak wpisów.'),
    Milestone('diagnoses', 'Diagnozy', 'Pierwszy kandydat otrzymuje diagnozę rano.',
              '7-22 co 10 min', '10:00', check_diagnoses, ('diagnoses',) * 3, 'Brak kandydatów.'),
    Milestone('interview', 'Wywiad dnia', 'Opracowujemy jeden wywiad z poprzedniego dnia.',
              'wybór 7:05, praca co 10 min', 'wybór 8:00, gotowy 18:00', check_interview,
              ('interview_run', 'interview_pick', 'interview_next'), 'Wywiady wyłączone.'),
    *(Milestone('message-' + camp, 'Przekaz dnia: ' + label, 'Przygotowujemy wspólny przekaz tej strony.',
                '9, 12, 15, 18, 21:30', '12:30, kontrola 22:15', partial(check_message, camp),
                ('message_free', 'message_backup', 'message_paid'), 'Wpisy z mniej niż 3 kont.')
      for camp, label in [('government', 'rządzący'), ('opposition', 'opozycja')]),
    Milestone('publication', 'Publikacja', 'Publikujemy zatwierdzoną diagnozę na X i w social mediach.',
              '8-21 co 30 min', '21:30', check_publication, ('publication',) * 3, 'Brak diagnoz do publikacji.'),
    Milestone('thread', 'Spinka Dr. Spina', 'Dodajemy kontekst spinu dnia w portalu.',
              '19:30', '20:30', check_thread, ('thread',) * 3, 'Brak spinu lub 3 materiałów kontekstu; wyłączone spinki.'),
    Milestone('weekly', 'Raport tygodnia', 'Podsumowujemy tydzień w portalu.',
              'niedziela 20:00', 'niedziela 21:00', check_weekly, ('weekly',) * 3, 'Dzień inny niż niedziela.'),
)


def snapshot(now=None):
    from django.utils import timezone
    from news.rescuer import state_data
    now = now or timezone.now()
    rows = []
    for item in MILESTONES:
        try:
            status, details = item.check(now)
        except Exception:
            status, details = result('alarm', 'Nie udało się odczytać stanu. Sprawdź logi Dyżurnego.')
        state = state_data(item.key, now)
        attempts = state.get('attempts', [])
        if status == 'late' and attempts:
            status = 'alarm' if state.get('escalated_at') else 'repairing'
        rows.append({'key': item.key, 'name': item.name, 'description': item.description, 'planned': item.planned,
                     'deadline': item.deadline, 'status': status, **details, 'attempt': len(attempts),
                     'attempts': [{k: a[k] for k in ('at', 'status', 'detail')} for a in attempts],
                     'not_applicable': item.not_applicable,
                     'proposal': state.get('proposal', ''), 'mail': state.get('mail', '')})
    priority = {'alarm': 0, 'repairing': 1, 'late': 2, 'budget': 3, 'running': 4, 'waiting': 5, 'done': 6, 'na': 7}
    return {'generated_at': now.isoformat(), 'results': sorted(rows, key=lambda r: priority[r['status']])}
