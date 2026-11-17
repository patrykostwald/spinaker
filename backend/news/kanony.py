"""Kanony (właściciel 5.10): do każdego tematu szukamy „praw wykonania” - krótkich, uznanych, darmowych zbiorów zasad
jak Laws of UX. Agenci danego tematu dostają je do kontekstu, a Badacz (łowca kanonów) co tydzień szuka kolejnych:
model proponuje adresy, sprawdzamy, czy strona działa, drugi model ocenia, czy to naprawdę zbiór zasad, a nie blog czy reklama.

CANONS: zestaw startowy (sprawdzony 5.10). Odkryte kanony trafiają do ImportState „kanony” i dopisują się do zestawu."""
from datetime import timedelta

import requests
from django.utils import timezone

from news import agents_common as common

STATE = 'kanony'
UA = {'User-Agent': 'spin.clinic Badacz (+https://spin.clinic)'}
CANONS = {
    'ux': [
        ('Laws of UX', 'https://lawsofux.com/', '30 praw psychologii projektowania (biblia Projektanta)'),
        ('GoodUI', 'https://goodui.org/', 'sprawdzone wzorce interfejsów z wynikami testów A/B'),
        ('10 heurystyk Nielsena', 'https://www.nngroup.com/articles/ten-usability-heuristics/', 'podstawowe zasady użyteczności'),
        ('Jak ludzie czytają w sieci (NN/g)', 'https://www.nngroup.com/articles/how-users-read-on-the-web/', 'skanowanie, wzorzec F, pisanie pod skanowanie'),
        ('UI Patterns', 'https://ui-patterns.com/', 'biblioteka wzorców rozwiązań typowych problemów'),
        ('Refactoring UI', 'https://refactoringui.com/', 'hierarchia, odstępy, kolor - praktyczne zasady wyglądu'),
        ('Deceptive Design', 'https://www.deceptive.design/', 'czego nie robić: zwodnicze wzorce (nasza zasada uczciwości)'),
        ('Humane by Design', 'https://humanebydesign.com/', 'projektowanie z szacunkiem dla uwagi i czasu użytkownika'),
        ('Growth.Design case studies', 'https://growth.design/case-studies', 'psychologia w prawdziwych produktach, krok po kroku'),
    ],
    'dostępność': [
        ('WCAG 2.2 skrót', 'https://www.w3.org/WAI/WCAG22/quickref/', 'oficjalne kryteria dostępności'),
        ('A11Y Project checklist', 'https://www.a11yproject.com/checklist/', 'lista kontrolna dostępności do każdego wdrożenia'),
        ('Inclusive Design Principles', 'https://inclusivedesignprinciples.info/', '7 zasad projektowania włączającego'),
    ],
    'automatyzacja': [
        ('Building effective agents (Anthropic)', 'https://www.anthropic.com/engineering/building-effective-agents', 'wzorce agentów i pętli: kiedy prostota wystarcza'),
        ('Google SRE book', 'https://sre.google/sre-book/table-of-contents/', 'niezawodność, alarmy, budżety błędów'),
        ('The Twelve-Factor App', 'https://12factor.net/', '12 zasad budowy usług odpornych na wdrożenia'),
    ],
    'bezpieczeństwo': [
        ('OWASP Top 10', 'https://owasp.org/www-project-top-ten/', 'najczęstsze zagrożenia aplikacji www'),
        ('OWASP Cheat Sheets', 'https://cheatsheetseries.owasp.org/', 'konkretne zasady bezpiecznej implementacji'),
    ],
    'seo': [
        ('Google SEO starter guide', 'https://developers.google.com/search/docs/fundamentals/seo-starter-guide', 'oficjalne podstawy widoczności w Google'),
    ],
    'osint': [
        ('Bellingcat resources', 'https://www.bellingcat.com/resources/', 'przewodniki i narzędzia śledztw z otwartych źródeł'),
        ('Verification Handbook (GIJN)', 'https://gijn.org/resource/verification-handbook/', 'weryfikacja materiałów, standard dziennikarski'),
    ],
}
TEXT = {'type': 'string'}
PROPOSE = {'type': 'object', 'properties': {'canons': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'name': TEXT, 'url': TEXT, 'what': TEXT}, 'required': ['name', 'url', 'what']}}}, 'required': ['canons']}
JUDGE = {'type': 'object', 'properties': {'keep': {'type': 'array', 'items': {'type': 'integer'}}, 'reason': TEXT}, 'required': ['keep', 'reason']}
HUNT = ('Jesteś łowcą kanonów. Dla tematu (topic) wskaż do 5 NOWYCH źródeł typu „prawa wykonania”: krótkie, uznane, darmowe zbiory zasad, '
        'heurystyk albo list kontrolnych dla praktyków (jak Laws of UX dla projektowania). Nie podawaj tych z known. Tylko prawdziwe, '
        'istniejące adresy, które znasz; bez blogów z newsami, kursów płatnych i stron sprzedażowych.')
CHECK = ('Oceń kandydatów (candidates: numer, nazwa, adres, tytuł strony). W keep podaj numery tylko tych, które są zbiorem zasad lub praw '
         'dla praktyków w temacie (topic), uznanym i darmowym; odrzuć blogi, reklamy, płatne kursy i strony bez zasad.')


def load():
    from news.models import ImportState
    state = ImportState.objects.filter(name=STATE).first()
    found = (state.cursor or {}).get('found', {}) if state else {}
    out = {t: list(rows) for t, rows in CANONS.items()}
    for topic, rows in found.items():
        known = {u for _, u, _ in out.get(topic, [])}
        out.setdefault(topic, []).extend(tuple(r) for r in rows if r[1] not in known)
    return out


def canons(topic, limit=12):
    """Dla agentów: kanony tematu jako krótkie linie (nazwa: co daje)."""
    return [f'{n}: {w} ({u})' for n, u, w in load().get(topic, [])[:limit]]


def _title(url):
    import re
    try:
        r = requests.get(url, timeout=15, headers=UA)
    except requests.RequestException:
        return None
    if r.status_code >= 400:
        return None
    m = re.search(r'<title[^>]*>(.*?)</title>', r.text[:50_000], re.S | re.I)
    return ' '.join(m.group(1).split())[:140] if m else ''


def hunt(force=False):
    """Raz w tygodniu: nowe kanony do każdego tematu (model proponuje, sprawdzamy adres, drugi model ocenia)."""
    from news.models import ImportState
    state, _ = ImportState.objects.get_or_create(name=STATE)
    cur = state.cursor or {}
    if not force and cur.get('at') and timezone.now() - timezone.datetime.fromisoformat(cur['at']) < timedelta(days=6):
        return {}
    found, added = cur.get('found', {}), {}
    for topic, rows in load().items():
        answer, author = common.ask_any(HUNT, {'topic': topic, 'known': [f'{n} {u}' for n, u, _ in rows]}, PROPOSE, force)
        known = {u for _, u, _ in rows}
        cands = []
        for c in answer.get('canons', [])[:5]:
            url = str(c.get('url', ''))
            if url.startswith('https://') and url not in known:
                title = _title(url)
                if title is not None:
                    cands.append({'name': str(c.get('name', ''))[:80], 'url': url, 'what': str(c.get('what', ''))[:160], 'title': title})
        if not cands:
            continue
        verdict, _ = common.ask_any(CHECK, {'topic': topic, 'candidates': [{'n': i, **c} for i, c in enumerate(cands)]}, JUDGE, force, exclude=(author,))
        keep = {int(x) for x in verdict.get('keep', []) if str(x).lstrip('-').isdigit()}
        new = [[c['name'], c['url'], c['what']] for i, c in enumerate(cands) if i in keep]
        if new:
            found.setdefault(topic, []).extend(new)
            added[topic] = [n for n, _, _ in new]
    state.cursor = {'at': timezone.now().isoformat(timespec='minutes'), 'found': found}
    state.save(update_fields=['cursor'])
    return added
