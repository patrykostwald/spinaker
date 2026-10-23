"""Pokrycie KRS przeszłość.today (sprint 23.10): każdy podmiot w bazie z odpisem z oficjalnego KRS i raport braków.

Trzy kroki, wszystkie po twardych identyfikatorach, nigdy po nazwie:
1. zasil(): do kolejki trafiają numery KRS podmiotów z bazy (brak NIP/REGON albo stary odpis), numery KRS z listy dotacji
   NIW-CRSO oraz NIP-y podmiotów z zamówień i dotacji (wykonawcy TED, zamawiający TED i BZP, beneficjenci FTS), których
   jeszcze nie mamy. Wykonawców-osób fizycznych nie bierzemy (parser TED nie zapisuje ich identyfikatorów).
2. uzupelnij(): NIP -> numer KRS z Białej listy podatników VAT (wl-api.mf.gov.pl, Ministerstwo Finansów; z odpowiedzi
   bierzemy wyłącznie pole „krs”, resztę, w tym nazwy osób, odrzucamy w pamięci), potem odpis aktualny z api-krs.ms.gov.pl.
   Podmiot zapisujemy tylko wtedy, gdy NIP z odpisu KRS jest tym samym NIP-em (dwa rejestry muszą się zgadzać).
   Odpis pełny pobieramy dla podmiotów z relacjami osób potwierdzonymi w KRS, żeby uzupełnić daty wykreślenia (weryfikacja
   jak w krs_agent.verify: inicjały, długość, ten sam rodzaj organu). Osób z KRS nie zapisujemy nigdy.
3. raport(): liczby pokrycia osób i podmiotów, stan kolejki, przyczyny braków.

Grzeczność wobec rejestrów: odstęp między zapytaniami (KRS_POKRYCIE_ODSTEP, domyślnie 1 s), limit na przebieg
(KRS_POKRYCIE_LIMIT), ponowienia po błędzie z rosnącą przerwą (2^n godzin, najwyżej 7 dni). Wyłączenie: KRS_POKRYCIE_ENABLED=false.
"""
from __future__ import annotations

import logging
import os
import re
import time
from collections import Counter
from datetime import date, timedelta

import requests
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from news import krs

logger = logging.getLogger(__name__)

WL_API = 'https://wl-api.mf.gov.pl/api/search/nips/{nips}'
WL_BATCH = 30            # tyle NIP-ów przyjmuje jedno zapytanie wyszukiwania Białej listy
STALE_DAYS = 90          # odpis aktualny starszy niż tyle dni odświeżamy
MAX_BACKOFF_HOURS = 24 * 7
PRIORITY = {'org': 0, 'niw': 1, 'ted_zamawiajacy': 2, 'bzp': 2, 'ted_wykonawca': 3, 'fts': 4}


def enabled() -> bool:
    return os.environ.get('KRS_POKRYCIE_ENABLED', 'true').strip().lower() not in ('0', 'false', 'no', 'off')


def _env_int(name, default):
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def _pause():
    try:
        seconds = float(os.environ.get('KRS_POKRYCIE_ODSTEP', '1'))
    except ValueError:
        seconds = 1.0
    if seconds > 0:
        time.sleep(seconds)


def valid_nip(value) -> str:
    """Same cyfry NIP z poprawną sumą kontrolną, inaczej ''."""
    nip = re.sub(r'\D', '', str(value or ''))
    if len(nip) != 10:
        return ''
    checksum = sum(int(d) * w for d, w in zip(nip[:9], (6, 5, 7, 2, 3, 4, 5, 6, 7))) % 11
    return nip if checksum == int(nip[-1]) else ''


# --- 1. zasilanie kolejki -------------------------------------------------------------------------------------------

def _enqueue(kind, value, origin, counter, stale=None):
    from news.przeszlosc_models import KrsKolejka
    priority = PRIORITY.get(origin, 5)
    stale = stale or timezone.now() - timedelta(days=_env_int('KRS_POKRYCIE_DNI', STALE_DAYS))
    try:
        with transaction.atomic():
            item, created = KrsKolejka.objects.get_or_create(kind=kind, value=value, defaults={'origin': origin, 'priority': priority})
    except IntegrityError:
        return
    if created:
        counter[origin] += 1
    elif item.status == 'ok' and origin == 'org' and (item.checked_at is None or item.checked_at < stale):
        # Śledczy R3 P1-21: tylko odpis starszy niż okres odświeżania; podmiot bez NIP w KRS nie wraca co noc
        # odpis do odświeżenia: wraca do kolejki, bez kasowania wyniku
        KrsKolejka.objects.filter(pk=item.pk).update(status='pending', next_try_at=timezone.now(), priority=0, attempts=0)
        counter['org_odswiez'] += 1
    elif priority < item.priority:
        KrsKolejka.objects.filter(pk=item.pk).update(priority=priority, origin=origin)


def record_identifiers(limit=None):
    """(rodzaj, wartość, pochodzenie) z rekordów pieniędzy; tylko jawne identyfikatory podmiotów."""
    from news.public_records_models import PublicRecord
    from news import drzewo_pieniedzy as money
    seen = set()

    def emit(kind, value, origin):
        if value and (kind, value) not in seen:
            seen.add((kind, value))
            return [(kind, value, origin)]
        return []

    out = []
    for data in PublicRecord.objects.filter(source='niw', kind='grant_pl').values_list('data', flat=True).iterator():
        out += emit('krs', krs.normalize_krs((data or {}).get('krs')) if len(money.digits((data or {}).get('krs'))) == 10 else '', 'niw')
    for data in PublicRecord.objects.filter(source='ted', kind='notice').values_list('data', flat=True).iterator():
        data = data or {}
        out += emit('nip', valid_nip(data.get('buyer_nip')), 'ted_zamawiajacy')
        for winner in data.get('winners') or []:
            if isinstance(winner, dict) and not winner.get('osoba_fizyczna'):
                raw = str(winner.get('id') or '').strip().upper()
                # tylko polski NIP (z prefiksem PL albo same cyfry); identyfikatory zagraniczne pomijamy
                if re.fullmatch(r'(PL)?[0-9 -]{10,13}', raw):
                    out += emit('nip', valid_nip(raw), 'ted_wykonawca')
    for data in PublicRecord.objects.filter(source='bzp', kind='notice').values_list('data', flat=True).iterator():
        out += emit('nip', valid_nip(money.buyer_nip(data or {})), 'bzp')
    for data in PublicRecord.objects.filter(source='fts', kind='eu_grant').values_list('data', flat=True).iterator():
        raw = str((data or {}).get('vat') or '').strip().upper()
        if re.fullmatch(r'(PL)?[0-9 -]{10,13}', raw):
            out += emit('nip', valid_nip(raw), 'fts')
    return out[:limit] if limit else out


def zasil(limit=None) -> dict:
    """Dopisuje do kolejki braki. Idempotentne: ten sam numer trafia do kolejki raz."""
    from news.political_models import RegisteredOrganisation
    counter = Counter()
    stale = timezone.now() - timedelta(days=_env_int('KRS_POKRYCIE_DNI', STALE_DAYS))
    orgs = RegisteredOrganisation.objects.filter(archived=False).filter(
        Q(nip='') | Q(regon='') | Q(legal_form='') | Q(source_checked_at__lt=stale))
    for number in orgs.values_list('krs_number', flat=True).iterator():
        _enqueue('krs', number, 'org', counter)
    known_krs = set(RegisteredOrganisation.objects.values_list('krs_number', flat=True))
    known_nip = set(RegisteredOrganisation.objects.exclude(nip='').values_list('nip', flat=True))
    for kind, value, origin in record_identifiers(limit):
        if (kind == 'krs' and value in known_krs) or (kind == 'nip' and value in known_nip):
            continue
        _enqueue(kind, value, origin, counter)
    return dict(counter)


# --- 2. uzupełnianie ------------------------------------------------------------------------------------------------

def _defer(item, status, error=''):
    item.attempts += 1
    item.status = status
    item.last_error = error[:120]
    item.checked_at = timezone.now()
    hours = min(MAX_BACKOFF_HOURS, 2 ** item.attempts) if status == 'error' else MAX_BACKOFF_HOURS * 8
    item.next_try_at = timezone.now() + timedelta(hours=hours)
    item.save(update_fields=['attempts', 'status', 'last_error', 'checked_at', 'next_try_at'])


def biala_lista(nips: list[str], day: date | None = None) -> tuple[dict[str, str], str]:
    """({nip: numer KRS albo ''}, status ok|error). Z odpowiedzi bierzemy tylko „nip” i „krs” - nic o osobach.

    NIP nieznany Białej liście (albo podmiot bez KRS, np. działalność osoby fizycznej) daje ''."""
    if not nips:
        return {}, 'ok'
    url = WL_API.format(nips=','.join(nips))
    try:
        response = requests.get(url, params={'date': (day or timezone.localdate()).isoformat()}, headers=krs.HEADERS, timeout=(5, 30))
    except requests.RequestException as error:
        logger.warning('Biała lista: %s', type(error).__name__)
        return {}, 'error'
    if response.status_code != 200:
        logger.warning('Biała lista: http %s', response.status_code)
        return {}, 'error'
    try:
        result = (response.json() or {}).get('result') or {}
    except ValueError:
        return {}, 'error'
    found = {nip: '' for nip in nips}
    subjects = list(result.get('subjects') or [])
    for entry in result.get('entries') or []:
        subjects += [s for s in (entry or {}).get('subjects') or [] if s]
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        nip = re.sub(r'\D', '', str(subject.get('nip') or ''))
        number = krs.normalize_krs(subject.get('krs')) if re.sub(r'\D', '', str(subject.get('krs') or '')) else ''
        if nip in found and number:
            found[nip] = number
    return found, 'ok'


def save_extract(extract: krs.Extract):
    """Podmiot z odpisu: tylko dane podmiotu (nazwa, forma, identyfikatory, sektor). Nazwa ładnie jak w agencie KRS."""
    from news.krs_agent import _pretty
    from news.political_models import RegisteredOrganisation
    defaults = {'name': (_pretty(extract.name) or extract.name).strip()[:512], 'kind': extract.kind,
                'legal_form': extract.legal_form.lower()[:128], 'register': extract.register,
                'official_register_url': extract.public_url, 'source_checked_at': timezone.now(),
                **{k: v for k, v in (('nip', extract.nip), ('regon', extract.regon)) if v}}
    org = RegisteredOrganisation.objects.filter(krs_number=extract.krs).first()
    if org is None:
        defaults['sector'] = extract.sector
        return RegisteredOrganisation.objects.create(krs_number=extract.krs, **defaults)
    if extract.sector in ('state', 'municipal') and org.sector in ('unknown', ''):
        defaults['sector'] = extract.sector
        defaults['sector_note'] = 'Wspólnik lub założyciel według KRS: ' + '; '.join(extract.owners[:3])
    for key, value in defaults.items():
        setattr(org, key, value)
    org.save()
    return org


def refresh_relations(org, extract_full: krs.Extract) -> int:
    """Odpis pełny: relacje osób potwierdzone w KRS dostają datę wykreślenia, gdy osoba zniknęła z organu.

    Ta sama weryfikacja co przy potwierdzeniu (inicjały, długość imienia i nazwiska, rodzaj organu). Bez zgodności nic nie zmieniamy."""
    from news.political_models import PublicFigureOrganisationRelation
    changed = 0
    rows = PublicFigureOrganisationRelation.objects.filter(organisation=org, verification_status='confirmed',
                                                           verification_method='krs_register', until__isnull=True)
    for rel in rows.select_related('public_figure'):
        people = [p for p in krs.matching_persons(extract_full, rel.public_figure.canonical_name)
                  if krs.same_organ(rel.organ or rel.public_role, p.organ, p.function)]
        if not people or any(p.until is None for p in people):
            continue  # nadal w organie albo brak zgodności - zostawiamy
        until = max(p.until for p in people)
        twin = PublicFigureOrganisationRelation.objects.filter(public_figure=rel.public_figure, organisation=org,
                                                                public_role=rel.public_role, relation_status='former').first()
        with transaction.atomic():
            if twin:
                twin.until = twin.until or until
                twin.save(update_fields=['until', 'updated_at'])
                rel.delete()
            else:
                rel.until, rel.relation_status = until, 'former'
                rel.save()  # zmiana twierdzenia cofa potwierdzenie (save) - potwierdza je ponownie ten sam odpis KRS
                rel.confirm_automatically('krs_register')
                rel.save(update_fields=['verification_method', 'verification_status', 'verified_by', 'verified_at', 'updated_at'])
        changed += 1
    return changed


def uzupelnij(limit: int | None = None, wl_limit: int | None = None) -> dict:
    """Jedna partia kolejki: najpierw NIP-y przez Białą listę (paczkami), potem odpisy KRS. Zwraca liczniki."""
    from news.przeszlosc_models import KrsKolejka
    limit = _env_int('KRS_POKRYCIE_LIMIT', 200) if limit is None else limit
    wl_limit = _env_int('BIALA_LISTA_ZAPYTAN', 10) if wl_limit is None else wl_limit
    stats = Counter()
    now = timezone.now()
    due = KrsKolejka.objects.filter(status__in=('pending', 'error'), next_try_at__lte=now)
    # NIP -> KRS (paczki po 30). NIP z wynikiem zostaje w kolejce z krs_number i idzie po odpis.
    nip_items = list(due.filter(kind='nip', krs_number='').order_by('priority', 'next_try_at', 'pk')[:WL_BATCH * wl_limit])
    for offset in range(0, len(nip_items), WL_BATCH):
        batch = nip_items[offset:offset + WL_BATCH]
        found, status = biala_lista([i.value for i in batch])
        stats['biala_lista_zapytania'] += 1
        for item in batch:
            if status == 'error':
                _defer(item, 'error', 'Biała lista nie odpowiada')
                stats['error'] += 1
            elif found.get(item.value):
                item.krs_number = found[item.value]
                item.save(update_fields=['krs_number'])
                stats['nip_z_krs'] += 1
            else:
                _defer(item, 'no_krs')
                stats['no_krs'] += 1
        _pause()
    from news.political_models import RegisteredOrganisation
    taken = 0
    items = due.filter(Q(kind='krs') | ~Q(krs_number='')).order_by('priority', 'next_try_at', 'pk')
    for item in items[:limit]:
        if item.kind == 'nip':
            known = RegisteredOrganisation.objects.filter(krs_number=item.krs_number).first()
            if known and known.nip == item.value:
                item.status, item.organisation, item.checked_at = 'ok', known, timezone.now()
                item.save(update_fields=['status', 'organisation', 'checked_at'])
                stats['ok'] += 1
                continue
            target = item.krs_number
        else:
            target = item.value
        stats[_process_krs_for(item, target)] += 1
        taken += 1
        _pause()
    stats['odpisy'] = taken
    return dict(stats)


def _process_krs_for(item, number) -> str:
    """Odpis dla pozycji kolejki: KRS wprost albo KRS znaleziony po NIP (wtedy NIP odpisu musi się zgadzać)."""
    from news.political_models import PublicFigureOrganisationRelation
    extract, status = krs.fetch_status(number, full=False)
    if status == 'error':
        _defer(item, 'error', 'api-krs nie odpowiada')
        return 'error'
    if extract is None or not extract.name:
        _defer(item, 'missing')
        return 'missing'
    if item.kind == 'nip' and extract.nip != item.value:
        _defer(item, 'mismatch', f'NIP w KRS: {extract.nip or "brak"}')
        return 'mismatch'
    org = save_extract(extract)
    if PublicFigureOrganisationRelation.objects.filter(organisation=org, verification_method='krs_register',
                                                       verification_status='confirmed', until__isnull=True).exists():
        _pause()
        full, full_status = krs.fetch_status(number, full=True)
        if full_status == 'ok' and full:
            refresh_relations(org, full)
    item.status, item.organisation, item.krs_number = 'ok', org, extract.krs
    item.checked_at, item.last_error, item.attempts = timezone.now(), '', 0
    item.next_try_at = timezone.now() + timedelta(days=_env_int('KRS_POKRYCIE_DNI', STALE_DAYS))
    item.save(update_fields=['status', 'organisation', 'krs_number', 'checked_at', 'last_error', 'attempts', 'next_try_at'])
    return 'ok'


def run() -> dict:
    """Nocny przebieg: zasilenie kolejki i jedna partia uzupełnień."""
    if not enabled():
        return {'status': 'disabled'}
    return {'status': 'ok', 'zasilono': zasil(), 'uzupelniono': uzupelnij()}


# --- 3. raport ------------------------------------------------------------------------------------------------------

def raport() -> dict:
    """Pokrycie osób i podmiotów; bez sieci. Te same liczby idą do strony stanu danych."""
    from news.political_models import PublicFigure, PublicFigureOrganisationRelation, RegisteredOrganisation
    from news.przeszlosc_models import KrsKolejka
    from news import krs_agent
    figures = PublicFigure.objects.filter(archived=False, merged_into__isnull=True)
    confirmed = PublicFigureOrganisationRelation.objects.filter(verification_status='confirmed')
    with_rel = figures.filter(organisation_relations__verification_status='confirmed').distinct().count()
    total = figures.count()
    checked = figures.exclude(organisations_checked_at__isnull=True).count()
    orgs = RegisteredOrganisation.objects.filter(archived=False)
    org_total = orgs.count()
    stale = timezone.now() - timedelta(days=_env_int('KRS_POKRYCIE_DNI', STALE_DAYS))
    queue = dict(KrsKolejka.objects.values_list('status').annotate(n=Count('pk')).values_list('status', 'n'))
    by_origin = {}
    for origin, status, n in KrsKolejka.objects.values_list('origin', 'status').annotate(n=Count('pk')).values_list('origin', 'status', 'n'):
        by_origin.setdefault(origin or '-', {})[status] = n
    current = figures.filter(status='current')
    return {
        'generated_at': timezone.now().isoformat(timespec='minutes'),
        'osoby': {
            'wszystkie': total, 'sprawdzone_w_krs': checked, 'niesprawdzone': total - checked,
            'z_potwierdzonym_podmiotem': with_rel,
            'aktualne_niesprawdzone': current.filter(organisations_checked_at__isnull=True).count(),
            'relacje_potwierdzone': confirmed.count(),
            'relacje_wedlug_metody': dict(confirmed.values_list('verification_method').annotate(n=Count('pk')).values_list('verification_method', 'n')),
            'relacje_do_przegladu': PublicFigureOrganisationRelation.objects.filter(verification_status='pending_review').count(),
            'agent_wlaczony': krs_agent.enabled(),
            'agent_dziennie': _env_int('KRS_AGENT_DAILY', 10),
        },
        'podmioty': {
            'wszystkie': org_total,
            'z_nip': orgs.exclude(nip='').count(), 'z_regon': orgs.exclude(regon='').count(),
            'bez_nip': orgs.filter(nip='').count(),
            'odpis_starszy_niz_dni': _env_int('KRS_POKRYCIE_DNI', STALE_DAYS),
            'odpis_stary': orgs.filter(source_checked_at__lt=stale).count(),
            'wedlug_sektora': dict(orgs.values_list('sector').annotate(n=Count('pk')).values_list('sector', 'n')),
        },
        'kolejka': {'wedlug_stanu': queue, 'wedlug_pochodzenia': by_origin,
                    'bledy': list(KrsKolejka.objects.filter(status='error').order_by('-checked_at')
                                  .values('kind', 'value', 'last_error', 'attempts')[:10])},
        'wlaczone': enabled(),
        'zasady': 'Łączymy wyłącznie po numerze KRS i NIP (Biała lista MF -> KRS, NIP musi się zgadzać). '
                  'Osoby z podmiotami tylko po potwierdzeniu w KRS (inicjały, długość, organ) albo w dwóch niezależnych źródłach.',
    }


def raport_tekst(data: dict) -> str:
    o, p, k = data['osoby'], data['podmioty'], data['kolejka']

    def pct(a, b):
        return f'{(100 * a / b):.0f}%' if b else '-'
    lines = [
        f"Pokrycie KRS ({data['generated_at']}), uzupełnianie {'włączone' if data['wlaczone'] else 'WYŁĄCZONE'}",
        '',
        'OSOBY PUBLICZNE',
        f"  wszystkie: {o['wszystkie']}",
        f"  sprawdzone w KRS: {o['sprawdzone_w_krs']} ({pct(o['sprawdzone_w_krs'], o['wszystkie'])}), niesprawdzone: {o['niesprawdzone']}"
        f" (w tym aktualne funkcje: {o['aktualne_niesprawdzone']})",
        f"  z co najmniej jednym potwierdzonym podmiotem: {o['z_potwierdzonym_podmiotem']}",
        f"  relacje potwierdzone: {o['relacje_potwierdzone']} {o['relacje_wedlug_metody']}, do weryfikacji zespołu: {o['relacje_do_przegladu']}",
        f"  agent KRS: {'włączony' if o['agent_wlaczony'] else 'WYŁĄCZONY (KRS_AGENT_ENABLED, GEMINI_API_KEY)'}, {o['agent_dziennie']} osób na dobę",
        '',
        'PODMIOTY',
        f"  wszystkie: {p['wszystkie']}, z NIP: {p['z_nip']} ({pct(p['z_nip'], p['wszystkie'])}), z REGON: {p['z_regon']}",
        f"  odpis starszy niż {p['odpis_starszy_niz_dni']} dni: {p['odpis_stary']}",
        f"  sektor: {p['wedlug_sektora']}",
        '',
        'KOLEJKA',
        f"  stan: {k['wedlug_stanu']}",
    ]
    for origin, states in sorted(k['wedlug_pochodzenia'].items()):
        lines.append(f'  {origin}: {states}')
    for err in k['bledy']:
        lines.append(f"  błąd: {err['kind']} {err['value']} - {err['last_error']} (prób {err['attempts']})")
    return '\n'.join(lines)
