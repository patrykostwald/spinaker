# Katalog źródeł

Stałe miejsce pracy: http://localhost:3000/editor/sources. Wymaga konta redakcji. Dane do lokalnego logowania są zapisane w `.local/admin-login.txt` — nie umieszczaj tego pliku w publicznym repozytorium.

## Jak korzystać

- **Dodaj źródło**: wpisz nazwę, adres i opcjonalną notatkę. Jeśli adresu jeszcze nie znamy, pozostaw go pusty. Nowy wpis jest nieaktywnym kandydatem.
- **Edytuj**: popraw nazwę, adres, rodzaj źródła, kanał RSS lub notatki. Domena źródła mającego materiały lub kolejkę archiwum jest chroniona; innego wydawcę dodaj osobno.
- **Wyłącz import**: zatrzymaj pobieranie nowych materiałów z danego źródła. Wykonywane już żądanie może się jeszcze zakończyć.
- **Wyklucz z katalogu**: usuń źródło z bieżącej listy i wyłącz pobieranie. Jego historię można znaleźć w filtrze „Wykluczone” i przywrócić jako nieaktywnego kandydata.
- **Eksport całego katalogu CSV**: pobierz wszystkie wpisy, również wykluczone i kandydatów. Plik można otworzyć w Excelu lub zaimportować do Arkuszy Google. Eksport jest kopią; zmiany w pobranym pliku nie aktualizują portalu automatycznie.

Wyłączenie lub wykluczenie źródła nie kasuje zgromadzonych artykułów i nie zmienia ich treści. Istniejące materiały pozostają w archiwum i wynikach wyszukiwania.

## Co oznaczają informacje

„Import włączony” oznacza ustawienie pobierania, a nie gwarancję dostępności wydawcy. „Skonfigurowane” nie oznacza kompletnego ani zweryfikowanego archiwum. Katalog pokazuje osobno błędy, liczbę materiałów i stan zadań archiwalnych. Liczba zadań zawiera również mapy witryn i ponowne próby; nie jest liczbą artykułów.

Odstęp w minutach i daty odbioru RSS dotyczą odświeżania kanału. Archiwum ma osobną kolejkę i datę ostatniej kontroli. Zapis adresu strony nie tworzy samodzielnie importera jej archiwum. Przed aktywowaniem kandydata sprawdzamy kanał i sposób pobierania.

„Kontrola dostępu” pokazuje rzeczywiście sprawdzony RSS, mapy i ujawnione listy stron. Rozwiń „Sprawdzone adresy”, aby zobaczyć dowody. „Lista na stronie do podłączenia” oznacza kandydata na adapter, a nie gotowy import. Daty najstarszego i najnowszego zapisanego materiału pokazują bieżące pokrycie bazy; nie dowodzą ciągłości archiwum.

Zmiana adresów powoduje oznaczenie wcześniejszej kontroli jako nieaktualnej. Osobny proces co pięć minut wybiera najwyżej jedno źródło wymagające kontroli: nowe, zmienione albo niesprawdzane przez siedem dni. Po nieoczekiwanym błędzie kontrola ma przerwę sześciu godzin. To nie zmienia częstotliwości RSS ani importerów archiwum. Właścicielskie wykluczenia są zachowywane.

Pełne badanie 9 września 2026 r.: 149 wierszy, 145 sprawdzonych i cztery bez adresu. Potwierdzono 56 RSS i 87 źródeł z mapami. Włączono 19 nowych kanałów i poprawiono pięć istniejących adresów RSS, bez zmiany odstępów pobierania. Raport i kalkulator: `outputs/archive-research-20260909/`.

## Jedno źródło konfiguracji

Autorytatywnym katalogiem jest tabela `Source` w bazie portalu, edytowana przez panel. Dotychczasowe pliki z listami służą do początkowego zasilania i dokumentowania pochodzenia propozycji. Ponowne zasilanie nie powinno zmieniać decyzji właściciela, reaktywować wykluczonych wpisów ani zastępować ręcznie ustawionej częstotliwości.

Katalog jest lokalnie w `backend/db.sqlite3` i jest objęty kopiami tej bazy. Do czasu wdrożenia serwera adres `localhost` działa na tym komputerze. Po wdrożeniu pozostanie ta sama ścieżka `/editor/sources` pod domeną portalu.

## Zweryfikowane źródła instytucjonalne oczekujące na adapter

Audyt z 14 września 2026 potwierdził podstawę ponownego wykorzystania i techniczny punkt wejścia dla KNF, URE, NIK, NSA/CBOSA, API BZP oraz UOKiK. Wpis nie oznacza aktywnego importu. Adapter musi zachować źródłowy URL, datę pozyskania i wymagane oznaczenie przetworzenia; dla NIK nie wolno używać ścieżki `/szukaj/`, a UOKiK wymaga osobnej oceny przed jakimkolwiek użyciem treści przez boty AI. Dokładne dowody i kandydaci do pilotów są w `SOURCE_ARCHIVE_AUDIT_WAVE3_2026-09-14.md`.

PKW, RCL, UODO i zasoby dane.gov.pl bez własnej jednoznacznej licencji pozostają kandydatami nieaktywnymi. Nie należy ich włączać na podstawie samej dostępności technicznej.
