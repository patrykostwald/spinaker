"""Publiczny eksport danych (CSV/JSON) i kanały RSS: wyłącznie to, co jest publiczne na stronie.

Zbiory: diagnozy (te same filtry co lista), osoby publiczne (te same filtry co rejestr), źródła, wskaźniki Kliniki.
Eksport nie zawiera pól wewnętrznych (kolejki, recenzje, konta zespołu) ani treści wpisów z X (tylko adres wpisu).
"""
import csv
import io
import json

from django.conf import settings
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.feedgenerator import Rss201rev2Feed
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from news import clinic

EXPORT_LIMIT = 5000
LICENSE_NOTE = 'Warunki ponownego użycia danych ustalimy przed wersją końcową serwisu.'
SITE = lambda: settings.ACCOUNT_PUBLIC_URL


class ExportAnonThrottle(AnonRateThrottle):
    scope = 'export'


class ExportUserThrottle(UserRateThrottle):
    scope = 'export_user'


def _site(path: str) -> str:
    return f'{SITE()}{path}'


def _cell(value):
    """Wartość komórki CSV; zabezpieczenie przed formułami arkusza (=, +, -, @ na początku tekstu)."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'tak' if value else 'nie'
    text = str(value).replace('\r', ' ').replace('\n', ' ')
    return "'" + text if text[:1] in ('=', '+', '-', '@', '\t') else text


# --- zbiory ---------------------------------------------------------------------------------

def _spins(params):
    from news.clinic_api import spin_rows
    rows, error = spin_rows(params)
    if error is not None:
        raise ValueError(error.data.get('detail', 'Nieprawidłowe filtry.'))
    columns = [('id', 'Numer diagnozy'), ('data_wpisu', 'Data wpisu'), ('obozu', 'Obóz'), ('autor', 'Autor wpisu'), ('konto_x', 'Konto X'),
               ('klub', 'Klub lub partia'), ('werdykt', 'Werdykt'), ('sila_spinu', 'Siła spinu (0-100)'), ('naglowek', 'Nagłówek'),
               ('podsumowanie', 'Podsumowanie'), ('techniki', 'Techniki perswazji'), ('tw_potwierdzone', 'Twierdzenia potwierdzone'),
               ('tw_sprzeczne', 'Twierdzenia sprzeczne ze źródłami'), ('tw_wprowadza_w_blad', 'Twierdzenia wprowadzające w błąd'),
               ('tw_niezweryfikowane', 'Twierdzenia niezweryfikowane'), ('zgodnosc_modeli', 'Zgodność modeli'),
               ('adres_wpisu', 'Adres wpisu'), ('adres_diagnozy', 'Adres diagnozy'), ('data_diagnozy', 'Data diagnozy')]
    out = []
    items = rows if isinstance(rows, list) else list(rows[:EXPORT_LIMIT])
    for start in range(0, min(len(items), EXPORT_LIMIT), 100):
        for card in clinic.cards(items[start:start + 100]):
            scan, post, author = card.get('scan') or {}, card.get('post') or {}, card.get('author') or {}
            claims, council = scan.get('claims') or {}, scan.get('council') or {}
            party = author.get('party') or {}
            out.append({
                'id': card['id'], 'data_wpisu': str(post.get('published_at') or '')[:10], 'obozu': card.get('camp_label', ''),
                'autor': author.get('name', ''), 'konto_x': author.get('handle', ''), 'klub': party.get('short', ''),
                'werdykt': card.get('verdict_label', ''), 'sila_spinu': card.get('intensity'), 'naglowek': card.get('headline', ''),
                'podsumowanie': card.get('summary', ''), 'techniki': '; '.join(card.get('technique_names') or []),
                'tw_potwierdzone': claims.get('supported', 0), 'tw_sprzeczne': claims.get('contradicted', 0),
                'tw_wprowadza_w_blad': claims.get('misleading', 0), 'tw_niezweryfikowane': claims.get('unverified', 0),
                'zgodnosc_modeli': council.get('agreement') or '', 'adres_wpisu': post.get('url', ''),
                'adres_diagnozy': _site(f"/klinika/{card['id']}"), 'data_diagnozy': str(scan.get('diagnosed_at') or '')[:10],
            })
    return columns, out


def _figures(params):
    from news.public_figures import figure_rows, figure_data, figures_with_verified_x
    try:
        ordered, _ = figure_rows(params)
    except ValueError as error:
        raise ValueError(str(error))
    ordered = ordered[:EXPORT_LIMIT]
    with_x = figures_with_verified_x([item['figure'] for item in ordered])
    columns = [('id', 'Numer profilu'), ('nazwa', 'Imię i nazwisko'), ('funkcja', 'Funkcja'), ('instytucja', 'Instytucja'),
               ('status', 'Status funkcji'), ('klub', 'Klub lub partia'), ('izba', 'Izba'), ('liczba_diagnoz', 'Liczba diagnoz Dr. Spina'),
               ('konto_x_potwierdzone', 'Konto X potwierdzone'), ('zrodlo_funkcji', 'Źródło funkcji'),
               ('sprawdzono', 'Data sprawdzenia źródła'), ('adres_profilu', 'Adres profilu')]
    from news.public_figures import CHAMBERS
    out = []
    for item in ordered:
        data = figure_data(item['figure'])
        out.append({
            'id': data['id'], 'nazwa': data['name'], 'funkcja': data['role_title'], 'instytucja': data['organisation'],
            'status': 'obecna' if data['status'] == 'current' else 'była', 'klub': (item['party'] or {}).get('short', ''),
            'izba': CHAMBERS.get(item['chamber'], ''), 'liczba_diagnoz': item['diagnoses'],
            'konto_x_potwierdzone': data['id'] in with_x, 'zrodlo_funkcji': data['evidence_url'],
            'sprawdzono': str(data['source_checked_at'] or '')[:10], 'adres_profilu': _site(f"/osoby-publiczne/{data['id']}"),
        })
    return columns, out


def _sources(params):
    from news.models import Source, SourceAccessInstruction
    from news.serializers import SourceSerializer
    approved = set(SourceAccessInstruction.objects.filter(status='approved', daily_request_cap__gt=0).values_list('source_id', flat=True))
    rows = SourceSerializer(Source.objects.exclude(catalog_stage='excluded').order_by('name', 'pk'), many=True, context={'approved_ids': approved}).data
    query = params.get('q', '').strip().casefold()
    status = params.get('status', '')
    if query:
        rows = [row for row in rows if query in f"{row['name']} {row['url']}".casefold()]
    if status == 'active':
        rows = [row for row in rows if row['is_active']]
    elif status == 'pending':
        rows = [row for row in rows if row['access'] != 'approved']
    groups = {'top': 'Wybrane media', 'media': 'Media', 'publiczne': 'Instytucje publiczne'}
    columns = [('nazwa', 'Nazwa źródła'), ('adres', 'Adres'), ('grupa', 'Grupa'), ('aktywne', 'Aktywne'), ('zgoda', 'Zgoda lub dane publiczne'),
               ('konto_x', 'Konto X'), ('youtube', 'Kanał YouTube')]
    rows = rows[:EXPORT_LIMIT]
    return columns, [{'nazwa': row['name'], 'adres': row['url'], 'grupa': groups.get(row['portal_group'], row['portal_group']),
                      'aktywne': row['is_active'], 'zgoda': row['access'] == 'approved', 'konto_x': row['x_handle'] or '',
                      'youtube': row['youtube_url'] or ''} for row in rows]


def _indicators(params):
    from news.clinic_stats import stats_data
    data = stats_data()
    camps = {'government': 'Rządzący', 'opposition': 'Opozycja'}
    columns = [('data', 'Data'), ('obozu', 'Obóz'), ('przeczytane', 'Wpisy przeczytane'), ('ocenione_wstepnie', 'Wpisy ocenione wstępnie'),
               ('zdiagnozowane', 'Diagnozy'), ('spiny', 'Diagnozy ze spinem'), ('wystarczajaca_proba', 'Wystarczająca próba (min. 10)')]
    out = []
    for day in data.get('daily', []):
        for camp, label in camps.items():
            row = (day.get('by_camp') or {}).get(camp) or {}
            out.append({'data': day['date'], 'obozu': label, 'przeczytane': row.get('read', 0), 'ocenione_wstepnie': row.get('screened', 0),
                        'zdiagnozowane': row.get('diagnosed', 0), 'spiny': row.get('spins', 0), 'wystarczajaca_proba': row.get('enough_data', False)})
    return columns, out


DATASETS = {'diagnozy': _spins, 'osoby': _figures, 'zrodla': _sources, 'wskazniki': _indicators}
FILTER_KEYS = {'diagnozy': ('camp', 'verdict', 'account', 'intensity_min', 'intensity_max', 'date_from', 'date_to', 'sort', 'technique', 'q', 'party'),
               'osoby': ('q', 'role_category', 'status', 'party', 'chamber', 'sort'), 'zrodla': ('q', 'status'), 'wskazniki': ()}


@extend_schema(summary='Eksport danych publicznych (CSV albo JSON) z filtrami jak na liście', tags=['dane'], responses=OpenApiTypes.BINARY,
               parameters=[OpenApiParameter('dataset', str, OpenApiParameter.PATH, enum=list(DATASETS)),
                           OpenApiParameter('ext', str, OpenApiParameter.PATH, enum=['csv', 'json'])])
@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([ExportAnonThrottle, ExportUserThrottle])
def export_dataset(request, dataset, ext):
    if dataset not in DATASETS or ext not in ('csv', 'json'):
        raise Http404
    params = {key: request.query_params.get(key, '') for key in FILTER_KEYS[dataset] if request.query_params.get(key)}
    try:
        columns, rows = DATASETS[dataset](params)
    except ValueError as error:
        return Response({'detail': str(error)}, status=400)
    stamp = timezone.now()
    name = f'spin-clinic-{dataset}-{stamp:%Y-%m-%d}'
    if ext == 'json':
        body = json.dumps({'zbior': dataset, 'wygenerowano': stamp.isoformat(), 'liczba': len(rows), 'filtry': params,
                           'licencja': LICENSE_NOTE, 'zrodlo': _site('/dane'), 'kolumny': {key: header for key, header in columns},
                           'dane': rows}, ensure_ascii=False, indent=1, default=str)
        response = HttpResponse(body, content_type='application/json; charset=utf-8')
    else:
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';', lineterminator='\r\n')
        writer.writerow([header for _, header in columns])
        for row in rows:
            writer.writerow([_cell(row.get(key)) for key, _ in columns])
        response = HttpResponse('﻿' + buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{name}.{ext}"'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Row-Limit'] = str(EXPORT_LIMIT)
    return response


# --- RSS ------------------------------------------------------------------------------------

AI_NOTE = 'Analiza AI, nie rozstrzygnięcie redakcji.'


def _feed_diagnoses():
    rows = clinic.cards(clinic.published_diagnoses().order_by('-diagnosed_at', '-pk')[:30])
    for card in rows:
        author = card.get('author') or {}
        party = (author.get('party') or {}).get('short')
        yield {'title': card.get('headline') or f"Diagnoza #{card['id']}", 'link': _site(f"/klinika/{card['id']}"),
               'description': f"{AI_NOTE} {card.get('verdict_label', '')}, siła spinu {card.get('intensity')}/100. {card.get('summary', '')} "
                              f"Autor wpisu: {author.get('name', '')}{f' ({party})' if party else ''}.".strip(),
               'pubdate': _parse((card.get('scan') or {}).get('diagnosed_at'))}


def _feed_messages():
    from news.clinic_models import ClinicDailyMessage
    labels = {'government': 'obóz rządzący', 'opposition': 'opozycja'}
    for row in ClinicDailyMessage.objects.filter(status='approved', camp__in=clinic.CAMPS).order_by('-day', 'camp')[:30]:
        yield {'title': f'Przekaz dnia {row.day:%d.%m.%Y}: {labels.get(row.camp, row.camp)}', 'link': _site(f'/klinika/przekazy/{row.day}'),
               'unique_id': _site(f'/klinika/przekazy/{row.day}#{row.camp}'),
               'description': f'{AI_NOTE} {row.message}', 'pubdate': row.reviewed_at or row.created_at}


def _feed_reports():
    from news.clinic_models import WeeklyReport
    for row in WeeklyReport.objects.all()[:20]:
        yield {'title': f'Raport tygodnia {row.week_start:%d.%m} – {row.week_end:%d.%m.%Y}', 'link': _site(f'/klinika/raporty/{row.week_end}'),
               'description': f'{AI_NOTE} {row.summary}'.strip(), 'pubdate': row.created_at}


def _parse(value):
    from django.utils.dateparse import parse_datetime
    if hasattr(value, 'isoformat'):
        return value
    return parse_datetime(value) if isinstance(value, str) and value else timezone.now()


FEEDS = {
    'diagnozy': ('spin.clinic: najnowsze diagnozy', '/klinika/diagnozy', 'Opublikowane diagnozy wpisów polityków (analiza AI).', _feed_diagnoses),
    'przekazy': ('spin.clinic: przekazy dnia', '/klinika/przekazy', 'Przekazy dnia obozu rządzącego i opozycji (analiza AI).', _feed_messages),
    'raporty': ('spin.clinic: raporty tygodnia', '/klinika/raporty', 'Cotygodniowe zestawienia danych Kliniki (analiza AI).', _feed_reports),
}


@extend_schema(summary='Kanał RSS: diagnozy, przekazy dnia albo raporty tygodnia', tags=['dane'], responses=OpenApiTypes.BINARY,
               parameters=[OpenApiParameter('name', str, OpenApiParameter.PATH, enum=list(FEEDS))])
@api_view(['GET'])
@permission_classes([AllowAny])
def rss_feed(request, name):
    if name not in FEEDS:
        raise Http404
    title, path, description, items = FEEDS[name]
    feed = Rss201rev2Feed(title=title, link=_site(path), description=description, language='pl',
                          feed_url=_site(f'/api/feeds/{name}.xml'))
    for item in items():
        feed.add_item(title=item['title'], link=item['link'], description=item['description'], pubdate=item['pubdate'],
                      unique_id=item.get('unique_id') or item['link'])
    response = HttpResponse(feed.writeString('utf-8'), content_type='application/rss+xml; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=300'
    return response
