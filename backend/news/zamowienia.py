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


def matches(record):
    """CPV z listy albo słowa kluczowe w przedmiocie zamówienia. Zwraca powód (do treści sygnału) albo ''."""
    codes = re.findall(r'\b(\d{8})-\d\b', str(record.data.get('cpvCode', '')))
    hit = [f'CPV {code} ({CPV[code]})' for code in codes if code in CPV]
    if hit:
        return ', '.join(hit)
    found = KEYWORDS.search(record.title or '')
    return f'słowo kluczowe: „{found.group(0).lower()}”' if found else ''


def offer_draft(record, deadline):
    buyer = record.data.get('organizationName') or 'Zamawiający'
    return (f'Szkic oferty (do decyzji właściciela, niczego nie wysyłamy):\n'
            f'Do: {buyer}, {record.data.get("organizationCity", "")}\n'
            f'Dotyczy: {record.data.get("noticeNumber", "")} - {record.title}\n\n'
            'iapply sp. z o.o. (Poznań) składa ofertę na wykonanie przedmiotu zamówienia zgodnie z SWZ. Proponujemy:\n'
            '1. Projekt i wdrożenie strony zgodnej z WCAG 2.1 AA, z audytem dostępności przed odbiorem (raport dla zamawiającego).\n'
            '2. Podgląd działającej strony przed odbiorem, wdrożenie treści i szkolenie redaktorów.\n'
            '3. Deklarację dostępności, instrukcję obsługi i gwarancję zgodnie z SWZ.\n'
            'Cena: do decyzji (punkt odniesienia z cennika iapply: strona firmowa 2 990 zł netto; zakres SWZ zwykle większy).\n'
            f'Termin składania ofert: {deadline:%d.%m.%Y %H:%M} (podpis elektroniczny prezesa lub pełnomocnika).\n'
            'Kontakt: kontakt@iapply.pl')


def body(record, reason, deadline):
    d = record.data
    value = 'poniżej progów UE (dokładna wartość w SWZ)' if d.get('isTenderAmountBelowEU') else 'w SWZ (BZP nie podaje jej na liście)'
    return '\n'.join([
        f"Zamawiający: {d.get('organizationName', '-')}, {d.get('organizationCity', '')}",
        f'Termin ofert: {deadline:%d.%m.%Y %H:%M}',
        f'Wartość: {value}',
        f"Rodzaj: {d.get('orderType', '-')}; ogłoszenie {d.get('noticeNumber', '')}",
        f'Dlaczego: {reason}',
        f'Link: {record.source_url}',
        '', offer_draft(record, deadline), '',
        'Lista kontrolna WCAG i BIP:', *[f'- {item}' for item in WCAG_CHECKLIST],
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
        reason = matches(record)
        if not reason or not deadline or deadline <= now:
            continue
        buyer = record.data.get('organizationName', 'Zamawiający')
        note = AgentNote.objects.create(
            agent='zamowienia', kind='signal', title=f'{buyer[:120]}: {record.title[:90]} (do {deadline.astimezone(WARSAW):%d.%m})',
            body=body(record, reason, deadline.astimezone(WARSAW)), sources=[record.source_url],
            scores={'notice_id': record.external_id, 'buyer': buyer, 'city': record.data.get('organizationCity', ''),
                    'deadline': deadline.isoformat(), 'value': 'below_eu' if record.data.get('isTenderAmountBelowEU') else 'swz',
                    'cpv': record.data.get('cpvCode', ''), 'reason': reason, 'decision': ''})
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
    lines = [f"- {n.title}\n  {n.sources[0]}" for n in created]
    return _mail(owner_address(), f'Zamówienia publiczne: {len(created)} nowe ogłoszenie(a) o strony i dostępność',
                 'Nowe ogłoszenia BZP pasujące do oferty iapply (strony, BIP, WCAG):\n\n' + '\n'.join(lines)
                 + '\n\nSzkic oferty i lista WCAG przy każdym sygnale. Decyzja w panelu: /admin/news/zamowieniesygnal/\n'
                 'Niczego nie wysłaliśmy do zamawiających.', important=True)


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
