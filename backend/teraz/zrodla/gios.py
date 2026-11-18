from datetime import timedelta
from urllib.parse import urlencode

from ..zbieranie import Adapter, BladFormatu
from .wspolne import czysty_tekst, data_iso, json_dane, punkt, wpis

BAZA = "https://api.gios.gov.pl/pjp-api/v1/rest"
URL_STACJI = BAZA + "/station/findAll"
URL_INDEKSU = BAZA + "/aqindex/getIndex"
MAPA = "https://powietrze.gios.gov.pl/pjp/current"
KATEGORIE = {4: "zły", 5: "bardzo zły"}
KLUCZ_LISTY_STACJI = "Lista stacji pomiarowych"



class AdapterGIOS(Adapter):
    limit_zadan = 10
    wersja_parsera = "3"

    def parsuj_stacje(self, odpowiedz):
        try:
            dane = json_dane(odpowiedz)
            stacje = {}
            for pole in dane[KLUCZ_LISTY_STACJI]:
                ident = str(int(pole["Identyfikator stacji"]))
                nazwa = czysty_tekst(pole["Nazwa stacji"], 200)
                polozenie = punkt(pole["WGS84 φ N"], pole["WGS84 λ E"])
                stacje[ident] = {"nazwa": nazwa, "polozenie": polozenie}
            if not stacje:
                raise ValueError
            nastepna = bool(dane.get("links", {}).get("next"))
            return stacje, nastepna
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise BladFormatu("GIOŚ: nieoczekiwana lista stacji API v1.") from exc

    def parsuj_indeksy(self, odpowiedz):
        try:
            dane = json_dane(odpowiedz)["AqIndex"]
            ident = str(int(dane["Identyfikator stacji pomiarowej"]))
            kod = dane["Wartość indeksu"]
            kod = -1 if kod is None else int(kod)
            if kod not in range(-1, 6):
                raise ValueError
            czas = dane["Data wykonania obliczeń indeksu"]
            if czas is None and kod != -1:
                raise ValueError
            return ident, data_iso(czas) if czas is not None else None, kod
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise BladFormatu("GIOŚ: nieoczekiwany format indeksu jakości powietrza API v1.") from exc

    def parsuj(self, odpowiedz):
        if odpowiedz.status == 204 and not odpowiedz.tresc:
            return []
        ident, stacja, zapisane = self.stacja
        ident_z_odpowiedzi, czas, kod = self.parsuj_indeksy(odpowiedz)
        if ident_z_odpowiedzi != ident:
            raise BladFormatu("GIOŚ: indeks pochodzi z innej stacji.")
        if czas is None:
            return []
        poprzednia = zapisane.get(ident)
        if poprzednia and czas < data_iso(poprzednia[0]):
            return []
        zapisane[ident] = [czas.isoformat(), kod]
        nazwa = stacja["nazwa"]
        opis = KATEGORIE.get(kod, str(kod))
        return [wpis(f"indeks:{ident}", f"Indeks jakości powietrza: {opis} ({nazwa})",
                     MAPA, czas, miejsce=nazwa, pomiar_aktywny=kod in KATEGORIE, **stacja["polozenie"])]

    def przeprowadz(self, cykl):
        stan = cykl.stan
        if not stan.get("kolejka"):
            numer = stan.get("numer_strony", 0)
            strony = stan.setdefault("strony", {})
            klucz = str(numer)

            def zapamietaj_liste(odpowiedz):
                stacje, nastepna = self.parsuj_stacje(odpowiedz)
                strony[klucz] = {"stacje": stacje, "nastepna": nastepna}
                return []

            def rozpocznij_obchod():
                if numer == 0:
                    stan["poczatek"] = cykl.start.isoformat()
                cykl.kontynuacja_at = cykl.start + timedelta(minutes=1)
                if strony[klucz]["nastepna"]:
                    stan["numer_strony"] = numer + 1
                    return
                stan.pop("numer_strony", None)
                stan["stacje"] = {
                    ident: stacja
                    for nr in range(numer + 1)
                    for ident, stacja in strony[str(nr)]["stacje"].items()
                }
                stan["kolejka"] = list(stan["stacje"])
                stan["indeksy"] = {ident: indeks for ident, indeks in stan.get("indeksy", {}).items()
                                   if ident in stan["stacje"]}
                # Zmniejszenie katalogu może pozostawić walidatory ostatnich stron.
                for nr in list(strony):
                    if int(nr) > numer:
                        del strony[nr]

            parametr = urlencode({"page": numer, "size": 500})
            cykl.wykonaj(f"{self.zrodlo.adres}?{parametr}", parser=zapamietaj_liste, po_odczycie=rozpocznij_obchod,
                         zrzut=False, zawsze_parsuj=True, warunkowo=klucz in strony)
            if "numer_strony" in stan:
                return

        for ident in stan["kolejka"][:self.limit_zadan - cykl.zadania]:
            self.stacja = (ident, stan["stacje"][ident], stan.setdefault("indeksy", {}))

            def zakoncz_stacje():
                stan["kolejka"].pop(0)
                if stan["kolejka"]:
                    cykl.kontynuacja_at = cykl.start + timedelta(minutes=1)
                else:
                    nastepny = data_iso(stan["poczatek"]) + timedelta(seconds=self.zrodlo.czestotliwosc_s)
                    cykl.kontynuacja_at = max(nastepny, cykl.start + timedelta(minutes=1))

            cykl.wykonaj_element_kolejki(f"{URL_INDEKSU}/{ident}", przesun=zakoncz_stacje, zrzut=False)
