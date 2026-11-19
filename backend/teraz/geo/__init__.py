"""Geokoder Teraz: TERYT i granice PRG.

Publiczne API:

* `geokoduj(tekst) -> Wynik`: kody TERYT miejsc wymienionych w polskim tekście
  (dokładność gmina/powiat/wojewodztwo/kraj/brak i pewność 0..1);
* `nazwa(kod)`, `wojewodztwo_powiatu(kod)`, `powiat_gminy(kod)`, `jednostka(kod)`: słownik TERYT;
* `w_ktorym_powiecie(lat, lon)`, `w_ktorym_wojewodztwie(lat, lon)`, `przecina(teryt, bbox)`:
  granice powiatów i województw (shapely, wczytywane przy pierwszym użyciu);
* `sprawdz_dane()`: sprawdzenie plików danych przy starcie workera (`BladDanych` przy uszkodzeniu);
* `ATRYBUCJA`: tekst atrybucji danych, czytany z `dane/teryt.json`.

Dane: GUGiK, Państwowy Rejestr Granic (odtwarzane skryptem `zbuduj_dane.py`).
"""

from .geokoder import Dopasowanie, Wynik, geokoduj
from .granice import przecina, w_ktorym_powiecie, w_ktorym_wojewodztwie
from .slownik import BladDanych, Jednostka, jednostka, nazwa, powiat_gminy, sprawdz_dane, wojewodztwo_powiatu

# Uwaga: nie eksportujemy funkcji `slownik`, bo przesłoniłaby podmoduł `teraz.geo.slownik`.
__all__ = [
    "ATRYBUCJA", "BladDanych", "Dopasowanie", "Jednostka", "Wynik", "geokoduj", "jednostka", "nazwa", "powiat_gminy",
    "przecina", "sprawdz_dane", "w_ktorym_powiecie", "w_ktorym_wojewodztwie", "wojewodztwo_powiatu",
]


def __getattr__(nazwa_atrybutu: str):
    # atrybucja pochodzi z danych (nie jest wpisana na sztywno), więc czytamy ją dopiero przy użyciu
    if nazwa_atrybutu == "ATRYBUCJA":
        from .slownik import slownik

        return slownik().atrybucja
    raise AttributeError(f"module {__name__!r} has no attribute {nazwa_atrybutu!r}")
