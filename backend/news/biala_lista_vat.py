"""Status VAT podmiotów z Białej listy podatników (Ministerstwo Finansów), 6.11.2026.

Zasady (docs/PRZESZLOSC_ZRODLA_DANYCH.md, pozycja 7; limity z gov.pl/web/kas/api-wykazu-podatnikow-vat):
- adres od 15.10.2026: https://wykazpodatnikowvat.mf.gov.pl/api (stary wl-api.mf.gov.pl działa tylko do 1.12.2026);
- metoda „search”: 100 zapytań dziennie po 30 NIP, wspólny licznik dla kolejki NIP→KRS i tego zbieracza (domyślnie 90 z zapasem);
- tylko podmioty, które już mamy (RegisteredOrganisation z NIP): status VAT, daty rejestracji, wykreślenia i przywrócenia,
  podstawa wykreślenia, flaga rachunków wirtualnych i LICZBA rachunków. Nie zapisujemy numerów rachunków, adresów, PESEL,
  reprezentantów, prokurentów ani wspólników (to dane osób); brak NIP w wykazie to „brak w wykazie”, nie „nie jest podatnikiem”.
"""
import hashlib
import json
import logging
import os
import re
import time
from collections import Counter
from datetime import timedelta

import requests
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_API = 'https://wykazpodatnikowvat.mf.gov.pl/api'
BATCH = 30
STALE_DAYS = 7
DAILY_DEFAULT = 90           # urząd: 100 zapytań „search” na dobę; zapas na kolejkę KRS i błędy
HEADERS = {'User-Agent': 'przeszlosc.today VAT status (+https://przeszlosc.today/przeszlosc/jak-to-dziala)', 'Accept': 'application/json'}
SOURCE, KIND = 'biala_lista', 'vat_status'
KEEP = {'statusVat': 'status_vat', 'registrationLegalDate': 'registration_date', 'registrationDenialDate': 'denial_date',
        'registrationDenialBasis': 'denial_basis', 'restorationDate': 'restoration_date', 'restorationBasis': 'restoration_basis',
        'removalDate': 'removal_date', 'removalBasis': 'removal_basis', 'exemptionSmeDate': 'exemption_sme_date',
        'hasVirtualAccounts': 'has_virtual_accounts'}


def enabled():
    return os.environ.get('BIALA_LISTA_VAT_ENABLED', 'true').strip().lower() not in ('0', 'false', 'no', 'off')


def api_base():
    return os.environ.get('BIALA_LISTA_API', DEFAULT_API).strip().rstrip('/')


def search_url(nips):
    return f"{api_base()}/search/nips/{','.join(nips)}"


def daily_limit():
    try:
        return max(0, int(os.environ.get('BIALA_LISTA_LIMIT_DZIENNY', DAILY_DEFAULT)))
    except ValueError:
        return DAILY_DEFAULT


def reserve_request():
    """Jedno zapytanie „search” z dziennego budżetu (cache, doba lokalna); False, gdy budżet wyczerpany."""
    key = f'biala_lista:zapytania:{timezone.localdate().isoformat()}'
    cache.add(key, 0, timeout=36 * 3600)
    try:
        used = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=36 * 3600)
        used = 1
    if used > daily_limit():
        try:
            cache.decr(key)
        except ValueError:
            pass
        return False
    return True


def subjects(payload):
    """Wszystkie obiekty podmiotów z odpowiedzi (wersje z „entries” i bez)."""
    result = (payload or {}).get('result') or {}
    found = list(result.get('subjects') or [])
    for entry in result.get('entries') or []:
        found += [s for s in (entry or {}).get('subjects') or [] if s]
    return [s for s in found if isinstance(s, dict)]


def reduce(subject):
    """Tylko pola o podmiocie (lista KEEP) i liczba rachunków; nic o osobach."""
    data = {new: subject.get(old) for old, new in KEEP.items() if subject.get(old) not in (None, '')}
    data['accounts'] = len(subject.get('accountNumbers') or [])
    return data


def fetch(nips, day=None):
    """({nip: dane albo None}, status ok|error|limit). None = NIP nieznany wykazowi."""
    if not nips:
        return {}, 'ok'
    if not reserve_request():
        return {}, 'limit'
    url = search_url(nips)
    try:
        response = requests.get(url, params={'date': (day or timezone.localdate()).isoformat()}, headers=HEADERS, timeout=(5, 30))
    except requests.RequestException as error:
        logger.warning('Biała lista (status VAT): %s', type(error).__name__)
        return {}, 'error'
    if response.status_code != 200:
        logger.warning('Biała lista (status VAT): http %s', response.status_code)
        return {}, 'error'
    try:
        payload = response.json()
    except ValueError:
        return {}, 'error'
    out = {nip: None for nip in nips}
    for subject in subjects(payload):
        nip = re.sub(r'\D', '', str(subject.get('nip') or ''))
        if nip in out:
            out[nip] = reduce(subject)
    return out, 'ok'


def _pause():
    try:
        seconds = float(os.environ.get('BIALA_LISTA_ODSTEP', '1'))
    except ValueError:
        seconds = 1.0
    if seconds > 0:
        time.sleep(seconds)


def _save(org, data, url):
    from news.public_records_models import PublicRecord
    today = timezone.localdate()
    record = PublicRecord.objects.filter(source=SOURCE, kind=KIND, external_id=org.nip).first()
    previous = (record.data if record else {}) or {}
    new = {'found': data is not None, **(data or {})}
    changes = list(previous.get('changes') or [])
    if record and previous.get('status_vat') != new.get('status_vat'):
        changes.append({'date': today.isoformat(), 'from': previous.get('status_vat'), 'to': new.get('status_vat')})
    new['changes'] = changes[-10:]
    digest = hashlib.sha256(json.dumps(new, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    PublicRecord.objects.update_or_create(source=SOURCE, kind=KIND, external_id=org.nip, defaults=dict(
        source_url='https://wykazpodatnikowvat.mf.gov.pl/', response_url=url, response_sha256=digest, fetched_at=timezone.now(),
        date=today, title=org.name[:2000], data=new))
    return bool(record and changes and changes[-1]['date'] == today.isoformat())


def refresh(max_requests=None):
    """Jedna partia: podmioty bez statusu albo ze statusem starszym niż STALE_DAYS (najstarsze pierwsze)."""
    from news.political_models import RegisteredOrganisation
    from news.public_records_models import PublicRecord
    if not enabled():
        return {'status': 'disabled'}
    try:
        max_requests = int(os.environ.get('BIALA_LISTA_VAT_ZAPYTAN', 20)) if max_requests is None else max_requests
    except ValueError:
        max_requests = 20
    fresh = {r.external_id: r.fetched_at for r in PublicRecord.objects.filter(source=SOURCE, kind=KIND)}
    cutoff = timezone.now() - timedelta(days=STALE_DAYS)
    orgs = [o for o in RegisteredOrganisation.objects.filter(archived=False).exclude(nip='').order_by('pk')
            if len(o.nip) == 10 and (o.nip not in fresh or fresh[o.nip] < cutoff)]
    orgs.sort(key=lambda o: fresh.get(o.nip) or timezone.make_aware(timezone.datetime(1970, 1, 1)))
    stats = Counter(due=len(orgs))
    for offset in range(0, min(len(orgs), BATCH * max_requests), BATCH):
        batch = orgs[offset:offset + BATCH]
        found, status = fetch([o.nip for o in batch])
        stats['zapytania'] += 1
        if status == 'limit':
            stats['limit_dzienny'] += 1
            break
        if status == 'error':
            stats['error'] += 1
            continue
        url = search_url([o.nip for o in batch])
        for org in batch:
            changed = _save(org, found.get(org.nip), url)
            stats['zapisano'] += 1
            stats['zmiana_statusu'] += int(changed)
        _pause()
    return {'status': 'ok', **stats}


def status_for(org):
    """Blok „vat” w profilu podmiotu albo None, gdy jeszcze nie sprawdzaliśmy."""
    from news.public_records_models import PublicRecord
    if not org.nip:
        return None
    record = PublicRecord.objects.filter(source=SOURCE, kind=KIND, external_id=org.nip).first()
    if record is None:
        return None
    d = record.data or {}
    return {'found': bool(d.get('found')), 'status': d.get('status_vat'), 'registration_date': d.get('registration_date'),
            'removal_date': d.get('removal_date'), 'removal_basis': d.get('removal_basis'), 'restoration_date': d.get('restoration_date'),
            'denial_date': d.get('denial_date'), 'virtual_accounts': d.get('has_virtual_accounts'), 'accounts': d.get('accounts'),
            'changes': d.get('changes') or [], 'checked_at': record.fetched_at.isoformat(timespec='minutes'),
            'source': 'Wykaz podatników VAT (Ministerstwo Finansów)', 'url': 'https://wykazpodatnikowvat.mf.gov.pl/',
            'note': 'Brak podmiotu w wykazie nie znaczy, że nie istnieje: wykaz obejmuje podatników VAT.'}
