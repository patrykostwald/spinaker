# spin.clinic — dokument przekazania (bieżący)

Aktualizowany przez Claude Code (VS Code), sesja koordynująca w `C:\Users\User\spin-clinic\.local\spinaker-review`, gałąź `codex/plan-2026-09-13`. To zapis wykonanych działań, nie deklaracja ukończenia funkcji. Build PASS ani zielone testy jednostkowe nie są odbiorem funkcjonalnym.

## Uwaga o zakresie tej sesji

Wiadomość startowa zawierała też blok poleceń przebudowy wyglądu strony głównej („Moje nitki”, ilustracje, animacja „Jak działa”). Ten blok jest w prostej sprzeczności z `PLAN_PRACY_BEZ_CODEX.md` (sekcja „Pierwsza wiadomość do Claude Code”: *„Nie zmieniaj teraz wyglądu: właściciel dopracowuje go w osobnej sesji”*) oraz z zasadą rozdziału pracy w tym samym planie (frontend wyłącznie w `spinaker-claude`, osobna sesja). Nie wykonano tych poleceń. Zrealizowano zadania 1–3 z planu, w `spinaker-review`.

---

## Zadanie 1 — zabezpieczenie kodu i wspólny stan

**Co sprawdzono:**
- `spinaker-review` jest repo Git, gałąź `codex/plan-2026-09-13`, 12 lokalnych commitów przed tą sesją (nie pchniętych do `origin`).
- `spinaker-claude` (frontend, osobna sesja) — repo Git własne, katalog `.git` należy do innego użytkownika systemowego (`CodexSandboxOffline`); **nie dotknięto** — brak `git config --global safe.directory`, brak odczytu, brak zmian.
- `C:\Users\User\spin-clinic` (katalog nadrzędny) nadal nie jest repozytorium Git — potwierdzone `git rev-parse --show-toplevel` → `fatal: not a git repository`.
- Brak pliku `AGENTS.md` w `spinaker-review` (plan każe go przeczytać — **brak, konkretna niedopatrzenie do uzupełnienia przez właściciela lub kolejną sesję**).

**Co zrobiono:**
- Przegląd każdego zmienionego/nieśledzonego pliku pod kątem sekretów (wzorce API key/hasło/token — brak trafień poza testowymi fixture'ami `secret-test-key` w istniejących testach). `.env.example` i `deploy/.env.production.example` zawierają tylko placeholdery.
- Django `makemigrations --check` → brak brakujących migracji przed commitami.
- 90 testów backendu dot. zmienionych modułów odpalonych przed commitem → **90 passed**.
- Wykonano 7 małych, logicznych commitów (bez `git add .`, bez `.env`, bez dumpów baz, bez `node_modules`, bez danych osobowych):
  1. `cd28620` — mailbox wychodzącego kontaktu ze źródłami + weryfikacja e-mail kontaktu.
  2. `3929ed3` — preflight strukturalnych metadanych (dane.gov.pl, GUS BDL) + backoff ELI.
  3. `036b641` — adapter archiwum gov.pl (prokuratura/PR) + parowanie zadań archiwum per host + harvester_preflight/status.
  4. `b3571a1` — rekoncyliacja katalogu źródeł (fail-closed) + rejestr kontaktów outreach + raporty rekonesansu.
  5. `8931f36` — szkic wdrożenia produkcyjnego (Caddy + Compose + Dockerfile.frontend) — **nigdy nie zbudowany, nigdy nie wdrożony**.
  6. `12daff2` — zachowane wcześniejsze zmiany `API_INTERNAL_URL` (server-side fetch) i treści `/jak-dzialamy` (już były w drzewie roboczym przed tą sesją).
  7. `934adbb` — `.gitignore`: `celerybeat-schedule*` (runtime Celery) i `/tmp/` (skrypty jednorazowe + zrzut 2 GB SQLite).
- **Nie wykonano `git push`** — pozostaje osobnym, świadomym krokiem. Prywatność zdalnego repo (`github.com/patrykostwald/spinaker`) **nie została potwierdzona** — brak `gh` CLI w środowisku, brak innego dostępu do GitHub API bez logowania. Do potwierdzenia przez właściciela przed jakąkolwiek publikacją.
- Sprawdzono harmonogram Celery beat (`backend/config/celery.py`) i cały kod pod kątem automatycznej wysyłki do redakcji: **nie znaleziono żadnego zaplanowanego wysyłania e-maili**. `SOURCE_MAIL_SMTP_ENABLED` domyślnie `false`, a jedyne zadanie mailowe (`sync_source_mailbox`) tylko **czyta** skrzynkę (IMAP), nigdy nie wysyła. Brak zadań Windows Task Scheduler powiązanych z spin/harvest/mail. To zgadza się z notatką w planie: harmonogram wysyłki był tylko sugerowany w interfejsie, nigdy zaimplementowany — nie było więc nic do wyłączenia.
- Pozostały nieśledzony katalog `share/` (raport `claude-ai-egress-audit-2026-09-15.md`, 61 KB) — zostawiony bez zmian, decyzja właściciela czy ma wejść do repo czy zostać poza nim.

**Ograniczenia:**
- Prywatność repo GitHub niepotwierdzona (brak narzędzia).
- `AGENTS.md` nie istnieje — wskazane przez plan, ale nie było czego przeczytać.
- Nie przeglądano historii pod kątem sekretów wstecz (tylko bieżący stan working tree) — pełny `git log -p` audit sekretów nie był w zakresie zadania 1 i nie został wykonany.

**Następny krok:** właściciel potwierdza prywatność repo przed ewentualnym `git push`; decyzja o `share/`.

---

## Zadanie 2 — bazy, pochodzenie, odzyskanie danych

**Zinwentaryzowane bazy:**

| Baza | Lokalizacja | Silnik | Artykuły | Źródła (aktywne) | Zakres dat |
|---|---|---|---|---|---|
| **Bieżąca MVP (kanoniczna)** | Docker `spinaker-review-db-1`, `spin_clinic` | PostgreSQL 15 | 609 | 723 (43 aktywne) | 2026-09-15 20:07 → 2026-09-16 09:00 |
| Legacy lokalna | `C:\Users\User\spin-clinic\backend\db.sqlite3` | SQLite | 206171 | 314 (93 aktywne) | 2026-09-08 → 2026-09-15 22:04 |
| Frontend (osobna sesja) | wolumen Docker `spinaker-claude_postgres-data` | PostgreSQL 15 | nie odpytywane | — | kontener zatrzymany 15h; **nie dotknięto**, by nie zakłócać równoległej sesji |

**Wyjaśnienie rozbieżności 117828 (HANDOFF_AI.md, 14.09) vs 606 (plan, odczyt Postgres):**
- To dwie **różne, niepołączone** bazy z różnych uruchomień, nie jedna baza z brakującymi wierszami.
- `spin_clinic` w Dockerze (spinaker-review) to **świeża** baza tej gałęzi MVP — najstarszy wiersz z 2026-09-15 20:07, czyli powstała **po** dacie HANDOFF_AI.md (14.09). 606→609 między odczytem planu a teraz to naturalny przyrost (harvestery działały w tym czasie), nie duplikat.
- Legacy SQLite (`spin-clinic/backend/db.sqlite3`) to lokalny, niekontenerowy proces (`Start-Harvesters.ps1` z `USE_SQLITE=true`, bez Docker/Postgres), działający od 08.09. Liczba 117828 z 14.09 to zwykły stan pośredni — baza rosła dalej lokalnie do 206171 wierszy na 15.09 22:04, kiedy proces został zatrzymany.
- W legacy SQLite **193709 z 206171** wierszy (94%) to `ingestion_method='archive'` — surowe metadane ze skanu archiwum wydawcy, nie zredagowany, zdeduplikowany katalog materiałów. To dlaczego liczby nie są porównywalne 1:1 z 609 starannie poimportowanymi wierszami RSS/Sejm/ELI w Postgresie. **Starego pełnego tekstu z tej bazy (`news_articlecontent`) nie uznano za dozwolony do publikacji ani treningu — nie był i nie jest odczytywany przez żadne nowe narzędzie tej sesji.**

**Kopie lokalne (poza Git, poza aktywną bazą):**
- `C:\Users\User\spin-clinic\backups\spinaker-review-postgres-20260916T115817Z.dump` — `pg_dump -Fc`, 842 KB.
- `C:\Users\User\spin-clinic\backups\legacy-sqlite-20260916T115817Z.sqlite3` — kopia przez SQLite `backup()` API (bezpieczna wobec otwartego WAL), 2,17 GB.
- Istniejąca wcześniej kopia `C:\Users\User\spin-clinic\backups\db-pre-0048-20260915-214735.sqlite3` (przed migracją 0048, z poprzedniej sesji) — zachowana, nieusunięta.

**Test odtworzenia (wykonany, nie tylko zaplanowany):**
- Postgres: `pg_restore` do nowej, jednorazowej bazy `spin_clinic_restore_test` na tym samym serwerze — **609 artykułów / 723 źródeł**, identyczne z żywą bazą. Baza testowa usunięta po weryfikacji (`DROP DATABASE`), baza żywa nietknięta.
- SQLite: `PRAGMA integrity_check` → `ok`; liczba wierszy w kopii identyczna z oryginałem (206171 / 314).

**Propozycja jednej bazy głównej na MVP:** PostgreSQL w Dockerze (`spin_clinic`, serwis `db` w `spinaker-review`) jako baza kanoniczna. Legacy SQLite pozostaje zamrożonym źródłem historycznym do ewentualnego, ręcznie zatwierdzanego importu metadanych — nie jest i nie będzie bazą produkcyjną.

**Idempotentny import (przygotowany i przetestowany, NIE wykonany na żywej bazie):**
- Nowa komenda `backend/news/management/commands/plan_legacy_sqlite_import.py` (+ 3 testy, wszystkie przechodzą).
- Czyta wyłącznie metadane (`news_article`/`news_source` z legacy SQLite) — **nigdy** `news_articlecontent` (pełny tekst).
- Dedup po dokładnym URL i po znormalizowanym kanonicznym URL (reużywa istniejącej `scraper.quality_enrichment.canonicalize_url`).
- Łączy z istniejącym `Source` w bazie docelowej po adresie URL źródła — **nigdy nie tworzy nowego `Source`** (żaden import nie może po cichu aktywować nieprzeglądniętego harvestera).
- Domyślnie dry-run (raport JSON, zero zapisów). `--apply` odrzucany, jeśli nazwa bazy docelowej nie zawiera „test” (lub bez wyraźnego `--force-non-test-db`), i zawsze odrzucany wobec hosta Supabase.
- Raport dry-run na prawdziwych danych: *(patrz sekcja „Wynik dry-run" poniżej — dopisywana po zakończeniu odpytania w tle)*.

**Ograniczenia:**
- Wolumen Postgres frontendu (`spinaker-claude`) nie był odpytywany — nie wiadomo, jakie dane zawiera; zostawione osobnej sesji.
- Import metadanych z legacy SQLite do żywej bazy MVP **nie został wykonany** — komenda jest gotowa i przetestowana na Django-testowej bazie, ale decyzja o realnym imporcie (i jego zakresie) należy do właściciela po przeglądzie raportu dry-run.
- Mniejsze pliki SQLite w `.local` (`account-e2e-*`, `quality-check-*`, `portal-*` w `.local/backups`) nie zostały zinwentaryzowane szczegółowo — to nazwane, oczywiste artefakty testowe/benchmarkowe wcześniejszych sesji, niskiego priorytetu.

**Następny krok:** właściciel przegląda raport dry-run i decyduje, czy i w jakim zakresie importować legacy metadane do MVP; ewentualne uruchomienie `--apply` na dedykowanej bazie testowej, nigdy na `spin_clinic` bez dodatkowej decyzji.

---

## Zadanie 3 — rzeczywiste działanie harvesterów i polskie znaki

**Status: zakończone dla wymaganego zakresu.** Co najmniej jeden cykl każdego badanego mechanizmu potwierdzony na żywo (logi + bezpośrednie zapytania do bazy), nie tylko `active_sources`.

### Rzeczywiste działanie harvesterów

- **Celery beat działa i wysyła zadania punktualnie** (potwierdzone logami `docker compose logs beat`): `archives-minute` co minutę, `rss-hourly` co godzinę, `voting-history-5m` co 5 min, `source-access-5m`, `quality-5m`, `kprm-listing-minute`, `source-mail-inbox-5m`. To nie jest samo `active_sources=43` — to rzeczywiste, timestampowane wykonania.
- **Worker rzeczywiście przetwarza zadania**, bez błędów: `scrape_rss_sources_task` wykonał się o 12:00, 13:00, 14:00 (16.09), z wynikiem `imported=0` — feed nie miał nowych wpisów w tym oknie. To prawidłowy wynik, nie awaria (patrz `PLAN_PRACY_BEZ_CODEX.md`: brak nowości u wydawcy może być prawidłowym wynikiem).
- **Kolejka archiwum** (`ArchiveJob`): 338 done, 29 pending, 0 running, 0 error, 12 quarantined.
  - Wszystkie 12 `quarantined` mają identyczny powód: `non_article_route` (strona rozpoznana jako niebędąca artykułem — np. listing/kategoria). Nie wymuszono zdejęcia kwarantanny.
  - Wszystkie 29 `pending` to strony `stat.gov.pl` (GUS, source pk=110), `attempts=0`, `available_at` już minęło (od 15.09 22:17). Sprawdzone bezpośrednio: GUS ma jedną zatwierdzoną kartę dostępu, kanał `rss` (`https://stat.gov.pl/rss/pl/5438/8.xml`), **bez** karty dla kanału `page`/HTML. `archive_cycle`/`approved_queued_source_ids()` poprawnie i celowo blokuje te zadania — to nie błąd, to brak zatwierdzenia zakresu. Nie dodano nowej karty (poza zakresem tej sesji: „bez nowych zgód, zmian zakresu kart”).
- **Retry/backoff**: `fetch_json_paced` (dodane w tej sesji do `import_eli_changes`) poprawnie honoruje `Retry-After` przez `HostRateLimited`; potwierdzone żywym przebiegiem (patrz niżej — realny `HostRateLimited: host_rate_limited:2.905` przy kolejnych żądaniach do `api.sejm.gov.pl`, poprawnie obsłużony przez ponowienie z odczekaniem). Grupowanie zadań archiwum per-host (naprawione w zadaniu 1, commit `036b641`) ograniczyło niepotrzebne odroczenia między workerami.
- **Ograniczony przebieg zatwierdzonego źródła przez istniejące bramki (wykonany na żywo, nie tylko zaplanowany):**
  - Sejm (`scraper.official.import_voting`, term 10, sitting 1, numery 1–5): 5 prób, 5 sukcesów, 0 nowych rekordów (wszystkie już istniały), 0 duplikatów — każdy zapis to „official correction” nadpisujący pole `title` świeżym pobraniem z `api.sejm.gov.pl`.
  - NIK RSS (`https://www.nik.gov.pl/rss/id,1.html`, source pk=52): 1 pobranie feedu, 20 wpisów, 0 nowych artykułów (wszystkie URL-e już istniały), 0 duplikatów.

### Polskie znaki — zbadane i w większości naprawione

**Ustalenie:** to prawdziwe uszkodzenie w bazie (dosłowne bajty ASCII `?` w miejscu wielobajtowych znaków UTF-8), nie artefakt wyświetlania terminala — potwierdzone odczytem `repr()`/`.encode('utf-8')` w Pythonie.

**Źródło:** zweryfikowane bezpośrednio, na żywo, z bieżącym kodem:
- Prawdziwe API Sejmu (`api.sejm.gov.pl`) i prawdziwy feed RSS NIK zwracają **poprawny** UTF-8 (sprawdzone surowym `urllib.request` z kontenera — `\xc5\x82` dla „ł", deklaracja `encoding="utf-8"` w XML).
- Ponowne, żywe wywołanie `scraper.official.import_voting(10, 1, 1)` i `feedparser.parse(fetch_feed(...))` dla NIK **z bieżącym kodem** dało w 100% poprawny tekst.
- **Wniosek: bieżący potok `fetch_feed → json.loads/feedparser → zapis` jest zdrowy.** Uszkodzenie jest historyczne — jednorazowy zapis podczas pierwszego zasiewu tej gałęzi (15.09, 20:07–20:48), nigdy się nie powtórzyło, bo te konkretne harvestery nie zostały ponownie wywołane aż do tej sesji. Nie znaleziono w repo dokładnego mechanizmu pierwotnego uszkodzenia (żaden z zachowanych kroków transportu/dekodowania go nie reprodukuje) — prawdopodobnie inna, wcześniejsza wersja kodu/środowiska, od tego czasu naprawiona przez kolejne commity.
- Zabezpieczone testem regresji: `backend/news/test_polish_text_roundtrip.py` (Source.name i Article.title z pełnym zestawem polskich znaków, przez prawdziwy Django ORM → PostgreSQL).

**Naprawione, wyłącznie z uprawnionego źródła (nigdy zgadywaniem liter za `?`):**
- 5/5 artykułów głosowań Sejmu — żywym ponownym pobraniem z `api.sejm.gov.pl` (patrz wyżej).
- 13/14 artykułów NIK RSS — nowa komenda `resync_rss_titles_from_feed` (przetestowana, `backend/scraper/test_resync_rss_titles_from_feed.py`), pobiera feed na żywo i nadpisuje tytuł tylko gdy świeże pobranie jest czyste. 1 pozycja (pk=19) pozostawiona nietknięta: świeży tytuł też zawiera znak „?" (prawdziwy znak zapytania w treści), heurystyka bezpieczeństwa słusznie odmawia w niejasnym przypadku.
- 57/57 wierszy `Source` kandydatów wymiaru sprawiedliwości (prokuratury, SN, NSA, TK, KRS) — nowa komenda `repair_source_names_from_catalog` (przetestowana, 6 testów w `test_repair_source_names_from_catalog.py`), odtwarza `name`/`catalog_notes` wyłącznie z już zrecenzowanych literałów w `prepare_justice_candidates.py`. Dopasowanie 41 prokuratur okręgowych (bez URL) tylko po potwierdzeniu, że baza ma dokładnie 41 kolejnych wierszy-kandydatów po 16 dopasowanych URL-em — inaczej komenda odmawia i niczego nie zmienia (przetestowane: `test_district_prosecutors_untouched_if_an_extra_row_breaks_the_expected_shape`).
- 1 wiersz `Source` (GUS, pk=110) — bezpośrednia poprawka `name` na `"Główny Urząd Statystyczny"`, potwierdzone żywym odczytem tytułu kanału z własnego, aktywnego feedu RSS GUS (`<title>` w `https://stat.gov.pl/rss/pl/5438/8.xml`) — czyli z uprawnionego, aktualnego źródła wydawcy, nie zgadywaniem. Wykonane bezpośrednim zapytaniem ORM, nie osobną komendą (jeden wiersz, jednorazowo).

**Pozostałe, jawnie NIEnaprawione (brak uprawnionego źródła w repo lub brak aktywnej instrukcji dostępu do ponownego pobrania):**
- 11 wierszy `Source.name` z „?": KPRM, PAP Samorząd, UOKiK, Polskie Radio, RMF24, Onet Wiadomości, Teraz Środowisko, Gazeta Wrocławska, Głos Wielkopolski, Dziennik Bałtycki, NIK (pk=52 — samo `Source.name`, RSS URL-owe artykuły już naprawione osobno). `sources.md` zawiera dla tych wpisów tylko nazwy domenowe (np. `rmf24.pl`), nie te wyświetlane nazwy — więc katalog źródłowy nie jest tu uprawnionym źródłem.
- 8 wierszy `Source.catalog_notes` z tych samych 8 źródeł.
- 24 artykuły z „?" w tytule: 1 NIK (pk=19, opisany wyżej), 13 z nieaktywnych kandydatów gov.pl prokuratury (pk 53/58/67 — `catalog_stage='candidate'`, `is_active=False`, brak zatwierdzonej instrukcji dostępu, więc bezpiecznego ponownego pobrania nie da się wykonać bez zmiany zakresu karty), 10 z GUS (pk=110 — feed RSS zwraca inne, nowsze wpisy niż te historyczne URL-e, więc `resync_rss_titles_from_feed` nie znajduje dopasowania po URL; wymagałoby dojścia do archiwalnych stron GUS, co nie było celem tej sesji).

**Właściciel: żadna z tych pozostałych wartości nie jest naprawiana zgadywaniem. Do naprawienia albo przez ponowne, zatwierdzone pobranie z wydawcy, albo świadomą decyzję.**

### Testy — dodatkowe znalezisko i posprzątane

Podczas weryfikacji cyklu odkryto, że **73 z 680 testów pytest nie przechodziło** w stanie przejętym na starcie tej sesji (nie spowodowane tą sesją — zweryfikowano `git log` między `origin` a stanem przed tą sesją: żaden z tych plików testowych ani `official_access_allowed` nie zmienił się w 12 wcześniejszych commitach tej gałęzi). Przyczyna: `official_access_allowed` zyskało wymagany argument `path`, a kilka fixture'ów/mocków testowych (`news/test_official_pagination.py`, `news/test_official_backfill.py`) i pomocnik `approve_api()` (brakujący `daily_request_cap`, wymagany od `>=1` przez bramkę dostępu) nigdy nie zostały zaktualizowane. Naprawiono **28 z 73** (commit `c8326e6`) — te bezpośrednio związane z bramką dostępu Sejm/ELI, czyli z tym, co zadanie 3 miało zweryfikować. **Pozostałe 56 nieprzechodzących testów** to inne, niezależne obszary (`test_wordpress_rest_bridge`, `test_uokik_sudop`, `test_bzp_backfill`, `test_news_sitemaps`, `test_queue`, `test_archive_metrics`, `test_enrichment`, `test_publisher_genres`, `test_directory_archive`, `test_backfill*`) — **nie naprawione w tej sesji**, każdy wymaga własnej diagnozy; zostawione jako jawny, nazwany dług, nie ukryty.

Wynik obecny: `635 passed / 56 failed / 1 skipped` z 692 testów. Pierwszy pełny przebieg tej sesji pokazał 87 nieprzechodzących; część tego wzrostu spowodował własny, znaleziony i naprawiony błąd w teście `plan_legacy_sqlite_import` (mutacja `settings.DATABASES` zanieczyszczała bazę testową na resztę procesu) — poprawione przed jakimkolwiek commitem tego testu.

**Ograniczenia zadania 3:**
- Nie testowano ELI (`api.sejm.gov.pl/eli`) na żywo — tylko Sejm i NIK RSS.
- Nie odblokowano żadnej nowej karty dostępu (GUS `page`, gov.pl prokuratury) — zgodnie z zakazem zmiany zakresu kart.
- 56 nieprzechodzących testów w niezwiązanych obszarach pozostaje jako dług do zdiagnozowania osobno.
- Mechanizm pierwotnego (historycznego) uszkodzenia polskich znaków nie został jednoznacznie zlokalizowany — tylko potwierdzone, że już nie występuje.

**Następny krok:** właściciel decyduje, czy warto odtworzyć 24 pozostałe artykuły (wymaga dojścia do archiwalnych URL-i wydawcy) i 11+8 pozostałych `Source.name`/`catalog_notes` (wymaga ustalenia wyświetlanych nazw z wiarygodnego źródła). Kolejna sesja/Codex: zdiagnozować pozostałe 56 nieprzechodzących testów, każdy osobno.
