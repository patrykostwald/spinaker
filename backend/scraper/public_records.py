"""Private, bounded public-record collection with durable checkpoints.

Every request uses the existing reviewed access card, host gateway and daily
budget, plus an independent per-collector budget. No Article writes or AI.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
import json
import os
import re
from time import sleep
from urllib.parse import quote, urlencode, urlsplit, parse_qs
from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from news.models import Source, OfficialRecord, PublicFigure, PublicFigureRole
from news.public_records_models import PublicRecord, PublicRecordPerson, PublicCollectionState, PublicCollectionJob
from news.repairer import flag
from scraper.access_gate import AccessDenied, approved_instruction
from scraper.official import API
from scraper.utils import fetch_feed, HostRateLimited
from scraper import public_record_parsers as parsers

TERM = 10
START = date(2023, 11, 13)
SEJM = API + '/sejm/term10'
MSWIA = 'https://www.gov.pl/web/mswia/dzialalnosc-lobbingowa'
LOBBY = 'https://www.sejm.gov.pl/sejm10.nsf/page.xsp/lobbing'
PKW = 'https://pkw.gov.pl/finansowanie-polityki/'
KRS_API = 'https://api-krs.ms.gov.pl/api/krs'
TED_SEARCH = 'https://api.ted.europa.eu/v3/notices/search'
TR_EXPORT = 'https://ec.europa.eu/transparencyregister/public/files/ODP/download/XML/latest'
# Sejm term-scoped sources (term field, START as the earliest date).
SEJM_SOURCES = {'votes', 'statements', 'interpellations', 'questions', 'consultations', 'assets', 'processes', 'committees',
                'videos'}
# Europoseł w PublicRecordPerson: kadencja 0 = identyfikator Parlamentu Europejskiego (ParliamentaryRosterEntry source='ep').
EP_TERM = 0
# Reklamy polityczne w UE: Meta zakończyła je 6.10.2025 (rozporządzenie TTPA) - zbieramy tylko archiwum sprzed tej daty.
META_ADS_ARCHIVE_END = date(2025, 10, 5)
# Hosts outside the Sejm API: (host, allowed path prefixes, catalogue root, channel).
EXTERNAL = {
    'krs_changes': ('api-krs.ms.gov.pl', ('/api/krs/Biuletyn/', '/api/krs/OdpisAktualny/'), 'https://api-krs.ms.gov.pl', 'api'),
    'ted': ('api.ted.europa.eu', ('/v3/notices/search',), 'https://api.ted.europa.eu', 'api'),
    'eu_transparency': ('ec.europa.eu', ('/transparencyregister/public/files/ODP/download/XML/',),
                        'https://ec.europa.eu/transparencyregister', 'export'),
}
# Zabezpieczenie przed botami (Imperva/Incapsula na www.sejm.gov.pl i orka.sejm.gov.pl, sprawdzone 7.10): pętla 302 do
# tego samego adresu (ciasteczko + JavaScript) albo strona wyzwania. Nie obchodzimy go: źródło staje z powodem
# 'bot_protection' i próbuje najwyżej raz na PUBLIC_RECORDS_<ŹRÓDŁO>_BOT_WALL_PAUSE_HOURS (domyślnie 24 h).
BOT_WALL = 'bot_protection'
# Zadania pomocnicze: ściana przy nich nie zatrzymuje źródła, tylko oznacza kontrolę jako niewykonaną.
OPTIONAL_WALL_KINDS = {'office_pdf': 'PDF Kancelarii Sejmu niedostępny automatycznie (zabezpieczenie strony przed botami)'}
TED_FIELDS = ['publication-number', 'publication-date', 'notice-type', 'buyer-name', 'buyer-country', 'notice-title',
              'classification-cpv', 'total-value', 'total-value-cur', 'winner-name', 'winner-identifier', 'winner-country']


@dataclass(frozen=True)
class Spec:
    title: str
    cap: int = 100
    refresh_hours: int = 24
    # First cycle without --since: look back N days instead of START (0 = START).
    lookback_days: int = 0
    # Later cycles re-read this many days before the previous cycle start.
    overlap_days: int = 7

    def flag(self, source):
        return 'PUBLIC_RECORDS_' + source.upper() + '_ENABLED'


SOURCES = {
    'votes': Spec('Głosowania imienne', 200, 1),
    'statements': Spec('Wypowiedzi Sejmu', 200, 6),
    'interpellations': Spec('Interpelacje', 100, 6),
    'questions': Spec('Zapytania poselskie', 100, 6),
    'lobby_mswia': Spec('Rejestr lobbingu MSWiA', 10, 168),
    'lobby_sejm': Spec('Lobbing w Sejmie', 10, 168),
    'consultations': Spec('Tabele konsultacji OSR', 30, 24),
    'pkw': Spec('Finanse partii i komitetów PKW', 40, 168),
    'assets': Spec('Indeks oświadczeń majątkowych', 60, 168),
    'meta_ads': Spec('Archiwum reklam politycznych Meta (do 5.10.2025, TTPA)', 30, 24),
    'processes': Spec('Procesy legislacyjne Sejmu', 150, 6),
    'committees': Spec('Komisje sejmowe i ich posiedzenia', 100, 24),
    'krs_changes': Spec('Zmiany w KRS obserwowanych podmiotów', 60, 24, lookback_days=3, overlap_days=2),
    'ted': Spec('Ogłoszenia TED zamawiających z Polski', 60, 24, lookback_days=14, overlap_days=2),
    'eu_transparency': Spec('Rejestr przejrzystości UE (Polska)', 2, 168),
    # Raport źródeł 6.10 (tydzień 1-2), kod w scraper.nowe_zrodla
    'videos': Spec('Transmisje wideo Sejmu (sala i komisje)', 120, 6, lookback_days=14, overlap_days=3),
    'howtheyvote': Spec('Głosowania europosłów z Polski (HowTheyVote.eu)', 300, 24, lookback_days=45, overlap_days=7),
    'wikidata': Spec('Tożsamości osób publicznych (Wikidata)', 4, 168),
    'kohesio': Spec('Fundusze UE 2014-2020 w Polsce (Kohesio)', 130, 168),
    'fts': Spec('Budżet UE - beneficjenci z Polski (FTS)', 3, 720),
    'integrity_watch': Spec('Dochody i spotkania europosłów (Integrity Watch EU)', 4, 168),
    'mileage': Spec('Kilometrówki i biura posłów (jakglosuja.pl)', 150, 720),
}
NEW_SOURCES = {'videos', 'howtheyvote', 'wikidata', 'kohesio', 'fts', 'integrity_watch', 'mileage'}


class BotWall(AccessDenied):
    """Host odpowiada zabezpieczeniem przed botami zamiast treści; nie obchodzimy go."""

    def __init__(self):
        super().__init__(BOT_WALL)


def setting_int(source, suffix, default, maximum):
    value = int(os.environ.get(f'PUBLIC_RECORDS_{source.upper()}_{suffix}', default))
    if value < 1 or value > maximum:
        raise ValueError('invalid_collector_limit')
    return value


def enqueue(state, url, kind, context=None):
    url = parsers.public_url(url)
    context = context or {}
    key = kind + '\n' + url
    if 'body' in context:  # POST pages share one URL; the body is part of identity.
        key += '\n' + json.dumps(context['body'], sort_keys=True)
    identity = sha256(key.encode()).hexdigest()
    job, created = PublicCollectionJob.objects.get_or_create(state=state, identity=identity,
        defaults={'url': url, 'kind': kind, 'context': context})
    return job, created


def figure_for(term, mp_id):
    if term == EP_TERM:
        return figure_for_ep(mp_id)
    # Require a term-scoped roster identity or a term-scoped role. A bare
    # import_key cannot establish the term and a surname never establishes ID.
    figures = set(PublicFigure.objects.filter(parliamentary_roster_entry__source='sejm',
        parliamentary_roster_entry__term=term,
        parliamentary_roster_entry__external_id__in=[str(mp_id), f'{mp_id:03d}']).values_list('pk', flat=True))
    figures.update(PublicFigureRole.objects.filter(import_key=f'sejm-term:{term}:{mp_id}')
                   .values_list('public_figure_id', flat=True))
    return next(iter(figures)) if len(figures) == 1 else None


def figure_for_ep(ep_id):
    """Europoseł: wyłącznie oficjalny identyfikator PE z rosteru (ParliamentaryRosterEntry source='ep'), nigdy nazwisko."""
    figures = set(PublicFigure.objects.filter(parliamentary_roster_entry__source='ep',
        parliamentary_roster_entry__external_id=str(ep_id)).values_list('pk', flat=True))
    figures.update(PublicFigureRole.objects.filter(import_key=f'ep:{ep_id}').values_list('public_figure_id', flat=True))
    return next(iter(figures)) if len(figures) == 1 else None


def save(job, raw, kind, external_id, *, data=None, title='', text='', source_url=None,
         date_value=None, people=(), print_number='', receipt=None, persons=()):
    defaults = dict(data=data or {}, title=title, text=text,
        term=TERM if job.state.source in SEJM_SOURCES else None,
        source_url=source_url or job.url, response_url=job.url, response_sha256=sha256(raw).hexdigest(),
        fetched_at=timezone.now(), date=parsers.day(date_value), print_number=print_number, fetch_attempt=receipt)
    defaults['official_print'] = (OfficialRecord.objects.filter(provider='sejm',
        external_id=f'print/{TERM}/{print_number}').first() if print_number else None)
    record, _ = PublicRecord.objects.update_or_create(source=job.state.source, kind=kind,
        external_id=str(external_id), defaults=defaults)
    # people: posłowie X kadencji; persons: pary (kadencja, identyfikator), w tym (EP_TERM, id PE) dla europosłów.
    pairs = {(TERM, int(i)) for i in people if i and int(i) > 0}
    pairs.update((int(t), int(i)) for t, i in persons if i and int(i) > 0)
    keep = Q(pk__in=[])
    for term, mp_id in pairs:
        keep |= Q(term=term, mp_id=mp_id)
    record.people.exclude(keep).delete()
    for term, mp_id in sorted(pairs):
        PublicRecordPerson.objects.update_or_create(record=record, term=term, mp_id=mp_id,
            defaults={'figure_id': figure_for(term, mp_id)})
    return record


def _json(raw, expected):
    result = json.loads(raw)
    if not isinstance(result, expected):
        raise ValueError('unexpected_response_shape')
    return result


def page_url(base, context, offset=0):
    return base + '?' + urlencode({**context, 'offset': offset, 'limit': 20})


def seed(state, since, incremental=False, backfill=False):
    source = state.source
    if source in NEW_SOURCES:
        from scraper import nowe_zrodla
        return nowe_zrodla.seed(state, since, incremental=incremental, backfill=backfill)
    if backfill and source in {'krs_changes', 'ted'}:
        from scraper.zasil_baze import seed_history
        if seed_history(state, since):
            return
    context = {'since': since.isoformat()}
    if source == 'votes':
        filters = {'dateFrom': since.isoformat(), 'dateTo': timezone.localdate().isoformat()}
        enqueue(state, page_url(SEJM + '/votings/search', filters), 'vote_index', {'filters': filters, 'offset': 0})
    elif source in {'interpellations', 'questions'}:
        resource = 'interpellations' if source == 'interpellations' else 'writtenQuestions'
        filters = {'sort_by': 'num', ('modifiedSince' if incremental else 'since'): since.isoformat()}
        enqueue(state, page_url(SEJM + '/' + resource, filters), 'question_index',
                {'resource': resource, 'filters': filters, 'offset': 0})
    elif source == 'statements':
        enqueue(state, SEJM + '/proceedings', 'proceedings', context)
    elif source == 'assets':
        enqueue(state, SEJM + '/MP', 'members', context)
    elif source == 'consultations':
        enqueue(state, SEJM + '/prints', 'prints', context)
    elif source == 'lobby_mswia':
        enqueue(state, MSWIA, 'mswia_index', context)
    elif source == 'lobby_sejm':
        enqueue(state, LOBBY, 'lobby_index', context)
    elif source == 'pkw':
        for part in ('finansowanie-partii-politycznych', 'finansowanie-kampanii-wyborczych'):
            enqueue(state, PKW + part, 'pkw_page', {**context, 'depth': 0})
    elif source == 'processes':
        filters = {'modifiedSince': since.isoformat() + 'T00:00:00', 'sort': 'lastModif'}
        enqueue(state, page_url(SEJM + '/processes', filters), 'process_index', {'filters': filters, 'offset': 0})
    elif source == 'committees':
        enqueue(state, SEJM + '/committees', 'committee_index', context)
    elif source == 'krs_changes':
        from news.political_models import RegisteredOrganisation
        if not RegisteredOrganisation.objects.filter(archived=False).exists():
            return  # Only companies we already track; nothing to watch yet.
        today = timezone.localdate()
        first = max(since, today - timedelta(days=14))
        for offset in range((today - first).days + 1):
            day_value = (first + timedelta(days=offset)).isoformat()
            enqueue(state, f'{KRS_API}/Biuletyn/{day_value}', 'krs_bulletin', {'day': day_value})
    elif source == 'ted':
        body = {'query': f"buyer-country=POL AND publication-date>={since:%Y%m%d}", 'fields': TED_FIELDS,
                'limit': 100, 'page': 1, 'paginationMode': 'PAGE_NUMBER', 'scope': 'ALL'}
        enqueue(state, TED_SEARCH, 'ted_page', {'body': body})
    elif source == 'eu_transparency':
        enqueue(state, TR_EXPORT, 'tr_export', context)
    elif source == 'meta_ads':
        version = os.environ.get('META_AD_LIBRARY_API_VERSION', '')
        if not re.fullmatch(r'v\d+\.0', version):
            raise ValueError('meta_api_version_required')
        pages = [p.strip() for p in os.environ.get('META_AD_LIBRARY_PAGE_IDS', '').split(',') if p.strip()]
        if not pages or any(not p.isdigit() for p in pages) or len(pages) > 100:
            raise ValueError('meta_page_ids_required')
        # Od 6.10.2025 Meta nie emituje reklam politycznych w UE (TTPA): tylko archiwum do META_ADS_ARCHIVE_END.
        until = min(timezone.localdate(), META_ADS_ARCHIVE_END)
        if since > until:
            return
        filters = {'ad_type': 'POLITICAL_AND_ISSUE_ADS', 'ad_reached_countries': '["PL"]',
            'ad_active_status': 'ALL',
            'ad_delivery_date_min': since.isoformat(), 'ad_delivery_date_max': until.isoformat(),
            'fields': 'id,page_id,page_name,bylines,currency,spend,impressions,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,delivery_by_region,ad_creative_bodies',
            'limit': 20}
        base = f'https://graph.facebook.com/{version}/ads_archive'
        # The documented API accepts at most ten Page IDs per query.
        for offset in range(0, len(pages), 10):
            batch = {**filters, 'search_page_ids': json.dumps(pages[offset:offset + 10])}
            enqueue(state, base + '?' + urlencode(batch), 'meta_page', {'base': base, 'filters': batch})


def source_access(job):
    p = urlsplit(job.url)
    source = job.state.source
    api = p.hostname == 'api.sejm.gov.pl' and p.path.startswith('/sejm/term10/')
    html_sejm = p.hostname == 'www.sejm.gov.pl' and (
        (source == 'assets' and p.path.lower() == '/sejm10.nsf/posel.xsp') or
        (source == 'lobby_sejm' and (p.path == '/sejm10.nsf/page.xsp/lobbing' or
         p.path == '/sejm10.nsf/lobbing_osoby_tab.xsp')))
    mswia = source == 'lobby_mswia' and p.hostname == 'www.gov.pl' and (
        job.url == MSWIA or p.path.startswith('/attachment/'))
    pkw = source == 'pkw' and p.hostname == 'pkw.gov.pl' and (
        p.path.startswith('/finansowanie-polityki/') or p.path.startswith('/uploaded_files/'))
    meta = source == 'meta_ads' and p.hostname == 'graph.facebook.com' and re.fullmatch(r'/v\d+\.0/ads_archive', p.path)
    external = EXTERNAL.get(source)
    if source in NEW_SOURCES and source != 'videos':
        from scraper.nowe_zrodla import HOSTS
        external = next((h for h in HOSTS[source] if p.hostname == h[0] and p.path.startswith(h[1])), HOSTS[source][0])
    other = bool(external) and p.hostname == external[0] and p.path.startswith(external[1])
    if external:
        api = False  # A new external collector never borrows the Sejm card.
    if not (api or html_sejm or mswia or pkw or meta or other) or p.scheme != 'https':
        raise AccessDenied('collector_url_out_of_scope')
    root = API + '/sejm' if api else ('https://www.gov.pl/web/mswia' if mswia else
            'https://graph.facebook.com' if meta else external[2] if other else 'https://' + p.hostname)
    provider = Source.objects.filter(url=root).first()
    channel = external[3] if other else 'api' if api or meta else 'html'
    instruction = approved_instruction(provider, channel, job.url)
    if instruction is None:
        raise AccessDenied('no_approved_instruction')
    if job.kind in {'statement', 'osr_text', 'register_pdf', 'meta_page', 'committee_transcript'} and instruction.allowed_scope not in {'content', 'snapshot'}:
        raise AccessDenied('content_scope_required')
    return provider, instruction


def fetch(job, token, backfill=None):
    """backfill ('noc' / 'resztka'): zasilanie bazy z osobnym limitem nocnym (scraper.zasil_baze), bez zjadania
    dziennego limitu zwykłego zbieracza; karta dostępu i odstęp hosta obowiązują tak samo."""
    source = job.state.source
    spec = SOURCES[source]
    if not flag(spec.flag(source), False):
        raise AccessDenied('collector_disabled')
    provider, instruction = source_access(job)
    now = timezone.now()
    with transaction.atomic():
        state = PublicCollectionState.objects.select_for_update().get(pk=job.state_id)
        if state.lease_token != token or state.lease_until <= now:
            raise AccessDenied('collector_lease_lost')
        if state.budget_day != timezone.localdate():
            state.budget_day, state.requests_today = timezone.localdate(), 0
        if not backfill and state.requests_today >= setting_int(source, 'DAILY_CAP', spec.cap, 10000):
            raise HostRateLimited(86400)
        if state.next_request_at and state.next_request_at > now:
            raise HostRateLimited((state.next_request_at - now).total_seconds())
        if backfill:
            from scraper.zasil_baze import reserve
            if not reserve(source, backfill):
                raise HostRateLimited(3600)
        interval = max(3, instruction.minimum_interval_seconds,
                       setting_int(source, 'INTERVAL_SECONDS', 3, 3600))
        state.requests_today += 0 if backfill else 1
        state.next_request_at = now + timedelta(seconds=interval)
        state.save(update_fields=['budget_day', 'requests_today', 'next_request_at'])
    if job.kind == 'tr_export':
        return transparency_download(job.url, provider, instruction), None
    from scraper import nowe_zrodla
    if job.kind in nowe_zrodla.DOWNLOADS:
        return nowe_zrodla.download(job, provider, instruction), None
    headers, method, body = nowe_zrodla.headers(job), 'GET', None
    if job.kind == 'ted_page':
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        method, body = 'POST', json.dumps(job.context['body']).encode()
    if source == 'meta_ads':
        secret = os.environ.get('META_AD_LIBRARY_TOKEN', '')
        if not secret:
            raise AccessDenied('meta_token_required')
        headers = {'Authorization': 'Bearer ' + secret}
    # Existing transport streams at most 5 MB and validates redirects and DNS.
    # Tokens are headers only, never stored in job URLs, cursors or error strings.
    try:
        raw, receipt = fetch_feed(job.url, hostname_transport=True, audit_source=provider,
            audit_instruction=instruction, requested_kind='api_record' if instruction.channel == 'api' else 'page',
            request_headers=headers, return_receipt=True, budget_share=1.0 if backfill else 0.6, method=method, body=body)
    except ValueError as exc:
        # Ciasteczko + 302 na ten sam adres bez końca: zabezpieczenie przed botami, nie błąd danych.
        if str(exc) == 'Too many source redirects':
            raise BotWall() from None
        raise
    if parsers.bot_wall(raw):
        raise BotWall()
    return raw, receipt


def transparency_download(url, provider, instruction):
    """Weekly 100+ MB open-data export: stream, keep only Polish entries, return them as JSON.

    The shared transport stops at 5 MB, so this one export is streamed here with the
    same access card (checked again just before the request), no redirects and a hard size cap.
    """
    import requests
    from scraper.utils import SOURCE_USER_AGENT
    if approved_instruction(provider, instruction.channel, url) is None:
        raise AccessDenied('no_approved_instruction')
    with requests.get(url, stream=True, allow_redirects=False, timeout=(10, 120),
                      headers={'User-Agent': SOURCE_USER_AGENT}) as response:
        if response.status_code != 200:
            raise ValueError(f'http_{response.status_code}')
        rows = parsers.transparency_polish(response.iter_content(1 << 16))
    return json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()


def _next_page(job, rows, base):
    if not rows:
        return
    context = dict(job.context)
    fingerprint = sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    if (fingerprint == context.get('previous_page') or job.state.jobs.filter(kind=job.kind,
            context__page_sha256=fingerprint).exclude(pk=job.pk).exists()):
        raise ValueError('repeated_api_page')
    job.context = {**job.context, 'page_sha256': fingerprint}
    job.save(update_fields=['context'])
    context.update(offset=context['offset'] + len(rows), previous_page=fingerprint)
    enqueue(job.state, page_url(base, context['filters'], context['offset']), job.kind, context)


def handle(job, raw, receipt=None):
    """One response -> records and child jobs. Caller commits this atomically."""
    kind, state, ctx = job.kind, job.state, job.context
    def put(record_kind, key, **kw):
        return save(job, raw, record_kind, key, receipt=receipt, **kw)

    if kind == 'vote_index':
        rows = _json(raw, list)
        for row in rows:
            if row['term'] != TERM:
                raise ValueError('term_mismatch')
            sitting, number = int(row['sitting']), int(row['votingNumber'])
            enqueue(state, f'{SEJM}/votings/{sitting}/{number}', 'vote', {'sitting': sitting, 'number': number})
        _next_page(job, rows, SEJM + '/votings/search')
    elif kind == 'vote':
        payload = _json(raw, dict)
        rows = parsers.ballots(payload, TERM, ctx['sitting'], ctx['number'])
        prefix = f"{TERM}/{ctx['sitting']}/{ctx['number']}"
        for row in rows:
            put('ballot', f"{prefix}/{int(row['MP'])}", title=payload['title'], date_value=payload['date'],
                data={**row, 'term': TERM, 'sitting': ctx['sitting'], 'number': ctx['number'],
                      'motion': payload.get('description') or payload.get('topic', ''), 'date': payload['date']}, people=[row['MP']])
        # Remove only ballots absent from a validated complete official correction.
        PublicRecord.objects.filter(source=state.source, kind='ballot', external_id__startswith=prefix + '/')\
            .exclude(external_id__in=[f"{prefix}/{int(v['MP'])}" for v in rows]).delete()
    elif kind == 'question_index':
        rows = _json(raw, list)
        for row in rows:
            data, authors = parsers.question(row, TERM)
            put(ctx['resource'], f"{TERM}/{row['num']}", data=data, title=row['title'], people=authors,
                date_value=row.get('receiptDate'), source_url=f"{SEJM}/{ctx['resource']}/{row['num']}")
        _next_page(job, rows, SEJM + '/' + ctx['resource'])
    elif kind == 'proceedings':
        for row in _json(raw, list):
            for day in row['dates']:
                if ctx['since'] <= day <= timezone.localdate().isoformat():
                    enqueue(state, f"{SEJM}/proceedings/{int(row['number'])}/{day}/transcripts", 'transcript_index',
                            {'sitting': int(row['number']), 'day': day})
    elif kind == 'transcript_index':
        data = _json(raw, dict)
        if data['proceedingNum'] != ctx['sitting'] or data['date'] != ctx['day']:
            raise ValueError('transcript_identity_mismatch')
        for row in data['statements']:
            enqueue(state, job.url + '/' + str(int(row['num'])), 'statement', {**ctx, 'statement': row,
                'index_url': job.url, 'index_sha256': sha256(raw).hexdigest(), 'index_fetched_at': timezone.now().isoformat()})
    elif kind == 'statement':
        row = ctx['statement']
        parsed = parsers.speech(raw)
        put('statement', f"{TERM}/{ctx['sitting']}/{ctx['day']}/{row['num']}", title=row['name'],
            text=parsed.pop('text'), date_value=ctx['day'], people=[row.get('memberID')],
            data={**row, **parsed, 'sitting': ctx['sitting'],
                  'index_url': ctx['index_url'], 'index_sha256': ctx['index_sha256'],
                  'index_fetched_at': ctx['index_fetched_at']})
    elif kind == 'members':
        for row in _json(raw, list):
            mp_id = int(row['id'])
            enqueue(state, f'https://www.sejm.gov.pl/sejm10.nsf/posel.xsp?id={mp_id:03d}&type=A',
                    'asset_profile', {**ctx, 'mp_id': mp_id, 'name': row['firstLastName']})
    elif kind == 'asset_profile':
        candidates = []
        for row in parsers.links(raw, job.url):
            p = urlsplit(row['url'])
            if (re.search(r'oświadczenia majątkowe', row['title'], re.I)
                    and p.hostname == 'www.sejm.gov.pl' and p.path.lower() == '/sejm10.nsf/posel.xsp'
                    and parse_qs(p.query).get('id') in ([str(ctx['mp_id'])], [f"{ctx['mp_id']:03d}"])):
                candidates.append(row)
        if not candidates:
            raise ValueError('asset_navigation_missing')
        for row in candidates:
            enqueue(state, row['url'], 'asset_index', ctx)
    elif kind == 'asset_index':
        for row in parsers.assets(raw, job.url):
            if row['year'] and row['year'] < parsers.day(ctx['since']).year:
                continue
            put('asset_document', f"{TERM}/{ctx['mp_id']}/" + sha256(row['url'].encode()).hexdigest(),
                source_url=row['url'], title=row['title'], data={**row, 'mp_id': ctx['mp_id'], 'name': ctx['name']},
                people=[ctx['mp_id']])
    elif kind == 'prints':
        for row in _json(raw, list):
            if row['term'] != TERM:
                raise ValueError('print_term_mismatch')
            if (row.get('changeDate') or row.get('deliveryDate') or '')[:10] < ctx['since']:
                continue
            if not re.search(r'rządowy projekt', row['title'], re.I):
                continue
            number = str(row['number'])
            for attachment in row.get('attachments', []):
                if not attachment.lower().endswith(('.pdf', '.docx', '.txt')):
                    continue
                url = f'{SEJM}/prints/{quote(number, safe="")}/{quote(attachment, safe="")}'
                put('osr_document', sha256(url.encode()).hexdigest(), title=row['title'], source_url=url,
                    print_number=number, data={'attachment': attachment, 'changeDate': row.get('changeDate'), 'status': 'pending'})
                enqueue(state, url, 'osr_text', {'number': number, 'title': row['title']})
    elif kind == 'osr_text':
        text = document_text(raw, job.url)
        rows, quality = parsers.consultations(text, ctx['number'])
        document_key = sha256(job.url.encode()).hexdigest()
        put('osr_document', document_key, title=ctx['title'], print_number=ctx['number'], data=quality)
        for row in rows:
            body = row.pop('_text', '')
            put('consultation', document_key + '/' + row['id'], text=body,
                title='; '.join(p['nazwa'] for p in row['podmioty']), data=row, print_number=ctx['number'])
        if rows:
            PublicRecord.objects.filter(source=state.source, kind='consultation', external_id__startswith=document_key + '/')\
                .exclude(external_id__in=[document_key + '/' + row['id'] for row in rows]).delete()
    elif kind == 'mswia_index':
        candidates = [r for r in parsers.links(raw, job.url) if urlsplit(r['url']).path.startswith('/attachment/')
                      and re.search(r'rejestr', r['title'], re.I) and re.search(r'lobb', r['title'], re.I)]
        if not candidates:
            raise ValueError('mswia_register_link_missing')
        for row in candidates:
            put('register_document', sha256(row['url'].encode()).hexdigest(), source_url=row['url'], title=row['title'], data=row)
            enqueue(state, row['url'], 'register_pdf')
    elif kind == 'register_pdf':
        text = parsers.pdf_text(raw)
        rows = parsers.lobby_register(text)
        put('register_snapshot', sha256(job.url.encode()).hexdigest(), text=text,
            data={'entries': len(rows), 'quality': 'heuristic' if rows else 'unparsed', 'ocr': False})
        for row in rows:
            put('lobby_entity', row['registration_number'], data=row, text=row['entry_text'])
    elif kind == 'lobby_index':
        found = 0
        for row in parsers.links(raw, job.url):
            path = urlsplit(row['url']).path
            if path.startswith('/lobbing/') and path.lower().endswith('.pdf'):
                years = re.findall(r'20\d{2}', row['url'])
                if years and int(years[0]) < parsers.day(ctx['since']).year:
                    continue
                put('lobby_document', sha256(row['url'].encode()).hexdigest(), source_url=row['url'], title=row['title'], data=row)
                found += 1
            elif path == '/sejm10.nsf/lobbing_osoby_tab.xsp':
                enqueue(state, row['url'], 'lobby_people')
                found += 1
        if not found:
            raise ValueError('sejm_lobby_index_changed')
    elif kind == 'lobby_people':
        found = 0
        for table in parsers.HTML(raw).root.find('table'):
            for tr in table.find('tr'):
                cells = [c.text() for c in tr.children if isinstance(c, parsers.Node) and c.tag == 'td']
                if len(cells) < 3:
                    continue
                registry = re.search(r'\((\d{5})\)', cells[1])
                if registry:
                    key = sha256(json.dumps(cells[:2], ensure_ascii=False).encode()).hexdigest()
                    put('lobby_activity', key, title=cells[0], data={'registration_number': registry[1], 'cells': cells})
                    found += 1
        if not found:
            raise ValueError('sejm_lobby_table_changed')
    elif kind in {'pkw_page', 'pkw_csv', 'pkw_xlsx'}:
        financial_rows = parsers.financial_tables(raw, csv_file=kind == 'pkw_csv', xlsx_file=kind == 'pkw_xlsx')
        for row in financial_rows:
            put('financial_row', sha256(job.url.encode()).hexdigest() + f"/{row['table']}/{row['row']}", data=row)
        if kind in {'pkw_csv', 'pkw_xlsx'}:
            return
        found = 0
        for row in parsers.links(raw, job.url):
            p = urlsplit(row['url'])
            if p.hostname != 'pkw.gov.pl':
                continue
            years = re.findall(r'(?<!\d)(20\d{2})(?!\d)', p.path)
            if years and max(map(int, years)) < parsers.day(ctx['since']).year:
                continue
            document = p.path.lower().endswith(('.pdf', '.csv', '.xlsx', '.xls', '.doc', '.docx', '.zip'))
            if p.path.startswith('/uploaded_files/') or (p.path.startswith('/finansowanie-polityki/') and document):
                put('financial_document', sha256(row['url'].encode()).hexdigest(), source_url=row['url'], title=row['title'], data=row)
                if p.path.lower().endswith('.csv'):
                    enqueue(state, row['url'], 'pkw_csv')
                elif p.path.lower().endswith('.xlsx'):
                    enqueue(state, row['url'], 'pkw_xlsx')
                found += 1
            elif p.path.startswith('/finansowanie-polityki/') and ctx['depth'] < 6:
                if ('sprawozdan' in p.path or 'finansowanie-kampanii-wyborczych' in p.path
                        or parse_qs(p.query).get('page')):
                    enqueue(state, row['url'], 'pkw_page', {**ctx, 'depth': ctx['depth'] + 1})
                    found += 1
        if not found and not financial_rows:
            raise ValueError('pkw_no_documents_or_tables')
    elif kind == 'meta_page':
        payload = _json(raw, dict)
        if not isinstance(payload.get('data'), list):
            raise ValueError('meta_response_shape')
        for row in payload['data']:
            data = parsers.meta_ad(row)
            put('political_ad', data['id'], data=data, title=data.get('page_name', ''),
                source_url='https://www.facebook.com/ads/library/?id=' + data['id'],
                text='\n'.join(data.get('ad_creative_bodies', [])), date_value=data.get('ad_delivery_start_time'))
        paging = payload.get('paging', {})
        if paging.get('next'):
            after = paging.get('cursors', {}).get('after')
            if not isinstance(after, str) or not re.fullmatch(r'[A-Za-z0-9_+/=-]{1,1024}', after) or after == ctx['filters'].get('after'):
                raise ValueError('invalid_meta_cursor')
            filters = {**ctx['filters'], 'after': after}
            # Never follow paging.next, which may contain credentials or another host.
            child, created = enqueue(state, ctx['base'] + '?' + urlencode(filters), 'meta_page', {**ctx, 'filters': filters})
            if not created and child.done:
                raise ValueError('repeated_meta_cursor')
    elif kind == 'process_index':
        rows = _json(raw, list)
        for row in rows:
            if row.get('term') != TERM:
                raise ValueError('process_term_mismatch')
            number = str(row['number'])
            enqueue(state, f'{SEJM}/processes/{quote(number, safe="")}', 'process', {'number': number})
        _next_page(job, rows, SEJM + '/processes')
    elif kind == 'process':
        payload = _json(raw, dict)
        if str(payload.get('number')) != ctx['number']:
            raise ValueError('process_identity_mismatch')
        data = parsers.process(payload, TERM)
        keys = [v['key'] for v in data['votings']]
        # Link to what we already hold: ballots (votes collector) and Sejm prints (OfficialRecord).
        official_votes = set(OfficialRecord.objects.filter(provider='sejm',
            external_id__in=['vote/' + key for key in keys]).values_list('external_id', flat=True))
        data['linked_votings'] = [key for key in keys if 'vote/' + key in official_votes or PublicRecord.objects.filter(
            source='votes', kind='ballot', external_id__startswith=key + '/').exists()]
        data['linked_prints'] = list(OfficialRecord.objects.filter(provider='sejm',
            external_id__in=[f'print/{TERM}/{n}' for n in data['prints']]).values_list('external_id', flat=True))
        put('process', f"{TERM}/{ctx['number']}", data=data, title=payload.get('title', ''),
            text=payload.get('description') or '', print_number=ctx['number'][:32],
            date_value=payload.get('processStartDate') or payload.get('documentDate'),
            source_url=f'{SEJM}/processes/{quote(ctx["number"], safe="")}')
    elif kind == 'committee_index':
        for row in _json(raw, list):
            data, members = parsers.committee(row)
            put('committee', f"{TERM}/{data['code']}", data=data, title=data.get('name', data['code']),
                date_value=data.get('appointmentDate'), people=members,
                source_url=f"{SEJM}/committees/{data['code']}")
            enqueue(state, f"{SEJM}/committees/{data['code']}/sittings", 'committee_sittings',
                    {**ctx, 'code': data['code'], 'name': data.get('name', '')})
    elif kind == 'committee_sittings':
        for row in _json(raw, list):
            data, agenda = parsers.committee_sitting(row, ctx['code'])
            if data['date'] < ctx['since']:
                continue
            data['linked_prints'] = list(OfficialRecord.objects.filter(provider='sejm',
                external_id__in=[f'print/{TERM}/{n}' for n in data['prints']]).values_list('external_id', flat=True))
            put('committee_sitting', f"{TERM}/{ctx['code']}/{data['num']}", data={**data, 'committee': ctx['name']},
                title=f"{ctx['name'] or ctx['code']} - posiedzenie nr {data['num']}", text=agenda,
                date_value=data['date'], source_url=f"{SEJM}/committees/{ctx['code']}/sittings/{data['num']}")
    elif kind == 'krs_bulletin':
        from news.political_models import RegisteredOrganisation
        counts = parsers.krs_bulletin(_json(raw, list))
        for org in RegisteredOrganisation.objects.filter(krs_number__in=list(counts), archived=False).order_by('krs_number'):
            put('krs_bulletin_entry', f"{org.krs_number}/{ctx['day']}", title=org.name, date_value=ctx['day'],
                data={'krs': org.krs_number, 'day': ctx['day'], 'entries': counts[org.krs_number],
                      'organisation_id': org.pk}, source_url=job.url)
            register = org.register if org.register in {'P', 'S'} else 'P'
            enqueue(state, f'{KRS_API}/OdpisAktualny/{org.krs_number}?rejestr={register}&format=json', 'krs_extract',
                    {'krs': org.krs_number, 'day': ctx['day'], 'organisation_id': org.pk})
    elif kind == 'krs_extract':
        header = parsers.krs_header(_json(raw, dict), ctx['krs'])
        put('krs_change', f"{ctx['krs']}/{header['last_entry_number']}", title=header['name'],
            date_value=header['last_entry_date'] or ctx['day'],
            data={**header, 'bulletin_day': ctx['day'], 'organisation_id': ctx['organisation_id']})
    elif kind == 'ted_page':
        payload = _json(raw, dict)
        notices = payload.get('notices')
        if not isinstance(notices, list):
            raise ValueError('ted_response_shape')
        for row in notices:
            data = parsers.ted_notice(row)
            put('notice', data['id'], data=data, title=data['title'], source_url=data['url'],
                text='; '.join(data['buyer']), date_value=data['date'] or None)
        body = ctx['body']
        total = int(payload.get('totalNoticeCount') or 0)
        if notices and len(notices) == body['limit'] and body['page'] * body['limit'] < min(total, 15000):
            enqueue(state, job.url, 'ted_page', {'body': {**body, 'page': body['page'] + 1}})
    elif kind == 'tr_export':
        rows = _json(raw, list)
        seen = []
        for row in rows:
            put('organisation', row['id'], data=row, title=row['name'], date_value=row.get('updated') or row.get('registered'),
                text=row.get('goals', ''),
                source_url='https://transparency-register.europa.eu/searchregister-or-update/organisation-detail_en?id=' + row['id'])
            seen.append(row['id'])
        # An organisation that left the export stays as evidence, marked as absent.
        for record in PublicRecord.objects.filter(source=state.source, kind='organisation').exclude(external_id__in=seen):
            if record.data.get('status') != 'brak_w_eksporcie':
                record.data = {**record.data, 'status': 'brak_w_eksporcie'}
                record.save(update_fields=['data'])
    else:
        from scraper.nowe_zrodla import HANDLERS
        if kind not in HANDLERS:
            raise ValueError('unknown_job_kind')
        HANDLERS[kind](job, raw, put)


def skip_walled(state, kind):
    """Kontrola pomocnicza za ścianą botów: wszystkie zaległe zadania tego rodzaju kończymy z adnotacją (bez sieci)."""
    note = OPTIONAL_WALL_KINDS[kind]
    with transaction.atomic():
        jobs = list(state.jobs.filter(done=False, kind=kind))
        if kind == 'office_pdf':
            for job in jobs:
                record = PublicRecord.objects.filter(source=state.source, kind='office_report',
                    external_id=f"{job.context.get('mp_id')}/{job.context.get('year')}").first()
                if record and record.data.get('pdf_check', '').startswith('oczekuje'):
                    record.data = {**record.data, 'pdf_check': note}
                    record.save(update_fields=['data'])
        state.jobs.filter(pk__in=[j.pk for j in jobs]).update(done=True, last_error='', retry_at=None)
    return len(jobs)


def document_text(raw, url):
    if raw.startswith(b'%PDF-'):
        return parsers.pdf_text(raw)
    if urlsplit(url).path.lower().endswith('.txt'):
        return raw.decode('utf-8-sig')
    # Small DOCX tables only, bounded ZIP expansion, stdlib XML; no macros/OCR.
    if urlsplit(url).path.lower().endswith('.docx'):
        from io import BytesIO
        from zipfile import ZipFile
        from xml.etree import ElementTree
        with ZipFile(BytesIO(raw)) as archive:
            info = archive.getinfo('word/document.xml')
            if info.file_size > 5_000_000:
                raise ValueError('docx_text_limit')
            xml = archive.read(info)
            if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                raise ValueError('unsafe_docx_xml')
            root = ElementTree.fromstring(xml)
        ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        return '\n'.join(''.join(p.itertext()) for p in root.iter(ns + 'p'))
    raise ValueError('unsupported_text_document')


def collect(source, *, since=None, max_requests=None, backfill=None):
    """One bounded tick. --since starts/resumes a historical cycle, never loops.

    backfill ('noc'/'resztka', scraper.zasil_baze): the same frontier and access card, but requests count against
    the separate backfill budget; a new cycle started with since seeds the full history (TED by month, KRS extracts)."""
    spec = SOURCES[source]
    if not flag(spec.flag(source), False):
        return {'status': 'disabled', 'new_records': 0}
    if source == 'meta_ads' and not os.environ.get('META_AD_LIBRARY_TOKEN'):
        return {'status': 'disabled', 'reason': 'meta_token_required', 'new_records': 0}
    since = parsers.day(since) if since else None
    earliest = START if source in SEJM_SOURCES else date(1970, 1, 1)
    if since and (since < earliest or since > timezone.localdate()):
        raise ValueError('since_outside_source_range')
    limit = setting_int(source, 'BATCH_REQUESTS', 4, 20)
    if max_requests is not None:
        if not 1 <= max_requests <= 20:
            raise ValueError('invalid_batch_size')
        limit = min(limit, max_requests)
    token, now = str(uuid4()), timezone.now()
    with transaction.atomic():
        state, _ = PublicCollectionState.objects.get_or_create(source=source)
        state = PublicCollectionState.objects.select_for_update().get(pk=state.pk)
        if state.lease_until and state.lease_until > now:
            return {'status': 'already_running', 'new_records': 0}
        if (state.status == 'blocked_access_review' and state.last_error == BOT_WALL and state.last_started_at
                and now - state.last_started_at < timedelta(hours=setting_int(source, 'BOT_WALL_PAUSE_HOURS', 24, 720))):
            return {'status': 'blocked_access_review', 'error': BOT_WALL, 'new_records': 0, 'completed': 0, 'requests': 0,
                    'pending': state.jobs.filter(done=False).count()}
        pending = state.jobs.filter(done=False).exists()
        if pending and since and state.since != since:
            raise ValueError('different_backfill_in_progress')
        if not pending:
            previous_scan = max((d for d in (state.last_complete_at, state.cycle_started_at) if d), default=None)
            if not since and previous_scan and now - previous_scan < timedelta(hours=spec.refresh_hours):
                return {'status': 'idle', 'new_records': 0}
            state.jobs.all().delete()
            first_start = timezone.localdate() - timedelta(days=spec.lookback_days) if spec.lookback_days else START
            start = since or (state.cycle_started_at.date() - timedelta(days=spec.overlap_days) if previous_scan else first_start)
            # Archive indexes (wealth, PKW, lobbying) need a full rediscovery for corrections.
            if source in {'assets', 'pkw', 'lobby_mswia', 'lobby_sejm'} and not since:
                start = START
            state.since = max(start, earliest)
            seed(state, state.since, incremental=bool(previous_scan and not since), backfill=bool(backfill and since))
            state.cycle_started_at = now
        state.lease_token, state.lease_until = token, now + timedelta(minutes=15)
        state.last_started_at, state.status = now, 'running'
        state.save()
    requests, completed, documents = 0, 0, 0
    status, error = 'partial', ''
    try:
        while requests < limit:
            now = timezone.now()
            job = state.jobs.filter(done=False).filter(Q(retry_at__isnull=True) | Q(retry_at__lte=now)).order_by('id').first()
            if job is None:
                status = 'deferred' if state.jobs.filter(done=False).exists() else 'ok'
                break
            binary = job.kind in {'osr_text', 'register_pdf', 'pkw_xlsx', 'tr_export', 'fts_year', 'iw_meetings', 'office_pdf'}
            if binary and documents:
                break  # At most one document per tick, never a large-file loop.
            requests += 1
            try:
                raw, receipt = fetch(job, token, backfill) if backfill else fetch(job, token)
                with transaction.atomic():
                    locked = PublicCollectionState.objects.select_for_update().get(pk=state.pk)
                    if locked.lease_token != token or locked.lease_until <= timezone.now():
                        raise AccessDenied('collector_lease_lost')
                    if not flag(spec.flag(source), False):
                        raise AccessDenied('collector_disabled')
                    source_access(job)  # A revoked/expired card cannot authorise a late write.
                    handle(job, raw, receipt)
                    job.done, job.last_error, job.retry_at = True, '', None
                    job.save(update_fields=['done', 'last_error', 'retry_at'])
                    locked.last_success_at = timezone.now()
                    locked.save(update_fields=['last_success_at'])
                completed += 1
                documents += int(binary)
            except BotWall:
                if job.kind not in OPTIONAL_WALL_KINDS:
                    raise
                skip_walled(state, job.kind)  # dalej zwykły odstęp hosta i następne zadanie
            except (AccessDenied, HostRateLimited):
                raise
            except Exception as exc:
                # No exception body: HTTP errors may contain credentials/provider content.
                review_errors = {'Source response too large', 'invalid_or_large_pdf', 'pdf_requires_manual_review',
                                 'pdf_text_limit', 'docx_text_limit', 'spreadsheet_expansion_limit'}
                requires_review = isinstance(exc, ValueError) and str(exc) in review_errors
                # Własne kody parserów (np. asset_navigation_missing) są bezpieczne i mówią, co się zmieniło.
                own_code = isinstance(exc, ValueError) and re.fullmatch(r'[a-z][a-z0-9_]{2,63}', str(exc))
                error = (str(exc).replace(' ', '_').lower() if requires_review else
                         f'{type(exc).__name__}: {exc}' if own_code else type(exc).__name__)
                job.failures += 1
                job.last_error, job.retry_at = error, timezone.now() + timedelta(hours=min(24, 2 ** min(job.failures, 5)))
                job.done = requires_review
                job.save(update_fields=['failures', 'last_error', 'retry_at', 'done'])
                if requires_review:
                    for record in PublicRecord.objects.filter(source=source, source_url=job.url,
                            kind__in=['osr_document', 'register_document', 'financial_document']):
                        record.data = {**record.data, 'status': 'needs_review', 'error': error}
                        record.save(update_fields=['data'])
                status = 'needs_review' if requires_review else 'error'
                break
            if requests < limit:
                state.refresh_from_db(fields=['next_request_at'])
                wait = max(0, (state.next_request_at - timezone.now()).total_seconds())
                if wait > 10:
                    break
                sleep(wait)
        if not state.jobs.filter(done=False).exists():
            status = 'needs_review' if state.jobs.exclude(last_error='').exists() else 'ok'
            if status == 'needs_review' and not error:
                error = 'documents_require_review'
    except AccessDenied as exc:
        status, error = 'blocked_access_review', str(exc)[:120]
    except HostRateLimited:
        status, error = 'deferred', 'request_limit_or_host_interval'
    finally:
        with transaction.atomic():
            current = PublicCollectionState.objects.select_for_update().get(pk=state.pk)
            if current.lease_token == token:
                current.status, current.last_error = status, error
                current.record_count = PublicRecord.objects.filter(source=source).count()
                current.lease_token, current.lease_until = '', None
                if status == 'ok':
                    current.last_complete_at = timezone.now()
                current.save()
    return {'status': status, 'completed': completed, 'requests': requests,
            'error': error, 'pending': state.jobs.filter(done=False).count()}
