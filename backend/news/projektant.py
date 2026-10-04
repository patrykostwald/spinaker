"""Projektant UX/UI (właściciel 5.10): ekspert od designu, UX i UI, który ciągle się uczy.

Raz w tygodniu:
1. „Stan wiedzy UX/UI”: czyta nagłówki z uznanych źródeł branżowych (FEEDS) i wybiera to, co warto wprowadzić
   w spin.clinic przy naszym zakresie; każdy punkt ma źródło, drugi model innej firmy sprawdza raport.
2. Przegląd stron: pobiera kluczowe strony serwisu, wyciąga strukturę (nagłówki, odnośniki, przyciski, obrazy, długości
   tekstów), sprawdza ją bez AI według przewodnika (GUIDE) i prosi model o konkretne poprawki z miejscem i uzasadnieniem.
Uczy się wszystkiego (właściciel 5.10), bo jego wiedzy używamy też w zbudujmi.com; przegląd stron dotyczy spin.clinic.
Projektant proponuje; poprawki wdraża człowiek (zmiany w kodzie strony wymagają zgody właściciela).
Z przewodnika i raportów korzystamy przy zmianach na froncie i przy stronach dla nowych klientów."""
import json
import re
from datetime import timedelta
from html.parser import HTMLParser

import requests
from django.utils import timezone

from news import agents_common as common
from news.agent_models import AgentNote

_used = {'author': None, 'checker': None}


def _ask_author(prompt, data, schema, force=False):
    answer, member = common.ask_any(prompt, data, schema, force)
    _used['author'] = member
    return answer


def _ask_checker(prompt, data, schema, force=False):
    answer, member = common.ask_any(prompt, data, schema, force, exclude=tuple(m for m in [_used['author']] if m))
    _used['checker'] = member
    return answer


WEEK = timedelta(days=6)
FEEDS = {
    'Nielsen Norman Group': 'https://www.nngroup.com/feed/rss/',
    'Smashing Magazine': 'https://www.smashingmagazine.com/feed/',
    'web.dev': 'https://web.dev/static/blog/feed.xml',
    'CSS-Tricks': 'https://css-tricks.com/feed/',
    'A List Apart': 'https://alistapart.com/main/feed/',
    'UX Collective': 'https://uxdesign.cc/feed',
    'Awwwards': 'https://www.awwwards.com/blog/feed/',
    'Codrops': 'https://tympanus.net/codrops/feed/',
}
# Kanon zasad z klasycznych podręczników (stała wiedza Projektanta; uzupełniana o nowe źródła na prośbę właściciela).
CANON = [
    'Nie każ myśleć (Krug): oczywiste etykiety, jedna główna akcja na ekranie, konwencje zamiast pomysłów.',
    'Hierarchia przez wielkość, grubość i kolor, nie przez ramki (Refactoring UI); mniej obramowań, więcej odstępów.',
    'Prawo Jakoba i Hicka (Laws of UX): użytkownik zna inne serwisy; mniej wyborów to szybsza decyzja.',
    'Prawo Fittsa: ważne cele duże i blisko; na telefonie w zasięgu kciuka.',
    'Bliskość i podobieństwo (Gestalt): elementy powiązane bliżej siebie i w tym samym stylu.',
    'Siatka i rytm: stałe odstępy w skali (4/8 px), wyrównanie do wspólnych krawędzi.',
    'Typografia: 45-75 znaków w wierszu, interlinia 1,4-1,6 dla tekstu, skala rozmiarów zamiast przypadkowych wartości.',
    'Dostępność WCAG 2.2: kontrast tekstu co najmniej 4,5:1, widoczny fokus, obsługa klawiaturą, cele dotykowe 24-44 px, nie tylko kolor.',
    'Stany puste, ładowania i błędu zaprojektowane tak samo starannie jak stan z danymi.',
    'Wydajność to UX: treść widoczna szybko, bez przeskakiwania układu (CLS).',
]
# Wszystkie główne widoki serwisu (właściciel 5.10: „audyt wszystkich elementów strony”)
PAGES = ['/', '/spinki', '/klinika', '/klinika/diagnozy', '/klinika/wskazniki', '/klinika/wywiady', '/klinika/wywiady/glosowanie',
         '/klinika/przekazy', '/klinika/raporty', '/klinika/korekty', '/konsylium', '/search', '/osoby-publiczne', '/o-nas',
         '/o-projekcie', '/metodologia', '/zrodla', '/wsparcie', '/dla-redakcji', '/zasady-korzystania', '/polityka-prywatnosci',
         '/konto', '/przeszlosc']
# Stałe zasady projektu (decyzje właściciela); Projektant ich pilnuje i proponuje kolejne.
GUIDE = [
    'Czysto, jasno, harmonijnie, profesjonalnie, minimalnie; najwyżej 2 kroje pisma.',
    'Boksy w rzędzie: te same krawędzie i wysokości, tytuły w ustalonej liczbie linii, nic nie ucięte w pół linii.',
    'Każdy odnośnik „… →” w jednym stylu: ten sam krój, rozmiar 15 px, grubość 600, niebieski akcent, bez wyglądu przycisku.',
    'Siła spinu zawsze tym samym kolorem (zielony < niebieski < czerwony), techniki jak sygnalizator.',
    'Bez pasków przewijania; na telefonie nic poza ekranem, elementy dotykowe co najmniej 44 px.',
    'Tytuł i podtytuł zaczynają się na lewej krawędzi treści pod nimi; liczby i wykresy dociągnięte do krawędzi.',
    'Wskaźnik ładowania tylko przy dłuższym czekaniu; brak migających pustych stanów.',
    'Ta sama miara wizualna dla obu stron sceny politycznej: identyczne kolory, rozmiary i kolejność.',
    'Bez wewnętrznych nazw i żargonu na stronie; teksty krótkie i zrozumiałe dla laika.',
]
TEXT = {'type': 'string'}
TREND = {'type': 'object', 'properties': {'title': TEXT, 'why': TEXT, 'apply': TEXT, 'source_url': TEXT},
         'required': ['title', 'why', 'apply', 'source_url']}
BRIEF_SCHEMA = {'type': 'object', 'properties': {'summary': TEXT, 'trends': {'type': 'array', 'items': TREND},
                'guide_additions': {'type': 'array', 'items': TEXT}}, 'required': ['summary', 'trends', 'guide_additions']}
FIX = {'type': 'object', 'properties': {'page': TEXT, 'element': TEXT, 'problem': TEXT, 'fix': TEXT,
       'priority': {'type': 'string', 'enum': ['wysoki', 'średni', 'niski']}}, 'required': ['page', 'element', 'problem', 'fix', 'priority']}
AUDIT_SCHEMA = {'type': 'object', 'properties': {'fixes': {'type': 'array', 'items': FIX}}, 'required': ['fixes']}
CHECK_SCHEMA = {'type': 'object', 'properties': {'remove': {'type': 'array', 'items': {'type': 'integer'}}, 'reason': TEXT},
                'required': ['remove', 'reason']}
LEARN = ('Jesteś Projektantem UX/UI grupy iapply: ekspertem od projektowania interfejsów, dostępności, czytelności, typografii, '
         'animacji i sprzedażowych stron www, który zna najnowsze trendy i dobre zasady branży. Uczysz się WSZYSTKIEGO, nie tylko pod jeden '
         'projekt: twoją wiedzę wykorzystują spin.clinic (serwis danych o przekazie polityków) i zbudujmi.com (strony i sklepy dla małych firm). '
         'Na podstawie WYŁĄCZNIE nagłówków i opisów z items wybierz do 10 najważniejszych rzeczy. Dla każdej: co to jest (title), dlaczego '
         'ważne (why), gdzie i jak zastosować (apply: wskaż spin.clinic, zbudujmi.com albo oba, konkretnie), source_url z items. '
         'W guide_additions podaj do 3 nowych, krótkich zasad ogólnych, jeśli są warte zapisania. Bez mody dla mody.')
LEARN_CHECK = ('Oceniasz wyłącznie wiedzę o projektowaniu UX/UI (nie treści polityczne ani dezinformację). Sprawdź raport kolegi wobec items i przewodnika. W remove podaj numery (od 0) trendów bez pokrycia w items, '
               'sprzecznych z przewodnikiem albo niepraktycznych dla tego serwisu.')
AUDIT = ('Jesteś Projektantem UX/UI spin.clinic. Uwaga: pages to kod strony przed uruchomieniem skryptów - brak h1 lub treści może znaczyć, że pojawiają się po wczytaniu; zgłaszaj to najwyżej jako średni priorytet. Masz przewodnik projektu (guide), strukturę stron (pages) i automatyczne uwagi '
         '(checks). Wypisz konkretne poprawki: strona, element (nagłówek, odnośnik, boks), problem i gotowa poprawka. '
         'Priorytet wysoki tylko dla błędów czytelności, spójności i dostępności. Bez ogólników.')
AUDIT_CHECK = ('Sprawdź poprawki kolegi. W remove podaj numery (od 0) poprawek niepopartych strukturą stron, sprzecznych z przewodnikiem '
               'albo ogólnikowych.')


def guide():
    """Przewodnik: stałe zasady i dopiski zaakceptowane z raportów Projektanta."""
    extra = []
    for note in AgentNote.objects.filter(agent='projektant', kind='report', status__in=['new', 'accepted'])[:8]:
        extra += [str(x) for x in (note.scores or {}).get('guide_additions', [])]
    return GUIDE + CANON + list(dict.fromkeys(extra))[:12]


def feed_items(limit=8):
    import feedparser
    items = []
    for name, url in FEEDS.items():
        try:
            response = requests.get(url, timeout=15, headers={'User-Agent': 'spin.clinic Projektant (+https://spin.clinic)'})
            parsed = feedparser.parse(response.content)
        except requests.RequestException:
            continue
        for entry in parsed.entries[:limit]:
            link = entry.get('link', '')
            if link.startswith('https://'):
                items.append({'source': name, 'title': entry.get('title', '')[:200], 'url': link,
                              'summary': re.sub(r'<[^>]+>', ' ', entry.get('summary', ''))[:500]})
    return items


class _Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.headings, self.links, self.buttons, self.images, self.text = [], [], [], [], [], 0
        self._capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('h1', 'h2', 'h3', 'a', 'button'):
            self._capture = [tag, attrs.get('class', ''), '']
        if tag == 'img':
            self.images.append({'alt': attrs.get('alt'), 'class': attrs.get('class', '')})

    def handle_data(self, data):
        self.text += len(data.strip())
        if self._capture:
            self._capture[2] += data

    def handle_endtag(self, tag):
        if self._capture and tag == self._capture[0]:
            kind, cls, text = self._capture
            text = ' '.join(text.split())[:120]
            if kind.startswith('h'):
                self.headings.append({'level': kind, 'text': text})
            elif kind == 'a':
                self.links.append({'text': text, 'class': cls.split(' ')[0] if cls else ''})
            else:
                self.buttons.append({'text': text, 'class': cls.split(' ')[0] if cls else ''})
            self._capture = None


def page_structure(base, path):
    html = requests.get(base.rstrip('/') + path, timeout=20, headers={'User-Agent': 'spin.clinic Projektant'}).text
    parser = _Structure()
    parser.feed(html)
    arrows = [l for l in parser.links if l['text'].endswith('→')]
    checks = []
    if len({l['class'] for l in arrows}) > 1:
        checks.append(f"Odnośniki „→” mają {len({l['class'] for l in arrows})} różne klasy stylu (zasada: jeden styl).")
    if sum(h['level'] == 'h1' for h in parser.headings) != 1:
        checks.append(f"Liczba nagłówków h1: {sum(h['level'] == 'h1' for h in parser.headings)} (powinien być jeden).")
    missing = [i for i in parser.images if i['alt'] is None]
    if missing:
        checks.append(f'{len(missing)} obrazów bez opisu alt.')
    long_titles = [h['text'] for h in parser.headings if len(h['text']) > 90]
    if long_titles:
        checks.append(f'{len(long_titles)} nagłówków dłuższych niż 90 znaków.')
    return {'page': path, 'headings': parser.headings[:25], 'arrow_links': arrows[:15], 'buttons': parser.buttons[:15],
            'images': len(parser.images), 'text_chars': parser.text, 'checks': checks}


def _site_base():
    import os
    return os.environ.get('PROJEKTANT_BASE_URL', '').strip() or 'http://frontend:3000'


def learn(force=False):
    items = feed_items()
    urls = {i['url'] for i in items}
    if not items:
        raise common.WindowClosed('Brak nagłówków ze źródeł branżowych.')
    author = checker = None
    brief = _ask_author(LEARN, {'items': items[:40], 'guide': guide()}, BRIEF_SCHEMA, force)
    trends = [t for t in brief.get('trends', []) if isinstance(t, dict) and t.get('source_url') in urls]
    verdict = _ask_checker(LEARN_CHECK, {'items': items[:40], 'guide': guide(), 'trends': trends}, CHECK_SCHEMA, force)
    drop = {int(x) for x in verdict.get('remove', []) if str(x).lstrip('-').isdigit()}
    brief['trends'] = [t for n, t in enumerate(trends) if n not in drop]
    data = {**brief, 'check': verdict.get('reason', ''), 'authors': [':'.join(_used['author'] or ('-',)), ':'.join(_used['checker'] or ('-',))]}
    note = AgentNote.objects.create(agent='projektant', kind='report', status='new',
        title=f'Stan wiedzy UX/UI: {timezone.localdate():%d.%m.%Y}', body=readable_brief(data), scores=data,
        sources=sorted({t['source_url'] for t in brief['trends']}))
    common.notify(note)
    return note


def audit(force=False, base=None):
    base = base or _site_base()
    pages = []
    for path in PAGES:
        try:
            pages.append(page_structure(base, path))
        except requests.RequestException:
            continue
    if not pages:
        raise common.WindowClosed('Strony serwisu niedostępne dla przeglądu.')
    author = checker = None
    fixes = []
    for start in range(0, len(pages), 6):  # partiami, żeby pytanie zmieściło się w limicie modelu
        batch = pages[start:start + 6]
        answer = _ask_author(AUDIT, {'guide': guide(), 'pages': batch}, AUDIT_SCHEMA, force)
        rows = [f for f in answer.get('fixes', []) if isinstance(f, dict)]
        if rows:
            verdict = _ask_checker(AUDIT_CHECK, {'guide': guide(), 'pages': batch, 'fixes': rows}, CHECK_SCHEMA, force)
            drop = {int(x) for x in verdict.get('remove', []) if str(x).lstrip('-').isdigit()}
            fixes += [f for n, f in enumerate(rows) if n not in drop]
    auto = [{'page': p['page'], 'check': c} for p in pages for c in p['checks']]
    data = {'fixes': fixes, 'auto_checks': auto, 'pages': [p['page'] for p in pages], 'authors': [':'.join(_used['author'] or ('-',)), ':'.join(_used['checker'] or ('-',))]}
    note = AgentNote.objects.create(agent='projektant', kind='audit', status='new' if fixes or auto else 'done',
        title=f"Przegląd stron: {len(pages)} stron, {len(fixes)} poprawek", body=readable_audit(data), scores=data, sources=[])
    if any(f.get('priority') == 'wysoki' for f in fixes):
        common.notify(note)
    return note


def step(force=False):
    last = AgentNote.objects.filter(agent='projektant', kind='report').first()
    if last and not force and timezone.now() - last.created_at < WEEK:
        return last
    note = learn(force)
    audit(force)
    from news import recenzent
    recenzent.audit_pages(force)  # raz w tygodniu wszystkie stałe teksty stron
    return note


def readable_brief(data):
    lines = [data.get('summary', ''), '']
    for t in data.get('trends', []):
        lines += [f"- {t['title']}: {t['why']}", f"  Jak u nas: {t['apply']} ({t['source_url']})"]
    if data.get('guide_additions'):
        lines += ['', 'Propozycje do przewodnika:'] + [f'- {g}' for g in data['guide_additions']]
    lines += ['', f"Sprawdzenie drugiego eksperta: {data.get('check', '')}"]
    return chr(10).join(lines).strip()


def readable_audit(data):
    order = {'wysoki': 0, 'średni': 1, 'niski': 2}
    lines = [f"[{f['priority']}] {f['page']} · {f['element']}: {f['problem']}{chr(10)}  Poprawka: {f['fix']}"
             for f in sorted(data.get('fixes', []), key=lambda f: order.get(f.get('priority'), 3))]
    if data.get('auto_checks'):
        lines += ['', 'Sprawdzenia automatyczne:'] + [f"- {a['page']}: {a['check']}" for a in data['auto_checks']]
    return chr(10).join(lines) or 'Bez uwag.'
