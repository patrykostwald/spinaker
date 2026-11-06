"""Kandydaci doniesień medialnych o podmiotach osób publicznych z NASZEGO korpusu artykułów (6.11.2026).

Bez żadnych zapytań na zewnątrz: dla osoby (pełne imię i nazwisko w tytule lub opisie artykułu, te same zasady co wzmianki:
imiennicy i krótkie nazwy pomijamy) szukamy w tym samym artykule pełnej nazwy podmiotu z naszej bazy KRS. Wynik trafia do
kolejki przeglądu (`pending_review`, podstawa „tylko po nazwie”, zbierał „agent”), nigdy od razu publicznie.
Nazwy zbyt ogólne (po zdjęciu formy prawnej zostaje jedno krótkie słowo) są pomijane. Kategoria to wskazówka dla redaktora
(słowa kluczowe w tytule/opisie), a nie ocena: wszystko i tak przechodzi przegląd.
"""
import re
import unicodedata
from collections import defaultdict

from news.media_mentions import CANDIDATE_LIMIT, candidate_filter, name_pattern, namesakes, normalize_name
from news.models import Article
from news.political_models import PublicFigure, PublicFigureMediaMention, PublicFigureOrganisationRelation, RegisteredOrganisation

LEGAL_WORDS = {'fundacja', 'fundacji', 'stowarzyszenie', 'stowarzyszenia', 'spółka', 'sp', 'z', 'o', 'oo', 'spółdzielnia', 'sa', 's', 'a',
               'ska', 'k', 'jawna', 'komandytowa', 'akcyjna', 'zoo', 'zrzeszenie', 'związek', 'instytut', 'towarzystwo', 'klub', 'im', 'imienia'}
GENERIC = {'polska', 'polskie', 'polski', 'polskiego', 'polskich', 'krajowa', 'krajowy', 'narodowa', 'narodowy', 'centrum', 'grupa',
           'pomocy', 'rozwoju', 'wspierania', 'dzieciom', 'dzieci', 'młodzieży', 'rodzina', 'rodzin', 'zdrowia', 'edukacji', 'kultury',
           'sportu', 'ochrony', 'wsi', 'miasta', 'gminy', 'powiatu', 'regionu', 'obywatelskie', 'społeczna', 'społeczne', 'inicjatyw'}
MIN_DISTINCT_CHARS = 8
# Kategoria tylko z MOCNYCH słów tuż przy podmiocie (okno CUE_WINDOW znaków); zwykłe słowa („założyliśmy”, „współpracuj”) nic nie znaczą.
CUES = (('denied', re.compile(r'dementuj|zaprzecz|sprostowa|nieprawd', re.I)),
        ('alleged', re.compile(r'powiązan\w* (?:z|ze)\b|związan\w* (?:z|ze)\b|fundator\w*|założyciel\w*|współzałożyciel\w*|prezes\w* (?:fundacji|stowarzyszenia)|rad[aęy] fundacji', re.I)))
PROXIMITY = 100        # osoba i podmiot najwyżej tyle znaków od siebie (inaczej to tylko dwa nazwiska w jednym opisie)
MAX_ORGS_IN_TEXT = 3   # tekst z większą liczbą różnych podmiotów z bazy to lista gości/partnerów/komunikat o grupie spółek: pomijamy
CUE_WINDOW = 120
WIDTH = 80


def _norm(text):
    return ' '.join(unicodedata.normalize('NFC', text or '').casefold().replace('„', ' ').replace('”', ' ').replace('"', ' ').split())


def distinct_part(name):
    """Nazwa bez formy prawnej i przyimków; None, gdy zostaje zbyt ogólna (jedno krótkie lub typowe słowo)."""
    words = [w for w in re.findall(r'[\w-]+', _norm(name)) if w not in LEGAL_WORDS]
    if not words or all(w in GENERIC for w in words):
        return None
    joined = ' '.join(words)
    if len(words) == 1 and (len(joined) < MIN_DISTINCT_CHARS or joined in GENERIC):
        return None
    return joined if len(joined) >= MIN_DISTINCT_CHARS else None


def org_index():
    """{fraza: organizacja}: pełna nazwa w zapisie znormalizowanym; przy kolizji dwóch podmiotów fraza jest pomijana."""
    phrases = defaultdict(set)
    for org in RegisteredOrganisation.objects.filter(archived=False).only('pk', 'name'):
        full = _norm(org.name)
        if distinct_part(org.name) and len(full) >= MIN_DISTINCT_CHARS:
            phrases[full].add(org.pk)
    unique = {p: next(iter(ids)) for p, ids in phrases.items() if len(ids) == 1}
    if not unique:
        return None, {}
    pattern = re.compile(r'(?<![\w-])(?:' + '|'.join(re.escape(p) for p in sorted(unique, key=len, reverse=True)) + r')(?![\w-])')
    return pattern, unique


def category_for(text):
    for key, cue in CUES:
        if cue.search(text):
            return key
    return 'mention'


def snippet(text, start, end, margin=40):
    a, b = max(0, start - margin), min(len(text), end + margin)
    return ('…' if a else '') + ' '.join(text[a:b].split()) + ('…' if b < len(text) else '')


def category_near(text, start, end):
    """Kategoria z mocnych słów tylko w oknie wokół podmiotu (nie z całego opisu)."""
    return category_for(text[max(0, start - CUE_WINDOW): end + CUE_WINDOW])


def _distance(a, b):
    """Odstęp w znakach między dwoma przedziałami (0 przy nakładaniu)."""
    return max(0, max(a[0], b[0]) - min(a[1], b[1]))


def candidates_for(figure, pattern, index, known_orgs=frozenset()):
    """Lista słowników-kandydatów dla osoby (bez zapisu).

    Warunki: pełne imię i nazwisko osoby oraz pełna nazwa podmiotu w tym samym artykule, najwyżej PROXIMITY znaków od siebie;
    teksty z więcej niż MAX_ORGS_IN_TEXT różnych podmiotów z bazy (listy gości, komunikaty o grupie spółek) pomijamy."""
    person = name_pattern(figure.canonical_name)
    if person is None or figure.archived or figure.merged_into_id or namesakes(figure, normalize_name(figure.canonical_name)):
        return []
    rows = Article.objects.filter(candidate_filter(normalize_name(figure.canonical_name).split()[-1]), published_date__isnull=False) \
        .select_related('source').order_by('-published_date')[:CANDIDATE_LIMIT]
    out = []
    for article in rows:
        text = ' '.join(filter(None, (article.title, article.description)))
        normalized = _norm(text)
        person_spans = [m.span() for m in person.finditer(normalized)]
        if not person_spans:
            continue
        hits = [(m.span(), index[m.group(0)]) for m in pattern.finditer(normalized)]
        if len({org_id for _, org_id in hits}) > MAX_ORGS_IN_TEXT:
            continue
        for span, org_id in hits:
            if org_id in known_orgs:
                continue
            nearest = min(person_spans, key=lambda p: _distance(p, span))
            if _distance(nearest, span) > PROXIMITY:
                continue
            start, end = min(nearest[0], span[0]), max(nearest[1], span[1])
            out.append({'figure': figure, 'org_id': org_id, 'article': article, 'category': category_near(normalized, *span),
                        'quote': snippet(normalized, start, end)[:300]})
    return out


def clear_agent_queue():
    """Usuwa z kolejki wyłącznie niepublikowane pozycje zebrane automatycznie (status do przeglądu, zbierał agent)."""
    deleted, _ = PublicFigureMediaMention.objects.filter(status='pending_review', collected_by='agent').delete()
    return deleted


def collect(apply=False, per_person=5, total=2000, with_known=False, figure_ids=None):
    pattern, index = org_index()
    stats = {'persons': 0, 'with_candidates': 0, 'candidates': 0, 'added': 0, 'skipped_existing': 0}
    if pattern is None:
        return stats
    figures = PublicFigure.objects.filter(archived=False, merged_into__isnull=True)
    if figure_ids:
        figures = figures.filter(pk__in=figure_ids)
    known = defaultdict(set)
    if not with_known:
        for fid, oid in PublicFigureOrganisationRelation.objects.filter(verification_status='confirmed').values_list('public_figure_id', 'organisation_id'):
            known[fid].add(oid)
    for figure in figures.select_related('parliamentary_roster_entry').order_by('pk'):
        stats['persons'] += 1
        found = candidates_for(figure, pattern, index, known[figure.pk])
        if not found:
            continue
        stats['with_candidates'] += 1
        seen, kept = set(), []
        for c in found:
            key = (c['org_id'], c['article'].url)
            if key in seen:
                continue
            seen.add(key)
            kept.append(c)
        for c in kept[:per_person]:
            stats['candidates'] += 1
            if PublicFigureMediaMention.objects.filter(public_figure=figure, organisation_id=c['org_id'], source_url=c['article'].url).exists():
                stats['skipped_existing'] += 1
                continue
            if apply and stats['added'] < total:
                PublicFigureMediaMention.objects.create(
                    public_figure=figure, organisation_id=c['org_id'], category=c['category'], match_basis='name_only',
                    source_url=c['article'].url, source_title=c['article'].title[:300], source_outlet=(c['article'].source.name if c['article'].source_id else '')[:120],
                    published_on=c['article'].published_date.date() if c['article'].published_date else None, quote=c['quote'], collected_by='agent')
                stats['added'] += 1
    return stats
