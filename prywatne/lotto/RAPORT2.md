# Czy da się zwiększyć szansę w Lotto? Etap 2: pięć prób znalezienia przewagi (22.10.2026)

Dane: 7420 prawdziwych losowań z lat 1957-2026 (`dane/lotto.csv`). Fakty do sprawdzenia oznaczone [DP].
Liczby poniżej generuje `python analiza2.py` (ok. 1 minuty); ten wstęp pisałem ręcznie na podstawie tych liczb.

## Werdykt prostym językiem
**Nie znalazłem żadnego sposobu na zwiększenie szansy trafienia.** Sprawdziłem wszystko, co mogłoby zdradzić niedoskonałą
maszynę lub kule, i za każdym razem wynik mieścił się w tym, co daje idealny los:

| Co sprawdzałem | Co wyszło | Działa? |
|---|---|---|
| 1. Czy w jakimś okresie (dekady, epoki 1, 2 i 3 losowań w tygodniu) jakieś liczby padały częściej | 11 testów, najmniejsze p = 0,047, po poprawce na wielokrotne testy nic | nie |
| 2. Czy jakieś pary lub trójki liczb padają razem częściej | najczęstsza para 31-42 padła 124 razy, a idealny los daje „rekordzistę” średnio 128 razy; trójka 21 razy wobec 22 | nie |
| 3. Czy losowanie zależy od poprzedniego (powtórki liczb, sumy, parzyste, niskie) | 11 miar wobec 1000 symulacji, nic istotnego po poprawce | nie |
| 4. Czy model uczony na latach 1957-2009 przewiduje lata 2010-2026 | 5 modeli (częste, rzadkie, „należy się”, Markow): wszystkie 0,72-0,73 trafienia na 6 liczb, czysty los 0,73-0,75 | nie |
| 4b. Jedyny ślad: w latach 1957-2009 liczby 40-49 padały ok. 4% rzadziej (istotne nawet po poprawce, p = 0,004) | w latach 2010-2026 już nie (p = 0,22) - to była cecha dawnych maszyn lub kul albo przypadek, dziś nie działa | nie |
| 5. Rozpisanie zakładów bez dublowania liczb | ta sama średnia trafień; szansa na choć jedną wygraną w losowaniu 32,6% zamiast 31,0% | szansy nie, pewności drobnej wygranej trochę |
| 5. Rzadko grane liczby (powyżej 31, bez wzorków) | ta sama szansa; przy wygranej 4, 5 lub 6 mniej osób dzieli nagrodę | szansy nie, wypłaty tak |

**Strategii `wykryta_nierownosc` nie dodaję:** nie ma czego wykorzystać. Jedyna nierówność (40-49) zniknęła po 2009 r.,
a nawet gdyby trwała, omijanie tych liczb podniosłoby średnią trafień o ok. 1% - zwrot z 5 zł zostałby ok. 1,16-1,18 zł.

## Szansa a wypłata - na czym polega różnica
- **Szansa** to to, jak często trafiasz. Każdy zestaw 6 liczb ma ją taką samą: 1 do 13 983 816 na szóstkę, ok. 1 do 57 na trójkę.
  20 zakładów to 20 razy większa szansa niż 1 zakład - i 20 razy większy koszt. Żaden wybór liczb tego nie zmienia.
- **Wypłata** to to, ile dostajesz, gdy trafisz. Trójka ma stałe 35 zł [DP], ale nagrody za 4, 5 i 6 dzieli się między
  wszystkich, którzy trafili. Ludzie chętnie grają daty (1-31), „szczęśliwe” liczby (3, 7, 9, 11, 13) i wzorki na kuponie.
  Kto gra liczby rzadko wybierane, przy tej samej szansie dzieli nagrodę z mniejszą liczbą osób (badania z Wielkiej Brytanii
  i Belgii [DP]). To strategia `rzadko_grane` - nadal na minusie, tylko z lepszą wypłatą w razie wygranej.
- **Pewność drobnej wygranej**: zakłady bez powtarzania tych samych par liczb (systemy pokrycia) rozkładają trafienia
  równiej. Średnio wygrywasz tyle samo, ale nieco częściej masz choć jedną trójkę (32,6% zamiast 31,0% przy 20 zakładach),
  a rzadziej kilka naraz. Bilans się nie zmienia.

## Uwaga o `rzadko_grane` w poprzednim teście
W backteście etapu 1 strategia `rzadko_grane` miała średnią trafień nieco niższą od teorii (z = -2,67). Przyczyna jest w danych,
nie w strategii: liczby 32-49, które ona woli, padały w latach 1957-2009 trochę rzadziej. Od 2010 r. różnicy już nie ma
(punkt 4b), a sam wynik z = -2,67 był zawyżony, bo 33 zakłady jednego losowania nie są od siebie niezależne.

## Jak powtórzyć
W folderze `prywatne/lotto` uruchom: `python analiza2.py` (liczby trafią do tabel niżej i do `wyniki/analiza2.json`).

## Wyniki testów (generuje `analiza2.py`)
<!-- WYNIKI-ANALIZY2: START (plik generuje analiza2.py, nie edytuj ręcznie) -->

Wygenerowano 2026-10-22 19:24. Dane: 7420 losowań (1957-01-27 - 2026-10-20). Poziom istotności 0,05 po poprawce na wielokrotne testy.

### 1. Nierówność liczb w okresach (chi-kwadrat, 48 st. swobody)

| Okres | Losowań | Chi-kwadrat | p | p po Bonferronim | q (BH) | Najczęstsza | Najrzadsza |
|---|---|---|---|---|---|---|---|
| 1957-1959 | 150 | 33,6 | 0,9424 | 1,0000 | 0,9493 | 8 (25 wobec 18) | 3 (12 wobec 18) |
| 1960-1969 | 528 | 59,3 | 0,1269 | 1,0000 | 0,4549 | 17 (89 wobec 65) | 48 (48 wobec 65) |
| 1970-1979 | 859 | 33,1 | 0,9493 | 1,0000 | 0,9493 | 29 (123 wobec 105) | 6 (85 wobec 105) |
| 1980-1989 | 1044 | 61,1 | 0,0977 | 1,0000 | 0,4549 | 6 (158 wobec 128) | 48 (100 wobec 128) |
| 1990-1999 | 1043 | 57,4 | 0,1654 | 1,0000 | 0,4549 | 34 (163 wobec 128) | 16 (106 wobec 128) |
| 2000-2009 | 1166 | 45,2 | 0,5872 | 1,0000 | 0,8074 | 24 (176 wobec 143) | 12 (124 wobec 143) |
| 2010-2019 | 1565 | 46,6 | 0,5285 | 1,0000 | 0,8074 | 6 (218 wobec 192) | 39 (165 wobec 192) |
| 2020-2026 | 1065 | 47,0 | 0,5134 | 1,0000 | 0,8074 | 38 (154 wobec 130) | 35 (101 wobec 130) |
| 1957-1974 (raz w tygodniu) | 1015 | 53,2 | 0,2818 | 1,0000 | 0,6200 | 17 (148 wobec 124) | 41 (97 wobec 124) |
| 1975-2006 (2 razy w tygodniu) | 3340 | 65,5 | 0,0475 | 0,5228 | 0,4549 | 21 (461 wobec 409) | 12 (363 wobec 409) |
| 2007-2026 (3 razy w tygodniu) | 3065 | 40,2 | 0,7819 | 1,0000 | 0,9493 | 38 (413 wobec 375) | 33 (333 wobec 375) |

Istotnych po poprawce: **0 z 11**.

### 2. Pary i trójki liczb

- **Pary** (1176 możliwych, każda powinna paść średnio 94,6 razy). Najczęstsze: 31-42 (124×), 21-39 (122×), 1-17 (121×), 6-42 (121×), 17-26 (120×). Najmniejsze p 0,0021, po Bonferronim 1,0000; istotnych według BH: 0. Rekord 124× wobec rekordów w 200 symulacjach idealnego losu: średnio 127,9, od 121 do 145 (p = 0,9250).
- **Trójki** (18424 możliwych, każda powinna paść średnio 8,1 razy). Najczęstsze: 1-17-38 (21×), 1-28-38 (21×), 10-11-24 (20×), 5-18-40 (19×), 21-22-25 (19×). Najmniejsze p 0,0001, po Bonferronim 1,0000; istotnych według BH: 0. Rekord 21× wobec rekordów w 200 symulacjach idealnego losu: średnio 21,7, od 19 do 27 (p = 0,8410).

### 3. Zależność od poprzednich losowań (1000 symulacji idealnego losu)

| Co sprawdzamy | Dane | Idealny los (średnio ± odchylenie) | p | q (BH) |
|---|---|---|---|---|
| ile liczb powtarza się z poprzedniego losowania | 0,7237 | 0,7348 ± 0,0089 | 0,2038 | 0,4678 |
| ile liczb powtarza się sprzed 2 losowań | 0,7443 | 0,7347 ± 0,0088 | 0,2807 | 0,4678 |
| ile liczb powtarza się sprzed 3 losowań | 0,7355 | 0,7348 ± 0,0090 | 0,9341 | 0,9590 |
| czy duża suma pociąga dużą sumę w następnym | 0,0059 | 0,0003 ± 0,0114 | 0,6154 | 0,7521 |
| to samo co 2 losowania dalej | 0,0115 | -0,0004 ± 0,0116 | 0,2977 | 0,4678 |
| czy liczba parzystych przechodzi na następne | 0,0243 | -0,0000 ± 0,0117 | 0,0450 | 0,2473 |
| czy liczba niskich (1-24) przechodzi na następne | 0,0005 | -0,0001 ± 0,0116 | 0,9590 | 0,9590 |
| średnia suma 6 liczb | 149,0970 | 149,9890 ± 0,3633 | 0,0120 | 0,1319 |
| rozrzut sumy | 1054,6767 | 1074,9150 ± 16,7453 | 0,2268 | 0,4678 |
| średnio parzystych w losowaniu | 2,9458 | 2,9392 ± 0,0137 | 0,6014 | 0,7521 |
| średnio niskich (1-24) w losowaniu | 2,9606 | 2,9390 ± 0,0131 | 0,0989 | 0,3626 |

Istotnych po poprawce: **0 z 11**.

### 4. Test przewidywania (uczenie na danych sprzed 2010-01-01, sprawdzenie na 2630 losowaniach od tej daty)

Każdy model typuje 6 liczb przed losowaniem, znając tylko przeszłość. Los daje średnio 0,7347 trafienia.

| Model | Śr. trafień | z | p po Bonferronim | 3+ trafień (oczekiwane) |
|---|---|---|---|---|
| `czeste_od_1957`: 6 liczb najczęstszych w całej dotychczasowej historii | 0,7346 | -0,01 | 1,0000 | 47 (49,0) |
| `czeste_ostatnie_50`: 6 liczb najczęstszych w ostatnich 50 losowaniach | 0,7304 | -0,29 | 1,0000 | 47 (49,0) |
| `rzadkie_ostatnie_50`: 6 liczb najrzadszych w ostatnich 50 losowaniach | 0,7202 | -0,98 | 1,0000 | 49 (49,0) |
| `najdluzej_nie_bylo`: 6 liczb, które najdłużej nie padły („należą się”) | 0,7278 | -0,47 | 1,0000 | 50 (49,0) |
| `markow`: liczby z najwyższą szansą po tym, co padło ostatnio (uczony tylko na danych sprzed testu) | 0,7323 | -0,16 | 1,0000 | 48 (49,0) |
| `los`: 6 losowych liczb (punkt odniesienia) | 0,7536 | 1,28 | 1,0000 | 58 (49,0) |

Modeli lepszych od losu po poprawce: **0**.

**4b. Hipoteza z danych 1957-2009, sprawdzona na 2010-2026.** Spośród 9 zakresów (1-9, 10-19, ..., 1-24, 32-49) najbardziej odstawał zakres 40-49: padał rzadziej (z = -3,50, p po Bonferronim 0,0042). Na nowych danych: 3183 wobec 3220,4 oczekiwanych, z = -0,78, p jednostronne 0,2175 - nie potwierdziła się.

### 5. Pokrycie: 20 zakładów losowych wobec rozpisanych (40000 prób)

| | Śr. trafień na zakład | Szansa na choć jedną wygraną (3+) | Rozkład liczby wygranych 0 / 1 / 2 / 3+ |
|---|---|---|---|
| Losowe (mogą się dublować) | 0,7332 | 31,00% | 69,00% / 25,84% / 4,65% / 0,51% |
| Rozpisane (najwyżej 2 wspólne) | 0,7341 | 32,60% | 67,39% / 27,73% / 4,47% / 0,41% |

Teoria dla 20 niezależnych zakładów: 31,36% na choć jedną wygraną.

**Kontrola `rzadko_grane`:** liczby 32-49 padły 16104 razy wobec 16354,3 oczekiwanych (z = -2,60, p = 0,0093).

**Werdykt automatu:** żaden test po poprawce nie pokazał nierówności, którą da się wykorzystać.

<!-- WYNIKI-ANALIZY2: KONIEC -->

## Odpowiedzialna gra
Gra od 18 lat. Pomoc: telefon zaufania uzależnień behawioralnych (także hazard) 801 889 880, codziennie 17-22;
bezpłatny Ogólnopolski Telefon Zaufania Uzależnienia (KCPU) 800 199 990, codziennie 16-21 [DP].
