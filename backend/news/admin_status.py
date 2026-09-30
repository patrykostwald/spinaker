"""Staff-only snapshot: database, cache and local OS; no outbound probes or AI."""
import os
import shutil
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db.models import Count, Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from news.clinic_models import (ClinicInterview, CouncilRecruitment, CouncilSeat,
                               SocialPost, SpinDiagnosis, SOCIAL_PLATFORMS)
from news.models import ArchiveJob, Article, FetchRequest, ImportState, Source
from news.newsletter_models import NewsletterSubscriber
from news.political_models import PoliticalPost
from news.task_heartbeat import cadence


def metric(label, value):
    return {'label': label, 'value': value if value is not None else 'unknown'}


def card(title, status='unknown', description='Brak danych.', last_event=None, metrics=None, items=None):
    return dict(title=title, status=status, description=description, last_event=last_event or 'unknown',
                metrics=metrics or [], items=items or [])


def worst(items):
    return next((s for s in ('error', 'warn', 'unknown') if any(i['status'] == s for i in items)), 'ok') if items else 'unknown'


def server(now):
    metrics, levels = [], []
    try:
        load = os.getloadavg()
        metrics += [metric(f'Obciążenie {n} min', round(v, 2)) for n, v in zip((1, 5, 15), load)]
        levels.append('warn' if load[0] > (os.cpu_count() or 1) * 2 else 'ok')
    except (AttributeError, OSError):
        metrics.append(metric('Obciążenie', None))
        levels.append('unknown')
    try:
        disk = shutil.disk_usage('/')
        metrics += [metric('Dysk wolny (GiB)', round(disk.free / 2**30, 2)), metric('Dysk wolny (%)', round(disk.free / disk.total * 100, 1))]
        levels.append('error' if disk.free / disk.total < .05 else 'warn' if disk.free / disk.total < .15 else 'ok')
    except OSError:
        metrics.append(metric('Dysk', None))
        levels.append('unknown')
    try:
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        total, available = (int(mem[k].split()[0]) for k in ('MemTotal', 'MemAvailable'))
        metrics += [metric('RAM dostępna (MiB)', round(available / 1024)), metric('RAM razem (MiB)', round(total / 1024))]
        levels.append('warn' if available / total < .1 else 'ok')
    except (OSError, KeyError, ValueError):
        metrics.append(metric('RAM', None))
        levels.append('unknown')
    commit = next((os.environ[k] for k in ('GIT_COMMIT', 'COMMIT_SHA', 'RAILWAY_GIT_COMMIT_SHA', 'VERCEL_GIT_COMMIT_SHA', 'SOURCE_VERSION') if os.environ.get(k)), None)
    if commit:
        metrics.append(metric('Wersja kodu', commit[:64]))
    return card('Serwer (VPS)', worst([{'status': s} for s in levels]),
                'Pomiar lokalnego środowiska API (w kontenerze: widoczne zasoby hosta). Nie sprawdza zewnętrznej dostępności strony.', now, metrics)


def tasks(now):
    from config.celery import app
    entries = app.conf.beat_schedule
    pulses = cache.get_many([f'heartbeat:{name}' for name in entries])
    rows = []
    for name, entry in entries.items():
        pulse = pulses.get(f'heartbeat:{name}', {})
        interval = cadence(entry['schedule'])
        started = parse_datetime(pulse.get('started_at', ''))
        stale = bool(started and interval and (now - started).total_seconds() > interval * 2)
        state = 'error' if pulse.get('phase') == 'error' else 'warn' if stale else 'ok' if pulse else 'unknown'
        rows.append(card(name, state, ('Brak uruchomienia przez ponad 2× rytm. ' if stale else '') + pulse.get('summary', 'Brak pulsu; historia sprzed wdrożenia nie jest dostępna.'),
                         pulse.get('last_event'), [metric('Ostatnie uruchomienie', pulse.get('started_at')),
                         metric('Ostatni wynik', pulse.get('result')), metric('Maksymalny odstęp (min)', interval / 60 if interval else None)]))
    return card('Zadania w tle', worst(rows), 'Puls wykonania; nie jest dowodem, że zadanie uruchomił beat. Przerwy nocne uwzględnione.',
                max((p.get('last_event', '') for p in pulses.values()), default=None),
                [metric('Zadania', len(rows)), metric('Ostrzeżenia', sum(r['status'] == 'warn' for r in rows))], rows)


def daily_counts(query, field, today, yesterday, tomorrow):
    return query.aggregate(today=Count('pk', filter=Q(**{f'{field}__gte': today, f'{field}__lt': tomorrow})),
                           yesterday=Count('pk', filter=Q(**{f'{field}__gte': yesterday, f'{field}__lt': today})), last=Max(field))


def diagnoses(title, field, today, yesterday, tomorrow, now):
    query = SpinDiagnosis.objects.all()
    counts = list(query.filter(**{f'{field}__gte': yesterday, f'{field}__lt': tomorrow}).order_by().values('status').annotate(
        today=Count('pk', filter=Q(**{f'{field}__gte': today})), yesterday=Count('pk', filter=Q(**{f'{field}__lt': today}))))
    labels = dict(SpinDiagnosis._meta.get_field('status').choices)
    rows = [card(labels.get(r['status'], r['status']), 'error' if r['status'] == 'failed' else 'ok',
                 'Obecny status rekordów utworzonych/diagnozowanych danego dnia.', metrics=[metric('Dziś', r['today']), metric('Wczoraj', r['yesterday'])]) for r in counts]
    # diagnose() records diagnosed_at on both success and failure. Screening has
    # no separate error history; its status is later overwritten by diagnosis.
    errors = list(query.filter(diagnosed_at__gte=now - timedelta(hours=24), diagnosed_at__lte=now).exclude(error='').order_by()
                  .values('error').annotate(count=Count('pk'), last=Max('diagnosed_at')).order_by('-count', 'error')[:5]) if field == 'diagnosed_at' else []
    rows += [card('Błąd diagnozy (24 h)', 'error', r['error'], r['last'], [metric('Liczba', r['count'])]) for r in errors]
    totals = daily_counts(query, field, today, yesterday, tomorrow)
    description = ('Obecne statusy rekordów przesiewu; status po diagnozie zastępuje status strażnika. Historia błędów strażnika: brak danych.'
                   if field == 'created_at' else 'Diagnozy według czasu ostatniej próby. Najczęstsze zapisane błędy z ostatnich 24 h; ponowienia nadpisują wcześniejszy wynik.')
    return card(title, worst(rows) if rows else 'ok' if totals['last'] else 'unknown', description,
                totals['last'], [metric('Dziś', totals['today']), metric('Wczoraj', totals['yesterday'])] +
                ([metric('Błędy strażnika (24 h)', None)] if field == 'created_at' else []), rows)


def interview():
    row = ClinicInterview.objects.order_by('-day', '-created_at').only('title', 'channel', 'status', 'error', 'created_at', 'diagnosed_at', 'day', 'hidden_at').first()
    if not row:
        return card('Wywiad dnia')
    stages = {'queued': 'W kolejce', 'approved': 'Opublikowany', 'failed': 'Błąd', 'pending_review': 'W toku: transkrypcja albo diagnoza', 'not_applicable': 'Bez treści do oceny', 'rejected': 'Odrzucony'}
    stage = 'Ukryty' if row.hidden_at else stages.get(row.status, 'unknown')
    return card('Wywiad dnia', 'error' if row.status == 'failed' else 'ok' if stage == 'Opublikowany' else 'warn',
                row.error or 'Najnowszy wybrany materiał. Dokładny etap pracy w toku nie jest rejestrowany.', row.diagnosed_at or row.created_at,
                [metric('Tytuł', row.title), metric('Kanał', row.channel), metric('Dzień emisji', row.day), metric('Etap', stage)])


def council():
    from news.council_charter import roster
    from news.council_recruiter import auto_mode
    seats = {(s.provider, s.model): s for s in CouncilSeat.objects.all()}
    rows = []
    for member in roster():
        seat = seats.get((member['provider'], member['model']))
        error = seat.last_error if seat else ''
        if '402' in error:
            error = '402 — brak środków / wymagana płatność u dostawcy. ' + error
        state = 'error' if error else 'ok' if member['status'] == 'dostępny' else 'warn'
        rows.append(card(f"{member['provider']} · {member['model']}", state, member['status'] + (f' · {error}' if error else ''),
                         max(filter(None, (seat.last_ok_at, seat.suspended_at, seat.admitted_at)), default=None) if seat else None,
                         [metric('Czas ostatniego błędu', None)] if error else []))
    recent = list(CouncilRecruitment.objects.order_by('-created_at', '-pk').values('provider', 'model', 'decision', 'mode', 'created_at')[:5])
    recruitments = [card(f"{r['provider']} · {r['model']}", 'ok', f"Decyzja: {r['decision']} · tryb: {r['mode']}", r['created_at']) for r in recent]
    return [card('Konsylium', worst(rows), 'Dostępność z konfiguracji i lokalnych limitów; bez odpytywania modeli.',
                 max((r['last_event'] for r in rows if r['last_event'] != 'unknown'), default=None), [metric('Członkowie', len(rows))], rows),
            card('Rekruter', 'ok' if recent else 'unknown', 'Ostatnie 5 zdarzeń.', recent[0]['created_at'] if recent else None,
                 [metric('Tryb próbny', not auto_mode()), metric('Pokazane zdarzenia', len(recent))], recruitments)]


def social(today, tomorrow):
    rows = []
    for platform, label in SOCIAL_PLATFORMS:
        post = SocialPost.objects.filter(platform=platform).order_by('-posted_at', '-pk').values('posted_at', 'error', 'deleted_at', 'external_id').first()
        rows.append(card(label, 'error' if post and post['error'] else 'ok' if post else 'unknown',
                         post['error'] or ('Usunięty' if post['deleted_at'] else f"Ostatni wpis: {post['external_id'] or 'brak identyfikatora'}") if post else 'Brak wpisów.',
                         post['posted_at'] if post else None))
    x = SpinDiagnosis.objects.aggregate(last=Max('x_posted_at'), today=Count('pk', filter=Q(x_posted_at__gte=today, x_posted_at__lt=tomorrow)))
    rows.append(card('X', 'ok' if x['last'] else 'unknown', 'Liczba opublikowanych wątków diagnoz (nie pojedynczych tweetów).', x['last'], [metric('Dziś', x['today'])]))
    return card('Media społecznościowe', worst(rows), 'Ostatni zapis na każdym kanale.',
                max((r['last_event'] for r in rows if r['last_event'] != 'unknown'), default=None), items=rows)


INGESTION_LABELS = {'rss': 'RSS', 'gdelt': 'GDELT', 'newsapi': 'NewsAPI', 'x': 'X (materiały)', 'sejm': 'API Sejmu',
                    'eli': 'ELI (akty prawne)', 'archive': 'Archiwa wydawców', 'youtube': 'YouTube', 'manual': 'Ręcznie'}


def intake(today, yesterday, tomorrow):
    """Ile materiałów weszło do bazy dziś i wczoraj — osobno z każdego źródła pobierania."""
    rows = []
    for method, label in INGESTION_LABELS.items():
        data = daily_counts(Article.objects.filter(ingestion_method=method), 'scraped_at', today, yesterday, tomorrow)
        if not (data['today'] or data['yesterday'] or data['last']):
            continue
        rows.append(card(label, 'ok' if data['today'] else 'warn' if data['yesterday'] else 'unknown',
                         'Nowe materiały według czasu zapisu w bazie.', data['last'],
                         [metric('Dziś', data['today']), metric('Wczoraj', data['yesterday'])]))
    total = daily_counts(Article.objects.all(), 'scraped_at', today, yesterday, tomorrow)
    return card('Pobieranie materiałów', 'ok' if total['today'] else 'warn', 'Materiały ze wszystkich harvesterów; szczegóły dla każdego źródła poniżej.',
                total['last'], [metric('Dziś razem', total['today']), metric('Wczoraj razem', total['yesterday']),
                               metric('W bazie', Article.objects.count())], rows)


def queues(now):
    """Kolejki pracy: archiwa wydawców, pobrania w toku, wpisy czekające na strażnika i diagnozę."""
    jobs = ArchiveJob.objects.aggregate(pending=Count('pk', filter=Q(status='pending')), ready=Count('pk', filter=Q(status='pending', available_at__lte=now)),
                                        failed=Count('pk', filter=Q(status='failed')), done_24h=Count('pk', filter=Q(checked_at__gte=now - timedelta(hours=24))))
    reserved = FetchRequest.objects.filter(state='reserved').count()
    clinic = SpinDiagnosis.objects.aggregate(queued=Count('pk', filter=Q(status='queued')), review=Count('pk', filter=Q(status='pending_review')),
                                             failed_24h=Count('pk', filter=Q(status='failed', diagnosed_at__gte=now - timedelta(hours=24))))
    status = 'warn' if jobs['failed'] > 50 or clinic['failed_24h'] > 5 else 'ok'
    return card('Kolejki', status, 'Co czeka na przetworzenie. Diagnozy robią się w dzień (7:00–23:00).', now, [
        metric('Archiwa: w kolejce', jobs['pending']), metric('Archiwa: gotowe teraz', jobs['ready']),
        metric('Archiwa: sprawdzone w 24 h', jobs['done_24h']), metric('Archiwa: nieudane', jobs['failed']),
        metric('Pobrania w toku', reserved), metric('Wpisy czekające na diagnozę', clinic['queued']),
        metric('Diagnozy do przeglądu', clinic['review']), metric('Nieudane diagnozy (24 h)', clinic['failed_24h'])])


def sources():
    states = list(ImportState.objects.order_by('name').values('name', 'last_success', 'last_started', 'last_error', 'imported'))
    rss = Source.objects.filter(source_type='rss').aggregate(
        active=Count('pk', filter=Q(is_active=True, scrape_enabled=True)),
        blocked=Count('pk', filter=Q(is_active=False) | Q(scrape_enabled=False)), errors=Count('pk', filter=~Q(last_error='')), last=Max('last_scraped'))
    rows = [card(r['name'], 'error' if r['last_error'] else 'ok' if r['last_success'] else 'unknown', r['last_error'] or 'Stan zapisany przez importer.',
                 r['last_started'] or r['last_success'], [metric('Ostatni sukces', r['last_success']), metric('Zaimportowano', r['imported'])]) for r in states]
    return card('Źródła / harvestery', 'warn' if rss['errors'] and worst(rows) != 'error' else worst(rows),
                'Liczba bieżących stanów z błędem; brak historycznego licznika błędów. RSS zablokowane = wyłączone źródło lub pobieranie.',
                max(filter(None, [rss['last']] + [r['last_success'] for r in states]), default=None),
                [metric('Importery z błędem', sum(bool(r['last_error']) for r in states)), metric('RSS aktywne', rss['active']),
                 metric('RSS zablokowane', rss['blocked']), metric('RSS z błędem', rss['errors']), metric('Historyczna liczba błędów', None)], rows)


@never_cache
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_status(request):
    now = timezone.now()
    local_day = now.astimezone(ZoneInfo('Europe/Warsaw')).date()
    today, yesterday, tomorrow = [datetime.combine(local_day + timedelta(days=d), time.min, ZoneInfo('Europe/Warsaw')) for d in (0, -1, 1)]
    sections = []
    def collect(title, fn):
        try:
            result = fn()
            sections.extend(result if isinstance(result, list) else [result])
        except Exception:
            # Partial outages must not hide the other cards or expose exception secrets.
            sections.append(card(title, description='Nie udało się odczytać stanu.'))
    collect('Serwer (VPS)', lambda: server(now))
    collect('Zadania w tle', lambda: tasks(now))
    def posts():
        import os
        data = daily_counts(PoliticalPost.objects.all(), 'fetched_at', today, yesterday, tomorrow)
        state = ImportState.objects.filter(name='political-x-budget').first()
        budget = dict(state.cursor) if state else {}
        limit = os.environ.get('X_POLITICAL_MONTHLY_USD_LIMIT', '5')
        spent = budget.get('spent_upper_usd')
        blocked = budget.get('blocked_until', '') > now.isoformat()
        near = spent is not None and float(spent) >= float(limit) * 0.95
        status = 'error' if blocked or (state and state.last_error) else 'warn' if near or not data['today'] else 'ok'
        note = ('Wstrzymane: X odrzuca zapytania (np. brak środków na koncie X) — wznowi się samo.' if blocked else
                'Miesięczny limit wydatków prawie wyczerpany — pobieranie stanie do nowego miesiąca albo podniesienia limitu.' if near else
                'Wpisy polityków z oficjalnego API X według czasu pobrania.')
        return card('X — pobieranie wpisów', status, note, data['last'], [
            metric('Dziś', data['today']), metric('Wczoraj', data['yesterday']),
            metric('Zapytania dziś', budget.get('daily_requests')), metric('Wydane w miesiącu (USD, górny szacunek)', spent),
            metric('Limit miesięczny (USD)', limit), metric('Ostatni błąd', (state.last_error if state else None) or 'brak')])
    collect('X — pobieranie wpisów', posts)
    collect('Strażnik', lambda: diagnoses('Strażnik', 'created_at', today, yesterday, tomorrow, now))
    collect('Diagnozy', lambda: diagnoses('Diagnozy', 'diagnosed_at', today, yesterday, tomorrow, now))
    collect('Wywiad dnia', interview)
    collect('Konsylium / Rekruter', council)
    collect('Media społecznościowe', lambda: social(today, tomorrow))
    collect('Pobieranie materiałów', lambda: intake(today, yesterday, tomorrow))
    collect('Kolejki', lambda: queues(now))
    collect('Źródła / harvestery', sources)
    def newsletter():
        data = NewsletterSubscriber.objects.filter(status='confirmed').aggregate(count=Count('pk'), last=Max('confirmed_at'))
        return card('Newsletter', 'ok', 'Potwierdzone zapisy.', data['last'], [metric('Zapisy', data['count'])])
    collect('Newsletter', newsletter)
    return Response({'generated_at': now, 'sections': sections})
