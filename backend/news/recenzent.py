"""Recenzent (właściciel 5.10): czyta wszystko, co trafia na spin.clinic, i wytyka błędy według ostrych, rzetelnych
i bezstronnych kryteriów. Drugi model innej firmy sprawdza jego zarzuty (bez zarzutów na wyrost).

Co robi z ustaleniami:
- raport instytucjonalny z poważnym zarzutem wraca do Raportysty do poprawki (najwyżej 3 rundy),
- spinka Dr. Spina wraca do zwykłej recenzji (Redaktor tytułów i językoznawca),
- diagnoz nikt nie zmienia (decyzja właściciela): Recenzent je tylko zgłasza w panelu,
- błędy krytyczne idą mailem do właściciela.
Darmowe modele, w oknach limitów jak pozostali agenci; najwyżej BATCH tekstów na jedno zapytanie."""
import hashlib
import json
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from news import agents_common as common
from news.agent_models import AgentNote

BATCH = 8
SEEN = 'recenzent:seen:'
CRITERIA = (
    '1. Pokrycie: każde zdanie ma oparcie w danych (dane wejściowe przy tekście); żadnych faktów, liczb ani wniosków spoza nich. '
    '2. Ta sama miara: rządzący i opozycja opisani tymi samymi słowami i progami; brak kwalifikatorów tylko dla jednej strony. '
    '3. Bez intencji i ocen ludzi: opisujemy słowa i materiały, nie motywy, charaktery ani winę. '
    '4. Czytelność dla laika: krótkie zdania, bez żargonu, wiadomo, co z czego wynika; tytuł mówi, co pokazano. '
    '5. Szablon: tytuł „Rodzaj: synteza”, podtytuł dwa zdania (co zbadano, co znaleziono); raport zaczyna się od najważniejszego. '
    '6. Polszczyzna: błędy, powtórzenia, anglicyzmy, długie myślniki, jednoliterowe słowa na końcu wiersza. '
    '7. Spójność: liczby, nazwy i daty zgadzają się w obrębie tekstu i z danymi.')
REVIEW = ('Jesteś Recenzentem spin.clinic: najbardziej wymagającym, rzetelnym i bezstronnym redaktorem, jakiego zna polskie '
          'dziennikarstwo. Dla każdego tekstu z items wypisz tylko rzeczywiste błędy według kryteriów: ' + CRITERIA +
          ' Każdy zarzut: id tekstu, criterion (1-7), severity (krytyczne, ważne, drobne), quote (dokładny fragment), '
          'problem (jedno zdanie) i fix (gotowa poprawka). Bez zarzutów na wyrost; jeśli tekst jest dobry, nie wypisuj nic.')
CHECK = ('Jesteś drugim recenzentem. Sprawdź zarzuty kolegi wobec tekstów i danych. W remove wpisz numery (index od 0) '
         'zarzutów nietrafnych, przesadzonych albo niepopartych cytatem z tekstu. Oceniaj tak samo surowo dla obu stron sceny politycznej.')
FINDING = {'type': 'object', 'properties': {
    'id': {'type': 'string'}, 'criterion': {'type': 'integer'}, 'severity': {'type': 'string', 'enum': ['krytyczne', 'ważne', 'drobne']},
    'quote': {'type': 'string'}, 'problem': {'type': 'string'}, 'fix': {'type': 'string'}},
    'required': ['id', 'criterion', 'severity', 'quote', 'problem', 'fix']}
REVIEW_SCHEMA = {'type': 'object', 'properties': {'findings': {'type': 'array', 'items': FINDING}}, 'required': ['findings']}
CHECK_SCHEMA = {'type': 'object', 'properties': {'remove': {'type': 'array', 'items': {'type': 'integer'}}, 'reason': {'type': 'string'}},
                'required': ['remove', 'reason']}


def _key(item):
    """Stały klucz tekstu (hash() w Pythonie zmienia się między procesami)."""
    return SEEN + item['id'] + ':' + hashlib.sha1(json.dumps(item['text'], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _cut(value, limit=700):
    value = ' '.join(str(value or '').split())
    return value if len(value) <= limit else value[:limit - 1] + '…'


def collect(since=None):
    """Nowe teksty od ostatniego przeglądu: spinki Dr. Spina, przekazy dnia, raporty i diagnozy."""
    from news.account_models import PersonalContextThread
    from news.clinic import published_diagnoses
    from news.clinic_models import ClinicDailyMessage
    from news.report_models import InstitutionalReport
    since = since or timezone.now() - timedelta(days=2)
    items = []
    for t in PersonalContextThread.objects.filter(owner__isnull=True, is_public=True, updated_at__gte=since).order_by('-updated_at')[:20]:
        notes = [i.link_note for i in t.items.order_by('position') if i.link_note][:6]
        items.append({'id': f'spinka:{t.pk}', 'kind': 'spinka Dr. Spina', 'url': f'https://spin.clinic/spinki/{t.pk}',
                      'text': {'tytuł': t.title, 'podtytuł': t.description, 'połączenia': notes}})
    for m in ClinicDailyMessage.objects.filter(status='approved', day__gte=since.date()).order_by('-day')[:6]:
        items.append({'id': f'przekaz:{m.pk}', 'kind': 'przekaz dnia', 'url': f'https://spin.clinic/klinika/przekazy/{m.day}',
                      'text': {'strona': m.camp, 'teza': _cut(m.thesis), 'przekaz': _cut(m.message, 900)}})
    for r in InstitutionalReport.objects.filter(status='awaiting_approval').order_by('-pk')[:3]:
        items.append({'id': f'raport:{r.pk}', 'kind': 'raport instytucjonalny', 'url': 'https://spin.clinic/panel',
                      'text': {'zdania': [s.get('text', '') for s in (r.draft or {}).get('sentences', [])][:12]},
                      'dane': {k: r.snapshot.get(k) for k in ('kind', 'start', 'end_exclusive', 'aggregates')}})
    for d in published_diagnoses().filter(created_at__gte=since).order_by('-created_at')[:12]:
        items.append({'id': f'diagnoza:{d.pk}', 'kind': 'diagnoza Dr. Spina (tylko zgłoszenie, bez zmian)',
                      'url': f'https://spin.clinic/klinika/{d.pk}', 'text': {'nagłówek': d.headline, 'w skrócie': _cut(d.summary)},
                      'dane': {'wpis': _cut(d.post.text, 600), 'siła': d.intensity}})
    return [i for i in items if not cache.get(_key(i))]


def _act(finding, item):
    """Poważny zarzut uruchamia poprawkę tam, gdzie wolno; diagnoz nie zmieniamy."""
    kind, pk = finding['id'].split(':', 1)
    if finding['severity'] == 'drobne':
        return ''
    if kind == 'raport':
        from news import raportysta
        from news.report_models import InstitutionalReport
        report = InstitutionalReport.objects.filter(pk=pk, status='awaiting_approval').first()
        if report and report.round < 3:
            raportysta._retry(report, [f"Recenzent ({finding['severity']}): {finding['problem']} Poprawka: {finding['fix']}"])
            report.status = 'working'
            report.save()
            return 'raport wrócił do poprawki'
    if kind == 'spinka':
        from news.account_models import PersonalContextThread
        from news.thread_review import enqueue
        from news.thread_review_models import ThreadReview
        thread = PersonalContextThread.objects.filter(pk=pk).first()
        review = ThreadReview.objects.filter(thread=thread).first() if thread else None
        if thread and review:
            enqueue(thread, {**review.payload.get('evidence', {}), 'recenzent': f"{finding['problem']} Poprawka: {finding['fix']}"})
            return 'spinka wróciła do recenzji'
    return ''


def step(force=False, items=None):
    items = items if items is not None else collect()
    if not items:
        return None
    author, checker = common.members(2, force)
    findings = []
    for start in range(0, len(items), BATCH):
        batch = items[start:start + BATCH]
        answer = common.ask(author, REVIEW, {'items': batch}, REVIEW_SCHEMA, force)
        rows = [f for f in answer.get('findings', []) if isinstance(f, dict) and any(f.get('id') == i['id'] for i in batch)]
        if rows:
            verdict = common.ask(checker, CHECK, {'items': batch, 'findings': rows}, CHECK_SCHEMA, force)
            drop = {int(x) for x in verdict.get('remove', []) if str(x).lstrip('-').isdigit()}
            rows = [f for n, f in enumerate(rows) if n not in drop]
        findings += rows
        for item in batch:
            cache.set(_key(item), 1, 60 * 60 * 24 * 14)
    by_id = {i['id']: i for i in items}
    for f in findings:
        f['action'] = _act(f, by_id.get(f['id'], {}))
        f['url'] = by_id.get(f['id'], {}).get('url', '')
    critical = [f for f in findings if f.get('severity') == 'krytyczne']
    note = AgentNote.objects.create(agent='recenzent', kind='review', status='new' if findings else 'done',
        title=f"Recenzja treści: {len(items)} tekstów, {len(findings)} uwag ({len(critical)} krytycznych)",
        body=readable(findings), scores={'findings': findings, 'checked': len(items), 'authors': [':'.join(author), ':'.join(checker)]},
        sources=sorted({f['url'] for f in findings if f.get('url')}))
    if critical:
        common.notify(note)
    return note


def readable(findings):
    if not findings:
        return 'Bez uwag: wszystkie sprawdzone teksty spełniają kryteria.'
    order = {'krytyczne': 0, 'ważne': 1, 'drobne': 2}
    lines = []
    for f in sorted(findings, key=lambda f: order.get(f.get('severity'), 3)):
        lines.append(f"[{f.get('severity')}] {f.get('id')} (kryterium {f.get('criterion')}): {f.get('problem')}")
        lines.append(f"  Fragment: „{f.get('quote')}”")
        lines.append(f"  Poprawka: {f.get('fix')}" + (f" · {f['action']}" if f.get('action') else ''))
    return chr(10).join(lines)


# --- audyt stałych tekstów stron (właściciel 5.10: „wszystko, co publikujemy na stronie, musi być rzetelne i czytelne”) ---
PANEL = ('Patrzysz na tekst czterema oczami naraz i przy każdym zarzucie podajesz perspektywę w polu problem (na początku, w nawiasie): '
         '(językoznawca) poprawność, styl, powtórzenia, anglicyzmy, interpunkcja; '
         '(dziennikarz) czy najważniejsze jest na początku, czy tekst jest konkretny, ciekawy i bez waty; '
         '(rzetelność) czy obietnice i twierdzenia o serwisie zgadzają się z tym, jak serwis działa (dane w opisie stanu), bez przesady; '
         '(czytelnik) czy laik zrozumie bez żargonu i wewnętrznych nazw. ')
STATE = ('Stan serwisu do sprawdzania rzetelności: oceny w spinkach dotyczą połączeń między boksami w kolejności ✕ ? ✓; '
         'diagnozy przygotowuje AI (konsylium modeli), człowiek może je tylko wycofać; ta sama miara dla rządzących i opozycji; '
         'tytuł spinki do 65 znaków, opis do 170; spinki Dr. Spina z diagnoz tylko od siły 70/100; serwis jest w becie.')


def page_texts(base=None):
    """Widoczne teksty stron serwisu (akapity i nagłówki) z listy Projektanta."""
    import re as _re
    import requests
    from news.projektant import PAGES, _site_base
    base = base or _site_base()
    items = []
    for path in PAGES:
        try:
            html = requests.get(base.rstrip('/') + path, timeout=20, headers={'User-Agent': 'spin.clinic Recenzent'}).text
        except requests.RequestException:
            continue
        html = _re.sub(r'(?s)<(script|style|svg|noscript)[^>]*>.*?</\1>', ' ', html)
        parts = [' '.join(_re.sub(r'<[^>]+>', ' ', m).split()) for m in _re.findall(r'(?s)<(?:p|h1|h2|h3|li|dd|dt)[^>]*>(.*?)</(?:p|h1|h2|h3|li|dd|dt)>', html)]
        parts = [x for x in dict.fromkeys(parts) if len(x) >= 25]
        if parts:
            items.append({'id': f'strona:{path}', 'kind': 'stały tekst strony', 'url': 'https://spin.clinic' + path,
                          'text': {'akapity': [_cut(x, 400) for x in parts[:40]]}})
    return items


def audit_pages(force=False, base=None):
    """Raz na tydzień i na żądanie: wszystkie stałe teksty stron przez czterech recenzentów, sprawdzone drugim modelem."""
    items = page_texts(base)
    if not items:
        raise common.WindowClosed('Strony serwisu niedostępne dla audytu tekstów.')
    author, checker = common.members(2, force)
    findings = []
    for item in items:
        answer = common.ask(author, REVIEW + ' ' + PANEL + STATE, {'items': [item]}, REVIEW_SCHEMA, force)
        rows = [f for f in answer.get('findings', []) if isinstance(f, dict)]
        for f in rows:
            f['id'] = item['id']
        if rows:
            verdict = common.ask(checker, CHECK + ' ' + STATE, {'items': [item], 'findings': rows}, CHECK_SCHEMA, force)
            drop = {int(x) for x in verdict.get('remove', []) if str(x).lstrip('-').isdigit()}
            rows = [f for n, f in enumerate(rows) if n not in drop]
        for f in rows:
            f['url'] = item['url']
        findings += rows
    critical = [f for f in findings if f.get('severity') == 'krytyczne']
    note = AgentNote.objects.create(agent='recenzent', kind='audit', status='new' if findings else 'done',
        title=f"Audyt tekstów stron: {len(items)} stron, {len(findings)} uwag ({len(critical)} krytycznych)",
        body=readable(findings), scores={'findings': findings, 'pages': [i['id'] for i in items], 'authors': [':'.join(author), ':'.join(checker)]},
        sources=sorted({f['url'] for f in findings}))
    common.notify(note)
    return note
