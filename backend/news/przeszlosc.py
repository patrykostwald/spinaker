"""przeszłość.today, tydzień 1: drzewo powiązań tematu z danych, które już zbieramy (decyzja właściciela 5.10).

Tylko osoby publiczne i podmioty. Krawędzie wyłącznie z potwierdzonych źródeł: posłowie z oficjalnych danych Sejmu,
konta X przez sprawdzony dowód, KRS i artykuły po weryfikacji. Nic nie jest ustalane po samym nazwisku.
Ta sama miara: rządzący i opozycja przechodzą przez identyczne zapytania.
"""
import os
import re

from django.db.models import F, Q

PER_KIND = 30
MEDIA_LIMIT = 100


def enabled():
    return os.environ.get('PRZESZLOSC_ENABLED', '').lower() == 'true'


def terms(query):
    """„CPK, lotnisko” → ['CPK', 'lotnisko']; pojedyncze słowa krótsze niż 3 znaki pomijamy."""
    return [t.strip() for t in re.split(r'[,;|]', query or '') if len(t.strip()) >= 3][:5]


# Rozwinięcia częstych skrótów (wyszukiwanie łapie oba zapisy)
EXPAND = {'cpk': ['Centralny Port Komunikacyjny', 'Centralnego Portu Komunikacyjnego', 'Port Polska', 'Portu Polska', 'Portem Polska'],
          'kpo': ['Krajowy Plan Odbudowy', 'Krajowego Planu Odbudowy'], 'krrit': ['Krajowa Rada Radiofonii', 'Krajowej Rady Radiofonii'],
          'nfz': ['Narodowy Fundusz Zdrowia', 'Narodowego Funduszu Zdrowia'], 'zus': ['Zakład Ubezpieczeń Społecznych', 'Zakładu Ubezpieczeń Społecznych'],
          'oze': ['odnawialnych źródeł', 'odnawialne źródła'],
          'vat': ['podatek od towarów i usług', 'podatku od towarów i usług', 'podatkiem od towarów i usług'],
          'pit': ['podatek dochodowy od osób fizycznych', 'podatku dochodowym od osób fizycznych', 'podatku dochodowego od osób fizycznych'],
          'cit': ['podatek dochodowy od osób prawnych', 'podatku dochodowym od osób prawnych', 'podatku dochodowego od osób prawnych'],
          'mon': ['Ministerstwo Obrony Narodowej', 'Ministra Obrony Narodowej', 'obronie Ojczyzny', 'obrony narodowej'],
          'nato': ['Sojuszu Północnoatlantyckiego', 'Traktatu Północnoatlantyckiego'],
          'cpn': ['paliw', 'stacjach paliw', 'cen paliw', 'Ceny Paliw Niżej'],
          'rcb': ['Rządowe Centrum Bezpieczeństwa', 'Rządowego Centrum Bezpieczeństwa', 'zarządzaniu kryzysowym'],
          'ue': ['Unii Europejskiej', 'Unia Europejska'], 'krs': ['Krajowy Rejestr Sądowy', 'Krajowego Rejestru Sądowego'],
          'tk': ['Trybunał Konstytucyjny', 'Trybunału Konstytucyjnego'], 'sn': ['Sąd Najwyższy', 'Sądu Najwyższego'],
          'pkp': ['Polskie Koleje Państwowe', 'kolei'], 'lpg': ['gazu płynnego', 'autogazu']}


def _stem(word):
    """Polskie odmiany: wspólny początek wyrazu (energia / energii / energią)."""
    word = word.strip()
    if len(word) <= 4 or word.isupper():
        return word
    return word[:max(4, len(word) - 2)]


def _phrase(term):
    """Wszystkie słowa frazy muszą wystąpić (w dowolnej odmianie)."""
    return [_stem(w) for w in re.split(r'\s+', term) if len(w) >= 2]


def _match(fields, words):
    """Fraza użytkownika: słowa w dowolnej odmianie; rozwinięcia skrótów: dokładny zapis (bez szumu jak „raport” dla „Port”)."""
    q = Q()
    for term in words:
        for full in EXPAND.get(term.lower().strip(), []):
            for field in fields:
                q |= Q(**{f'{field}__icontains': full})
        if term.strip().isupper() and len(term.strip()) <= 6:
            for field in fields:
                q |= Q(**{f'{field}__regex': r'(^|[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż])' + re.escape(term.strip()) + r'($|[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż])'})
            continue
        variants = [_phrase(term)]
        for stems in variants:
            for field in fields:
                part = Q()
                for stem in stems:
                    part &= Q(**{f'{field}__icontains': stem})
                q |= part
    return q


EU_FUNDS = {'eu_project': 'Fundusze UE (Kohesio)', 'eu_grant': 'Budżet UE (FTS)'}


def eu_funds(query, limit=12):
    """Dotacje UE w temacie (Kohesio CC0, FTS CC BY 4.0): beneficjenci-organizacje, kwoty i źródło."""
    from news.public_records_models import PublicRecord
    from scraper.nowe_zrodla import LICENSES
    words = terms(query)
    if not words:
        return {'results': [], 'total_eur': 0, 'sources': []}
    rows = (PublicRecord.objects.filter(_match(['title', 'text'], words), kind__in=list(EU_FUNDS))
            .order_by(F('date').desc(nulls_last=True), '-pk')[:limit])
    out = [{'kind': EU_FUNDS[r.kind], 'beneficiary': r.data.get('beneficiary', ''), 'title': (r.data.get('project') or r.data.get('subject') or '')[:300],
            'amount_eur': r.data.get('eu_budget') if r.kind == 'eu_project' else r.data.get('amount'),
            'year': (r.date.year if r.date else None), 'url': r.source_url, 'krs': r.data.get('krs', ''),
            'link': r.data.get('link', '')} for r in rows]
    return {'results': out, 'total_eur': round(sum(x['amount_eur'] or 0 for x in out), 2),
            'sources': [LICENSES['kohesio'], LICENSES['fts']]}


def topic_graph(query):
    from news.material_type import MATERIAL_LABELS, classify_material_type
    from news.clinic import figures_by_account, published_diagnoses
    from news.models import Article
    from news.political_models import (PoliticalPost, PublicFigure, PublicFigureArticleReference,
                                       PublicFigureOrganisationRelation)
    from news.public_records_models import PublicRecord

    words = terms(query)
    nodes, edges = {}, []
    if not words:
        return {'topic': query, 'terms': [], 'nodes': [], 'edges': [], 'counts': {}}

    def node(key, kind, label, **meta):
        label = label or ''
        extra = {'text': label[:4000]} if len(label) > 160 else {}
        nodes.setdefault(key, {'id': key, 'kind': kind, 'label': label[:160], **extra, **meta})
        return key

    def figure(f):
        from news.przeszlosc_osoba import slug
        return node(f'figure:{f.pk}', 'person', f.canonical_name, role=f.role_title, url=f.official_profile_url or f.evidence_url, slug=slug(f))

    # Sejm: druki, głosowania, konsultacje, lobbing - osoby tylko z oficjalnych identyfikatorów posłów
    records = (PublicRecord.objects.filter(_match(['title', 'text'], words))
               .order_by('-date', '-pk').prefetch_related('people__figure')[:PER_KIND])
    seen_titles = set()
    for record in records:
        title_key = (record.title or '').strip().lower()[:120]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        key = node(f'record:{record.pk}', 'record', record.title or f'{record.kind} {record.external_id}',
                   date=record.date.isoformat() if record.date else None, url=record.source_url,
                   sub=EU_FUNDS.get(record.kind, record.kind))
        # Fundusze UE (Kohesio, FTS): beneficjent-organizacja z KRS, gdy nazwa jednoznacznie wskazuje obserwowany podmiot
        org_id = (record.data or {}).get('organisation_id') if record.kind in EU_FUNDS else None
        if org_id:
            org_node = node(f'org:{org_id}', 'organisation', record.data.get('beneficiary', ''), sub=f"KRS {record.data.get('krs', '')}")
            edges.append({'source': org_node, 'target': key, 'label': 'dotacja UE'})
        for person in record.people.all():
            if person.figure_id and not person.figure.archived:
                edges.append({'source': figure(person.figure), 'target': key, 'label': 'w dokumencie'})

    # Wpisy polityków na X i diagnozy Dr. Spina
    posts = list(PoliticalPost.objects.filter(_match(['text'], words), available=True)
                 .select_related('account').order_by('-published_at')[:PER_KIND])
    people = figures_by_account({post.account_id for post in posts})
    diagnoses = {d.post_id: d for d in published_diagnoses().filter(post__in=posts)}
    for post in posts:
        key = node(f'post:{post.pk}', 'statement', post.text, date=post.published_at.date().isoformat(), url=post.url,
                   sub=post.account.display_name, camp=post.camp_at_collection)
        author = people.get(post.account_id)
        who = figure(author) if author else node(f'account:{post.account_id}', 'person', post.account.display_name, institution=True)
        nodes[who].setdefault('camp', post.camp_at_collection)
        edges.append({'source': who, 'target': key, 'label': 'napisał(a)'})
        diagnosis = diagnoses.get(post.pk)
        if diagnosis:
            d = node(f'diagnosis:{diagnosis.pk}', 'diagnosis', diagnosis.headline, url=f'https://spin.clinic/klinika/{diagnosis.pk}',
                     date=post.published_at.date().isoformat(), intensity=diagnosis.intensity)
            edges.append({'source': key, 'target': d, 'label': 'diagnoza Dr. Spina'})

    # Media: artykuły z bazy; osoby tylko przez potwierdzone powiązanie
    articles = list(Article.objects.filter(_match(['title', 'description'], words)).select_related('source')
                    .order_by(F('published_date').desc(nulls_last=True), '-pk')[:MEDIA_LIMIT])
    seen_titles = set()
    visible_article_ids = []
    for article in articles:
        title_key = article.title.strip().lower()[:120]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        visible_article_ids.append(article.pk)
        material_type = classify_material_type(article)
        node(f'article:{article.pk}', 'media', article.title, url=article.url, sub=article.source.name if article.source_id else '',
             date=article.published_date.date().isoformat() if article.published_date else None,
             match_type='automatic', material_type=material_type, kind_label=MATERIAL_LABELS[material_type])
    for ref in (PublicFigureArticleReference.objects.filter(article_id__in=visible_article_ids, verification_status='confirmed')
                .select_related('public_figure')):
        edges.append({'source': figure(ref.public_figure), 'target': f'article:{ref.article_id}', 'label': 'w artykule'})

    # KRS: spółki i fundacje osób, które pojawiły się w temacie (tylko zweryfikowane relacje)
    figure_ids = [int(k.split(':')[1]) for k in nodes if k.startswith('figure:')]
    relations = (PublicFigureOrganisationRelation.objects
                 .filter(public_figure_id__in=figure_ids, verification_status='confirmed', organisation__archived=False)
                 .select_related('organisation')[:PER_KIND * 2])
    for rel in relations:
        org = rel.organisation
        key = node(f'org:{org.pk}', 'organisation', org.name, url=org.official_register_url, sub=f'KRS {org.krs_number}')
        edges.append({'source': f'figure:{rel.public_figure_id}', 'target': key, 'label': rel.organ or rel.public_role})

    counts = {}
    for item in nodes.values():
        counts[item['kind']] = counts.get(item['kind'], 0) + 1
    # najpierw osoby z największą liczbą powiązań
    degree = {}
    for edge in edges:
        degree[edge['source']] = degree.get(edge['source'], 0) + 1
    for key, item in nodes.items():
        item['links'] = degree.get(key, 0) + sum(1 for e in edges if e['target'] == key)
    return {'topic': query, 'terms': words, 'nodes': sorted(nodes.values(), key=lambda n: (-n['links'], n.get('date') or '')),
            'edges': edges, 'counts': counts}


from rest_framework.decorators import api_view, permission_classes  # noqa: E402
from rest_framework.permissions import AllowAny  # noqa: E402
from rest_framework.response import Response  # noqa: E402


VOTE_GROUP = {'YES': 'za', 'NO': 'przeciw', 'ABSTAIN': 'wstrzymał się', 'ABSENT': 'nieobecny', 'NO_VOTE': 'nieobecny',
              'PRESENT': 'obecny, bez głosu', 'VOTE_VALID': 'głos na liście', 'VOTE_INVALID': 'głos nieważny'}


def topic_votes(query, limit=8):
    """Głosowania Sejmu w temacie (właściciel 5.10, funkcja 1 z mapy): wynik zbiorczo, kluby i głosy imienne posłów.
    Dopasowanie po tytule punktu i opisie głosowania; kluby w kolejności wielkości, ta sama skala dla wszystkich."""
    from collections import Counter
    from news.models import ParliamentaryVoting
    words = terms(query)
    if not words:
        return []
    rows = []
    votings = (ParliamentaryVoting.objects.filter(_match(['article__title', 'motion'], words))
               .select_related('article').prefetch_related('ballots').order_by('-article__published_date', '-number')[:limit])
    for v in votings:
        ballots = list(v.ballots.all())
        clubs = Counter(b.club or 'niezrzeszeni' for b in ballots)
        by_club = []
        for club, size in clubs.most_common():
            tally = Counter(VOTE_GROUP.get(b.vote, 'inne') for b in ballots if (b.club or 'niezrzeszeni') == club)
            by_club.append({'club': club, 'size': size, 'votes': dict(tally)})
        when = v.article.published_date
        rows.append({
            'id': f'{v.term}/{v.sitting}/{v.number}', 'title': v.article.title[:300], 'motion': (v.motion or '')[:400],
            'date': when.date().isoformat() if when else None, 'kind': v.kind,
            'result': {k: v.counts.get(k) for k in ('yes', 'no', 'abstain', 'notParticipating') if k in (v.counts or {})},
            'url': (f'https://www.sejm.gov.pl/sejm{v.term}.nsf/agent.xsp?symbol=glosowania&NrKadencji={v.term}'
                    f'&NrPosiedzenia={v.sitting}&NrGlosowania={v.number}'),
            'clubs': by_club,
            'members': sorted([[b.name, b.club or 'niezrzeszeni', VOTE_GROUP.get(b.vote, 'inne')] for b in ballots], key=lambda m: (m[1], m[0])),
            'mp_votes': [[b.mp_id, VOTE_GROUP.get(b.vote, 'inne')] for b in ballots],
        })
    return rows


def link_votes(data):
    """Krawędzie osoba → głosowanie (audyt 6.10: bez nich nie ma drzewa). Tylko posłowie z tematu, połączeni z mandatem
    przez oficjalny identyfikator Sejmu w rejestrze osób (nigdy po nazwisku)."""
    from news.political_models import PublicFigure
    ids = [int(n['id'].split(':')[1]) for n in data['nodes'] if n['id'].startswith('figure:')]
    if not ids or not data.get('votes'):
        return data
    mp = {}
    for f in PublicFigure.objects.filter(pk__in=ids).select_related('parliamentary_roster_entry'):
        e = f.parliamentary_roster_entry
        if e and e.source == 'sejm' and str(e.external_id).isdigit() and e.term:
            mp[(int(e.external_id), e.term)] = f'figure:{f.pk}'
    if not mp:
        return data
    for v in data['votes']:
        term = int(v['id'].split('/')[0])
        key = f"vote:{v['id']}"
        linked = False
        for mp_id, vote in v.get('mp_votes', []):
            who = mp.get((mp_id, term))
            if who:
                if not linked:
                    data['nodes'].append({'id': key, 'kind': 'vote', 'label': v['title'][:160], 'date': v['date'], 'url': v['url'], 'links': 0})
                    linked = True
                data['edges'].append({'source': who, 'target': key, 'label': f'głosował(a): {vote}'})
    for v in data['votes']:
        v.pop('mp_votes', None)
    return data


@api_view(['GET'])
@permission_classes([AllowAny])
def topic_view(request):
    """GET /api/przeszlosc/temat/?q=CPK - wyłączone, dopóki PRZESZLOSC_ENABLED nie jest true."""
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    query = request.query_params.get('q', '')[:120]
    if not terms(query):
        return Response({'detail': 'Podaj temat (co najmniej 3 znaki).'}, status=400)
    from django.core.cache import cache
    from django.db import connection
    key = 'przeszlosc:v2:' + query.lower()
    data = cache.get(key) if connection.vendor == 'postgresql' else None
    if data is None:
        data = topic_graph(query)
        data['votes'] = topic_votes(query)
        data['eu_funds'] = eu_funds(query)
        link_votes(data)
        if data['votes']:
            data['counts']['vote'] = len(data['votes'])
        if connection.vendor == 'postgresql':
            cache.set(key, data, 600)
    from news.przeszlosc_dostep import access, has
    data = {**data, 'access': access(request)}
    if not has('money_trail', request):
        data.pop('eu_funds', None)  # ślad pieniędzy to funkcja Pro (po becie); w becie otwarta dla wszystkich
    return Response(data)


KIND_LABELS = {'print': 'Druk sejmowy', 'ballot': 'Głosowanie', 'voting': 'Głosowanie', 'consultation': 'Konsultacje',
               'lobby_activity': 'Lobbing', 'lobby_document': 'Lobbing', 'financial_document': 'Finanse', 'financial_row': 'Finanse',
               'interpellation': 'Interpelacja'}


SOURCE_LABELS = {'sejm': 'Sejm', 'senat': 'Senat', 'lobbying': 'Lobbing', 'rcl': 'Projekt rządowy', 'krs': 'KRS', 'mf': 'Finanse publiczne',
                 'gov': 'Rząd', 'consultations': 'Konsultacje', 'eli': 'Dziennik Ustaw'}


def start_data():
    """Strona główna przeszłość.today: co jest w bazie i co nowego w Sejmie (same zbiorcze liczby i dokumenty publiczne)."""
    from news.clinic import published_diagnoses
    from news.models import Article
    from news.political_models import PoliticalPost, PublicFigure, PublicFigureOrganisationRelation
    from news.public_records_models import PublicRecord
    latest, seen = [], set()
    # najpierw dokumenty z datą (w Postgresie puste daty stały na górze); bez daty liczy się dzień pobrania (audyt 6.10)
    from django.db.models import F
    for r in PublicRecord.objects.exclude(title='').order_by(F('date').desc(nulls_last=True), '-fetched_at', '-pk')[:80]:
        key = r.title.strip().lower()[:120]
        if key not in seen:
            seen.add(key)
            latest.append(r)
        if len(latest) == 6:
            break
    return {
        'counts': {
            'people': PublicFigure.objects.filter(archived=False).count(),
            'organisations': PublicFigureOrganisationRelation.objects.filter(verification_status='confirmed').values('organisation').distinct().count(),
            'records': PublicRecord.objects.count(),
            'posts': PoliticalPost.objects.count(),
            'diagnoses': published_diagnoses().count(),
            'articles': Article.objects.count(),
        },
        'latest': [{'title': r.title[:180], 'date': (r.date or r.fetched_at.date()).isoformat(),
                    'kind': KIND_LABELS.get(r.kind) or SOURCE_LABELS.get(r.source, 'Dokument'),
                    'url': r.source_url} for r in latest],
        'topics_enabled': enabled(),
        'auto_topics': [{'topic': t['topic'], 'edges': t['edges']} for t in auto_topics()],
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def start_view(request):
    from django.core.cache import cache
    from django.db import connection
    data = cache.get('przeszlosc:start') if connection.vendor == 'postgresql' else None
    if data is None:
        data = start_data()
        if connection.vendor == 'postgresql':
            cache.set('przeszlosc:start', data, 600)
    from news.przeszlosc_dostep import access
    return Response({**data, 'access': access(request)})


def topic_rss(query):
    """Kanał RSS tematu (alerty bez konta, właściciel 6.10): najnowsze wpisy, dokumenty Sejmu i artykuły w temacie,
    każdy z datą i odnośnikiem do źródła. Czytnik RSS albo skrzynka z obsługą RSS daje powiadomienie o nowościach."""
    from xml.sax.saxutils import escape
    graph = topic_graph(query)
    kinds = {'statement': 'Wpis', 'record': 'Sejm', 'media': 'Artykuł', 'diagnosis': 'Diagnoza Dr. Spina'}
    rows = sorted((n for n in graph['nodes'] if n['kind'] in kinds and n.get('date')), key=lambda n: n['date'], reverse=True)[:40]
    page = 'https://spin.clinic/przeszlosc?q=' + escape(query)
    items = []
    for n in rows:
        title = kinds[n['kind']] + (' · ' + n['sub'] if n.get('sub') else '') + ': ' + n['label'][:140]
        items.append(f"<item><title>{escape(title)}</title><link>{escape(n.get('url') or page)}</link>"
                     f"<guid isPermaLink='false'>{escape(n['id'])}</guid><pubDate>{n['date']}</pubDate>"
                     f"<description>{escape(n['label'])}</description></item>")
    head = (f"<title>{escape('przeszłość.today: ' + query)}</title><link>{page}</link>"
            f"<description>{escape('Nowe wpisy, dokumenty Sejmu i artykuły w temacie: ' + query)}</description><language>pl</language>")
    return '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>' + head + ''.join(items) + '</channel></rss>'


@api_view(['GET'])
@permission_classes([AllowAny])
def rss_view(request):
    """GET /api/przeszlosc/rss/?q=CPK - kanał RSS tematu."""
    from django.http import HttpResponse
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    query = request.query_params.get('q', '')[:120]
    if not terms(query):
        return Response({'detail': 'Podaj temat (co najmniej 3 znaki).'}, status=400)
    return HttpResponse(topic_rss(query), content_type='application/rss+xml; charset=utf-8')


# --- automatyczny wybór tematów (właściciel 5.10: „sam wybierz, to ma być też zautomatyzowane”) ---
TOPICS_STATE = 'przeszlosc-auto-topics'
PRINT_SUBJECT = re.compile(r'ustaw\w*\s+o\s+(?:zmianie\s+(?:niektórych\s+)?ustaw\w*\s+(?:w\s+związku\s+z\s+)?(?:o\s+)?)?([^,(;]{6,60})', re.I)
ACRONYM = re.compile(r'\b([A-ZĄĆĘŁŃÓŚŹŻ]{2,6})\b')
STOP = {'PIS', 'PO', 'PSL', 'KO', 'TVN', 'RP', 'UE', 'USA', 'AI', 'PAP', 'ON', 'TO', 'NIE', 'JEST', 'PL', 'II', 'III', 'NA', 'KE', 'OK', 'TAK',
        'UWAGA', 'PILNE', 'ME', 'MSZ', 'TVP', 'KPRM', 'SEJM', 'RM', 'ŻE', 'JAK', 'CO', 'ALE', 'DLA', 'PO', 'BO', 'TU', 'WAŻNE', 'STOP', 'NOWE', 'TAK', 'BRAWO', 'HIT'}


def candidates(days=45, limit=24):
    """Kandydaci: przedmioty najnowszych ustaw z druków i skróty najczęstsze we wpisach polityków."""
    from collections import Counter
    from datetime import timedelta
    from django.utils import timezone
    from news.political_models import PoliticalPost
    from news.public_records_models import PublicRecord
    since = timezone.now() - timedelta(days=days)
    subjects = Counter()
    for title in PublicRecord.objects.filter(fetched_at__gte=since).exclude(title='').values_list('title', flat=True)[:3000]:
        m = PRINT_SUBJECT.search(title)
        if m:
            subject = ' '.join(m.group(1).strip(' -–—"„”').split()[:4])
            if len(subject) >= 5 and not subject.lower().startswith(('zmianie', 'niektórych')):
                subjects[subject] += 1
    acronyms = Counter()
    for text in PoliticalPost.objects.filter(published_at__gte=since).values_list('text', flat=True)[:5000]:
        for a in set(ACRONYM.findall(text)):
            if a not in STOP:
                acronyms[a] += 1
    pool = [x for x, _ in subjects.most_common(limit // 2)] + [a for a, n in acronyms.most_common(limit) if n >= 3][:limit // 2]
    return list(dict.fromkeys(pool))


def score(graph):
    kinds = set(graph['counts'])
    return (len(graph['edges']) * 3 + len(kinds) * 5 + min(graph['counts'].get('record', 0), 10) * 2
            + graph['counts'].get('diagnosis', 0) * 4)


def pick_topics(top=6):
    """Raz dziennie: ocenia kandydatów po bogactwie drzewa i zapisuje najlepsze tematy (ta sama reguła dla wszystkich)."""
    from django.utils import timezone
    from news.models import ImportState
    from news.przeszlosc_osoba import remember_topics
    rows, people = [], {}
    for term in candidates():
        graph = topic_graph(term)
        if len(graph['edges']) >= 3 and len(graph['counts']) >= 3:
            rows.append({'topic': term, 'score': score(graph), 'counts': graph['counts'], 'edges': len(graph['edges'])})
            people[term] = [int(n['id'].split(':')[1]) for n in graph['nodes'] if n['id'].startswith('figure:')]
    rows.sort(key=lambda r: -r['score'])
    # kto występował w tematach dnia: dowód współwystępowania na profilu osoby (Wspólne mianowniki)
    remember_topics([{'topic': r['topic'], 'people': people[r['topic']]} for r in rows[:max(top, 12)]])
    state, _ = ImportState.objects.get_or_create(name=TOPICS_STATE)
    state.cursor = {'at': timezone.now().isoformat(timespec='minutes'), 'topics': rows[:top]}
    state.save(update_fields=['cursor'])
    return rows[:top]


def auto_topics():
    from news.models import ImportState
    state = ImportState.objects.filter(name=TOPICS_STATE).first()
    return (state.cursor or {}).get('topics', []) if state else []
