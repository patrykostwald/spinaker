"""Read-only operational evidence. No external requests and no model calls."""
import math
import os
import re
import shutil
from datetime import datetime, timedelta, time, timezone as dt_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate
from django.utils.dateparse import parse_datetime

from news.clinic_models import ClinicInterview, SpinDiagnosis, SocialPost
from news.models import (Article, ArticleContent, ArchiveJob, OfficialRecord,
                         ParliamentaryVoting, Source)
from news.political_models import PoliticalAccount, PoliticalPost, PublicFigure

WARSAW = ZoneInfo('Europe/Warsaw')


def safe_error(value):
    """Only classifications leave the server: exception messages can contain keys."""
    if not value:
        return ''
    message = str(value).lower()
    for code, label in ((402, 'brak środków — doładuj konto dostawcy'),
                        (401, 'brak autoryzacji — sprawdź konfigurację klucza'),
                        (403, 'brak uprawnień — sprawdź dostęp'),
                        (429, 'limit zapytań — poczekaj na reset'),
                        (404, 'nie znaleziono zasobu'),
                        (500, 'błąd serwera dostawcy'), (502, 'błąd bramy dostawcy'),
                        (503, 'dostawca niedostępny')):
        if re.search(rf'(?<!\d){code}(?!\d)', message):
            return f'{code} — {label}'
    if 'timeout' in message or 'timed out' in message:
        return 'Przekroczony czas odpowiedzi — sprawdź połączenie.'
    return 'Zapisano błąd — szczegóły w chronionych logach.'


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def counts(query, field, today, yesterday, tomorrow):
    return query.aggregate(
        today=Count('pk', filter=Q(**{f'{field}__gte': today, f'{field}__lt': tomorrow})),
        yesterday=Count('pk', filter=Q(**{f'{field}__gte': yesterday, f'{field}__lt': today})),
        week=Count('pk', filter=Q(**{f'{field}__gte': today - timedelta(days=6), f'{field}__lt': tomorrow})),
        last=Max(field))


def intake(now, today, yesterday, tomorrow):
    from news.admin_status import card, metric, worst, INGESTION_LABELS
    recent = Article.objects.filter(scraped_at__gte=today - timedelta(days=6), scraped_at__lt=tomorrow)
    methods = list(recent.order_by().values('ingestion_method').annotate(
        today=Count('pk', filter=Q(scraped_at__gte=today)),
        yesterday=Count('pk', filter=Q(scraped_at__gte=yesterday, scraped_at__lt=today)),
        week=Count('pk'), last=Max('scraped_at')).order_by('ingestion_method'))
    rows = [card(INGESTION_LABELS.get(r['ingestion_method'], r['ingestion_method'] or 'Nieoznaczone'),
                 'ok', 'Materiały zapisane w bazie.', r['last'],
                 [metric('Dziś', r['today']), metric('Wczoraj', r['yesterday']), metric('7 dni', r['week'])]) for r in methods]
    top = recent.filter(scraped_at__gte=today).order_by().values('source_id', 'source__name').annotate(
        count=Count('pk')).order_by('-count', 'source_id')[:10]
    rows.append(card('Top 10 źródeł dnia', 'ok', 'Według nowych materiałów.', items=[
        card(r['source__name'], 'ok', metrics=[metric('Materiały dziś', r['count'])]) for r in top]))
    rss = Source.objects.filter(source_type='rss')
    rss_data = rss.aggregate(errors=Count('pk', filter=~Q(last_error='')), last=Max('last_attempted'))
    produced = Article.objects.filter(ingestion_method='rss', scraped_at__gte=now - timedelta(hours=24),
                                      scraped_at__lte=now).values('source_id').distinct().count()
    errors = rss.exclude(last_error='').order_by('-last_attempted', 'pk').values('name', 'last_error', 'last_attempted')[:5]
    rows.append(card('RSS', 'warn' if rss_data['errors'] else 'ok',
                     'Źródła z nowymi materiałami; bieżące błędy, nie historyczna liczba awarii.', rss_data['last'],
                     [metric('Źródła z materiałem w 24 h', produced), metric('Źródła z błędem', rss_data['errors'])],
                     [card(r['name'], 'error', safe_error(r['last_error']), r['last_attempted']) for r in errors]))
    archives = list(ArchiveJob.objects.order_by().values('status').annotate(count=Count('pk'), last=Max('checked_at')))
    rows.append(card('Archiwa', 'error' if any(r['status'] == 'failed' for r in archives) else 'ok', 'Bieżące statusy wszystkich zadań archiwalnych.', items=[
        card(r['status'], 'error' if r['status'] == 'failed' else 'ok', last_event=r['last'],
             metrics=[metric('Zadania', r['count'])]) for r in archives]))
    read = counts(ArticleContent.objects.exclude(text=''), 'fetched_at', today, yesterday, tomorrow)
    rows.append(card('Czytanie treści', 'ok', 'Rekordy z niepustym tekstem według fetched_at; bez historii ponownych odczytów.',
                     read['last'], [metric('Dziś', read['today']), metric('Wczoraj', read['yesterday']), metric('7 dni', read['week'])]))
    official = OfficialRecord.objects.order_by().values('provider').annotate(
        total=Count('pk'), today=Count('pk', filter=Q(fetched_at__gte=today, fetched_at__lt=tomorrow)), last=Max('fetched_at'))
    rows.append(card('Oficjalne źródła', 'ok', 'Głosowania dziś: czas zapisu powiązanego artykułu, nie data głosowania.',
                     metrics=[metric('Głosowania pobrane dziś', ParliamentaryVoting.objects.filter(
                         article__scraped_at__gte=today, article__scraped_at__lt=tomorrow).count())], items=[
                         card(r['provider'], 'ok', last_event=r['last'], metrics=[metric('Dziś', r['today']), metric('W bazie', r['total'])]) for r in official]))
    return card('Pobieranie i czytanie', worst(rows), 'Dziś, wczoraj i 7 dni kalendarzowych (łącznie z dziś), Europe/Warsaw.',
                max((r['last'] for r in methods), default=None),
                [metric('Dziś', sum(r['today'] for r in methods)), metric('Wczoraj', sum(r['yesterday'] for r in methods)),
                 metric('7 dni', sum(r['week'] for r in methods))], rows)


def x_read(now, today, yesterday, tomorrow):
    from news.admin_status import card, metric
    from news.models import ImportState
    data = counts(PoliticalPost.objects.all(), 'fetched_at', today, yesterday, tomorrow)
    state = ImportState.objects.filter(name='political-x-budget').first()
    budget = state.cursor if state and isinstance(state.cursor, dict) else {}
    utc_now = now.astimezone(dt_timezone.utc)
    current_day = budget.get('day') == utc_now.date().isoformat()
    current_month = budget.get('month') == utc_now.strftime('%Y-%m')
    spent = number(budget.get('spent_upper_usd')) if current_month else None
    limit = number(os.environ.get('X_POLITICAL_MONTHLY_USD_LIMIT', '5'))
    try:
        blocked_until = parse_datetime(str(budget.get('blocked_until', '')))
        if blocked_until and blocked_until.tzinfo is None:
            blocked_until = None
    except ValueError:
        blocked_until = None
    blocked = bool(blocked_until and blocked_until > now)
    accounts = list(PoliticalAccount.objects.select_related('confirmed_by').all())
    errors = [a for a in accounts if a.last_error]
    confirmed = sum(a.is_confirmed() for a in accounts)
    polled = sum(bool(a.last_polled_at and now - timedelta(hours=24) <= a.last_polled_at <= now) for a in accounts)
    status = 'error' if blocked or (state and state.last_error) else 'warn' if errors or (spent is not None and limit is not None and spent >= limit * .95) else 'ok'
    return card('X — pobieranie wpisów', status,
                ('Pobieranie wstrzymane. ' if blocked else '') +
                'Wpisy: Europe/Warsaw. Licznik budżetu ma dobę i miesiąc UTC; brak aktualnego okresu = unknown. Koszt to górny szacunek rezerwacji.',
                data['last'], [metric('Dziś', data['today']), metric('Wczoraj', data['yesterday']), metric('7 dni', data['week']),
                metric('Zapytania w dobie budżetu UTC', number(budget.get('daily_requests')) if current_day else None),
                metric('Wpisy w dobie budżetu UTC (z rezerwacjami)', number(budget.get('daily_posts')) if current_day else None),
                metric('Doba budżetu UTC', budget.get('day')), metric('Miesiąc budżetu UTC', budget.get('month')),
                metric('Wydane w miesiącu (USD, górny szacunek)', spent), metric('Limit miesięczny (USD)', limit),
                metric('Blokada do', blocked_until.astimezone(WARSAW) if blocked_until else None),
                metric('Potwierdzone konta', confirmed), metric('Odpytane konta w 24 h', polled), metric('Konta z błędem', len(errors)),
                metric('Ostatni błąd', safe_error(state.last_error) if state and state.last_error else 'brak')],
                [card('@' + a.handle, 'error', safe_error(a.last_error), a.last_polled_at) for a in errors[:10]])


def x_publish(today, yesterday, tomorrow):
    from news.admin_status import card, metric
    data = counts(SpinDiagnosis.objects.all(), 'x_posted_at', today, yesterday, tomorrow)
    last = SpinDiagnosis.objects.filter(x_posted_at__isnull=False).order_by('-x_posted_at').values('headline', 'x_posted_at').first()
    partial = SpinDiagnosis.objects.filter(x_posted_at__isnull=True).exclude(x_posted_ids=[]).count()
    return card('X — publikacja', 'warn' if partial else 'ok' if last else 'unknown',
                'Pełne wątki diagnoz. Błędy publikacji są w logach; nie są trwale zapisywane ani wiarygodnie liczone w pulsie zadania.',
                data['last'], [metric('Wątki dziś', data['today']), metric('Wątki wczoraj', data['yesterday']), metric('Wątki 7 dni', data['week']),
                metric('Ostatni wątek', last['headline'] if last else None), metric('Częściowe wątki', partial), metric('Błędy publikacji', None)])


def youtube(now, today, tomorrow):
    from news.admin_status import card, metric, interview
    from news.youtube_collect import daily_units, units_used, QUOTA_ZONE
    used, total = units_used(), daily_units()
    reset = datetime.combine(now.astimezone(QUOTA_ZONE).date() + timedelta(days=1), time.min, QUOTA_ZONE).astimezone(WARSAW)
    return card('YouTube', 'warn' if used >= total else 'ok',
                'Lokalnie zarezerwowane jednostki API; doba dostawcy to America/Los_Angeles. Filmy: dzień Europe/Warsaw.', now,
                [metric('Jednostki zużyte', used), metric('Jednostki pozostałe', max(0, total - used)), metric('Limit jednostek', total),
                metric('Następny reset', reset), metric('Filmy pobrane dziś', Article.objects.filter(
                    ingestion_method='youtube', scraped_at__gte=today, scraped_at__lt=tomorrow).count())], [interview()])


def next_run(schedule, now, started=None):
    """Next configured slot, never a claim that beat/worker is alive."""
    if hasattr(schedule, 'run_every'):
        if not started:
            return None
        return max(now, started + schedule.run_every).astimezone(WARSAW)
    if not all(hasattr(schedule, name) for name in ('minute', 'hour', 'day_of_week', 'day_of_month', 'month_of_year')):
        return None
    # All deployed schedules recur within one week. A bounded search also
    # handles most future monthly entries without walking minute by minute.
    local = now.astimezone(WARSAW)
    for offset in range(367):
        day = local.date() + timedelta(days=offset)
        if day.month not in schedule.month_of_year or day.day not in schedule.day_of_month or (day.weekday() + 1) % 7 not in schedule.day_of_week:
            continue
        for hour in sorted(schedule.hour):
            for minute in sorted(schedule.minute):
                candidate = datetime.combine(day, time(hour, minute), WARSAW)
                # Reject nonexistent local wall times during the spring jump.
                utc_candidate = candidate.astimezone(dt_timezone.utc)
                if utc_candidate.astimezone(WARSAW).replace(tzinfo=None) != candidate.replace(tzinfo=None):
                    continue
                if utc_candidate > now:
                    return candidate
    return None


def agents(now, today, tomorrow):
    from config.celery import app
    from news.admin_status import card, metric, worst
    from news.task_heartbeat import cadence
    names = {'council-recruiter-night': 'Rekruter', 'krs-agent-night': 'Agent KRS',
             'dr-spin-thread-daily': 'Dr. Spin — spinki', 'clinic-daily-messages-day': 'Przekazy dnia',
             'clinic-daily-messages-evening': 'Przekazy wieczorne', 'weekly-report-sunday': 'Raport tygodnia',
             'deleted-posts-3h': 'Strażnik usuniętych wpisów', 'social-publish-day': 'Publikacje social',
             'x-publish-day': 'Publikacje X'}
    pulses = cache.get_many([f'heartbeat:{key}' for key in names])
    rows = []
    for key, label in names.items():
        entry = app.conf.beat_schedule.get(key)
        pulse = pulses.get(f'heartbeat:{key}', {})
        try:
            started = parse_datetime(pulse.get('started_at', ''))
            if started and started.tzinfo is None:
                started = None
        except (ValueError, TypeError):
            started = None
        interval = cadence(entry['schedule']) if entry else None
        stale = bool(started and interval and (now - started).total_seconds() > interval * 2)
        status = 'error' if pulse.get('phase') == 'error' else 'warn' if stale else 'ok' if pulse else 'unknown'
        metrics = [metric('Ostatni przebieg', started), metric('Wynik', pulse.get('result')),
                   metric('Następny termin w harmonogramie', next_run(entry['schedule'], now, started) if entry else None)]
        if key == 'krs-agent-night':
            day = today.date().isoformat()
            values = cache.get_many([f'krs-agent-spent:{day}', f'krs-agent-done:{day}'])
            spent = number(values.get(f'krs-agent-spent:{day}'))
            limit = number(os.environ.get('KRS_DAILY_BUDGET_USD', '0.5'))
            metrics += [metric('Wydatki dziś (USD, cache)', spent), metric('Budżet dzienny (USD)', limit),
                        metric('Pozostały budżet (USD)', max(0, limit - spent) if limit is not None and spent is not None else None),
                        metric('Osoby podjęte dziś (cache)', values.get(f'krs-agent-done:{day}')),
                        metric('Osoby sprawdzone dziś (baza)', PublicFigure.objects.filter(
                            organisations_checked_at__gte=today, organisations_checked_at__lt=tomorrow).count())]
        description = pulse.get('summary', 'Brak zapisanego pulsu. Nie potwierdzono wykonania.')
        if pulse.get('phase') == 'error':
            description = safe_error(description)
        rows.append(card(label, status, description, pulse.get('last_event'), metrics))
    return card('Agenci', worst(rows),
                'Terminy z konfiguracji Celery, nie gwarancja wykonania. Puls jest przechowywany 7 dni; cache może zostać utracone.',
                items=rows)


def storage(now):
    from news.admin_status import card, metric, worst
    rows = []
    db = settings.DATABASES.get('default', {})
    db_path = db.get('NAME') if str(db.get('ENGINE', '')).endswith('sqlite3') and db.get('NAME') != ':memory:' else os.environ.get('PGDATA')
    for label, path in (('Dysk bazy', db_path), ('Dysk mediów', getattr(settings, 'MEDIA_ROOT', None))):
        try:
            if not path or not Path(path).exists():
                raise OSError
            disk = shutil.disk_usage(path)
            state = 'error' if disk.free / disk.total < .05 else 'warn' if disk.free / disk.total < .15 else 'ok'
            rows.append(card(label, state, 'Wolne miejsce na widocznym woluminie; nie rozmiar samych danych.', now,
                             [metric('Wolne (GiB)', round(disk.free / 2**30, 2)), metric('Razem (GiB)', round(disk.total / 2**30, 2)),
                              metric('Wolne (%)', round(disk.free / disk.total * 100, 1))]))
        except (OSError, ValueError, TypeError):
            rows.append(card(label, description='Katalog danych nie jest widoczny w kontenerze API.', metrics=[metric('Wolne (GiB)', None)]))
    models = (Article, Source, ArticleContent, ArchiveJob, OfficialRecord, ParliamentaryVoting,
              PoliticalPost, PoliticalAccount, SpinDiagnosis, ClinicInterview, SocialPost, PublicFigure)
    record_counts = cache.get('admin-status:table-counts:v1')
    if record_counts is None:
        record_counts = {'at': now, 'metrics': [metric(model.__name__, model.objects.count()) for model in models]}
        cache.set('admin-status:table-counts:v1', record_counts, 60)
    rows.append(card('Rekordy tabel', 'ok', 'Dokładne liczniki rekordów z chwili pomiaru; cache do 60 s.',
                     record_counts['at'], record_counts['metrics']))
    latest = None
    try:
        # Single directory only: never recursively walk mounted archive trees.
        with os.scandir('/srv/backups') as files:
            for index, file in enumerate(files):
                if index >= 2000:
                    latest = None  # An incomplete scan cannot establish newest.
                    break
                if file.is_file(follow_symlinks=False) and file.name.endswith(('.sql', '.sql.gz', '.dump', '.backup', '.tar.gz', '.tgz', '.zip')):
                    stamp = file.stat(follow_symlinks=False).st_mtime
                    latest = max(latest, stamp) if latest is not None else stamp
    except OSError:
        latest = None
    at = datetime.fromtimestamp(latest, WARSAW) if latest is not None else None
    rows.append(card('Kopia zapasowa', 'unknown' if at is None else 'warn' if (now - at).total_seconds() > 48 * 3600 else 'ok',
                     'Wiek pliku kopii według mtime w /srv/backups (bez podkatalogów). Nie potwierdza poprawności ani odtwarzalności kopii.',
                     at, [metric('Wiek pliku kopii (h)', round((now - at).total_seconds() / 3600, 1) if at and at <= now else None)]))
    return card('Dysk, baza i kopie', worst(rows), 'Tylko zasoby widoczne lokalnie.', now, items=rows)


def extended_sections(now, today, yesterday, tomorrow):
    from news.admin_status import card
    sections = []
    for title, fn in (
        ('Pobieranie i czytanie', lambda: intake(now, today, yesterday, tomorrow)),
        ('X — pobieranie wpisów', lambda: x_read(now, today, yesterday, tomorrow)),
        ('X — publikacja', lambda: x_publish(today, yesterday, tomorrow)),
        ('YouTube', lambda: youtube(now, today, tomorrow)),
        ('Agenci', lambda: agents(now, today, tomorrow)), ('Dysk, baza i kopie', lambda: storage(now)),
    ):
        try:
            sections.append(fn())
        except Exception:
            sections.append(card(title, description='Nie udało się odczytać stanu; szczegóły w chronionych logach.'))
    return sections


def telemetry_series(today, tomorrow):
    series = []
    for key, label, model, field in (('intake', 'Pobrane materiały', Article, 'scraped_at'),
                                    ('diagnoses', 'Próby diagnoz', SpinDiagnosis, 'diagnosed_at')):
        rows = model.objects.filter(**{f'{field}__gte': today - timedelta(days=6), f'{field}__lt': tomorrow}).order_by().annotate(
            day=TruncDate(field, tzinfo=WARSAW)).values('day').annotate(value=Count('pk'))
        values = {r['day']: r['value'] for r in rows}
        series.append({'key': key, 'label': label, 'points': [
            {'date': (today.date() - timedelta(days=offset)).isoformat(),
             'value': values.get(today.date() - timedelta(days=offset), 0)} for offset in range(6, -1, -1)]})
    return series


def kpis_from_sections(sections):
    result = []
    for key, title, label in (('intake', 'Pobieranie i czytanie', 'Pobrane materiały'),
                              ('x', 'X — pobieranie wpisów', 'Wpisy X'), ('diagnoses', 'Diagnozy', 'Próby diagnoz')):
        section = next((s for s in sections if s['title'] == title), {})
        metrics = {m['label']: m['value'] for m in section.get('metrics', [])}
        result.append({'key': key, 'label': label, 'today': metrics.get('Dziś', 'unknown'), 'yesterday': metrics.get('Wczoraj', 'unknown')})
    return result
