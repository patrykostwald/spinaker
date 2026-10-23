"""Korektor - ostry recenzent faktów o osobach i urzędach (właściciel 23.10.2026).

Trzy wpadki, które nie mogą się powtórzyć: „prezydent Andrzej Duda” po 6.08.2025 (model z wiedzą sprzed zmiany),
osoba publiczna bez przypiętego konta X, puste sekcje profili przeszłości. Korektor:
- sprawdza treści z ostatnich N dni (wywiad dnia, diagnozy, przekazy dnia) z rejestrem urzędów (news/urzedy.py);
- liczy osoby bez konta X z listy zweryfikowanej (news/data/osoby_x.csv z gałęzi osoby-x, jeśli jest) i puste sekcje profili;
- `--napraw` robi tylko bezpieczne rzeczy: poprawia metadane (gość wywiadu), wstrzymuje i zleca ponowne wygenerowanie treści
  z błędem urzędu (treści nie edytuje), przypina konta X z listy zweryfikowanej; reszta idzie do raportu dla koordynatora.
Bramka (bramka_*): ta sama kontrola przed automatyczną publikacją. Bez AI.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path

from django.utils import timezone

from news import urzedy

logger = logging.getLogger(__name__)

PREFIX = 'korektor_urzad'
RETRIES = 1                 # ile razy zlecamy ponowne wygenerowanie, zanim treść czeka na człowieka
LIST_MAX = 40
OSOBY_X = Path(__file__).resolve().parent / 'data' / 'osoby_x.csv'
SECTIONS = ('krs', 'oswiadczenia', 'glosowania', 'zamowienia')


# --- reguły tekstu ----------------------------------------------------------------------------

def _alt(words) -> str:
    return '|'.join(re.escape(word) for word in sorted(set(words), key=len, reverse=True))


def _person_re(osoba: str) -> str:
    return _alt(urzedy.formy(osoba))


def _pattern(slowa, osoba: str) -> re.Pattern:
    """„prezydent [RP] [Andrzej] Duda” albo „Andrzej Duda, prezydent” / „Andrzej Duda (Prezydent RP)”.
    Słowa urzędu i nazwiska bez względu na wielkość liter; wtrącone imię musi być z wielkiej."""
    office, person = _alt(slowa), _person_re(osoba)
    middle = r'(?:(?i:rp|rzeczypospolitej polskiej)\s+)?(?:[A-ZŁŚŻŹĆÓ][\w-]+\s+)?'
    return re.compile(rf'(?<!\w)(?i:(?P<urzad>{office}))\s+{middle}(?i:(?P<osoba>{person}))(?!\w)'
                      rf'|(?<!\w)(?i:(?P<osoba2>{person}))\s*(?:,|\(|-|–)\s*(?i:(?P<urzad2>{office}))(?!\w)')


def _znani() -> list[str]:
    """Osoby z rejestru, które umiemy odmieniać - tylko one mogą być „zamienione” w regule urzędu."""
    return list(urzedy.ODMIANA)


def _byly_przed(text: str, start: int) -> bool:
    return bool(urzedy.BYLY_PRZED.search(text[max(0, start - 30):start]))


def bledy_urzedu(text: str, day: date | None = None) -> list[dict]:
    """Błędy „urząd + niewłaściwa osoba” w tekście z dnia `day`.

    Dla urzędów pewnych i jednoosobowych: osoba odmieniana w rejestrze, ale nie obecny urzędnik, podpisana tym urzędem
    (bez „były/ówczesny” przed). Dla byłych urzędników liczy się data: tekst sprzed końca kadencji jest poprawny."""
    if not text:
        return []
    day = day or timezone.localdate()
    found, seen = [], set()
    for office in urzedy.pewne():
        if not office.slowa or not office.jedyny:
            continue
        holder = office.osoba
        formers = {row.osoba: row for row in urzedy.byli(office.klucz)}
        for osoba in _znani():
            if osoba == holder:
                continue
            former = formers.get(osoba)
            if former and day < former.do:
                continue  # tekst z czasu, gdy pełnił urząd
            if office.od and day < office.od and not former:
                continue
            for match in _pattern(office.slowa, osoba).finditer(text):
                start = match.start('urzad') if match.group('urzad') else match.start('urzad2')
                if _byly_przed(text, start):
                    continue
                key = (office.klucz, osoba)
                if key in seen:
                    continue
                seen.add(key)
                found.append({'rodzaj': 'urzad', 'urzad': office.urzad, 'napisano': osoba, 'powinno': holder,
                              'byly': bool(former), 'fragment': text[max(0, match.start() - 40):match.end() + 40].strip(),
                              'zrodlo': office.zrodlo})
    return found


def _text(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False) if value else ''


def opis(bledy: list[dict]) -> str:
    return '; '.join(f"{b['urzad']}: napisano {b['napisano']}, powinno {b['powinno']}" if b['rodzaj'] == 'urzad'
                     else f"gość: {b.get('napisano')} - {b.get('powod', '')}" for b in bledy)[:200]


# --- wywiad dnia ------------------------------------------------------------------------------

def _mentions(text: str) -> list[str]:
    lowered = (text or '').casefold()
    out = []
    for osoba in _znani():
        if re.search(rf'(?<!\w)(?:{_person_re(osoba)})(?!\w)', lowered):
            out.append(osoba)
    return out


def _same(a: str, b: str) -> bool:
    surname = lambda name: (name or '').strip().split()[-1].casefold() if (name or '').strip() else ''  # noqa: E731
    return bool(surname(a)) and surname(a) == surname(b)


def gosc_z_tytulu(interview) -> str | None:
    """Gość z tytułu filmu (i opisu kanału, gdy tytuł milczy): dokładnie jedna osoba z rejestru."""
    names = _mentions(interview.title)
    return names[0] if len(names) == 1 else None


def bledy_goscia(interview) -> list[dict]:
    """Metadane gościa: zgodność z tytułem filmu i z urzędem (np. rola „Prezydent RP” przy Andrzeju Dudzie)."""
    out = []
    day = interview.day or timezone.localdate()
    for row in bledy_urzedu(f'{interview.guest_role} {interview.guest_name}', day):
        out.append({**row, 'rodzaj': 'gosc', 'pole': 'guest', 'powod': f"rola „{interview.guest_role}” należy do: {row['powinno']}"})
    expected = gosc_z_tytulu(interview)
    if expected and interview.guest_name and not _same(expected, interview.guest_name) \
            and not any(_same(expected, name) for name in interview.guest_name.split(',')):
        out.append({'rodzaj': 'gosc', 'pole': 'guest_name', 'napisano': interview.guest_name, 'powinno': expected,
                    'powod': f'tytuł filmu wskazuje: {expected}', 'urzad': ''})
    # Ta sama osoba różnie podpisana na jednej stronie: nagłówek o kimś innym niż podpis gościa.
    in_headline = _mentions(interview.headline)
    if interview.guest_name and in_headline and not any(_same(name, interview.guest_name) for name in in_headline) \
            and any(_same(name, expected or '') for name in in_headline):
        out.append({'rodzaj': 'gosc', 'pole': 'headline', 'napisano': interview.guest_name, 'powinno': in_headline[0],
                    'powod': 'nagłówek raportu i podpis gościa wskazują różne osoby', 'urzad': ''})
    return out


def popraw_goscia(interview, *, save: bool = True) -> list[str]:
    """Bezpieczna poprawka metadanych (treści nie dotyka): gość według tytułu filmu, funkcja według rejestru.
    Bez wskazania w tytule nie zmieniamy nazwiska - tylko usuwamy funkcję przypisaną komuś innemu."""
    changed = []
    bledy = bledy_goscia(interview)
    if not bledy:
        return changed
    day = interview.day or timezone.localdate()
    target = gosc_z_tytulu(interview)
    if target and not _same(target, interview.guest_name):
        interview.guest_name = target[:200]
        changed.append('guest_name')
    name = interview.guest_name
    role = urzedy.obecna_funkcja(name)
    if role and interview.guest_role != role[0][:60]:
        interview.guest_role = role[0][:60]
        changed.append('guest_role')
    elif not role and bledy_urzedu(f'{interview.guest_role} {name}', day):
        interview.guest_role = ''
        changed.append('guest_role')
    if changed and save and interview.pk:
        interview.save(update_fields=changed)
    return changed


def teksty_wywiadu(interview) -> str:
    guest, host = interview.guest_analysis or {}, interview.host_analysis or {}
    return '\n'.join([interview.headline, interview.summary, interview.overall, _text(guest.get('summary')),
                      _text(host.get('summary')), _text(guest.get('claims')), _text(guest.get('techniques')),
                      _text(host.get('notes')), interview.limitations])


def bledy_wywiadu(interview) -> list[dict]:
    return bledy_goscia(interview) + bledy_urzedu(teksty_wywiadu(interview), interview.day or timezone.localdate())


def bramka_wywiadu(interview) -> list[dict]:
    """Przed publikacją: najpierw poprawia metadane gościa, potem zwraca błędy, które zostały (w treści)."""
    popraw_goscia(interview, save=False)
    return [b for b in bledy_wywiadu(interview) if b['rodzaj'] == 'urzad']


# --- diagnozy i przekazy ----------------------------------------------------------------------

def teksty_diagnozy(row) -> str:
    return '\n'.join([row.headline, row.summary, row.analysis, _text(row.plain), _text(row.x_thread),
                      _text(row.claims), _text(row.techniques), row.limitations])


def bledy_diagnozy(row) -> list[dict]:
    day = timezone.localdate(row.post.published_at) if row.post.published_at else timezone.localdate()
    return bledy_urzedu(teksty_diagnozy(row), day)


def bramka_diagnozy(row) -> list[dict]:
    """Wołane w clinic.diagnose po zapisaniu wyniku w polach, przed zapisem w bazie."""
    bledy = bledy_diagnozy(row)
    if not bledy:
        return []
    row.usage = {key: value for key, value in (row.usage or {}).items() if key not in ('snapshot', 'snapshot_at')}
    row.usage['korektor'] = bledy[:5]
    row.reviewed_at = None
    if row.repair_attempts < RETRIES:
        row.repair_attempts += 1
        row.status = 'queued'  # wraca do kolejki - nowa diagnoza z blokiem urzędów w promptcie
    else:
        row.status = 'pending_review'  # czeka na decyzję człowieka (zatwierdź / odrzuć)
    row.error = f'{PREFIX}: {opis(bledy)}'[:240]
    return bledy


def teksty_przekazu(result: dict) -> str:
    return '\n'.join([result.get('message', ''), result.get('analysis', ''), result.get('thesis', ''),
                      _text(result.get('points')), _text(result.get('themes'))])


def bledy_przekazu(result: dict, day: date) -> list[dict]:
    return bledy_urzedu(teksty_przekazu(result), day)


# --- konta X i profile ------------------------------------------------------------------------

def _col(row: dict, *names) -> str:
    lowered = {(key or '').strip().casefold(): (value or '').strip() for key, value in row.items()}
    return next((lowered[name] for name in names if lowered.get(name)), '')


def lista_x(path: Path | None = None) -> list[dict]:
    """Zweryfikowana lista kont X (gałąź osoby-x). Brak pliku - pusta lista. Tylko wysoka pewność."""
    path = path or OSOBY_X
    if not path.exists():
        return []
    rows = []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            handle_x = _col(row, 'konto', 'handle', 'konto_x', 'x_handle', 'proposed_x_handle').lstrip('@')
            pewnosc = _col(row, 'pewnosc', 'pewność', 'confidence', 'verification_status').casefold()
            if not handle_x or pewnosc in ('niska', 'low', 'dp', '[dp]', 'niepewne'):
                continue
            rows.append({'osoba': _col(row, 'imie_nazwisko', 'imię i nazwisko', 'nazwa', 'name', 'public_figure_name'),
                         'id': _col(row, 'id', 'osoba_id', 'figure_id', 'identyfikator', 'public_figure_id'),
                         'konto': handle_x, 'zrodlo': _col(row, 'zrodlo', 'źródło', 'source', 'official_evidence_url')})
    return rows


def braki_x(path: Path | None = None) -> dict:
    path = path or OSOBY_X
    from news.political_models import PublicFigure
    from news.przeszlosc_osoba import x_accounts
    rows = lista_x(path)
    if not rows:
        return {'lista': str(path.name), 'dostepna': path.exists(), 'braki': [], 'sprawdzone': 0}
    ids = {row['id'] for row in rows if row['id'].isdigit()}
    figures = {str(f.pk): f for f in PublicFigure.objects.filter(pk__in=ids, archived=False)}
    braki = []
    for row in rows:
        figure = figures.get(row['id'])
        if figure is None:
            continue
        handles = {account.handle.casefold() for account, _ in x_accounts(figure)}
        if row['konto'].casefold() not in handles:
            braki.append({'osoba': figure.canonical_name, 'id': figure.pk, 'konto': row['konto'], 'zrodlo': row['zrodlo']})
    return {'lista': path.name, 'dostepna': True, 'braki': braki, 'sprawdzone': len(rows)}


def przypnij_x(path: Path | None = None) -> dict:
    """Przypina konta z listy zweryfikowanej istniejącą komendą importu (ta sama walidacja dowodów, idempotentnie)."""
    path = path or OSOBY_X
    from io import StringIO
    from django.core.management import call_command
    from django.core.management.base import CommandError
    if not path.exists():
        return {'status': 'brak_listy'}
    out = StringIO()
    try:
        call_command('import_public_figure_x_csv', str(path), apply=True, stdout=out)
    except (CommandError, TypeError) as error:
        return {'status': 'odrzucone', 'powod': str(error)[:300]}
    return {'status': 'ok', 'wynik': out.getvalue()[-500:]}


def puste_profile(limit: int | None = None) -> dict:
    """Profile przeszłości (osoby obecne) z pustymi sekcjami: KRS, oświadczenia, głosowania (tylko posłowie), zamówienia."""
    from news.clinic_models import AssetDeclaration
    from news.political_models import PublicFigure, PublicFigureOrganisationRelation
    from news.przeszlosc_osoba import _ballots, mp_identities
    from news.drzewo_pieniedzy import person_companies
    figures = PublicFigure.objects.filter(archived=False, status='current', merged_into__isnull=True).order_by('canonical_name')
    if limit:
        figures = figures[:limit]
    krs = set(PublicFigureOrganisationRelation.objects.filter(verification_status='confirmed')
              .values_list('public_figure_id', flat=True))
    declarations = set(AssetDeclaration.objects.exclude(figure__isnull=True).values_list('figure_id', flat=True))
    declared_mps = set(AssetDeclaration.objects.values_list('mp_id', flat=True))
    out = {name: [] for name in SECTIONS}
    total = 0
    for figure in figures:
        total += 1
        row = {'id': figure.pk, 'osoba': figure.canonical_name, 'funkcja': figure.role_title}
        if figure.pk not in krs:
            out['krs'].append(row)
        identities = mp_identities(figure)
        if figure.pk not in declarations and not any(mp_id in declared_mps for _, mp_id in identities):
            out['oswiadczenia'].append(row)
        if identities and not _ballots(identities).exists():
            out['glosowania'].append(row)
        if figure.pk in krs and not any(company['contracts']['count'] for company in person_companies(figure)):
            out['zamowienia'].append(row)
    return {'osoby': total, 'liczby': {name: len(rows) for name, rows in out.items()}, 'listy': out}


# --- kolejka „Do decyzji” Strażnika kont (dopisek OSOBY_X 23.10) ---------------------------------

PARTY_WORDS = ('platforma', 'lewica', 'pis', 'prawo i sprawiedliwość', 'konfederacja', 'korona', 'psl', 'polska 2050',
               'razem', 'koalicja', 'klub', 'partia', 'stronnictwo', 'ruch narodowy', 'nowa nadzieja', 'centrum')


def _party_account(handle: str, name: str) -> bool:
    from scraper.catalog import TWITTER_POLITICIANS
    known = {h.casefold() for h, row in TWITTER_POLITICIANS.items() if len(row.get('name', '').split()) < 2
             or any(word in row['name'].casefold() for word in PARTY_WORDS)}
    text = f'{handle} {name}'.casefold().replace('_', ' ')
    return handle.casefold() in known or any(re.search(rf'(?<!\w){re.escape(word)}(?!\w)', text) for word in PARTY_WORDS)


def _name_fits(person: str, handle: str, name: str) -> bool:
    parts = [part.casefold() for part in re.split(r'[\s-]+', person or '') if len(part) >= 3]
    text = f'{handle} {name}'.casefold()
    return bool(parts) and parts[-1][:5] in text


def do_decyzji() -> dict:
    """Nierozstrzygnięte kandydatury kont X: ile czeka i od kiedy, a do człowieka tylko prawdziwy konflikt dowodów -
    z gotową propozycją. Bez zmian w danych (rozstrzyga Drugi klucz i gałąź osoby-x)."""
    from collections import Counter
    from news.political_models import PoliticalAccountCandidate, PublicFigure
    rows = list(PoliticalAccountCandidate.objects.filter(resolved_account__isnull=True).order_by('created_at'))
    reasons, konflikty = Counter(), []
    for row in rows:
        reason = (row.resolution_error or 'bez powodu').removeprefix('Strażnik: ')[:80]
        reasons[reason] += 1
        if 'innym profilem' not in reason and 'odrzucony wcześniej' not in reason:
            continue
        people = [ev.subject for ev in row.social_evidence.all() if isinstance(getattr(ev, 'subject', None), PublicFigure)]
        names = sorted({p.canonical_name for p in people})
        if _party_account(row.handle, row.display_name):
            proposal = 'odrzucić jako konto osoby: to konto partii lub klubu'
        else:
            fits = [name for name in names if _name_fits(name, row.handle, row.display_name)]
            proposal = (f'przypiąć tylko do: {fits[0]} (nazwa konta pasuje), pozostałe dowody odrzucić' if len(fits) == 1
                        else 'do weryfikacji: nazwa konta nie rozstrzyga')
        konflikty.append({'konto': row.handle, 'nazwa': row.display_name, 'osoby': names, 'od': row.created_at.date().isoformat(),
                          'powod': reason, 'propozycja': proposal})
    konflikty += konflikty_straznika({row['konto'].casefold() for row in konflikty})
    return {'czeka': len(rows), 'najstarsza': rows[0].created_at.date().isoformat() if rows else None,
            'powody': dict(reasons.most_common(10)), 'konflikty': konflikty}


def konflikty_straznika(znane: set[str] = frozenset()) -> list[dict]:
    """Konflikty dowodów z ostatniej nocy Strażnika kont (account_warden.conflicts_for_report) w formacie kolejki;
    konto już opisane z kandydatury nie powtarza się."""
    from news.account_warden import conflicts_for_report
    out = []
    for row in conflicts_for_report():
        handle = (row.get('handle') or '').lstrip('@')
        if not handle or handle.casefold() in znane:
            continue
        znane = {*znane, handle.casefold()}
        out.append({'konto': handle, 'nazwa': '', 'osoby': [row['name']] if row.get('name') else [], 'od': None,
                    'powod': (row.get('reason') or '')[:120], 'propozycja': row.get('proposal') or 'do weryfikacji',
                    'zrodlo': row.get('source') or '', 'straznik': True})
    return out


# --- przebieg ---------------------------------------------------------------------------------

def _since(dni: int):
    return timezone.now() - timedelta(days=dni)


def skanuj(dni: int = 2) -> dict:
    from news.clinic_models import ClinicDailyMessage, ClinicInterview, SpinDiagnosis
    since = _since(dni)
    wywiady, diagnozy, przekazy = [], [], []
    for row in ClinicInterview.objects.filter(day__gte=since.date()).exclude(status__in=['failed', 'not_applicable']):
        bledy = bledy_wywiadu(row)
        if bledy:
            wywiady.append({'id': row.pk, 'obj': row, 'status': row.status, 'tytul': row.title, 'bledy': bledy})
    for row in (SpinDiagnosis.objects.filter(status__in=['approved', 'pending_review'], diagnosed_at__gte=since)
                .select_related('post__account')):
        bledy = bledy_diagnozy(row)
        if bledy:
            diagnozy.append({'id': row.pk, 'obj': row, 'status': row.status, 'tytul': row.headline, 'bledy': bledy})
    for row in ClinicDailyMessage.objects.filter(day__gte=since.date(), status__in=['approved', 'pending_review']):
        bledy = bledy_przekazu({'message': row.message, 'analysis': row.analysis, 'thesis': row.thesis,
                                'points': row.points, 'themes': row.themes}, row.day)
        if bledy:
            przekazy.append({'id': row.pk, 'obj': row, 'status': row.status, 'tytul': f'{row.day} {row.camp}', 'bledy': bledy})
    return {'wywiady': wywiady, 'diagnozy': diagnozy, 'przekazy': przekazy}


def _napraw_wywiad(item: dict) -> str:
    from news import clinic_ai, clinic_interview
    row = item['obj']
    poprawki = popraw_goscia(row)
    tresc = [b for b in bledy_urzedu(teksty_wywiadu(row), row.day or timezone.localdate())]
    if not tresc:
        return f"poprawiono metadane: {', '.join(poprawki)}" if poprawki else 'bez zmian'
    if row.repair_attempts >= RETRIES or not row.transcript:
        row.status, row.error = 'flagged', f'{PREFIX}: {opis(tresc)}'[:240]
        row.save(update_fields=['status', 'error'])
        return 'wstrzymany, czeka na decyzję (limit ponowień)'
    row.repair_attempts += 1
    row.save(update_fields=['repair_attempts', *poprawki])
    try:
        clinic_interview.rediagnose(row)  # bramka w rediagnose sprawdza wynik jeszcze raz
    except clinic_ai.ClinicAIError as error:
        row.status, row.error = 'flagged', f'{PREFIX}: ponowna diagnoza nieudana {error.code}'[:240]
        row.save(update_fields=['status', 'error'])
        return f'wstrzymany: {error.code}'
    return f'ponowna diagnoza: {row.status}'


def _napraw_diagnoze(item: dict) -> str:
    row = item['obj']
    if row.repair_attempts >= RETRIES:
        row.status, row.error = 'pending_review', f'{PREFIX}: {opis(item["bledy"])}'[:240]
        row.save(update_fields=['status', 'error'])
        return 'wstrzymana, czeka na decyzję (limit ponowień)'
    row.repair_attempts += 1
    row.status, row.error, row.reviewed_at = 'queued', f'{PREFIX}: {opis(item["bledy"])}'[:240], None
    row.usage = {key: value for key, value in (row.usage or {}).items() if key not in ('snapshot', 'snapshot_at')}
    row.save(update_fields=['status', 'error', 'reviewed_at', 'repair_attempts', 'usage'])
    return 'wycofana z publikacji, w kolejce do ponownej diagnozy'


def _napraw_przekaz(item: dict) -> str:
    from news import clinic
    row = item['obj']
    if row.reviewed_by_id:
        return 'zatwierdzony ręcznie - tylko w raporcie'
    day, camp = row.day, row.camp
    row.status, row.error = 'failed', f'{PREFIX}: {opis(item["bledy"])}'[:300]
    row.save(update_fields=['status', 'error'])
    try:
        clinic.run_daily_messages(day, camps=(camp,), only_missing=True)
    except Exception as error:  # noqa: BLE001 - naprawa jednego przekazu nie przerywa raportu
        return f'wstrzymany, ponowne wygenerowanie nieudane: {error}'[:200]
    row.refresh_from_db()
    return f'wygenerowany ponownie: {row.status}'


def run(dni: int = 2, napraw: bool = False, profile_limit: int | None = None) -> dict:
    found = skanuj(dni)
    akcje = []
    if napraw:
        for kind, fix in (('wywiady', _napraw_wywiad), ('diagnozy', _napraw_diagnoze), ('przekazy', _napraw_przekaz)):
            for item in found[kind]:
                try:
                    item['akcja'] = fix(item)
                except Exception as error:  # noqa: BLE001 - jedna treść nie zatrzymuje reszty
                    logger.exception('korektor: naprawa %s %s', kind, item['id'])
                    item['akcja'] = f'błąd naprawy: {error}'[:200]
                akcje.append(f"{kind} #{item['id']}: {item['akcja']}")
    x = braki_x()
    if napraw and x['braki']:
        x['przypiecie'] = przypnij_x()
        x = {**braki_x(), 'przypiecie': x['przypiecie']}
    profiles = puste_profile(profile_limit)
    kolejka = do_decyzji()
    for kind in ('wywiady', 'diagnozy', 'przekazy'):
        for item in found[kind]:
            item.pop('obj', None)
    return {'dzien': timezone.localdate().isoformat(), 'dni': dni, 'napraw': napraw, **found, 'akcje': akcje,
            'konta_x': x, 'kolejka_x': kolejka, 'profile': profiles, 'przyczyna': PRZYCZYNA,
            'podsumowanie': {'wywiady': len(found['wywiady']), 'diagnozy': len(found['diagnozy']),
                             'przekazy': len(found['przekazy']), 'konta_x_braki': len(x['braki']),
                             'konta_x_czeka': kolejka['czeka'], 'konta_x_konflikty': len(kolejka['konflikty']),
                             **{f'profile_bez_{k}': v for k, v in profiles['liczby'].items()}}}


PRZYCZYNA = ('Przyczyna podpisu „Andrzej Duda” przy wywiadzie z prezydentem Nawrockim: transkrypcję robi Gemini, który sam '
             'rozpoznaje gościa i jego funkcję z wiedzy sprzed 6.08.2025 („prezydent” = Andrzej Duda). Wynik nadpisywał '
             'gościa wskazanego wcześniej z tytułu filmu (clinic_interview.process), a żaden prompt nie znał aktualnych urzędów. '
             'Naprawa: blok urzędów z rejestru w promptach (transkrypcja, wywiad, diagnozy, przekaz dnia, wątek X), '
             'tytuł i kanał filmu jako wskazówka przy transkrypcji, Korektor poprawia gościa według tytułu i rejestru, '
             'bramka wstrzymuje treść z błędem urzędu przed publikacją.')


def text(report: dict) -> str:
    s = report['podsumowanie']
    lines = [f"Korektor spin.clinic · {report['dzien']} (treści z {report['dni']} dni, naprawa: {'tak' if report['napraw'] else 'nie'})", '',
             f"Błędy urzędów i osób: wywiady {s['wywiady']}, diagnozy {s['diagnozy']}, przekazy {s['przekazy']}."]
    for kind, label in (('wywiady', 'Wywiad'), ('diagnozy', 'Diagnoza'), ('przekazy', 'Przekaz')):
        for item in report[kind][:LIST_MAX]:
            lines.append(f"- {label} #{item['id']} ({item['status']}) {item['tytul'][:80]}: {opis(item['bledy'])}"
                         + (f" -> {item['akcja']}" if item.get('akcja') else ''))
    x = report['konta_x']
    lines += ['', '== Konta X ==']
    if not x['dostepna']:
        lines.append(f"Brak listy zweryfikowanej ({x['lista']}) - czeka na gałąź osoby-x.")
    else:
        lines.append(f"Lista zweryfikowana: {x['sprawdzone']} kont, nieprzypiętych: {len(x['braki'])}.")
        lines += [f"- {b['osoba']} (#{b['id']}): @{b['konto']} ({b['zrodlo']})" for b in x['braki'][:LIST_MAX]]
        if x.get('przypiecie'):
            lines.append(f"Przypięcie: {x['przypiecie'].get('status')} {x['przypiecie'].get('powod', '')}".strip())
    q = report['kolejka_x']
    lines.append(f"Kandydatury kont X czekające na rozstrzygnięcie: {q['czeka']}" + (f", najstarsza od {q['najstarsza']}" if q['najstarsza'] else '') + '.')
    lines += [f'- {reason}: {count}' for reason, count in q['powody'].items()]
    if q['konflikty']:
        lines.append('Konflikty dowodów (do decyzji człowieka, z propozycją):')
        lines += [f"- @{c['konto']}" + (f" ({c['nazwa']})" if c['nazwa'] else '') + f", osoby: {', '.join(c['osoby']) or 'brak'}"
                  + (f", od {c['od']}" if c['od'] else ', Strażnik ostatniej nocy') + f" -> {c['propozycja']}"
                  + (f" · {c['zrodlo']}" if c.get('zrodlo') else '') for c in q['konflikty'][:LIST_MAX]]
    p = report['profile']
    lines += ['', f"== Profile przeszłości ({p['osoby']} osób obecnych) - puste sekcje ==",
              f"KRS {p['liczby']['krs']}, oświadczenia {p['liczby']['oswiadczenia']}, głosowania (posłowie) "
              f"{p['liczby']['glosowania']}, zamówienia (osoby z KRS) {p['liczby']['zamowienia']}."]
    labels = {'krs': 'Bez KRS', 'oswiadczenia': 'Bez oświadczeń', 'glosowania': 'Bez głosowań', 'zamowienia': 'Bez zamówień'}
    for key in SECTIONS:
        rows = p['listy'][key][:15]
        if rows:
            lines.append(f"{labels[key]}: " + ', '.join(f"{r['osoba']} (#{r['id']})" for r in rows)
                         + (' …' if len(p['listy'][key]) > 15 else ''))
    lines += ['', '== Dla koordynatora ==', report['przyczyna'],
              'Rejestr urzędów: backend/news/urzedy.py (pozycje [DP] nie trafiają do promptów ani reguł).', '']
    return '\n'.join(lines)


def send(report: dict) -> dict:
    """Jeden mail dziennie na LOOP_REPORT_EMAIL (ten sam odbiorca co Raport pętli)."""
    from django.core.cache import cache
    from news.raport_petli import recipient
    from news.social_publish import _mail
    to = recipient()
    if not to:
        return {'status': 'not_configured'}
    key = f"korektor-mail:{report['dzien']}"
    if not cache.add(key, True, 26 * 3600):
        return {'status': 'already_run'}
    s = report['podsumowanie']
    bad = s['wywiady'] + s['diagnozy'] + s['przekazy']
    subject = f"spin.clinic · Korektor {report['dzien']}: " + (f'{bad} błędów urzędów' if bad else 'bez błędów urzędów')
    try:
        ok = _mail(to, subject, text(report), important=True)
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        cache.delete(key)
    return {'status': 'ok' if ok else 'error'}
