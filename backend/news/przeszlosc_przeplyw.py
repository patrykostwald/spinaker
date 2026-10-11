"""Drzewo przepływu v1: wyłącznie lokalne, potwierdzone dane i jawne hipotezy nazwowe.

Poziom oznacza rolę w widoku, nie kierunek krawędzi. Źródła pieniędzy
prowadzą do kanału, a kanał do odbiorcy, także gdy odbiorca jest korzeniem.
"""
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime

from django.core.cache import cache
from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from news import drzewo_pieniedzy as money
from news import przeszlosc_osoba as person

VERSION = 'v1'
CACHE_SECONDS = 86400
MAX_NODES = 300
MAX_EDGES = 600
CATEGORIES = {'nieruchomosci': 'Nieruchomości', 'spolki': 'Spółki',
              'dotacje': 'Dotacje i fundusze', 'zamowienia': 'Zamówienia publiczne',
              'polityka': 'Polityka i lobbing', 'orzeczenia': 'Orzeczenia'}
AVAILABLE = {'spolki', 'dotacje', 'zamowienia', 'polityka'}
EXTRA_SOURCES = {
    'sejm': {'label': 'Kancelaria Sejmu', 'license': 'informacja publiczna', 'url': 'https://api.sejm.gov.pl/'},
    'profile': {'label': 'Rejestr osób publicznych', 'license': 'metadane własne przeszłość.today', 'url': '/przeszlosc'},
    'x': {'label': 'X - wpis autora', 'license': 'prawa autora; krótki cytat i odnośnik', 'url': 'https://x.com/'},
    'media': {'label': 'Materiał wydawcy', 'license': 'prawa wydawcy; metadane i odnośnik', 'url': ''},
    'spin': {'label': 'Dr. Spin', 'license': 'materiał własny spin.clinic', 'url': 'https://spin.clinic/'},
}


def iso(value):
    if isinstance(value, datetime):
        return (timezone.localtime(value) if timezone.is_aware(value) else value).date().isoformat()
    return value.isoformat() if value else None


def source(key, url=None, retrieved_at=None):
    from scraper.nowe_zrodla import LICENSES
    definition = money.SOURCES.get(key) or LICENSES.get(key) or EXTRA_SOURCES[key]
    return {'key': key, 'label': definition['label'], 'license': definition['license'],
            'url': url or definition['url'],
            'retrieved_at': retrieved_at.isoformat() if retrieved_at else None}


def options(params):
    categories = sorted(set(params.get('kategorie', ','.join(AVAILABLE)).split(',')))
    if not set(categories) <= set(CATEGORIES):
        raise ValueError('Nieznana kategoria.')
    depth = params.get('glebokosc', '2')
    if depth not in ('1', '2', '3'):
        raise ValueError('Głębokość musi wynosić od 1 do 3.')
    flags = [params.get(key, '0') for key in ('narracja', 'pokaz_niepowiazane', 'cala_historia')]
    if any(flag not in ('0', '1') for flag in flags):
        raise ValueError('Przełączniki przyjmują 0 lub 1.')
    dates = []
    for key in ('od', 'do'):
        value = params.get(key)
        if value:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value:
                raise ValueError('Data musi mieć format YYYY-MM-DD.')
        dates.append(value or None)
    if all(dates) and dates[0] > dates[1]:
        raise ValueError('Data od nie może być późniejsza niż data do.')
    return {'categories': categories, 'depth': int(depth), 'start': dates[0], 'end': dates[1],
            'narrative': flags[0] == '1', 'unlinked': flags[1] == '1', 'whole_history': flags[2] == '1'}


class Graph:
    def __init__(self, opts):
        self.opts = opts
        self.nodes = {}
        self.edges = {}
        self.grouped = Counter()
        self.omitted = set()
        # Okresy funkcji osoby w spółkach (P0-2): {org.pk: [(since, until)]}; None = korzeń to spółka.
        self.tenures = None

    def in_dates(self, value):
        day = iso(value)
        return (not self.opts['start'] or day and day >= self.opts['start']) and (
            not self.opts['end'] or day and day <= self.opts['end'])

    def node(self, ident, kind, label, level, category, provenance, *, day=None,
             amount=None, currency=None, certainty='identifier', url=None, meta=None, structural=False):
        if ident in self.nodes:
            return ident
        if level > self.opts['depth'] or (level and not structural and not self.in_dates(day)):
            return None
        if certainty == 'name_only' and not self.opts['unlinked']:
            return None
        if len(self.nodes) >= MAX_NODES:
            if ident not in self.omitted:
                self.omitted.add(ident)
                self.grouped[(category, kind, certainty)] += 1
            return None
        # No raw record JSON is ever serialized, particularly private names/identifiers.
        if kind == 'person_anon':
            label, url, meta = 'osoba fizyczna', None, {}
        label = str(label or '')[:300]
        if amount is not None:
            amount = money._amount(amount)
            if amount is not None and not math.isfinite(amount):
                amount = None
        # Unverified amounts cannot be accidentally summed by a client.
        if certainty == 'name_only':
            amount, currency = None, None
        self.nodes[ident] = {'id': ident, 'kind': kind, 'label': label,
            'short': label if len(label) <= 28 else label[:27] + '…', 'level': level,
            'category': category, 'date': iso(day), 'amount': amount, 'currency': currency or None,
            'certainty': certainty, 'source': provenance, 'url': url, 'meta': meta or {}}
        return ident

    def edge(self, start, end, label, provenance, *, since=None, until=None, amount=None,
             currency=None, certainty='identifier', suffix=''):
        if start not in self.nodes or end not in self.nodes or start == end:
            return
        ident = hashlib.sha256(f'{start}|{end}|{label}|{suffix}'.encode()).hexdigest()[:24]
        if ident in self.edges:
            return
        if len(self.edges) >= MAX_EDGES:
            if ident not in self.omitted:
                self.omitted.add(ident)
                self.grouped[(self.nodes[end]['category'], 'edge', certainty)] += 1
            return
        self.edges[ident] = {'id': ident, 'from': start, 'to': end, 'label': label,
            'date_from': iso(since), 'date_to': iso(until),
            'amount': amount if certainty != 'name_only' else None,
            'currency': currency or None, 'source_key': provenance['key'], 'certainty': certainty}

    def finish(self, root):
        counts = Counter('polityka' if n['category'] == 'media' else n['category']
                         for n in self.nodes.values() if n['level'] and n['certainty'] != 'name_only')
        return {'root': {key: self.nodes[root][key] for key in ('id', 'kind', 'label', 'url')},
            'nodes': list(self.nodes.values()), 'edges': list(self.edges.values()),
            'categories': [{'key': k, 'label': label, 'count': counts[k] if k in AVAILABLE else 0,
                            'available': k in AVAILABLE} for k, label in CATEGORIES.items()],
            'timeline': sorted([{'date': n['date'], 'node_id': n['id'], 'kind': n['kind'],
                                'label': n['label'], 'category': n['category']}
                               for n in self.nodes.values() if n['date']], key=lambda x: (x['date'], x['node_id'])),
            'signals': [], 'limits': {'max_nodes': MAX_NODES, 'max_edges': MAX_EDGES,
                'truncated': bool(self.grouped), 'grouped': [
                    {'id': f'group:{cat}:{kind}:{certainty}',
                     'label': f'{count} pominiętych elementów' + (' (niepowiązane)' if certainty == 'name_only' else ''),
                     'count': count, 'category': cat, 'kind': kind}
                    for (cat, kind, certainty), count in sorted(self.grouped.items())]},
            'legal': {'notes': [money.NOTE, 'Dopasowania po nazwie są niepowiązane i pozostają poza kwotami oraz licznikami kategorii.',
                       'Poziomy oznaczają rolę w widoku; strzałki pokazują kierunek przepływu.'],
                      'narrative': self.opts['narrative']},
            'generated_at': timezone.now().isoformat()}


def org_node(graph, org, level):
    info = money.organisation(org)
    return graph.node(f'org:{org.pk}', 'organisation', info['name'], level, 'spolki',
                      source('krs', info['url'], org.source_checked_at),
                      url=f'/przeszlosc/spolka/{org.krs_number}', structural=True)


def figure_node(graph, figure, level):
    return graph.node(f'figure:{figure.pk}', 'person', figure.canonical_name, level,
                      'polityka' if level == 0 else 'spolki', source('profile', figure.evidence_url),
                      url=f'/przeszlosc/osoba/{person.slug(figure)}', structural=True)


def relations(graph, *, figure=None, organisations=None):
    from news.political_models import PublicFigureOrganisationRelation
    rows = PublicFigureOrganisationRelation.objects.filter(
        verification_status='confirmed', public_figure__archived=False,
        public_figure__merged_into__isnull=True, organisation__archived=False)
    rows = rows.filter(public_figure=figure) if figure else rows.filter(organisation_id__in=organisations)
    if graph.opts['start']:
        rows = rows.filter(Q(until__isnull=True) | Q(until__gte=graph.opts['start']))
    if graph.opts['end']:
        rows = rows.filter(Q(since__isnull=True) | Q(since__lte=graph.opts['end']))
    orgs = {}
    if figure:
        graph.tenures = defaultdict(list)
    for rel in rows.select_related('organisation', 'public_figure').order_by('pk').iterator():
        org = rel.organisation
        if figure:
            graph.tenures[org.pk].append((rel.since, rel.until))
        org_id = org_node(graph, org, 1) if figure else f'org:{org.pk}'
        who = f'figure:{figure.pk}' if figure else figure_node(graph, rel.public_figure, 3)
        graph.edge(who, org_id, 'pełni funkcję w KRS', source('krs', rel.evidence_url),
                   since=rel.since, until=rel.until, certainty='manual', suffix=str(rel.pk))
        if org_id in graph.nodes:
            orgs[org.pk] = org
    return orgs


def dated(rows, opts, field='date'):
    if opts['start']:
        rows = rows.filter(**{f'{field}__gte': opts['start']})
    if opts['end']:
        rows = rows.filter(**{f'{field}__lte': opts['end']})
    return rows


def bounded(graph, rows, category, kind, certainty='identifier'):
    """One aggregate plus a bounded SELECT, even for decades of political history."""
    count = rows.count()
    if count > MAX_NODES:
        graph.grouped[(category, kind, certainty)] += count - MAX_NODES
    return rows[:MAX_NODES]


def in_tenure(day, windows):
    """Czy data mieści się w którymś okresie funkcji (brak początku lub końca = otwarty).

    Brak daty rekordu nie dowodzi niczego: przechodzi tylko okres w pełni otwarty (bez znanych granic)."""
    if day is None:
        return any(since is None and until is None for since, until in windows)
    day = day.date() if isinstance(day, datetime) else day
    return any((since is None or since <= day) and (until is None or day <= until) for since, until in windows)


def finance(graph, organisations):
    """Batch source queries. JSON residual checks never replace identifier validation."""
    from news.public_records_models import PublicRecord
    by_id = defaultdict(set)
    by_nip = defaultdict(set)
    for org in organisations.values():
        for key, value in money.identifiers(org).items():
            by_id[value].add(org.pk)
            if key == 'NIP':
                by_nip[value].add(org.pk)
    for key, kind, field, category, index in (
        ('ted', 'notice', 'winners', 'zamowienia', by_id),
        ('bzp', 'notice', 'organizationNationalId', 'zamowienia', by_nip),
        ('fts', 'eu_grant', 'vat', 'dotacje', by_nip),
        ('kohesio', 'eu_project', None, 'dotacje', {}),
    ):
        if category not in graph.opts['categories']:
            continue
        needles = []
        for ident in index:
            for variant in money.variants(ident):
                needles.append(Q(**{f'data__{field}__icontains': variant}))
        if graph.opts['unlinked'] and key in ('fts', 'kohesio'):
            needles.append(Q(data__organisation_id__in=list(organisations)))
        if not needles:
            continue
        # UNION bounds each expression tree for SQLite, also deduplicating records
        # matching several identifiers. One SQL statement, not one query per company.
        batches = []
        for offset in range(0, len(needles), 100):
            query = Q(pk__in=[])
            for clause in needles[offset:offset + 100]:
                query |= clause
            batches.append(dated(PublicRecord.objects.filter(query, source=key, kind=kind), graph.opts).order_by())
        records = batches[0].union(*batches[1:]) if len(batches) > 1 else batches[0]
        for record in records.order_by(F('date').desc(nulls_last=True), '-pk').iterator():
            data = record.data or {}
            private_names = [w.get('name') for w in data.get('winners') or []
                             if w.get('osoba_fizyczna') and w.get('name')]
            def safe_label(value):
                text = str(value or '')
                for name in private_names:
                    text = re.sub(re.escape(name), 'osoba fizyczna', text, flags=re.IGNORECASE)
                return text
            hits = set()
            if key == 'ted':
                for winner in data.get('winners') or []:
                    if not winner.get('osoba_fizyczna'):
                        hits.update(index.get(money.digits(winner.get('id')), set()))
            elif field:
                hits.update(index.get(money.digits(data.get(field)), set()))
            certainty = 'identifier'
            if not hits:
                hinted = data.get('organisation_id')
                if not graph.opts['unlinked'] or hinted not in organisations:
                    continue
                hits = {hinted}
                certainty = 'name_only'
            outside = False
            if graph.tenures is not None:
                # P0-2: w drzewie osoby pieniądze spółki tylko z okresu jej funkcji (chyba że włączono całą historię).
                inside = {pk for pk in hits if in_tenure(record.date, graph.tenures.get(pk, []))}
                if not graph.opts['whole_history']:
                    hits = inside
                    if not hits:
                        continue
                outside = hits != inside
            provenance = source(key, record.source_url, record.fetched_at)
            if graph.opts['depth'] == 1:
                if key in ('ted', 'fts') and certainty == 'identifier':
                    label = '; '.join(data.get('buyer') or []) if key == 'ted' else 'Komisja Europejska'
                    authority = graph.node(f'authority:{key}:{record.pk}', 'authority', safe_label(label) or 'Zamawiający',
                        1, category, provenance, structural=True, url=record.source_url,
                        meta={'channel_level': 2})
                    for pk in sorted(hits):
                        graph.edge(authority, f'org:{pk}', 'zamówienie - kanał na poziomie 2' if key == 'ted'
                                   else 'dotacja - kanał na poziomie 2', provenance, since=record.date)
                continue
            node_kind = 'contract' if category == 'zamowienia' else 'grant'
            amount = data.get('value') if key == 'ted' else data.get('amount') if key == 'fts' else data.get('eu_budget') if key == 'kohesio' else None
            currency = (data.get('currency') or None) if key == 'ted' else 'EUR' if category == 'dotacje' else None
            channel = graph.node(f'{key}:{record.pk}', node_kind,
                safe_label(data.get('subject') or data.get('project') or record.title), 2, category, provenance,
                day=record.date, amount=amount, currency=currency, certainty=certainty, url=record.source_url)
            if not channel:
                continue
            if outside:
                graph.nodes[channel]['meta'] = {**graph.nodes[channel]['meta'], 'outside_tenure': True}
            if money.amount_suspect(graph.nodes[channel]['amount']):
                # Kwota nierealna (P0-1): węzeł zostaje, ale bez kwoty, z flagą w meta.
                graph.nodes[channel]['amount'] = None
                graph.nodes[channel]['meta'] = {**graph.nodes[channel]['meta'], 'amount_suspect': True}
            amount = graph.nodes[channel]['amount']
            for pk in sorted(hits):
                org_id = f'org:{pk}'
                start, end = (org_id, channel) if key == 'bzp' else (channel, org_id)
                graph.edge(start, end, 'zamawia' if key == 'bzp' else 'wykonawca' if key == 'ted' else 'beneficjent',
                           provenance, since=record.date, amount=None if key == 'ted' else amount,
                           currency=currency, certainty=certainty)
            if key != 'bzp' and certainty == 'identifier':
                # Buyer identity is unavailable in our TED payload. Keep a record-local authority,
                # never merge different authorities on their textual name.
                label = '; '.join(data.get('buyer') or []) if key == 'ted' else 'Komisja Europejska'
                authority = graph.node(f'authority:{key}:{record.pk}', 'authority', safe_label(label) or 'Zamawiający',
                    1, category, provenance, structural=True, url=record.source_url)
                graph.edge(authority, channel, 'zamawia' if key == 'ted' else 'finansuje', provenance,
                           since=record.date, amount=amount, currency=currency)
            if key == 'ted' and graph.opts['depth'] == 3:
                for position, winner in enumerate(data.get('winners') or []):
                    if winner.get('osoba_fizyczna'):
                        anonymous = graph.node(f'anon:ted:{record.pk}:{position}', 'person_anon', '', 3,
                                               category, provenance, structural=True)
                        graph.edge(channel, anonymous, 'wykonawca', provenance, since=record.date)


def politics(graph, figure):
    from news.political_models import PoliticalPost, PublicFigureArticleReference
    from news.public_records_models import PublicRecord, PublicRecordPerson
    from scraper.public_records import SEJM_SOURCES
    identities = person.mp_identities(figure)
    identity_query = Q(figure=figure)
    for term, mp_id in identities:
        identity_query |= Q(term=term, mp_id=mp_id)
    linked = PublicRecordPerson.objects.filter(identity_query).values('record_id')
    records = dated(PublicRecord.objects.filter(pk__in=linked, source__in=SEJM_SOURCES | {'sejm'})
                    .exclude(kind__in=person.MEMBERSHIP_KINDS), graph.opts)
    if graph.opts['depth'] == 1:
        records = records.exclude(kind__in=('vote', 'voting', 'ballot'))
    # Separate kinds preserve truthful overflow counts without reading full records.
    records = records.order_by(F('date').desc(nulls_last=True), '-pk')
    selected_records = list(records[:MAX_NODES])
    totals = records.order_by().values('kind').annotate(n=Count('pk'))
    loaded = Counter(r.kind for r in selected_records)
    def record_kind(kind):
        return 'vote' if kind in ('vote', 'voting', 'ballot') else 'statement' if kind in ('statement', 'committee_speech') else 'document'
    for total in totals:
        kind = record_kind(total['kind'])
        if kind != 'vote' or graph.opts['depth'] >= 2:
            graph.grouped[('polityka', kind, 'identifier')] += total['n'] - loaded[total['kind']]
    for record in selected_records:
        kind = 'vote' if record.kind in ('vote', 'voting', 'ballot') else 'statement' if record.kind in ('statement', 'committee_speech') else 'document'
        provenance = source('sejm', record.source_url, record.fetched_at)
        target = graph.node(f'record:{record.pk}', kind, record.title or person.RECORD_LABEL.get(record.kind, person.DOCUMENT_LABEL),
                            2 if kind == 'vote' else 1, 'polityka', provenance, day=record.date, url=record.source_url)
        graph.edge(f'figure:{figure.pk}', target, 'w dokumencie', provenance, since=record.date)
    if graph.opts['depth'] >= 2:
        ballots = dated(person._ballots(identities), graph.opts, 'voting__article__published_date__date')
        for ballot in bounded(graph, ballots.select_related('voting__article').order_by('-voting_id'), 'polityka', 'vote'):
            vote = ballot.voting
            day = vote.article.published_date
            provenance = source('sejm', person.vote_url(vote))
            target = graph.node(f'vote:{vote.pk}', 'vote', vote.motion or vote.article.title, 2, 'polityka',
                                provenance, day=day, url=person.vote_url(vote), meta={'vote': person.VOTE_LABEL.get(ballot.vote, 'inne')})
            graph.edge(f'figure:{figure.pk}', target, 'głosuje', provenance, since=day)
    accounts = [account for account, _ in person.x_accounts(figure)]
    posts = dated(PoliticalPost.objects.filter(account__in=accounts, available=True), graph.opts, 'published_at__date')
    shown_posts = []
    for post in bounded(graph, posts.order_by('-published_at', '-pk'), 'polityka', 'statement'):
        provenance = source('x', post.url, post.fetched_at)
        target = graph.node(f'post:{post.pk}', 'statement', post.text[:160], 1, 'polityka', provenance,
                            day=post.published_at, url=post.url)
        graph.edge(f'figure:{figure.pk}', target, 'publikuje wpis', provenance, since=post.published_at)
        if target:
            shown_posts.append(post.pk)
    if graph.opts['narrative'] and graph.opts['depth'] >= 2:
        from news.clinic import published_diagnoses
        for diagnosis in published_diagnoses().filter(post_id__in=shown_posts).order_by('pk'):
            url = f'https://spin.clinic/klinika/{diagnosis.pk}'
            provenance = source('spin', url, diagnosis.diagnosed_at)
            target = graph.node(f'diagnosis:{diagnosis.pk}', 'diagnosis', 'Diagnoza Dr. Spina', 2, 'polityka', provenance,
                                day=diagnosis.post.published_at, url=url, meta={'intensity': diagnosis.intensity})
            graph.edge(f'post:{diagnosis.post_id}', target, 'diagnoza Dr. Spina', provenance, since=diagnosis.post.published_at)
    if graph.opts['depth'] < 3:
        return
    refs = PublicFigureArticleReference.objects.filter(public_figure=figure, verification_status='confirmed', article__source__is_active=True)
    refs = dated(refs, graph.opts, 'article__published_date__date')
    refs = refs.order_by().values('article_id').distinct()
    from news.models import Article
    articles = Article.objects.filter(pk__in=refs).select_related('source').order_by('-published_date', 'pk')
    for article in bounded(graph, articles, 'media', 'media', 'manual'):
        provenance = source('media', article.url)
        provenance['label'] = article.source.name
        target = graph.node(f'article:{article.pk}', 'media', article.title, 3, 'media', provenance,
                            day=article.published_date, url=article.url, certainty='manual')
        graph.edge(f'figure:{figure.pk}', target, 'w materiale', provenance, since=article.published_date, certainty='manual')
    if graph.opts['unlinked']:
        from news.media_mentions import mentions_data
        for row in mentions_data(figure)['results']:
            provenance = source('media', row['url'])
            provenance['label'] = row['source']
            target = graph.node(f'article:{row["id"]}', 'media', row['title'], 3, 'media', provenance,
                                day=row['published_date'], url=row['url'], certainty='name_only')
            graph.edge(f'figure:{figure.pk}', target, 'zbieżność nazwy w metadanych', provenance,
                       since=row['published_date'], certainty='name_only')


def build(root_object, is_person, opts):
    graph = Graph(opts)
    root = figure_node(graph, root_object, 0) if is_person else org_node(graph, root_object, 0)
    orgs = {}
    if is_person:
        # Structural companies remain when their financial category is selected.
        if set(opts['categories']) & {'spolki', 'dotacje', 'zamowienia'}:
            orgs = relations(graph, figure=root_object)
        if 'polityka' in opts['categories']:
            politics(graph, root_object)
    else:
        orgs = {root_object.pk: root_object}
    if orgs:
        finance(graph, orgs)
    if opts['depth'] == 3 and 'spolki' in opts['categories'] and orgs:
        relations(graph, organisations=orgs)
    graph.grouped = +graph.grouped  # Counter discards zero counts.
    return graph.finish(root)


def cache_is_public(data, root_object, is_person):
    """Recheck publication gates even after bulk updates, which bypass Django signals."""
    from news.political_models import (PublicFigure, RegisteredOrganisation, PoliticalPost,
                                       PublicFigureOrganisationRelation, PublicFigureArticleReference)
    from news.models import Article
    from news.clinic import published_diagnoses
    nodes = data['nodes']
    def ids(prefix):
        return {int(n['id'].split(':')[1]) for n in nodes if n['id'].startswith(prefix + ':')}
    figures, orgs, posts, diagnoses, articles = (ids(p) for p in ('figure', 'org', 'post', 'diagnosis', 'article'))
    if figures and PublicFigure.objects.filter(pk__in=figures, archived=False, merged_into__isnull=True).count() != len(figures):
        return False
    if orgs and RegisteredOrganisation.objects.filter(pk__in=orgs, archived=False).count() != len(orgs):
        return False
    if posts:
        accounts = [account.pk for account, _ in person.x_accounts(root_object)] if is_person else []
        if PoliticalPost.objects.filter(pk__in=posts, available=True, account_id__in=accounts).count() != len(posts):
            return False
    if diagnoses and published_diagnoses().filter(pk__in=diagnoses).count() != len(diagnoses):
        return False
    krs_edges = {e['id'] for e in data['edges'] if e['label'] == 'pełni funkcję w KRS'}
    if krs_edges:
        rels = PublicFigureOrganisationRelation.objects.filter(public_figure_id__in=figures,
                   organisation_id__in=orgs, verification_status='confirmed').values_list('pk', 'public_figure_id', 'organisation_id')
        live_edges = {hashlib.sha256(f'figure:{f}|org:{o}|pełni funkcję w KRS|{pk}'.encode()).hexdigest()[:24]
                      for pk, f, o in rels}
        if not krs_edges <= live_edges:
            return False
    if articles:
        if Article.objects.filter(pk__in=articles, source__is_active=True).count() != len(articles):
            return False
        manual = {int(n['id'].split(':')[1]) for n in nodes if n['kind'] == 'media' and n['certainty'] == 'manual'}
        refs = PublicFigureArticleReference.objects.filter(public_figure=root_object, article_id__in=articles)
        live = set(refs.filter(verification_status='confirmed').values_list('article_id', flat=True))
        if not manual <= live or refs.filter(article_id__in=articles - manual, verification_status__in=('rejected', 'confirmed')).exists():
            return False
    return True


@api_view(['GET'])
@permission_classes([AllowAny])
def flow_view(request, ident):
    from news.przeszlosc import enabled
    from news.przeszlosc_dostep import has, locked
    from news.political_models import RegisteredOrganisation
    if not enabled():
        return Response({'detail': 'Funkcja jeszcze wyłączona.'}, status=404)
    try:
        opts = options(request.query_params)
    except (ValueError, TypeError):
        return Response({'detail': 'Nieprawidłowe parametry drzewa przepływu.'}, status=400)
    prefix, _, value = ident.partition(':')
    obj = None
    if prefix == 'osoba':
        obj = person.resolve(value)
    elif prefix == 'spolka' and value.isdigit() and len(value) <= 18:
        obj = money.resolve(value)
        if obj is None and value.isdigit() and len(value) == 10:
            matches = list(RegisteredOrganisation.objects.filter(nip=value, archived=False)[:2])
            obj = matches[0] if len(matches) == 1 else None
    if obj is None:
        return Response({'detail': 'Nie ma takiej osoby publicznej lub podmiotu.'}, status=404)
    if not has('money_trail', request):
        return locked('money_trail')
    digest = hashlib.sha256(json.dumps([ident, opts], sort_keys=True).encode()).hexdigest()
    from news.przeplyw_cache import revision
    key = f'przeszlosc:przeplyw:{VERSION}:{revision()}:{digest}'
    data = cache.get(key)
    if data is None or not cache_is_public(data, obj, prefix == 'osoba'):
        data = build(obj, prefix == 'osoba', opts)
        cache.set(key, data, CACHE_SECONDS)
    return Response(data)
