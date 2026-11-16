"""Samorozwój przeszłość.today (właściciel 16.11.2026): portal ma się zasilać i rozwijać bez ręcznego kroku właściciela.

Trzy części, wszystkie bez sieci i bez modeli AI (tylko nasza baza):

1. odblokuj(): zadanie zbieracza, które padło ODLOZ_PO_BLEDACH razy (domyślnie 10; przy przerwie rosnącej do 24 h to około
   tygodnia prób), zostaje odłożone: done=True, błąd z przedrostkiem „odlozone:”. Cykl źródła może się wtedy domknąć, a kolejny
   cykl (po refresh_hours) zakłada zadania od nowa, np. z poprawionym adresem po wdrożeniu. Wcześniej jedno trwale błędne zadanie
   trzymało źródło w stanie „deferred” na zawsze, a odblokowanie wymagało ręcznego polecenia na serwerze (5.11.2026: interpelacje,
   zapytania, KRS, FTS). Rekordów nie usuwamy. Nie dotyczy źródeł zatrzymanych przez bramkę dostępu (blocked_access_review), źródeł
   w trakcie biegu (dzierżawa) ani zadań oznaczonych do przeglądu człowieka.
2. doba(): co doszło w ciągu doby (rekordy per źródło), co się nie udało (zaległe, puste, błędy zadań, odłożone), rozgrzewanie
   tematów dnia, pokrycie KRS i kolejka rozwoju. Migawka w RepairerState; sekcja w porannym Raporcie pętli (jeden mail dziennie,
   decyzja z 5.10) i w logu workera.
3. kolejka(): kolejne pozycje z listy rozwoju (katalog docs/PRZESZLOSC_ZRODLA_DANYCH.md, kolejność z planu 6 miesięcy i decyzji
   z 8.11.2026). Stan każdej pozycji wynika z faktów: jest kod, jest włączona flaga, są rekordy, jest zatwierdzona karta dostępu
   (scraper/access_gate: Prawnik ją przeszedł). Pierwsza niedziałająca pozycja to „następna”; raport mówi, na kogo czeka i od kiedy.

Bramki (czego automat NIGDY nie robi): nie włącza źródła (flaga zostaje w .env.production, ustawia ją właściciel), nie zatwierdza
karty dostępu, nie scala tożsamości osób, nie publikuje powiązań i nie wdraża kodu. Jedyne działanie poza raportem: gdy następna
pozycja ma zatwierdzoną kartę dostępu, nie ma kodu i nie dotyczy danych osób prywatnych, zakłada jeden bilet budowy w Sprincie
(status „proposed”), żeby budowa nie czekała, aż ktoś przypomni sobie o liście.
"""
from __future__ import annotations

import importlib.util
import logging
import os
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

WARSAW = ZoneInfo('Europe/Warsaw')
PARKED = 'odlozone:'
DOBA_KEY = 'przeszlosc-doba:'          # + data (RepairerState.key ma najwyżej 40 znaków)
SNAPSHOT_KEY = 'przeszlosc-doba:migawka'
QUEUE_KEY = 'przeszlosc-kolejka'
TICKET_PREFIX = '[przeszłość] Źródło: '
WARM_BEATS = ('przeszlosc-warm-hot', 'przeszlosc-warm-all', 'przeszlosc-topics')


def _flag(name, default):
    value = os.environ.get(name)
    if value is None or value.strip() == '':
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _int(name, default, low, high):
    try:
        return max(low, min(high, int(os.environ.get(name, default))))
    except (TypeError, ValueError):
        return default


def enabled():
    return _flag('PRZESZLOSC_SAMOROZWOJ_ENABLED', True)


# 1. Odkładanie trwale błędnych zadań --------------------------------------------------------------------------------------

def odblokuj(now=None, prog=None):
    """Odkłada zadania z prog+ błędami; zwraca {źródło: [(rodzaj, błąd), ...]}. Bez sieci, w transakcji z blokadą stanu."""
    from news.public_records_models import PublicCollectionState
    now = now or timezone.now()
    prog = prog or _int('PRZESZLOSC_ODLOZ_PO_BLEDACH', 10, 3, 100)
    parked = {}
    candidates = (PublicCollectionState.objects.filter(jobs__done=False, jobs__failures__gte=prog)
                  .exclude(status='blocked_access_review').distinct().values_list('pk', flat=True))
    for pk in candidates:
        with transaction.atomic():
            state = PublicCollectionState.objects.select_for_update().get(pk=pk)
            if state.status == 'blocked_access_review' or (state.lease_until and state.lease_until > now):
                continue  # bramka dostępu decyduje sama; trwający bieg nie traci zadań spod ręki
            jobs = list(state.jobs.filter(done=False, failures__gte=prog))
            for job in jobs:
                job.done = True
                job.last_error = (PARKED + (job.last_error or 'blad'))[:120]
                job.retry_at = None
                job.save(update_fields=['done', 'last_error', 'retry_at'])
            if jobs:
                parked[state.source] = [(j.kind, j.last_error[len(PARKED):]) for j in jobs]
                logger.warning('przeszlosc_samorozwoj: %s odłożone zadania: %d (%s)', state.source, len(jobs),
                               ', '.join(sorted({e for _, e in parked[state.source]}))[:200])
    return parked


# 3. Kolejka rozwoju (lista kolejnych źródeł) ------------------------------------------------------------------------------

@dataclass(frozen=True)
class Pozycja:
    key: str
    title: str
    katalog: int              # numer w tabeli docs/PRZESZLOSC_ZRODLA_DANYCH.md
    host: str                 # początek adresu oficjalnego punktu dostępu (do dopasowania karty dostępu)
    modul: str = ''           # moduł z kodem zbieracza; brak modułu = do zbudowania
    flaga: str = ''           # zmienna w .env.production, którą włącza właściciel
    domyslnie: bool = False
    rekordy: str = ''         # klucz w PublicRecord.source (puste: zbiór poza PublicRecord albo wyłącznie wzbogacenie)
    zewnetrzne: str = ''      # na co czekamy poza nami (urząd, licencja, rejestracja właściciela)
    wrazliwe: bool = False    # dane osób fizycznych spoza osób publicznych: bez biletu, zawsze decyzja właściciela


# Kolejność: miesiąc 1 (identyfikatory i NIP), 2 (nieruchomości), 3 (fundusze), 4 (orzeczenia i ryzyko), 5 (beneficjenci, sankcje).
KOLEJKA = (
    Pozycja('bzp', 'BZP / e-Zamówienia (UZP)', 2, 'https://ezamowienia.gov.pl/', 'scraper.bzp_backfill', 'BZP_API_ENABLED',
            rekordy='bzp', zewnetrzne='Prawnik: adapter używa mo-board/api/v1/Board/Search spoza regulaminu API UZP (Zarządzenie '
            '20/2022); udokumentowany jest BZP WebService mo-client-board/api/notices/ (ustalenie 15.11.2026).'),
    Pozycja('biala_lista', 'Biała lista VAT (MF)', 7, 'https://wykazpodatnikowvat.mf.gov.pl/', 'news.biala_lista_vat',
            'BIALA_LISTA_VAT_ENABLED', True, rekordy='biala_lista'),
    Pozycja('bir', 'REGON - GUS BIR1', 8, 'https://wyszukiwarkaregon.stat.gov.pl/', 'news.regon_bir', 'REGON_BIR_ENABLED',
            zewnetrzne='Klucz produkcyjny BIR na wniosek właściciela (regon_bir@stat.gov.pl).'),
    Pozycja('sudop', 'SUDOP - pomoc publiczna (UOKiK)', 6, 'https://sudop.uokik.gov.pl/', 'news.sudop', 'SUDOP_ENABLED'),
    Pozycja('ceidg', 'CEIDG (dane.biznes.gov.pl)', 41, 'https://dane.biznes.gov.pl/', 'news.ceidg', 'CEIDG_ENABLED',
            zewnetrzne='Token JWT z konta właściciela (Profil Zaufany).', wrazliwe=True),
    Pozycja('uldk', 'Działki - ULDK (GUGiK)', 14, 'https://uldk.gugik.gov.pl/', 'news.uldk', 'ULDK_ENABLED'),
    Pozycja('rcn', 'Rejestr Cen Nieruchomości (GUGiK)', 13, 'https://mapy.geoportal.gov.pl/', 'news.rcn', 'RCN_ENABLED'),
    Pozycja('fundusze', 'Beneficjenci funduszy 2021-2027 i KPO', 17, 'https://www.funduszeeuropejskie.gov.pl/',
            'news.fundusze_beneficjenci', 'FUNDUSZE_BENEFICJENCI_ENABLED'),
    Pozycja('ssp', 'Spółki Skarbu Państwa (wykaz)', 40, 'https://www.gov.pl/', 'news.spolki_skarbu', 'SPOLKI_SKARBU_ENABLED'),
    Pozycja('kio', 'Orzeczenia KIO', 23, 'https://orzeczenia.uzp.gov.pl/', 'news.kio', 'KIO_ENABLED'),
    Pozycja('orzeczenia', 'Portal Orzeczeń Sądów Powszechnych', 20, 'https://orzeczenia.ms.gov.pl/', 'news.orzeczenia',
            'ORZECZENIA_ENABLED'),
    Pozycja('krz', 'Krajowy Rejestr Zadłużonych (tylko podmioty)', 19, 'https://krz.ms.gov.pl/', 'news.krz', 'KRZ_ENABLED',
            zewnetrzne='Brak publicznego API (MS prowadzi analizy); bez scrapowania portalu.'),
    Pozycja('crbr', 'CRBR - beneficjenci rzeczywiści (MF)', 16, 'https://crbr.podatki.gov.pl/', 'news.crbr', 'CRBR_ENABLED',
            zewnetrzne='Od 1.01.2027 dostęp tylko z uzasadnionym interesem; wniosek na 2027.', wrazliwe=True),
    Pozycja('sankcje', 'Sankcje UE i lista MSWiA', 30, 'https://www.gov.pl/', 'news.sankcje', 'SANKCJE_ENABLED'),
)

STANY = {
    'dziala': 'działa',
    'puste': 'włączone, ale bez rekordów (zobacz błędy zbieraczy)',
    'do_wlaczenia': 'kod i karta dostępu gotowe; czeka na włączenie flagi przez właściciela',
    'czeka_na_prawnika': 'czeka na kartę dostępu (Prawnik, scraper/access_gate)',
    'czeka_na_zewnatrz': 'czeka na urząd, licencję lub rejestrację',
    'do_budowy': 'karta dostępu zatwierdzona, brak kodu: bilet budowy w Sprincie',
    'decyzja_wlasciciela': 'karta dostępu zatwierdzona, ale dane osób fizycznych: decyzja właściciela przed budową',
}
NA_KOGO = {'dziala': '', 'puste': 'zbieracz', 'do_wlaczenia': 'właściciel', 'czeka_na_prawnika': 'Prawnik',
           'czeka_na_zewnatrz': 'urząd lub właściciel', 'do_budowy': 'budowa (Codex/Claude), potem wdrożenie właściciela',
           'decyzja_wlasciciela': 'właściciel'}


def _karta(host):
    """Czy istnieje aktualna, zatwierdzona karta dostępu na punkt pod tym hostem (te same warunki co access_gate)."""
    from news.models import SourceAccessInstruction
    return SourceAccessInstruction.objects.filter(
        endpoint__startswith=host, status=SourceAccessInstruction.Status.APPROVED, minimum_interval_seconds__gte=3,
        daily_request_cap__gte=1, valid_until__gt=timezone.now(), reviewed_at__isnull=False,
    ).exclude(terms_url='').exclude(reviewed_by='').exclude(evidence={}).exists()


def _kod(modul):
    try:
        return bool(modul) and importlib.util.find_spec(modul) is not None
    except (ImportError, ValueError):
        return False


def stan_pozycji(p, rekordy=None):
    from news.public_records_models import PublicRecord
    kod, wlaczone, karta = _kod(p.modul), _flag(p.flaga, p.domyslnie) if p.flaga else False, _karta(p.host)
    if p.rekordy:
        liczba = rekordy.get(p.rekordy, 0) if rekordy is not None else PublicRecord.objects.filter(source=p.rekordy).count()
    else:
        liczba = None
    if kod and wlaczone:
        stan = 'puste' if liczba == 0 else 'dziala'
    elif kod and karta:
        stan = 'do_wlaczenia'
    elif kod:
        stan = 'czeka_na_zewnatrz' if p.zewnetrzne else 'czeka_na_prawnika'
    elif karta:
        stan = 'decyzja_wlasciciela' if p.wrazliwe else 'do_budowy'
    else:
        stan = 'czeka_na_zewnatrz' if p.zewnetrzne else 'czeka_na_prawnika'
    return {'key': p.key, 'title': p.title, 'katalog': p.katalog, 'stan': stan, 'opis': STANY[stan], 'na_kogo': NA_KOGO[stan],
            'kod': kod, 'wlaczone': wlaczone, 'karta': karta, 'rekordy': liczba, 'zewnetrzne': p.zewnetrzne,
            'flaga': p.flaga, 'wrazliwe': p.wrazliwe}


def kolejka(now=None, zapisz=False):
    """Stan wszystkich pozycji z datą wejścia w obecny stan; „następna” to pierwsza niedziałająca."""
    from news.models import RepairerState
    from news.public_records_models import PublicRecord
    now = now or timezone.now()
    rekordy = dict(PublicRecord.objects.values_list('source').annotate(n=Count('pk')).values_list('source', 'n'))
    rows = [stan_pozycji(p, rekordy) for p in KOLEJKA]
    row = RepairerState.objects.filter(key=QUEUE_KEY).first()
    seen = dict(((row.data if row else None) or {}).get('pozycje') or {})
    for r in rows:
        prev = seen.get(r['key']) or {}
        r['od'] = prev['od'] if prev.get('stan') == r['stan'] and prev.get('od') else now.isoformat()
    if zapisz:
        RepairerState.objects.update_or_create(key=QUEUE_KEY, defaults={'data': {
            'pozycje': {r['key']: {'stan': r['stan'], 'od': r['od']} for r in rows}, 'at': now.isoformat()}})
    nastepna = next((r for r in rows if r['stan'] != 'dziala'), None)
    return {'pozycje': rows, 'nastepna': nastepna}


def zglos_budowe(nastepna):
    """Jedyne działanie kolejki: bilet budowy dla następnej pozycji po bramce Prawnika (karta zatwierdzona, brak kodu, bez danych
    osób prywatnych). Jeden bilet na pozycję; drugi tylko gdy poprzedni odrzucono. Zwraca numer biletu albo None."""
    from news.agent_models import BuildTicket
    if not nastepna or nastepna['stan'] != 'do_budowy' or not _flag('PRZESZLOSC_KOLEJKA_BILETY', True):
        return None
    title = TICKET_PREFIX + nastepna['title']
    if BuildTicket.objects.filter(title=title).exclude(status='dropped').exists():
        return None
    p = next(p for p in KOLEJKA if p.key == nastepna['key'])
    brief = (f"Zbuduj zbieracz źródła „{p.title}” (katalog poz. {p.katalog}, docs/PRZESZLOSC_ZRODLA_DANYCH.md) w module {p.modul}. "
             f"Karta dostępu dla {p.host} jest zatwierdzona: każde zapytanie przez scraper/access_gate.require_approved_instruction, "
             "odstęp i dzienny limit z karty, reakcja na 429/Retry-After, bez obchodzenia blokad. Łączenie tylko po identyfikatorach "
             "(NIP, KRS, REGON), nigdy po nazwie; osoby prywatne jako anonimowy węzeł, PESEL nigdy. "
             f"Flaga {p.flaga} domyślnie wyłączona (włącza właściciel). Wiersz w news/przeszlosc_stan.py (Stan danych). "
             "Testy na fikcyjnych odpowiedziach, bez sieci. Wdrożenie robi właściciel.")
    ticket = BuildTicket.objects.create(
        title=title, brief=brief, effort='M', executor='codex', status='proposed', rank=50,
        acceptance=['zbieracz przechodzi przez access_gate i respektuje limity karty', 'testy bez sieci przechodzą',
                    f'flaga {p.flaga} domyślnie wyłączona', 'wiersz w Stanie danych z opisem braków'])
    logger.info('przeszlosc_samorozwoj: bilet budowy #%s dla %s', ticket.pk, p.key)
    return ticket.pk


# 2. Raport doby -----------------------------------------------------------------------------------------------------------

def _liczniki():
    """Liczby rekordów per źródło (PublicRecord) i per zbiór (Stan danych), do różnicy dzień do dnia."""
    from news import przeszlosc_stan
    from news.public_records_models import PublicRecord
    counts = {'zrodlo:' + s: n for s, n in PublicRecord.objects.values_list('source').annotate(n=Count('pk'))
              .values_list('source', 'n')}
    for row in przeszlosc_stan.datasets():
        counts['zbior:' + row['key']] = row['records']
    return counts


def _bledy_zadan():
    """Oczekujące zadania z błędami: źródło -> (liczba, najczęstszy błąd)."""
    from news.public_records_models import PublicCollectionJob
    out = {}
    rows = (PublicCollectionJob.objects.filter(done=False, failures__gt=0)
            .values_list('state__source', 'last_error'))
    by_source = {}
    for source, error in rows:
        by_source.setdefault(source, Counter())[error or 'blad'] += 1
    for source, errors in by_source.items():
        out[source] = (sum(errors.values()), errors.most_common(1)[0][0])
    return out


def _rozgrzewanie():
    from news.raport_petli import pulse
    out = {}
    for beat in WARM_BEATS:
        p = pulse(beat)
        out[beat] = {'ostatni_sukces': p.get('last_success') or '', 'wynik': p.get('result') or p.get('phase') or '',
                     'blad': (p.get('last_error') or '')[:120]}
    return out


def doba(now=None, parked=None, queue=None, zapisz=False):
    """Raport doby: nowe rekordy (różnica z migawką sprzed doby), pobrane lub odświeżone w 24 h, problemy, odłożone, kolejka."""
    from news import przeszlosc_stan
    from news.models import RepairerState
    from news.public_records_models import PublicRecord
    now = now or timezone.now()
    counts = _liczniki()
    snap = RepairerState.objects.filter(key=SNAPSHOT_KEY).first()
    before = (snap.data or {}).get('liczniki') if snap else None
    nowe = {k: n - before.get(k, 0) for k, n in counts.items() if before is not None and n != before.get(k, 0)}
    odswiezone = dict(PublicRecord.objects.filter(fetched_at__gte=now - timedelta(hours=24)).values_list('source')
                      .annotate(n=Count('pk')).values_list('source', 'n'))
    stan = przeszlosc_stan.sources() + przeszlosc_stan.datasets()
    problemy = [{'key': r['key'], 'title': r['title'], 'status': r['status'], 'last_fetch': r['last_fetch'],
                 'last_error': r['last_error']} for r in stan if r['status'] in ('stale', 'empty')]
    try:
        krs = przeszlosc_stan.krs_summary()
    except Exception:  # noqa: BLE001 - raport wychodzi także bez pokrycia KRS
        krs = {}
    queue = queue or kolejka(now)
    data = {'at': now.isoformat(), 'dzien': now.astimezone(WARSAW).date().isoformat(), 'pierwszy_raport': before is None,
            'nowe': nowe, 'odswiezone_24h': odswiezone, 'problemy': problemy, 'bledy_zadan': _bledy_zadan(),
            'odlozone': {s: len(v) for s, v in (parked or {}).items()},
            'odlozone_bledy': {s: sorted({e for _, e in v})[:3] for s, v in (parked or {}).items()},
            'rozgrzewanie': _rozgrzewanie(), 'krs': {k: krs.get(k) for k in ('people_total', 'people_checked', 'entities_total',
                                                                              'entities_with_nip', 'queue') if k in krs},
            'kolejka': queue, 'liczniki': counts}
    if zapisz:
        RepairerState.objects.update_or_create(key=DOBA_KEY + data['dzien'], defaults={'data': data})
        RepairerState.objects.update_or_create(key=SNAPSHOT_KEY, defaults={'data': {'liczniki': counts, 'at': data['at']}})
    return data


def report_lines(now=None):
    """Sekcja porannego Raportu pętli: zapisany raport dnia (zadanie 6:35), a gdy go nie ma, odczyt na żywo bez zapisu."""
    from news.models import RepairerState
    now = now or timezone.now()
    row = RepairerState.objects.filter(key=DOBA_KEY + now.astimezone(WARSAW).date().isoformat()).first()
    data = row.data if row else doba(now)
    return lines(data, saved=bool(row))


def lines(data, saved=True):
    out = [] if saved else ['(zadanie przeszlosc-doba jeszcze dziś nie ruszyło; odczyt na żywo)']
    nowe = data.get('nowe') or {}
    if data.get('pierwszy_raport'):
        out.append('Doszło: pierwsza migawka, różnice od jutra.')
    else:
        rosly = sorted(((k.split(':', 1)[1], n) for k, n in nowe.items() if n > 0), key=lambda x: -x[1])
        out.append('Doszło w dobie: ' + (', '.join(f'{k} +{n}' for k, n in rosly[:15]) if rosly else 'nic nowego.'))
        spadly = [(k.split(':', 1)[1], n) for k, n in nowe.items() if n < 0]
        if spadly:
            out.append('Ubyło (sprawdzić): ' + ', '.join(f'{k} {n}' for k, n in spadly))
    odsw = data.get('odswiezone_24h') or {}
    if odsw:
        out.append('Pobrane lub odświeżone w 24 h: ' + ', '.join(f'{k} {n}' for k, n in sorted(odsw.items(), key=lambda x: -x[1])[:15]))
    problemy = data.get('problemy') or []
    bledy = data.get('bledy_zadan') or {}
    if problemy or bledy:
        out.append('Nie udało się:')
        for p in problemy:
            label = 'zaległe' if p['status'] == 'stale' else 'puste'
            err = f", błąd: {p['last_error']}" if p.get('last_error') else ''
            out.append(f"- {p['key']} ({label}, ostatnie pobranie {p.get('last_fetch') or 'nigdy'}{err})")
        for source, (n, err) in sorted(bledy.items()):
            out.append(f'- {source}: {n} zadań z błędem, najczęściej {err}')
    else:
        out.append('Nie udało się: nic, wszystkie włączone źródła w terminie.')
    for source, n in (data.get('odlozone') or {}).items():
        errs = ', '.join(data.get('odlozone_bledy', {}).get(source) or [])
        out.append(f'Odłożone automatycznie (trwały błąd, źródło odblokowane, nowy cykl zacznie od nowa): {source} {n} ({errs})')
    for beat, w in (data.get('rozgrzewanie') or {}).items():
        if w.get('blad') or not w.get('ostatni_sukces'):
            out.append(f"Rozgrzewanie {beat}: {w.get('wynik') or 'brak biegu'}{', ' + w['blad'] if w.get('blad') else ''}")
    krs = data.get('krs') or {}
    if krs:
        out.append(f"KRS: osoby sprawdzone {krs.get('people_checked')}/{krs.get('people_total')}, podmioty {krs.get('entities_total')} "
                   f"(z NIP {krs.get('entities_with_nip')}), kolejka {krs.get('queue')}")
    q = data.get('kolejka') or {}
    nxt = q.get('nastepna')
    if nxt:
        od = (nxt.get('od') or '')[:10]
        out.append(f"Następna pozycja z listy rozwoju: {nxt['title']} (katalog {nxt['katalog']}): {nxt['opis']}; "
                   f"czeka na: {nxt['na_kogo']}; w tym stanie od {od}.")
        if nxt.get('zewnetrzne'):
            out.append(f"  {nxt['zewnetrzne']}")
        if nxt['stan'] == 'do_wlaczenia':
            out.append(f"  Włączenie: {nxt['flaga']}=true w .env.production i przebudowa worker/beat.")
    dzialaja = sum(1 for r in q.get('pozycje') or [] if r['stan'] == 'dziala')
    if q.get('pozycje'):
        out.append(f"Lista rozwoju: działa {dzialaja} z {len(q['pozycje'])} pozycji (python manage.py przeszlosc_doba --kolejka).")
    return out


def run(now=None):
    """Zadanie dnia: odłóż trwale błędne zadania, policz dobę, zaktualizuj kolejkę i (po bramce) załóż bilet budowy."""
    now = now or timezone.now()
    if not enabled():
        return {'status': 'disabled'}
    parked = odblokuj(now)
    queue = kolejka(now, zapisz=True)
    ticket = zglos_budowe(queue['nastepna'])
    data = doba(now, parked=parked, queue=queue, zapisz=True)
    for line in lines(data):
        logger.info('przeszlosc_doba: %s', line)
    return {'status': 'ok', 'produced': 1, 'odlozone': sum(len(v) for v in parked.values()),
            'problemy': len(data['problemy']), 'nowe': sum(n for n in data['nowe'].values() if n > 0),
            'nastepna': (queue['nastepna'] or {}).get('key', ''), 'bilet': ticket}
