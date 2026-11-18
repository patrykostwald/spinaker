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
- Sprzeczny kontekst. Gdy powiat wymieniony w tekście wyklucza wszystkich kandydatów nazwy („Pożar w Lesznie,
  powiat pruszkowski”, „Pożar w Chełmie, powiat bocheński”), wynik to sam powiat (jego kod), a gmina zostaje tylko
  w `dopasowania` (uwaga `powiat-wyklucza`). Nie przechodzimy na województwo tego powiatu i nie wybieramy miasta
  spoza niego (także miasta o tej samej nazwie co powiat, np. Leszno przy „powiecie leszczyńskim”).
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
  Nazwa klubu (w każdym przypadku: „Wisły”, „Legii”, „Lecha”, „Śląska”) blokuje miasto stojące tuż po niej
  („Wisła Kraków”, „Raków Częstochowa”, „Legii Warszawa”): to drużyna, nie miejsce zdarzenia. Bez miasta za nią
  blokuje samą siebie, gdy w tym samym zdaniu jest słowo z kręgu sportu (kibic, klub, mecz, piłkarz, zawodnik,
  trener, drużyna, stadion, derby, liga, puchar, kolejka: „Kibice Wisły zatrzymani w Płocku” daje tylko Płock);
  bez takiego słowa zostaje gminą („Pożar w Wiśle”, gmina Wisła istnieje). Miasto zdarzenia w tym samym zdaniu
  zostaje. Przecinek, przyimek i koniec zdania przerywają blokadę miasta. Lista: `_RZEKI`, `_KLUBY`, `_SPORT_*`
  w `geokoder.py`.
- Nazwy gmin w liczbie mnogiej („Zawady”, „Kozy”, „Mrozy”, „Marki”, „Brody”...: jednowyrazowe na „-y/-i”)
  dopasowują się tylko do form liczby mnogiej („w Zawadach”, „Kozach”, „z Zawad”). Miejscownik liczby pojedynczej
  („Utonięcie w Zawadzie”, „w Kozie”, „w Mrozie”) nie daje tych gmin.
- Imię i nazwisko. Nazwa gminy bez przyimka, tuż po imieniu („Andrzej Kalisz”, „Tomasz Opole”, „Maciej Brzeg”), nie
  jest miejscem; podobnie nazwa będąca imieniem, po której stoi nazwisko („Jarosław Kaczyński”). Imiona: ręczna lista
  kilkuset najpopularniejszych imion z odmianą regułową (`imiona.py`). Z przyimkiem („w Kaliszu”) nic się nie zmienia.
- Formy przymiotnikowe nazw na „-o”: „Główna/Główny/Główne/Główną/Głównej/Głównych” (np. „Komenda Główna Policji”) nie
  są miastem Głowno („ó” w tekście i „o” w nazwie rozróżnia regułę; „y” i „e” nie są rzeczownikowymi formami nazw
  na „-o”). Nie rozstrzygamy par, w których forma jest identyczna także z „ł”, np. „Piłą” (narzędnik miasta Piła i
  rzeczownik „piła”); takie nazwy są dodatkowo na liście `_NIE_NA_POCZATKU_ZDANIA`.
- Nazwy, które są też zwykłymi słowami: `_TYLKO_ZNACZNIK` (Nowe, Nowa, Dobra, Dobre, Czarna, Czarne, Biała, Stare)
  wymaga słowa „gmina/miasto/powiat” („Nowy Jork” nie jest gminą Nowe); `_NIE_NA_POCZATKU_ZDANIA` (Koło, Kowal,
  Gniew, Piła, Marki, Klucze, Płoty, Mikołajki, Kozy, Brody, Kamień, Pokój) wymaga wielkiej litery w środku
  zdania („Piła: pożar hali” i „Marki: wypadek na S8” dają `brak`, „pożar w Pile” gminę).
- Skróty członów z kropką: „Ostrowie Wlkp.”, „Mińsku Maz.”, „Bielsku Podl.”, „Janowie Lub.”, „Wodzisławiu Śl.” oraz
  województw: „woj. małop.”, „woj. mazow.”, „woj. wlkp.”, „woj. podkarp.”, „woj. podl.” (lista w `fleksja.py`).
  „lub.” skraca tylko człon gminy; przy województwie jest wieloznaczne (lubelskie, lubuskie), więc nie jest rozpoznane.
- Krainy („w Kotlinie Kłodzkiej”, „w Górach Stołowych”, „w Puszczy Białowieskiej”): jednowyrazowa gmina, po
  której stoi przymiotnik lub rzeczownik wielką literą tworzący nazwę spoza słownika gmin, nie jest gminą.
- „Polska” i jej odmiany („w Polsce obowiązują ostrzeżenia”) nie są nazwami gmin; odrzucona nazwa bez
  kontekstu nie obniża pewności pozostałych miejsc.
- Wejście jest normalizowane przed tokenizacją: tekst w postaci rozłożonej (NFD, litera i osobny akcent, np. z
  komputerów Apple) jest składany do NFC, a znaki niewidoczne (U+00AD, U+200B, U+200C, U+200D, U+FEFF, np. z
  kopiowanego tekstu „Wroc­ławiu”) są usuwane. Pozycje dopasowań nadal wskazują oryginalny tekst (złożony znak
  wskazuje cały ciąg, razem z akcentem). Typ wejścia: `str` albo `None`; inny typ (liczba, `bytes`, lista) daje
  `brak` z uwagą `zly-typ-wejscia`, a nie wyjątek.
- Dzielnice Warszawy (wszystkie 18) nie dają gmin, także bez słowa „dzielnica” („na Bielanach” to nie gmina
  Bielany pod Sochaczewem). „Dzielnica X” daje Warszawę, „gmina Bielany” gminę.
- Adresy (ulice, numery), wsie i osiedla są pomijane.
- Wieś lub miasteczko (gmina wiejska i miejsko-wiejska) bez przyimka przed nazwą nie jest miejscem
  (np. „w legendarnym Kotle czarownic” to nie gmina Kotla).
- Jednostki służb: komenda, komisariat, prokuratura, sąd i jednostka „w X” (także małą literą: „z komisariatu
  w Pilawie”, i skróty KPP, KMP, KWP, KSP, KP, JRG, PSP, KP PSP, KW PSP, KM PSP) to miejsce jednostki, nie
  zdarzenia: komenda wojewódzka daje województwo, powiatowa powiat (uwaga `jednostka`, pewność najwyżej 0,8). Gdy
  w tekście jest też inne miejsce zdarzenia, miejsce jednostki zostaje w `dopasowania` z uwagami `jednostka` i
  `poza-wynikiem`, ale nie trafia do `teryt` („Policjanci z KMP w Płocku zatrzymali w gminie Słupno” daje tylko
  Słupno). Gdy jednostka jest jedynym miejscem w tekście, daje wynik jak wyżej.
- Miejsce pochodzenia: dopełniacz po „mieszkaniec/mieszkańca/mieszkańców/mieszkanka/mieszkanki”, „kierowca”,
  „obywatel”, „rodak”, „pochodzący z” oraz po „z/ze/od” („mieszkańca Lublina”, „mężczyzny z Rzeszowa”) wskazuje,
  skąd ktoś pochodzi. Gdy w tym samym zdaniu jest miejsce jednostki lub zdarzenia, miejsce pochodzenia zostaje w
  `dopasowania` z uwagami `pochodzenie` i `poza-wynikiem`, a nie w `teryt` („Sąd Rejonowy w Chełmie skazał
  mieszkańca Lublina” daje Chełm; jednostka zostaje jako miejsce, gdy jest jedyna). Pochodzenie zostaje, gdy jest
  jedynym miejscem, po „dla” („Komunikat dla mieszkańców Lublina”) i w trasie „z A do B”; narzędnik („z Tuchowem”,
  „z Warszawą”) pochodzenia nie wskazuje.
- Zasięg krajowy (`kraj`) tylko przy słowach o zasięgu: „obowiązuje w całym kraju”, „na terenie całego kraju”,
  „dla całej Polski”. „Z całej Polski”, „najwięcej w całym kraju” i „na terenie Polski” nim nie są. `kraj` nie
  zeruje innych trafień: konkretne miejsca zostają w `teryt`, a `dokladnosc` to `kraj`.
- Zasięg alertu się nie zawęża. Województwo, region i powiat wskazane wprost zostają w `teryt` także wtedy,
  gdy w treści padają dokładniejsze miejsca („Ostrzeżenie dla województwa mazowieckiego. Najsilniejsze
  opady w Warszawie.” daje `('14', '1465011')`, dokładność `wojewodztwo`). Szerszy kod znika tylko przy czystej
  hierarchii jednego miejsca: (1) „w” przed każdym poziomem, rozdzielone samym przecinkiem („w woj. lubelskim,
  w powiecie chełmskim, w gminie Rejowiec” daje tylko gminę); (2) dopisek za nazwą („Chełm, woj. lubelskie”,
  „Zakopane (powiat tatrzański)”, „bieszczadzkiego (woj. podkarpackie), tatrzańskiego (woj. małopolskie)”, „A, B
  (woj. X)”); (3) lista powiatów pod województwem bez „dla” („części województwa: lubelskiego - powiaty: A, B” daje
  same powiaty). Kod szerszy poprzedzony „dla” nigdy nie znika, także nad listą powiatów („Ostrzeżenie dla woj.
  lubelskiego - powiaty: chełmski, włodawski” daje `06` i oba powiaty). Kod szerszy w nagłówku alertu (pierwsze
  zdanie, fraza przed dwukropkiem, tekst po prefiksie „Alert RCB”, „Ostrzeżenie”, „Komunikat”, z dwukropkiem lub
  bez) też nie znika, gdy węższe miejsce nie jest czystą hierarchią: szerszy kod bez własnego „w” albo oddzielony
  dwukropkiem lub myślnikiem to nagłówek lub wyliczenie zasięgu. „Alert RCB woj. małopolskie: w powiecie tatrzańskim”
  daje `12` i `1217`; „Alert RCB: powiat tatrzański, w gminie Zakopane” daje `1217` i Zakopane; „Ostrzeżenie dla
  województwa lubelskiego: miasto Chełm i gmina Rejowiec” daje `06` i obie gminy; „woj. mazowieckie, miasto
  Warszawa” (bez „w”) daje `14` i Warszawę.
  Kod z miejsca jednostki lub ze spadku homonimu znika, gdy w tekście jest węższe miejsce w nim zawarte.
- Lista powiatów może być rozdzielona przecinkiem, „i/oraz” albo średnikiem („powiaty: tatrzański; nowotarski”):
  każdy daje kod powiatu (4 cyfry), nie całe województwo.
- Pewność wyniku to najniższa z pewności przyjętych miejsc. Mnożnik 0,9 dostaje tylko wynik, w którym była
  nierozstrzygnięta nazwa ze znacznikiem („gmina Czernichów” bez kontekstu). Nazwa samodzielna odrzucona bez
  kontekstu („w Tomaszowie”, skrót lub homonim) pewności pozostałych miejsc nie obniża. Do publikacji automatycznej
  zalecany próg 0,8; wpisy od 0,6 do 0,8 wymagają sprawdzenia (redakcja lub reguły klasy wpisu).
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
słownikiem) i zgłasza `BladDanych` z nazwą pliku i opisem. Każdy błąd w treści plików (także zły typ wartości,
np. niehashowalny kod, czy błąd shapely przy wczytaniu granic) jest `BladDanych`, nie surowy `TypeError`.
Wywołaj ją raz przy starcie workera.

Odtworzenie (ręcznie, gdy GUGiK opublikuje nowy stan; wymaga `pyshp`, które nie jest zależnością działania).
Flaga `--stan` jest wymagana (data trafia do atrybucji, więc nie ma wartości domyślnej):

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
- Gmina miejsko-wiejska bez przyimka tuż przed nazwą nie jest miejscem, więc w liście po jednym „w”
  („w Ostrowie, Pleszewie i Kaliszu”) Pleszew znika (wynik `brak`, nie błędna gmina). Imię na początku zdania bez
  nazwiska („Jarosław potwierdził”) nadal może być miastem Jarosław.
- Miejsce pochodzenia po „z/ze/od” w dopełniaczu nie trafia do wyniku, gdy w zdaniu jest miejsce zdarzenia lub
  jednostki; trasa „z A do B” zostaje w całości, a „Policjanci z Koła zatrzymali w Chełmie” daje tylko Chełm.
- Wczytanie granic (shapely) trwa przy pierwszym użyciu ok. 0,5 s na proces, potem wyszukiwanie punktu
  to ułamek milisekundy; `geokoduj` nie ładuje shapely.
