# Porównawczy audyt poprawki transportu — 14 września 2026 (zadanie 015)

## Zakres i metoda

Niezależny audyt `backend/scraper/utils.py::fetch_feed()` i wywołań
`hostname_transport=True` w `backend/scraper/archive.py`, w kontekście
`docs/TRANSPORT_DIAGNOSIS_2026-09-14.md` (diagnoza pierwotnej awarii) i
`docs/TRANSPORT_PEER_REVIEW_2026-09-14.md` (przegląd 014, który dodał test
`test_hostname_transport_still_rejects_private_redirect` do
`backend/scraper/tests.py` — ta zmiana jest już w drzewie roboczym,
niescalona). Nie uruchamiano harvestera, nie wykonano żadnych żądań
sieciowych, nie dotknięto frontendu, Supabase ani sekretów. Kod produkcyjny
**nie został zmieniony** w tym audycie — patrz sekcja "Uruchomione testy":
brak dowodu defektu, więc zgodnie z poleceniem zadania nie ma podstawy do
zmiany kodu.

## 1. Code review

**SSRF / DNS rebinding.** Preflight (`safe_url` + `socket.getaddrinfo` +
odrzucenie niepublicznych adresów) wykonuje się bezwarunkowo na początku
każdej z maks. 4 iteracji pętli, niezależnie od `hostname_transport` — redirect
na adres prywatny jest więc zawsze łapany, zanim nastąpi kolejne połączenie.
Ścieżka domyślna (`hostname_transport=False`) łączy się z adresem IP już
zwalidowanym w tej samej iteracji — brak drugiej, niezależnej rezolucji DNS,
więc rebinding jest tu strukturalnie niemożliwy. Ścieżka
`hostname_transport=True` łączy się przez `urllib3.PoolManager` pełnym
URL-em z nazwą hosta, co wymusza **drugą, niezależną rezolucję DNS** w
momencie faktycznego connect wewnątrz urllib3. Powstaje wąskie okno TOCTOU:
atakujący kontrolujący DNS zweryfikowanej domeny (przejęta subdomena,
skompromitowany panel DNS, złośliwy operator CDN) mógłby w tym oknie
skierować połączenie na adres prywatny mimo przejścia preflightu. To realne,
ale wąskie ryzyko — wymaga kontroli nad DNS domeny, która już przeszła
operatorską konfigurację `catalog_stage='configured'`, nie dowolnego URL-a.
Zgadzam się z oceną tego ryzyka w przeglądzie 014 (sekcja 3 tamtego
dokumentu) i nie znajduję dodatkowego wektora poza już opisanym.

**Poprawność urllib3.** Branch `hostname_transport=True` używa
`PoolManager.urlopen('GET', request_url, ...)` z pełnym URL-em i bez
ręcznego nagłówka `Host` — to poprawne wywołanie API (PoolManager sam
zarządza pulami per-host i ustawia `Host` z URL-a). Branch domyślny łączy
`HTTPSConnectionPool`/`HTTPConnectionPool` pod zwalidowanym adresem IP z
ręcznym `Host` i `server_hostname`/`assert_hostname` do weryfikacji
certyfikatu — też poprawne, to standardowy wzorzec pinningu IP w urllib3.
Sprzątanie poola: `getattr(pool, 'close', None) or getattr(pool, 'clear', None)`
poprawnie obsługuje, że `PoolManager` w części wersji urllib3 ma `clear()`,
a `HTTPSConnectionPool`/`HTTPConnectionPool` mają `close()`. Brak `assert_hostname`
w gałęzi `hostname_transport` nie jest błędem — połączenie po hostname
weryfikuje certyfikat automatycznie przez SSL context, w przeciwieństwie do
połączenia po IP, gdzie trzeba to jawnie nadpisać.

**Redirecty.** `redirect=False` w obu gałęziach; `Location` wraca na początek
pętli i przechodzi ten sam preflight (`safe_url` + DNS) co URL wejściowy,
z twardym limitem 4 przekierowań. Zachowanie identyczne dla obu wartości
`hostname_transport` — to poprawnie utrzymuje "per-hop" walidację.

**Testowalność.** Kod jest łatwo testowalny przez mockowanie
`socket.getaddrinfo` i `urllib3.PoolManager`/`HTTPSConnectionPool` — testy
istniejące (patrz sekcja 3) to potwierdzają i nie wymagają realnej sieci.
Ograniczenie: żaden test (mockowany na poziomie `PoolManager`) nie może
udowodnić braku drugiej rezolucji DNS w prawdziwym urllib3 — to inherentna
granica testu jednostkowego dla tego konkretnego ryzyka, nie wada tego testu.

**Zgodność z celem legalnego archiwum.** `hostname_transport=True` jest
używane wyłącznie w `archive.py`, wyłącznie dla źródeł z
`catalog_stage='configured'` (przefiltrowanych w `process()`/`discover()`
przez `Source.objects.filter(..., catalog_stage='configured')`), nigdy dla
URL-i pochodzących od użytkownika. To zawęża ryzyko z sekcji "SSRF/DNS
rebinding" do katalogu operatorsko skonfigurowanych źródeł — węższego niż
"dowolny URL", choć szerszego niż wąska allowlista
`SourceAccessInstruction.APPROVED` (ta rozbieżność jest już opisana jako
osobne ryzyko w przeglądzie 014, sekcja 2, i nie jest przedmiotem tego
audytu transportowego — nie powtarzam tu jej analizy, tylko odnotowuję jako
kontekst ryzyka w sekcji "Ryzyka" niżej).

**Wniosek code review:** mechanika transportu jest poprawna i minimalna
względem postawionego celu (przywrócić połączenie po hostname wyłącznie dla
zatwierdzonych publisherów, z zachowaniem preflightu na każdym hopie). Nie
znaleziono defektu wymagającego zmiany kodu.

## 2. Porównanie z dwiema alternatywami

### Alternatywa A — zawsze pinować IP (cofnąć `hostname_transport`)

Usunąć parametr, wrócić do jedynej ścieżki: połączenie zawsze po
zwalidowanym IP, tak jak przed poprawką z `db79de4`.

- **Zysk:** zero okna DNS rebinding/TOCTOU — najprostszy możliwy kod.
- **Koszt:** to dokładnie odtwarza defekt opisany w
  `docs/TRANSPORT_DIAGNOSIS_2026-09-14.md` — CDN-y i load balancery
  odrzucające połączenia bezpośrednio po IP powodują `NewConnectionError`,
  fałszywe retry i wyczerpywanie prób archiwizacji dla realnych,
  zatwierdzonych źródeł. To nie jest hipotetyczny koszt: to udokumentowana
  przyczyna, dla której poprawka w ogóle powstała.
- **Ocena:** brak mierzalnej przewagi nad obecnym wariantem — usuwa jedno
  ryzyko (wąskie, wymagające kontroli DNS zweryfikowanej domeny), ale
  przywraca inne, już potwierdzone w produkcji (masowe fałszywe awarie
  zatwierdzonych źródeł). Odrzucam tę alternatywę.

### Alternatywa B — weryfikacja adresu gniazda po connect (defense in depth)

Podklasa `HTTPConnection`/`HTTPSConnection` nadpisująca `connect()`, która po
faktycznym otwarciu gniazda sprawdza `sock.getpeername()[0]` przez
`ipaddress.ip_address(...).is_global`, zanim pójdzie handshake TLS/żądanie —
zamyka niemal całe okno TOCTOU, bo waliduje adres realnie użytego gniazda,
a nie osobną, wcześniejszą odpowiedź DNS.

- **Zysk:** redukuje okno DNS rebinding z "między dwoma niezależnymi
  zapytaniami DNS" do praktycznie zera, bez utraty zgodności z CDN (nadal
  łączy się po hostname).
- **Koszt:** wymaga podklasowania wewnętrznych klas połączeń urllib3
  (`HTTPConnection.connect`), nietrywialnej integracji z `PoolManager`
  (trzeba podmienić `connection_pool_kw`/`pool_classes_by_scheme` albo użyć
  custom `HTTPConnectionPool` z nadpisaną fabryką połączeń), i osobnych
  testów dla nowej ścieżki. To wyraźnie większa zmiana niż "najmniejsza
  wystarczająca poprawka", z własnym ryzykiem regresji (błędna integracja z
  poolingiem mogłaby np. cicho pomijać weryfikację przy ponownym użyciu
  połączenia z puli).
- **Ocena:** technicznie lepsza względem czystego ryzyka DNS rebinding, ale
  nie ma **mierzalnej** przewagi wystarczającej do uzasadnienia zmiany w tym
  audycie — zagrożenie jest już wąskie (wymaga kontroli DNS zweryfikowanej,
  operatorsko skonfigurowanej domeny) i nieużyte w drodze do dowolnego
  URL-a. Zostawiam jako udokumentowaną rekomendację na przyszłość, do
  wdrożenia gdyby granica zaufania kiedyś się rozszerzyła (np. samoobsługowe
  dodawanie źródeł bez ręcznej weryfikacji operatora) — nie teraz.

## 3. Minimalny zestaw testów rozstrzygających

Cztery testy w `backend/scraper/tests.py` (wszystkie już obecne w drzewie
roboczym, w tym jeden dodany w przeglądzie 014) razem rozstrzygają o
bezpieczeństwie tej poprawki — żaden nie jest zbędny, żaden nie brakuje do
pokrycia zamierzonego zachowania:

1. `test_private_fetch_is_rejected_before_connection` — prywatny adres
   odrzucony przed jakimkolwiek połączeniem (pula nigdy nie tworzona).
2. `test_public_fetch_pins_ip_and_rejects_private_redirect` — ścieżka
   domyślna: redirect na adres prywatny kończy się błędem przed drugim
   połączeniem; pool tworzony pod adresem IP, nie hostname.
3. `test_approved_source_uses_hostname_transport_after_public_dns_check` —
   `hostname_transport=True` faktycznie łączy się po hostname (pełny URL do
   `PoolManager.urlopen`, brak ręcznego `Host`) — potwierdza, że poprawka
   robi to, po co powstała.
4. `test_hostname_transport_still_rejects_private_redirect` — dla
   `hostname_transport=True` redirect na adres prywatny nadal kończy się
   błędem po jednym wywołaniu `urlopen` — potwierdza, że per-hop preflight
   obejmuje też tę gałąź.

Poza tym: pełny `backend/scraper/tests.py` i `backend/scraper/test_archive.py`
powinny przejść bez regresji (używają `fetch_feed`/`robots` przez mocki na
poziomie modułu, więc nie są wrażliwe na tę zmianę sygnatury poza
opcjonalnym `hostname_transport=False`).

## Uruchomione testy

Środowisko audytu (`.local/spinaker-review`) nie ma dostępnego interpretera
Pythona (`python`/`py` w PATH to tylko aliasy Microsoft Store, bez realnej
instalacji) — **testy nie zostały uruchomione lokalnie**, tak jak w
przeglądzie 014. Logika czterech testów z sekcji 3 została zweryfikowana
ręcznie przez odczytanie treści testów i prześledzenie kolejności operacji w
`fetch_feed()`; są spójne z zachowaniem kodu opisanym w sekcji 1. Właściciel
powinien uruchomić `pytest backend/scraper/tests.py backend/scraper/test_archive.py`
przed scaleniem.

## Zmienione pliki

Brak zmian w kodzie produkcyjnym ani w testach w ramach tego audytu — nie
znaleziono defektu, więc zgodnie z poleceniem zadania nie było podstawy do
edycji. Jedyny nowy plik to ten raport:
`docs/TRANSPORT_COMPARATIVE_AUDIT_2026-09-14.md`.

(Stan `backend/scraper/tests.py` w drzewie roboczym pochodzi z wcześniejszego
zadania 014, nie z tego audytu — pozostawiony bez zmian.)

## Ryzyka

1. Wąskie okno DNS rebinding/TOCTOU w `hostname_transport=True` (sekcja 1) —
   niskie prawdopodobieństwo, wymaga kontroli DNS zweryfikowanej domeny;
   akceptowalne dla obecnego zasięgu, opisana ścieżka złagodzenia to
   Alternatywa B, nie zmiana dziś.
2. Zasięg `hostname_transport=True` = `catalog_stage='configured'`, szerszy
   niż wąska allowlista `SourceAccessInstruction.APPROVED` — opisane w
   przeglądzie 014 jako osobne ryzyko produktowe, nie transportowe; wzmacnia
   (ale nie zmienia jakościowo) ryzyko #1, bo zwiększa liczbę domen, których
   DNS musiałby zostać przejęty.
3. Brak lokalnego uruchomienia testów w tym środowisku (brak interpretera
   Pythona) — niskie ryzyko, bo wszystkie cztery testy z sekcji 3 już
   istnieją w drzewie roboczym i były analogicznie zweryfikowane ręcznie w
   przeglądzie 014; wymaga potwierdzenia przez właściciela przed scaleniem.

## Rekomendacja

**Zostaw obecny wariant bez zmian.** Żadna z dwóch rozważonych alternatyw
nie ma mierzalnej przewagi wystarczającej do zmiany: Alternatywa A (zawsze
pinować IP) usuwa wąskie ryzyko TOCTOU kosztem przywrócenia udokumentowanej
awarii kompatybilności z CDN; Alternatywa B (weryfikacja peer IP po connect)
jest technicznie mocniejsza, ale nieproporcjonalnie większa niż wymagana
minimalna poprawka wobec dziś wąskiego, dobrze ograniczonego ryzyka —
zostaje jako udokumentowana opcja na przyszłość, nie jako zmiana teraz.

## Następny krok

Właściciel uruchamia `pytest backend/scraper/tests.py backend/scraper/test_archive.py`
w środowisku z interpreterem Pythona, aby potwierdzić brak regresji przed
scaleniem zmiany z zadania 014 (nowy test w `tests.py`). Jeśli granica
zaufania dla `hostname_transport=True` kiedykolwiek rozszerzy się poza
ręcznie skonfigurowany katalog (np. samoobsługowe dodawanie źródeł), wrócić
do Alternatywy B (weryfikacja peer IP po connect) jako uzasadnionej wtedy
zmiany.
