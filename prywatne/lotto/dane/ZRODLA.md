# Źródła danych Lotto

Stan na 22.10.2026. Fakty do sprawdzenia oznaczone [DP].

## Stan pobrania: dane jeszcze NIE są pobrane
Sesja w chmurze (22.10.2026) nie miała dostępu do żadnej strony z wynikami. Serwer pośredniczący sesji odrzucał
połączenia z lotto.pl, mbnet.com.pl, megalotto.pl, wynikilotto.net.pl, multipasko.pl, Wikipedią i web.archive.org
(odpowiedź 403 albo brak nazwy hosta). Otwarte były tylko rejestry pakietów (PyPI, npm). Tam są wyłącznie programy
pobierające wyniki, bez archiwum. Nie omijałem tej blokady.

Dlatego `dane/lotto.csv` powstaje na komputerze właściciela jednym poleceniem (w folderze `prywatne/lotto`):

    python lotto.py pobierz

Polecenie pobiera archiwum, sprawdza kompletność, porównuje losową próbkę 20 losowań z lotto.pl,
zapisuje wynik w `dane/kontrola.json`, a każdy odczyt w `dane/pobrania.log`. Potem `python analiza.py` liczy wszystko
od nowa na prawdziwych danych i podmienia wyniki w RAPORT.md.

## Źródła
| Co | Adres | Jak używane | Warunki |
|---|---|---|---|
| Pełna historia losowań od 27.01.1957 (numer, data, 6 liczb) | http://www.mbnet.com.pl/dl.txt | jeden plik, jeden odczyt na uruchomienie | publiczny plik tekstowy; przed odczytem program sprawdza robots.txt [DP: regulamin serwisu] |
| Druga strona porównania (20 losowań) i wysokości wygranych | lotto.pl, publiczne odczyty strony wyników (`/api/lotteries/draw-results/...`, `/api/lotteries/draw-prizes/...`) | 1 zapytanie na losowanie, 3 s przerwy | robots.txt sprawdzany w kodzie; oficjalny interfejs dla programistów wymaga klucza i konta, więc go nie używamy [DP: adresy i format odpowiedzi] |

Jeśli robots.txt któregoś źródła zabrania odczytu, program go pomija i zapisuje to w `dane/pobrania.log`.
Wtedy trzeba dopisać ten fakt do RAPORT.md i wskazać inne legalne źródło.

Wysokości wygranych: lotto.pl podaje je dla nowszych losowań [DP: od którego roku]. Gdy ich brakuje, analiza
przyjmuje średnie z tabeli niżej.

## Zasady gry (do automatu i do wyliczeń)
| Fakt | Wartość | Źródło |
|---|---|---|
| Cena zakładu | **5 zł od 18.08.2026** (wcześniej 3 zł, od 2009 r.) [DP] | [TVP Info](https://www.tvp.info/94928475/lotto-2026-cena-zakladu-wzrosla-sprawdz-nowe-ceny-i-wygrane), [Bankier](https://www.bankier.pl/wiadomosc/Lotto-podrozalo-Wieksza-pula-na-glowna-wygrana-i-wyzsza-trojka-9184259.html) |
| Dni losowań | wtorek, czwartek, sobota, 22:00 [DP] | [TVP Info](https://www.tvp.info/94928475/lotto-2026-cena-zakladu-wzrosla-sprawdz-nowe-ceny-i-wygrane) |
| Trójka (3 trafienia) | 35 zł, stała (wcześniej 24 zł) [DP] | [Bankier](https://www.bankier.pl/wiadomosc/Lotto-podrozalo-Wieksza-pula-na-glowna-wygrana-i-wyzsza-trojka-9184259.html), [TVN24 20.10.2026](https://tvn24.pl/biznes/pieniadze/lotto-i-lotto-plus-wyniki-i-wygrane-z-20-pazdziernika-2026-oto-liczby-z-ostatniego-losowania-st9297475) |
| Czwórka | zmienna, ok. 200 zł (20.10.2026: 217,80 zł) [DP] | [TVP Info](https://www.tvp.info/94928475/lotto-2026-cena-zakladu-wzrosla-sprawdz-nowe-ceny-i-wygrane), [Multipasko](https://www.multipasko.pl/news-podwyzka-ceny-zakladu-lotto-238.html) |
| Piątka | zmienna, ok. 7-8 tys. zł (20.10.2026: 8 673 zł) [DP] | [TVP Info](https://www.tvp.info/94928475/lotto-2026-cena-zakladu-wzrosla-sprawdz-nowe-ceny-i-wygrane) |
| Szóstka | pula co najmniej 3 mln zł (wcześniej 2 mln), dzielona między zwycięzców [DP] | [TVP Info](https://www.tvp.info/94928475/lotto-2026-cena-zakladu-wzrosla-sprawdz-nowe-ceny-i-wygrane) |
| Podatek | 10% od całej wygranej, gdy jednorazowa wygrana przekracza 2280 zł; pobiera go organizator (art. 30 ust. 1 pkt 2 i art. 21 ust. 1 pkt 6a ustawy o PIT) [DP] | [Infor](https://ksiegowosc.infor.pl/podatki/podatki-osobiste/pit/291601,podatek-od-wygranej-w-lotto.html), [money.pl](https://www.money.pl/podatki/poradniki/artykul/pit-podatek-od-wygranej-w-grach-losowych,156,0,2286748.html) |

Źródła prasowe nie zastępują regulaminu: przed prawdziwą grą sprawdź cennik i regulamin na lotto.pl.

## Popularność liczb (do strategii `rzadko_grane`)
- J. Simon, *An Analysis of the Distribution of Combinations Chosen by UK National Lottery Players*,
  Journal of Risk and Uncertainty 17(3), 1998, s. 243-276: gracze nie wybierają losowo, tylko według własnych sposobów
  ([IDEAS](https://ideas.repec.org/a/kap/jrisku/v17y1998i3p243-76.html)).
- S. Cox, G. Daniell, D. Nicole, *Using maximum entropy to double one's expected winnings in the UK National Lottery*,
  JRSS Series D, 1998: rzadko wybierane zestawy mogą podwoić oczekiwaną wygraną w stopniach dzielonych
  ([Southampton](https://eprints.soton.ac.uk/250895)) [DP: dokładny tytuł].
- Badania belgijskiego Lotto (UCLouvain, 2024): gracze wolą liczby poniżej 30 (urodziny) i liczby pierwsze, co obniża
  ich średni zwrot w grze z dzieloną pulą ([IDEAS](https://ideas.repec.org/p/ajf/louvlr/2024002.html)) [DP: autorzy].
- H. Riedwyl, analiza szwajcarskiego Lotto: popularne są liczby do 31 i wzorki na kuponie
  ([City AM](https://cityam.com/?p=354401)) [DP: oryginalna publikacja].

Wniosek z tych prac: rzadko wybierane liczby **nie zwiększają szansy trafienia**, tylko zmniejszają liczbę osób,
z którymi dzieli się wygraną 4, 5 albo 6 (trójka w Polsce jest stała, więc tam to nic nie daje).
