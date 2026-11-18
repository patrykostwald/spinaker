# Z1 - fundament modułu „Teraz”

Gałąź robocza `codex/teraz-01`. Zmiany są gotowe do przeglądu koordynatora w katalogu roboczym.

## Zakres zmian

| Pliki | Zmiana |
| --- | --- |
| `backend/teraz/__init__.py`, `apps.py`, `models.py`, `migrations/__init__.py`, `migrations/0001_initial.py` | Aplikacja i pierwsza migracja z pięcioma modelami, tabelami relacji, indeksami i ograniczeniami. Migracja dodaje wyłącznie obiekty `teraz`. |
| `backend/teraz/api.py`, `urls.py`, `cache.py` | Pięć publicznych tras GET, paginacja, filtry, świeżość i linia stanu. Zmiany redakcyjne unieważniają cache po zatwierdzeniu transakcji. |
| `backend/teraz/admin.py`, `storage.py` | Panel wszystkich modeli, decyzje redakcji i wydawcy oraz prywatny magazyn plików. Panel pobrania pokazuje nazwę zrzutu. |
| `backend/teraz/zbieranie.py`, `transport.py`, `tasks.py`, `schedule.py` | Adapter bazowy, rejestr z fikcyjnym adapterem, zabezpieczenia HTTP, zapis pobrań i wpisów, harmonogram oraz retencja. |
| `backend/teraz/tests/__init__.py`, `conftest.py`, `test_publiczne.py`, `test_zbieranie.py`, `test_tasks_admin.py` | Testy offline bramki, endpointów, zbierania, retencji, admina i tras Celery. |

## Integracja

| Plik | Zmiana |
| --- | --- |
| `backend/config/settings.py` | Rejestracja `teraz.apps.TerazConfig`, trasa `teraz.tasks.*` do kolejki `teraz`, alias cache Redis `teraz` z `TERAZ_REDIS_URL` i prefiksem `teraz`, katalog zrzutów oraz retencja `TERAZ_RETENCJA_ZRZUTOW_DNI` (90) i `TERAZ_RETENCJA_OSOBOWE_DNI` (30). |
| `backend/config/celery.py` | Warunkowy import słownika `teraz.schedule.beat_schedule` i scalenie z dotychczasowym harmonogramem. Blok importu pomija harmonogram przy braku modułu `teraz` lub `teraz.schedule`. |
| `backend/config/urls.py` | Prefiks `api/teraz/` przed ogólnym `api/` aplikacji `news`. |
| `deploy/docker-compose.production.yml` | `worker-teraz` korzysta z obrazu budowanego tak samo jak `worker`, uruchamia `celery -A config worker -l info -Q teraz --concurrency=2` i ma limity 768 MiB oraz 1 CPU. Backend i nowy worker mają `TERAZ_REDIS_URL` (domyślnie baza Redis `/2`). Worker zapisuje na wolumenie `teraz_zrzuty`, backend montuje go do odczytu. Definicja `worker` jest identyczna z `HEAD`. Domyślna kolejka `celery` zachowuje zadania `news` i `scraper`. |

## Decyzje projektowe

- Odczyt obejmuje `warstwy/`, `wpisy/`, `zdarzenia/`, `zdarzenia/<id>/` oraz `stan/` pod `/api/teraz/`. Parametry `od` i `do` filtrują czas publikacji, `teryt` działa jako prefiks, a `bbox` przyjmuje zachód, południe, wschód i północ. Liczniki obejmują publiczne wpisy opublikowane w ostatnich 24 godzinach.
- `Wpis.objects.publiczne()` stosuje łącznie tryb źródła, klasę, decyzję redakcji i oba rodzaje wyłącznika. API używa tej samej bramki do liczników i zagnieżdżonych wpisów. Zdarzenie wymaga co najmniej jednego wpisu i jawności wszystkich powiązanych wpisów, ponieważ jego tytuł może powstać z kilku komunikatów. Status `Potwierdzone` wymaga redaktora, czasu weryfikacji i dwóch różnych instytucji. Faktyczną niezależność źródeł ocenia redakcja.
- Pola mapy dla dopuszczonych klas wrażliwych są uogólnione do TERYT województwa (wojsko, granica, infrastruktura) lub najwyżej powiatu (osoba poszukiwana, klasa wrażliwa). Filtry stosują tę samą dokładność. Przy dopuszczaniu redakcja sprawdza również tytuł, treść i link, które mogą zawierać dokładniejsze dane.
- Wydawca z uprawnieniem superuser przełącza źródło na publiczne osobną akcją, z podstawą i odnośnikiem do rejestru. Akcja zapisuje wykonawcę i czas. Redakcja może zawęzić tryb, zatrzymać wpis albo aktywować wyłącznik kategorii.
- Cache odpowiedzi ma TTL 20 s i `Cache-Control: public, max-age=15`. Zmiana generacji kluczy po decyzji redakcyjnej zachowuje limity HTTP i blokady zadań w tym samym aliasie Redis. U klienta lub pośrednika poprzednia odpowiedź może być dostępna przez okres określony w nagłówku. Przy błędzie aliasu `teraz` warstwa cache odpowiedzi pomija zapis lub odczyt z niego.
- `Zrodlo.zrodlo_dostepu` wskazuje opcjonalnie na `news.Source`. Zbieracz HTTP wymaga powiązania z aktywną, zatwierdzoną kartą dla rzeczywistego kanału i adresu. Obowiązują odstęp na host i dzienny budżet karty. Zapis treści i zrzutu respektuje zakres karty. Kanał `x` pozostaje zamknięty dla automatycznego pobierania jako kanał bez odpowiednika w istniejącej bramce. Fikcyjny adapter działa w pamięci.
- Transport używa `requests`, przypina połączenie do sprawdzonego publicznego IP, zachowuje weryfikację TLS dla nazwy hosta, wyłącza przekierowania i proxy, ogranicza czas i treść do 5 MiB oraz odrzuca wymuszoną kompresję. Walidatory są przypisane do adresu i wersji parsera.
- `200` z identycznym hashem i poprawne `304` dostają rekord `bez_zmian` bez pliku. Kanon hasha to NFC, końce linii LF i usunięte białe znaki na końcu każdej linii. Unikalność `(zrodlo, zewnetrzny_id)` zachowuje pierwszą wersję wpisu i późniejsze decyzje redakcji. Zapis zrzutu wymaga zmiany treści i karty `snapshot`.
- Retencja usuwa pliki, zachowując rekord i hash pobrania. Krótsza retencja uwzględnia również ponownie pobrane wpisy, które redakcja później sklasyfikowała jako osobowe. Oddzielna procedura usuwa osierocone pliki z katalogu zrzutów po krótszym terminie.
- Beat co minutę planuje należne źródła z losowym opóźnieniem 0-5 s. Zadania pobrania wygasają po 120 s i mają limit wykonania 50 s. Wybrano wczesne potwierdzenie `acks_late=False`, aby awaria workera nie powodowała automatycznej powtórki żądania. Następny przebieg podejmie źródło ponownie, gdy pozostanie należne. Retencja działa o 04:20, a jej zadanie wygasa po godzinie.

## Weryfikacja

- `pytest teraz -q` z migracjami - 294 zaliczone, w tym 270 kombinacji bramki. Pełny przebieg trwał 8 min 12 s.
- Wspólny przebieg ze schematem testowym `--nomigrations` - 294 zaliczone w `teraz` i 12 zaliczonych w wybranych testach `news` (rejestr źródeł, odzyskiwanie dostępu, deduplikacja i polityka miniaturek).
- `pytest scraper -q -x` - 802 zaliczone, 1 pominięty.
- `pytest news -q -x -k "not slow"` - 32 zaliczone, 3 odfiltrowane i 1 błąd w `news/test_account_lifecycle.py::test_feature_off_and_csrf`. Kopiowanie kontekstu Django 5.1 na Pythonie 3.14 powoduje ten sam błąd także bez kodu repozytorium. Nowy test admina ma poprawkę ograniczoną do swojego przebiegu. Obraz produkcyjny używa Pythona 3.11.
- `python manage.py check` - 0 problemów. `python manage.py makemigrations --check` - brak różnic między modelami a migracjami.

Walidacja Compose przeszła poleceniem `docker compose -f deploy/docker-compose.production.yml config --no-env-resolution --no-interpolate --quiet` z wyłączonym domyślnym plikiem środowiska. Sprawdzenie tras odbyło się bez brokera. Kompilator Django wygenerował SQL kluczowych zapytań dla SQLite i PostgreSQL.

## Kolejne etapy i ograniczenia

- Kolejne zlecenia obejmują zbieracze produkcyjne, TERYT i geokoder, mapę, panel redakcyjny oraz reguły opóźniania publikacji i łączenia warstw.
- Admin Django działa pod `/admin/` w backendzie. Obecne reguły Caddy domen publicznych kierują tę ścieżkę do frontendu. Redakcja będzie potrzebowała zatwierdzonej drogi do admina na wdrożeniu.
- Testy wykonano na SQLite i z atrapami HTTP oraz cache. Zachowanie rzeczywistych źródeł, PostgreSQL i Redis zweryfikuje integracja kolejnych zleceń.

## Migracja

Uruchom z katalogu głównego wdrożenia po dostarczeniu zmian przez koordynatora.

```sh
docker compose --env-file .env.production -f deploy/docker-compose.production.yml exec -T backend python manage.py migrate teraz --noinput
```

Effort `high`.
