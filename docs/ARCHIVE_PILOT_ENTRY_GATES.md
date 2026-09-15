# Bramy wejścia do pierwszego pilota archiwum

Stan: 15 września 2026. Ten dokument określa warunki uruchomienia małego pilota. Nie jest zgodą na pobieranie żadnego źródła.

## P0 — bez tego pilot nie rusza

### 1. Zatwierdzona instrukcja dostępu

Każda metoda jest opisana osobną, wersjonowaną kartą:

- źródło i host;
- kanał: API, RSS, sitemap albo HTML;
- konkretny endpoint lub ograniczony wzorzec URL;
- zakres pobrania: metadane, snapshot techniczny albo treść;
- link do pierwotnego dowodu oraz krótka notatka, co on potwierdza;
- minimalny odstęp, data ważności, autor przeglądu i status.

Ocena warunków źródła jest decyzją redakcyjno-prawną opartą na dowodzie, nie automatycznym „legal clearance” modelu. Brak aktualnej, zatwierdzonej karty blokuje request przed siecią. Kanały nie dziedziczą zgody.

### 2. Ślad każdego wyjścia do sieci

Przed skalowaniem potrzebujemy append-only `FetchAttempt` lub równoważnego, niezmiennego logu dla każdego requestu. Minimalny zapis:

- czas UTC, host, kanał i URL;
- identyfikator oraz wersja instrukcji dostępu;
- wynik preflightu albo HTTP status;
- czas odpowiedzi, Content-Type i rozmiar;
- ETag/Last-Modified, gdy serwer je zwraca;
- hash odpowiedzi lub bezpiecznego snapshotu technicznego;
- identyfikator workera.

Sukces HTTP bez zapisanego śladu jest błędem krytycznym: kolejny request do danego hosta zostaje zatrzymany do wyjaśnienia.

### 3. Jeden limit na cały host

RSS, sitemap, API i HTML tego samego hosta korzystają z jednego limitera. Rezerwacja następuje przed requestem, a kolejne okno otwiera się nie wcześniej niż po zakończeniu odpowiedzi plus zatwierdzony odstęp. `Retry-After` ma pierwszeństwo; 429 i powtarzalne 5xx uruchamiają wstrzymanie hosta.

Pilot sprawdza na atrapach transportu, że żadne dwa requesty tego samego hosta nie są bliżej niż ustalony limit. Wieloprocesowy limiter jest warunkiem dopiero przed uruchomieniem wielu procesów; lokalny pilot może działać przez jeden kontrolowany proces.

### 4. Minimalizacja danych i kategorie wykluczone

Pierwszy pilot obejmuje wyłącznie wcześniej zatwierdzone materiały instytucjonalne oraz metadane konieczne do działania boxów. Nie pobieramy komentarzy, forów, prywatnych profili, kontaktów ani danych, których nie potrzebujemy do kontekstu.

Nazwisko osoby pełniącej publiczną rolę w tytule materiału nie jest samo w sobie sygnałem do usunięcia. Numery telefonów, e-maile, adresy prywatne, numery identyfikacyjne i podobne dane przypadkowo zawarte w polach wejściowych są blokowane lub redagowane przed publicznym pokazaniem. Pełnotekstowy filtr PII należy wdrożyć przed włączeniem pełnych treści lub OCR.

### 5. Rozdzielenie zastosowań

Pozyskanie metadanych nie daje prawa do OCR, pełnego tekstu, RAG, zewnętrznego AI ani treningu. Te zastosowania mają niezależne, wersjonowane decyzje. Pierwszy pilot używa wyłącznie metadanych i linków.

## Warunki zatrzymania pilota

Pilota zatrzymujemy dla hosta, gdy wystąpi choć jedno z poniższych:

- request bez aktualnej instrukcji albo poza jej endpointem;
- brak śladu pobrania;
- naruszenie odstępu na hoście;
- 429 albo powtarzalny 403/5xx wymagający audytu;
- nieoczekiwane dane wrażliwe;
- zmiana warunków lub robots.txt wskazująca na konieczność ponownej oceny.

## Rozszerzanie

1. Jeden host, mała ograniczona próbka, pojedynczy proces.
2. Trzy źródła o osobno zatwierdzonych instrukcjach; obserwacja jakości i śladów.
3. Osiem źródeł po dwóch czystych sesjach pilota.
4. Dopiero potem wspólny limiter wieloprocesowy i stopniowe dojście do 32 niezależnych hostów.

Liczba workerów nie jest celem samym w sobie. Celem jest udokumentowany, powtarzalny i zgodny import.
