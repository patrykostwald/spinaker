"""Ratownik: zamknięta lista napraw, trzy próby na dzień, bez decyzji LLM."""
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from news.models import DutyAlarm, RepairerState
from news.repairer import stamp

SPACING = timedelta(minutes=15)
LEASE = timedelta(minutes=40)


def state_key(key, now):
    from news.daily_schedule import bounds
    return f'rescue:{bounds(now)[0].date()}:{key}'


def state_data(key, now):
    row = RepairerState.objects.filter(key=state_key(key, now)).first()
    return row.data if row else {}


def escalate(item, now):
    from news.council_recruiter import _owner_email
    from news.social_publish import _mail
    from news.push_events import _enqueue_staff
    with transaction.atomic():
        row = RepairerState.objects.select_for_update().get(key=state_key(item.key, now))
        if row.data.get('escalated_at'):
            return
        data = dict(row.data)
        data['escalated_at'] = now.isoformat()
        data['mail'] = 'Zarezerwowano pilny mail.'
        row.data = data
        row.save(update_fields=['data'])
    errors = '; '.join(a.get('detail', 'Brak wyniku workera.') for a in data['attempts'])
    body = (f'{item.name}: trzy próby nie przyniosły wyniku.\nOstatnie wyniki: {errors}\n'
            'Naprawiacz przygotuje propozycję. Decyzja o zmianie produkcji należy do właściciela.')
    DutyAlarm.objects.filter(key='schedule:' + item.key, status='open').update(severity='critical')
    # Istniejący Naprawiacz zapisuje analizę i propozycję dla właściciela.
    from news.repairer import schedule_proposal
    schedule_proposal(row.key, item.name, body, now)
    try:
        sent = _mail(_owner_email(), 'spin.clinic: pilne, ' + item.name, body, important=True)
    except Exception:
        sent = False
    with transaction.atomic():
        row = RepairerState.objects.select_for_update().get(pk=row.pk)
        row.data = {**row.data, 'mail': 'Wysłano.' if sent else 'Nie wysłano. Sprawdź SMTP w panelu.'}
        row.save(update_fields=['data'])
    try:
        _enqueue_staff(row.key, {'title': 'Alarm: ' + item.name, 'body': 'Trzy próby bez wyniku. Sprawdź panel.',
                                'url': '/panel', 'tag': row.key})
    except Exception:
        pass


def rescue(item, now):
    """Rezerwacja przeżywa błąd brokera; sukces potwierdzamy tylko wynikiem w bazie."""
    from config.celery import app
    should_escalate = False
    with transaction.atomic():
        row, _ = RepairerState.objects.get_or_create(key=state_key(item.key, now))
        row = RepairerState.objects.select_for_update().get(pk=row.pk)
        data = dict(row.data)
        attempts = list(data.get('attempts', []))
        if attempts:
            last = attempts[-1]
            elapsed = now - stamp(last['at'])
            if elapsed < SPACING or (last['status'] in ('reserved', 'running') and elapsed < LEASE):
                return
            if last['status'] in ('reserved', 'running'):
                last.update(status='failed', detail='Worker nie potwierdził wyniku w ciągu 40 min.')
        if len(attempts) >= 3:
            should_escalate = True
        else:
            token = uuid4().hex
            attempts.append({'at': now.isoformat(), 'token': token, 'remedy': item.remedies[len(attempts)],
                             'status': 'reserved', 'detail': 'Zarezerwowano naprawę.'})
        data['attempts'] = attempts
        row.data = data
        row.save(update_fields=['data'])
    if should_escalate:
        escalate(item, now)
        return
    try:
        app.send_task('news.tasks.schedule_rescue_task', args=[item.key, row.key, token], expires=900, retry=False)
    except Exception:
        finish(row.key, token, 'failed', 'Nie udało się wysłać zadania do brokera.')
        if len(attempts) == 3:
            escalate(item, now)


def finish(key, token, status, detail):
    with transaction.atomic():
        row = RepairerState.objects.select_for_update().get(key=key)
        data = dict(row.data)
        for attempt in data['attempts']:
            if attempt['token'] == token:
                attempt.update(status=status, detail=detail[:300])
        row.data = data
        row.save(update_fields=['data'])


def execute(key, stored_key, token):
    from news.daily_schedule import MILESTONES
    item = next(m for m in MILESTONES if m.key == key)
    now = timezone.now()
    if state_key(key, now) != stored_key:
        return {'status': 'expired'}
    with transaction.atomic():
        row = RepairerState.objects.select_for_update().get(key=stored_key)
        attempt = row.data['attempts'][-1]
        if attempt['token'] != token or attempt['status'] != 'reserved':
            return {'status': 'already_running'}
        if now - stamp(attempt['at']) >= SPACING:
            return {'status': 'expired'}
        attempt['status'] = 'running'
        row.save(update_fields=['data'])
    try:
        status, detail = item.check(now)
        if status != 'late':
            finish(stored_key, token, 'skipped', detail['detail'])
            return {'status': 'skipped'}
        outcome = apply_remedy(item, attempt['remedy'])
        status, detail = item.check(timezone.now())
        from news.task_heartbeat import summary
        errors = '; '.join((outcome.get('errors') or {}).values()) if isinstance(outcome, dict) and isinstance(outcome.get('errors'), dict) else ''
        finish(stored_key, token, 'done' if status in ('done', 'na') else 'failed',
               detail['detail'] + ' ' + summary(outcome) + (' ' + errors if errors else ''))
    except Exception as error:
        from news.admin_telemetry import safe_error
        finish(stored_key, token, 'failed', safe_error(error).replace('—', '-'))
    # Długi wywiad może trwać ponad odstęp między kontrolami.
    if state_key(key, timezone.now()) == stored_key:
        status, _ = item.check(timezone.now())
        if status == 'late' and len(state_data(key, now).get('attempts', [])) == 3:
            escalate(item, timezone.now())
        guard(timezone.now(), items=(item,))
    return {'status': 'ok'}


def apply_remedy(item, remedy):
    from news import tasks
    simple = {'poll': tasks.political_poll_task, 'screen': tasks.clinic_screen_task,
              'diagnoses': tasks.clinic_diagnose_task, 'thread': tasks.dr_spin_thread_task,
              'weekly': tasks.weekly_report_task}
    if remedy in simple:
        if remedy == 'diagnoses':
            requeue_diagnosis()
        kwargs = {'include_old': True} if remedy == 'screen' else {}
        return simple[remedy].apply(kwargs=kwargs, throw=True).result
    if remedy == 'publication':
        x = tasks.x_publish_task.apply(throw=True).result
        social = tasks.social_publish_task.apply(throw=True).result
        return {'x': x, 'social': social}
    if remedy.startswith('interview_'):
        from news.clinic_interview import pick_yesterday, release_stuck
        release_stuck()
        if remedy != 'interview_run':
            pick_yesterday(next_candidate=remedy == 'interview_next')
        outcome = tasks.clinic_interview_task.apply(
            kwargs={'day': (timezone.localdate() - timedelta(days=1)).isoformat()}, throw=True).result
        from news.clinic_models import ClinicInterview
        from news.admin_telemetry import safe_error
        errors = ClinicInterview.objects.filter(day=timezone.localdate() - timedelta(days=1), status='failed').values_list('pk', 'error')
        return {**outcome, 'errors': {str(pk): safe_error(error).replace('—', '-') for pk, error in errors}}
    if remedy.startswith('message_'):
        from news.clinic import run_daily_messages
        from news.clinic_ai import DAILY_MESSAGE_MODELS
        model = DAILY_MESSAGE_MODELS[('message_free', 'message_backup', 'message_paid').index(remedy)]
        return run_daily_messages(day=timezone.localdate(), camps=(item.key.removeprefix('message-'),),
                                  models=(model,), only_missing=True)
    raise ValueError('Nieznana naprawa.')


def requeue_diagnosis():
    """Jedna świeża diagnoza po błędzie chwilowym; zachowujemy zapisany wynik AI."""
    from news.clinic import budget_left, diagnosis_reserve
    from news.clinic_models import SpinDiagnosis
    from news.repairer import transient
    if budget_left() < diagnosis_reserve():
        return
    with transaction.atomic():
        rows = SpinDiagnosis.objects.select_for_update().filter(status='failed', hidden_at__isnull=True,
            withdrawn_at__isnull=True, post__available=True,
            post__published_at__gte=timezone.now() - timedelta(hours=24)).order_by('-screen_score')
        for row in rows:
            if transient(row.error) and '_daily_limit' not in row.error:
                row.status = 'queued'
                row.save(update_fields=['status'])
                return


def guard(now, items=None):
    from news.daily_schedule import MILESTONES
    for item in items if items is not None else MILESTONES:
        key = 'schedule:' + item.key
        try:
            status, details = item.check(now)
        except Exception:
            # Brak dowodu nie zamyka istniejącego alarmu i nie uruchamia naprawy.
            DutyAlarm.objects.update_or_create(key='schedule-check:' + item.key, defaults={
                'rule': 'schedule-health', 'severity': 'warning', 'title': 'Błąd kontroli: ' + item.name,
                'instruction': 'Sprawdź logi Dyżurnego.', 'status': 'open', 'last_seen': now, 'closed_at': None})
            continue
        DutyAlarm.objects.filter(key='schedule-check:' + item.key, status='open').update(status='closed', closed_at=now)
        if status != 'late':
            DutyAlarm.objects.filter(key=key, status='open').update(status='closed', closed_at=now)
            continue
        state = state_data(item.key, now)
        row, created = DutyAlarm.objects.get_or_create(key=key, defaults={
            'rule': 'schedule', 'severity': 'warning', 'title': item.name + ': po terminie',
            'instruction': 'Ratownik wykona najwyżej trzy próby. Potem sprawdź propozycję Naprawiacza.',
            'first_seen': now, 'since': now})
        row.status, row.closed_at, row.last_seen = 'open', None, now
        row.severity = 'critical' if state.get('escalated_at') else 'warning'
        row.details = details
        row.occurrences += 1
        row.save()
        rescue(item, now)
