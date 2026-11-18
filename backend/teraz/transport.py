"""Transport HTTP dla adresów zatwierdzonych w bramce dostępu."""

import ipaddress
import logging
import os
import re
import socket
from collections.abc import Callable, Mapping
from contextlib import closing, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from email.message import Message
from time import monotonic
from urllib.parse import unquote, urlsplit, urlunsplit

import requests
import sentry_sdk
from billiard.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.cache import caches
from redis.exceptions import RedisError
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from sentry_sdk.client import NonRecordingClient

from scraper.access_gate import AccessDenied, require_approved_instruction

USER_AGENT = "przeszlosc.today-teraz/1.0 (+https://przeszlosc.today; kontakt@iapply.pl)"
LIMIT_ROZMIARU = 5 * 1024 * 1024
LIMIT_CZASU_TRESCI = 25
ROZMIAR_FRAGMENTU = 8 * 1024
TIMEOUT_POLACZENIA = 3
TIMEOUT_ODCZYTU = 8
PORTY_HTTP = {"http": 80, "https": 443}
NIEDOZWOLONE_ZNAKI_SCIEZKI = re.compile(r"[\\;%?#\x00-\x1f\x7f]")
BAZA_FIRMS = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SEGMENT_KLUCZA_FIRMS = "FIRMS_KEY"
SIECI_PRZEJSCIOWE_IPV6 = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
    ipaddress.ip_network("2001::/32"),
    ipaddress.ip_network("2002::/16"),
)


class BladPobrania(Exception):
    def __init__(self, opis, *, status_http=None):
        super().__init__(opis)
        self.status_http = status_http


class BladKonfiguracji(BladPobrania):
    """Brak konfiguracji potrzebnej do bezpiecznego wykonania pobrania."""


class BladFormatu(BladPobrania):
    """Czytelny opis oczekiwanego formatu, bez danych z odpowiedzi."""


TERMIN_CYKLU = ContextVar("termin_cyklu_teraz", default=None)
_KLUCZ_FIRMS = ContextVar("klucz_transportu_firms", default="")


class _FiltrKluczaFIRMS(logging.Filter):
    def filter(self, rekord):
        klucz = _KLUCZ_FIRMS.get()
        if klucz:
            if rekord.exc_info or rekord.stack_info:
                return False
            rekord.msg = rekord.getMessage().replace(klucz, "***")
            rekord.args = ()
        return True


class _BezTelemetriiFIRMS(NonRecordingClient):
    def is_active(self):
        # Aktywny klient bez integracji HTTP i bez wysyłki przejmuje lokalny zakres SDK.
        return True


for nazwa_logu in ("urllib3.connectionpool", "urllib3.util.retry"):
    logging.getLogger(nazwa_logu).addFilter(_FiltrKluczaFIRMS())


def _odpowiedz_firms(adres, naglowki, zrodlo_dostepu, instrukcja, opcje):
    klucz = getattr(settings, "TERAZ_FIRMS_MAP_KEY", os.environ.get("TERAZ_FIRMS_MAP_KEY", ""))
    if not isinstance(klucz, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", klucz):
        return BladKonfiguracji("FIRMS: skonfiguruj TERAZ_FIRMS_MAP_KEY.")
    token = _KLUCZ_FIRMS.set(klucz)
    try:
        with sentry_sdk.new_scope() as zakres:
            zakres.set_client(_BezTelemetriiFIRMS())
            adres_z_kluczem = adres.replace(f"/{SEGMENT_KLUCZA_FIRMS}/", f"/{klucz}/", 1)
            aktualna = require_approved_instruction(zrodlo_dostepu, instrukcja.channel, request_url=adres_z_kluczem)
            if aktualna.pk != instrukcja.pk:
                return AccessDenied("Zmieniono kartę dostępu FIRMS.")
            odpowiedz = pobierz_http(adres_z_kluczem, naglowki, **opcje)
        if klucz.encode() in odpowiedz.tresc or klucz in (odpowiedz.kodowanie or ""):
            return BladFormatu("FIRMS: odpowiedź zawiera poufne dane konfiguracji.", status_http=odpowiedz.status)
        czyste = CaseInsensitiveDict(
            (nazwa, wartosc) for nazwa, wartosc in odpowiedz.naglowki.items() if klucz not in nazwa and klucz not in wartosc
        )
        return OdpowiedzHTTP(odpowiedz.status, czyste, odpowiedz.tresc, odpowiedz.kodowanie)
    except (LimitHosta, AccessDenied, SoftTimeLimitExceeded) as exc:
        return type(exc)("Wstrzymano żądanie FIRMS.")
    except Exception as exc:
        status = getattr(exc, "status_http", None)
        status = status if type(status) is int else None
        return BladPobrania("Nie udało się pobrać odpowiedzi FIRMS.", status_http=status)
    finally:
        _KLUCZ_FIRMS.reset(token)


def pobierz_firms_http(adres, naglowki, *, zrodlo_dostepu, instrukcja, **opcje):
    if not adres.startswith(f"{BAZA_FIRMS}/{SEGMENT_KLUCZA_FIRMS}/"):
        raise BladKonfiguracji("FIRMS: nieoczekiwany adres żądania.")
    wynik = _odpowiedz_firms(adres, naglowki, zrodlo_dostepu, instrukcja, opcje)
    if isinstance(wynik, Exception):
        # Zwrócony błąd nie zachowuje stosu ani kontekstu transportu z uwierzytelnionym adresem.
        raise wynik
    return wynik


@contextmanager
def budzet_czasu(termin):
    token = TERMIN_CYKLU.set(termin)
    try:
        yield
    finally:
        TERMIN_CYKLU.reset(token)


def _pozostaly_czas():
    termin = TERMIN_CYKLU.get()
    if termin is None:
        return LIMIT_CZASU_TRESCI
    pozostalo = termin - monotonic()
    if pozostalo <= 0:
        raise BladPobrania("Przekroczono budżet czasu cyklu.")
    return pozostalo


class LimitHosta(BladPobrania):
    """Host jest jeszcze objęty odstępem między żądaniami."""


@dataclass(frozen=True)
class OdpowiedzHTTP:
    status: int
    naglowki: Mapping[str, str]
    tresc: bytes
    kodowanie: str | None


def _netloc(host):
    return f"[{host}]" if ":" in host else host


def kanoniczny_adres(adres):
    """Podaj bramce tę samą ścieżkę, która trafi do serwera."""
    try:
        if not isinstance(adres, str) or any(znak.isspace() or ord(znak) < 32 for znak in adres):
            raise ValueError
        czesci = urlsplit(adres)
        port = PORTY_HTTP.get(czesci.scheme)
        if (
            not port
            or not czesci.hostname
            or czesci.port not in (None, port)
            or czesci.username is not None
            or "%" in czesci.hostname
            or "\\" in czesci.netloc
        ):
            raise ValueError
        for segment in czesci.path.split("/"):
            odkodowany = unquote(segment, errors="strict")
            if (
                odkodowany in (".", "..")
                or "/" in odkodowany
                or NIEDOZWOLONE_ZNAKI_SCIEZKI.search(odkodowany)
            ):
                raise ValueError
        przygotowany = requests.Request("GET", adres).prepare()
        czesci = urlsplit(przygotowany.url)
        host = czesci.hostname.rstrip(".")
        if not host:
            raise ValueError
        return urlunsplit((czesci.scheme, _netloc(host), czesci.path, czesci.query, ""))
    except (ValueError, requests.exceptions.RequestException):
        raise BladPobrania("Nieprawidłowy adres HTTP źródła.") from None


def _publiczny_ip(adres):
    ip = ipaddress.ip_address(adres)
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped or ip.scope_id or ip.is_site_local or any(ip in siec for siec in SIECI_PRZEJSCIOWE_IPV6):
            return False
    return ip.is_global and not (ip.is_multicast or ip.is_reserved)


def _adres_ip(host, port):
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    try:
        adresy = [str(ip)] if ip else [
            wynik[4][0] for wynik in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ]
        if adresy and all(_publiczny_ip(adres) for adres in adresy):
            return adresy[0]
    except (OSError, ValueError):
        raise BladPobrania("Nie udało się bezpiecznie rozwiązać adresu źródła.") from None
    raise BladPobrania("Adres źródła nie jest publiczny.")


def _zarezerwuj_hosta(host, minimalny_odstep):
    try:
        wolny = caches["teraz"].add(f"pobranie:host:{host}", True, timeout=max(3, minimalny_odstep))
    except RedisError:
        raise BladPobrania("Nie udało się sprawdzić limitu zapytań do hosta.") from None
    if not wolny:
        raise LimitHosta("Host osiągnął limit częstotliwości zapytań.")


def _odczytaj_tresc(odpowiedz):
    status = odpowiedz.status_code
    kodowanie_tresci = odpowiedz.headers.get("Content-Encoding", "").strip().lower()
    if kodowanie_tresci not in ("", "identity"):
        raise BladPobrania("Źródło zwróciło nieobsługiwane kodowanie treści.", status_http=status)
    rozmiar = odpowiedz.headers.get("Content-Length", "").strip().lstrip("0")
    if rozmiar.isascii() and rozmiar.isdecimal():
        if len(rozmiar) > len(str(LIMIT_ROZMIARU)) or int(rozmiar) > LIMIT_ROZMIARU:
            raise BladPobrania("Odpowiedź źródła przekroczyła limit rozmiaru.", status_http=status)
    termin = monotonic() + min(LIMIT_CZASU_TRESCI, _pozostaly_czas())
    tresc = bytearray()
    for fragment in odpowiedz.iter_content(chunk_size=ROZMIAR_FRAGMENTU):
        if len(tresc) + len(fragment) > LIMIT_ROZMIARU:
            raise BladPobrania("Odpowiedź źródła przekroczyła limit rozmiaru.", status_http=status)
        if monotonic() > termin:
            raise BladPobrania("Przekroczono limit czasu odczytu odpowiedzi.", status_http=status)
        tresc.extend(fragment)
    return bytes(tresc)


def pobierz_http(
    adres,
    naglowki=None,
    *,
    minimalny_odstep=3,
    przed_zadaniem: Callable[[], None] | None = None,
):
    """Pobierz pojedynczą odpowiedź, bez przekierowań, proxy i ponowień."""
    czesci = urlsplit(kanoniczny_adres(adres))
    host = czesci.hostname
    ip = _adres_ip(host, PORTY_HTTP[czesci.scheme])
    adres_przypiety = urlunsplit((czesci.scheme, _netloc(ip), czesci.path, czesci.query, ""))
    naglowki_transportu = {"Host": _netloc(host), "User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    for nazwa, wartosc in (naglowki or {}).items():
        if (
            nazwa.lower() in ("if-none-match", "if-modified-since")
            and wartosc
            and "\r" not in wartosc
            and "\n" not in wartosc
        ):
            naglowki_transportu[nazwa] = wartosc.strip()
    przygotowane = requests.Request("GET", adres_przypiety, headers=naglowki_transportu).prepare()
    pozostalo = _pozostaly_czas()
    _zarezerwuj_hosta(host, minimalny_odstep)
    if przed_zadaniem is not None:
        przed_zadaniem()

    status = None
    try:
        # HTTPAdapter wysyła jedno żądanie. Session obsługuje przekierowania
        # i proxy, więc nie używamy jej w transporcie z przypiętym adresem.
        with closing(HTTPAdapter(pool_connections=1, pool_maxsize=1)) as klient:
            if czesci.scheme == "https":
                klient.init_poolmanager(1, 1, server_hostname=host, assert_hostname=host)
            # Timeout odczytu ogranicza bezczynność gniazda. Limit zadania obejmuje cały strumień.
            with klient.send(przygotowane, stream=True, timeout=(min(TIMEOUT_POLACZENIA, pozostalo), min(TIMEOUT_ODCZYTU, pozostalo)),
                             verify=True, proxies={}) as odpowiedz:
                status = odpowiedz.status_code
                wyzwanie = odpowiedz.headers.get("cf-mitigated") == "challenge"
                tresc = _odczytaj_tresc(odpowiedz) if 200 <= status < 300 and not wyzwanie else b""
                typ_tresci = Message()
                typ_tresci["Content-Type"] = odpowiedz.headers.get("Content-Type", "")
                return OdpowiedzHTTP(status, odpowiedz.headers.copy(), tresc, typ_tresci.get_content_charset())
    except requests.exceptions.RequestException:
        raise BladPobrania("Nie udało się pobrać odpowiedzi źródła.", status_http=status) from None
