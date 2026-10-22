"""Badacz (właściciel 5.10: „druga pętla do researchu, nie chcę tylko z 10 źródeł”): wspólny zbiór źródeł dla wszystkich agentów.

Pętla: źródła agentów (nasiona) -> Badacz czyta nowości -> z linków w nich odkrywa nowe strony -> szuka ich kanałów RSS/Atom
(<link rel="alternate">) -> drugi model ocenia, czy kandydat jest wartościowy dla danego tematu -> aktywne źródło trafia do zbioru
-> agenci (Automatyk, Projektant, Pracownia OSINT) dostają przy każdym czytaniu podstawowe źródła + porcję odkrytych
-> kanał, który 3 razy z rzędu nie odpowiada, zostaje uśpiony (strażnik jakości).
Tylko publiczne kanały RSS/Atom i strony główne (bez logowania, bez scrapowania treści)."""
import re
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests
from django.utils import timezone

from news import agents_common as common

STATE = 'badacz-sources'
TOPICS = {
    'automatyzacja': 'automatyzacja, agenci AI, orkiestracja, niezawodność systemów, ewaluacja modeli',
    'ux': 'projektowanie UX/UI, dostępność, typografia, interfejsy, strony i sklepy',
    'osint': 'OSINT, dziennikarstwo śledcze i danych, rejestry publiczne, fact-checking, dezinformacja',
    'ai': 'modele językowe, narzędzia AI, otwarte modele, koszty i limity',
}
UA = {'User-Agent': 'spin.clinic Badacz (+https://spin.clinic)'}
SKIP_HOSTS = ('twitter.com', 'x.com', 'facebook.com', 'instagram.com', 'linkedin.com', 'youtube.com', 'tiktok.com', 'google.com',
              't.co', 'bit.ly', 'github.com', 'arxiv.org', 'reddit.com', 'news.ycombinator.com')
MAX_FAILS = 3
TEXT = {'type': 'string'}
JUDGE = {'type': 'object', 'properties': {'keep': {'type': 'array', 'items': {'type': 'integer'}}, 'reason': TEXT}, 'required': ['keep', 'reason']}
JUDGE_PROMPT = ('Jesteś Badaczem, strażnikiem jakości źródeł. Dla tematu (topic) oceń kandydatów (candidates: numer, strona, tytuły '
                'ostatnich wpisów). W keep podaj numery tylko tych, które są wartościowe, merytoryczne i regularnie piszą o temacie; '
                'odrzuć sklepy, agregatory bez treści, spam, strony jednej firmy reklamujące siebie i źródła bez związku z tematem.')


def _seeds():
    """Nasiona: źródła, które agenci mają już w kodzie."""
    from news import automatyk, pracownia_osint, projektant
    out = {}
    for topic, feeds in (('automatyzacja', automatyk.LEARN_FEEDS), ('automatyzacja', automatyk.WIDE_FEEDS), ('ux', projektant.FEEDS),
                         ('osint', pracownia_osint.FEEDS), ('ai', pracownia_osint.TECH_FEEDS)):
        for name, url in feeds.items():
            out.setdefault(url, {'name': name, 'topic': topic, 'status': 'nasiono', 'fails': 0, 'added': None})
    return out


def load():
    from news.models import ImportState
    state = ImportState.objects.filter(name=STATE).first()
    data = dict((state.cursor or {}).get('sources', {})) if state else {}
    for url, row in _seeds().items():
        data.setdefault(url, row)
    return data


def save(data):
    from news.models import ImportState
    state, _ = ImportState.objects.get_or_create(name=STATE)
    state.cursor = {'at': timezone.now().isoformat(timespec='minutes'), 'sources': data}
    state.save(update_fields=['cursor'])


class _Alt(HTMLParser):
    def __init__(self):
        super().__init__()
        self.feeds, self.title = [], ''
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'link' and 'alternate' in (a.get('rel') or '') and (a.get('type') or '') in ('application/rss+xml', 'application/atom+xml'):
            self.feeds.append(a.get('href') or '')
        self._in_title = tag == 'title'

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()[:120]


def find_feed(site):
    """Kanał RSS/Atom strony głównej (autodiscovery); None, gdy brak."""
    try:
        html = requests.get(site, timeout=12, headers=UA).text[:200_000]
    except requests.RequestException:
        return None, ''
    parser = _Alt()
    parser.feed(html)
    feeds = [urljoin(site, f) for f in parser.feeds if f]
    return (feeds[0] if feeds else None), parser.title


def read(url, limit=5):
    import feedparser
    parsed = feedparser.parse(requests.get(url, timeout=15, headers=UA).content)
    return [{'title': e.get('title', '')[:200], 'url': e.get('link', ''), 'summary': re.sub(r'<[^>]+>', ' ', e.get('summary', ''))[:600]}
            for e in parsed.entries[:limit] if e.get('link', '').startswith('https://')]


def discover(data, per_run=12):
    """Z linków w nowościach aktywnych źródeł: nowe strony z kanałem RSS -> kandydaci (per temat)."""
    known_hosts = {urlparse(u).netloc for u in data}
    found = {}
    for url, row in list(data.items()):
        if row['status'] in ('uśpione', 'odrzucone') or len(found) >= per_run * 3:
            continue
        try:
            items = read(url)
            row['fails'] = 0
        except Exception:  # noqa: BLE001 - zły kanał liczymy, nie przerywamy
            row['fails'] = row.get('fails', 0) + 1
            if row['fails'] >= MAX_FAILS:
                row['status'] = 'uśpione'
            continue
        for item in items:
            for link in re.findall(r'https://[^\s"\'<>)]+', item['summary']) + [item['url']]:
                host = urlparse(link).netloc.lower()
                if host and host not in known_hosts and not any(host.endswith(s) for s in SKIP_HOSTS):
                    found.setdefault(host, (row['topic'], f'https://{host}/'))
    candidates = []
    for host, (topic, site) in list(found.items())[:per_run]:
        feed, title = find_feed(site)
        if feed and feed not in data:
            try:
                sample = [i['title'] for i in read(feed, 4)]
            except Exception:  # noqa: BLE001
                continue
            if sample:
                candidates.append({'topic': topic, 'feed': feed, 'site': site, 'name': title or host, 'titles': sample})
    return candidates


def judge(candidates, force=False):
    """Drugi model: tylko wartościowe źródła per temat stają się aktywne."""
    accepted = []
    for topic, description in TOPICS.items():
        rows = [c for c in candidates if c['topic'] == topic]
        if not rows:
            continue
        answer, _ = common.ask_any(JUDGE_PROMPT, {'topic': description, 'candidates': [{'n': n, 'site': c['site'], 'titles': c['titles']}
                                                                                         for n, c in enumerate(rows)]}, JUDGE, force)
        keep = {int(x) for x in answer.get('keep', []) if str(x).lstrip('-').isdigit()}
        accepted += [c for n, c in enumerate(rows) if n in keep]
    return accepted


def trusted_pages(data):
    """Strony wskazane przez właściciela: kanał RSS znaleziony automatycznie trafia od razu do aktywnych (bez oceny)."""
    from news.projektant import DESIGN_PAGES
    added = 0
    for name, page in DESIGN_PAGES.items():
        if any(r.get('page') == page for r in data.values()):
            continue
        feed, _ = find_feed(page)
        key = feed or page
        data.setdefault(key, {'name': name, 'topic': 'ux', 'status': 'odkryte' if feed else 'strona', 'fails': 0,
                              'added': timezone.localdate().isoformat(), 'page': page})
        added += bool(feed)
    return added


def step(force=False):
    data = load()
    trusted_pages(data)
    try:  # łowca kanonów: „prawa wykonania” do każdego tematu (właściciel 5.10)
        from news import kanony
        kanony.hunt()
    except common.WindowClosed:
        pass
    candidates = discover(data)
    accepted = judge(candidates, force) if candidates else []
    today = timezone.localdate().isoformat()
    for c in accepted:
        data[c['feed']] = {'name': c['name'], 'topic': c['topic'], 'status': 'odkryte', 'fails': 0, 'added': today}
    for c in candidates:
        data.setdefault(c['feed'], {'name': c['name'], 'topic': c['topic'], 'status': 'odrzucone', 'fails': 0, 'added': today})
    save(data)
    return {'kandydaci': len(candidates), 'przyjęte': len(accepted), 'źródła': sum(r['status'] in ('nasiono', 'odkryte') for r in data.values()),
            'uśpione': sum(r['status'] == 'uśpione' for r in data.values())}


def feeds(topic, limit=8):
    """Dla agentów: porcja odkrytych źródeł danego tematu (najnowsze najpierw); rotuje co tydzień."""
    rows = [(u, r) for u, r in load().items() if r['topic'] == topic and r['status'] == 'odkryte']
    rows.sort(key=lambda x: x[1].get('added') or '', reverse=True)
    if not rows:
        return {}
    week = timezone.now().isocalendar()[1]
    start = (week * limit) % len(rows)
    chosen = (rows + rows)[start:start + min(limit, len(rows))]
    return {f"{r['name']} (odkryte)": u for u, r in chosen}
