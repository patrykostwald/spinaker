# Demo wyszukiwania hybrydowego — 9 września 2026

Podgląd lokalny: http://localhost:3000/search. Jedno hasło lub URL uruchamia niezależnie wyszukiwanie zapisanych rekordów i — po konfiguracji API — wyszukiwanie internetowe AI. Nie trzeba czekać na zakończenie importu archiwów.

## Działanie

1. Baza odpowiada od razu, wraz z filtrami dat i kategorii oraz odpowiedziami o głosowaniach z danych Sejmu. URL wyszukuje konkretny zapisany adres.
2. Strumień Responses przekazuje rzeczywiste etapy pracy web_search i adresy odnalezione w aktywnym katalogu źródeł. Nie transmitujemy niezweryfikowanych strzępów tekstu modelu jako faktów.
3. Znaleziony URL trafia do kolejki z priorytetem. Link bez odczytanych metadanych jest widoczny w osobnej grupie. Nie ma zmyślonej daty ani miniatury.
4. Metadane odczytane u wydawcy są scalane z wynikami lokalnymi: jedna karta rekordu, sortowanie po dacie publikacji, brak dat osobno. Filtry dotyczą sklasyfikowanych rekordów; nie ukrywają odnalezionych URL o nieustalonych danych. Priorytetowy odczyt działa jako zadanie research-metadata co 10 sekund w tym samym procesie co import archiwów. Ma najwyżej 3 wykonawców, do 15 adresów i budżet czekania 20 sekund; nie obiecuje odczytania wszystkich trafień. Serwer WWW tylko kolejkuje i odczytuje bazę, więc nie uruchamia konkurencyjnego crawlera z osobnymi ograniczeniami domen.
5. Cytowane materiały z datami tworzą szkic kontekstu do 15 boxów, od najstarszego. Nie obiecujemy kompletnego początku historii ani obiektywnego rankingu wszystkich wydarzeń.
6. Przycisk Zatrzymaj zamyka połączenie klienta i dalsze odświeżanie tej sesji. Przyjęte zadania archiwum mogą skończyć się w tle. Anulowanie nie cofa kosztu poniesionego u dostawcy. Ponowienie jest osobną, świadomą próbą.

Wyniki lokalne mają cache do 5 sekund (wcześniej 5 minut). Pierwsza strona jest odświeżana co 5 sekund w aktywnej karcie, z możliwością wyłączenia. Po rozwinięciu starszych stron automatyczne odświeżanie stron jest wstrzymane, aby nie przeliczać całego długiego wyniku. Odnalezione URL są odczytywane ponownie z bazy przez najwyżej 150 sekund; później pozostają w kolejce archiwum.

## Rzetelność i ograniczenia

- Wyłącznie bieżąca lista aktywnych źródeł; sam model nie dodaje wydawców ani faktów z pamięci do rekordów.
- Jedno wyszukiwanie ma ograniczenia budżetu: do 4 wywołań narzędzia i 4000 tokenów odpowiedzi, do 30 pokazywanych odnośników oraz do 15 materiałów w szkicu. Nie oznacza przeszukania wszystkich stron każdego wydawcy. Kolejne szersze przebiegi wymagają pomiaru kosztów pilotażu.
- Surowy tekst AI trafia do notatki dopiero po walidacji cytowań do adresów zgłoszonych przez narzędzie; obecność cytowania nie potwierdza prawdziwości zdania. Szkic nie jest automatycznie publikowaną nitką redakcyjną.
- Strumień ma trwały identyfikator UUID blokujący podwójne płatne przyjęcie tego samego żądania. Błędy i próby przerwane również liczą się do budżetu dziennego.
- Publiczny licznik pokazuje rzeczywiste rekordy i skonfigurowane aktywne źródła. Stan „Importery działają” wymaga świeżego sygnału z procesu. Nie deklarujemy osiągnięcia największej bazy ani kompletności.
- Obecny lokalny serwer Django działa przez WSGI. Proxy Next.js ma timeout 130 sekund (domyślne 30 sekund było krótsze od limitu analizy). Wdrożenie na ASGI wymaga adaptacji iteratora strumienia; proxy produkcyjne nie może buforować SSE.

## Co działa i co pozostaje

Wyszukiwanie lokalne i frontend sprawdzone na prawdziwej bazie. Obsługa SSE, dopływania linków, ich zastępowania kartami, anulowania i zmiany hasła przetestowana z odizolowaną symulacją dostawcy w przeglądarce; symulacja nie zapisuje rekordów w bazie i nie jest publicznym trybem demo.

Na 9 września nie skonfigurowano klucza/modelu/salda API. Nie wykonano płatnego zapytania ani nie potwierdzono trafności wyszukiwania na żywym koncie. Instrukcja: AI_START_CHECKLIST_PL.md. Po podłączeniu potrzebny pilot prawdziwych tematów i odczyt kosztu, czasu oraz jakości źródeł.

Dowody: reports/live-search-browser.json, reports/live-search-desktop.png, reports/live-search-mobile.png. Import archiwów, kontrola źródeł, jakość, import urzędowy i kopie lokalne są obsługiwane przez istniejący run_local_jobs; nie uruchamiamy drugiego schedulera.

Końcowy pomiar kolejki priorytetowej: po wykorzystaniu podzapytania ID i istniejącego indeksu selektor wykonuje się w 0,170 / 0,092 / 0,076 ms, zamiast wcześniejszych 1,57–2,04 s. Zmiana nie wymaga migracji i zachowuje warunki dostępności źródła, odroczeń oraz blokad zadań. 13 testów helpera przeszło. Raport: reports/research-selector-performance-2026-09-09.json. Importery zostały ponownie uruchomione z tą poprawką; o 18:42 UTC baza przekroczyła 64 tysiące rekordów.
