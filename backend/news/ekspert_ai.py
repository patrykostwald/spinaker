"""Ekspert AI (właściciel 5.10.2026): raz w tygodniu „Stan wiedzy o AI” na podstawie znalezisk Pielgrzyma
i egzaminów Rekrutera. Konsylium ma być na bieżąco, ale rzetelnie: każde twierdzenie musi mieć źródło
z danych wejściowych, a drugi model (innej firmy) sprawdza raport, zanim trafi do panelu.

Z raportu korzystają: Rekruter (modele wskazane przez eksperta egzaminuje najpierw; egzamin i kryteria bez zmian)
oraz Recenzent merytoryczny spinek, gdy tekst dotyczy AI. Darmowe modele, w oknach limitów jak Pielgrzym."""
import json
import re
from datetime import timedelta

from django.utils import timezone

from news import agents_common as common
from news.agent_models import AgentNote

TEXT = {'type': 'string'}
URL_ITEM = {'type': 'object', 'properties': {'title': TEXT, 'why': TEXT, 'source_url': TEXT}, 'required': ['title', 'why', 'source_url']}
BRIEF_SCHEMA = {'type': 'object', 'properties': {
    'summary': TEXT,
    'developments': {'type': 'array', 'items': URL_ITEM},
    'model_watch': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'model': TEXT, 'why': TEXT, 'source_url': TEXT}, 'required': ['model', 'why', 'source_url']}},
    'method_risks': {'type': 'array', 'items': TEXT}},
    'required': ['summary', 'developments', 'model_watch', 'method_risks']}
CHECK_SCHEMA = {'type': 'object', 'properties': {
    'ok': {'type': 'boolean'}, 'remove': {'type': 'array', 'items': TEXT}, 'reason': TEXT},
    'required': ['ok', 'remove', 'reason']}
PROMPT = ('Jesteś Ekspertem AI Konsylium spin.clinic: znasz najnowsze modele językowe, metody oceny i ich ograniczenia. '
          'Na podstawie WYŁĄCZNIE danych wejściowych (znaleziska badacza, katalogi modeli, wyniki egzaminów) napisz krótki '
          'stan wiedzy: co nowego ma znaczenie dla wiarygodnej, bezstronnej oceny przekazu politycznego, które modele warto '
          'egzaminować i jakie ryzyka widzisz dla naszej metody. Każdy punkt musi mieć source_url z danych wejściowych. '
          'Bez reklamy i przesady; nie wybieraj modeli według firmy ani kraju, tylko według jakości i jawności.')
CHECK = ('Jesteś drugim ekspertem AI. Sprawdź raport kolegi wobec danych wejściowych. Wypisz w remove tytuły lub nazwy '
         'modeli, których dane nie potwierdzają albo które są przesadzone. ok=false, jeśli raport jako całość wprowadza w błąd.')
WEEK = timedelta(days=6)


def inputs():
    since = timezone.now() - timedelta(days=14)
    findings = []
    for note in AgentNote.objects.filter(agent='pielgrzym', kind='finding', created_at__gte=since)[:8]:
        try:
            findings.extend(json.loads(note.body).get('findings', []))
        except (ValueError, AttributeError):
            continue
    from news.clinic_models import CouncilSeat
    exams = list(CouncilSeat.objects.order_by('-pk').values('provider', 'model', 'status')[:12]) if hasattr(CouncilSeat, 'status') else []
    return {'findings': [{k: str(f.get(k, ''))[:1200] for k in ('title', 'url', 'summary')} for f in findings][:20], 'exams': exams}


def _grounded(items, urls, key='source_url'):
    return [item for item in items if isinstance(item, dict) and item.get(key) in urls]


def step(force=False):
    last = AgentNote.objects.filter(agent='ekspert', kind='report').first()
    if last and not force and timezone.now() - last.created_at < WEEK:
        return last
    data = inputs()
    urls = {f['url'] for f in data['findings'] if f.get('url')}
    if not urls:
        raise common.WindowClosed('Brak świeżych znalezisk Pielgrzyma.')
    author, checker = common.members(2, force)
    brief = common.ask(author, PROMPT, data, BRIEF_SCHEMA, force)
    brief['developments'] = _grounded(brief.get('developments', []), urls)
    brief['model_watch'] = _grounded(brief.get('model_watch', []), urls)
    verdict = common.ask(checker, CHECK, {'input': data, 'report': brief}, CHECK_SCHEMA, force)
    removed = {str(x).casefold() for x in verdict.get('remove', [])}
    brief['developments'] = [d for d in brief['developments'] if d['title'].casefold() not in removed]
    brief['model_watch'] = [m for m in brief['model_watch'] if m['model'].casefold() not in removed]
    status = 'new' if verdict.get('ok') else 'rejected'
    data = {**brief, 'check': verdict.get('reason', ''), 'authors': [':'.join(author), ':'.join(checker)]}
    note = AgentNote.objects.create(agent='ekspert', kind='report', status=status,
        title=f'Stan wiedzy o AI: {timezone.localdate():%d.%m.%Y}', body=readable(data), scores=data,
        sources=sorted({d['source_url'] for d in brief['developments'] + brief['model_watch']}))
    if status == 'new':
        common.notify(note)
    return note


def readable(data):
    lines = [data.get('summary', ''), '']
    if data.get('developments'):
        lines += ['Co nowego:'] + [f"- {d['title']}: {d['why']} ({d['source_url']})" for d in data['developments']] + ['']
    if data.get('model_watch'):
        lines += ['Modele do egzaminu:'] + [f"- {m['model']}: {m['why']} ({m['source_url']})" for m in data['model_watch']] + ['']
    if data.get('method_risks'):
        lines += ['Ryzyka dla naszej metody:'] + [f'- {r}' for r in data['method_risks']] + ['']
    lines += [f"Sprawdzenie drugiego eksperta: {data.get('check', '')}", f"Autorzy: {', '.join(data.get('authors', []))}"]
    return chr(10).join(lines).strip()


def latest():
    note = AgentNote.objects.filter(agent='ekspert', kind='report', status='new').first()
    return note.scores if note and isinstance(note.scores, dict) and note.scores else None


def watched_models():
    """Nazwy modeli wskazanych przez eksperta (małe litery) - Rekruter egzaminuje je wcześniej."""
    brief = latest() or {}
    return {str(m.get('model', '')).casefold().strip() for m in brief.get('model_watch', []) if m.get('model')}


AI_TEXT = re.compile(r'\b(AI|SI|LLM|model\w*|sztuczn\w+ inteligencj\w+|algorytm\w*|chatbot\w*)\b', re.I)


def context_for(texts):
    """Krótki stan wiedzy dla recenzenta, tylko gdy tekst dotyczy AI."""
    joined = ' '.join(str(v) for v in (texts or {}).values())
    brief = latest()
    if not brief or not AI_TEXT.search(joined):
        return None
    return {'summary': brief.get('summary', '')[:600], 'method_risks': brief.get('method_risks', [])[:5]}
