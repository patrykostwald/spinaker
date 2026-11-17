"""Transport HTTP dla adresów zatwierdzonych w bramce dostępu."""

import ipaddress
import re
import socket
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
from email.message import Message
from time import monotonic
from urllib.parse import unquote, urlsplit, urlunsplit

import requests
from django.core.cache import caches
from redis.exceptions import RedisError
from requests.adapters import HTTPAdapter

USER_AGENT = "przeszlosc.today-teraz/1.0 (+https://przeszlosc.today; kontakt@iapply.pl)"
LIMIT_ROZMIARU = 5 * 1024 * 1024
LIMIT_CZASU_TRESCI = 25
ROZMIAR_FRAGMENTU = 8 * 1024
TIMEOUT_POLACZENIA = 3
TIMEOUT_ODCZYTU = 8
PORTY_HTTP = {"http": 80, "https": 443}
NIEDOZWOLONE_ZNAKI_SCIEZKI = re.compile(r"[\\;%?#\x00-\x1f\x7f]")
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
    termin = monotonic() + LIMIT_CZASU_TRESCI
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
            with klient.send(przygotowane, stream=True, timeout=(TIMEOUT_POLACZENIA, TIMEOUT_ODCZYTU),
                             verify=True, proxies={}) as odpowiedz:
                status = odpowiedz.status_code
                tresc = _odczytaj_tresc(odpowiedz) if 200 <= status < 300 else b""
                typ_tresci = Message()
                typ_tresci["Content-Type"] = odpowiedz.headers.get("Content-Type", "")
                return OdpowiedzHTTP(status, odpowiedz.headers.copy(), tresc, typ_tresci.get_content_charset())
    except requests.exceptions.RequestException:
        raise BladPobrania("Nie udało się pobrać odpowiedzi źródła.", status_http=status) from None
