import re

from ..models import Wpis, Zdarzenie
from ..zbieranie import Adapter, BladFormatu
from .wspolne import czysty_tekst, data_iso, identyfikator, json_dane, kody_powiatow, wpis

URL_METEO = "https://danepubliczne.imgw.pl/api/data/warningsmeteo"
LINK_MAPY = "https://meteo.imgw.pl/"
ODWOLANIE = re.compile(r"odwołan|anulowan|cancel", re.I)


def rekordy(odpowiedz):
    dane = json_dane(odpowiedz)
    if not isinstance(dane, list):
        raise ValueError
    return dane


def parsuj_ostrzezenia(odpowiedz, *, hydro=False):
    rodzaj = "hydrologiczne" if hydro else "meteorologiczne"
    wynik = []
    if odpowiedz.status == 204 and not odpowiedz.tresc:
        return wynik
    try:
        for dane in rekordy(odpowiedz):
            nazwa = czysty_tekst(dane.get("nazwa_zjawiska") or dane.get("nazwa_zdarzenia") or dane.get("nazwa") or dane["zjawisko"])
            opublikowano = data_iso(dane.get("opublikowano") or dane.get("data_wydania") or dane["obowiazuje_od"])
            # IMGW podaje numer ostrzeżenia i w części odpowiedzi osobny identyfikator wersji.
            numer = dane.get("numer_ostrzezenia") or dane.get("numer") or dane.get("id_ostrzezenia") or dane.get("id")
            organ = czysty_tekst(dane.get("biuro", "") or "", 120)
            teryt = kody_powiatow(dane.get("teryt") or dane.get("kody_teryt"))
            obszar = dane.get("obszar") or dane.get("obszary") or ""
            if isinstance(obszar, list):
                obszar = ", ".join(str(pole.get("nazwa", "")) if isinstance(pole, dict) else str(pole) for pole in obszar)
            miejsce = czysty_tekst(obszar, 2000)
            if numer is None:
                od = dane.get("obowiazuje_od")
                if not od or not (teryt or miejsce):
                    raise ValueError
                numer = identyfikator(f"{nazwa}:{od}:{','.join(teryt) or miejsce}")
            grupa = f"{organ}:{identyfikator(numer)}"
            tresc = czysty_tekst(dane.get("tresc") or dane.get("przebieg") or "")
            zdarzenie = Zdarzenie.Status.ODWOLANE if dane.get("odwolane") is True or ODWOLANIE.search(
                str(dane.get("status") or dane.get("typ_komunikatu") or "")
            ) else Zdarzenie.Status.KOMUNIKAT_OFICJALNY
            stopien = dane.get("stopien")
            tytul = f"Ostrzeżenie {rodzaj} IMGW: {nazwa}"
            if stopien is not None and str(stopien).isdigit():
                tytul += f" (stopień {stopien})"
            wynik.append(wpis(
                grupa, tytul, LINK_MAPY, opublikowano, tresc=tresc, zdarzenie_id=grupa, status_zdarzenia=zdarzenie,
                dokladna_godzina_publikacji=bool(dane.get("opublikowano") or dane.get("data_wydania")),
                czas_zrodlowy_at=data_iso(dane["obowiazuje_od"]) if dane.get("obowiazuje_od") else None,
                miejsce=miejsce, teryt=teryt, dokladnosc=Wpis.Dokladnosc.POWIAT if teryt else Wpis.Dokladnosc.BRAK,
                pewnosc_lokalizacji=1 if teryt else 0,
            ))
    except (ValueError, KeyError, AttributeError, TypeError) as exc:
        raise BladFormatu(f"IMGW: nieoczekiwany format ostrzeżeń ({rodzaj}).") from exc
    return wynik


class AdapterIMGWMeteo(Adapter):
    def parsuj(self, odpowiedz):
        return parsuj_ostrzezenia(odpowiedz)
