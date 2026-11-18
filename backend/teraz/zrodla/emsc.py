import socket
from datetime import timezone
from urllib.parse import quote, urlsplit

from scraper.access_gate import AccessDenied
from scraper.utils import reserve_daily_fetch_budget

from ..models import Zrodlo
from ..transport import BladPobrania, OdpowiedzHTTP, USER_AGENT, _adres_ip, _zarezerwuj_hosta
from ..zbieranie import Adapter, BladFormatu, WYZWANIE_BOTA, hash_tresci

from .wspolne import czysty_tekst, data_iso, identyfikator, json_dane, punkt, w_obszarze, wpis

URL_EMSC = "wss://www.seismicportal.eu/standing_order/websocket"
OKOLICE_POLSKI = (12, 47, 26, 56)
LIMIT_KOMUNIKATU = 65536


class AdapterEMSC(Adapter):
    def karta_dostepu(self, adres):
        if adres != URL_EMSC or self.zrodlo.sposob_dostepu != Zrodlo.SposobDostepu.WEBSOCKET:
            raise AccessDenied("nieobslugiwany_adres_websocket")
        karta = super().karta_dostepu(adres)
        czesci = urlsplit(karta.endpoint)
        if (czesci.scheme != "wss" or czesci.netloc not in ("www.seismicportal.eu", "www.seismicportal.eu:443")
                or czesci.query or czesci.fragment):
            raise AccessDenied("nieobslugiwany_adres_karty_websocket")
        return karta

    def polacz(self, klient):
        adres = self.zrodlo.adres
        karta = self.karta_dostepu(adres)
        host = urlsplit(adres).hostname
        _zarezerwuj_hosta(host, karta.minimum_interval_seconds)
        if not reserve_daily_fetch_budget(karta):
            raise AccessDenied("limit_dzienny_instrukcji")
        ip = _adres_ip(host, 443)
        sock = socket.create_connection((ip, 443), timeout=5)
        try:
            return klient(adres, sock=sock, server_hostname=host, compression=None, proxy=None,
                          max_size=LIMIT_KOMUNIKATU, max_queue=4, user_agent_header=USER_AGENT,
                          open_timeout=5, ping_interval=15, ping_timeout=15, close_timeout=3)
        except BaseException:
            sock.close()
            raise

    def parsuj(self, odpowiedz):
        try:
            komunikat = json_dane(odpowiedz)
            if komunikat["action"] not in {"create", "update", "delete"}:
                raise ValueError
            obiekt = komunikat["data"]
            if komunikat["action"] == "delete":
                return []
            if obiekt["type"] != "Feature" or obiekt["geometry"]["type"] != "Point":
                raise ValueError
            lon, lat, *_ = obiekt["geometry"]["coordinates"]
            polozenie = punkt(lat, lon)
            dane = obiekt["properties"]
            ident = identyfikator(dane.get("unid") or obiekt["id"])
            data = data_iso(dane["time"], timezone.utc)
            region = czysty_tekst(dane["flynn_region"], 200)
            mag = float(dane["mag"])
            if not -5 <= mag <= 15:
                raise ValueError
            if not w_obszarze(polozenie, OKOLICE_POLSKI):
                return []
            return [wpis(ident, f"Wstrząs M {mag:g}: {region}",
                         f"https://www.seismicportal.eu/eventdetails.html?unid={quote(ident, safe='')}",
                         data, miejsce=region, **polozenie)]
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise BladFormatu("EMSC: nieoczekiwany format komunikatu WebSocket.") from exc

    def przyjmij(self, wiadomosc):
        tresc = wiadomosc.encode() if isinstance(wiadomosc, str) else wiadomosc
        if WYZWANIE_BOTA.search(tresc[:LIMIT_KOMUNIKATU]):
            raise BladPobrania("Wyzwanie bota", status_http=403)
        if len(tresc) > LIMIT_KOMUNIKATU:
            raise BladFormatu("EMSC: przekroczony limit rozmiaru komunikatu.")
        karta = self.karta_dostepu(self.zrodlo.adres)
        odpowiedz = OdpowiedzHTTP(None, {}, tresc, "utf-8")
        wpisy = self._parsuj(self.parsuj, odpowiedz)
        if not wpisy:
            return None
        cykl, _ = self._otworz_cykl()
        if cykl is None:
            raise AccessDenied("zrodlo_wylaczone")
        cykl.odcisk = self.odcisk_adresu(self.zrodlo.adres)
        poprzednie = self._ostatnie_udane(cykl.odcisk)
        return self._zapisz(cykl, odpowiedz, karta.allowed_scope, hash_tresci(tresc), wpisy, poprzednie, zrzut=False)

    def zapisz_blad_strumienia(self, exc):
        cykl, _ = self._otworz_cykl()
        if cykl is None:
            return
        cykl.odcisk = self.odcisk_adresu(self.zrodlo.adres)
        cykl.blokada = getattr(exc, "status_http", None) == 403
        self._zapisz_blad(cykl, exc)
