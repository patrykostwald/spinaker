# Lotto, etap 3: 26 technik „przewidywania” i wielka symulacja (23.10.2026)

Dane: 7420 prawdziwych losowań 1957-2026 (`dane/lotto.csv`). Opis technik i źródła: `TECHNIKI.md`.
Liczby niżej generuje `python symulacja.py` w folderze `etap3` (ok. 10 minut); ten wstęp pisałem ręcznie na ich podstawie.

## Werdykt prostym językiem
**Żadna z 26 technik i żadne z 5 połączeń nie zawęża okna wypadających liczb w sposób istotny i powtarzalny.**
Najlepsze wyniki z lat do 2009 nie powtórzyły się w latach 2010-2026, a po poprawce na wielokrotne testy nic nie jest
istotne ani na całej historii, ani w teście poza próbą. Nie dodaję żadnej „przewidującej” strategii do automatu.

| Co sprawdziłem | Co wyszło |
|---|---|
| 26 technik: systemy graczy (częste, gorące, zimne, zaległe, delta, suma, parzyste, pozycje, pary, szablony), statystyka (EWMA, Markow, Bayes, hazard przerw, anomalie), uczenie maszynowe (regresja logistyczna, las losowy, boosting, sieć neuronowa, algorytm genetyczny, klastry, analogi, bandyta) | w 12 najwyżej ocenionych liczbach średnio 1,40-1,50 z 6 wylosowanych; czysty los: 1,47. Najlepsza w latach 2010-2026: las losowy 1,49 (p = 0,11 przed poprawką, 1,00 po) |
| 5 połączeń: głosowanie rang (Borda), średnia, stacking, najlepsza para i trójka wybrane na latach do 2009 | trójka (zaległe + powtórki + delta) do 2009: 1,54 - wygląda na sukces; w latach 2010-2026: 1,45, czyli **poniżej** losu. Klasyczne przeuczenie: wybierając najlepszą z 2600 trójek, zawsze znajdzie się „zwycięzca” |
| Ślad z etapu 2 | techniki faworyzujące „typowe” zestawy (suma, delta) miały w latach 1957-2009 ok. 1,53 (szablony 1,50), a od 2010 r. 1,44-1,45. To ten sam ślad co w etapie 2 (liczby 40-49 padały wtedy rzadziej) - dawne maszyny lub kule, dziś już nie działa |
| Zakłady systemowe 7-12 liczb z rankingów każdej metody | 1152 testy „co najmniej 3, 4, 5 trafionych w top-n”: po poprawce Holma żaden istotny. Zwrot ze złotówki skacze (0,16-0,63 zł) tylko tam, gdzie raz trafiła się szóstka w top-n - przypadek, nie metoda |
| Wynik w zł (20 zakładów z top-12) | wszystkie metody od −61 do −82 zł na losowanie, los −81 zł w tej historii (teoria −77 zł). Różnice robią **pojedyncze** trafienia wszystkich 6 liczb w top-12 (0-2 razy na 6920 losowań, los spodziewa się 0,46 razy) - jedno takie zdarzenie to ok. +9 zł na losowanie w średniej. To szczęście, nie metoda |
| Wariant 100 zł: 2 systemy po 7 liczb + 6 zakładów | od −71 do −83 zł na losowanie, los −80,5 zł; ta sama szansa, inaczej rozłożona |

**Jak czytać:** gdyby jakaś technika naprawdę zawężała okno, miałaby w teście 2010-2026 wyraźnie więcej niż 1,47
w top-12 (np. 1,55) i p po poprawce poniżej 0,05. Najbliżej było 1,49 z p = 1,00 po poprawce - to zwykły rozrzut losu
(przy 2630 losowaniach różnica ±0,03 zdarza się sama z siebie).

## Co trafiło do automatu
Zgodnie z poleceniem, skoro żaden ranking nie przeszedł testu poza próbą, dodałem tylko wariant porównawczy
**`system7_los`** (`strategie.py`): 2 zakłady systemowe po 7 losowych liczb (14 zakładów) + 6 zwykłych zakładów = 100 zł.
To ta sama szansa co 20 zwykłych zakładów, inaczej rozłożona: rzadziej wygrywa się cokolwiek, ale przy trafieniu
5 lub 6 liczb z siódemki wygrywa się kilka stopni naraz. [DP: potwierdź w regulaminie Lotto, że system 7 jest dostępny
i kosztuje 7 zakładów.]

## Systemy 7-12 liczb - na czym polegają
System n liczb to wszystkie C(n,6) zwykłych zakładów z tych liczb naraz: 7 = 7 zakładów (35 zł), 8 = 28, 9 = 84, 10 = 210,
11 = 462, 12 = 924 (4 620 zł). Jeśli wśród n liczb są 3, 4, 5 albo 6 wylosowanych, wygrywa się wiele stopni naraz,
ale średni zwrot ze złotówki jest dokładnie ten sam co przy zwykłych zakładach (0,23 zł z każdej złotówki, licząc szóstkę
jako 3 mln zł; bez szóstki ok. 0,17-0,19 zł). System opłaca się więc tylko wtedy, gdy ranking naprawdę zawęża okno - a nie zawęża.

## Metoda w skrócie
- Każda technika dostaje losowania po kolei i ocenia 49 liczb **zanim** zobaczy losowanie, które przewiduje
  (sprawdzone testem: zmiana przyszłości nie zmienia żadnej wcześniejszej oceny). Rozgrzewka: 500 losowań; oceniane 6920.
- Modele uczenia maszynowego douczane co 250-500 losowań, tylko na przeszłości; sieć neuronowa (okno 10 losowań)
  zastępuje LSTM, bo zasady pozwalają tylko na numpy i scikit-learn.
- Istotność: każdy wynik porównany z 20 000 losowymi rankingami; poprawka Holma na wszystkie 33 metody × 4 progi (k = 6, 12, 18, 24);
  95% przedział z bootstrapu blokowego. Połączenia wybierane wyłącznie na latach do 2009, oceniane na 2010-2026.
- Nagrody jak w RAPORT.md: 3 = 35 zł, 4 = 200 zł, 5 = 7 500 zł, 6 = 3 mln zł [DP].

## Szczegółowe wyniki

<!-- WYNIKI-SYMULACJI: START (plik generuje symulacja.py, nie edytuj ręcznie) -->

Policzono 2026-10-22T23:26:44: 7420 losowań (1957-01-27 - 2026-10-20), ocenianych 6920 po rozgrzewce 500; uczenie (wybór połączeń) do 2009-12-31 (4290 losowań), test poza próbą od 2010-01-02 (2630 losowań). Los: 20000 losowych rankingów. Czas obliczeń: 7 min.

### Tabela 1. Trafienia w top-12 (los = 1,47 na 6 liczb) i wynik w zł

Kolumny: średnia liczba wylosowanych liczb w 12 najwyżej ocenionych; różnica z losem i 95% przedział; p po poprawce Holma (wszystkie metody i k); wynik w zł = średni bilans na losowanie przy 20 zakładach po 5 zł z top-12 (czysty los: −77 zł).

| Metoda | Na czym polega | Cała historia: top-12 | różnica (95% CI) | p Holma | 2010-2026: top-12 | różnica (95% CI) | p Holma | zł / losowanie | Werdykt |
|---|---|---|---|---|---|---|---|---|---|
| `los` | losowy ranking (punkt odniesienia) | 1,478 | 0,009 (-0,018; 0,033) | 1,000 | 1,483 | 0,014 (-0,024; 0,058) | 1,000 | −81 zł | punkt odniesienia |
| `czeste` | najczęstsze w całej historii | 1,475 | 0,006 (-0,019; 0,028) | 1,000 | 1,467 | -0,003 (-0,037; 0,034) | 1,000 | −73 zł | jak los |
| `czeste_epoka` | najczęstsze od początku bieżącej epoki maszyn | 1,475 | 0,005 (-0,018; 0,028) | 1,000 | 1,451 | -0,018 (-0,061; 0,020) | 1,000 | −81 zł | jak los |
| `gorace` | najczęstsze w ostatnich 50 | 1,467 | -0,002 (-0,025; 0,023) | 1,000 | 1,485 | 0,015 (-0,018; 0,051) | 1,000 | −81 zł | jak los |
| `zimne` | najrzadsze w ostatnich 50 | 1,466 | -0,003 (-0,027; 0,019) | 1,000 | 1,441 | -0,029 (-0,069; 0,003) | 1,000 | −82 zł | jak los |
| `zalegle` | najdłużej nieobecne („należy się”) | 1,470 | 0,000 (-0,023; 0,024) | 1,000 | 1,468 | -0,001 (-0,040; 0,033) | 1,000 | −81 zł | jak los |
| `ewma` | częstość z zapominaniem (połowa wagi po 100 losowaniach) | 1,476 | 0,006 (-0,017; 0,031) | 1,000 | 1,486 | 0,017 (-0,021; 0,060) | 1,000 | −80 zł | jak los |
| `bayes` | Dirichlet z zapominaniem (połowa po 500), założenie: wszystkie równe | 1,477 | 0,007 (-0,015; 0,031) | 1,000 | 1,461 | -0,008 (-0,041; 0,031) | 1,000 | −62 zł | jak los |
| `anomalia` | największe odchylenie w górę w ostatnich 300 | 1,473 | 0,004 (-0,023; 0,026) | 1,000 | 1,479 | 0,010 (-0,032; 0,052) | 1,000 | −71 zł | jak los |
| `powtorki` | liczby z ostatnich losowań (ostatnie najwyżej) | 1,468 | -0,001 (-0,025; 0,023) | 1,000 | 1,492 | 0,023 (-0,011; 0,068) | 1,000 | −71 zł | jak los |
| `sasiedzi` | sąsiedzi (±1) liczb z ostatniego losowania | 1,480 | 0,011 (-0,013; 0,035) | 1,000 | 1,492 | 0,022 (-0,015; 0,062) | 1,000 | −69 zł | jak los |
| `pary` | najczęstsi partnerzy liczb z ostatniego losowania | 1,483 | 0,014 (-0,007; 0,036) | 1,000 | 1,460 | -0,010 (-0,037; 0,021) | 1,000 | −82 zł | jak los |
| `markow` | łańcuch Markowa: co pada po liczbach z ostatniego losowania | 1,489 | 0,020 (-0,005; 0,041) | 1,000 | 1,478 | 0,008 (-0,031; 0,041) | 1,000 | −80 zł | jak los |
| `hazard_przerw` | empiryczna szansa powrotu po przerwie obecnej długości | 1,485 | 0,016 (-0,006; 0,040) | 1,000 | 1,485 | 0,015 (-0,026; 0,054) | 1,000 | −61 zł | jak los |
| `suma` | zestawy o sumie w środkowych 50% dawnych sum | 1,495 | 0,025 (-0,001; 0,050) | 1,000 | 1,441 | -0,028 (-0,065; 0,014) | 1,000 | −82 zł | jak los |
| `delta` | system delta: różnice w typowych (10-90%) przedziałach | 1,499 | 0,030 (0,005; 0,056) | 0,972 | 1,448 | -0,022 (-0,058; 0,022) | 1,000 | −70 zł | jak los |
| `pozycje` | każda pozycja (1.-6. liczba) w typowym przedziale (25-75%) | 1,461 | -0,008 (-0,033; 0,015) | 1,000 | 1,452 | -0,017 (-0,057; 0,027) | 1,000 | −82 zł | jak los |
| `parzyste_niskie` | najczęstsze proporcje parzyste/nieparzyste i niskie/wysokie | 1,462 | -0,007 (-0,027; 0,016) | 1,000 | 1,431 | -0,038 (-0,075; 0,002) | 1,000 | −81 zł | jak los |
| `szablony` | szablony Gianelli: najczęstsze układy dziesiątek | 1,476 | 0,007 (-0,017; 0,031) | 1,000 | 1,441 | -0,028 (-0,081; 0,016) | 1,000 | −71 zł | jak los |
| `logistyczna` | regresja logistyczna na 7 cechach | 1,454 | -0,016 (-0,042; 0,009) | 1,000 | 1,400 | -0,070 (-0,109; -0,031) | 1,000 | −81 zł | jak los |
| `las` | las losowy (60 drzew, głębokość 6) | 1,488 | 0,019 (-0,002; 0,041) | 1,000 | 1,494 | 0,024 (-0,014; 0,061) | 1,000 | −69 zł | jak los |
| `boosting` | gradient boosting (100 iteracji) | 1,486 | 0,016 (-0,007; 0,043) | 1,000 | 1,476 | 0,007 (-0,037; 0,048) | 1,000 | −81 zł | jak los |
| `siec` | sieć neuronowa na oknie 10 losowań (zamiast LSTM) | 1,479 | 0,009 (-0,013; 0,033) | 1,000 | 1,469 | -0,000 (-0,043; 0,032) | 1,000 | −62 zł | jak los |
| `genetyczny` | algorytm genetyczny dobiera wagi cech | 1,477 | 0,008 (-0,014; 0,033) | 1,000 | 1,454 | -0,015 (-0,050; 0,024) | 1,000 | −82 zł | jak los |
| `klastry` | k-średnich (8 grup) + przejścia między grupami | 1,475 | 0,006 (-0,020; 0,028) | 1,000 | 1,469 | -0,001 (-0,036; 0,037) | 1,000 | −71 zł | jak los |
| `analogi` | co padało po 50 losowaniach najbardziej podobnych do ostatniego | 1,460 | -0,009 (-0,031; 0,012) | 1,000 | 1,454 | -0,015 (-0,047; 0,024) | 1,000 | −62 zł | jak los |
| `bandyta` | uczenie ze wzmocnieniem: próbkowanie Thompsona z zapominaniem | 1,461 | -0,009 (-0,035; 0,015) | 1,000 | 1,444 | -0,025 (-0,071; 0,015) | 1,000 | −82 zł | jak los |
| `borda` | głosowanie rang wszystkich technik | 1,480 | 0,011 (-0,009; 0,032) | 1,000 | 1,438 | -0,031 (-0,070; 0,009) | 1,000 | −61 zł | jak los |
| `srednia` | średnia ocen wszystkich technik | 1,467 | -0,002 (-0,023; 0,021) | 1,000 | 1,432 | -0,037 (-0,070; 0,001) | 1,000 | −62 zł | jak los |
| `stacking` | regresja logistyczna na rangach (uczona na przeszłości) | 1,451 | -0,019 (-0,043; 0,003) | 1,000 | 1,445 | -0,025 (-0,065; 0,016) | 1,000 | −72 zł | jak los |
| `para` | najlepsza para z lat do 2009: zimne + delta | 1,496 | 0,026 (0,001; 0,051) | 1,000 | 1,435 | -0,034 (-0,074; 0,006) | 1,000 | −80 zł | jak los |
| `trojka` | najlepsza trójka z lat do 2009: zalegle + powtorki + delta | 1,506 | 0,036 (0,013; 0,064) | 0,218 | 1,448 | -0,021 (-0,058; 0,024) | 1,000 | −79 zł | jak los |

### Tabela 2. Wszystkie k na latach 2010-2026 (test poza próbą): średnia trafień (p Holma)

| Metoda | top-6 (los 0,73) | top-12 (los 1,47) | top-18 (los 2,20) | top-24 (los 2,94) |
|---|---|---|---|---|
| `los` | 0,736 (1,000) | 1,483 (1,000) | 2,199 (1,000) | 2,949 (1,000) |
| `czeste` | 0,737 (1,000) | 1,467 (1,000) | 2,216 (1,000) | 2,944 (1,000) |
| `czeste_epoka` | 0,732 (1,000) | 1,451 (1,000) | 2,163 (1,000) | 2,902 (1,000) |
| `gorace` | 0,727 (1,000) | 1,485 (1,000) | 2,236 (1,000) | 2,948 (1,000) |
| `zimne` | 0,723 (1,000) | 1,441 (1,000) | 2,153 (1,000) | 2,916 (1,000) |
| `zalegle` | 0,721 (1,000) | 1,468 (1,000) | 2,208 (1,000) | 2,954 (1,000) |
| `ewma` | 0,760 (1,000) | 1,486 (1,000) | 2,223 (1,000) | 2,965 (1,000) |
| `bayes` | 0,744 (1,000) | 1,461 (1,000) | 2,210 (1,000) | 2,930 (1,000) |
| `anomalia` | 0,742 (1,000) | 1,479 (1,000) | 2,229 (1,000) | 2,954 (1,000) |
| `powtorki` | 0,746 (1,000) | 1,492 (1,000) | 2,235 (1,000) | 2,931 (1,000) |
| `sasiedzi` | 0,727 (1,000) | 1,492 (1,000) | 2,222 (1,000) | 2,966 (1,000) |
| `pary` | 0,734 (1,000) | 1,460 (1,000) | 2,194 (1,000) | 2,912 (1,000) |
| `markow` | 0,741 (1,000) | 1,478 (1,000) | 2,216 (1,000) | 2,944 (1,000) |
| `hazard_przerw` | 0,727 (1,000) | 1,485 (1,000) | 2,233 (1,000) | 2,956 (1,000) |
| `suma` | 0,717 (1,000) | 1,441 (1,000) | 2,165 (1,000) | 2,891 (1,000) |
| `delta` | 0,714 (1,000) | 1,448 (1,000) | 2,161 (1,000) | 2,927 (1,000) |
| `pozycje` | 0,727 (1,000) | 1,452 (1,000) | 2,183 (1,000) | 2,916 (1,000) |
| `parzyste_niskie` | 0,730 (1,000) | 1,431 (1,000) | 2,155 (1,000) | 2,898 (1,000) |
| `szablony` | 0,717 (1,000) | 1,441 (1,000) | 2,182 (1,000) | 2,929 (1,000) |
| `logistyczna` | 0,683 (1,000) | 1,400 (1,000) | 2,152 (1,000) | 2,898 (1,000) |
| `las` | 0,743 (1,000) | 1,494 (1,000) | 2,223 (1,000) | 2,928 (1,000) |
| `boosting` | 0,742 (1,000) | 1,476 (1,000) | 2,203 (1,000) | 2,938 (1,000) |
| `siec` | 0,739 (1,000) | 1,469 (1,000) | 2,227 (1,000) | 2,984 (1,000) |
| `genetyczny` | 0,711 (1,000) | 1,454 (1,000) | 2,206 (1,000) | 2,935 (1,000) |
| `klastry` | 0,752 (1,000) | 1,469 (1,000) | 2,207 (1,000) | 2,923 (1,000) |
| `analogi` | 0,736 (1,000) | 1,454 (1,000) | 2,230 (1,000) | 2,955 (1,000) |
| `bandyta` | 0,727 (1,000) | 1,444 (1,000) | 2,194 (1,000) | 2,949 (1,000) |
| `borda` | 0,715 (1,000) | 1,438 (1,000) | 2,209 (1,000) | 2,927 (1,000) |
| `srednia` | 0,724 (1,000) | 1,432 (1,000) | 2,191 (1,000) | 2,940 (1,000) |
| `stacking` | 0,730 (1,000) | 1,445 (1,000) | 2,181 (1,000) | 2,929 (1,000) |
| `para` | 0,717 (1,000) | 1,435 (1,000) | 2,167 (1,000) | 2,899 (1,000) |
| `trojka` | 0,721 (1,000) | 1,448 (1,000) | 2,158 (1,000) | 2,906 (1,000) |

Najmniejsze p przed poprawką (cała historia, dowolne k): `trojka` top-12 p = 0,002, `delta` top-12 p = 0,008, `suma` top-6 p = 0,008, `delta` top-24 p = 0,009, `para` top-18 p = 0,011. Przy 128 testach kilka p poniżej 0,05 przed poprawką to rzecz normalna.

### Tabela 3. Zakłady systemowe 7-12 liczb z top-n rankingu (cała historia)

Zwrot na złotówkę (los: 0,233 zł z każdej złotówki dla każdego systemu) oraz jak często top-n zawierało co najmniej 4 wylosowane liczby (w nawiasie: los).

| Metoda | system 7 (35 zł) | system 8 (140 zł) | system 9 (420 zł) | system 10 (1050 zł) | system 11 (2310 zł) | system 12 (4620 zł) |
|---|---|---|---|---|---|---|
| `los` | 0,175 zł; ≥4: 0,25% (0,22%) | 0,161 zł; ≥4: 0,40% (0,43%) | 0,182 zł; ≥4: 0,68% (0,74%) | 0,194 zł; ≥4: 1,20% (1,18%) | 0,183 zł; ≥4: 1,89% (1,79%) | 0,191 zł; ≥4: 2,67% (2,57%) |
| `czeste` | 0,202 zł; ≥4: 0,12% (0,22%) | 0,195 zł; ≥4: 0,30% (0,43%) | 0,181 zł; ≥4: 0,58% (0,74%) | 0,173 zł; ≥4: 0,85% (1,18%) | 0,164 zł; ≥4: 1,34% (1,79%) | 0,271 zł; ≥4: 2,24% (2,57%) |
| `czeste_epoka` | 0,161 zł; ≥4: 0,25% (0,22%) | 0,157 zł; ≥4: 0,40% (0,43%) | 0,184 zł; ≥4: 0,78% (0,74%) | 0,187 zł; ≥4: 1,27% (1,18%) | 0,195 zł; ≥4: 2,02% (1,79%) | 0,191 zł; ≥4: 2,72% (2,57%) |
| `gorace` | 0,142 zł; ≥4: 0,13% (0,22%) | 0,143 zł; ≥4: 0,35% (0,43%) | 0,160 zł; ≥4: 0,81% (0,74%) | 0,186 zł; ≥4: 1,24% (1,18%) | 0,177 zł; ≥4: 1,91% (1,79%) | 0,188 zł; ≥4: 2,72% (2,57%) |
| `zimne` | 0,281 zł; ≥4: 0,22% (0,22%) | 0,238 zł; ≥4: 0,48% (0,43%) | 0,225 zł; ≥4: 0,71% (0,74%) | 0,201 zł; ≥4: 1,01% (1,18%) | 0,197 zł; ≥4: 1,56% (1,79%) | 0,185 zł; ≥4: 2,30% (2,57%) |
| `zalegle` | 0,173 zł; ≥4: 0,29% (0,22%) | 0,190 zł; ≥4: 0,56% (0,43%) | 0,185 zł; ≥4: 0,75% (0,74%) | 0,189 zł; ≥4: 1,18% (1,18%) | 0,193 zł; ≥4: 1,82% (1,79%) | 0,192 zł; ≥4: 2,76% (2,57%) |
| `ewma` | 0,215 zł; ≥4: 0,19% (0,22%) | 0,221 zł; ≥4: 0,30% (0,43%) | 0,216 zł; ≥4: 0,69% (0,74%) | 0,193 zł; ≥4: 1,17% (1,18%) | 0,206 zł; ≥4: 1,78% (1,79%) | 0,198 zł; ≥4: 2,63% (2,57%) |
| `bayes` | 0,166 zł; ≥4: 0,23% (0,22%) | 0,162 zł; ≥4: 0,46% (0,43%) | 0,202 zł; ≥4: 0,71% (0,74%) | 1,070 zł; ≥4: 1,10% (1,18%) | 0,581 zł; ≥4: 1,62% (1,79%) | 0,378 zł; ≥4: 2,41% (2,57%) |
| `anomalia` | 0,142 zł; ≥4: 0,14% (0,22%) | 0,147 zł; ≥4: 0,32% (0,43%) | 0,168 zł; ≥4: 0,62% (0,74%) | 0,617 zł; ≥4: 1,18% (1,18%) | 0,384 zł; ≥4: 1,73% (1,79%) | 0,288 zł; ≥4: 2,64% (2,57%) |
| `powtorki` | 0,166 zł; ≥4: 0,27% (0,22%) | 0,182 zł; ≥4: 0,46% (0,43%) | 0,177 zł; ≥4: 0,74% (0,74%) | 0,179 zł; ≥4: 1,16% (1,18%) | 0,187 zł; ≥4: 1,92% (1,79%) | 0,288 zł; ≥4: 2,43% (2,57%) |
| `sasiedzi` | 0,161 zł; ≥4: 0,20% (0,22%) | 0,199 zł; ≥4: 0,51% (0,43%) | 0,224 zł; ≥4: 0,81% (0,74%) | 0,226 zł; ≥4: 1,20% (1,18%) | 0,411 zł; ≥4: 1,82% (1,79%) | 0,314 zł; ≥4: 2,63% (2,57%) |
| `pary` | 0,173 zł; ≥4: 0,25% (0,22%) | 0,168 zł; ≥4: 0,45% (0,43%) | 0,195 zł; ≥4: 0,85% (0,74%) | 0,178 zł; ≥4: 1,24% (1,18%) | 0,189 zł; ≥4: 1,92% (1,79%) | 0,183 zł; ≥4: 2,54% (2,57%) |
| `markow` | 0,223 zł; ≥4: 0,20% (0,22%) | 0,208 zł; ≥4: 0,36% (0,43%) | 0,183 zł; ≥4: 0,71% (0,74%) | 0,178 zł; ≥4: 1,26% (1,18%) | 0,181 zł; ≥4: 1,82% (1,79%) | 0,195 zł; ≥4: 2,54% (2,57%) |
| `hazard_przerw` | 0,245 zł; ≥4: 0,29% (0,22%) | 0,197 zł; ≥4: 0,46% (0,43%) | 0,195 zł; ≥4: 0,82% (0,74%) | 0,192 zł; ≥4: 1,37% (1,18%) | 0,391 zł; ≥4: 1,95% (1,79%) | 0,387 zł; ≥4: 2,82% (2,57%) |
| `suma` | 0,182 zł; ≥4: 0,23% (0,22%) | 0,176 zł; ≥4: 0,49% (0,43%) | 0,193 zł; ≥4: 0,75% (0,74%) | 0,190 zł; ≥4: 1,32% (1,18%) | 0,183 zł; ≥4: 2,07% (1,79%) | 0,184 zł; ≥4: 2,79% (2,57%) |
| `delta` | 0,175 zł; ≥4: 0,22% (0,22%) | 0,224 zł; ≥4: 0,43% (0,43%) | 0,222 zł; ≥4: 0,82% (0,74%) | 0,208 zł; ≥4: 1,24% (1,18%) | 0,207 zł; ≥4: 1,92% (1,79%) | 0,305 zł; ≥4: 2,76% (2,57%) |
| `pozycje` | 0,222 zł; ≥4: 0,20% (0,22%) | 0,206 zł; ≥4: 0,42% (0,43%) | 0,192 zł; ≥4: 0,77% (0,74%) | 0,189 zł; ≥4: 1,18% (1,18%) | 0,190 zł; ≥4: 1,76% (1,79%) | 0,181 zł; ≥4: 2,59% (2,57%) |
| `parzyste_niskie` | 0,168 zł; ≥4: 0,25% (0,22%) | 0,171 zł; ≥4: 0,53% (0,43%) | 0,209 zł; ≥4: 0,78% (0,74%) | 0,194 zł; ≥4: 1,21% (1,18%) | 0,186 zł; ≥4: 1,73% (1,79%) | 0,185 zł; ≥4: 2,64% (2,57%) |
| `szablony` | 0,289 zł; ≥4: 0,19% (0,22%) | 0,206 zł; ≥4: 0,36% (0,43%) | 0,183 zł; ≥4: 0,62% (0,74%) | 0,185 zł; ≥4: 1,16% (1,18%) | 0,384 zł; ≥4: 1,73% (1,79%) | 0,290 zł; ≥4: 2,56% (2,57%) |
| `logistyczna` | 0,237 zł; ≥4: 0,25% (0,22%) | 0,199 zł; ≥4: 0,51% (0,43%) | 0,205 zł; ≥4: 0,88% (0,74%) | 0,204 zł; ≥4: 1,34% (1,18%) | 0,202 zł; ≥4: 1,91% (1,79%) | 0,194 zł; ≥4: 2,59% (2,57%) |
| `las` | 0,169 zł; ≥4: 0,25% (0,22%) | 0,174 zł; ≥4: 0,53% (0,43%) | 0,197 zł; ≥4: 0,84% (0,74%) | 0,628 zł; ≥4: 1,40% (1,18%) | 0,406 zł; ≥4: 2,18% (1,79%) | 0,307 zł; ≥4: 2,90% (2,57%) |
| `boosting` | 0,317 zł; ≥4: 0,32% (0,22%) | 0,257 zł; ≥4: 0,58% (0,43%) | 0,215 zł; ≥4: 0,85% (0,74%) | 0,206 zł; ≥4: 1,39% (1,18%) | 0,196 zł; ≥4: 1,99% (1,79%) | 0,187 zł; ≥4: 2,64% (2,57%) |
| `siec` | 0,169 zł; ≥4: 0,26% (0,22%) | 0,210 zł; ≥4: 0,46% (0,43%) | 0,180 zł; ≥4: 0,75% (0,74%) | 0,168 zł; ≥4: 1,17% (1,18%) | 0,365 zł; ≥4: 1,62% (1,79%) | 0,381 zł; ≥4: 2,60% (2,57%) |
| `genetyczny` | 0,226 zł; ≥4: 0,23% (0,22%) | 0,215 zł; ≥4: 0,43% (0,43%) | 0,188 zł; ≥4: 0,74% (0,74%) | 0,180 zł; ≥4: 1,21% (1,18%) | 0,173 zł; ≥4: 1,69% (1,79%) | 0,178 zł; ≥4: 2,47% (2,57%) |
| `klastry` | 0,160 zł; ≥4: 0,22% (0,22%) | 0,186 zł; ≥4: 0,42% (0,43%) | 0,179 zł; ≥4: 0,66% (0,74%) | 0,195 zł; ≥4: 1,14% (1,18%) | 0,189 zł; ≥4: 1,79% (1,79%) | 0,286 zł; ≥4: 2,46% (2,57%) |
| `analogi` | 0,204 zł; ≥4: 0,20% (0,22%) | 0,193 zł; ≥4: 0,35% (0,43%) | 0,178 zł; ≥4: 0,68% (0,74%) | 0,629 zł; ≥4: 0,95% (1,18%) | 0,395 zł; ≥4: 1,50% (1,79%) | 0,385 zł; ≥4: 2,14% (2,57%) |
| `bandyta` | 0,145 zł; ≥4: 0,20% (0,22%) | 0,152 zł; ≥4: 0,43% (0,43%) | 0,151 zł; ≥4: 0,74% (0,74%) | 0,167 zł; ≥4: 1,11% (1,18%) | 0,172 zł; ≥4: 1,60% (1,79%) | 0,178 zł; ≥4: 2,51% (2,57%) |
| `borda` | 0,163 zł; ≥4: 0,22% (0,22%) | 0,194 zł; ≥4: 0,49% (0,43%) | 0,209 zł; ≥4: 0,79% (0,74%) | 0,628 zł; ≥4: 1,21% (1,18%) | 0,384 zł; ≥4: 1,82% (1,79%) | 0,392 zł; ≥4: 2,59% (2,57%) |
| `srednia` | 0,166 zł; ≥4: 0,16% (0,22%) | 0,210 zł; ≥4: 0,36% (0,43%) | 1,251 zł; ≥4: 0,66% (0,74%) | 0,611 zł; ≥4: 1,13% (1,18%) | 0,373 zł; ≥4: 1,76% (1,79%) | 0,377 zł; ≥4: 2,40% (2,57%) |
| `stacking` | 0,228 zł; ≥4: 0,26% (0,22%) | 0,212 zł; ≥4: 0,42% (0,43%) | 0,197 zł; ≥4: 0,78% (0,74%) | 0,613 zł; ≥4: 1,21% (1,18%) | 0,368 zł; ≥4: 1,75% (1,79%) | 0,277 zł; ≥4: 2,50% (2,57%) |
| `para` | 0,172 zł; ≥4: 0,26% (0,22%) | 0,170 zł; ≥4: 0,52% (0,43%) | 0,186 zł; ≥4: 0,94% (0,74%) | 0,195 zł; ≥4: 1,47% (1,18%) | 0,203 zł; ≥4: 2,24% (1,79%) | 0,198 zł; ≥4: 2,95% (2,57%) |
| `trojka` | 0,175 zł; ≥4: 0,26% (0,22%) | 0,207 zł; ≥4: 0,58% (0,43%) | 0,210 zł; ≥4: 0,91% (0,74%) | 0,209 zł; ≥4: 1,36% (1,18%) | 0,195 zł; ≥4: 1,97% (1,79%) | 0,205 zł; ≥4: 2,77% (2,57%) |

Wszystkie 6 liczb w top-12 (system 12 = szóstka): `los` 0, `czeste` 1, `czeste_epoka` 0, `gorace` 0, `zimne` 0, `zalegle` 0, `ewma` 0, `bayes` 2, `anomalia` 1, `powtorki` 1, `sasiedzi` 1, `pary` 0, `markow` 0, `hazard_przerw` 2, `suma` 0, `delta` 1, `pozycje` 0, `parzyste_niskie` 0, `szablony` 1, `logistyczna` 0, `las` 1, `boosting` 0, `siec` 2, `genetyczny` 0, `klastry` 1, `analogi` 2, `bandyta` 0, `borda` 2, `srednia` 2, `stacking` 1, `para` 0, `trojka` 0 razy; los spodziewa się 0.46 razy.

Test dwumianowy „co najmniej 3, 4, 5 trafionych w top-n” (n = 7-12, cała historia i 2010-2026): 1152 testów, istotnych po poprawce Holma: 0. Najmniejsze p: `ewma`, 2010-2026, system 11, co najmniej 5: p = <0,001 przed poprawką, 0,900 po.

### Tabela 4. Wariant 100 zł: 2 systemy po 7 liczb (rangi 1-7 i 8-14) + 6 zwykłych zakładów z top-12

| Metoda | bilans na losowanie, cała historia | 2010-2026 | zwykłe 20 zakładów z top-12, cała historia |
|---|---|---|---|
| `los` | −80 zł | −83 zł | −81 zł |
| `czeste` | −77 zł | −80 zł | −73 zł |
| `czeste_epoka` | −80 zł | −83 zł | −81 zł |
| `gorace` | −83 zł | −83 zł | −81 zł |
| `zimne` | −79 zł | −83 zł | −82 zł |
| `zalegle` | −82 zł | −82 zł | −81 zł |
| `ewma` | −81 zł | −76 zł | −80 zł |
| `bayes` | −75 zł | −75 zł | −62 zł |
| `anomalia` | −78 zł | −76 zł | −71 zł |
| `powtorki` | −79 zł | −72 zł | −71 zł |
| `sasiedzi` | −79 zł | −79 zł | −69 zł |
| `pary` | −83 zł | −83 zł | −82 zł |
| `markow` | −80 zł | −77 zł | −80 zł |
| `hazard_przerw` | −71 zł | −61 zł | −61 zł |
| `suma` | −80 zł | −77 zł | −82 zł |
| `delta` | −76 zł | −77 zł | −70 zł |
| `pozycje` | −79 zł | −77 zł | −82 zł |
| `parzyste_niskie` | −82 zł | −83 zł | −81 zł |
| `szablony` | −74 zł | −64 zł | −71 zł |
| `logistyczna` | −79 zł | −84 zł | −81 zł |
| `las` | −75 zł | −70 zł | −69 zł |
| `boosting` | −77 zł | −80 zł | −81 zł |
| `siec` | −78 zł | −77 zł | −62 zł |
| `genetyczny` | −82 zł | −78 zł | −82 zł |
| `klastry` | −80 zł | −75 zł | −71 zł |
| `analogi` | −73 zł | −85 zł | −62 zł |
| `bandyta` | −81 zł | −84 zł | −82 zł |
| `borda` | −77 zł | −76 zł | −61 zł |
| `srednia` | −77 zł | −77 zł | −62 zł |
| `stacking` | −78 zł | −78 zł | −72 zł |
| `para` | −80 zł | −85 zł | −80 zł |
| `trojka` | −77 zł | −77 zł | −79 zł |

Wybrane na latach do 2009: para = zimne + delta, trójka = zalegle + powtorki + delta.
Metody, które przeszły test poza próbą: **żadna**.

<!-- WYNIKI-SYMULACJI: KONIEC -->
