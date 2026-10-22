# Lotto, etap 3: przegląd technik przewidywania i wielka symulacja (23.10.2026, prywatne)

Gałąź `cloud/prywatne-lotto`, folder `prywatne/lotto/etap3/`. Dane: `dane/lotto.csv` (7420 losowań 1957-2026). Sesja nie ma
dostępu do stron z wynikami, ale wyszukiwarka działa - research rób wyszukiwaniem.

## Pytanie właściciela
„Czy są jakiekolwiek, choćby nowe trendy w nauce, żeby zawęzić okno wypadających liczb? Wybierz techniki, zrób listę,
przeprowadź symulacje każdej metody osobno, a potem połączonych. Spróbujmy wszystkiego.”

## Część 1: research (`TECHNIKI.md`)
Znajdź i opisz co najmniej 20 technik z różnych źródeł: systemy graczy (częstości, „zaległe” liczby, delta, sumy, parzyste i
nieparzyste, pozycje, pary, koła), statystyka (rozkłady, łańcuchy Markowa, bayes, entropia), uczenie maszynowe (regresja
logistyczna, lasy losowe, gradient boosting, sieci LSTM i transformery, uczenie ze wzmocnieniem, algorytmy genetyczne,
klastrowanie), badania fizyczne (stronniczość maszyn i kul, analogie z ruletką), prace naukowe i repozytoria z ostatnich lat
(arXiv, GitHub, Kaggle - z linkami). Przy każdej: na czym polega, skąd (link), co obiecuje, czy ktoś ją rzetelnie zweryfikował,
i jak ją przetestujemy na naszych danych. Oznacz wprost pseudonaukę.

## Część 2: symulacja (`symulacja.py`, wyniki w `etap3/wyniki/`)
- Każda technika jako funkcja: wejście = losowania DO dnia t, wyjście = ranking 49 liczb (albo zestaw liczb). Ściśle bez
  podglądania przyszłości (walk-forward), rozgrzewka np. 500 losowań.
- Miary na każdym losowaniu: ile z 6 wylosowanych liczb trafia w top-k rankingu dla k = 6, 12, 18, 24 (los: 6k/49),
  średnie trafienia zakładu z top-6, wirtualny wynik w zł (20 zakładów po 5 zł, nagrody jak w RAPORT.md).
- Istotność: test permutacyjny / bootstrap wobec losowego rankingu, z poprawką na wielokrotne testy (Holm albo FDR
  na wszystkie techniki i k). Osobno okres 2010-2026 (nowe maszyny) jako test poza próbą.
- Połączenia: głosowanie rang (Borda), średnia, stacking z modelem uczonym tylko na przeszłości, najlepsza para i trójka technik.
  Uwaga na przeuczenie: wybór połączeń na latach do 2009, ocena na 2010-2026.
- Modele ML trzymaj w rozsądnych rozmiarach (CPU, całość do ok. 60 minut obliczeń); numpy i scikit-learn dozwolone,
  jeśli trzeba, `pip install scikit-learn` (bez innych instalacji).

## Część 3: `RAPORT3.md` (prosty język, na górze werdykt)
Tabela wszystkich technik i połączeń: trafienia w top-12 (los = 1,47), różnica z przedziałem ufności, p po poprawce, wynik w zł,
werdykt. Jasne zdanie: czy którakolwiek metoda zawęża okno w sposób istotny i powtarzalny. Jeśli coś przejdzie test poza próbą,
dodaj ją jako strategię do automatu (`strategie.py`) z testem; jeśli nic - napisz to wprost.
Dopisz krótką sekcję do strony (`strona.py`): „Etap 3: N technik, wynik”, bez zmiany reszty strony.

Testy pytest dla nowych funkcji (szczególnie brak podglądania przyszłości). Commit i push po każdej części (pierwsza linia bez
polskich znaków, na końcu `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Celuj w ok. 2 godziny. W ostatniej
wiadomości najwyżej 12 linii.

## Część 2b: zakłady systemowe (dopisek właściciela, 23.10)
Lotto pozwala skreślić od 7 do 12 liczb (zakład systemowy) [DP: potwierdź regulamin Lotto]. To C(n,6) zwykłych zakładów naraz:
7 liczb = 7 zakładów, 8 = 28, 9 = 84, 10 = 210, 11 = 462, 12 = 924 (koszt = liczba zakładów x cena jednego zakładu z RAPORT.md).
System nie zmienia szansy na złotówkę, ale jest naturalnym sposobem wykorzystania „zawężonego okna”: jeśli top-n rankingu zawiera
3, 4, 5 albo 6 wylosowanych liczb, system n wygrywa naraz wiele stopni.
- Dla każdej techniki i połączenia, dla n = 7..12: jak często top-n zawierało co najmniej 3, 4, 5, 6 wylosowanych liczb, wobec losu
  (rozkład hipergeometryczny; np. wszystkie 6 w losowej dwunastce: 924 / 13 983 816, ok. 1 na 15 134).
- Wirtualny wynik w zł systemów 7..12 na historii (wszystkie wygrane z rozpisanych zakładów, koszt jak wyżej), na złotówkę wobec
  zwykłych zakładów i wobec losowego systemu.
- W budżecie 100 zł na losowanie sprawdź wariant „2 systemy po 7 liczb + 6 zwykłych zakładów” z najlepszego rankingu i dodaj go
  do tabeli w RAPORT3.md. Do automatu trafia tylko, jeśli ranking przejdzie test poza próbą; inaczej dodaj „system 7 z losu” jako
  wariant porównawczy z opisem, że to ta sama szansa, inaczej rozłożona.
