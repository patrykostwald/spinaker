"""Pętla „Zamówienia publiczne” (plan finansowy 6.10, ruch 7): strony WWW i dostępność dla gmin, szkół i instytucji.

Codziennie bez AI i bez sieci czyta ogłoszenia BZP zapisane już przez zbieracz BZP (PublicRecord source='bzp',
kind='notice': CPV, zamawiający, termin ofert) i wybiera te o stronach internetowych, BIP i dostępności (WCAG).
Każde pasujące ogłoszenie o zamówieniu z terminem w przyszłości = jeden sygnał AgentNote (agent 'zamowienia',
kind 'signal') z terminem, zamawiającym, wartością, linkiem, szkicem oferty iapply i listą kontrolną WCAG.
Niczego nie wysyła do zamawiających. Decyzja „składamy / pomijamy” należy do właściciela w panelu;
sygnał bez decyzji po terminie ofert zamyka się sam („termin minął”).

Zasięg: BZP obejmuje zamówienia od 130 tys. zł netto. Mniejsze zapytania ofertowe gmin (typowa strona za 5-20 tys. zł)
są na platformach zakupowych i w BIP; platformazakupowa.pl nie ma publicznego RSS ani API (sprawdzone 6.10.2026,
robots.txt Crawl-delay 900), więc jej nie czytamy.
"""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

WARSAW = ZoneInfo('Europe/Warsaw')
CPV = {'72413000': 'projektowanie stron WWW', '72212224': 'oprogramowanie do edycji stron WWW',
       '79822500': 'projektowanie graficzne', '72415000': 'hosting stron WWW', '72420000': 'rozwijanie internetu',
       '72400000': 'usługi internetowe', '72212220': 'oprogramowanie internetowe'}
KEYWORDS = re.compile(r'stron[aeyi]? (?:internetow|www)|stron internetowych|serwis\w* internetow|portal\w* (?:internetow|www|informacyjn)'
                      r'|\bwcag\b|dostępnoś\w* cyfrow|deklaracj\w* dostępności|\bbip\b|biuletyn\w* informacji publicznej', re.I)
# Łowca zleceń (właściciel 21.10: „alerty dla projektów, które moglibyśmy zrealizować”): oprócz stron WWW
# wszystko, co iapply robi. Każdy profil: kody CPV, słowa w przedmiocie zamówienia i krótki zakres do szkicu oferty.
PROFILES = [
    {'key': 'www', 'label': 'Strony WWW, BIP i dostępność', 'cpv': CPV, 'keywords': KEYWORDS,
     'offer': ['Projekt i wdrożenie strony zgodnej z WCAG 2.1 AA, z audytem dostępności przed odbiorem (raport dla zamawiającego).',
               'Podgląd działającej strony przed odbiorem, wdrożenie treści i szkolenie redaktorów.',
               'Deklarację dostępności, instrukcję obsługi i gwarancję zgodnie z SWZ.']},
    {'key': 'oprogramowanie', 'label': 'Oprogramowanie i aplikacje',
     'cpv': {'72200000': 'programowanie i doradztwo', '72210000': 'programowanie pakietów', '72212000': 'programowanie oprogramowania',
             '72230000': 'oprogramowanie na zamówienie', '72232000': 'oprogramowanie do przetwarzania transakcji',
             '72240000': 'analiza i programowanie systemów', '72260000': 'usługi w zakresie oprogramowania',
             '72262000': 'rozbudowa oprogramowania', '72263000': 'wdrażanie oprogramowania', '72266000': 'doradztwo w zakresie oprogramowania'},
     'keywords': re.compile(r'aplikacj\w* (?:mobiln|webow|internetow|dedykowan)|oprogramowani\w* (?:na zamówienie|dedykowan)'
                            r'|system\w* (?:informatyczn|teleinformatyczn|informacji o prawie)|(?:budow|rozbudow|modernizacj|wdrożeni|wykonani)\w* (?:\w+ )?(?:platformy|aplikacji) (?:cyfrow|internetow|mobiln|webow|do )'
                            r'|platform\w* (?:cyfrow|internetow|e-)|e-usług', re.I),
     'offer': ['Analiza wymagań z SWZ i działający prototyp przed odbiorem.',
               'Wykonanie i wdrożenie w uzgodnionych etapach, z testami i dokumentacją.',
               'Przeniesienie praw autorskich, szkolenie użytkowników i gwarancja zgodnie z SWZ.']},
    {'key': 'ai', 'label': 'AI i analiza danych',
     'cpv': {'72316000': 'analiza danych', '72310000': 'przetwarzanie danych', '72320000': 'bazy danych',
             '72322000': 'zarządzanie danymi', '72319000': 'dostarczanie danych'},
     'keywords': re.compile(r'sztuczn\w* inteligencj|\bAI\b|uczeni\w* maszynow|chat\s?bot|czat\s?bot|asystent\w* (?:wirtualn|AI|cyfrow)'
                            r'|analiz\w* (?:dużych )?danych|model\w* językow|\bLLM\b|przetwarzani\w* języka|rozpoznawani\w* mowy'
                            r'|transkrypcj|anonimizacj', re.I),
     'offer': ['Rozwiązanie AI z kontrolą jakości odpowiedzi (kilka niezależnych modeli, odpowiedź „nie wiem” zamiast zgadywania).',
               'Pilot na danych zamawiającego, pomiar jakości przed wdrożeniem, dane przetwarzane w UE.',
               'Dokumentacja, szkolenie i opieka po wdrożeniu zgodnie z SWZ.']},
    {'key': 'automatyzacja', 'label': 'Automatyzacja i integracje',
     'cpv': {'72227000': 'integracja oprogramowania'},
     'keywords': re.compile(r'automatyzacj\w* (?:proces|obsług|zadań|pracy|biur)|\bRPA\b|robotyzacj\w* proces|integracj\w* (?:system\w* informatyczn|danych|oprogramow)'
                            r'|(?:elektroniczn\w* )?obieg\w* dokument|workflow', re.I),
     'offer': ['Mapa procesu i lista integracji przed rozpoczęciem prac.',
               'Automatyzacja z dziennikiem działań i możliwością ręcznego przejęcia każdego kroku.',
               'Szkolenie, instrukcja i gwarancja zgodnie z SWZ.']},
    {'key': 'marketing', 'label': 'Marketing, media społecznościowe i filmy',
     'cpv': {'79340000': 'reklama i marketing', '79341000': 'usługi reklamowe', '79341400': 'kampanie reklamowe',
             '79342000': 'usługi marketingowe', '79413000': 'doradztwo marketingowe', '79416000': 'public relations',
             '92111200': 'produkcja filmów reklamowych'},
     'keywords': re.compile(r'media\w* społecznościow|social media|prowadzeni\w* (?:profil|kanał)|film\w* (?:promocyjn|informacyjn)'
                            r'|spot\w* (?:promocyjn|reklamow)|kampani\w* (?:promocyjn|informacyjn|reklamow)', re.I),
     'offer': ['Plan publikacji z kalendarzem do akceptacji (z możliwością zmian przez zamawiającego).',
               'Grafiki, krótkie filmy i teksty w jednym stylu, publikacja i raport miesięczny.',
               'Przeniesienie praw do materiałów zgodnie z SWZ.']},
    {'key': 'szkolenia', 'label': 'Szkolenia cyfrowe i AI',
     'cpv': {'80533100': 'szkolenia komputerowe', '80533000': 'szkolenia użytkowników komputerów'},
     'keywords': re.compile(r'szkoleni\w* (?:z zakresu |z |dotycząc\w* )?(?:sztucznej inteligencji|AI\b|kompetencji cyfrowych|narzędzi cyfrowych)'
                            r'|kompetencj\w* cyfrow', re.I),
     'offer': ['Program szkolenia dopasowany do grupy, ćwiczenia na narzędziach używanych przez zamawiającego.',
               'Materiały po szkoleniu i ankieta oceny.',
               'Terminy i forma (stacjonarnie lub zdalnie) zgodnie z SWZ.']},
]
ACTIONABLE = ('ContractNotice', 'CompetitionNotice')
LOOKBACK = timedelta(days=3)
WCAG_CHECKLIST = [
    'WCAG 2.1 AA (ustawa z 4.04.2019 o dostępności cyfrowej): wymagania z SWZ wypisane punkt po punkcie',
    'kontrast tekstu co najmniej 4,5:1, powiększenie do 200% bez utraty treści',
    'pełna obsługa klawiaturą, widoczny fokus, kolejność tabulacji, link „przejdź do treści”',
    'teksty alternatywne obrazów, napisy do filmów, transkrypcje nagrań',
    'nagłówki i punkty orientacyjne (landmarki), poprawne etykiety formularzy i komunikaty błędów',
    'język strony, czytelne linki, brak treści migających częściej niż 3 razy na sekundę',
    'deklaracja dostępności według wzoru ministra (adres /deklaracja-dostepnosci) i dane koordynatora',
    'tekst łatwy do czytania (ETR) i informacja w polskim języku migowym (PJM), jeśli wymaga ich zamawiający',
    'BIP: menu przedmiotowe, rejestr zmian, metryczki dokumentów, stopka redakcyjna (jeśli zamówienie obejmuje BIP)',
    'audyt: automatyczny (axe, Lighthouse) + ręczny z czytnikiem ekranu (NVDA, VoiceOver) i raport dla zamawiającego',
    'szkolenie redaktorów z dodawania dostępnych treści i instrukcja w PDF',
    'okres gwarancji i poprawek dostępności po odbiorze (wpisać zgodnie z SWZ)',
]


def _date(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return timezone.make_aware(dt, WARSAW) if timezone.is_naive(dt) else dt


def classify(record):
    """(profil, powód) dla pierwszego pasującego profilu albo (None, ''). Najpierw CPV, potem słowa w przedmiocie.
    Dostawy (np. sprzętu) tylko z kodem CPV oprogramowania 48xxxxxx - iapply nie sprzedaje sprzętu."""
    codes = re.findall(r'\b(\d{8})-\d\b', str(record.data.get('cpvCode', '')))
    if record.data.get('orderType') == 'Delivery' and not any(code.startswith('48') for code in codes):
        return None, ''
    for profile in PROFILES:
        hit = [f"CPV {code} ({profile['cpv'][code]})" for code in codes if code in profile['cpv']]
        if hit:
            return profile, ', '.join(hit)
    # Szkolenia najpierw: „szkolenie z AI” to szkolenie, nie wdrożenie AI.
    for profile in sorted(PROFILES, key=lambda p: p['key'] != 'szkolenia'):
        found = profile['keywords'].search(record.title or '')
        if found:
            return profile, f'słowo kluczowe: „{found.group(0).lower()}”'
    return None, ''


def matches(record):
    """Powód dopasowania (do treści sygnału) albo ''."""
    return classify(record)[1]


def offer_draft(record, deadline, profile=None):
    buyer = record.data.get('organizationName') or 'Zamawiający'
    lines = (profile or PROFILES[0])['offer']
    return (f'Szkic oferty (do decyzji właściciela, niczego nie wysyłamy):\n'
            f'Do: {buyer}, {record.data.get("organizationCity", "")}\n'
            f'Dotyczy: {record.data.get("noticeNumber", "")} - {record.title}\n\n'
            'iapply sp. z o.o. (Poznań) składa ofertę na wykonanie przedmiotu zamówienia zgodnie z SWZ. Proponujemy:\n'
            + ''.join(f'{i}. {line}\n' for i, line in enumerate(lines, 1)) +
            'Przed decyzją: sprawdzić w SWZ warunki udziału (doświadczenie, referencje), w razie potrzeby partner w konsorcjum.\n'
            'Cena: do decyzji właściciela, na podstawie zakresu z SWZ.\n'
            f'Termin składania ofert: {deadline:%d.%m.%Y %H:%M} (podpis elektroniczny prezesa lub pełnomocnika).\n'
            'Kontakt: kontakt@iapply.pl')


def body(record, reason, deadline, profile=None):
    d = record.data
    profile = profile or PROFILES[0]
    value = 'poniżej progów UE (dokładna wartość w SWZ)' if d.get('isTenderAmountBelowEU') else 'w SWZ (BZP nie podaje jej na liście)'
    checklist = ['', 'Lista kontrolna WCAG i BIP:', *[f'- {item}' for item in WCAG_CHECKLIST]] if profile['key'] == 'www' else []
    return '\n'.join([
        f"Obszar: {profile['label']}",
        f"Zamawiający: {d.get('organizationName', '-')}, {d.get('organizationCity', '')}",
        f'Termin ofert: {deadline:%d.%m.%Y %H:%M}',
        f'Wartość: {value}',
        f"Rodzaj: {d.get('orderType', '-')}; ogłoszenie {d.get('noticeNumber', '')}",
        f'Dlaczego: {reason}',
        f'Link: {record.source_url}',
        '', offer_draft(record, deadline, profile), *checklist,
        '', 'Decyzja w panelu: „Składamy” albo „Pomijamy”. Bez decyzji sygnał zamknie się sam po terminie ofert.'])


def scan(now=None):
    from news.agent_models import AgentNote
    from news.public_records_models import PublicRecord
    now = now or timezone.now()
    records = PublicRecord.objects.filter(source='bzp', kind='notice', fetched_at__gte=now - LOOKBACK)
    seen = set(AgentNote.objects.filter(agent='zamowienia').values_list('scores__notice_id', flat=True))
    created, scanned = [], 0
    for record in records.order_by('fetched_at', 'pk').iterator():
        scanned += 1
        if record.external_id in seen or record.data.get('noticeType') not in ACTIONABLE:
            continue
        deadline = _date(record.data.get('submittingOffersDate'))
        profile, reason = classify(record)
        if not reason or not deadline or deadline <= now:
            continue
        buyer = record.data.get('organizationName', 'Zamawiający')
        note = AgentNote.objects.create(
            agent='zamowienia', kind='signal', title=f'{buyer[:120]}: {record.title[:90]} (do {deadline.astimezone(WARSAW):%d.%m})',
            body=body(record, reason, deadline.astimezone(WARSAW), profile), sources=[record.source_url],
            scores={'notice_id': record.external_id, 'buyer': buyer, 'city': record.data.get('organizationCity', ''),
                    'deadline': deadline.isoformat(), 'value': 'below_eu' if record.data.get('isTenderAmountBelowEU') else 'swz',
                    'cpv': record.data.get('cpvCode', ''), 'reason': reason, 'profile': profile['key'], 'decision': ''})
        seen.add(record.external_id)
        created.append(note)
    return scanned, created


def close_expired(now=None):
    """Bez decyzji po terminie ofert: zamknięte automatycznie (nic nie czeka bez końca)."""
    from news.agent_models import AgentNote
    now = now or timezone.now()
    closed = 0
    for note in AgentNote.objects.filter(agent='zamowienia', status__in=('new', 'pending')):
        deadline = _date(note.scores.get('deadline'))
        if deadline and deadline < now:
            note.status, note.scores = 'rejected', {**note.scores, 'decision': 'termin minął'}
            note.save(update_fields=['status', 'scores'])
            closed += 1
    return closed


def decide(note, decision, user=None):
    assert decision in ('składamy', 'pomijamy')
    note.status = 'accepted' if decision == 'składamy' else 'rejected'
    note.scores = {**note.scores, 'decision': decision}
    note.decided_by, note.decided_at = user, timezone.now()
    note.save(update_fields=['status', 'scores', 'decided_by', 'decided_at'])


def notify(created):
    """Jeden mail na bieg z nowymi sygnałami (terminy są krótkie). Brak SMTP nie zatrzymuje pętli: sygnały są w panelu."""
    if not created:
        return False
    from news.sales import owner_address
    from news.social_publish import _mail
    labels = {p['key']: p['label'] for p in PROFILES}
    groups = {}
    for note in sorted(created, key=lambda n: n.scores.get('deadline', '')):  # najbliższy termin ofert pierwszy
        groups.setdefault(note.scores.get('profile', 'www'), []).append(f"- {note.title}\n  {note.sources[0]}")
    text = '\n\n'.join(f'{labels.get(key, key)}:\n' + '\n'.join(lines) for key, lines in groups.items())
    return _mail(owner_address(), f'Łowca zleceń: {len(created)} nowe zamówienie(a) dla iapply',
                 'Nowe ogłoszenia BZP pasujące do oferty iapply, według obszarów, najbliższy termin ofert pierwszy:\n\n' + text
                 + '\n\nPrzy każdym sygnale szkic oferty; przed decyzją sprawdź w SWZ warunki udziału (referencje).\n'
                 'Decyzja w panelu: /admin/news/zamowieniesygnal/\nNiczego nie wysłaliśmy do zamawiających.', important=True)


def run(now=None):
    from news.public_records_models import PublicRecord
    now = now or timezone.now()
    scanned, created = scan(now)
    closed = close_expired(now)
    mailed = notify(created)
    total = PublicRecord.objects.filter(source='bzp', kind='notice').count()
    return {'status': 'ok', 'scanned': scanned, 'signals': len(created), 'closed': closed, 'mailed': bool(mailed),
            'bzp_notices': total, 'produced': scanned,
            **({'hint': 'Brak ogłoszeń BZP w bazie: włącz zbieracz BZP (BZP_API_ENABLED).'} if not total else {})}
