"""Oświadczenia majątkowe posłów (decyzja właściciela 13.10; flaga ASSETS_DECLARATIONS_ENABLED, domyślnie wyłączona).

Źródło: istniejący zbieracz `scraper/public_records.py` (źródło `assets`, flaga PUBLIC_RECORDS_ASSETS_ENABLED) zapisuje
indeks oświadczeń z profilu posła na www.sejm.gov.pl jako PublicRecord(kind='asset_document') z linkiem do PDF.
Ten moduł:
1. `sync()` - przenosi indeks do AssetDeclaration (rok, typ: oświadczenie/korekta, data złożenia z opisu, poseł po
   identyfikatorze Sejmu i kadencji, nigdy po nazwisku);
2. `fetch_metadata()` - grzecznie pobiera PDF tylko z www.sejm.gov.pl (opóźnienie, ETag/If-Modified-Since, limit liczby
   i rozmiaru), zapisuje sumę kontrolną i rozmiar; PDF nie jest przechowywany; odczyt automatyczny tylko liczby stron
   i obecności warstwy tekstu (skany bez OCR), oznaczony „odczytane automatycznie, sprawdź w PDF”;
3. `public_block()` - lista w profilu osoby: link do PDF i metadane. Bez wskaźników pochodnych, porównań i ocen.
Ta sama procedura dla każdego posła.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import date, timedelta
from io import BytesIO
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

ALLOWED_HOST = 'www.sejm.gov.pl'
MAX_BYTES = 10_000_000
REFRESH_DAYS = 30
AUTO_READ_NOTE = 'Odczytane automatycznie, sprawdź w PDF.'
NOTICE = ('Oświadczenia majątkowe w oryginale (PDF z serwisu Sejmu RP). Pokazujemy dokumenty i ich daty; nie porównujemy '
          'ich, nie liczymy wskaźników i nie oceniamy. Rozstrzyga treść PDF.')
SOURCE = {'name': 'Sejm RP, oświadczenia majątkowe posłów', 'url': 'https://www.sejm.gov.pl',
          'license': 'informacja publiczna (jawność oświadczeń z ustawy o wykonywaniu mandatu posła i senatora)'}
KIND_LABEL = {'oswiadczenie': 'Oświadczenie majątkowe', 'korekta': 'Korekta oświadczenia', 'inne': 'Dokument'}
USER_AGENT = 'przeszlosc.today (iapply sp. z o.o.; kontakt@iapply.pl) - indeks oświadczeń, 1 zapytanie na kilka sekund'


def enabled() -> bool:
    from news.v3_flags import flag
    return flag('ASSETS_DECLARATIONS_ENABLED')


def classify(text) -> str:
    text = (text or '').lower()
    if 'korekt' in text:
        return 'korekta'
    if re.search(r'oświadcz|oswiadcz|majątk|majatk', text):
        return 'oswiadczenie'
    return 'inne'


def filing_date(text):
    """Data złożenia z opisu w indeksie (dd.mm.rrrr albo rrrr-mm-dd); None, gdy brak albo niejednoznaczna."""
    found = set()
    for d, m, y in re.findall(r'(?<!\d)(\d{1,2})\.(\d{1,2})\.(20\d{2})(?!\d)', text or ''):
        found.add((int(y), int(m), int(d)))
    for y, m, d in re.findall(r'(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)', text or ''):
        found.add((int(y), int(m), int(d)))
    if len(found) != 1:
        return None
    try:
        return date(*found.pop())
    except ValueError:
        return None


def sync() -> dict:
    """Indeks z PublicRecord(asset_document) -> AssetDeclaration (idempotentnie, po adresie PDF)."""
    from news.clinic_models import AssetDeclaration
    from news.przeszlosc_osoba import figures_for_mps
    from news.public_records_models import PublicRecord
    created = updated = 0
    rows = list(PublicRecord.objects.filter(kind='asset_document').order_by('pk'))
    pairs = {(r.term or 10, int((r.data or {}).get('mp_id') or 0)) for r in rows if (r.data or {}).get('mp_id')}
    figures = figures_for_mps(pairs)
    for r in rows:
        data = r.data or {}
        mp_id = int(data.get('mp_id') or 0)
        if not mp_id or not r.source_url:
            continue
        term = r.term or 10
        text = f"{r.title} {data.get('context', '')}"
        _, was_created = AssetDeclaration.objects.update_or_create(url=r.source_url, defaults={
            'record': r, 'term': term, 'mp_id': mp_id, 'name': str(data.get('name', ''))[:200],
            'figure': figures.get((term, mp_id)), 'year': data.get('year') if data.get('year_status') == 'reported' else None,
            'kind': classify(text), 'title': (r.title or '')[:400], 'published_on': filing_date(data.get('context', ''))})
        created += int(was_created)
        updated += int(not was_created)
    return {'created': created, 'updated': updated}


def auto_read(raw) -> dict:
    """Tylko liczba stron i obecność warstwy tekstu (bez OCR, bez odczytu kwot); oznaczenie do sprawdzenia w PDF."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            return {'status': 'zaszyfrowany PDF', 'note': AUTO_READ_NOTE}
        chars = sum(len(page.extract_text() or '') for page in reader.pages[:20])
        return {'pages': len(reader.pages), 'text_layer': chars > 50,
                'status': 'warstwa tekstu' if chars > 50 else 'skan bez warstwy tekstu', 'note': AUTO_READ_NOTE}
    except Exception as error:  # noqa: BLE001 - uszkodzony PDF nie zatrzymuje kolejki
        return {'status': f'nie udało się odczytać ({type(error).__name__})', 'note': AUTO_READ_NOTE}


ROBOTS_URL = 'https://www.sejm.gov.pl/robots.txt'
ROBOTS_CACHE = 'assets:robots:www.sejm.gov.pl'
TIMEOUT = (5, 20)  # (połączenie, odczyt) w sekundach


def robots_policy(session):
    """robots.txt www.sejm.gov.pl z cache 24 h. Zwraca parser albo None, gdy nie udało się pobrać (wtedy decyzja
    ASSETS_ROBOTS_FAIL_OPEN, domyślnie False = nie pobieramy). Brak pliku (404) = brak ograniczeń (konwencja robots)."""
    from urllib.robotparser import RobotFileParser
    from django.core.cache import cache
    text = cache.get(ROBOTS_CACHE)
    if text is None:
        try:
            response = session.get(ROBOTS_URL, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT)
            if response.status_code == 404:
                text = ''
            elif response.status_code == 200:
                text = response.text
            else:
                return None
        except Exception:  # noqa: BLE001
            return None
        cache.set(ROBOTS_CACHE, text, 24 * 3600)
    parser = RobotFileParser()
    parser.parse(text.splitlines())
    return parser


def fetch_metadata(limit=20, delay=None, session=None, now=None) -> dict:
    """Grzeczne pobranie metadanych PDF: tylko www.sejm.gov.pl, opóźnienie między zapytaniami, ETag i If-Modified-Since,
    odświeżenie najwyżej co 30 dni, limit rozmiaru. PDF nie jest zapisywany."""
    import requests
    from news.clinic_models import AssetDeclaration
    now = now or timezone.now()
    delay = float(getattr(settings, 'ASSETS_DECLARATIONS_DELAY_SECONDS', 5.0) if delay is None else delay)
    session = session or requests.Session()
    due = (AssetDeclaration.objects.filter(fetched_at__isnull=True) | AssetDeclaration.objects.filter(
        fetched_at__lt=now - timedelta(days=REFRESH_DAYS))).order_by('fetched_at', 'pk')[:limit]
    done = unchanged = errors = 0
    policy = robots_policy(session)
    if policy is None and not getattr(settings, 'ASSETS_ROBOTS_FAIL_OPEN', False):
        return {'fetched': 0, 'unchanged': 0, 'errors': 0, 'stopped': 'robots.txt niedostępny: przerwano (fail-closed)'}
    for i, row in enumerate(due):
        parts = urlsplit(row.url)
        if parts.scheme != 'https' or parts.hostname != ALLOWED_HOST or not parts.path.lower().endswith('.pdf'):
            row.fetch_error, row.fetched_at = 'adres spoza www.sejm.gov.pl albo nie PDF', now
            row.save(update_fields=['fetch_error', 'fetched_at'])
            errors += 1
            continue
        if policy is not None and not policy.can_fetch(USER_AGENT, row.url):
            row.fetch_error, row.fetched_at = 'robots.txt zabrania pobrania', now
            row.save(update_fields=['fetch_error', 'fetched_at'])
            errors += 1
            continue
        if i and delay:
            time.sleep(delay)
        headers = {'User-Agent': USER_AGENT}
        if row.etag:
            headers['If-None-Match'] = row.etag
        if row.last_modified:
            headers['If-Modified-Since'] = row.last_modified
        response = None
        try:
            response = session.get(row.url, headers=headers, timeout=TIMEOUT, stream=True)
            if response.status_code == 304:
                row.fetched_at, row.fetch_error = now, ''
                row.save(update_fields=['fetched_at', 'fetch_error'])
                unchanged += 1
                continue
            response.raise_for_status()
            declared = response.headers.get('Content-Length')
            if declared and declared.isdigit() and int(declared) > MAX_BYTES:
                raise ValueError('pdf_too_large')  # przed pobraniem treści
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError('pdf_too_large')  # natychmiast, bez składania reszty
                chunks.append(chunk)
            raw = b''.join(chunks)
            if not raw.startswith(b'%PDF-'):
                raise ValueError('not_pdf')
        except Exception as error:  # noqa: BLE001
            row.fetch_error, row.fetched_at = f'{type(error).__name__}: {error}'[:200], now
            row.save(update_fields=['fetch_error', 'fetched_at'])
            errors += 1
            continue
        finally:
            if response is not None and hasattr(response, 'close'):
                response.close()
        row.sha256, row.size = hashlib.sha256(raw).hexdigest(), len(raw)
        row.etag, row.last_modified = response.headers.get('ETag', '')[:200], response.headers.get('Last-Modified', '')[:100]
        row.fetched_at, row.fetch_error, row.auto_read = now, '', auto_read(raw)
        row.save(update_fields=['sha256', 'size', 'etag', 'last_modified', 'fetched_at', 'fetch_error', 'auto_read'])
        done += 1
    return {'fetched': done, 'unchanged': unchanged, 'errors': errors}


def public_block(figure) -> dict:
    from django.db.models import Q
    from news.clinic_models import AssetDeclaration
    from news.przeszlosc_osoba import mp_identities
    q = Q(figure=figure)
    for term, mp_id in mp_identities(figure):
        q |= Q(term=term, mp_id=mp_id)
    items = [{'year': d.year, 'kind': d.kind, 'kind_label': KIND_LABEL[d.kind], 'published_on': d.published_on,
              'title': d.title, 'url': d.url, 'sha256': d.sha256 or None, 'checked_at': d.fetched_at,
              'auto_read': ({**d.auto_read, 'note': AUTO_READ_NOTE} if d.auto_read else None)}
             for d in AssetDeclaration.objects.filter(q).order_by('-year', '-published_on', '-pk')[:60]]
    return {'items': items, 'notice': NOTICE, 'source': SOURCE,
            'rights': 'Osoba może zgłosić błąd w opisie dokumentu albo sprzeciw: kontakt@iapply.pl.'}


def extend_profile(data: dict, figure) -> dict:
    if enabled():
        data['assets_declarations'] = public_block(figure)
    return data
