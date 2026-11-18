from ..zbieranie import Adapter, BladFormatu
from .imgw_meteo import LINK_MAPY, parsuj_ostrzezenia, rekordy
from .wspolne import czysty_tekst, data_iso, punkt, wpis

URL_OSTRZEZENIA = "https://danepubliczne.imgw.pl/api/data/warningshydro"
URL_STANY = "https://danepubliczne.imgw.pl/api/data/hydro/"


class AdapterIMGWHydro(Adapter):
    limit_zadan = 2

    def parsuj(self, odpowiedz):
        return parsuj_ostrzezenia(odpowiedz, hydro=True)

    def przeprowadz(self, cykl):
        cykl.wykonaj(self.zrodlo.adres)
        cykl.wykonaj(URL_STANY, parser=self.parsuj_stany, zrzut=False)

    def parsuj_stany(self, odpowiedz):
        wynik = []
        try:
            dane_stacji = rekordy(odpowiedz)
            if not dane_stacji:
                raise ValueError
            for dane in dane_stacji:
                stan = dane["stan_wody"]
                if stan in ("", None):
                    continue
                int(stan)
                stacja = czysty_tekst(dane["stacja"], 200)
                miejsce = czysty_tekst(dane["rzeka"] or "", 200)
                lat, lon = dane.get("lat"), dane.get("lon")
                polozenie = punkt(lat, lon) if lat not in ("", None) and lon not in ("", None) else {}
                wynik.append(wpis(
                    f'stan:{dane["id_stacji"]}', f"Stan wody IMGW: {stacja} ({stan} cm)", LINK_MAPY,
                    data_iso(dane["stan_wody_data_pomiaru"]), miejsce=", ".join(filter(None, (stacja, miejsce))),
                    **polozenie,
                ))
        except (ValueError, KeyError, AttributeError, TypeError) as exc:
            raise BladFormatu("IMGW: nieoczekiwany format stanów wód.") from exc
        return wynik
