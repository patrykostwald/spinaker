"""Koszt filmów i równa miara w prywatnych raportach Kliniki."""
import logging
from collections import Counter
from contextvars import ContextVar
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from news.clinic_ai import GEMINI_SPEND_KEY
from news.models import RepairerState
from news.political_models import PoliticalPost

logger = logging.getLogger(__name__)
CAMPS = {'government': 'Rządzący', 'opposition': 'Opozycja'}
STATUSES = ('full', 'partial', 'thumbnail', 'unseen')
video_camp = ContextVar('clinic_video_camp', default='unassigned')
DAY_KEY = 'clinic-video-cost:'


def _cached_cost(day):
    return (cache.get(GEMINI_SPEND_KEY.format(day=day.isoformat(), task='video')) or {}).get('usd', 0)


def record_cost(cost, day):
    """Trwały licznik z blokadą wiersza, także dla ponowień i nieudanych diagnoz."""
    key = DAY_KEY + day.isoformat()
    # Przy pierwszym zapisie zachowujemy wcześniejszy koszt z licznika Gemini.
    with transaction.atomic():
        state, _ = RepairerState.objects.get_or_create(
            key=key, defaults={'data': {'unassigned': str(_cached_cost(day))}})
        state = RepairerState.objects.select_for_update().get(pk=state.pk)
        camp = video_camp.get()
        camp = camp if camp in CAMPS else 'unassigned'
        data = dict(state.data)
        data[camp] = str(Decimal(str(data.get(camp, 0))) + Decimal(str(cost)))
        state.data = data
        state.save(update_fields=['data'])


def costs(start, end):
    totals = {camp: Decimal(0) for camp in (*CAMPS, 'unassigned')}
    rows = {row.key: row.data for row in RepairerState.objects.filter(
        key__gte=DAY_KEY + start.isoformat(), key__lte=DAY_KEY + end.isoformat())}
    day = start
    while day <= end:
        data = rows.get(DAY_KEY + day.isoformat())
        if data is None:
            data = {'unassigned': _cached_cost(day)}
        for camp in totals:
            totals[camp] += Decimal(str(data.get(camp, 0)))
        day += timedelta(days=1)
    return totals


def monthly_cost(today=None):
    today = today or timezone.localdate()
    usd = sum(costs(today.replace(day=1), today).values())
    return {'month': today.strftime('%Y-%m'), 'usd': float(usd),
            'pln': float(usd * Decimal(str(settings.CLINIC_VIDEO_USD_PLN))),
            'threshold_pln': settings.CLINIC_VIDEO_MONTHLY_ALERT_PLN,
            'usd_pln': settings.CLINIC_VIDEO_USD_PLN}


def _empty():
    return {'posts': 0, 'videos': 0, **dict.fromkeys(STATUSES, 0), 'reasons': Counter()}


def _outcomes(post):
    diagnosis = getattr(post, 'spin_diagnosis', None)
    usage = diagnosis.usage if diagnosis else {}
    usage = usage or {}
    saved = ((usage.get('snapshot') or {}).get('usage') or {}).get('videos')
    saved = saved if saved is not None else usage.get('videos', [])
    saved = [v for v in saved if isinstance(v, dict)]
    media = [v for v in post.media or [] if isinstance(v, dict) and v.get('type') in ('video', 'animated_gif')]
    # Zachowujemy wyniki także po usunięciu mediów niedostępnego wpisu.
    for index in range(1, max(len(media), len(saved)) + 1):
        item = media[index - 1] if index <= len(media) else {}
        result = next((v for v in saved if item.get('media_key') and v.get('media_key') == item['media_key']), None)
        result = result or next((v for v in saved if v.get('index') == index), None)
        if result and result.get('status') in STATUSES:
            yield result['status'], result.get('limitation') or 'brak zapisanego powodu'
        else:
            reason = ('wpis niedostępny' if not post.available else
                      'brak diagnozy' if diagnosis is None else
                      f'brak wyniku oglądania: {diagnosis.get_status_display()}')
            yield 'unseen', reason


def _finish(rows, spending):
    result = {}
    for camp, label in CAMPS.items():
        row = rows[camp]
        # Miniatura nie oznacza obejrzenia filmu ani odsłuchania wypowiedzi.
        not_watched = row['unseen'] + row['thumbnail']
        result[camp] = {**row, 'label': label, 'reasons': dict(row['reasons']),
                        'unwatched_share': not_watched / row['videos'] if row['videos'] else None,
                        'cost_usd': float(spending[camp]),
                        'cost_pln': float(spending[camp] * Decimal(str(settings.CLINIC_VIDEO_USD_PLN)))}
    return result


def build_report(today=None):
    """Wpisy według lokalnej daty publikacji; koszty według dnia wywołania Gemini."""
    today = today or timezone.localdate()
    end, start = today - timedelta(days=1), today - timedelta(days=7)
    daily = {start + timedelta(days=n): {camp: _empty() for camp in CAMPS} for n in range(7)}
    posts = (PoliticalPost.objects.filter(published_at__date__gte=start, published_at__date__lte=end,
                                         camp_at_collection__in=CAMPS)
             .select_related('spin_diagnosis').order_by())
    for post in posts.iterator():
        outcomes = list(_outcomes(post))
        if not outcomes:
            continue
        row = daily[timezone.localdate(post.published_at)][post.camp_at_collection]
        row['posts'] += 1
        row['videos'] += len(outcomes)
        for status, reason in outcomes:
            row[status] += 1
            if status in ('unseen', 'thumbnail'):
                row['reasons'][reason] += 1
    totals = {camp: _empty() for camp in CAMPS}
    for rows in daily.values():
        for camp, row in rows.items():
            for key in ('posts', 'videos', *STATUSES):
                totals[camp][key] += row[key]
            totals[camp]['reasons'].update(row['reasons'])
    worse = []
    for offset in (2, 1, 0):
        rows = daily[end - timedelta(days=offset)]
        gov, opp = rows['government'], rows['opposition']
        if not gov['videos'] or not opp['videos']:
            worse.append(None)
            continue
        # Porównanie całkowitoliczbowe: dokładnie 10 pp nie uruchamia ostrzeżenia.
        diff = ((gov['unseen'] + gov['thumbnail']) * opp['videos']
                - (opp['unseen'] + opp['thumbnail']) * gov['videos'])
        worse.append(('government' if diff > 0 else 'opposition')
                     if abs(diff) * 10 > gov['videos'] * opp['videos'] else None)
    warning = ''
    if worse[0] and len(set(worse)) == 1:
        warning = (f'UWAGA: {CAMPS[worse[0]]}: udział nieobejrzanych filmów wyższy o ponad 10 pp '
                   'przez 3 kolejne dni. Sprawdź, czy limit zaburza równą miarę.')
    periods = []
    for label, first, rows in [('Wczoraj', end, daily[end]), ('Ostatnie 7 dni', start, totals)]:
        spending = costs(first, end)
        periods.append({'label': label, 'start': first.isoformat(), 'end': end.isoformat(),
                        'camps': _finish(rows, spending), 'unassigned_usd': float(spending['unassigned'])})
    return {'as_of': today.isoformat(), 'periods': periods, 'warning': warning, 'monthly': monthly_cost(today)}


def format_report(report):
    month = report['monthly']
    lines = [f"Filmy: {month['month']}, koszt {month['pln']:.2f} PLN ({month['usd']:.4f} USD).",
             f"Próg alertu: {month['threshold_pln']:.2f} PLN; kurs: {month['usd_pln']} PLN/USD.",
             'Wpisy według daty publikacji, zakres oglądania według ostatniego zapisanego wyniku.',
             'Koszty według daty wywołania, łącznie z ponowieniami. Miniatura liczy się jako film nieobejrzany.']
    for period in report['periods']:
        lines.append(f"\n{period['label']} ({period['start']} do {period['end']}):")
        for row in period['camps'].values():
            share = f"{row['unwatched_share']:.1%}" if row['unwatched_share'] is not None else 'brak filmów'
            lines.append(f"{row['label']}: wpisy {row['posts']}, filmy {row['videos']}, całe {row['full']}, "
                         f"fragment {row['partial']}, miniatura {row['thumbnail']}, nieobejrzane {row['unseen']}; "
                         f"udział bez obejrzenia {share}; koszt {row['cost_pln']:.2f} PLN ({row['cost_usd']:.4f} USD).")
            lines.extend(f'  {reason}: {count}' for reason, count in sorted(row['reasons'].items()))
        lines.append(f"Koszt bez przypisania do strony: {period['unassigned_usd']:.4f} USD.")
    if report['warning']:
        lines.extend(['', report['warning']])
    return '\n'.join(lines)


def notify(*, daily=False, today=None):
    """Wspólna poczta dla kosztu i równowagi; trwała deduplikacja po udanej wysyłce."""
    from news.council_recruiter import _owner_email
    from news.social_publish import _mail

    today = today or timezone.localdate()
    month = monthly_cost(today)
    key = 'clinic-video-alert:' + month['month']
    with transaction.atomic():
        state, _ = RepairerState.objects.get_or_create(key=key)
        state = RepairerState.objects.select_for_update().get(pk=state.pk)
        data = dict(state.data)
        alert = month['pln'] > month['threshold_pln'] and not data.get('cost_sent')
        daily_due = daily and data.get('daily_sent') != today.isoformat()
        if not alert and not daily_due:
            return False
        report = build_report(today)
        # Codzienne zestawienie widać w panelu; mail tylko przy alercie kosztu albo ostrzeżeniu o nierównej mierze (właściciel 3.10).
        if not alert and not report['warning']:
            return False
        body = format_report(report)
        subject = 'spin.clinic · Filmy: zestawienie'
        if alert:
            subject += ' i alert kosztu'
            body = 'Przekroczono miesięczny próg kosztu filmów. Oglądanie trwa nadal.\n\n' + body
        try:
            sent = _mail(_owner_email(), subject, body, important=True)
        except Exception:
            logger.warning('Nie udało się wysłać raportu filmów', exc_info=True)
            return False
        if sent:
            if alert:
                data['cost_sent'] = timezone.now().isoformat()
            if daily_due:
                data['daily_sent'] = today.isoformat()
            state.data = data
            state.save(update_fields=['data'])
        return sent
