"""Nowe źródła danych (raport źródeł 6.10, tydzień 1 i 2) w tej samej trwałej kolejce, kartach dostępu, odstępie hosta
i limitach co scraper.public_records. Bez AI, bez logowania, bez scrapowania stron (tylko udokumentowane API i pliki
otwartych danych), bez pełnych tekstów artykułów. Każde źródło ma własną flagę PUBLIC_RECORDS_<ŹRÓDŁO>_ENABLED.

- videos: transmisje Sejmu (api.sejm.gov.pl /videos) i zapisy przebiegu posiedzeń komisji (html z API Sejmu) ->
  wystąpienia posłów z miejscem w nagraniu; diagnozy robi news.sejm_wideo (Konsylium, ta sama miara).
- howtheyvote: głosowania imienne w PE (HowTheyVote.eu, ODbL 1.0) - tylko europosłowie z Polski, osoba po id PE.
- wikidata: tożsamości osób publicznych (CC0): id posła (URL profilu Sejmu), id PE, Wikipedia, historia partyjna.
  Konto X tylko jako wskazówka do sprawdzenia - nigdy nie potwierdza konta (zasada podwójnego potwierdzenia zostaje).
- kohesio: projekty funduszy spójności 2014-2020 w Polsce (Kohesio, CC0); beneficjent tylko organizacja.
- fts: budżet UE zarządzany przez KE (FTS, CC BY 4.0), pliki roczne; tylko beneficjenci z Polski i tylko organizacje.
- integrity_watch: deklaracje (dochody dodatkowe) i spotkania z lobbystami europosłów z Polski (Transparency
  International EU, ODbL 1.0); bez e-maili i dat urodzenia.
- mileage: kilometrówki i sprawozdania biur posłów (jakglosuja.pl, CC BY 4.0). Kontrola z Sejmem: id i nazwisko posła
  z listy X kadencji oraz suma sprawozdania porównana z PDF Kancelarii Sejmu (orka.sejm.gov.pl).
Osoby fizyczne bez funkcji publicznej (beneficjenci, wykonawcy) są pomijane (LEGAL w news.pracownia_osint).
"""
from collections import Counter
from datetime import date, timedelta
from hashlib import sha256
import csv
import io
import json
import re
from time import monotonic
from urllib.parse import quote, urlencode, urlsplit

from django.utils import timezone

from scraper import public_record_parsers as parsers

HTV = 'https://howtheyvote.eu/api/votes'
WIKIDATA = 'https://query.wikidata.org/sparql'
KOHESIO = 'https://cohesiondata.ec.europa.eu/resource/557j-pmg8.json'
FTS = 'https://ec.europa.eu/budget/financial-transparency-system/download/{year}_FTS_dataset_en.xlsx'
IW = 'https://www.integritywatch.eu/data/'
IW_MEPS = IW + 'meps/dpi_legislature_10/meps.json'
IW_INCOME = IW + 'meps/dpi_legislature_10/new_dpi_activities_1.csv'
IW_MEETINGS = IW + 'mepmeetings/legislature_10/mepmeetings.json'
JAKGLOSUJA = 'https://jakglosuja.pl/api/eksport/'
MILEAGE = JAKGLOSUJA + 'kilometrowki?format=json'
OFFICES = JAKGLOSUJA + 'sprawozdania?format=json'

# Hosty spoza API Sejmu: (host, prefiks ścieżki, adres katalogu źródła, kanał karty). Pierwszy wiersz = główny.
HOSTS = {
    'howtheyvote': [('howtheyvote.eu', '/api/votes', 'https://howtheyvote.eu', 'api')],
    'wikidata': [('query.wikidata.org', '/sparql', 'https://query.wikidata.org', 'api')],
    'kohesio': [('cohesiondata.ec.europa.eu', '/resource/557j-pmg8.json', 'https://cohesiondata.ec.europa.eu', 'api')],
    'fts': [('ec.europa.eu', '/budget/financial-transparency-system/download/',
             'https://ec.europa.eu/budget/financial-transparency-system', 'export')],
    'integrity_watch': [('www.integritywatch.eu', '/data/', 'https://www.integritywatch.eu', 'export')],
    'mileage': [('jakglosuja.pl', '/api/eksport/', 'https://jakglosuja.pl', 'api'),
                ('orka.sejm.gov.pl', '/rozlicz10.nsf/', 'https://orka.sejm.gov.pl', 'export')],
}
# Atrybucja i licencja (pokazywane przy danych na stronach; ODbL: pochodną bazę udostępniamy na tej samej licencji).
LICENSES = {
    'videos': {'label': 'Kancelaria Sejmu (api.sejm.gov.pl)', 'license': 'informacja publiczna',
               'url': 'https://api.sejm.gov.pl/videos.html'},
    'howtheyvote': {'label': 'HowTheyVote.eu', 'license': 'ODbL 1.0', 'url': 'https://howtheyvote.eu/about',
                    'note': 'Dane o głosowaniach: HowTheyVote.eu na licencji ODbL 1.0. Zestawienia pochodne udostępniamy '
                            'na tej samej licencji.'},
    'wikidata': {'label': 'Wikidata', 'license': 'CC0 1.0', 'url': 'https://www.wikidata.org/wiki/Wikidata:Data_access'},
    'kohesio': {'label': 'Kohesio, Komisja Europejska', 'license': 'CC0 1.0', 'url': 'https://kohesio.ec.europa.eu/'},
    'fts': {'label': 'Financial Transparency System, Komisja Europejska', 'license': 'CC BY 4.0',
            'url': 'https://ec.europa.eu/budget/financial-transparency-system/'},
    'integrity_watch': {'label': 'Integrity Watch EU (Transparency International EU)', 'license': 'ODbL 1.0',
                        'url': 'https://www.integritywatch.eu/about.php',
                        'note': 'Dane: Integrity Watch EU na licencji ODbL 1.0, źródło pierwotne: deklaracje i rejestr '
                                'spotkań Parlamentu Europejskiego. Zestawienia pochodne na tej samej licencji.'},
    'mileage': {'label': 'jakglosuja.pl', 'license': 'CC BY 4.0', 'url': 'https://jakglosuja.pl/dane-otwarte',
                'note': 'Dane: jakglosuja.pl (CC BY 4.0). Sprawozdania biur sprawdzamy z PDF Kancelarii Sejmu.'},
}
DOWNLOADS = {'fts_year', 'iw_meetings'}
WIKIDATA_HINT = 'wskazówka z Wikidata - konto nie jest potwierdzone'
SKIPPED_PERSON = 'pominięto: osoba fizyczna'


# --- wspólne ------------------------------------------------------------------------------------------------

def headers(job):
    if job.state.source == 'wikidata':
        return {'Accept': 'application/sparql-results+json'}
    if job.state.source in {'howtheyvote', 'kohesio', 'mileage'} and job.kind != 'office_pdf':
        return {'Accept': 'application/json'}
    return None


def _json(raw, expected):
    from scraper.public_records import _json as parse
    return parse(raw, expected)


def _key(*parts):
    return sha256('\n'.join(str(p) for p in parts).encode()).hexdigest()[:40]


def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _money(value):
    try:
        return round(float(str(value).replace(' ', '').replace(',', '.')), 2)
    except (TypeError, ValueError):
        return None


def _iso(value):
    """dd-mm-yyyy albo yyyy-mm-dd(...) -> yyyy-mm-dd; inne -> None."""
    value = str(value or '').strip()
    m = re.fullmatch(r'(\d{2})[-.](\d{2})[-.](\d{4})', value)
    if m:
        return f'{m[3]}-{m[2]}-{m[1]}'
    return value[:10] if re.match(r'\d{4}-\d{2}-\d{2}', value) else None


def _tokens(name):
    return tuple(sorted(w for w in re.split(r'[\s\-]+', (name or '').casefold()) if w))


def seed(state, since, incremental=False, backfill=False):
    from scraper.public_records import SEJM, enqueue, page_url
    source, today = state.source, timezone.localdate()
    if source == 'videos':
        filters = {'since': since.isoformat(), 'till': today.isoformat()}
        enqueue(state, page_url(SEJM + '/videos', filters), 'video_index', {'filters': filters, 'offset': 0})
    elif source == 'howtheyvote':
        enqueue(state, htv_url(1), 'htv_index', {'page': 1, 'since': since.isoformat()})
    elif source == 'wikidata':
        for which in ('sejm', 'ep'):
            enqueue(state, wikidata_url(which), 'wd_query', {'which': which})
    elif source == 'kohesio':
        enqueue(state, kohesio_url(0), 'kohesio_page', {'offset': 0})
    elif source == 'fts':
        for year in fts_years(since, today):
            enqueue(state, FTS.format(year=year), 'fts_year', {'year': year})
    elif source == 'integrity_watch':
        enqueue(state, IW_MEPS, 'iw_meps')
        enqueue(state, IW_INCOME, 'iw_income')
        enqueue(state, IW_MEETINGS, 'iw_meetings')
    elif source == 'mileage':
        enqueue(state, MILEAGE, 'mileage_export')
        enqueue(state, OFFICES, 'office_export')


def download(job, provider, instruction):
    """Duże pliki (FTS ok. 20 MB, spotkania europosłów ok. 30 MB): strumień z tą samą kartą (sprawdzaną tuż przed
    zapytaniem), bez przekierowań i z twardym limitem; zwraca tylko polskie wiersze jako mały JSON."""
    import requests
    from scraper.access_gate import AccessDenied, approved_instruction
    from scraper.utils import SOURCE_USER_AGENT
    if approved_instruction(provider, instruction.channel, job.url) is None:
        raise AccessDenied('no_approved_instruction')
    limit = 150_000_000 if job.kind == 'fts_year' else 80_000_000
    with requests.get(job.url, stream=True, allow_redirects=False, timeout=(10, 180),
                      headers={'User-Agent': SOURCE_USER_AGENT}) as response:
        if response.status_code != 200:
            raise ValueError(f'http_{response.status_code}')
        if job.kind == 'fts_year':
            rows = fts_polish(response.iter_content(1 << 16), limit)
        else:
            rows = meetings_polish(response.iter_content(1 << 16), limit)
    return json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()


def _buffer(chunks, limit):
    data, size = bytearray(), 0
    for chunk in chunks:
        size += len(chunk)
        if size > limit:
            raise ValueError('Source response too large')
        data.extend(chunk)
    return bytes(data)


# --- 1. Sejm: transmisje wideo i zapisy posiedzeń komisji ----------------------------------------------------

def video(row):
    if not isinstance(row, dict) or not re.fullmatch(r'[0-9A-F]{32}', str(row.get('unid', ''))):
        raise ValueError('video_shape')
    player = row.get('playerLink') or ''
    if player:
        player = parsers.public_url(player)
    return {'unid': row['unid'], 'type': str(row.get('type') or ''), 'title': ' '.join(str(row.get('title') or '').split()),
            'description': parsers.strip_tags(row.get('description'))[:4000], 'committee': str(row.get('committee') or ''),
            'subcommittee': str(row.get('subcommittee') or ''), 'room': str(row.get('room') or ''),
            'start': str(row.get('startDateTime') or ''), 'end': str(row.get('endDateTime') or ''),
            'player': player, 'transcribe': bool(row.get('transcribe'))}


def video_index(job, raw, put):
    from news.public_records_models import PublicRecord
    from scraper.public_records import SEJM, TERM, _next_page, enqueue
    rows = _json(raw, list)
    for row in rows:
        data = video(row)
        put('video', data['unid'], data=data, title=data['title'] or data['type'], text=data['description'],
            date_value=data['start'][:10] or None, source_url=data['player'] or job.url)
        if data['type'] != 'komisja' or not re.fullmatch(r'[A-Z0-9]{2,8}', data['committee']) or not data['start']:
            continue
        # Zapis przebiegu posiedzenia komisji: numer posiedzenia z danych komisji (zbieracz committees), po unid nagrania.
        sittings = PublicRecord.objects.filter(source='committees', kind='committee_sitting',
                                               external_id__startswith=f"{TERM}/{data['committee']}/", date=data['start'][:10])
        for sitting in sittings:
            if any(data['unid'] in str(link) for link in sitting.data.get('video') or []):
                num = int(sitting.data['num'])
                enqueue(job.state, f"{SEJM}/committees/{data['committee']}/sittings/{num}/html", 'committee_transcript',
                        {'code': data['committee'], 'num': num, 'unid': data['unid'], 'day': data['start'][:10],
                         'start': data['start'], 'end': data['end'], 'player': data['player'],
                         'committee': sitting.data.get('committee') or data['title']})
    _next_page(job, rows, SEJM + '/videos')


SPEAKER = re.compile(r'<p>\s*<b>\s*([^<]{3,200}?)\s*:\s*</b>\s*(?:<br\s*/?>)?', re.I)
MP_SPEAKER = re.compile(r'pos(?:eł|łanka)\s+([^()]+?)\s*\(([^)]{1,40})\)\s*$', re.I)


def committee_speeches(raw):
    """Zapis przebiegu posiedzenia komisji -> [(mówca, tekst, pozycja 0-1)]; bez nagrań, tylko tekst urzędowy."""
    html = raw.decode('utf-8-sig', 'replace') if isinstance(raw, bytes) else raw
    start = html.find('class="transcript"')
    body = html[start:] if start >= 0 else html
    marks = list(SPEAKER.finditer(body))
    if not marks:
        return []
    total = len(body)
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        text = parsers.strip_tags(body[m.end():end].replace('<p>', '\n<p>'))
        if text:
            out.append((' '.join(m[1].split()), text, round(m.start() / total, 4)))
    return out


def mp_by_name(speaker, club, code):
    """Poseł z mówcy zapisu: imię i nazwisko z klubem z oficjalnego składu komisji (API Sejmu), a gdy go tam nie ma -
    z listy posłów X kadencji; tylko wynik jednoznaczny. Nazwisko samo nigdy nie wystarcza."""
    from news.political_models import ParliamentaryRosterEntry
    from news.public_records_models import PublicRecord
    from scraper.public_records import TERM
    wanted = _tokens(speaker)
    club_key = (club or '').split('-')[0].casefold()
    committee = PublicRecord.objects.filter(source='committees', kind='committee', external_id=f'{TERM}/{code}').first()
    found = {int(m['id']) for m in (committee.data.get('members') if committee else []) or []
             if _tokens(m.get('lastFirstName')) == wanted and str(m.get('club', '')).split('-')[0].casefold() == club_key}
    if len(found) == 1:
        return found.pop(), 'skład komisji (imię, nazwisko, klub)'
    found = {int(e.external_id) for e in ParliamentaryRosterEntry.objects.filter(source='sejm', term=TERM)
             if str(e.external_id).isdigit() and _tokens(e.full_name) == wanted
             and (not e.club or e.club.split('-')[0].casefold() == club_key)}
    if len(found) == 1:
        return found.pop(), 'lista posłów X kadencji (imię, nazwisko, klub)'
    return None, 'bez jednoznacznego posła'


def committee_transcript(job, raw, put):
    ctx = job.context
    speeches = committee_speeches(raw)
    if not speeches:
        return  # zapis jeszcze nie gotowy: kolejny cykl (z zakładką) zapyta znowu
    for index, (speaker, text, position) in enumerate(speeches):
        m = MP_SPEAKER.search(speaker)
        if not m:
            continue  # tylko posłowie (przewodniczący, ministrowie i goście bez diagnozy w tym kroku)
        name, club = ' '.join(m[1].split()), m[2].strip()
        mp_id, how = mp_by_name(name, club, ctx['code'])
        put('committee_speech', f"{ctx['code']}/{ctx['num']}/{index}", title=f"{name} ({club}) - {ctx['committee']}"[:300],
            text=text[:20000], date_value=ctx['day'], people=[mp_id] if mp_id else [],
            source_url=job.url,
            data={'speaker': speaker, 'name': name, 'club': club, 'code': ctx['code'], 'sitting': ctx['num'],
                  'committee': ctx['committee'], 'unid': ctx['unid'], 'player': ctx['player'], 'video_start': ctx['start'],
                  'video_end': ctx['end'], 'position': position, 'words': len(text.split()), 'match': how})


# --- 2. HowTheyVote.eu: głosowania PE ---------------------------------------------------------------------------

def htv_url(page):
    return HTV + '?' + urlencode({'page': page, 'page_size': 50})


def htv_index(job, raw, put):
    from scraper.public_records import enqueue
    payload = _json(raw, dict)
    rows = payload.get('results')
    if not isinstance(rows, list):
        raise ValueError('howtheyvote_shape')
    since, older = job.context['since'], False
    for row in rows:
        vote_id = str(row.get('id', ''))
        if not vote_id.isdigit():
            raise ValueError('howtheyvote_id')
        if str(row.get('timestamp', ''))[:10] < since:
            older = True
            continue
        enqueue(job.state, f'{HTV}/{vote_id}', 'htv_vote', {'id': vote_id})
    page = int(job.context['page'])
    if rows and payload.get('has_next') and not older and page < 500:
        enqueue(job.state, htv_url(page + 1), 'htv_index', {**job.context, 'page': page + 1})


def htv_vote(job, raw, put):
    from scraper.public_records import EP_TERM
    data = _json(raw, dict)
    if str(data.get('id')) != job.context['id']:
        raise ValueError('howtheyvote_identity_mismatch')
    polish = []
    for row in data.get('member_votes') or []:
        member = row.get('member') or {}
        if (member.get('country') or {}).get('code') != 'POL' or not _int(member.get('id')):
            continue
        polish.append({'ep_id': _int(member['id']), 'name': member.get('full_name', ''),
                       'group': (member.get('group') or {}).get('short_label', ''),
                       'party': (member.get('national_party') or {}).get('short_label')
                       or (member.get('national_party') or {}).get('label', ''), 'position': row.get('position', '')})
    stats = (data.get('stats') or {}).get('total') or {}
    put('ep_vote', job.context['id'], title=str(data.get('display_title') or '')[:500],
        text=str(data.get('description') or '')[:2000], date_value=str(data.get('timestamp', ''))[:10] or None,
        source_url=f"https://howtheyvote.eu/votes/{job.context['id']}",
        persons=[(EP_TERM, v['ep_id']) for v in polish],
        data={'reference': data.get('reference') or '', 'is_main': bool(data.get('is_main')), 'result': data.get('result'),
              'total': {k: stats.get(k) for k in ('FOR', 'AGAINST', 'ABSTENTION', 'DID_NOT_VOTE')},
              'polish': dict(Counter(v['position'] for v in polish)), 'votes': polish,
              'procedure': {k: (data.get('procedure') or {}).get(k) for k in ('reference', 'title', 'url')},
              'document': (data.get('document') or {}).get('url'), 'license': 'ODbL 1.0'})


# --- 3. Wikidata: tożsamości i historia partyjna ---------------------------------------------------------------

WIKIDATA_QUERIES = {
    # Posłowie: oficjalny URL profilu posła (P973 „described at URL”) z identyfikatorem Sejmu.
    'sejm': 'FILTER(CONTAINS(LCASE(STR(?url)), "sejm.gov.pl/sejm10.nsf/posel.xsp")) ?item wdt:P973 ?url .',
    # Europosłowie z Polski: identyfikator PE (P1186), obywatelstwo polskie i mandat w PE.
    'ep': '?item wdt:P1186 ?ep ; wdt:P27 wd:Q36 ; wdt:P39 wd:Q27169 .',
}


def wikidata_url(which):
    head = WIKIDATA_QUERIES[which]
    query = ('SELECT ?item ?itemLabel ?url ?ep ?x ?wiki ?party ?partyLabel ?start ?end WHERE { ' + head +
             ' OPTIONAL { ?item wdt:P973 ?url . } OPTIONAL { ?item wdt:P1186 ?ep . } OPTIONAL { ?item wdt:P2002 ?x . }'
             ' OPTIONAL { ?wiki schema:about ?item ; schema:isPartOf <https://pl.wikipedia.org/> . }'
             ' OPTIONAL { ?item p:P102 ?st . ?st ps:P102 ?party . OPTIONAL { ?st pq:P580 ?start . }'
             ' OPTIONAL { ?st pq:P582 ?end . } }'
             ' SERVICE wikibase:label { bd:serviceParam wikibase:language "pl,en". } } LIMIT 20000')
    return WIKIDATA + '?' + urlencode({'query': query, 'format': 'json'})


SEJM_PROFILE = re.compile(r'sejm\.gov\.pl/sejm(\d+)\.nsf/posel\.xsp\?id=0*(\d{1,4})', re.I)


def wikidata_people(payload):
    people = {}
    for b in (payload.get('results') or {}).get('bindings') or []:
        value = lambda k: (b.get(k) or {}).get('value', '')  # noqa: E731
        qid = value('item').rsplit('/', 1)[-1]
        if not re.fullmatch(r'Q\d{1,12}', qid):
            continue
        p = people.setdefault(qid, {'qid': qid, 'label': value('itemLabel'), 'sejm': set(), 'ep': set(), 'x': set(),
                                    'wiki': '', 'parties': {}})
        for term, mp in SEJM_PROFILE.findall(value('url')):
            p['sejm'].add((int(term), int(mp)))
        if value('ep').isdigit():
            p['ep'].add(int(value('ep')))
        if re.fullmatch(r'[A-Za-z0-9_]{1,15}', value('x')):
            p['x'].add(value('x'))
        if value('wiki').startswith('https://pl.wikipedia.org/'):
            p['wiki'] = value('wiki')
        party = value('party').rsplit('/', 1)[-1]
        if re.fullmatch(r'Q\d{1,12}', party):
            key = (party, value('start')[:10], value('end')[:10])
            p['parties'][key] = {'qid': party, 'name': value('partyLabel'), 'start': value('start')[:10] or None,
                                 'end': value('end')[:10] or None}
    return people


def wd_query(job, raw, put):
    from news.public_records_models import PublicRecord
    from scraper.public_records import EP_TERM
    for qid, p in wikidata_people(_json(raw, dict)).items():
        old = PublicRecord.objects.filter(source='wikidata', kind='person', external_id=qid).first()
        before = old.data if old else {}
        sejm = {tuple(x) for x in before.get('sejm_ids') or []} | p['sejm']
        ep = set(before.get('ep_ids') or []) | p['ep']
        parties = {(x['qid'], x.get('start') or '', x.get('end') or ''): x for x in before.get('parties') or []}
        parties.update(p['parties'])
        put('person', qid, title=p['label'][:300], source_url=f'https://www.wikidata.org/wiki/{qid}',
            persons=[*sejm, *((EP_TERM, e) for e in ep)],
            data={'qid': qid, 'sejm_ids': sorted(sejm), 'ep_ids': sorted(ep), 'wikipedia': p['wiki'] or before.get('wikipedia', ''),
                  'x_hints': sorted(set(before.get('x_hints') or []) | p['x']), 'x_note': WIKIDATA_HINT,
                  'parties': sorted(parties.values(), key=lambda x: (x.get('start') or '', x['name'])),
                  'license': 'CC0 1.0'})


# --- 6. Kohesio i FTS: fundusze UE ------------------------------------------------------------------------------

KOHESIO_COLUMNS = ('operation_unique_identifier', 'operation_name_programme_language', 'operation_name_english',
                   'beneficiary_name', 'beneficiary_unique_identifier', 'operation_start_date', 'operation_end_date',
                   'total_eligible_expenditure_amount', 'project_eu_budget', 'fund_code', 'programme_code',
                   'programme_name', 'region', 'nuts3_code', 'programming_period', 'category_label')
KOHESIO_PAGE = 1000


def kohesio_url(offset):
    return KOHESIO + '?' + urlencode({'$select': ','.join(KOHESIO_COLUMNS), '$where': "country='Poland'",
                                      '$order': ':id', '$limit': KOHESIO_PAGE, '$offset': offset})


FORMS = ((r'sp(ó|o)(ł|l)ka z ograniczon(ą|a) odpowiedzialno(ś|s)ci(ą|a)', 'sp z o o'), (r'sp(ó|o)(ł|l)ka akcyjna', 's a'),
         (r'sp(ó|o)(ł|l)ka komandytowa', 'sp k'), (r'sp(ó|o)(ł|l)ka jawna', 'sp j'))
_ORGS = {'at': 0.0, 'index': {}}


def org_key(name):
    value = (name or '').casefold()
    for pattern, short in FORMS:
        value = re.sub(pattern, short, value)
    value = re.sub(r'[^\w\s]', ' ', value)
    return ' '.join(value.split())


def org_index(refresh=False):
    """Znormalizowana nazwa -> (id, KRS) organizacji z KRS, które już obserwujemy; tylko nazwy jednoznaczne."""
    from news.political_models import RegisteredOrganisation
    if refresh or monotonic() - _ORGS['at'] > 600:
        seen, index = Counter(), {}
        for pk, name, krs in RegisteredOrganisation.objects.filter(archived=False).values_list('pk', 'name', 'krs_number'):
            key = org_key(name)
            seen[key] += 1
            index[key] = (pk, krs)
        _ORGS.update(at=monotonic(), index={k: v for k, v in index.items() if seen[k] == 1})
    return _ORGS['index']


def org_link(name):
    match = org_index().get(org_key(name))
    return {'organisation_id': match[0], 'krs': match[1], 'link': 'nazwa z KRS (do sprawdzenia)'} if match else {}


def kohesio_page(job, raw, put):
    from scraper.public_records import enqueue
    rows = _json(raw, list)
    skipped = 0
    for row in rows:
        project = str((row.get('operation_unique_identifier') or {}).get('url', '')).rsplit('/', 1)[-1]
        name = ' '.join(str(row.get('beneficiary_name') or '').split())
        if not re.fullmatch(r'Q\d{1,12}', project):
            continue
        if not name or parsers.is_natural_person(name):
            skipped += 1  # LEGAL: osoby fizyczne (także JDG) pomijamy
            continue
        title = ' '.join(str(row.get('operation_name_programme_language') or row.get('operation_name_english') or '').split())
        put('eu_project', project, title=f'{title} - {name}'[:500], text=name[:1000],
            date_value=str(row.get('operation_start_date') or '')[:10] or None,
            source_url=f'https://kohesio.ec.europa.eu/pl/projects/{project}',
            data={'beneficiary': name, 'project': title[:500], 'eu_budget': _money(row.get('project_eu_budget')),
                  'total': _money(row.get('total_eligible_expenditure_amount')), 'currency': 'EUR',
                  'fund': row.get('fund_code', ''), 'programme': row.get('programme_name', ''),
                  'region': row.get('region', ''), 'nuts3': row.get('nuts3_code', ''),
                  'period': row.get('programming_period', ''), 'start': str(row.get('operation_start_date') or '')[:10],
                  'end': str(row.get('operation_end_date') or '')[:10], 'category': row.get('category_label', ''),
                  'license': 'CC0 1.0', **org_link(name)})
    offset = int(job.context['offset'])
    if len(rows) == KOHESIO_PAGE and offset < 400_000:
        enqueue(job.state, kohesio_url(offset + KOHESIO_PAGE), 'kohesio_page', {'offset': offset + KOHESIO_PAGE})
    job.context = {**job.context, 'skipped_people': skipped}
    job.save(update_fields=['context'])


def fts_years(since, today):
    """Plik roczny FTS ukazuje się w połowie następnego roku; pierwszy rok: od since (najwcześniej 2014)."""
    last = today.year - 1 if today.month >= 7 else today.year - 2
    return list(range(max(2014, since.year), last + 1))


FTS_COLUMNS = {
    'name': ('name of beneficiary',), 'vat': ('vat number',), 'country': ('country / territory', 'country'),
    'city': ('city',), 'amount': ("beneficiary's contracted amount", 'beneficiary’s contracted amount',
                                  'contracted amount'),
    'subject': ('subject of grant or contract',), 'programme': ('programme name',), 'year': ('year',),
    'department': ('responsible department',), 'funding': ('funding type',), 'type': ('expense type',),
    'key': ('commitment position key',),
}


def _fts_columns(header):
    columns = {}
    lower = [str(h or '').strip().casefold() for h in header]
    for field, names in FTS_COLUMNS.items():
        for i, h in enumerate(lower):
            if any(h.startswith(n) for n in names) and field not in columns:
                columns[field] = i
    return columns if {'name', 'country'} <= set(columns) else None


def fts_polish(chunks, limit=150_000_000):
    """Plik XLSX FTS (strumień na dysk, odczyt arkusza strumieniowo) -> wiersze z Polski, tylko organizacje."""
    import tempfile
    from zipfile import ZipFile
    from xml.etree.ElementTree import iterparse
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    with tempfile.TemporaryFile() as handle:
        size = 0
        for chunk in chunks:
            size += len(chunk)
            if size > limit:
                raise ValueError('Source response too large')
            handle.write(chunk)
        handle.seek(0)
        with ZipFile(handle) as archive:
            names = archive.namelist()
            sheet = next((n for n in names if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', n)), None)
            if not sheet or sum(i.file_size for i in archive.infolist()) > 2_000_000_000:
                raise ValueError('spreadsheet_expansion_limit')
            shared = []
            if 'xl/sharedStrings.xml' in names:
                with archive.open('xl/sharedStrings.xml') as stream:
                    for _, el in iterparse(stream):
                        if el.tag == ns + 'si':
                            shared.append(''.join(el.itertext()))
                            el.clear()
            rows, columns = [], None
            with archive.open(sheet) as stream:
                for _, el in iterparse(stream):
                    if el.tag != ns + 'row':
                        continue
                    cells = []
                    for cell in el.findall(ns + 'c'):
                        ref = re.fullmatch(r'([A-Z]{1,3})\d+', cell.get('r', ''))
                        column = 0
                        for c in ref[1] if ref else '':
                            column = column * 26 + ord(c) - 64
                        if not column or column > 256:
                            continue
                        cells.extend([''] * (column - len(cells)))
                        value = cell.findtext(ns + 'v', '')
                        if cell.get('t') == 's' and value.isdigit() and int(value) < len(shared):
                            value = shared[int(value)]
                        elif cell.get('t') == 'inlineStr':
                            value = ''.join(t.text or '' for t in cell.iter(ns + 't'))
                        cells[column - 1] = value
                    el.clear()
                    if columns is None:
                        columns = _fts_columns(cells)
                        continue
                    get = lambda f: cells[columns[f]].strip() if f in columns and columns[f] < len(cells) else ''  # noqa: E731
                    if get('country').casefold() not in {'poland', 'pl', 'polska'}:
                        continue
                    name = ' '.join(get('name').split())
                    if not name or parsers.is_natural_person(name) or 'natural person' in name.casefold():
                        continue
                    rows.append({f: get(f) for f in FTS_COLUMNS if f in columns})
    if columns is None:
        raise ValueError('fts_header_missing')
    return rows


def fts_year(job, raw, put):
    year = int(job.context['year'])
    for row in _json(raw, list):
        name = row.get('name', '')
        put('eu_grant', _key(year, row.get('key'), name, row.get('amount'), row.get('subject')),
            title=f"{name}: {row.get('subject') or row.get('programme') or 'budżet UE'}"[:500], text=name,
            date_value=f'{year}-12-31', source_url='https://ec.europa.eu/budget/financial-transparency-system/index.html',
            data={'year': year, 'beneficiary': name, 'vat': row.get('vat', ''), 'city': row.get('city', ''),
                  'amount': _money(row.get('amount')), 'currency': 'EUR', 'subject': row.get('subject', '')[:1000],
                  'programme': row.get('programme', ''), 'department': row.get('department', ''),
                  'funding': row.get('funding', ''), 'license': 'CC BY 4.0', **org_link(name)})


# --- 7. Integrity Watch EU: deklaracje i spotkania europosłów z Polski ----------------------------------------

def _polish_meps():
    from news.public_records_models import PublicRecord
    return set(PublicRecord.objects.filter(source='integrity_watch', kind='mep').values_list('external_id', flat=True))


def iw_meps(job, raw, put):
    from scraper.public_records import EP_TERM
    for row in _json(raw, list):
        epid = str(row.get('epid', ''))
        if row.get('country') != 'Poland' or not epid.isdigit():
            continue
        links = [{'title': ' '.join(str(d.get('title', '')).split())[:200], 'url': parsers.public_url(d['url'])}
                 for d in row.get('DPI_links') or [] if isinstance(d, dict) and str(d.get('url', '')).startswith('https://')]
        put('mep', epid, title=str(row.get('full_name', ''))[:300], source_url=f'https://www.europarl.europa.eu/meps/pl/{epid}',
            persons=[(EP_TERM, int(epid))],
            data={'ep_id': int(epid), 'name': row.get('full_name', ''), 'group': row.get('eugroup', ''),
                  'party': row.get('party', ''), 'committees': row.get('committee') or [], 'declarations': links[:20],
                  'events': int(row.get('events_declaration_num') or 0), 'license': 'ODbL 1.0'})


def iw_income(job, raw, put):
    from scraper.public_records import EP_TERM
    polish = _polish_meps()
    if not polish:
        raise ValueError('integrity_watch_meps_first')
    rows = {}
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        epid = str(row.get('mep_id', '')).strip()
        if epid not in polish:
            continue
        item = rows.setdefault(epid, {'name': row.get('mep_name', ''), 'group': row.get('mep_group', ''), 'activities': []})
        item['activities'].append({
            'type': row.get('activity_type', ''), 'activity': ' '.join(str(row.get('activity', '')).split())[:500],
            'amount': _money(row.get('income_amt_clean')), 'currency': row.get('income_currency', ''),
            'none': bool(row.get('income_none')), 'periodicity': row.get('periodicity_streamlined', ''),
            'total_eur': _money(row.get('income_amt_total_eur_manual') or row.get('income_amt_total_eur_auto'))})
    for epid, item in rows.items():
        paid = [a for a in item['activities'] if a['total_eur']]
        put('mep_income', epid, title=f"{item['name']} - dochody dodatkowe"[:300],
            source_url=f'https://www.integritywatch.eu/mepincomes', persons=[(EP_TERM, int(epid))],
            data={**item, 'paid_activities': len(paid), 'total_eur': round(sum(a['total_eur'] for a in paid), 2),
                  'license': 'ODbL 1.0'})


def meetings_polish(chunks, limit=80_000_000):
    rows = json.loads(_buffer(chunks, limit))
    if not isinstance(rows, list):
        raise ValueError('integrity_watch_meetings_shape')
    keep = ('date', 'epid', 'mep', 'group', 'role', 'title', 'lobbyists', 'location', 'dossier', 'committees')
    return [{k: row.get(k) for k in keep} for row in rows if isinstance(row, dict) and row.get('country') == 'Poland']


def iw_meetings(job, raw, put):
    from scraper.public_records import EP_TERM
    for row in _json(raw, list):
        epid = str(row.get('epid', ''))
        day = _iso(row.get('date'))
        if not epid.isdigit():
            continue
        put('mep_meeting', _key(epid, day, row.get('lobbyists'), row.get('title')),
            title=f"{row.get('mep', '')}: {row.get('lobbyists', '')}"[:500], text=str(row.get('title') or '')[:1000],
            date_value=day, source_url='https://www.integritywatch.eu/mepmeetings', persons=[(EP_TERM, int(epid))],
            data={**{k: row.get(k) for k in ('mep', 'group', 'role', 'title', 'lobbyists', 'location', 'dossier')},
                  'ep_id': int(epid), 'date': day, 'license': 'ODbL 1.0'})


# --- 9. Kilometrówki i sprawozdania biur posłów -----------------------------------------------------------------

def roster_check(member):
    """Kontrola z listą posłów Sejmu: ten sam identyfikator X kadencji i to samo imię i nazwisko."""
    from news.political_models import ParliamentaryRosterEntry
    from scraper.public_records import TERM
    mp_id = _int(member.get('id'))
    entry = ParliamentaryRosterEntry.objects.filter(source='sejm', term=TERM, external_id__in=[str(mp_id), f'{mp_id:03d}']).first() \
        if mp_id else None
    name = f"{member.get('first_name', '')} {member.get('last_name', '')}"
    if not entry:
        return 'brak posła o tym identyfikatorze na liście Sejmu'
    return 'zgodne z listą posłów Sejmu' if _tokens(entry.full_name) == _tokens(name) else 'inne nazwisko na liście Sejmu'


def _export_rows(raw):
    payload = _json(raw, dict)
    rows = payload.get('records')
    if not isinstance(rows, list) or payload.get('term') not in (10, '10'):
        raise ValueError('jakglosuja_export_shape')
    return rows


def mileage_export(job, raw, put):
    for row in _export_rows(raw):
        member = row.get('member') or {}
        mp_id = _int(member.get('id'))
        if not mp_id:
            continue
        name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
        period = str(row.get('period_label') or row.get('period_start') or '')[:20]
        put('mileage', f'{mp_id}/{period}', title=f'{name} - kilometrówki {period}'[:300], people=[mp_id],
            date_value=row.get('period_end'), source_url='https://jakglosuja.pl/dane-otwarte#kilometrowki',
            data={'mp_id': mp_id, 'name': name, 'club': member.get('club', ''), 'period': period,
                  'start': row.get('period_start'), 'end': row.get('period_end'), 'amount_pln': _money(row.get('amount_pln')),
                  'km': round(float(row['km_distance'])) if _money(row.get('km_distance')) is not None else None,
                  'origin': row.get('source_name', ''), 'origin_url': row.get('source_url', ''),
                  'check': roster_check(member), 'license': 'CC BY 4.0 (jakglosuja.pl)'})


def office_export(job, raw, put):
    from scraper.public_records import enqueue
    for row in _export_rows(raw):
        member = row.get('member') or {}
        mp_id, year = _int(member.get('id')), _int(row.get('report_year'))
        if not mp_id or not year:
            continue
        name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
        pdf = str(row.get('pdf_url') or '')
        official = urlsplit(pdf).hostname == 'orka.sejm.gov.pl' and f'{year}{mp_id}' in pdf
        put('office_report', f'{mp_id}/{year}', title=f'{name} - biuro poselskie {year}'[:300], people=[mp_id],
            date_value=f'{year}-12-31', source_url=pdf if official else 'https://jakglosuja.pl/dane-otwarte#sprawozdania',
            data={'mp_id': mp_id, 'name': name, 'club': member.get('club', ''), 'year': year,
                  'total_pln': _money(row.get('total_pln')), 'items': [
                      {'label': str(i.get('label', ''))[:200], 'amount_pln': _money(i.get('amount_pln'))}
                      for i in row.get('items') or [] if isinstance(i, dict)][:30],
                  'pdf_url': pdf, 'check': roster_check(member),
                  'pdf_check': 'oczekuje na PDF Kancelarii Sejmu' if official else 'brak PDF Kancelarii Sejmu',
                  'license': 'CC BY 4.0 (jakglosuja.pl)'})
        if official:
            enqueue(job.state, pdf, 'office_pdf', {'mp_id': mp_id, 'year': year})


def amount_variants(value):
    whole, cents = f'{value:.2f}'.split('.')
    groups = f'{int(whole):,}'
    return {f'{whole},{cents}', f'{whole}.{cents}', groups.replace(',', ' ') + ',' + cents,
            groups.replace(',', ' ') + ',' + cents, groups.replace(',', '.') + ',' + cents}


def office_pdf(job, raw, put):
    """Suma ze sprawozdania jakglosuja.pl porównana z PDF Kancelarii Sejmu (tekst PDF nie jest zapisywany)."""
    from news.public_records_models import PublicRecord
    record = PublicRecord.objects.filter(source='mileage', kind='office_report',
                                         external_id=f"{job.context['mp_id']}/{job.context['year']}").first()
    if record is None:
        return
    try:
        text = parsers.pdf_text(raw)
    except Exception:  # noqa: BLE001 - skan bez warstwy tekstu albo PDF do ręcznego przeglądu
        text = ''
    total = record.data.get('total_pln')
    flat = ' '.join(text.split())
    if not flat:
        result = 'PDF bez warstwy tekstu - nie sprawdzono automatycznie'
    elif total is not None and any(v in flat for v in amount_variants(total)):
        result = 'zgodne z PDF Kancelarii Sejmu'
    else:
        result = 'suma nie znaleziona w PDF Kancelarii Sejmu - do sprawdzenia'
    record.data = {**record.data, 'pdf_check': result, 'pdf_sha256': sha256(raw).hexdigest(),
                   'pdf_checked_at': timezone.now().isoformat(timespec='minutes')}
    record.save(update_fields=['data'])


HANDLERS = {
    'video_index': video_index, 'committee_transcript': committee_transcript,
    'htv_index': htv_index, 'htv_vote': htv_vote, 'wd_query': wd_query,
    'kohesio_page': kohesio_page, 'fts_year': fts_year,
    'iw_meps': iw_meps, 'iw_income': iw_income, 'iw_meetings': iw_meetings,
    'mileage_export': mileage_export, 'office_export': office_export, 'office_pdf': office_pdf,
}
