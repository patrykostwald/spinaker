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
