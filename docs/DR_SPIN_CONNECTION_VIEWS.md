# Dr Spin — „co łączy X z Y?”

## Cel

Dr Spin ma pomóc zobaczyć udokumentowany kontekst dwóch osób, instytucji lub tematów. Nie orzeka, że istnieje relacja, jeśli baza pokazuje wyłącznie wspólną wzmiankę albo zbieżność czasu.

Każdy wynik prowadzi do źródeł. Box jest przypisem: pokazuje tytuł, źródło, datę, typ materiału i odsyła do oryginalnego URL.

## Zasada języka

Interfejs nazywa dokładnie to, co stwierdza:

- **współwystępowanie** — X i Y występują w tym samym boxie;
- **zbieżność czasowa** — materiały o X i Y wystąpiły w tym samym okresie;
- **zatwierdzona relacja** — relacja ma wskazany dowód;
- **wspólny podmiot** — najkrótsza udokumentowana ścieżka prowadzi przez osobę, organizację albo dokument;
- **brak potwierdzenia** — baza nie daje podstawy do pokazania relacji.

Nigdy nie zastępujemy tych określeń słowami sugerującymi intencję, winę, współpracę, spór albo przyczynowość, jeżeli nie ma dla nich odrębnego dowodu.

## Widok 1 — oś zbieżności (MVP)

Pytanie: **„Kiedy X i Y pojawiali się w tym samym kontekście?”**

Użytkownik widzi dwa spokojne tory czasu oraz wspólne punkty. Kliknięcie punktu rozwija boxy: tytuł, wydawcę, datę, typ i link. Podsumowanie mówi np. „12 udokumentowanych współwystąpień”, nigdy „12 dowodów relacji”.

Dane: metadane boxów, daty, źródła i zatwierdzone relacje. Bez pełnych tekstów, cytatów i streszczeń.

Niepewność: niepotwierdzona data ma przerywany znacznik; wspólna wzmianka ma etykietę „charakter relacji nieustalony”.

## Widok 2 — drzewo dowodów (MVP po zasileniu relacji)

Pytanie: **„Jaka jest najkrótsza udokumentowana ścieżka między X i Y?”**

Użytkownik widzi prostą ścieżkę: X → dokument, osoba albo instytucja → Y. Każdy krok ma co najmniej jeden box-dowód. Kliknięcie rozwija metadane i linki, bez kopiowania artykułu.

Dokumenty urzędowe są oddzielnie oznaczone od prasy. Brak podstawy treściowej pokazujemy jako „uzasadnienie niedostępne”; nie wypełniamy luki domysłem.

Niepewność: pełna linia oznacza relację potwierdzoną przez dokument lub wiele niezależnych dowodów; przerywana — pojedynczy dowód; brak dowodu — brak krawędzi.

## Widok 3 — graf narracji (faza 2)

Pytanie: **„Kto, gdzie i jak często łączył te tematy?”**

Użytkownik widzi maksymalnie kilkanaście węzłów: X, Y, autorów, wydawców i wspólne dokumenty. Grubość linii pokazuje liczbę boxów, a nie „siłę” ani prawdziwość relacji. Kliknięcie otwiera listę właściwych boxów.

Dane: autor, źródło, data, typ materiału, zatwierdzone relacje i dokumenty. Bez rekonstrukcji cudzej narracji z pełnych tekstów.

## Widok 4 — karta Dr Spina (faza 3)

Pytanie: **„Co można potwierdzić, a czego nie?”**

AI układa kilka sprawdzalnych zdań, a każde prowadzi do konkretnego dowodu. Karta zawsze ma część „ograniczenia analizy”. Model dostaje tylko dane, na których użycie pozwala aktualna decyzja dla źródła; bez takiej decyzji pracuje wyłącznie na metadanych i zatwierdzonych relacjach.

## Kolejność wdrożenia

1. Oś zbieżności z metadanych.
2. Drzewo dowodów po przygotowaniu ręcznie zatwierdzonych relacji.
3. Graf narracji i konta użytkowników.
4. Karta AI Dr Spina po zbudowaniu wystarczającego, dozwolonego zbioru danych.

W każdym etapie źródło jest pierwsze, kontekst jest widoczny, a granica wiedzy systemu pozostaje jawna.
