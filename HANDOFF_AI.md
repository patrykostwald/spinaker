# spin.clinic — pakiet przekazania dla kolejnego asystenta AI

Stan: 14 września 2026. Ten dokument nie zawiera sekretów i może zostać otwarty przez asystenta przeglądarkowego.

## Materiały wejściowe

- Repozytorium: https://github.com/patrykostwald/spinaker
- Gałąź robocza: `codex/plan-2026-09-13`
- Aktualny plan: `PLAN_AKTUALNY.md`
- Audyt istniejącego Supabase: `docs/SUPABASE_AUDIT_2026-09-14.md`
- Instrukcja aplikacji lokalnej: `README_APP.md`
- Projekt Supabase: `yyrwcggmksjhzeaovrvl`, publiczny adres projektu: `https://yyrwcggmksjhzeaovrvl.supabase.co`

Nie proś właściciela o wklejenie hasła bazy, klucza `service_role`, klucza API ani pliku `.env` do rozmowy. Nie umieszczaj sekretów w kodzie, odpowiedzi ani repozytorium. Asystent przeglądarkowy bez osobnej autoryzacji ma przygotowywać analizę lub patch, a nie zakładać, że ma prawo zapisywać GitHub albo Supabase.

## Tryb autonomiczny właściciela

Właściciel upoważnia agentów do nieprzerwanego wykonywania prac, które pchają projekt do przodu: lokalnych zmian kodu i dokumentacji, testów, audytu publicznych źródeł, przygotowania kart dostępu, kontrolowanych pobrań zgodnych z jawną dokumentacją źródła, diagnozy błędów, zadań dla Claude Code oraz porządkowania kolejki. Dotyczy to także nocnego cyklu pracy: raport ma opisywać wykonany postęp, a nie zastępować pracy.

Nie czekaj na potwierdzenie przy rutynowej decyzji technicznej lub przy wypełnieniu wewnętrznej karty audytowej na podstawie jednoznacznie publicznej dokumentacji API. Zatrzymaj się wyłącznie przed działaniem nieodwracalnym albo zewnętrznym wymagającym decyzji właściciela: publikacją, wysłaniem wiadomości, wydatkiem, wdrożeniem produkcyjnym, zapisem do produkcyjnego Supabase, zakupem, użyciem sekretu lub pobieraniem mimo niejednoznacznej podstawy/warunków źródła.

## Niezmienne decyzje produktu

1. Jeden Box to jeden materiał źródłowy: artykuł, reportaż, wywiad, film, podcast, post, komunikat, dokument, akt prawny, głosowanie, orzeczenie, reklama lub inny jawnie oznaczony typ.
2. Box publiczny pokazuje przede wszystkim tytuł, źródło, datę, miniaturę, typ i link do oryginału. Obecność materiału nie potwierdza jego twierdzeń.
3. Nitka odwołuje się do Boxów i nie kopiuje ich treści.
4. Rzetelność obejmuje jawne braki, datę i metodę pozyskania, historię zmian oraz oddzielenie danych źródłowych, klasyfikacji automatycznej i komentarzy użytkowników.
5. Użytkownik może mieć jedną reakcję i jeden komentarz na Box. Widoczność aktywności na profilu kontroluje użytkownik.
6. Wysyłanie próśb do wydawców zawsze wymaga zatwierdzenia właściciela. Problemy techniczne i prawne trafiają do kolejki administratora.
7. MVP korzysta z wymiennego adaptera AI. Dane, źródła, reguły i wyniki ewaluacji pozostają przenośne; nie zakładamy przeniesienia pamięci ani wag usługowego modelu.

## Potwierdzony stan techniczny

- Lokalny Django/SQLite: 314 źródeł, 117 828 materiałów, 3 563 664 zadań archiwalnych, 111 327 rekordów `ArticleContent`.
- Supabase: 601 źródeł, 0 Boxów. Schemat aplikacyjny istnieje, ale przed zapisem wymaga migracji bezpieczeństwa opisanej w audycie.
- Lokalny harvester metadanych działa z czterema wykonawcami. Nowe pełne teksty są domyślnie wyłączone przez `ARCHIVE_STORE_FULL_TEXT=false`.
- Backend: 416 testów zaliczonych. Oba frontendy Next.js budują się poprawnie.

## Najbliższy zakres pracy

1. Zaproponuj mapowanie lokalnego `Article` do Supabase `boxes` bez wykonywania migracji i bez sekretów.
2. Zdefiniuj kontrakt rekordu pośredniego harvester → walidator → Supabase, w tym identyfikator źródła, kanonikalny URL, precyzję daty, typ materiału, miniaturę, wynik polityki i pochodzenie.
3. Wypisz przypadki deduplikacji i błędów. Ten sam URL ma być idempotentny; podobny tytuł nie wystarcza do scalenia.
4. Przygotuj testy kontraktu na fikcyjnych domenach. Nie uruchamiaj masowego pobierania.
5. Zgłoś rozbieżności z `PLAN_AKTUALNY.md`; nie zmieniaj samodzielnie decyzji produktu.

## Wybór dostawcy AI

OpenAI pozostaje dostawcą istniejącego prototypu wyszukiwania internetowego. Mistral EU jest drugim dostawcą pilotażowym do klasyfikacji, rankingu kandydatów i embeddings po potwierdzeniu dostępności funkcji regionalnych. Globalnego wyszukiwania Mistral nie włączamy automatycznie. DeepSeek pozostaje wykluczony. Komentarze, dane kont i prywatna aktywność użytkowników nie trafiają do zewnętrznych modeli. Szczegóły: `docs/AI_PROVIDER_PLAN.md`.

## Aktualizacja 5 listopada 2026: przeszlosc.today jako narzędzie OSINT, scalenie gałęzi

**Zrobione i sprawdzone**
- Ustalono, gdzie jest kod: wspólny ze spin.clinic, w tym repozytorium (`frontend-spin/app/przeszlosc/*`, `backend/news/przeszlosc*.py`, `drzewo_pieniedzy.py`, `pracownia_osint.py`, `krs*.py`). `main` jest nieaktualny; praca z października leżała na gałęziach `cloud/integracja-2310` (23.10, 33 commity) i `codex/mvp-public-frontend` (31.10, 6 commitów). Żadna nie zawierała drugiej.
- Obie scalono do gałęzi roboczej `claude/upbeat-noether-7k08ac` (PR #29). Bez konfliktów w kodzie. Konflikt w `CLAUDE.md` rozwiązano: zachowane zasady właściciela, dopisana sekcja zasad nadrzędnych.
- Dodano migrację scalającą `0172_merge_0170_clientnote_file_0171_krs_kolejka` (pusta): obie gałęzie dodały równoległe migracje 0170. Po niej `makemigrations --check` nie zgłasza zmian.
- `manage.py check`: bez uwag. Build `frontend-spin` (`pnpm build`): przechodzi.
- Gałęzie źródłowe i `main` nie były modyfikowane.

**Wynik testów backendu (5.11.2026, pytest, SQLite, pełny przebieg ok. 10,5 min)**
- Przed poprawkami: 3955 zaliczonych, 2 nieudane, 1 pominięty. Oba błędy pochodziły z gałęzi `codex/mvp-public-frontend`, nie ze scalenia:
  - `news/test_duty.py::test_registry_covers_every_beat_task`: zadanie `zbudujmi_note_files_cleanup_task` było w harmonogramie Celery, ale nie w `news/agent_registry.py`. Dodano wpis `zbudujmi-pliki-uwag`.
  - `news/test_clinic_corrections.py::test_reply_length_and_admin_immutable_ai`: formularz wycofania diagnozy wymaga teraz pola `reason_code`, a test go nie wysyłał. Test uzupełniono o `reason_code: OTHER`.
- Po poprawkach oba pliki testowe przechodzą (83 testy). Pełnego przebiegu po poprawkach nie powtarzano (oba zmiany są lokalne: wpis w rejestrze i jedno pole w teście).
- **Znany problem, niezwiązany ze scaleniem:** `news/test_audyt_petli.py::test_thread_review_enqueue_runs_in_own_transaction` przechodzi w pełnym przebiegu, ale pada uruchomiony osobno (z moją zmianą i bez niej), bo `thread_review.enqueue` kończy się wcześniej, gdy `threads_enabled()` zwraca fałsz. Test zależy od flagi `THREADS_ENABLED` i kolejności testów. Do poprawy osobno: test powinien jawnie ustawiać flagę.

**Niesprawdzone / w toku**
- Nie wiadomo, który wariant jest na produkcji (VPS, `/srv/spin-clinic`). Nic nie wdrażano.
- Nie przejrzano pozostałych gałęzi `cloud/*` ani otwartych PR #21 do #28.

**Dokumenty**
- Zasady nadrzędne właściciela: `CLAUDE.md` (sekcja na końcu). Obowiązują wszystkich agentów.
- Plan przeszlosc.today (OSINT): `docs/PLAN_PRZESZLOSC_OSINT.md`; katalog źródeł z priorytetami: `docs/PRZESZLOSC_ZRODLA_DANYCH.md`; wdrożenie 23.10: `docs/zadania-chmura/WDROZENIE_2310.md`.
- Starsze opisy przeszlosc.today jako „alternatywnego brandu" w `PLAN_AKTUALNY.md`, `project.md`, `roadmap.md`, `docs/CONTEXT_ARCHIVE_PRODUCT.md` są w tym zakresie przestarzałe.

**Wdrożenie 5.11.2026 (wykonał właściciel na VPS `/srv/spin-clinic`, gałąź `claude/upbeat-noether-7k08ac`, commit `b243cd5d`):** kopia bazy (lokalnie i w zaszyfrowanym koszyku) przed migracjami, migracje 0170, 0171, 0172 zastosowane, kontenery frontend/backend/beat/worker uruchomione, `KOREKTOR_NAPRAW=false` dopisane do `.env.production` na pierwsze 3 dni. Produkcja przed wdrożeniem działała na odłączonym HEAD = koniec `codex/mvp-public-frontend` (`e5b3bbaa`). **Punkt powrotu:** `git checkout e5b3bbaa`, migracje cofać do `0170_clientnote_file` (NIE do 0169, bo skasuje to dane załączników z codexa).

**OSINT-01 (5.11):** `/przeszlosc/dane` i `/api/przeszlosc/stan-danych/` działają na produkcji. Odczyt: 15 źródeł OK, 14 zaległych, 2 puste, 1 wyłączone. Część „zaległych" to fałszywy alarm (sztywne 48 h dla źródeł tygodniowych i miesięcznych); poprawka w kodzie (`przeszlosc_stan.py`: próg = 2 x własny interwał, min. 48 h; testy w `test_przeszlosc_stan.py`) czeka na wdrożenie. Realne problemy do zbadania w logach: `krs_changes` (JSONDecodeError od 8.10), `assets` (0 rekordów, request_limit_or_host_interval), `fts` (nigdy nie pobrane), `kohesio` (0 rekordów), `interpellations` i `questions` (stoją od 22.10 i 10.10), `niw`/`mf_opp` (od 13.10; beat tygodniowy dodany), `bzp` (9 rekordów). Szczegóły w `docs/PLAN_PRZESZLOSC_OSINT.md`. Teksty „do potwierdzenia" nadal niezmieniane.

**Następny krok:** wdrożyć poprawkę progu; zebrać z serwera logi dla powyższych źródeł i zdiagnozować; potem uzupełnić „do potwierdzenia". Wdrożenie na VPS robi właściciel: komendy w `docs/zadania-chmura/WDROZENIE_2310.md`, kopia bazy przed migracjami (`sh deploy/backup.sh`); nowa migracja 0172 jest pusta, ale musi zostać zastosowana.

## Aktualizacja 5 listopada 2026 (wieczór): pętla person i pierwsze poprawki

**Zrobione i sprawdzone (lokalnie: 145 testów frontendu, typecheck, build; 4 testy modułu Stanu danych)**
- Runda 1 pętli person (10 person, żywy portal): wyniki i zbiorcza lista w `docs/PERSONY_PRZESZLOSC_RUNDA1.md`. Średnia 4,2/10, ale **zaniżona artefaktami testu** (narzędzie bez przeglądarki, 10 person z jednego IP, HTTP 429). Nie używać jako wskaźnika postępu; kolejne rundy po 2-3 persony naraz, czekanie 8-10 s.
- Frontend `frontend-spin/app/przeszlosc/`: własne OG/opis przeszłość.today (`layout.tsx`), ponawianie odczytów po 429/502-504 (`retry-fetch.ts`, `RetryFetch.tsx`, test 129), nagłówek „Ścieżka w Sejmie i rejestrach" (`TopicTree.tsx`), Odstępstwa: wyjaśnienie okna, podpisane liczniki, „Pokaż więcej" (`Odstepstwa.tsx`, `odstepstwa-okno.ts`, test 130).
- Backend `news/przeszlosc_stan.py`: próg zaległości zależy od interwału źródła (2 x, min. 48 h), pola `refresh_hours` i `stale_after_hours`.

**Do wdrożenia przez właściciela (kod na gałęzi `claude/upbeat-noether-7k08ac`, brak nowych migracji):** przebudowa `backend` i `frontend`.
**Do konfiguracji na serwerze:** `TRUSTED_PROXY_COUNT=1` w `.env.production` (potwierdzone, że brakuje; bez tego wszyscy anonimowi użytkownicy mogą dzielić jeden limit 100 zapytań/min). Wymaga restartu backendu.

**Niesprawdzone / otwarte**
- Czy wejścia „Spółka" i „Osoba" na stronie głównej są dość widoczne dla laika (przeglądarka, zrzuty 390 i 1440).
- Pomyłka Bosak/Bosacki i nagłówek „Głosowania w temacie": **sprawdzone na profilu `/przeszlosc/osoba/256-krzysztof-bosak`, niepotwierdzone** (Bosackiego tam nie ma, głosowania to własne głosy posła). Źródło pomyłki: rozmyte wyszukiwanie osób (Bosacki wychodzi jako trzeci wynik dla „Bosak"). Zostaje do rozważenia zawężenie dopasowania rozmytego przy pełnym imieniu i nazwisku w widoku tematu.
- 7 zepsutych źródeł (lista w planie) i przekaz dnia spin.clinic: diagnoza przez właściciela (polecenia podane w rozmowie); przekaz dnia prowadzi osobna sesja naprawcza spin.clinic.
- Odstępstwa: filtr po pośle i eksport CSV; imienne głosy posła i „Mój poseł" w profilu; widoki PKW i lobbingu; oś „projekt ustawy"; tagi tematyczne głosowań (patrz dokument person).

## Koordynacja z sesją „spin.clinic repair" (5.11.2026, wieczór)

- Sesja naprawcza pracuje na gałęzi `claude/napraw-mercury-przekaz-883a1d`, zresetowanej na `b243cd5d` (ten sam commit, na którym stoi serwer). Zmienia tylko: `backend/news/inception.py`, `backend/news/test_inception.py`, `docs/KONSYLIUM.md`. **Bez migracji** (numer 0173 pozostaje wolny). Nie dotyka `.env.production`, Korektora, X ani kontenerów; nie zmienia danych przeszłość.today.
- Przyczyna przekazu dnia `failed` (wg tamtej sesji): domyślny model Inception `mercury-2.5` wycofany przez dostawcę, wymiana na `mercury-3`; dodatkowo `_note_error` tam, gdzie odpowiedź bez poprawnego JSON ginęła bez zapisu w `last_error`. Dziś (5.11) pole `error` pokazuje `inception_invalid_json` dla obu obozów. Awarie wystąpiły też przed Korektorem (30.10 do 4.11), więc nie on je powoduje.
- Moja gałąź (`claude/upbeat-noether-7k08ac`, PR #29) zmienia od `b243cd5d` tylko pliki przeszłość.today, dokumentację i `backend/news/przeszlosc_stan.py`. **Brak wspólnych plików z gałęzią naprawczą.**
- Ustalone: **jedno wdrożenie** z obu zestawów zmian; żadna sesja nie przełącza ani nie restartuje serwera sama; wdrożenie robi właściciel z gotowych poleceń. Plan: po wypchnięciu gałęzi naprawczej scalić ją do gałęzi PR #29, uruchomić testy (frontend, backend: `test_inception`, `test_przeszlosc_stan`), podać jedną procedurę (w niej `TRUSTED_PROXY_COUNT=1`).
- Stan na teraz: gałąź naprawcza **nie jest jeszcze na GitHubie**; serwer nadal na `b243cd5d`; nic z ostatnich zmian nie jest wdrożone.

## Wdrożenie Mercury i zasada bezpieczeństwa wdrożeń (5.11.2026, noc), wg raportu sesji „spin.clinic repair"

**Stan (relacja tamtej sesji, nie weryfikowana przeze mnie na serwerze):** Mercury (Inception) naprawiony i wdrożony; domyślny model `mercury-3`; w bazie 22792 wpisów (bez zmian); logi czyste. Serwer stoi na commicie z jej gałęzi `claude/napraw-mercury-przekaz-883a1d` (jeden commit `b28e3ad` na `b243cd5d`). Backend był niedostępny ok. 10 minut podczas wdrożenia (pierwsze próby trafiły w złe pliki Compose). Posprzątano: błędny symlink `.env`, pusty osierocony wolumin `deploy_postgres-data` (z myślnikiem), nieużywane obrazy `spin-clinic-*`. PR #30 (jej) może być zamknięty jako wdrożony.
**Zweryfikowane w repozytorium:** gałąź naprawcza to 1 commit, 3 pliki (`inception.py`, `test_inception.py`, `docs/KONSYLIUM.md`), 0 migracji, 0 wspólnych plików z moimi zmianami; została scalona do `claude/upbeat-noether-7k08ac` (commit `0d580cc`); 110 testów (`test_inception`, `test_przeszlosc_stan`, `test_duty`, `test_clinic_corrections`) przechodzi, `check` i `makemigrations --check` czyste.

**ZASADA (zweryfikowana: w repozytorium są dwa pliki Compose bez `name:`, więc nazwa projektu = nazwa katalogu):** `docker-compose.yml` w katalogu głównym tworzy projekt „spin-clinic" z własnym, pustym woluminem bazy; produkcyjny `deploy/docker-compose.production.yml` tworzy projekt „deploy" (kontenery `deploy-*`, wolumin `deploy_postgres_data`). **Jedyna bezpieczna komenda na serwerze, zawsze z `/srv/spin-clinic`:**
`docker compose --env-file .env.production -f deploy/docker-compose.production.yml <polecenie>`
Nigdy samo `docker compose up` bez tych flag i nigdy z innego katalogu.

**Otwarte:** stan serwera (commit i gałąź) do potwierdzenia poleceniem `git log -1` i `git status -sb`; wdrożenie zmian przeszłość.today (commity po `b243cd5d`, w tym `TRUSTED_PROXY_COUNT=1`) wciąż czeka.


## Wdrożone i zweryfikowane na produkcji (5.11.2026, noc)

- Serwer `/srv/spin-clinic` na commicie `1fce169` (gałąź `claude/upbeat-noether-7k08ac`), kontenery `deploy-*` odtworzone; `TRUSTED_PROXY_COUNT=1` w `.env.production` **i** w działającym backendzie (`printenv` w kontenerze).
- Zweryfikowane z zewnątrz (Firecrawl): API Stanu danych ma `refresh_hours` i `stale_after_hours`; rozkład statusów 22 OK / 7 zaległych / 2 puste / 1 wyłączone; OG przeszłość.today; Odstępstwa: wyjaśnienie okna, „Pokaż więcej", „pokazujemy 30 z 187".
- Punkt powrotu: `b28e3ad4` (poprzedni stan serwera, z naprawionym Mercury); brak nowych migracji, więc powrót nie dotyka bazy. Kopia bazy z 5.11 21:05.
- **Do zrobienia (kod):** status źródła z zerem rekordów = „puste" (dziś Kohesio pokazuje „OK" przy 0); eksport pełnej listy odstępstw (backend ucina do 30 na klub); filtr po pośle; widoki PKW i lobbingu; imienne głosy posła w profilu.
- **Do zbadania w logach (czekamy na wyniki poleceń od właściciela):** `krs_changes` (stoi od 8.10), `interpellations` (22.10), `questions` (10.10), `fts` (nigdy), `bzp` (9 rekordów), `niw`/`mf_opp` (po dodaniu harmonogramu tygodniowego powinny odświeżyć się w niedzielę 8.11).
- **Poza kodem:** `assets` blokuje `bot_protection`; potrzebna oficjalna droga dostępu do oświadczeń majątkowych.


## Diagnoza zbieraczy (5.11.2026, noc)

- Polecenie stanu źródeł dało: `assets` `blocked_access_review`/`bot_protection` (polityka: nie obchodzimy), `kohesio` OK z 0 rekordów (źródło nie podaje beneficjentów z Polski: 0 z 102 721), `fts`/`interpellations`/`questions`/`krs_changes` `deferred` z pustym błędem (zadania w odroczeniu; powody w `PublicCollectionJob.last_error`).
- **Zmiany w kodzie (lokalnie, do wypchnięcia i wdrożenia):** `backend/news/przeszlosc_stan.py` (zero rekordów = „puste", opis luki Kohesio), `test_przeszlosc_stan.py`, `frontend-spin/app/przeszlosc/jak-to-dziala/tresc.ts` (datowana informacja o Kohesio i FTS). Testy: 5 backend (stan danych), 145 frontend, typecheck czysty.
- **Następny krok:** odczyt błędów zadań dla `fts`, `interpellations`, `questions`, `krs_changes` (polecenie dla właściciela), potem naprawa przyczyny (nie masowe zerowanie opóźnień).
- **Uwaga techniczna:** push na GitHub był odrzucany błędem po stronie GitHuba (`fatal error in commit_refs`); commity są lokalne, przypomnienie o ponowieniu ustawione.


## Diagnoza zbieraczy, część 2 (5.11.2026, noc)

- **Naprawione w kodzie (lokalnie/na gałęzi, niewdrożone):** `scraper/public_records.py` - `modifiedSince` dla interpelacji i zapytań z godziną `T00:00:00` (API Sejmu zwraca 404 dla samej daty); test `test_sejm_questions_incremental_uses_datetime_modified_since`; 117 testów zbieraczy przechodzi.
- **Po wdrożeniu trzeba jednorazowo usunąć oczekujące zadania** źródeł `interpellations` i `questions` (mają zapisany błędny adres; kod nie założy nowych, dopóki jakieś są oczekujące). To zmiana w bazie produkcyjnej: tylko za zgodą właściciela i z kopią bazy.
- **Do sprawdzenia na serwerze (tylko odczyt):** odpowiedź API KRS dla `krs_changes` (JSONDecodeError) i nagłówek pliku FTS (`fts_header_missing`).


## Diagnoza zbieraczy, część 3 (6.11.2026): wszystkie cztery przyczyny ustalone i naprawione w kodzie

| Źródło | Przyczyna (potwierdzona) | Poprawka (kod, niewdrożona) |
|---|---|---|
| interpellations, questions | API Sejmu: `modifiedSince` bez godziny daje 404 | `T00:00:00` w `scraper/public_records.py` |
| krs_changes | API KRS: 204 bez treści dla rejestru P (podmiot w rejestrze S) | pusta odpowiedź = próba drugiego rejestru |
| fts | kolumna kraju to „Beneficiary country" | dodana nazwa w `scraper/nowe_zrodla.py` |
| kohesio | zbiór nie ma nazw beneficjentów z Polski (0 z 102 721) | status „puste", opis w Stanie danych i „Jak to działa" |

**Po wdrożeniu (zmiana w bazie produkcyjnej, za zgodą właściciela, po kopii bazy):** usunąć oczekujące zadania interpelacji i zapytań (mają zapisany błędny adres, kod nie założy nowych, dopóki istnieją oczekujące) oraz przyspieszyć ponowienie zadań FTS i KRS (`retry_at=teraz`); kod radzi sobie już z obiema przyczynami. `assets`: zablokowane zabezpieczeniem antybotowym, decyzja właściciela o wyłączeniu i oficjalnej drodze dostępu otwarta.

**Testy przed wdrożeniem poprawek zbieraczy (6.11.2026, commit `72b6adc`):** pełny backend (pytest, SQLite) 3963 zaliczone, 2 pominięte, 0 nieudanych; frontend 145 testów, typecheck i build czyste (wcześniej). Brak nowych migracji. Punkt powrotu: `1fce1696`.


## Pasek „Ostatnio w bazie” i retencja kopii (6.11.2026, niewdrożone)

- **Pasek (uwaga właściciela, zrzut):** tekst stał ok. 5 px nad środkiem paska, a pasek był 24 px pod menu zamiast „prawie doklejony”. Przyczyna: `align-items: baseline` w wierszu, w którym przyciski 44 px z ujemnymi marginesami przesuwały linię bazową. Poprawka w `frontend-spin/app/przeszlosc/pasek-nowosci.css`: `align-items: center` (wiersz, grupa przycisków, odnośniki) i `gap: 8px` w `.px-home-top:has(.pt-tick)` (odstęp od menu 24 -> 8 px; od paska do treści nadal 24 px).
- **Sprawdzone (Playwright, zrzuty 1329 i 390 px):** środki tekstów 91-92 przy środku paska 92 (desktop), 82,8-83,7 przy 84 (telefon); odstęp od linii menu 8 px na obu. Test `tests/126-przeszlosc-pasek-nowosci.test.cjs` zaktualizowany do nowych reguł; `node --test tests/*.test.cjs` 145/145, `pnpm typecheck` i `pnpm build` przechodzą.
- **Retencja kopii w B2:** `RETENTION_DAYS` 30 -> 18 (`backend/news/kopia_zapasowa.py`, decyzja właściciela: opcja A). Kopia bazy ok. 0,4 GB x 18 = ok. 7,6 GB, czyli poniżej progu alarmu 8 GB (darmowe 10 GB w Backblaze). Lokalnie nadal 14 dni. Zaktualizowane: `deploy/backup.sh` (komentarze), `docs/KOPIE-I-ODTWORZENIE.md`, testy `news/test_kopia_zapasowa.py` (10 zaliczonych). Przy pierwszym przebiegu po wdrożeniu `kopia_task` usunie z B2 obiekty starsze niż 18 dni (to zamierzone).
- **Wdrożenie:** razem z następnym wydaniem (frontend + backend); żadne polecenie na serwerze poza standardową procedurą z sekcji o wdrożeniu (kopia bazy, `$DC up -d --build`).


## BZP: przyczyna zatrzymanego kursora (6.11.2026, kod gotowy, niewdrożone)

- **Stan produkcji 6.11 (odczyt):** zbieracze interpelacji (20 362), zapytań (4 030), FTS (5 167) i krs_changes działają po wdrożeniu `84bdb04`. Błędy krs_changes to pojedyncze ponowienia dla rejestru S (1 porażka każdy), nie awaria. Karta dostępu BZP jest zatwierdzona do 22.03.2027, `BZP_API_ENABLED=True`.
- **BZP, przyczyna (sprawdzona na żywej odpowiedzi API):** API filtruje dni po dacie UTC. Ogłoszenie Gmina Niegowa z 26.07 22:57 UTC to już 27.07 w Warszawie, a zbieracz sprawdzał tylko dzień warszawski, więc zgłaszał „poza oknem” i kursor stał na 26.07 od 6.10. Poprawka: `scraper/bzp_backfill.py` akceptuje dzień w oknie liczony po UTC albo po Warszawie; wpis spoza okna w obu miarach nadal zatrzymuje kursor. Test `test_notice_after_utc_evening_is_accepted_when_api_day_is_utc`; stary test „spoza okna” dostał datę naprawdę spoza okna (16.09).
- **Drugi problem:** beat `bzp-metadata-3m` co 3 min kolidował z bramką hosta (3 min przerwy), więc co druga próba była odrzucana. Najpierw `*/4`, potem (patrz niżej) `*/5` z wieloma stronami na uruchomienie (nazwa wpisu bez zmian, odwołuje się do niej `repairer` i `harvester_coverage`). Szybkość zbierania nadal ogranicza karta dostępu (interwał 180 s); jej zmiana to decyzja o zgodzie na korzystanie z API, nie zmiana kodu.
- **Efekt po wdrożeniu (do sprawdzenia):** `official-backfill:bzp:v1` ma ruszyć z kursora 26.07 w głąb historii; liczba rekordów BZP na stronie „Stan danych” powinna rosnąć (dziś 9 na stronie, 580 zaimportowanych w stanie).
- **Testy:** `scraper/test_bzp_backfill.py` 7/7; testy powiązane (scraper, repairer) 63 zaliczone.


## BZP: szybsze zbieranie, najwyżej 20 zapytań/min (6.11.2026, kod gotowy, niewdrożone; decyzja właściciela)

- **Podstawa:** urząd gwarantuje 30 zapytań/min z adresu IP (ezamowienia.gov.pl/pl/integracja/, od 6.10.2026). Nasza karta dostępu pozwalała na 1 zapytanie / 3 min i 480 / dobę. Właściciel: „najwyżej 20 zapytań na minutę”.
- **Kod:** `scraper/bzp_backfill.py::bzp_backfill_run` (wiele stron w jednym uruchomieniu: budżet 240 s, najwyżej 120 stron, pauza 3,2 s między stronami, czyli < 20/min; odczekanie bramki hosta zamiast błędu; odpowiedź 429 zatrzymuje zbieracz do czasu Retry-After przez cache `bzp:pause_until`). Zadanie `import_bzp_metadata` woła runner (limity 330/360 s), beat `bzp-metadata-3m` co 5 min (nazwa wpisu bez zmian).
- **Nowa karta dostępu:** `configure_bzp_metadata_source` tworzy kartę v+1: `minimum_interval_seconds=3` (20/min), `daily_request_cap=5000`; stara karta (180 s, 480/dobę) zostaje w historii, bo wygrywa najwyższa wersja. Karta wchodzi w życie dopiero po poleceniu na serwerze (za zgodą właściciela).
- **Testy:** `scraper/test_bzp_backfill.py` (4 nowe testy runnera), `test_configure_bzp_metadata_source.py` (wymiana karty); scraper + repairer + automatyk + przeszlosc_stan: 848 zaliczonych, 1 pominięty.
- **Do sprawdzenia po wdrożeniu:** rekordy BZP w „Stan danych” rosną; brak błędów `host_rate_limited` w stanie `official-backfill:bzp:v1`; liczba żądań dziennie poniżej 5000; kursor schodzi w głąb historii.


## Pozycja 2, część a: filtr po pośle i CSV w Odstępstwach (6.11.2026, niewdrożone)

- **Backend (`news/voting_anomalies.py`):** nocne przeliczenie zapisuje wszystkie odstępstwa w zwartej formie (`ev`: tabela głosowań, tabela posłów, wiersze), a klub ma listę `rebels` (poseł, liczba). Nowe parametry `GET /api/przeszlosc/odstepstwa/`: `zdarzenia=1` (pełna lista JSON, opcjonalnie `klub`, `posel`), `eksport=csv` (średniki, BOM, komórki zabezpieczone przed formułami arkusza; nazwa pliku `odstepstwa-{posel-ID|klub|wszystkie}-{okres}.csv`). Parametr nazywa się `eksport`, nie `format`, bo `format` przejmuje DRF. Odpowiedź publiczna listy klubów nadal nie zawiera `ev` ani `members`.
- **Ważne po wdrożeniu:** stary zapis nie ma pola `ev`, więc pełna lista i CSV dają 409 („pojawi się po nocnym przeliczeniu”), a strona zostaje przy skrócie 30. Przeliczenie ręczne: komenda `odstepstwa` (albo poczekać na 4:35). Frontend sam przechodzi na pełną listę, gdy ją dostanie.
- **Frontend (`app/przeszlosc/Odstepstwa.tsx`, `odstepstwa.css`):** wiersz „Poseł z klubu X” z listą posłów i liczbą odstępstw (nad obu boksami, żeby boksy zostały równe), pełna lista zamiast skrótu 30, po „Pokaż więcej” do 100 pozycji, odnośnik „Pobierz CSV (N)”. Filtr i okres/klub resetują się razem.
- **Sprawdzone:** pytest `news/test_voting_anomalies.py` 11/11 (3 nowe: zwarta lista i filtry, zabezpieczenie formuł w CSV, API i brak `ev`); `node --test tests/*.test.cjs` 149/149, `pnpm typecheck`, `pnpm build`; pomiar Playwright 1440 i 390 px z atrapą API (lista i CSV zmieniają się po wyborze posła, bez przewijania poziomego, cele 44 px).
- **Niesprawdzone na produkcji:** rozmiar zapisu `ev` dla całej kadencji (szacunek kilka MB) i czas odpowiedzi eksportu; do zmierzenia po pierwszym przeliczeniu.
- **Zostaje z pozycji 2:** „Mój poseł” (wejście po nazwisku/okręgu), imienne głosy w profilu osoby, etykiety tematów przy głosowaniach.


## Pozycja 2, część b: „Mój poseł” (6.11.2026, niewdrożone)

- **Co to jest:** strona `/przeszlosc/moj-posel`: wybór okręgu wyborczego → posłowie z okręgu (klub, odnośnik do profilu w przeszłość.today; gdy posła nie ma w rejestrze osób, odnośnik do oficjalnej strony Sejmu i adnotacja „brak profilu u nas”).
- **Backend:** `news/przeszlosc_moj_posel.py`, `GET /api/przeszlosc/moj-posel/` (lista okręgów z liczbą posłów) i `?okreg=Kraków` (posłowie, wielkość liter bez znaczenia, 404 dla nieznanego okręgu). Dane z `ParliamentaryRosterEntry` (źródło `sejm`, aktywni, z okręgiem), powiązane z `PublicFigure`; bez sieci i AI. Wpis „Mój poseł” w rejestrze funkcji (`news/przeszlosc_dostep.py`, strona „Funkcje”).
- **Frontend:** `app/przeszlosc/MojPosel.tsx`, `moj-posel/page.tsx`, `moj-posel/MojPoselPage.tsx`, `moj-posel.css`; odnośnik „Szukasz swojego posła? Wybierz okręg →” na stronie Odstępstw. Nie dodano szóstej pozycji do menu (menu ma 5, szkoda na pasek), więc strona jest dostępna z Funkcji i Odstępstw; do rozważenia po decyzji właściciela.
- **Sprawdzone:** pytest `test_przeszlosc_moj_posel.py` (2), `test_pracownia_osint`, `test_przeszlosc_dostep` razem 14 zaliczonych; `node --test` 152/152, typecheck, build; pomiar Playwright 1440 i 390 px (atrapa API): odstęp od menu 32 i 24 px, wiersze 64 px, pole 44 px, bez przewijania poziomego.
- **Niesprawdzone na produkcji:** czy pole `district` roster ma wartości dla wszystkich posłów i jak wyglądają nazwy okręgów (numer okręgu nie jest zapisywany, tylko nazwa z API Sejmu); ile figur ma powiązanie z rejestrem. Do odczytu po wdrożeniu: `/api/przeszlosc/moj-posel/`.
- **Zostaje z pozycji 2:** imienne głosy w profilu osoby, etykiety tematów przy głosowaniach.


## Pozycja 2, część c: oddane głosy w profilu; etykiety tematów wstrzymane (6.11.2026, niewdrożone)

- **Imienne głosy w profilu już istniały** (`GlosowaniaOsoby.tsx`, `/api/przeszlosc/osoba/<id>/glosowania/`: pełna lista z filtrami kadencji, wyniku, zgodności z klubem i dat, ładowana po przewinięciu do sekcji). Wniosek z rundy person „dziś tylko sumy” wynikał z lazy-ładowania (narzędzie bez przewijania); nie ma czego dublować.
- **Dodane:** `attendance` w odpowiedzi (`news/przeszlosc_glosowania_rodzaje.py::attendance`): liczba głosowań, oddane głosy (za/przeciw/wstrzymał się), bez głosu; liczone po kadencji i datach, bez filtrów wyniku i klubu; tylko Sejm (dla PE `null`). Wiersz „Oddane głosy: X z Y głosowań (Z%)…” nad listą; nazwa celowo nie „frekwencja”, bo brak głosu to nieobecność albo niegłosowanie, a powodu nie znamy i nie oceniamy.
- **Testy:** pytest `test_przeszlosc_glosowania_rodzaje.py` 5/5 (nowy: obecność niezależna od filtrów, PE bez obecności); `node --test` 154/154; typecheck i build.
- **Etykiety tematów przy głosowaniach: NIE zbudowane (decyzja potrzebna).** Słownik `news/topics.py` to tagi wydawców i ma zasadę „dokładne tagi, nigdy zgadywanie po tytułach”. Opcje: (A) reguły słów kluczowych w tytule, jawnie opisane „wg słów w tytule”, po recenzji Prawnika i Recenzenta (szybkie, ale to heurystyka); (B) powiązanie głosowania z drukiem, procesem legislacyjnym i komisją (źródło oficjalne, ale większa praca i brak komisji w wielu tytułach, np. „Sprawozdanie Komisji o uchwale Senatu…”). Rekomendacja: B, A tylko jako uzupełnienie z wyraźną etykietą.


## Wdrożenie 6.11.2026 (wykonał właściciel na VPS, gałąź `claude/upbeat-noether-7k08ac`, commit `d273d59`)

- **Zrobione i sprawdzone:** kopia bazy; kod pobrany (`d273d59`); `PUBLIC_RECORDS_ASSETS_ENABLED=false`; przebudowa i start `frontend`, `backend`, `worker`, `beat` (budowa 197 s, wszystkie `Up`); `configure_bzp_metadata_source --apply` utworzył kartę dostępu v2 (3 s, 5000/dobę); `manage.py odstepstwa` przeliczył wynik (kadencja: 1851 głosowań, 3968 głosów wbrew klubowi; 90 dni: 457 głosowań, 1182). Publicznie: `/api/przeszlosc/moj-posel/?okreg=Kraków` zwraca 22 posłów z profilami; Stan danych: ok 25, stale 3, empty 2, off 2 (`assets` wyłączone).
- **Zrobione, niesprawdzone:** BZP na nowej karcie (kursor miał ruszyć z 26.07 w głąb historii; Stan danych nadal pokazywał 9 rekordów i ostatni zapis 6.10 kilka minut po starcie). Odpowiedź `zdarzenia=1` dla dużego klubu ma ok. 330 tys. znaków; frontend ogranicza widok do 100 pozycji, ale API zwraca całość (do przycięcia, np. stronicowaniem).
- **Odkryte:** BZP ma 580 artykułów, ale 9 rekordów `PublicRecord`; zapis rekordu połykał błędy (`except: pass`). Kod loguje teraz ostrzeżenie `bzp notice record not saved: ...` (do wdrożenia razem z następną porcją); właściciel dostał polecenie diagnostyczne z próbą zapisu w cofanej transakcji.
- **Rollback:** poprzedni wdrożony commit `84bdb04`.


## BZP działa na produkcji; blokada przebiegów i przycięcie JSON (6.11.2026, kod gotowy, niewdrożone)

- **Zrobione i sprawdzone na produkcji (odczyt 02:16 UTC):** BZP po wdrożeniu `d273d59` nadrabia historię: kursor z 26.07 do 01.02.2026 w ok. 13 min, artykułów 2334 (było 589), rekordów `PublicRecord` 1754 (było 9), `last_error` pusty, zadanie `import_bzp_metadata` kończy się `succeeded` (24-57 stron na przebieg, 98-243 s). Przyczyną zatrzymania było okno UTC (poprawka `4a443b1`); wdrożony kod ma poprawkę, karta v2 (3 s, 5000/dobę) aktywna. Podejrzenie połykanego błędu zapisu rekordu nie potwierdziło się (próba zapisu na Postgresie OK; 9 rekordów to ślad po starym przebiegu).
- **Zrobione, niesprawdzone (kod, niewdrożone):** `bzp_backfill_run` ma blokadę „jedno uruchomienie naraz” (cache `bzp:run_lock`, wygasa po budżecie + 90 s); w logu produkcji nakładające się przebiegi walczyły o bramkę hosta (`host_rate_limited:149.8` w wyniku zadania, choć dane rosły). Odpowiedź `GET /api/przeszlosc/odstepstwa/?zdarzenia=1` ma `limit` (domyślnie 100, najwyżej 500; pełna lista tylko w `eksport=csv`), bo dla dużego klubu miała ok. 330 tys. znaków.
- **Testy:** `scraper/test_bzp_backfill.py` + `news/test_voting_anomalies.py`: 24 zaliczone.
- **Do sprawdzenia po następnym wdrożeniu:** w logach worker brak `host_rate_limited` w wynikach zadania BZP; kursor dochodzi do ok. 22.09.2025 (365 dni przed odcięciem 22.09.2026), potem przejście „do przodu” od 22.09.2026.


## Etykiety tematów przy głosowaniach, opcja B (6.11.2026, kod gotowy, niewdrożone)

- **Decyzja właściciela:** „b”, czyli oficjalne powiązanie głosowanie → proces legislacyjny → druk i komisja, bez zgadywania po słowach w tytule.
- **Kod:** `news/glosowania_tematy.py` buduje indeks z rekordów `PublicRecord` (`processes/process`: lista `votings`, etapy z `committeeCode`, `titleFinal`, `documentType`; nazwy komisji z `committees/committee`), cache 26 h, odświeżany co noc w `voting_deviations_task` (`news/tasks.py`) i leniwie przy pierwszym użyciu. `news/przeszlosc_glosowania_rodzaje.py::_sejm_rows` dodaje do wiersza głosowania pole `topic` (`druk`, `tytul`, `rodzaj`, `komisje`) albo `null`. Głosowanie bez procesu (wnioski formalne, uchwały) nie ma etykiety: to „brak powiązania w naszych danych”.
- **Frontend:** `GlosowaniaOsoby.tsx` dopisuje do linii pod tytułem „druk 3300, Komisja Zdrowia” (do 2 komisji), pełny tytuł procesu w podpowiedzi (`title`).
- **Sprawdzone:** pytest `test_przeszlosc_glosowania_rodzaje.py` 6/6 (etykiety tylko z rekordów procesu i komisji, brak etykiety dla głosowania bez procesu), razem z `test_voting_anomalies` 17 zaliczonych; `node --test` 155/155, typecheck, build.
- **Niesprawdzone na produkcji:** jaki odsetek głosowań ma powiązany proces (procesów 1776, głosowań ok. 1850; część procesów może nie mieć listy głosowań), czas pierwszego zbudowania indeksu (iteracja po ok. 1800 rekordach z JSON etapów) i rozmiar cache. Cache profilu osoby trwa 1 h, więc etykiety pojawią się po jego wygaśnięciu albo zmianie wersji.
- **Zostaje:** etykieta w ogólnym widoku `/przeszlosc/glosowania` (lista wszystkich głosowań) i filtr „według komisji”.


## Źródła: Biała lista VAT, nowy adres API i dzienny limit (6.11.2026, kod gotowy, niewdrożone)

- **Odkrycie (oficjalna strona gov.pl/web/kas/api-wykazu-podatnikow-vat):** od 15.10.2026 `wl-api.mf.gov.pl` jest tylko przekierowany, a **stary adres przestaje działać 1.12.2026**; nowy: `https://wykazpodatnikowvat.mf.gov.pl/api` (struktura odpowiedzi ta sama, sprawdzone na żywo). Limity urzędu: metoda `search` 100 zapytań dziennie po 30 NIP, `check` 5000 podmiotów, API WL2 (`/api2`, tylko status) 50 000 zapytań dziennie; po przekroczeniu blokada do 0:00 także dla wyszukiwarki www.
- **Zmiany (kod):** `news/biala_lista_vat.py` (nowy): adres z `BIALA_LISTA_API` (domyślnie nowy), wspólny dzienny licznik zapytań w cache (`BIALA_LISTA_LIMIT_DZIENNY`, domyślnie 90) używany też przez kolejkę NIP→KRS (`news/krs_pokrycie.py`: odpowiedź `limit` zatrzymuje partię bez ponowień i bez kar w kolejce), zbieracz statusu VAT dla `RegisteredOrganisation` z NIP (`PublicRecord` `biala_lista/vat_status`: status, daty rejestracji/wykreślenia/przywrócenia, podstawa, rachunki wirtualne, LICZBA rachunków, historia zmian statusu do 10 wpisów). Nie zapisujemy numerów rachunków, adresów, PESEL, reprezentantów, prokurentów ani wspólników. Zadanie `news.tasks.biala_lista_vat_task` codziennie o 2:33 (po kolejce KRS o 1:47), do 20 zapytań (600 NIP), odświeżanie statusu co 7 dni; flaga `BIALA_LISTA_VAT_ENABLED` (domyślnie włączone). Wpis w rejestrze agentów (`biala-lista-vat`), w „Stanie danych” (źródło „Status VAT podmiotów (Biała lista MF)”), pole `vat` w `/api/przeszlosc/spolka/<KRS>/` i wiersz „Status VAT: …” na stronie spółki (`DrzewoPieniedzy.tsx`, `vatLine`).
- **Sprawdzone:** pytest `news/test_biala_lista_vat.py` 6/6 (nowy adres, brak danych o osobach, wspólny limit z kolejką KRS, zapis i zmiana statusu, błędy i wyłączenie, API spółki); pełny backend bez porażek (4000 testów, 0 F/E); frontend `node --test` 160/160, typecheck.
- **Niesprawdzone na produkcji:** realna odpowiedź dla 679 podmiotów z NIP (część to JST bez KRS w Białej liście: `krs: null` w odpowiedzi; zbieracz opiera się na NIP), czas pierwszego przebiegu, wpływ na limit 100/dobę razem z kolejką KRS (10 + do 20 zapytań dziennie). Do odczytu po wdrożeniu: Stan danych (źródło `biala_lista`), `/api/przeszlosc/spolka/<KRS>/` (pole `vat`).
- **Zostaje w „źródłach”:** BIR/REGON (SOAP, klucz na wniosek do GUS: wymaga działania właściciela), SUDOP (pomoc publiczna), RCN i ULDK (nieruchomości), lista beneficjentów funduszy 2021-2027. Sygnał S5 (wspólny rachunek/adres) wymaga osobnej decyzji (przechowywanie numerów rachunków).


## Siedziba podmiotu i dopasowanie po nazwie z drugim danym; klient KRS po nazwie (6.11.2026, kod gotowy; wdrożenie zleca właściciel)

- **Migracja `0173_registeredorganisation_seat`:** `RegisteredOrganisation.seat_city`, `seat_postal_code`, `seat_voivodeship` (puste domyślnie; wypełniane z odpisu KRS przy kolejnym pobraniu odpisu przez kolejkę KRS, `news/krs.py::seat` czyta `dzial1.siedzibaIAdres.siedziba/adres`; **układ pola sprawdzony tylko na danych syntetycznych**, na prawdziwym odpisie do potwierdzenia po wdrożeniu; bez ulicy i numeru). `makemigrations --check`: bez zmian.
- **`news/dopasowanie_nazw.py`:** normalizacja nazwy (bez diakrytyków, cudzysłowów, zapis form prawnych), `choose` (klasy `nazwa_i_siedziba`, `nazwa`, brak przy niejednoznaczności; sprzeczna siedziba = flaga `conflict`), `match_own` (dopasowanie do podmiotów z bazy). Zasada: `docs/PRZESZLOSC_ZRODLA_DANYCH.md`. Nie ma jeszcze konsumenta (czeka na plik listy projektów UE 2021-2027).
- **`news/krs_nazwa.py`:** klient wyszukiwania w KRS po nazwie, **wyłączony bez `KRS_NAME_SEARCH_URL`**; bez klucza strony wyszukiwarki, bez nagłówków origin/referer; format zapytania i odpowiedzi z obserwacji publicznej strony (`listaPodmiotow`: nazwa, miejscowosc, numer, typRejestru, czyOPP, czyUpadlosc); limit 1 zapytanie/s, cache 24 h. Projekt wniosku do MS: `docs/WNIOSEK_MS_WYSZUKIWANIE_KRS_PO_NAZWIE.md` (niewysłany).
- **Testy:** `news/test_dopasowanie_nazw.py` 8/8; sweep (krs, organisation, drzewo, stan, agent, schedule) 364 zaliczone. Pełny backend z VAT-em wcześniej bez porażek.


## Stan wdrożenia na noc 6/7.11.2026 i procedura na rano

- **Na produkcji (VPS `/srv/spin-clinic`) działa commit `d273d59`** (gałąź `claude/upbeat-noether-7k08ac`). Wdrożenie 6.11 o ok. 03:00 przeszło tylko częściowo: kroki budowy poszły na starym kodzie, bo `git fetch`/`pull` nie zakończył się przed budową (budowa trwała 5 s zamiast ok. 200 s, brak migracji `0173`). Nic się nie zepsuło: usługi wstały na `d273d59`. Świeża kopia bazy z 6.11 03:24 istnieje (`/srv/backups/spin_clinic-20261106-0322.sql.gz`, 425 MB).
- **Czeka na wdrożenie:** commity do `0a9d55f` (blokada BZP, limit JSON, etykiety tematów, nowy adres Białej listy i status VAT, migracja `0173`, dopasowanie nazw, klient KRS po nazwie wyłączony, `deploy/wdroz.sh`).
- **Procedura (właściciel, terminal SSH serwera):** `cd /srv/spin-clinic && git fetch origin claude/upbeat-noether-7k08ac && git pull --ff-only origin claude/upbeat-noether-7k08ac && sh deploy/wdroz.sh`. Skrypt sam robi kopię bazy, buduje, czeka na backend, sprawdza migracje i przelicza Odstępstwa; zatrzymuje się przy pierwszym błędzie. Ostatnia linia: „GOTOWE. Wdrożony commit: 0a9d55f”.
- **Po wdrożeniu do sprawdzenia:** Stan danych (źródło „Status VAT podmiotów”), pole `vat` w `/api/przeszlosc/spolka/<KRS>/`, kolumny siedziby w `RegisteredOrganisation` po kolejnych odpisach KRS, etykiety `topic` w głosowaniach profilu, BZP bez `host_rate_limited`.


## Wdrożenie 6.11.2026 (rano, commit `5dc04bd`) i filtr „według komisji” w ogólnym widoku głosowań

- **Wdrożenie wykonane przez `deploy/wdroz.sh` (właściciel):** budowa 235 s, `backend odpowiada`, `wszystkie migracje zastosowane` (w tym `0173`), Odstępstwa przeliczone, wszystkie usługi `Up`. **Sprawdzone publicznie po wdrożeniu:** Stan danych ma źródło „Status VAT podmiotów (Biała lista MF)” (status `empty`, jeszcze bez pobrania: zadanie nocne o 2:33 czasu harmonogramu minęło przed wdrożeniem; pierwsze pobranie następnej nocy albo ręcznie), `/api/przeszlosc/odstepstwa/?...&zdarzenia=1&limit=3` zwraca `total` 484 i 3 pozycje (limit działa), BZP `ok`, 3513 rekordów, `last_error` pusty; KRS: podmioty 866 (wcześniej 803), z NIP 747.
- **Do sprawdzenia (niezależnie od wdrożenia):** BZP ma tylko 3513 rekordów za rok historii (oczekiwano znacznie więcej przy ok. 1000+ ogłoszeń dziennie w dni robocze); możliwe, że endpoint `Board/Search` zwraca ograniczony podzbiór albo strona jest ucinana. Do zbadania: liczba rekordów na dzień roboczy z ImportState i odpowiedź API dla jednego dnia roboczego.
- **Nowe w kodzie (niewdrożone):** ogólny widok głosowań `/przeszlosc/glosowania`: filtr „Komisja” (`?komisja=`, lista z liczbą głosowań, `committees` w odpowiedzi API) i etykieta „druk 3300, Komisja Zdrowia” w jednej linii pod tytułem; `news/glosowania_tematy.py` (`committees`, `keys_for_committee`), `news/przeszlosc_v3.py::votes_page` (filtr po grupach (kadencja, posiedzenie), nieznana komisja daje pustą listę, nie „wszystko”). Testy: pytest `test_przeszlosc_glosowania_rodzaje.py` + `test_spina_v3.py` 54 zaliczone; `node --test` 163/163 (nowy `135-...komisja`, poprawione `119-...lista` o pole `komisja`), typecheck, build.


## Runda person 2 i poprawki z raportów (6.11.2026, kod gotowy, niewdrożone)

- Raport: `docs/PERSONY_PRZESZLOSC_RUNDA2.md` (obywatel 7/10, compliance 5/10, radny 3/10). Największa otwarta luka: jednostki samorządu i podmioty bez KRS nie są wyszukiwalne, a BZP po NIP nie ma widoku (plan „podmiot po NIP” w raporcie).
- Poprawione w kodzie: `vat` ze statusem „jeszcze niepobrany”/„brak NIP” zamiast `null` (`news/biala_lista_vat.py::status_for`, `vatLine`), stała notatka o zakresie listy osób (`news/drzewo_pieniedzy.py::PEOPLE_SCOPE`), `legend` i skrócone po słowie tytuły w odstępstwach (`news/voting_anomalies.py`; tytuły w zapisie po następnym nocnym przeliczeniu), echo `zgodnosc` zamiast `klub` w głosowaniach posła, `sejm_id` i skrót odstępstw 90 dni przy pośle w „Mój poseł”.
- Testy: backend (VAT, odstępstwa, Mój poseł, głosowania, drzewo) 51+ zaliczonych; `node --test` 165/165; typecheck.


## PKW: odczyt uchwał o sprawozdaniach partii i widok „Finanse partii” (6.11.2026, kod gotowy, niewdrożone)

- **Stan danych PKW na produkcji (odczyt właściciela):** 969 rekordów `financial_document` (tytuł, adres PDF na pkw.gov.pl), bez dat i bez żadnych odczytanych kwot (`financial_row` nie ma ani jednego).
- **Co jest w PDF-ach (sprawdzone na 3 próbkach przez Firecrawl):** (1) uchwały PKW o sprawozdaniach partii (np. Polska Partia Piratów, „EwP”): tekst z warstwą tekstową, podpis elektroniczny; w zdaniach decyzja (przyjąć/odrzucić, „ze wskazaniem uchybienia”), rok, łączne przychody, wpłaty osób fizycznych (składki, darowizny zbiorczo), wartości niepieniężne, wpływy na Fundusz Wyborczy; bez nazwisk darczyńców. (2) Sprawozdania komitetów wyborczych: **skany formularzy** (bez warstwy tekstowej, z danymi osobowymi pełnomocników i adresami). Zasada: nigdy OCR, więc skanów nie czytamy.
- **Kod:** `scraper/public_record_parsers.py::pkw_report` (wzorce na tekście uchwały, cytat przy każdej kwocie, bez numerów rachunków i nazwisk), `scraper/public_records.py` (nowy rodzaj zadania `pkw_pdf`: tekst z PDF przez istniejące `pdf_text`, rekord `financial_report` pod tym samym kluczem co dokument; skan/inny dokument dostaje rekord „nieczytelny” z powodem), `scraper/management/commands/pkw_raporty_zasiej.py` (jednorazowo dodaje zadania `pkw_pdf` dla istniejących dokumentów; bez `--apply` tylko liczy), `news/przeszlosc_pkw.py` + `GET /api/przeszlosc/pkw/` (q, rodzaj, z_danymi, strona; streszczenie uchwały przy dokumencie; data publikacji z prefiksu pliku = czas wgrania na stronę PKW), wpis w „Funkcjach”, strona `/przeszlosc/finanse-partii` (`FinansePartii.tsx`).
- **Wdrożenie i uruchomienie odczytu (za zgodą właściciela):** po wdrożeniu jednorazowo `manage.py pkw_raporty_zasiej --apply` (tylko dodaje zadania). Zbieracz PKW czyta pliki w swoich limitach: domyślnie 40 żądań na dobę i 4 na tick co 15 minut, więc ok. 969 PDF-ów to ponad 3 tygodnie; `PUBLIC_RECORDS_PKW_DAILY_CAP` (do 10000, w granicach karty dostępu pkw.gov.pl) przyspiesza.
- **Sprawdzone:** pytest `scraper/test_pkw_raporty.py` (test na prawdziwym tekście uchwały Piratów, odrzucenie, separator tysięcy, skan, komenda), `news/test_przeszlosc_pkw.py` (spis, filtr, streszczenie, powody braku odczytu), `scraper/test_public_records.py` (zaktualizowana asercja: PDF-y z `/uploaded_files/` dostają `pkw_pdf`); sweep backendu 353 zaliczone; `node --test` 169/169, typecheck, build; pomiar Playwright 1440 i 390 px (atrapa API).
- **Niesprawdzone na produkcji:** ilu z 969 plików to uchwały z warstwą tekstową (szacunek: dziesiątki do kilkuset, reszta skany), pokrycie wzorców dla innych wariantów uchwał (np. wydatki, koalicje, odrzucenia), tempo i obciążenie hosta pkw.gov.pl. Do odczytu po kilku dniach: `PublicRecord` `financial_report` (liczba czytelnych vs nieczytelnych) i `/api/przeszlosc/pkw/?z_danymi=1`.


## Podmiot po NIP dla gmin i podmiotów bez KRS (6.11.2026, kod gotowy, niewdrożone)

- **Cel:** największa luka z rundy person 2 (radny 3/10): jednostki samorządu nie mają KRS, więc nie dało się ich wyszukać, mimo że mamy ogłoszenia BZP po NIP zamawiającego.
- **Kod:** `news/przeszlosc_podmiot_nip.py`, `GET /api/przeszlosc/podmiot/<NIP>/` (walidacja sumy kontrolnej NIP, 400 dla niepoprawnego; `status`: `found` / `empty` / `krs` z odsyłaczem do strony spółki). Używa tych samych funkcji i zasad co drzewo spółki (`drzewo_pieniedzy.contracts/grants`: BZP jako zamawiający po NIP, TED jako wykonawca, FTS po VAT; kwoty wątpliwe poza sumami); nazwa, miejscowość i województwo tylko z ogłoszeń BZP tego samego NIP-u; nic o osobach; bez zgadywania po nazwie. `news/przeszlosc_spolki.py::search`: przy NIP spoza bazy dodaje `nip_page` (url, has_data) i komunikat; przy nazwie typu „gmina/urząd/miasto…” dopisuje, że jednostki samorządu zwykle nie mają KRS i trzeba wpisać NIP.
- **Frontend:** strona `/przeszlosc/podmiot/<NIP>` (`PodmiotNip.tsx`, `podmiot-nip.css`), link w wyszukiwarce spółek (`TopicTree.tsx`: „Zobacz ogłoszenia i dotacje po NIP →”).
- **Sprawdzone:** pytest `news/test_przeszlosc_podmiot_nip.py` (suma kontrolna, inne zapisy NIP, inny NIP nie wchodzi, brak danych, podmiot z KRS, walidacja i flaga, wskazówki wyszukiwarki) + `test_krs_pokrycie` 18 zaliczonych; `node --test` 172/172, typecheck, build; pomiar Playwright 1440 i 390 px (atrapa API).
- **Niesprawdzone na produkcji:** ile gmin ma ogłoszenia (BZP ma 3513 rekordów; wcześniej zaobserwowano niski wolumen), jakość nazw z BZP. Zwrotnie do rundy person: radny ma ścieżkę „NIP gminy → ogłoszenia”; kwot i wykonawców BZP nie podaje, więc lista to metadane ogłoszeń.


## Wdrożenie 6.11.2026 (wieczór, commit `eba10bd`)

- **Zrobione i sprawdzone (wynik wklejony przez właściciela):** `deploy/wdroz.sh` przeszedł do końca: budowa 212 s, `backend odpowiada`, `wszystkie migracje zastosowane` (bez nowych od `0173`), Odstępstwa przeliczone (kadencja 10: 1851 głosowań, 4 oznaczone), usługi `Up`. Wdrożone razem: filtr komisji i etykiety tematów w ogólnym widoku głosowań, poprawki z rundy person 2, PKW (odczyt uchwał, `/przeszlosc/finanse-partii`), podmiot po NIP.
- **Kolejka PKW:** `manage.py pkw_raporty_zasiej --apply` dodało 969 zadań `pkw_pdf` (do odczytu 969, odczytanych 0). `PUBLIC_RECORDS_PKW_DAILY_CAP=200` ustawione w `.env.production` (worker i beat przeładowane), czyli odczyt całości ok. 5 dni zamiast ponad 3 tygodni.
- **Sprawdzone po wdrożeniu (w Django test client z serwera):** `/api/przeszlosc/pkw/`, `/podmiot/5771960580/`, `/podmiot/7962958767/`, `/glosowania/`, `/stan-danych/` zwracają 200. Właściciel obejrzał stronę `/przeszlosc/podmiot/5771960580` (Gmina Niegowa): 1 zamówienie BZP (Orlik 2012, 27.07.2026), 0 dotacji FTS, opis „podmiot bez wpisu KRS”.
- **Niesprawdzone:** filtr komisji i „Mój poseł” na ekranie, strona Finanse partii z danymi (zależy od odczytu kolejki), pierwszy przebieg Białej listy (noc 2:33), pomiary wyglądu strony podmiotu na produkcji (uwagi niżej).
- **Poprawione w kodzie (7.11, z zrzutu właściciela; niewdrożone):** (1) BETA zderzała się z logo, bo na urządzeniach bez Georgii napis w SVG był szerszy niż ramka (241 zamiast 204 jedn.): `textLength=204` w `Logo` (`ui.tsx`) daje stałą szerokość w każdym kroju; (2) pusta przestrzeń pod pozycją w boksie: globalny szablon wierszy dawał dodatkowy pusty wiersz siatki i 12 px odstępu, teraz `grid-template-rows: none` i wiersz 56 px (dolny odstęp 16 px); (3) przypis źródeł: odnośniki były blokami `inline-flex` o wysokości 51 px, teraz zwykłe odnośniki w tekście, równy krok linii (1440 i 390 px zmierzone). Testy 172/172, typecheck, build. Podmiot z jednym ogłoszeniem potwierdza niski wolumen BZP (3513 rekordów/rok), do zbadania.


## Szybki start dla innej sesji (np. iApply) - stan na 6.11.2026

- **Gdzie:** repozytorium `patrykostwald/spinaker`, gałąź `claude/upbeat-noether-7k08ac`, PR #29 (szkic). Na produkcji (VPS `/srv/spin-clinic`) działa commit `eba10bd`.
- **Co czytać:** sekcje powyżej (od końca: wdrożenie 6.11 wieczór, podmiot po NIP, PKW, runda person 2) oraz `docs/PLAN_PRZESZLOSC_OSINT.md` i `docs/PRZESZLOSC_ZRODLA_DANYCH.md`.
- **Czeka:** odczyt 969 PDF-ów PKW (ok. 5 dni, limit 200/dobę), pierwszy przebieg Białej listy VAT (noc 2:33), niski wolumen BZP (3513 rekordów/rok) do zbadania, trzy poprawki układu strony podmiotu (BETA przy logo, pusta przestrzeń w boksie, odstępy przypisu), pismo do MS w sprawie KRS po nazwie (niewysłane, wymaga zgody właściciela).
- **Zasady twarde:** nie ruszać kodu spin.clinic; nie zapisywać klucza strony wyszukiwarki KRS; bez OCR; bez danych osób prywatnych; łączenie podmiotów tylko po NIP/KRS; wdrożenie wyłącznie `sh deploy/wdroz.sh` z `/srv/spin-clinic` i tylko za zgodą właściciela; odpowiedzi po polsku.


## Rozbieżność serwer/GitHub (6.11.2026 wieczór) i zablokowane wdrożenie 98e1740

- **Serwer (`/srv/spin-clinic`) ma lokalny, niewypchnięty commit scalający `16d57a0c`** (`Merge origin/claude/napraw-mercury-przekaz-883a1d` do gałęzi przeszlosc.today; gałąź Mercury = hotfix modelu `mercury-3` i `inception.chat`, praca drugiej sesji, spin.clinic). Na GitHubie gałąź przeszlosc.today kończy się na `98e1740`; serwer jest „ahead 2”. Kontenery `backend`, `worker`, `beat` na serwerze były przebudowane ok. 10 minut przed odczytem (najpewniej wdrożenie hotfixu Mercury z tego scalenia), `frontend` starszy (nasze poprawki układu `b1636c2` jeszcze niewdrożone). **Niesprawdzone:** dokładny commit, z którego zbudowano backend.
- **Wdrożenie `deploy/wdroz.sh` wstrzymane przez krok kopii bazy:** lokalna kopia OK (`/srv/backups/spin_clinic-20261106-1441.sql.gz`, 408 MB), wysyłka do Backblaze B2 odrzucona (HTTP 403 przy PUT; klucz wygasły/odwołany albo bez prawa zapisu). Skrypt słusznie nic nie zmienił. Do naprawy przez właściciela w panelu B2 i `.env.production` (`B2_KEY_ID`, `B2_APP_KEY`); Dyżurny alarmuje po 26 h bez kopii.
- **Na serwerze nieśledzone pliki:** `.env.production`, `.env.productionx` (nieznane pochodzenie, prawdopodobnie kopia z sekretami), `.konsylium-powtorz-0610.done`, `archiwa/`. Nie commitować; `.env.productionx` do wyjaśnienia przez właściciela.
- **Zasada na przyszłość:** nie scalać cudzych gałęzi lokalnie na serwerze bez wypchnięcia i zapisu w HANDOFF; wdrażać wyłącznie z gałęzi na GitHubie.


## Podmioty z doniesień medialnych przy osobie (6.11.2026, kod gotowy, niewdrożone)

- **Decyzja właściciela:** osobne okno przy osobie: źródło wzmianki w mediach + podmiot z naszej bazy, bez opisu „jakie połączenie i dlaczego”, z kategorią doniesienia (wzmianka / rzekome powiązanie / sprostowane lub zaprzeczone / inne). Właściciel zgodził się na **kolejkę zatwierdzania** (nic nie jest publiczne bez przeglądu zespołu).
- **Kod:** model `PublicFigureMediaMention` (`news/political_models.py`, migracja `0174`; osoba, podmiot z KRS, kategoria, podstawa dopasowania `identifier|name_only`, link, tytuł, redakcja, data, cytat do 300 znaków, status `pending_review|published|rejected`; zmiana treści opublikowanej pozycji cofa ją do kolejki), panel admina z akcjami „Opublikuj”/„Odrzuć” (`political_admin.py`, bez usuwania), `news/przeszlosc_doniesienia.py::mentions_for` (tylko opublikowane, podmiot nie zarchiwizowany; świeże, poza cache profilu), pole `org_mentions` w `GET /api/przeszlosc/osoba/<id>/`, komenda `przeszlosc_doniesienia_import <plik.csv> [--apply]` (bez `--apply` tylko sprawdza; wiersze trafiają do kolejki; zakazane kolumny PESEL/data urodzenia), frontend `PodmiotyZMediow.tsx` + `podmioty-media.css` w `PersonProfile.tsx` po „Wzmiankach” (okno znika, gdy brak opublikowanych pozycji).
- **Zasady (z konsylium Prawnika do dopracowania):** stała notka „Wzmianka w mediach nie jest dowodem powiązania”; dopasowanie tylko po KRS/NIP albo etykieta „niepotwierdzone” (sama nazwa); tylko link, tytuł, redakcja, data i krótki cytat (bez kopiowania tekstów); link „Poprawki” do zgłaszania błędów; podmiot wyłącznie z naszej bazy.
- **Sprawdzone:** pytest `news/test_przeszlosc_doniesienia.py` 6/6 (kolejka, kategorie, cofnięcie do przeglądu, walidacje, import), `node --test` 176/176 (nowy `138-…doniesienia-medialne`), typecheck; pomiar Playwright 1440/390 px na atrapie danych (wiersze 96 px, tytuł okna w jednej linii, bez przewijania poziomego, cele 44 px).
- **Niesprawdzone / zaplanowane:** (1) **zbieranie doniesień**: nie ma jeszcze żadnego rekordu; źródła mediów do ustalenia (Research + Prawnik): lista redakcji z RSS lub wyszukiwanie ręczne/agentowe w kolejce, pierwsze wsady przez CSV; (2) przegląd Prawnika (art. 23/24 KC, prawo prasowe, RODO), tekst notki i etykiet; (3) ocena zespołu: czy „Rzekome powiązanie” zostaje nazwą; (4) test na realnym profilu po wdrożeniu; (5) migracja `0174` do wdrożenia wraz z kopią bazy.
- **Pytanie „czy 800 spółek to za mało” (odczyt `przeszlosc_krs_pokrycie` 6.11 15:27):** w bazie jest już **1534 podmiotów** (licznik 800 na zrzucie był sprzed zasilenia z kolejki), z tego 1172 NGO; 775 osób wszystkie sprawdzone w KRS, 507 osób ma co najmniej jeden potwierdzony podmiot (1043 relacje), 268 osób bez żadnego. Kolejka ma 16 507 oczekujących NIP/KRS (głównie TED wykonawcy 9542 i NIW 4406) i rośnie; błędy `api-krs nie odpowiada` to chwilowe ponowienia. Odkrywanie nowych podmiotów osoby–spółki nie idzie po nazwie (urzędowy KRS API nie ma wyszukiwania po nazwie), tylko z kandydatur i dowodów publicznych, stąd realny sufit.

- **Zbieranie doniesień dla wszystkich osób (6.11.2026, decyzja właściciela „wszystkich”):** bez sieci i bez kosztów zewnętrznych, z naszego korpusu artykułów: `news/doniesienia_zbieranie.py` + `manage.py przeszlosc_doniesienia_zbierz [--apply] [--na-osobe 5] [--razem 2000] [--ze-znanymi] [--osoba ID]`. Zasady: osoba z pełnym imieniem i nazwiskiem w tytule lub opisie (te same reguły co wzmianki; imiennicy i krótkie nazwy pomijani) + **pełna nazwa podmiotu z KRS w tym samym artykule**; nazwy zbyt ogólne (po zdjęciu formy prawnej jedno krótkie lub typowe słowo, poniżej 8 znaków) pominięte; kolizje nazw dwóch podmiotów pominięte; podmioty z potwierdzoną relacją KRS osoby domyślnie pomijane. Wszystko trafia jako `pending_review`, `name_only` („niepotwierdzone”), `collected_by=agent`, kategoria jako wskazówka po słowach kluczowych (denied/alleged/mention). Bez `--apply` tylko raport. Testy `news/test_doniesienia_zbieranie.py` 4/4. **Niesprawdzone:** ilu kandydatów wyjdzie na produkcji i jaki procent to trafienia (precyzja do oceny na próbce przez zespół), czas przebiegu na pełnym korpusie, zbieranie spoza korpusu (media bez RSS, wyszukiwarki) wymaga narzędzia wyszukiwania i zgody na koszty.


## Wdrożenie 6.11.2026 (wieczór): okno doniesień, poprawki układu, przycięcie B2

- **Zrobione i sprawdzone (wynik wklejony przez właściciela):** `deploy/wdroz.sh` na serwerze z lokalnym scaleniem (HEAD serwera `7d5507fa` = nasza gałąź do `25e64d1` + scalenie hotfixu Mercury z gałęzi `claude/napraw-mercury-przekaz-883a1d`): budowa 218 s, `backend odpowiada`, `wszystkie migracje zastosowane` (w tym `0174` modelu doniesień), Odstępstwa przeliczone, usługi `Up`. Wdrożone razem: okno „Podmioty z doniesień medialnych”, komendy `przeszlosc_doniesienia_import` i `przeszlosc_doniesienia_zbierz`, poprawki układu (logo/BETA, boks i przypis podmiotu po NIP).
- **Przyczyna blokady wdrożenia i naprawa:** koszyk B2 `spinclinic-kopie-0610` miał 10,2 GB przy dziennym limicie pamięci 10 GB i wydatkach 0 USD (do tego „Keep all versions”: skasowane kopie zostawały jako ukryte wersje); zapisy dawały 403. Właściciel kazał zostawić po 2 najnowsze kopie na katalog: `deploy/b2_przytnij.sh [--apply] [N]` skasował 59 wersji (pg 10,65 GB), ponowny raport pokazał 0 do skasowania, zostają pg 2, glosy 2, media 1. **Niesprawdzone:** czy nocna kopia o 3:30 zapisze się do B2 (pierwszy zapis w `wdroz.sh` tej nocy się udał, jeśli skrypt przeszedł krok 2/7). **Do decyzji właściciela:** retencja 18 dni znów napełni koszyk ok. 7,6 GB baz plus media; skrócić `RETENTION_DAYS` (np. do 7) albo podnieść limit wydatków w Backblaze (Caps & Alerts) i ustawić Lifecycle „Keep only the last version”.
- **Rozbieżność repozytorium:** serwer nadal ma lokalne commity scalające, których nie ma na GitHubie. Kolejne aktualizacje na serwerze: `git fetch origin claude/upbeat-noether-7k08ac && git merge --no-edit origin/claude/upbeat-noether-7k08ac` (nie `pull --ff-only`). Docelowo scalić gałąź Mercury ze spin.clinic osobnym PR-em i wyrównać serwer.
- **Czeka:** pierwszy raport zbierania doniesień (`przeszlosc_doniesienia_zbierz`, bez zapisu) i ocena precyzji na próbce; zapis do kolejki dopiero po akceptacji liczb; przegląd Prawnika; pomiar okna na prawdziwym profilu.

- **Ocena pierwszego zbierania (6.11 wieczór, próbka 30 z 150 pozycji z produkcji):** filtr „osoba i pełna nazwa podmiotu w tym samym artykule” był **za luźny** (precyzja szacunkowo 10–15%): większość to dwa nazwiska w jednym opisie (lista gości debaty, komunikat o grupie spółek, opis konferencji, protest), a kategoria „rzekome powiązanie” przypadkowo od słów typu „założyliśmy”, „połączyć siły”. Publikacja tego wprost sugerowałaby nieistniejące powiązania (ryzyko prawne). **Poprawione w kodzie (niewdrożone):** `news/doniesienia_zbieranie.py` wymaga bliskości osoby i podmiotu (do 100 znaków), pomija teksty z więcej niż 3 różnymi podmiotami z bazy (listy), kategorię „rzekome powiązanie” daje tylko przy mocnych słowach w oknie ±120 znaków wokół podmiotu („powiązany z”, „fundator”, „założyciel”, „prezes fundacji”), cytat obejmuje oba nazwy; `przeszlosc_doniesienia_zbierz --wyczysc-kolejke` kasuje wyłącznie niepublikowane pozycje zebrane automatycznie. Testy `test_doniesienia_zbieranie.py` 7/7. **Stan na produkcji do oczyszczenia:** 150 pozycji `pending_review` zebranych luźnym filtrem (żadna nie jest publiczna): po wdrożeniu poprawki uruchomić `--wyczysc-kolejke`, potem raport i próbkę.

- **Druga ocena zbierania (6.11 wieczór, 58 pozycji po zaostrzeniu bliskości):** precyzja nadal ok. 15% (ok. 8–10 realnych: Horała/ruch „Tak dla Rozwoju”, Wawrykiewicz/KOD, Nowacka/Zjednoczona Lewica). Trzy źródła szumu: (1) podmiot o jednowyrazowej, zwykłej nazwie („Skrzydła”: 13 pozycji, „skrzydła budynku”), (2) partie jako „osoby” (rekordy `role_category='party'`) i jako „podmioty” (Inicjatywa Polska, KOD, Zjednoczona Lewica), (3) układ listy gości, gdzie podmiot po nazwisku należy do następnej osoby. **Poprawione w kodzie (niewdrożone):** nazwa dopasowywanej frazy ≥ 2 słowa, słowa polityczne w nazwie podmiotu wykluczają go (komitet, koalicja, lewica, partia, stronnictwo, związki samorządów, platforma, konfederacja), osoby `party` pominięte, teksty z wypunktowaniami/myślnikami (`LIST_MARKS`) pomijane. Testy 9/9. 58 pozycji `pending_review` na produkcji do oczyszczenia (`--wyczysc-kolejke`) po wdrożeniu. **Wniosek:** zbieranie z samego korpusu (współwystępowanie nazw) to najwyżej pomoc redaktora, nie źródło „powiązań”; właściwy cel (fundacje powiązane z politykami wg doniesień śledczych) wymaga agenta czytającego artykuły ze zrozumieniem (wyszukiwanie + przegląd), do zrobienia po przywróceniu narzędzia wyszukiwania i za zgodą na koszty.

- **Trzecia ocena zbierania (6.11 późny wieczór, po zaostrzeniu: 7 pozycji dla 5 osób z 775):** 0 użytecznych (zbieg nazw w opisie debaty, numerowana lista panelistów, zdanie o „zbyt blisko powiązanym z premierem” kandydacie na RPO, nazwa cyklu spotkań). **Decyzja: zbieranie z samego korpusu artykułów nie jest źródłem „powiązań” i nie publikujemy z niego niczego.** Kod zostaje jako narzędzie pomocnicze (może posłużyć do podpowiedzi dla redaktora), kolejka produkcyjna do wyczyszczenia (`--wyczysc-kolejke`). Właściwa droga: agent z wyszukiwarką, który czyta artykuły o fundacjach i spółkach powiązanych z osobami, zapisuje link, redakcję, datę i cytat do CSV, a CSV trafia do `przeszlosc_doniesienia_import` (kolejka przeglądu) i do oceny Prawnika; wymaga przywrócenia narzędzia wyszukiwania i zgody właściciela na koszty zapytań. Okno w profilu osoby (model, kolejka, API, widok) jest wdrożone i czeka na pierwsze rzetelne pozycje.

- **Badacz doniesień przez Claude API (6.11 wieczór, decyzja właściciela: „mamy na koncie Anthropic 30 USD, jeśli nie da się za darmo, użyj”; Firecrawl bez kredytów do 7.11 15:54 UTC):** `news/doniesienia_badacz.py` + `manage.py przeszlosc_doniesienia_badaj [--szacuj] [--apply] [--osoba ID] [--limit-usd N]`. Używa `clinic_ai._call_claude(web_search=True)` (ten sam klient, klucz `ANTHROPIC_API_KEY`, model `CLINIC_MODEL` domyślnie `claude-sonnet-5`, wyszukiwarka `web_search_20260209`, obsługa `pause_turn`, schemat JSON). Kod nie ufa modelowi: link musi być z wyników wyszukiwania, podmiot musi być w naszej bazie (numer KRS z odpowiedzi albo pełna jednoznaczna nazwa → „niepotwierdzone”), wszystko `pending_review`, `collected_by='claude'`, twardy limit kosztu przebiegu (`--limit-usd`, domyślnie 5; wycena zawyżona z `clinic_ai.cost_usd`), `--szacuj` nie wysyła nic płatnego, bez `--apply` tylko raport. Domyślna lista ok. 40 znanych osób (`DEFAULT_NAMES`; nieznalezione w rejestrze raportowane). Testy `test_doniesienia_badacz.py` 4/4. **Niesprawdzone:** jakość wyników i realny koszt na produkcji (pierwszy test na jednej osobie), pokrycie podmiotów w bazie (część wskazanych przez media fundacji nie ma w `RegisteredOrganisation`: raportowane jako „poza bazą”; dodanie ich do bazy wymaga KRS), cytaty niezweryfikowane maszynowo (redaktor sprawdza w linku), przegląd Prawnika przed pierwszą publikacją.

- **Błąd 400 przy pierwszej próbie badacza (6.11 wieczór):** Anthropic odrzuca w `output_config.format.schema` pole `maxItems` („For 'array' type, property 'maxItems' is not supported”); test diagnostyczny na serwerze potwierdził, że prosty request, adaptive thinking, `web_search_20260209` i `fallbacks='default'` na `claude-sonnet-5` działają. Usunięto `maxItems` ze schematu (limit 6 pozycji w kodzie), dodany test pilnujący, że schemat nie zawiera nieobsługiwanych słów (`maxItems`, `minItems`, `maxLength`, `minLength`, `minimum`, `maximum`).

- **Zawieszenie badacza (6.11 wieczór):** po poprawce schematu pierwsze zapytanie trwało powyżej limitu 5 minut klienta (`timeout=300`, komunikat „Retrying request”), bo ustawienia Kliniki to `CLINIC_EFFORT=high` i 6 wyszukiwań. `doniesienia_badacz._light_settings()` na czas wywołania ustawia `CLINIC_EFFORT=low` (nadpisanie: `DONIESIENIA_EFFORT`) i `CLINIC_WEB_SEARCH_MAX_USES=4` (`DONIESIENIA_MAX_SEARCHES`), potem przywraca; `clinic_ai.py` bez zmian. Komenda wypisuje „Badam: <osoba>” przed każdym zapytaniem. Test 7/7. **Niesprawdzone:** realny czas i koszt jednego zapytania przy niskim wysiłku.

- **Pierwsza udana próba badacza (6.11 późny wieczór, Romanowski id 239, bez zapisu):** zapytanie trwało ok. 2 min (niski wysiłek, 4 wyszukiwania), 6 pozycji, 0 odrzuconych linków, koszt ok. 0,50 USD (wycena zawyżona; realnie niższa przy cenniku Sonnet 5: 2/10 USD za 1M), ale **wszystkie 6 poza bazą** (Fundacja Profeto ×3, Fundusz Sprawiedliwości ×1 i inne). Powód: do `RegisteredOrganisation` trafiają tylko podmioty znalezione po twardych identyfikatorach (funkcje osób w KRS, NIP/KRS z zamówień i dotacji); powiązanie medialne przez dotacje nie daje wpisu osoby w KRS, a KRS nie ma wyszukiwania po nazwie. **Rozwiązanie w kodzie (niewdrożone):** `adopt_from_krs`: gdy podmiotu nie ma w bazie, a model podał numer KRS, kod sprawdza go w urzędowym API KRS (`krs.fetch_status`, jedno zapytanie na sekundę) i porównuje nazwę z odpisem (`krs.names_match`); tylko przy zgodności dodaje podmiot z danych odpisu (`krs_pokrycie.save_extract`) i podpina doniesienie do kolejki przeglądu; bez `--apply` tylko raport (`org_added`). Fundusze państwowe bez KRS (np. Fundusz Sprawiedliwości) zostają „poza bazą”. Testy `test_doniesienia_badacz.py` 10/10.

- **Doprecyzowanie właściciela (6.11 późny wieczór):** powiązanie medialne nie musi oznaczać funkcji w podmiocie (np. polityk nie jest w fundacji, ale media piszą o jego udziale w przyznawaniu jej środków); okno ma to pokazywać **ze źródłem**, a przy podmiocie **link do urzędowego rejestru** (KRS; w przyszłości CEIDG dla jednoosobowych działalności bez KRS). Zrobione w kodzie (niewdrożone): pole `organisation.register_url` w `org_mentions`, link „KRS <numer> ↗” w oknie, wiersz 120 px. **Poza zakresem na teraz:** podmioty bez KRS (jednoosobowa działalność z CEIDG, fundusze państwowe) wymagają osobnego modelu (identyfikator NIP/REGON zamiast FK do `RegisteredOrganisation`); do decyzji po pierwszej partii.

- **Potwierdzenie zakresu przez właściciela (6.11 późny wieczór):** przy każdej osobie publicznej pokazujemy doniesienia medialne o fundacjach i spółkach, z którymi media ją wiążą także wtedy, gdy osoba nie ma funkcji w podmiocie (np. udział w przyznawaniu środków fundacji; wspomniany z pamięci przypadek Dariusza Mateckiego i dwóch fundacji: **niezweryfikowane, badacz ma sprawdzić doniesienia i zwrócić źródła, nie przesądzamy**), zawsze ze źródłem i linkiem do rejestru. Dodano: model `MediaResearchLog` (migracja `0175`; kogo zbadano, ile pozycji, koszt, model), pomijanie osób zbadanych w ostatnich 60 dniach (`--ponow` je włącza), `--nazwisko "Imię Nazwisko"`, Dariusz Matecki w liście domyślnej, `DONIESIENIA_MODEL` (tańszy model dla dalszych partii). Testy `test_doniesienia_badacz.py` 12/12.
- **Budżet (uczciwie):** wycena kodu to zawyżone ok. 0,50 USD za osobę; realnie prawdopodobnie 0,2–0,3 USD (do potwierdzenia na pierwszej partii). Przy 30 USD na koncie Anthropic starcza na ok. 60–120 osób, nie na 775. Plan: najpierw lista 39 znanych osób, potem kolejne partie wg ważności (ministrowie, liderzy klubów, osoby z doniesieniami o fundacjach) albo tańszy model (`DONIESIENIA_MODEL=claude-haiku-5-5`, koszt wyszukiwań ok. 0,04 USD za osobę zostaje).

- **Decyzje właściciela (6.11 późny wieczór): zasada produktu „perfekcyjne narzędzie OSINT”:** pokazujemy dane ze źródłem, **nie redagujemy, nie oceniamy i nie piszemy wniosków**; jedno miejsce, gdzie użytkownik sam łączy fakty. Okno doniesień medialnych jest najważniejsze, więc stoi wysoko w profilu (przed „W mediach”). Badamy **wszystkich** (nie tylko listę 39). Dodano kategorię **„Lobbing”** (firma wiązana przez media z osobą i podmioty-klienci, dla których media piszą, że firma lobbuje; jedna pozycja na podmiot ze swoim źródłem) i polecenie badacza o tym; przypadek Wiplera/Five Rand to relacja właściciela, **niezweryfikowana**, badacz ma znaleźć źródła albo nic. Nowe: `--wszyscy` (niezbadani, kolejność: rząd, partie, parlament krajowy, europejski, politycznie wpływowi, samorząd) i `--max-osob N`; migracja `0176` (zmiana listy kategorii). Testy 30/30 (backend), 177/177 (frontend).
- **Ryzyko prawne do przeglądu Prawnika przed pierwszą publikacją:** etykiety „Rzekome powiązanie” i „Lobbing” przy nazwiskach osób; zasada „tylko źródło i krótki cytat” ogranicza odpowiedzialność, ale nie zastępuje opinii prawnej (dobra osobiste, prawo prasowe, RODO). Każda pozycja zostaje w kolejce do ręcznej akceptacji.

- **Misja projektu (właściciel, 6.11.2026):** przeszłość.today ma być najlepszym miejscem do OSINT w Polsce; stale dodajemy publiczne źródła, płatne kupuje właściciel (każdy zakup po jego zgodzie i z limitem), pokazujemy tylko sprawdzone dane ze źródłem, bez wniosków. Kolejka następnych źródeł z priorytetami i potrzebami od właściciela: `docs/PRZESZLOSC_ZRODLA_DANYCH.md`, sekcja „Misja i zasady rozbudowy źródeł”. Następne w kolejce po doniesieniach medialnych: rejestr lobbingu MSWiA/Sejm, CEIDG (token), REGON/BIR (klucz GUS), sprawozdania finansowe z RDF, Rejestr Korzyści, SUDOP, listy beneficjentów funduszy celowych.

- **Przegląd źródeł płatnych (6.11.2026, wstępny):** `docs/PRZESZLOSC_ZRODLA_PLATNE.md`. Niepełny (brak cenników), nic nie kupiono. **Ważne do oceny Prawnika:** nowelizacja ustawy o KRS (art. 4c-4m, art. 60a: nieuprawniony dostęp do API KRS jako przestępstwo) a nasze użycie otwartego API KRS (`api-krs.ms.gov.pl`, limity, tylko dane podmiotów). Do powtórzenia po przywróceniu dostępu do sieci/Firecrawl (7.11 15:54 UTC): cenniki i regulaminy rejestr.io, Transparent Data, OpenSanctions.

- **Rozwiązywanie numeru KRS po dwóch danych (pomysł właściciela, 6.11 wieczór; niewdrożone):** podmiot wskazany przez media bez numeru KRS: (1) badacz zwraca też `city` (miejscowość siedziby) i `board_member` (osoba z zarządu/członek) ze źródła; (2) gdy brak numeru, `find_krs_candidate` robi drugą, tanią rundę z wyszukiwarką (nazwa + druga dana; bez drugiej danej nie szuka); (3) `verify_candidate` w **urzędowym API KRS** wymaga zgodności nazwy (`krs.names_match`) **oraz** drugiej danej (miejscowość siedziby równa albo osoba z zarządu w odpisie przez `krs.matching_persons`); brak drugiej danej lub niezgodność = odrzucenie z powodem w raporcie; dopiero potem `save_extract` dodaje podmiot (dane z odpisu) i powstaje pozycja `pending_review`. Ulicy nie porównujemy (nie mamy jej w modelu odpisu). Testy `test_doniesienia_badacz.py` 18/18. Koszt drugiej rundy wliczony w limit przebiegu.

- **Lekcja (6.11 wieczór): serwer uruchamia Python 3.11, środowisko testowe 3.13.** Napis `f'...{x['klucz']}...'` (te same cudzysłowy w środku) jest poprawny w 3.12+, a w 3.11 to `SyntaxError`; komenda `przeszlosc_doniesienia_badaj` nie ładowała się na produkcji mimo zielonych testów. Naprawione (wartość przed napisem). **Zasada przed każdym pushem backendu:** `python3.11 -m py_compile <zmienione pliki .py>` (jest `/usr/bin/python3.11`); wszystkie pliki zmienione od `eba10bd` skompilowano na 3.11 bez błędów.

- **Lejek doniesień (6.11 późny wieczór, po decyzji właściciela: agent z wyszukiwarką kosztował ok. 0,35 USD za osobę, 2 osoby bez wyniku):** `news/doniesienia_lejek.py` + `manage.py przeszlosc_doniesienia_lejek [--apply] [--nazwisko "…"] [--wszyscy --max-osob N] [--limit-usd N] [--szukaj-krs] [--bez-gdelt] [--ponow]`. Etapy: (1) kandydaci z korpusu artykułów + GDELT (otwarte, ok. 3 miesięcy wstecz, słabe pokrycie PL, 1 zapytanie/5,5 s); (2) pobranie artykułu zgodnie z zasadami prawnymi projektu: `media_metadata._known` (rejestr odmów wydawców), `media_metadata.tdm_allows` (robots.txt i sygnał TDM), UA `ContextBeforeContent`, tylko HTML do 1,5 MB, **bez zapisu pełnych tekstów** (do bazy najwyżej cytat do 300 znaków); fragmenty ±350 znaków wokół pełnego imienia i nazwiska z wyzwalaczami (fundacja, spółka, lobbing, dotacja...); (3) `claude-haiku-5-5` bez wyszukiwarki (`DONIESIENIA_LEJEK_MODEL`, ok. 0,001 USD na osobę) wyciąga podmioty z cytatem; (4) kod weryfikuje, że cytat dosłownie jest we fragmentach artykułu i że nazwa podmiotu (odporna na odmianę) też; (5) wspólne `doniesienia_badacz.store_items`: podmiot z bazy lub weryfikacja w KRS (nazwa + druga dana), zapis tylko do kolejki, `collected_by='lejek'`; druga runda z wyszukiwarką tylko z `--szukaj-krs`. Zbadane osoby w `MediaResearchLog` (pomijane 60 dni). Testy `test_doniesienia_lejek.py` + badacz + doniesienia: 42/42. **Niesprawdzone (sieć z sesji zablokowana):** realne odpowiedzi GDELT i pokrycie polskich mediów, ile artykułów odmawia robots.txt, jakość Haiku na fragmentach, czy `output_config` z formatem JSON przechodzi dla Haiku 5.5 (jest tryb zapasowy), koszt na osobę (oczekiwane grosze). Pierwsza próba na serwerze: 3 osoby, wynik do oceny przed pełną partią. Opcja Bing/Google News RSS pominięta do oceny Prawnika (regulaminy).
