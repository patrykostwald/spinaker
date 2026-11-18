# Geokoder Teraz (TERYT i PRG)

Pakiet zamienia polski tekst komunikatu na kody TERYT miejsc, a punkt (szerokość, długość)
na powiat. Nie ma modeli ani migracji; działa na plikach w `dane/` i nie używa sieci.

## Użycie

```python
from teraz.geo import geokoduj, nazwa, w_ktorym_powiecie, przecina, sprawdz_dane

sprawdz_dane()  # raz przy starcie workera: BladDanych z czytelnym opisem, gdy plik w dane/ jest uszkodzony

wynik = geokoduj("Alert RCB wysłany na terenie woj. lubelskiego i podkarpackiego.")
wynik.teryt        # ('06', '18') (krotka)
wynik.dokladnosc   # 'wojewodztwo' (gmina | powiat | wojewodztwo | kraj | brak)
wynik.pewnosc      # 0.95 (0..1, dla 'brak' 0.0)
wynik.dopasowania  # krotka miejsc: fraza, pozycje znaków, kody, tryb, uwagi, kandydaci
wynik.uwagi        # np. ('obcieto-tekst',), gdy wejście przekroczyło 20 000 znaków

nazwa("1206092", pelna=True)        # 'gmina Mogilany, powiat krakowski, woj. małopolskie'
w_ktorym_powiecie(50.0617, 19.9373)  # '1261' (Kraków)
przecina("14", (20.85, 52.10, 21.20, 52.35))  # bbox: (zachód, południe, wschód, północ)
```

`Wynik` i `Dopasowanie` są niezmienne i hashowalne (wszędzie krotki); `jako_dict()` daje listy do JSON.
`teraz.geo.ATRYBUCJA` to tekst atrybucji czytany z `dane/teryt.json`.

Kody: województwo 2 cyfry, powiat 4, gmina 7. Powiaty od numeru 61 to miasta na prawach powiatu;
nazwa miasta w tekście daje kod gminy (7 cyfr), a nazwa na liście powiatów kod powiatu (4 cyfry).

## Zasady

Nadrzędna: **lepiej `brak` albo województwo niż zgadnięta gmina lub powiat.**

- Homonimy. Nazwa wieloznaczna (np. „Czernichów”, „Dąbrowa”) jest rozstrzygana tylko województwem lub
  powiatem wymienionym w tekście. Bez kontekstu: wspólny powiat albo województwo kandydatów (pewność 0,7
  i 0,6, uwaga `homonim`), a przy kandydatach z różnych województw wynik `brak` (lista kandydatów w
  `dopasowania[].kandydaci`).
- Wyjątek: miasto wygrywa z wiejskim homonimem (pewność 0,65, uwagi `homonim`, `preferowane-miasto`),
  gdy jest jedynym takim kandydatem **w tym samym województwie**: miasto na prawach powiatu (Chełm) albo
  gmina miejska obok wiejskiej w tym samym powiecie (Mielec). Miasto z wiejskim homonimem w innym
  województwie („Leszno”, „Olsztyn”) bez kontekstu daje `brak`; zasada dotyczy też pierwszego słowa bez
  przyimka („Leszno: pożar”). Wyłącza to stała `PREFERUJ_MIASTO` w `geokoder.py`.
- Skrócone nazwy („w Grodzisku”, „w Ostrowie”, „w Bielsku”, „w Jastrzębiu”, „Mińsk”, „Tomaszów”, „Środa”,
  „Kędzierzyn”, „Starogard”): nazwa jest początkiem dłuższych nazw gmin, a sama nie jest miastem, więc wynik
  to `brak` z uwagą `skrot`. Kontekst (województwo lub powiat w tekście), który wskazuje jedną jednostkę,
  rozstrzyga (uwagi `skrot`, `kontekst`, pewność najwyżej 0,75). Pełne nazwy miast, które są początkiem innych
  nazw („Opole”, „Brzeg”, „Tarnów”, „Wadowice”), nie są skrótami.
- Rzeki i kluby. Nazwy rzek, które są też gminami (Wisła, Warta, Nysa, Pilica, Wieprz, Narew...), nie dają
  gminy po „na/nad/rzeka”, z członem „Kłodzka/Łużycka” ani w tekście o stanie wód (słowa jak „hydrologiczny”,
  „stan alarmowy”, „wezbranie”, „powódź”); „Pożar w Wiśle” poza taką okolicznością to nadal miasto Wisła.
  Nazwa klubu (w każdym przypadku: „Wisły”, „Legii”, „Lecha”, „Śląska”) blokuje i siebie, i miasto stojące
  tuż po niej („Wisła Kraków”, „Raków Częstochowa”, „Legii Warszawa”): to drużyna, nie miejsce zdarzenia.
  Miasto zdarzenia w tym samym zdaniu zostaje („Kibice Wisły Kraków zatrzymani w Płocku” daje Płock).
  Przecinek, przyimek i koniec zdania przerywają blokadę. Lista: `_RZEKI`, `_KLUBY` w `geokoder.py`.
- Krainy („w Kotlinie Kłodzkiej”, „w Górach Stołowych”, „w Puszczy Białowieskiej”): jednowyrazowa gmina, po
  której stoi przymiotnik lub rzeczownik wielką literą tworzący nazwę spoza słownika gmin, nie jest gminą.
- „Polska” i jej odmiany („w Polsce obowiązują ostrzeżenia”) nie są nazwami gmin; odrzucona nazwa bez
  kontekstu nie obniża pewności pozostałych miejsc.
- Znaki niewidoczne (U+00AD, U+200B, U+200C, U+200D, U+FEFF, np. z kopiowanego tekstu „Wroc­ławiu”) są
  usuwane przed tokenizacją; pozycje dopasowań nadal wskazują oryginalny tekst.
- Dzielnice Warszawy (wszystkie 18) nie dają gmin, także bez słowa „dzielnica” („na Bielanach” to nie gmina
  Bielany pod Sochaczewem). „Dzielnica X” daje Warszawę, „gmina Bielany” gminę.
- Adresy (ulice, numery), wsie i osiedla są pomijane.
- Wieś lub miasteczko (gmina wiejska i miejsko-wiejska) bez przyimka przed nazwą nie jest miejscem
  (np. „w legendarnym Kotle czarownic” to nie gmina Kotla).
- Jednostki służb: komenda, komisariat, prokuratura, sąd i jednostka „w X” (także małą literą: „z komisariatu
  w Pilawie”, i skróty KPP, KMP, KWP, KSP, KP, JRG, PSP, KP PSP, KW PSP) to miejsce jednostki, nie zdarzenia:
  komenda wojewódzka daje województwo, powiatowa powiat (uwaga `jednostka`, pewność najwyżej 0,8). Gdy w tekście
  jest też inne miejsce zdarzenia, miejsce jednostki zostaje w `dopasowania` z uwagą `jednostka`, ale nie trafia
  do `teryt` („Policjanci z KMP w Płocku zatrzymali w gminie Słupno” daje tylko Słupno). Gdy jednostka jest
  jedynym miejscem w tekście, daje wynik jak wyżej.
- Zasięg krajowy (`kraj`) tylko przy słowach o zasięgu: „obowiązuje w całym kraju”, „na terenie całego kraju”,
  „dla całej Polski”. „Z całej Polski”, „najwięcej w całym kraju” i „na terenie Polski” nim nie są. `kraj` nie
  zeruje innych trafień: konkretne miejsca zostają w `teryt`, a `dokladnosc` to `kraj`.
- Zasięg alertu się nie zawęża. Województwo, region i powiat wskazane wprost zostają w `teryt` także wtedy,
  gdy w treści padają dokładniejsze miejsca („Ostrzeżenie dla województwa mazowieckiego. Najsilniejsze
  opady w Warszawie.” daje `('14', '1465011')`, dokładność `wojewodztwo`). Szerszy kod znika tylko, gdy węższe
  miejsce jest jego doprecyzowaniem: lista powiatów pod województwem („woj. lubelskie - powiaty: ...”) albo
  zapis adresowy stojący obok („woj. lubelskie, powiat chełmski, gmina Chełm”, „Chełm, woj. lubelskie”,
  „Zakopane (powiat tatrzański)”). Kod szerszy poprzedzony „dla” albo stojący w nagłówku alertu (pierwsze zdanie
  lub fraza przed dwukropkiem) nigdy nie znika: „Ostrzeżenie dla województwa lubelskiego: miasto Chełm i gmina
  Rejowiec” daje `06` i obie gminy, a „Alert RCB dla powiatu tatrzańskiego, miasto Zakopane” daje `1217` i Zakopane.
  Lista powiatów z województwem w nawiasie („bieszczadzkiego (woj. podkarpackie), tatrzańskiego (woj.
  małopolskie)”) daje same powiaty, bez kodu województwa.
  Kod z miejsca jednostki lub ze spadku homonimu znika, gdy w tekście jest węższe miejsce w nim zawarte.
- Pewność wyniku to najniższa z pewności przyjętych miejsc, razy 0,9, gdy w tekście była nazwa
  wieloznaczna bez rozstrzygnięcia. Do publikacji automatycznej zalecany próg 0,8; wpisy od 0,6 do 0,8
  wymagają sprawdzenia (redakcja lub reguły klasy wpisu).
- Wejście dłuższe niż 20 000 znaków (`MAKS_DLUGOSC`) jest obcinane (uwaga `obcieto-tekst`); pozycje
  dopasowań zawsze wskazują oryginalny tekst. Wyszukiwanie jest liniowe (indeks województw po pozycji).

## Dane (`dane/`)

| Plik | Zawartość |
| --- | --- |
| `teryt.json` | 16 województw, 380 powiatów, 2479 gmin: kody, nazwy, rodzaje, punkt wewnątrz jednostki |
| `granice_powiaty.geojson` | uproszczone granice powiatów (WGS84, jedna pokrywa bez szczelin i nakładek) |
| `granice_wojewodztwa.geojson` | granice województw jako suma uproszczonych powiatów |

Źródło: GUGiK, Państwowy Rejestr Granic, jednostki administracyjne, otwarte dane, stan 10.11.2026
(opendata.geoportal.gov.pl). Atrybucja do wyświetlania: „Granice: GUGiK, Państwowy Rejestr Granic,
stan 10.11.2026” (`teraz.geo.ATRYBUCJA`, czytana z `teryt.json`). Słownik TERYT powstaje z tych samych
plików PRG (kody i nazwy jednostek), osobny plik TERC z GUS nie jest potrzebny.

`sprawdz_dane()` sprawdza spójność plików (kody, rodzaje, hierarchię, współrzędne, zgodność granic ze
słownikiem) i zgłasza `BladDanych` z nazwą pliku i opisem. Wywołaj ją raz przy starcie workera.

Odtworzenie (ręcznie, gdy GUGiK opublikuje nowy stan; wymaga `pyshp`, które nie jest zależnością działania):

```
python -m teraz.geo.zbuduj_dane KATALOG_Z_PLIKAMI_SHP --stan RRRR-MM-DD
```

Surowe pliki PRG (ok. 120 MB) nie należą do repozytorium; katalog `_zrodla/` jest ignorowany przez git.
Skrypt sam przelicza układ współrzędnych, jeśli granice nie są geograficzne (wtedy potrzebny jest `pyproj`).
Wersje narzędzi do budowy (`pyshp==3.1.9`, `pyproj==3.7.2`) są przypięte w nagłówku `zbuduj_dane.py`.

## Ograniczenia

- Tolerancja uproszczenia granic ok. 0,002° (kilkaset metrów w najgorszym razie): punkt przy samej
  granicy powiatów może trafić do sąsiada (na 30 tys. losowych punktów inny powiat niż w surowym PRG:
  0,16%, wszystkie w odległości do 90 m od granicy). Granic gmin nie przechowujemy.
- Punkt tuż poza wielokątami dostaje najbliższy powiat tylko w promieniu `TOLERANCJA_M` (250 m, liczone w
  metrach w lokalnym układzie, a nie w stopniach); dalej, np. za granicą państwa, wynik to `None`.
- Miejscowości (wsie, osiedla) nie są w PRG, więc nie są rozpoznawane; „w gminie X” działa dla każdej gminy.
- Fleksja jest regułowa (rdzenie i końcówki), bez słownika morfologicznego; rzadkie formy
  (np. dopełniacz liczby mnogiej „Tychów”) mogą nie zostać rozpoznane.
- Wielka litera jest warunkiem nazwy miasta i gminy (teksty pisane małymi literami nie dadzą trafień);
  w tekście pisanym WIELKIMI LITERAMI trafienia bez słowa „gmina/miasto/powiat” mają pewność niższą o 15%.
- Nazwa regionu (Mazowsze, Małopolska...) jest rozpoznawana także jako nazwa własna kampanii
  („Akcja Mazowsze bezpieczne”); nie rozróżniamy tego.
- W komunikacie hydrologicznym nazwa rzeki będąca też miastem („powódź w Nysie”) daje `brak` zamiast miasta
  (lepiej brak niż zgadnięta gmina).
- Wczytanie granic (shapely) trwa przy pierwszym użyciu ok. 0,5 s na proces, potem wyszukiwanie punktu
  to ułamek milisekundy; `geokoduj` nie ładuje shapely.
