# Lotto, etap 2: strona z podglądem i głębsze szukanie przewagi (22.10.2026, prywatne)

Gałąź `cloud/prywatne-lotto`, folder `prywatne/lotto/`. Dane są już w repo: `dane/lotto.csv` (7420 losowań, 1957-2026),
kupony w `kupony/`, analiza w `wyniki/analiza.json`. Sesja w chmurze nie ma dostępu do stron z wynikami - pracuj na plikach.
Raport z przeglądu gier: `git show origin/cloud/prywatne-hazard:prywatne/hazard-przeglad/RAPORT.md`.

## Część A: czy da się zwiększyć szansę trafienia? (`analiza2.py`, wynik w `RAPORT2.md`)
Właściciel pyta wprost, czy jest jakikolwiek sposób. Sprawdź uczciwie wszystko, co mogłoby dać przewagę, jeśli losowanie
nie jest idealnie losowe, i powiedz jasno, co wyszło:
1. Nierówność liczb w epokach (np. dekady, zmiany maszyn i zestawów kul [DP: daty z historii Lotto]) - chi-kwadrat z poprawką
   na wielokrotne testy (np. Bonferroni / FDR).
2. Pary i trójki liczb padające częściej niż z rachunku (z poprawką na wielokrotne testy).
3. Zależność od poprzednich losowań (autokorelacja, powtórzenia liczb z poprzedniego losowania, sumy, parzyste/nieparzyste,
   niskie/wysokie) w porównaniu z symulacją Monte Carlo idealnie losowych losowań.
4. Test „przewidywania”: model uczony na danych do roku X (np. częstości, prosty model statystyczny), sprawdzany na danych po X
   (bez podglądania przyszłości). Porównaj z losem; podaj, czy różnica jest istotna.
5. Rzeczy, które NIE zwiększają szansy, a zwiększają wypłatę lub pewność drobnych wygranych: rozpisanie zakładów, żeby nie dublować
   liczb (systemy pokrycia), wybór rzadko granych liczb (mniej dzielenia nagrody). Wyjaśnij różnicę między „szansą” a „wypłatą”.
Werdykt prostym językiem na początku RAPORT2.md: co działa, co nie, z liczbami. Jeśli coś okaże się istotne, zaproponuj
strategię `wykryta_nierownosc` i dodaj ją do automatu (`strategie.py`) z testem; jeśli nic - napisz to wprost.

## Część B: strona z podglądem (`strona.py`)
`python strona.py` generuje do `strona/lotto/` pliki `index.html` (jeden plik, CSS i JS w środku, bez zewnętrznych skryptów)
i `dane.json`. Strona pokazuje:
- ostatnie losowanie i najbliższe, kupony każdej strategii na najbliższe losowanie (zablokowane przed losowaniem, z godziną zapisu
  i sumą kontrolną),
- dziennik eksperymentu: dla każdej strategii wydane, wygrane, bilans, trafienia 3/4/5/6, wykres bilansu w czasie,
- wnioski z testu na historii (analiza.json) i z części A,
- skrót przeglądu gier (tabela ocen z RAPORT.md przeglądu) z odnośnikiem do pełnego raportu (wygeneruj też `strona/lotto/przeglad.html`),
- wyraźną informację: „eksperyment na wirtualnych pieniądzach, żadna strategia nie zwiększa szansy”, oraz o odpowiedzialnej grze
  (18+, telefon zaufania dla osób z problemem hazardowym [DP: aktualny numer]).
Design: czysto, ciemny motyw, najwyżej 2 kroje, boksy równe i dociągnięte, czytelnie na telefonie (390 px). `noindex, nofollow`.
Bez nazw osób, bez linków afiliacyjnych, bez reklam operatorów.

## Część C: aktualizacja po losowaniu
Dopisz do `lotto.py sprawdz` (albo osobne `lotto.py strona`) generowanie strony po każdym sprawdzeniu. Wdrożenie na serwer zrobi
koordynator lokalnie - Ty tylko generujesz pliki.

Testy pytest dla strona.py i nowych funkcji. Commit i push po każdej części (pierwsza linia bez polskich znaków, na końcu
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Celuj w ok. 90 minut. W ostatniej wiadomości najwyżej 12 linii.
