import csv
import io
import math
import re
from datetime import timezone

from django.conf import settings

from ..models import Klasa, Zdarzenie
from ..zbieranie import Adapter, BladKonfiguracji, BladFormatu
from ..transport import BAZA_FIRMS as BAZA, SEGMENT_KLUCZA_FIRMS, pobierz_firms_http
from .wspolne import POLSKA, data_iso, odczytaj, punkt, w_obszarze, wpis

MAPA = "https://firms.modaps.eosdis.nasa.gov/map/"
SENSORY = ("VIIRS_NOAA20_NRT", "MODIS_NRT")
KOLUMNY = {"latitude", "longitude", "acq_date", "acq_time", "satellite", "instrument"}


def odleglosc_km(lat, lon, lat2, lon2):
    a = (math.sin(math.radians(lat2 - lat) / 2) ** 2
         + math.cos(math.radians(lat)) * math.cos(math.radians(lat2)) * math.sin(math.radians(lon2 - lon) / 2) ** 2)
    return 12742 * math.asin(math.sqrt(min(1, a)))


class AdapterFIRMS(Adapter):
    limit_zadan = len(SENSORY)
    wersja_parsera = "3"
    pola_stanu_bledu = ("ostrzezenie",)

    def przeprowadz(self, cykl):
        obiekty = self._obiekty()
        konfiguracja = self.odcisk_adresu(repr(obiekty))
        konfiguracje = cykl.stan.setdefault("konfiguracje_sensorow", {})
        if obiekty:
            cykl.stan.pop("ostrzezenie", None)
        else:
            cykl.stan["ostrzezenie"] = "brak listy obiektów wrażliwych"
        obszar = ",".join(map(str, POLSKA))
        for sensor in SENSORY:
            zmiana = konfiguracja != konfiguracje.get(sensor)

            def zapamietaj_konfiguracje():
                konfiguracje[sensor] = konfiguracja

            cykl.wykonaj(f"{BAZA}/{SEGMENT_KLUCZA_FIRMS}/{sensor}/{obszar}/1",
                         po_odczycie=zapamietaj_konfiguracje, zrzut=False, warunkowo=not zmiana, zawsze_parsuj=zmiana)

    def odcisk_adresu(self, adres):
        return super().odcisk_adresu(adres.replace(f"/{SEGMENT_KLUCZA_FIRMS}/", "/***/"))

    def _transport(self, adres, naglowki, *, instrukcja, **opcje):
        return pobierz_firms_http(adres, naglowki, zrodlo_dostepu=self.zrodlo.zrodlo_dostepu,
                                 instrukcja=instrukcja, **opcje)

    def _obiekty(self):
        wartosci = getattr(settings, "TERAZ_FIRMS_OBIEKTY_WRAZLIWE", ())
        try:
            return [punkt(lat, lon) for lat, lon in wartosci]
        except (TypeError, ValueError) as exc:
            raise BladKonfiguracji("FIRMS: nieprawidłowa lista obiektów wrażliwych.") from exc

    def parsuj(self, odpowiedz):
        obiekty = self._obiekty()
        try:
            csv_dane = csv.DictReader(io.StringIO(odczytaj(odpowiedz)), strict=True)
            if not KOLUMNY.issubset(csv_dane.fieldnames or ()):
                raise ValueError
            wynik = []
            for dane in csv_dane:
                if None in dane or any(dane[k] in (None, "") for k in KOLUMNY):
                    raise ValueError
                polozenie = punkt(dane["latitude"], dane["longitude"])
                if not w_obszarze(polozenie, POLSKA):
                    continue
                godzina = dane["acq_time"].zfill(4)
                if not re.fullmatch(r"\d{4}", godzina):
                    raise ValueError
                czas = data_iso(f'{dane["acq_date"]}T{godzina[:2]}:{godzina[2:]}', timezone.utc)
                sensor = dane["instrument"]
                if sensor not in ("VIIRS", "MODIS") or not re.fullmatch(r"[A-Za-z0-9-]{1,25}", dane["satellite"]):
                    raise ValueError
                lat, lon = polozenie["szerokosc"], polozenie["dlugosc"]
                ident = f'{dane["satellite"]}:{sensor}:{czas.isoformat()}:{lat}:{lon}'
                rekord = wpis(ident, f"Anomalia termiczna ({sensor}, satelita)", MAPA, czas,
                              zdarzenie_id=ident, status_zdarzenia=Zdarzenie.Status.ZGLOSZONE, **polozenie)
                if not obiekty:
                    rekord["klasa"] = Klasa.NIEZNANA
                elif any(odleglosc_km(lat, lon, cel["szerokosc"], cel["dlugosc"]) <= 2 for cel in obiekty):
                    rekord["klasa"] = Klasa.INFRASTRUKTURA
                wynik.append(rekord)
        except (ValueError, TypeError, csv.Error) as exc:
            raise BladFormatu("FIRMS: nieoczekiwany format danych CSV.") from exc
        return wynik
