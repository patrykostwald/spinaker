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
