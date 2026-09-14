# Nocny audyt niezawodności backfillu — 14 września 2026

Zakres: wyłącznie lokalny kod i testy (`backend/scraper/archive.py`, `backend/scraper/backfill.py`, komendy
`backfill_archives*`, `run_local_jobs.py`). Nie zatrzymano działającego importu, nie zmieniono listy
zatwierdzonych źródeł, nie obniżono odstępów domenowych, nie łączono się z produkcyjnym Supabase. Nie
uruchomiono testów przez `pytest` — uruchamianie interpretera Pythona z tego katalogu roboczego wymagało
zatwierdzenia, którego nie było komu udzielić w trybie nienadzorowanym; poprawność zweryfikowano ręcznym
prześledzeniem ścieżki wykonania i istniejących wzorców testowych. **Zalecenie: przed scaleniem uruchomić
`scraper/test_archive_metrics.py` i `scraper/test_archive.py`.**

## Co już działa poprawnie (sprawdzone, bez zmian)

- **Podwójny leasing w oknie żywej dzierżawy**: `run_batch` wybiera zadanie przez
  `select_for_update()` wewnątrz `transaction.atomic()` i od razu zapisuje `available_at = now + 15 min`
  w tej samej transakcji. Zapytanie kwalifikujące filtruje `available_at__lte=now`, więc żaden inny wątek/proces
  nie zobaczy zadania jako dostępnego, dopóki dzierżawa trwa.
- **Wygasłe dzierżawy i wznowienie po restarcie**: zapytanie kwalifikujące celowo obejmuje `status in
  ('pending', 'error', 'running')`. Jeśli proces padnie w trakcie przetwarzania (twardy restart, OOM), rekord
  zostaje `running` z `available_at` w przeszłości i po 15 minutach jest automatycznie odzyskiwany bez
  interwencji ręcznej — to jest właściwy mechanizm bezpiecznego wznowienia.
- **Retry 429/5xx**: `_transient_error` rozpoznaje 429/5xx/timeout/connection error; `retry_delay` honoruje
  nagłówek `Retry-After` jako dolną granicę i dodaje jitter. Pokryte testem
  `test_transient_retry_honors_retry_after_without_duplicate_job`.
- **Circuit breaker per-host**: po 3 błędach przejściowych host dostaje `circuit_until` do 900 s, pokryte
  `test_host_circuit_opens_after_three_transient_failures`.
- **Kontencja SQLite**: `settings.py` ustawia `OPTIONS={"timeout": 30, "transaction_mode": "IMMEDIATE"}` dla
  lokalnej bazy — krótkie blokady zapisu przy wielu wątkach `run_parallel_batch` nie kończą się natychmiastowym
  `database is locked`.

## Znaleziona wada: podwójne zaraportowanie ukończenia po przejętej dzierżawie

**Plik:** `backend/scraper/archive.py`, funkcja `run_batch`.

Finalizacja zadania robi zapis warunkowy (optymistyczna blokada):

```python
ArchiveJob.objects.filter(pk=job.pk, status='running', available_at=lease).update(...)
if state_callback is not None:
    state_callback(job)
```

Jeśli przetwarzanie jednego zadania trwa dłużej niż 15-minutowa dzierżawa, inny wątek/proces może w
międzyczasie legalnie przejąć to samo zadanie (dokładnie mechanizm opisany wyżej jako "poprawny"). Wtedy
warunkowy `.update()` trafia w 0 wierszy — to poprawnie chroni rekord `ArchiveJob` przed nadpisaniem przez
"spóźnionego" workera. **Ale `state_callback(job)` wywoływało się bezwarunkowo**, niezależnie od tego, czy
zapis się powiódł. W `scraper/backfill.py` ten callback (`checkpoint`) inkrementuje trwały licznik w
`ImportState.cursor` (`pages_completed`, `skipped_cutoff`, `last_job_id`). Efekt: to samo zadanie mogło zostać
policzone dwa razy w kursorze backfillu — raz przez workera, który przegrał wyścig, i raz przez workera, który
faktycznie je ukończył — mimo że w tabeli `ArchiveJob` istnieje tylko jeden, spójny stan końcowy.

To bezpośrednio zniekształca metryki, których Codex miałby użyć do decyzji o współbieżności (patrz sekcja
niżej) — zawyżony `pages_completed` wygląda jak wyższa przepustowość niż realna.

**Poprawka (odwracalna, jedna linia + komentarz):** wywołuj `state_callback` tylko wtedy, gdy warunkowy
`update()` faktycznie zmienił wiersz (`updated = ...update(...); if state_callback and updated:`).

**Test regresyjny:** `test_stale_lease_finalize_skips_state_callback_after_job_is_reclaimed` w
`test_archive_metrics.py` — symuluje przejęcie dzierżawy w trakcie `process()` i sprawdza, że `state_callback`
nie zostaje wywołany, a rekord zadania pozostaje pod kontrolą przejmującego workera.

## Nienaprawione, świadomie pozostawione ryzyka (poza minimalnym zakresem poprawki)

1. **Liczniki w pamięci (`counters['pages_completed']`, `new_articles`, `completed`) są inkrementowane przed
   sprawdzeniem, czy zapis wygrał wyścig.** W tym samym rzadkim scenariuszu co wyżej (zadanie przetwarzane
   dłużej niż 15 min) liczniki zwracane z pojedynczego wywołania `run_batch`/`run_parallel_batch` mogą być
   zawyżone o te same zadania. Nie naprawiono w tym przebiegu, bo wymagałoby to przesunięcia logiki liczników
   z czterech gałęzi `except`/sukcesu do miejsca po warunkowym `update()` — większa, bardziej ryzykowna zmiana
   niż dozwolona "najmniejsza odwracalna poprawka". Warto to zrobić w osobnym, przemyślanym PR.
2. **Brak `try/except` wokół wyboru zadania i wokół `state_callback` w `run_batch`.** Jeśli sam wybór zadania
   (blok `select_for_update()`) albo `checkpoint()` w `backfill.py` rzuci nieprzechwycony wyjątek (np.
   przejściowy błąd bazy dłuższy niż 30 s `timeout`), wyjątek propaguje przez `run_parallel_batch` →
   `run_backfill` aż do `backfill_archives_loop.py`, które nie ma własnego `try/except` wokół wywołania
   `run_backfill`. Cała ograniczona czasowo pętla backfillu kończy się wtedy nieobsłużonym wyjątkiem zamiast
   kontynuować z pozostałymi źródłami. Zadania w bazie nie giną (zostają w swoim ostatnim stanie i są
   bezpiecznie odzyskiwalne po restarcie — patrz sekcja wyżej), ale proces wymaga ręcznego restartu i traci
   dotychczasowy `last_success`/`last_error` na ten cykl. Nie naprawiono, bo obserwowana konfiguracja SQLite
   (`timeout=30`, `IMMEDIATE`) czyni to mało prawdopodobnym w normalnej pracy, a poprawa wymagałaby decyzji o
   tym, jak dokładnie degradować (pomijać źródło vs. przerwać cały cykl) — to decyzja produktowa, nie czysto
   techniczna poprawka.

## Metryki do decyzji o współbieżności (nie podnoszono automatycznie)

Wcześniejszy pomiar (`docs/ARCHIVE_CAPACITY_2026-09-14.md`) ustalił 32 workery jako zmierzony bezpieczny sufit
z malejącym zwrotem powyżej tej wartości. Żeby Codex mógł podjąć decyzję o zmianie tego limitu po nocy, warto
zebrać z kilku kolejnych cykli `archive_cycle`/`run_backfill`:

- **`deferred_jobs` względem `completed`** (metryki `run_batch`): rosnący udział `deferred_jobs` (odroczenia
  przez `SourceDelay`, czyli zajętą blokadę hosta) przy tej samej liczbie workerów oznacza, że workerów jest
  już więcej niż realnie równoległych hostów w kolejce — dokładanie kolejnych nic nie da.
- **`active_workers` względem żądanych `workers`** (`run_parallel_batch`): jeśli `active_workers` konsekwentnie
  wychodzi niższe niż skonfigurowane `workers`, nadmiar jest marnowany, bo `run_parallel_batch` ogranicza się
  do `min(workers, liczba źródeł z zaległymi zadaniami)`.
- **Częstość otwarcia circuit breakera per host** (`_HOST_STATES[...]['circuit_until'] > 0` / wpisy
  `last_error` typu przejściowego): częste otwieranie na tym samym hoście = ten host już dostaje maksimum
  bezpiecznego ruchu, więcej workerów tylko zwiększy ryzyko trwałej blokady.
- **Udział kodów 429 w `failed_jobs`/`last_error`**: rosnący udział 429 przy stałej liczbie workerów sygnalizuje
  zbliżanie się do limitu wydawcy niezależnie od lokalnej pojemności maszyny.
- **`elapsed_seconds` vs `completed` między kolejnymi cyklami przy tej samej liczbie workerów**: płaski lub
  malejący trend przy niezmienionej liczbie workerów wskazuje na ograniczenie sieciowe/hostowe, nie na
  ograniczenie liczby workerów.
- **Rozkład `last_error`** w `ArchiveJob` (typ wyjątku vs. znane stringi typu `robots_disallowed`,
  `missing_source_title`): jeśli dominują błędy przejściowe (sieć/5xx), podniesienie współbieżności tylko
  zwiększy liczbę ponowień bez realnego przyrostu postępu.
- Przy odczycie `pages_completed` z `ImportState.cursor` pamiętać o zastrzeżeniu z sekcji "Nienaprawione
  ryzyka" pkt 1 — licznik w pamięci z pojedynczego przebiegu może być nieznacznie zawyżony w rzadkim wyścigu
  dzierżaw; kursor backfillu (po dzisiejszej poprawce) już nie.

## Zmienione pliki

- `backend/scraper/archive.py` — `run_batch`: `state_callback` wywoływany tylko po wygranym zapisie warunkowym.
- `backend/scraper/test_archive_metrics.py` — nowy test regresyjny.
- `docs/BACKFILL_RELIABILITY_AUDIT_2026-09-14.md` — ten raport.
- `docs/PROGRESS.md` — wpis do kroniki.
