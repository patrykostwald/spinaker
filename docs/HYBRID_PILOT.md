# Pilotaż hybrydowy: wyszukiwanie, źródła i szkice

Decyzja: bez paywalla w walidacji. Baza lokalna i import archiwalny pozostają. Publiczne wyszukiwanie uruchamia równolegle zapytanie do bazy oraz OpenAI Responses z web_search po aktywnych źródłach. Odnośniki napływają w strumieniu, a odczytane metadane zasilają oś czasu. Nitki redakcyjne nadal zatwierdza i publikuje człowiek. Bieżący opis demo: LIVE_SEARCH_DEMO.md.

## Wyszukiwanie zewnętrzne

GET /api/search/external/?q=... korzysta z Brave Web Search, wyłącznie po włączeniu EXTERNAL_SEARCH_ENABLED i dodaniu BRAVE_SEARCH_API_KEY. Domyślnie 100 zapytań dziennie; rezerwacja w bazie obejmuje również nieudane próby. Brak klucza nie blokuje wyszukiwania lokalnego. Klucz pozostaje na backendzie. Na etap pilotażu limit chroni budżet, nie zapewnia każdemu użytkownikowi osobnej puli.

Lista dozwolonych domen wynika z aktywnych źródeł z włączonym pobieraniem. Wyniki są filtrowane również po odpowiedzi dostawcy. Nie dodajemy automatycznie przypadkowych nowych wydawców.

Tytuł w wyniku zewnętrznym pochodzi z indeksu i nie jest jeszcze zweryfikowany u wydawcy. Nie używamy daty indeksacji/modyfikacji jako daty publikacji. Dlatego kandydaci są osobną grupą, bez dat i z nieustaloną kategorią. Filtry dat/kategorii dotyczą lokalnych, sklasyfikowanych rekordów. To jawne ograniczenie pilotażu, nie kompletna federacja filtrów.

Adres kandydata trafia do ArchiveJob (EXTERNAL_SEARCH_ARCHIVE_URLS=true). Importer pobiera źródło zgodnie z dotychczasowymi ograniczeniami i dopiero na jego podstawie tworzy Article. Brak dostępu pozostawia niezweryfikowanego kandydata. Kolejka nie gwarantuje odczytania adresu podczas tej samej sesji wyszukiwania. Brak daty nigdy nie zostaje uzupełniony domysłem.

Cache odpowiedzi dostawcy domyślnie wyłączony. EXTERNAL_SEARCH_CACHE_SECONDS należy ustawić dopiero po sprawdzeniu uprawnień wybranego planu do przechowywania wyników. Pobieranie i prezentowanie metadanych wydawcy również wymaga respektowania jego warunków; integracja nie stanowi licencji do miniaturek lub treści.

## Archiwa i uruchomienie

Lokalna baza: backend/db.sqlite3. Harmonogram: USE_SQLITE=true ARCHIVE_WORKERS=32, polecenie backend/manage.py run_local_jobs w środowisku .venv. Jest to limit liczby grup: rzeczywista liczba zależy od źródeł z gotowymi zadaniami. W pomiarze 2026-09-09 przy tym ustawieniu pracowało 27–28 grup; nie osiągnięto granicy sprzętu. Wyniki i ograniczenia: reports/archive-capacity-2026-09-09.md. Ten sam proces uruchamia bieżące importy, kontrolę jakości i lokalne kopie. Nie należy uruchamiać drugiego schedulera. Kopie na tym samym komputerze nie zastępują kopii poza nim.

Wcześniejsze konfiguracje 2 lub 8 importerów zostały zastąpione pomiarem do 32. Odstępy dla wydawców i robots są zachowane. Bramka hosta działa w jednym procesie dla importu archiwalnego; nie zastępuje rozproszonego limitera produkcyjnego.

## Co właściciel konfiguruje na końcu

- Konto OpenAI API, klucz serwerowy, model z obsługą web_search i limity prób (AI_START_CHECKLIST_PL.md). To jedyna niezbędna płatna integracja tego wariantu demo.
- Opcjonalnie Brave Search API jako dodatkowe odkrywanie odnośników; nie jest potrzebne do OpenAI web_search.
- Docelowy serwer, domena, HTTPS i kopie poza maszyną.
- Pilotaż redakcyjny 20–30 tematów: trafność i brakujące źródła, poprawność dat, koszt, czas oraz błędne skojarzenia. Dopiero po tym decyzja o automatycznej publikacji.

Nie wdrożono automatycznego osądzania spinu, własnego treningu modelu, paywalla ani automatycznej publikacji. Obecny szkic jest doborem kontekstu na podstawie metadanych, a nie sprawdzeniem wszystkich twierdzeń źródłowych.
