# Eksperyment Lotto - automat na wirtualnych pieniądzach (prywatny, nie iapply)

Zleceniodawca: właściciel (prywatnie, dla znajomego). Koordynator: Kai. Pracujesz na gałęzi `cloud/prywatne-lotto`,
wyłącznie w folderze `prywatne/lotto/`. Nigdy nie łączysz tej gałęzi z kodem iapply.

## Cel
Sprawdzić uczciwie, na danych, czy da się „przechytrzyć” Lotto (6 z 49, Totalizator Sportowy), i postawić automat, który
przy każdym losowaniu gra WIRTUALNIE za 100 zł kilkoma strategiami naraz, a po losowaniu liczy wyniki. Żadnych prawdziwych
pieniędzy, żadnych kuponów, żadnych kont.

## Zasady
- Dane tylko z oficjalnych źródeł albo publicznych archiwów wyników, z poszanowaniem regulaminu i robots.txt (pojedyncze odczyty,
  przerwy między zapytaniami, nagłówek User-Agent z opisem). Nie logujesz się, nie zakładasz kont, nie omijasz zabezpieczeń.
  Jeśli źródło zabrania automatycznego pobierania, zapisz to w RAPORT.md i użyj innego legalnego źródła.
- Nie czytasz plików .env, nie zmieniasz niczego poza `prywatne/lotto/`. Bez PR, bez wdrożeń, bez powiadomień.
- Każda liczba w raporcie ma źródło albo jest wyliczona w kodzie. Fakty do sprawdzenia oznacz [DP]. Nie obiecujesz wygranych.
- Python 3.11+, biblioteka standardowa (numpy dozwolone), testy pytest.

## Część 1: dane
Pełna historia losowań Lotto (numer, data, 6 liczb) w `dane/lotto.csv` + `dane/ZRODLA.md` (skąd, kiedy pobrane, warunki
korzystania). Sprawdź kompletność (liczba losowań, luki, duplikaty) i porównaj losową próbkę 20 losowań z drugim źródłem.
Jeśli są dostępne, zbierz też wysokości wygranych (stopnie 3, 4, 5, 6) dla każdego losowania.
Sprawdź aktualną cenę zakładu Lotto i dni losowań [DP, ze źródłem].

## Część 2: testy hipotez (`analiza.py`, wyniki w RAPORT.md)
1. Czy pełna szóstka kiedykolwiek się powtórzyła; ile powtórek wynika z rachunku prawdopodobieństwa przy tej liczbie losowań.
2. Test chi-kwadrat: czy liczby wypadają równomiernie.
3. Backtest na całej historii (okno kroczące, bez podglądania przyszłości), 33 zakłady na losowanie dla każdej strategii:
   - `historia` - zestawy wylosowane z puli bez dawnych szóstek (pomysł właściciela),
   - `gorace` - najczęstsze liczby z ostatnich N losowań,
   - `zimne` - najrzadsze liczby z ostatnich N losowań,
   - `rzadko_grane` - liczby i układy, które gracze wybierają rzadko (więcej liczb powyżej 31, bez ciągów, bez wzorków na kuponie,
     bez dawnych szóstek), żeby przy wygranej mniej dzielić nagrodę; podaj źródła o popularności liczb (badania lotto w innych krajach),
   - `los` - czysty los jako punkt odniesienia.
   Dla każdej: średnia liczba trafień na zakład (teoria: 6*6/49 = 0,7347), rozkład 3/4/5/6 trafień, wirtualny wynik w zł
   (stawka, wygrane według historycznych wysokości nagród albo średnich, jeśli brak), przedział ufności i wniosek prostym językiem.
4. Między zakładami jednej strategii najwyżej 2 wspólne liczby (żeby nie dublować tych samych szans).

## Część 3: automat (`lotto.py`)
- `python lotto.py generuj` - dla najbliższego losowania zapisuje kupony wszystkich strategii do `kupony/<data>.json`
  z godziną zapisu i sumą kontrolną SHA-256 (blokada: nie nadpisuje istniejących kuponów).
- `python lotto.py sprawdz` - pobiera wyniki losowań, których jeszcze nie sprawdzono (także zaległe), liczy trafienia i wirtualne
  wygrane każdej strategii, dopisuje do `DZIENNIK.csv`.
- `python lotto.py raport` - podsumowanie: wydane, wygrane, bilans, trafienia, dla każdej strategii i łącznie.
- `zadanie_windows.ps1` - skrypt rejestrujący w Harmonogramie zadań Windows dwa zadania (generuj przed losowaniem, sprawdz po nim
  i rano następnego dnia na wypadek wyłączonego komputera). NIE uruchamiaj go - właściciel zrobi to lokalnie.
- Testy pytest: generator (liczby 1-49, bez powtórzeń w zakładzie, limit nakładania), sprawdzanie trafień, blokada nadpisania.

## Część 4: RAPORT.md (prosty język, dla laika)
Werdykt dla każdej strategii, wartość oczekiwana na losowanie i na tydzień przy 100 zł, podatek od wygranych w Polsce [DP, źródło],
co by się stało przy prawdziwej grze, jak grać odpowiedzialnie (limit, stop). Najwyżej 2 strony.

## Git
Po każdej części commit i push na `cloud/prywatne-lotto` (pierwsza linia bez polskich znaków, na końcu linia
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Celuj w ok. 90 minut pracy. W ostatniej wiadomości najwyżej 15 linii.
