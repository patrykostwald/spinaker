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

_used = {'author': None, 'checker': None}


def _ask_author(prompt, data, schema, force=False):
    answer, member = common.ask_any(prompt, data, schema, force)
    _used['author'] = member
    return answer


def _ask_checker(prompt, data, schema, force=False):
    answer, member = common.ask_any(prompt, data, schema, force, exclude=tuple(m for m in [_used['author']] if m))
    _used['checker'] = member
    return answer


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
        items.append({'id': f'diagnoza:{d.pk}', 'kind': 'diagnoza Dr. Spina (wolno poprawić tylko formę, nigdy sens)',
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
    if kind == 'diagnoza' and finding.get('criterion') in (4, 6):
        from news.clinic_models import SpinDiagnosis
        d = SpinDiagnosis.objects.filter(pk=pk).first()
        if d and polish_diagnosis(d):
            return 'redakcja językowa (sens bez zmian, oryginał zachowany)'
        return ''
    if kind == 'przekaz' and finding.get('criterion') in (4, 6):
        from news.clinic_models import ClinicDailyMessage
        m = ClinicDailyMessage.objects.filter(pk=pk).first()
        if m and polish_message(m):
            return 'redakcja językowa (sens bez zmian, oryginał zachowany)'
        return ''
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
    author = checker = None
    findings = []
    for start in range(0, len(items), BATCH):
        batch = items[start:start + BATCH]
        answer = _ask_author(REVIEW, {'items': batch}, REVIEW_SCHEMA, force)
        rows = [f for f in answer.get('findings', []) if isinstance(f, dict) and any(f.get('id') == i['id'] for i in batch)]
        if rows:
            verdict = _ask_checker(CHECK, {'items': batch, 'findings': rows}, CHECK_SCHEMA, force)
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
        body=readable(findings), scores={'findings': findings, 'checked': len(items), 'authors': [':'.join(_used['author'] or ('-',)), ':'.join(_used['checker'] or ('-',))]},
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
        html = _re.sub(r'(?s)<(script|style|svg|noscript|nav|footer)[^>]*>.*?</\1>', ' ', html)
        parts = [' '.join(_re.sub(r'<[^>]+>', ' ', m).split()) for m in _re.findall(r'(?s)<(?:p|h1|h2|h3|li|dd|dt)[^>]*>(.*?)</(?:p|h1|h2|h3|li|dd|dt)>', html)]
        parts = [x for x in dict.fromkeys(parts) if len(x) >= 25]
        if parts:
            items.append({'id': f'strona:{path}', 'kind': 'stały tekst strony', 'url': 'https://spin.clinic' + path,
                          'text': {'akapity': [_cut(x, 1200) for x in parts[:40]]}})
    return items


def audit_pages(force=False, base=None):
    """Raz na tydzień i na żądanie: wszystkie stałe teksty stron przez czterech recenzentów, sprawdzone drugim modelem."""
    items = page_texts(base)
    if not items:
        raise common.WindowClosed('Strony serwisu niedostępne dla audytu tekstów.')
    author = checker = None
    findings = []
    for item in items:
        answer = _ask_author(REVIEW + ' ' + PANEL + STATE, {'items': [item]}, REVIEW_SCHEMA, force)
        rows = [f for f in answer.get('findings', []) if isinstance(f, dict)]
        for f in rows:
            f['id'] = item['id']
        if rows:
            verdict = _ask_checker(CHECK + ' ' + STATE, {'items': [item], 'findings': rows}, CHECK_SCHEMA, force)
            drop = {int(x) for x in verdict.get('remove', []) if str(x).lstrip('-').isdigit()}
            rows = [f for n, f in enumerate(rows) if n not in drop]
        for f in rows:
            f['url'] = item['url']
        findings += rows
    critical = [f for f in findings if f.get('severity') == 'krytyczne']
    note = AgentNote.objects.create(agent='recenzent', kind='audit', status='new' if findings else 'done',
        title=f"Audyt tekstów stron: {len(items)} stron, {len(findings)} uwag ({len(critical)} krytycznych)",
        body=readable(findings), scores={'findings': findings, 'pages': [i['id'] for i in items], 'authors': [':'.join(_used['author'] or ('-',)), ':'.join(_used['checker'] or ('-',))]},
        sources=sorted({f['url'] for f in findings}))
    common.notify(note)
    return note


# --- redakcja językowa diagnoz (właściciel 5.10: „tylko czytelniej, nie tracąc sensu; nic w sam sens”) ---
# Poprawiamy wyłącznie formę nagłówka, podsumowania i uzasadnienia. Trzy bezpieczniki: (1) te same liczby, nazwy
# i cytaty, (2) długość 60-130% oryginału, (3) drugi model innej firmy potwierdza ten sam sens. Oryginał zostaje
# w usage['original_text'] i jest jawny na stronie („pokaż tekst pierwotny”).
POLISH_FIELDS = ('headline', 'summary', 'analysis')
MESSAGE_FIELDS = ('thesis', 'message', 'analysis')
LIMITS = {'thesis': 160, 'headline': 200}
POLISH = ('Jesteś redaktorem językowym. Popraw WYŁĄCZNIE formę tekstów, żeby czytelnik laik zrozumiał je szybciej: '
          'krótsze zdania, prostszy szyk, bez powtórzeń i żargonu, poprawna polszczyzna, krótkie myślniki. NIE zmieniaj sensu, ocen, '
          'siły twierdzeń, liczb, nazw, nazwisk, dat ani cytatów; nie dodawaj i nie usuwaj żadnej informacji. Sformułowania, które '
          'relacjonują czyjeś stanowisko (np. „opozycja podkreśla, że…”), zostaw w brzmieniu tej strony. Jeśli tekst jest już '
          'czytelny, zwróć go bez zmian.')
SAME = ('Porównaj oryginał i wersję po redakcji każdego pola. same=true tylko wtedy, gdy sens, oceny, stopień pewności, '
        'liczby, nazwy, cytaty i relacjonowane stanowiska stron są identyczne, a zmieniła się wyłącznie forma.')


def _schemas(fields):
    return ({'type': 'object', 'properties': {k: {'type': 'string'} for k in fields}, 'required': list(fields)},
            {'type': 'object', 'properties': {**{k: {'type': 'boolean'} for k in fields}, 'reason': {'type': 'string'}},
             'required': [*fields, 'reason']})


def _facts(text):
    import re as _re
    nums = set(_re.findall(r'\d+(?:[.,]\d+)?', text or ''))
    names = set(_re.findall(r'(?<![.!?]\s)(?<!^)\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,}', text or ''))
    quotes = set(_re.findall(r'[„"]([^”"]{4,})[”"]', text or ''))
    return nums, names, quotes


def safe_rewrite(original, rewritten):
    """Bezpieczniki automatyczne: te same liczby, nazwy własne i cytaty; rozsądna długość."""
    if not rewritten or not original:
        return False
    if not 0.6 <= len(rewritten) / max(1, len(original)) <= 1.3:
        return False
    a, b = _facts(original), _facts(rewritten)
    return a[0] == b[0] and a[1] <= b[1] | {w for w in a[1] if w.lower() in rewritten.lower()} and a[2] == b[2]


def polish(obj, fields, force=False):
    """Redakcja językowa obiektu (diagnoza albo przekaz dnia): tylko forma, trzy bezpieczniki, oryginał w usage."""
    from django.utils import timezone
    original = {k: getattr(obj, k) or '' for k in fields}
    if (obj.usage or {}).get('readability_edit') or not any(original.values()):
        return []
    polish_schema, same_schema = _schemas(fields)
    draft = _ask_author(POLISH, {'tekst': original}, polish_schema, force)
    candidate = {k: str(draft.get(k) or '').strip() for k in fields}
    changed = [k for k in fields if candidate[k] and candidate[k] != original[k] and safe_rewrite(original[k], candidate[k])
               and len(candidate[k]) <= LIMITS.get(k, 100000)]
    if not changed:
        return []
    _, same_schema = _schemas(changed)
    verdict = _ask_checker(SAME, {'oryginał': {k: original[k] for k in changed}, 'po_redakcji': {k: candidate[k] for k in changed}},
                           same_schema, force)
    changed = [k for k in changed if verdict.get(k) is True]
    if not changed:
        return []
    usage = dict(obj.usage or {})
    usage['original_text'] = {k: original[k] for k in changed}
    usage['readability_edit'] = {'at': timezone.now().isoformat(timespec='minutes'), 'fields': changed,
                                 'editor': ':'.join(_used['author'] or ('-',)), 'checker': ':'.join(_used['checker'] or ('-',)),
                                 'reason': str(verdict.get('reason', ''))[:300]}
    for k in changed:
        setattr(obj, k, candidate[k])
    obj.usage = usage
    obj.save(update_fields=[*changed, 'usage'])
    return changed


def polish_diagnosis(diagnosis, force=False):
    return polish(diagnosis, POLISH_FIELDS, force)


def polish_message(message, force=False):
    return polish(message, MESSAGE_FIELDS, force)