# Lotto, etap 3: przegląd technik „przewidywania” liczb (23.10.2026)

Pytanie właściciela: czy jest jakakolwiek technika, choćby nowa, która zawęża okno wypadających liczb.
Poniżej 28 technik z pięciu rodzin. Przy każdej: na czym polega, skąd, co obiecuje, kto ją rzetelnie sprawdził i jak testujemy
ją na naszych 7420 losowaniach (nazwa funkcji w `symulacja.py`). Oznaczenia:
**[PSEUDONAUKA]** - obietnica sprzeczna z rachunkiem prawdopodobieństwa albo brak jakiegokolwiek uczciwego testu;
**[SENSOWNE]** - działa tylko wtedy, gdy losowanie jest wadliwe (np. przechylona maszyna, lżejsza kula).

Jedna zasada wspólna dla wszystkich: przy uczciwej maszynie każde losowanie jest niezależne od poprzednich,
więc żadna technika oparta na historii nie może pomóc. Może pomóc tylko wtedy, gdy maszyna lub kule mają wadę,
a my tę wadę wykryjemy szybciej, niż operator ją usunie. Dlatego każdą technikę traktujemy jako „wykrywacz wady”.

Ważne o danych: w `dane/lotto.csv` liczby są zapisane rosnąco, nie w kolejności wypadania. Technik opartych na kolejności
(pozycja kuli w maszynie, „sygnatura” prowadzącego) nie da się więc sprawdzić; testujemy pozycje w zestawie posortowanym.

## Mapa: 28 technik
| Nr | Technika | Rodzina | Ocena | Test u nas |
|---|---|---|---|---|
| 1 | Częste liczby (cała historia) | systemy graczy | [SENSOWNE] tylko przy wadzie | `czeste` |
| 2 | Gorące liczby (ostatnie 50) | systemy graczy | [PSEUDONAUKA] | `gorace` |
| 3 | Zimne liczby (ostatnie 50) | systemy graczy | [PSEUDONAUKA] | `zimne` |
| 4 | Zaległe liczby („należy się”) | systemy graczy | [PSEUDONAUKA] | `zalegle` |
| 5 | System delta (różnice między liczbami) | systemy graczy | [PSEUDONAUKA] | `delta` |
| 6 | Suma liczb w „typowym” przedziale | systemy graczy | [PSEUDONAUKA] | `suma` |
| 7 | Parzyste i nieparzyste, niskie i wysokie | systemy graczy | [PSEUDONAUKA] | `parzyste_niskie` |
| 8 | Pozycje (rozkład 1., 2., ... 6. liczby) | systemy graczy | [PSEUDONAUKA] | `pozycje` |
| 9 | Pary towarzyszące ostatniemu losowaniu | systemy graczy | [PSEUDONAUKA] | `pary` |
| 10 | Powtórki i sąsiedzi z ostatniego losowania | systemy graczy | [PSEUDONAUKA] | `powtorki`, `sasiedzi` |
| 11 | Szablony Gianelli („geometria przypadku”) | systemy graczy | [PSEUDONAUKA] | `szablony` |
| 12 | Koła i systemy pokrycia (wheeling) | systemy graczy | nie przewiduje | etap 2 (pokrycie) |
| 13 | Rozkład i test chi-kwadrat (wykrywanie nierównej kuli) | statystyka | [SENSOWNE] | `czeste`, `czeste_epoka` |
| 14 | Średnia ważona w czasie (EWMA) | statystyka | [SENSOWNE] przy wadzie zmiennej w czasie | `ewma` |
| 15 | Łańcuch Markowa | statystyka | [PSEUDONAUKA] dla kul | `markow` |
| 16 | Bayes (Dirichlet, Compound-Dirichlet-Multinomial) | statystyka | [SENSOWNE] przy wadzie | `bayes` |
| 17 | Funkcja hazardu przerw (statystyczne „zaległe”) | statystyka | [PSEUDONAUKA] | `hazard_przerw` |
| 18 | Entropia i anomalie krótkookresowe | statystyka | [SENSOWNE] jako alarm, nie przewidywanie | `anomalia` |
| 19 | Regresja logistyczna | uczenie maszynowe | [PSEUDONAUKA] w obietnicach | `logistyczna` |
| 20 | Las losowy | uczenie maszynowe | [PSEUDONAUKA] w obietnicach | `las` |
| 21 | Gradient boosting | uczenie maszynowe | [PSEUDONAUKA] w obietnicach | `boosting` |
| 22 | Sieci LSTM, GRU, transformery | uczenie maszynowe | [PSEUDONAUKA] w obietnicach | `siec` (sieć na oknie 10 losowań) |
| 23 | Uczenie ze wzmocnieniem (bandyta wielorękie) | uczenie maszynowe | [PSEUDONAUKA] w obietnicach | `bandyta` |
| 24 | Algorytm genetyczny | uczenie maszynowe | [PSEUDONAUKA] w obietnicach | `genetyczny` |
| 25 | Klastrowanie i metoda analogów (kNN) | uczenie maszynowe | [PSEUDONAUKA] | `klastry`, `analogi` |
| 26 | Stronniczość maszyny i kul (badania fizyczne) | fizyka | [SENSOWNE] | `czeste_epoka`, `bayes` |
| 27 | Analogia z ruletką (fizyka ruchu, przechył koła) | fizyka | [SENSOWNE] dla ruletki, nieprzenośne | nie da się (brak kolejności i pomiarów) |
| 28 | „AI wróżenie z fusów”, numerologia, daty urodzin | inne | [PSEUDONAUKA] | nie (nie ma czego mierzyć) |

Do tego połączenia: głosowanie rang (Borda), średnia wyników, stacking (model uczony tylko na przeszłości),
najlepsza para i trójka technik wybrane na latach do 2009 i sprawdzone na 2010-2026. Punkt odniesienia: `los` (losowy ranking).

## Systemy graczy

### 1. Częste liczby (cała historia) - `czeste`
- **Na czym polega:** grać liczby, które od początku padały najczęściej.
- **Skąd:** najstarszy system, opisywany w każdym poradniku (np. książki Gail Howard, „Lottery Master Guide”, Smart Luck).
- **Obiecuje:** „liczby, które lubi maszyna”.
- **Weryfikacja:** to jedyny system graczy z sensownym uzasadnieniem: jeśli kula jest lżejsza, będzie padać częściej.
  Eksperyment z maszyną na sprężone powietrze: kula lżejsza o 1-5% dawała już wyniki istotnie nierówne
  ([Pinitsoontorn i in., Asia-Pacific Journal of Science and Technology](https://so01.tci-thaijo.org/index.php/APST/article/view/83061)).
  Audyty prawdziwych loterii przeważnie nic nie znajdują: rumuńskie 6/49, 2706 losowań, brak odchyleń
  ([Ungar 2025, Revista Economica](https://ideas.repec.org/a/blg/reveco/v77y2025i1p13-24.html)); meksykańskie i włoskie
  lotto - pojedyncze okresy odchyleń, zalecany stały audyt ([arXiv:0806.4595](https://arxiv.org/pdf/0806.4595)).
  U nas w etapie 2: jedyny ślad (40-49 rzadziej do 2009 r.) zniknął po 2010 r.
- **Test:** ranking według liczby wystąpień w całej przeszłości.

### 2. Gorące liczby - `gorace` [PSEUDONAUKA]
- **Na czym polega:** grać liczby najczęstsze w ostatnich 50 losowaniach („są w formie”).
- **Skąd:** poradniki i serwisy z „analizą liczb”; złudzenie „gorącej ręki” opisane w badaniach graczy
  ([Kong, Granic, Lambert, Teo, Management Science 2020](https://ai.stanford.edu/~nlambert/papers/Kong_Granic_Lambert_Teo_(MS_2020))).
- **Obiecuje:** trend krótkoterminowy.
- **Weryfikacja:** badania pokazują, że to błąd poznawczy graczy, nie cecha losowań. Etap 1: wynik jak los.
- **Test:** ranking według wystąpień w ostatnich 50 losowaniach.

### 3. Zimne liczby - `zimne` [PSEUDONAUKA]
- **Na czym polega:** odwrotność gorących - najrzadsze w ostatnich 50.
- **Skąd i weryfikacja:** „złudzenie hazardzisty”; klasyczne badanie Maryland: gracze przestają stawiać na liczbę zaraz
  po jej wylosowaniu i wracają do niej po kilku miesiącach ([Clotfelter i Cook 1993, Management Science](https://scholars.duke.edu/publication/859676)).
  Błąd graczy, nie cecha kul.
- **Test:** ranking odwrotny do `gorace`.

### 4. Zaległe liczby - `zalegle` [PSEUDONAUKA]
- **Na czym polega:** liczba, której dawno nie było, „należy się”.
- **Skąd:** to samo złudzenie hazardzisty co wyżej.
- **Obiecuje:** powrót do średniej w krótkim czasie.
- **Weryfikacja:** kule nie pamiętają. Etap 2 (model „należy się”): jak los.
- **Test:** ranking według liczby losowań od ostatniego wystąpienia (najdłużej nieobecne pierwsze).

### 5. System delta - `delta` [PSEUDONAUKA]
- **Na czym polega:** zamiast liczb wybiera się różnice między kolejnymi liczbami zestawu (najczęściej małe: 1-15)
  i z nich składa zestaw.
- **Skąd:** poradniki graczy z lat 90. (systemy Gail Howard i naśladowcy; brak pracy naukowej).
- **Obiecuje:** „zestawy o typowym kształcie”.
- **Weryfikacja:** małe różnice są częste, bo takich zestawów jest po prostu więcej; każdy pojedynczy zestaw ma tę samą szansę.
  Żadnego niezależnego testu nie znalazłem.
- **Test:** losujemy wiele zestawów, zostawiamy te, których różnice leżą w najczęstszych (z przeszłości) przedziałach,
  i liczymy, jak często występuje w nich każda liczba. Tak powstaje ranking.

### 6. Suma w typowym przedziale - `suma` [PSEUDONAUKA]
- **Na czym polega:** grać tylko zestawy o sumie bliskiej średniej (ok. 150 dla 6 z 49).
- **Skąd:** poradniki i serwisy „analizy” (np. Lotterycodex i podobne).
- **Weryfikacja:** to samo co delta: sumy środkowe są częstsze, bo takich zestawów jest więcej. Nie zmienia szansy zestawu.
- **Test:** jak w `delta`, filtr: suma w środkowych 50% sum z przeszłości.

### 7. Parzyste i nieparzyste, niskie i wysokie - `parzyste_niskie` [PSEUDONAUKA]
- **Na czym polega:** grać zestawy 3:3 (albo 2:4, 4:2) parzystych do nieparzystych i niskich do wysokich.
- **Skąd:** serwisy analityczne; rozkład 3:3 wypada w ok. 33% losowań i to wynika wprost z liczenia kombinacji
  ([Draw Analytics, przykład](https://www.drawanalytics.com/illinois/il_lotto/number-patterns)).
- **Weryfikacja:** czysta kombinatoryka, żadnej przewagi.
- **Test:** filtr zestawów o najczęstszych w przeszłości proporcjach, ranking jak w `delta`.

### 8. Pozycje - `pozycje` [PSEUDONAUKA]
- **Na czym polega:** osobny rozkład dla najmniejszej, drugiej, ... największej liczby zestawu; z każdej pozycji
  bierze się najczęstsze wartości.
- **Skąd:** programy do „analizy lotto” i notatniki z GitHub/Kaggle.
- **Test:** wynik liczby = suma po pozycjach częstości tej liczby na danej pozycji w przeszłości, ważona szczytem rozkładu.

### 9. Pary - `pary` [PSEUDONAUKA]
- **Na czym polega:** grać liczby, które najczęściej padały razem z liczbami z ostatniego losowania.
- **Weryfikacja:** etap 2: najczęstsza para (31-42, 124 razy) jest dokładnie taka, jakiej rekordzistki spodziewamy się po losie.
- **Test:** wynik liczby = suma jej wspólnych wystąpień z 6 liczbami ostatniego losowania (cała przeszłość).

### 10. Powtórki i sąsiedzi - `powtorki`, `sasiedzi` [PSEUDONAUKA]
- **Na czym polega:** grać liczby z ostatniego losowania albo ich sąsiadów (±1).
- **Weryfikacja:** etap 2: liczba powtórek z poprzedniego losowania zgodna z losem.
- **Test:** `powtorki` - najwyżej liczby z ostatniego losowania, potem z przedostatniego itd.; `sasiedzi` - najwyżej liczby o 1 mniejsze i większe.

### 11. Szablony Gianelli - `szablony` [PSEUDONAUKA]
- **Na czym polega:** liczby dzieli się na grupy (1-9, 10-19, ...); „szablon” to ile liczb z każdej grupy. Gra się szablony najczęstsze.
- **Skąd:** Renato Gianella, „The Geometry of Chance”; omówienie i krytyka: Polster i Ross pokazują, że szablon nie zmienia
  szansy żadnego zestawu ([Polster i Ross, „The media lottery”](https://www.qedcat.com/misc/193.html);
  [City A.M.](https://cityam.com/?p=354401)).
- **Test:** filtr zestawów o najczęstszych w przeszłości szablonach dziesiątek, ranking jak w `delta`.

### 12. Koła i systemy pokrycia (wheeling) - nie przewiduje
- **Na czym polega:** z wybranej puli liczb buduje się zakłady tak, by przy trafieniu kilku liczb z puli mieć gwarantowaną
  drobną wygraną.
- **Skąd:** Gail Howard („Lotto Wheel Five to Win”, Smart Luck); teoria planów pokrywających w kombinatoryce.
- **Weryfikacja:** gwarancje są matematycznie prawdziwe, ale **warunkowe** (jeśli trafisz X liczb z puli). Średnia wygrana
  się nie zmienia. Etap 2: szansa na choć jedną wygraną 32,6% zamiast 31,0% przy 20 zakładach, bilans ten sam.
- **Test:** zrobiony w etapie 2; tu nie ma rankingu do sprawdzenia.

## Statystyka

### 13. Rozkład i chi-kwadrat - `czeste`, `czeste_epoka` [SENSOWNE]
- **Na czym polega:** sprawdzić, czy liczby padają równo; jeśli nie - grać te nadreprezentowane.
- **Skąd:** standard audytu loterii (np. regulator brytyjskiej loterii publikuje analizy maszyn,
  [University of Hertfordshire](https://uhra.herts.ac.uk/id/eprint/11868/1/S76.pdf)); test „bez celu” wybranego z góry
  ([arXiv:2103.11952](https://arxiv.org/abs/2103.11952v1)).
- **Test:** `czeste_epoka` - częstości liczone tylko od początku bieżącej epoki (1957, 1975, 2007 - zmiany liczby losowań
  w tygodniu; daty zmian maszyn nie są publicznie znane [DP]).

### 14. Średnia ważona w czasie (EWMA) - `ewma` [SENSOWNE]
- **Na czym polega:** częstość z „zapominaniem” (nowsze losowania ważą więcej), żeby szybko złapać nową wadę.
- **Skąd:** standardowa technika wykrywania zmian w procesach (kontrola jakości).
- **Test:** wykładnicza waga z połówkowym okresem 100 losowań.

### 15. Łańcuch Markowa - `markow` [PSEUDONAUKA dla kul]
- **Na czym polega:** prawdopodobieństwo, że liczba padnie, zależnie od tego, co padło w poprzednim losowaniu.
- **Skąd:** np. „Markov-chain Based Lottery Analysis System in Mobile Cloud Computing”
  ([He i in., ICAMCS 2016](https://www.atlantis-press.com/proceedings/icamcs-16/25854930)) - obiecuje „zawężenie zakresu”,
  ale nie podaje żadnej trafności.
- **Weryfikacja:** etap 2: model Markowa jak los. Brak niezależnego potwierdzenia.
- **Test:** macierz przejść 49×49 z całej przeszłości (wygładzona), wynik liczby = suma przejść od 6 liczb ostatniego losowania.

### 16. Bayes (Dirichlet) - `bayes` [SENSOWNE przy wadzie]
- **Na czym polega:** zaczynamy od założenia „wszystkie równe” i powoli przesuwamy wiarę w stronę liczb częstszych;
  silne założenie początkowe chroni przed gonieniem szumu.
- **Skąd:** praca o modelu Compound-Dirichlet-Multinomial, która twierdzi o zysku w grze Pick-3 w Vermont
  ([Nkomozake, arXiv:2403.12836](https://arxiv.org/html/2403.12836v1)) - twierdzenie niesprawdzone niezależnie, pojedyncza gra.
- **Test:** średnia rozkładu a posteriori z zapominaniem (okres połówkowy 500 losowań) i założeniem równym 300 losowaniom.

### 17. Funkcja hazardu przerw - `hazard_przerw` [PSEUDONAUKA]
- **Na czym polega:** „statystyczna” wersja zaległych: z historii liczymy, jak często liczba wraca po przerwie długości g.
- **Weryfikacja:** przy niezależnych losowaniach hazard jest stały (6/49), więc to tylko szum.
- **Test:** empiryczny hazard dla bieżącej przerwy każdej liczby (wspólny dla wszystkich liczb, z przeszłości).

### 18. Entropia i anomalie krótkookresowe - `anomalia` [SENSOWNE jako alarm]
- **Na czym polega:** mierzy się, czy ostatnie losowania są „mniej losowe” niż powinny (niższa entropia, skrajne wyniki
  testu); jeśli tak, gra się liczby odpowiedzialne za odchylenie.
- **Skąd:** testy losowości (NIST SP 800-22, audyty loterii z arXiv:0806.4595).
- **Test:** wynik z (odchylenie standardowe) liczby wystąpień w ostatnich 300 losowaniach.

## Uczenie maszynowe
Wspólne dla 19-25: modele uczą się tylko na przeszłości i są douczane co 250 losowań. Cechy każdej liczby: wystąpienia
w ostatnich 10, 50, 200 losowaniach i w całości, przerwa od ostatniego wystąpienia, czy była w ostatnim losowaniu,
EWMA; cel: czy padnie w następnym losowaniu.

### 19-21. Regresja logistyczna, las losowy, gradient boosting - `logistyczna`, `las`, `boosting`
- **Skąd:** dziesiątki notatników i repozytoriów, np. projekty zbierane w
  [LotteryPrediction (yangboz)](https://gittrend.io/repo/yangboz/LotteryPrediction),
  [takarakuji-ai](https://hunted.space/product/takarakuji-ai); popularne wpisy typu „Analyzing Lotto with data”
  ([DEV Community](https://dev.to/freyasky/analyzing-lotto-with-data-can-machine-learning-provide-the-answer-c6k)).
- **Obiecuje:** „model wykrył wzorce”.
- **Weryfikacja:** rzetelna praca naukowa na trzech prawdziwych loteriach (testy losowości, ARIMA, sieci neuronowe)
  nie znalazła żadnych wzorców ([Hernández i in., „Analysis of the results of lotteries using statistical methods and artificial
  neural networks”](https://redi.cedia.edu.ec/document/23527)). Wiele „sukcesów” w notatnikach to przeuczenie albo
  podglądanie przyszłości (uczenie na całych danych).
- **Test:** scikit-learn: `LogisticRegression`, `RandomForestClassifier` (60 drzew, głębokość 6),
  `HistGradientBoostingClassifier` (100 iteracji).

### 22. Sieci LSTM, GRU, transformery - `siec`
- **Skąd:** np. [PowerPredict](https://ithub.global.ssl.fastly.net/cpeoples/powerpredict) (transformer + dwukierunkowe LSTM/GRU),
  [tw-lottery-recommendation](https://awesome.ecosyste.ms/projects/github.com%2Fzients%2Ftw-lottery-recommendation) (transformer).
  Oba repozytoria same piszą, że wyniki loterii są losowe i model ich nie przewiduje.
  Na arXiv jedyna „praca” o przewidywaniu loterii przez AI to satyra:
  [SmileyNet - Towards the Prediction of the Lottery by Reading Tea Leaves with AI (arXiv:2407.21385)](https://arxiv.org/abs/2407.21385v1).
- **Weryfikacja:** brak jakiejkolwiek recenzowanej pracy z wynikiem lepszym od losu.
- **Test:** bez PyTorcha (zasada: tylko numpy i scikit-learn) używamy sieci wielowarstwowej (`MLPClassifier`) na oknie
  ostatnich 10 losowań (490 wejść, 49 wyjść). To ten sam pomysł co LSTM: sieć widzi sekwencję i przewiduje następne
  losowanie. Jeśli w sekwencji nie ma sygnału, większa sieć też go nie znajdzie, tylko mocniej się przeuczy.

### 23. Uczenie ze wzmocnieniem (bandyta) - `bandyta`
- **Skąd:** repozytoria RL nie zawierają rzetelnych projektów lotto (wyszukiwanie zwraca tylko „lottery ticket hypothesis”,
  czyli coś zupełnie innego: [arXiv:1906.02768](https://arxiv.org/pdf/1906.02768)). Najprostsza uczciwa postać RL dla
  tego problemu to wielorękie bandyta: 49 „ramion”, nagroda = liczba padła.
- **Test:** próbkowanie Thompsona z zapominaniem (rozkład Beta dla każdej liczby).

### 24. Algorytm genetyczny - `genetyczny`
- **Skąd:** pojawia się w „programach do lotto” i pracy o modelowaniu rynku loterii agentami
  ([Chie i Chen 2003](https://econpapers.repec.org/RePEc:sce:scecf3:155)); nie znalazłem pracy z testem przewidywania.
- **Test:** algorytm genetyczny dobiera wagi cech (jak w 19-21), żeby maksymalizować trafienia w top-12 na przeszłości;
  co 500 losowań nowa ewolucja.

### 25. Klastrowanie i analogi - `klastry`, `analogi`
- **Na czym polega:** `klastry` - grupujemy dawne losowania (k-średnich, 8 grup), sprawdzamy, po jakiej grupie zwykle
  przychodzi jaka, i gramy środek przewidywanej grupy; `analogi` - szukamy 50 dawnych losowań najbardziej podobnych
  do ostatniego i liczymy, co padło po nich.
- **Skąd:** typowe w notatnikach Kaggle i blogach o „AI w lotto”.

## Fizyka

### 26. Stronniczość maszyny i kul
- **Na czym polega:** kula lżejsza, porowata, zużyta albo maszyna przechylona może dawać nierówne wyniki.
- **Skąd i weryfikacja:** eksperyment z maszyną powietrzną: 1-5% różnicy masy wystarczyło do istotnej nierówności, ale do
  wykrycia potrzeba było ok. 1000 losowań ([Pinitsoontorn i in.](https://so01.tci-thaijo.org/index.php/APST/article/view/83061)).
  Operatorzy ważą i wymieniają kule oraz losują, która maszyna i który zestaw kul będą użyte
  ([Straight Dope](https://www.straightdope.com/21342169/how-can-i-pick-the-winning-number-in-the-lottery)).
  Wniosek: wada musiałaby trwać tysiące losowań bez wymiany kul, żebyśmy ją zdążyli wykorzystać.
- **Test:** `czeste_epoka`, `bayes`, `ewma` (każda wykrywa trwałą wadę w innym tempie).

### 27. Analogia z ruletką
- **Na czym polega:** w ruletce fizyka ruchu kulki daje przewagę: model z pomiarem prędkości dał oczekiwany zwrot +18%
  zamiast -2,7% ([Small i Tse, „Predicting the outcome of roulette”, Chaos 2012, arXiv:1204.6412](https://arxiv.org/pdf/1204.6412)),
  a lekko przechylone koło daje silną stronniczość. Historyczne przypadki: Joseph Jagger (Monte Carlo, XIX w.) i Gonzalo
  García-Pelayo (Madryt, lata 90.) - zapisywali wyniki i wykryli wadliwe koła; kasyna zaczęły zamieniać koła między stołami.
- **Czy przenośne na Lotto:** nie. W ruletce mierzy się ruch w trakcie gry i można postawić po wypuszczeniu kulki;
  w Lotto zakład zamyka się przed losowaniem, a maszyny i kule są rotowane. Zostaje tylko ślad w częstościach (pkt 26).
- **Test:** niemożliwy (brak kolejności wypadania i pomiarów fizycznych).

### Przypadki „pokonania loterii” (dla porządku)
Stefan Mandel wygrał kilkanaście razy, kupując (prawie) wszystkie kombinacje w loteriach z małą liczbą kombinacji i dużą
kumulacją, np. Wirginia 1992 (ok. 7 mln kombinacji) ([The Hustle](https://thehustle.co/the-man-who-won-the-lottery-14-times)).
To nie przewidywanie, tylko arbitraż: działa, gdy kumulacja przekracza koszt wszystkich zakładów, i dziś jest zakazane lub
niewykonalne. W Lotto 6/49 kupienie wszystkich 13 983 816 zakładów kosztowałoby prawie 70 mln zł.

## Inne

### 28. „AI wróżenie z fusów”, numerologia, daty urodzin [PSEUDONAUKA]
- Numerologia i „szczęśliwe liczby” nie mają czego mierzyć. Daty urodzin nic nie zmieniają w szansie, a pogarszają wypłatę
  (więcej osób gra 1-31, etap 2). SmileyNet (arXiv:2407.21385) to celowa satyra na takie pomysły.

## Jak liczymy (skrót metody z `symulacja.py`)
- Każda technika dostaje losowania po kolei; ranking 49 liczb na losowanie t powstaje, zanim program zobaczy losowanie t
  (ściśle bez podglądania przyszłości, sprawdzone testem). Rozgrzewka: pierwsze 500 losowań.
- Miary: ile z 6 wylosowanych liczb jest w top-k (k = 6, 12, 18, 24; los daje 6k/49), wirtualny wynik w zł (20 zakładów po 5 zł
  z top-12, nagrody 35 / 200 / 7 500 / 3 mln zł jak w RAPORT.md).
- Istotność: wobec 20 000 losowych rankingów; poprawka Holma na wszystkie techniki i k. Osobno lata 2010-2026 jako test poza próbą.
