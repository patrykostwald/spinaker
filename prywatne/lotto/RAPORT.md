# Czy da się przechytrzyć Lotto? Raport z eksperymentu (wirtualne pieniądze)

Stan: 22.10.2026. Fakty do sprawdzenia oznaczone [DP], źródła w `dane/ZRODLA.md`.

## Najważniejsze w 5 zdaniach
1. Nie da się. Każdy zestaw 6 liczb ma tę samą szansę: 1 do 13 983 816. Żadna strategia tego nie zmienia.
2. Z każdych 5 zł postawionych w Lotto wraca średnio ok. 1,16 zł (ok. 23%), licząc szóstkę jako 3 mln zł [DP].
   Nawet średnia szóstka 8-12 mln zł podnosi tę kwotę tylko do ok. 1,50-1,80 zł, bo szóstka zdarza się tak rzadko.
3. Grając wirtualnie za 100 zł na losowanie, tracisz średnio ok. 77 zł na losowanie i ok. 230 zł na tydzień (3 losowania).
4. „Mądre” strategie (gorące, zimne, bez dawnych szóstek) dają w testach ten sam wynik co czysty los.
5. Jedyny realny zysk: rzadko wybierane liczby zmniejszają ryzyko **dzielenia** nagrody z innymi, ale nie zwiększają szansy wygranej.

## Ważne: dane
Sesja w chmurze nie miała dostępu do stron z wynikami (blokada sieci, szczegóły w `dane/ZRODLA.md`).
Liczby z części „Wyniki testów” pochodzą więc z **symulacji**: komputer uczciwie wylosował 7 300 losowań, tyle ile
mniej więcej było ich od 1957 r. [DP]. Pokazuje to metodę i skalę wyników. Prawdziwe wyniki: na swoim komputerze
w folderze `prywatne/lotto` uruchom kolejno:

    python lotto.py pobierz
    python analiza.py

Drugie polecenie podmieni część „Wyniki testów” na liczby z prawdziwej historii (ok. 2 minuty).

## Werdykt dla każdej strategii
| Strategia | Na czym polega | Werdykt |
|---|---|---|
| `historia` | nie gra zestawów, które już kiedyś padły | Nic nie daje. Dawna szóstka ma tę samą szansę co każda inna; takich zestawów jest ok. 7 300 na prawie 14 mln. Powtórki szóstek **muszą** się czasem zdarzać: przy 7 300 losowaniach rachunek przewiduje średnio ok. 1,9 powtórki. |
| `gorace` | liczby najczęstsze w ostatnich 50 losowaniach | Nic nie daje. Kule nie pamiętają poprzednich losowań. |
| `zimne` | liczby najrzadsze w ostatnich 50 losowaniach | Nic nie daje. Liczba nie „należy się” po przerwie. |
| `rzadko_grane` | liczby powyżej 31, bez ciągów i wzorków na kuponie | Ta sama szansa trafienia. Przy trafieniu 4, 5 lub 6 mniej osób dzieli nagrodę, więc wypłata może być wyższa (badania z Wielkiej Brytanii i Belgii). Trójka jest stała (35 zł), więc tam nic nie zmienia. Najlepsza z pięciu, ale nadal na minusie. |
| `los` | czysty los | Punkt odniesienia. Tyle samo co pozostałe. |

## Ile to kosztuje (dzisiejsze zasady: zakład 5 zł, 3 trafienia = 35 zł, 4 ≈ 200 zł, 5 ≈ 7 500 zł, 6 ≥ 3 mln zł) [DP]
| Gra za 100 zł na losowanie (20 zakładów) | Kwota |
|---|---|
| Średnio wraca na losowanie | ok. 23 zł |
| Średnia strata na losowanie | ok. 77 zł |
| Średnia strata na tydzień (3 losowania, 300 zł) | ok. 230 zł |
| Średnia strata w rok (156 losowań, 15 600 zł) | ok. 12 000 zł |
| Szansa na choć jedną trójkę w losowaniu | ok. 30% |
| Szansa na szóstkę w ciągu roku takiej gry | ok. 0,02% (raz na ok. 4 500 lat) |

**Podatek** [DP]: wygrana do 2 280 zł jest bez podatku. Powyżej organizator sam potrąca 10% od całej kwoty
(np. piątka 7 500 zł - na rękę 6 750 zł; szóstka 3 mln zł - na rękę 2,7 mln zł). Nie trzeba składać osobnego PIT.

**Co by się stało przy prawdziwej grze:** te same liczby, tylko w prawdziwych złotówkach. Po roku gry za 100 zł na losowanie
najbardziej prawdopodobny wynik to ok. 12 000 zł mniej na koncie i kilkadziesiąt trójek.
Automat w tym folderze nigdy nie kupuje kuponów - wszystko dzieje się na papierze.

## Jak grać odpowiedzialnie, jeśli w ogóle
- Traktuj Lotto jak bilet do kina: płacisz za emocje, nie inwestujesz.
- Ustal stały limit na miesiąc (np. 30 zł) i nigdy go nie podnoś po przegranej („odgrywanie się” to pierwszy sygnał problemu).
- Stop: gdy grasz za pieniądze potrzebne na rachunki, ukrywasz granie albo myślisz o nim codziennie.
- Pomoc: telefon zaufania uzależnień behawioralnych (także hazard) 801 889 880, codziennie 17-22;
  bezpłatny Ogólnopolski Telefon Zaufania Uzależnienia (KCPU) 800 199 990, codziennie 16-21 [DP].

## Wyniki testów (generuje `analiza.py`)
<!-- WYNIKI-ANALIZY: START (plik generuje analiza.py, nie edytuj ręcznie) -->

Wygenerowano 2026-10-22 18:30. Dane: **SYMULACJA** - prawdziwych danych jeszcze nie pobrano (dane/ZRODLA.md); losowania wygenerował komputer, więc wyniki pokazują metodę i skalę, nie historię Lotto.

**1. Powtórki szóstek.** Zestawy, które padły więcej niż raz: 6-8-16-30-32-33, 3-9-29-36-39-43, 3-21-24-27-36-37. Przy 7300 losowaniach rachunek daje średnio 1.91 powtórki (szansa, że choć jedna się zdarzy: 85%).

**2. Równomierność (chi-kwadrat, 48 st. swobody, poprawka na losowanie bez zwracania).** Wynik 48.09, p = 0.4694. Najczęstsza liczba 41 (950 razy), najrzadsza 33 (826), oczekiwane 893.9. Brak dowodu na nierówność (p > 0,05).

**3. Backtest: 33 zakłady na losowanie, okno kroczące, ceny i nagrody według dzisiejszych zasad** (zakład 5 zł; 3 = 35 zł, 4 ≈ 200 zł, 5 ≈ 7 500 zł, 6 = 3 mln zł) [DP]. Teoria: 0.7347 trafienia na zakład, zwrot 23.3% stawki.

| Strategia | Śr. trafień (95%) | z | 3 / 4 / 5 / 6 trafień | Wydane | Wygrane | Zwrot | Bilans na losowanie bez szóstek (95%) |
|---|---|---|---|---|---|---|---|
| `historia` | 0.7338 (0.7308-0.7369) | -0.57 | 4149 / 211 / 5 / 0 | 1 196 250 zł | 224 915 zł | 18.8% | -133.98 zł (-138.59 do -129.36) |
| `gorace` | 0.7335 (0.7305-0.7366) | -0.76 | 4253 / 212 / 4 / 0 | 1 196 250 zł | 221 255 zł | 18.5% | -134.48 zł (-138.70 do -130.27) |
| `zimne` | 0.7366 (0.7336-0.7396) | +1.23 | 4177 / 220 / 6 / 0 | 1 196 250 zł | 235 195 zł | 19.7% | -132.56 zł (-137.64 do -127.48) |
| `rzadko_grane` | 0.7369 (0.7339-0.7400) | +1.45 | 4315 / 231 / 6 / 0 | 1 196 250 zł | 242 225 zł | 20.2% | -131.59 zł (-136.65 do -126.53) |
| `los` | 0.7333 (0.7303-0.7363) | -0.89 | 4167 / 207 / 4 / 0 | 1 196 250 zł | 217 245 zł | 18.2% | -135.04 zł (-139.19 do -130.88) |

Oczekiwane z rachunku przy tej liczbie zakładów: 3 / 4 / 5 / 6 = 4222.9 / 231.7 / 4.4 / 0.0. Limit najwyżej 2 wspólnych liczb między zakładami: naruszeń 0. |z| < 2 oznacza: strategia nie różni się od losu.

<!-- WYNIKI-ANALIZY: KONIEC -->

## Jak działa automat
- `python lotto.py generuj` - kupony wszystkich strategii (po 20 zakładów = 100 zł) na najbliższe losowanie w `kupony/<data>.json`,
  z godziną zapisu i sumą kontrolną SHA-256; istniejących kuponów nie nadpisuje.
- `python lotto.py sprawdz` - wyniki zaległych losowań, trafienia i wirtualne wygrane do `DZIENNIK.csv`.
- `python lotto.py raport` - wydane, wygrane i bilans dla strategii i łącznie.
- `zadanie_windows.ps1` - uruchamia to samo samo z siebie (wt/czw/sob przed i po losowaniu, rano na wypadek wyłączonego komputera).
