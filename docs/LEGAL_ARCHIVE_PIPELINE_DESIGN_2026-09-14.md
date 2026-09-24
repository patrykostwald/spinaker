# Niezależny projekt architektury: legalne, ciągłe pobieranie historii (2026-09-14)

Dokument projektowy. Nie uruchamia harvestera, nie wykonuje requestów
sieciowych, nie zmienia frontendu, Supabase ani sekretów. Cel: rzetelna baza
kontekstu, a nie maksymalna liczba żądań. Ocenia i rozszerza istniejące
`docs/SOURCE_AUDITOR_CHECKLIST.md` i `docs/SOURCE_RECOVERY_WORKFLOW.md` o
jeden spójny widok cyklu życia źródła, role agentów i konkretne zabezpieczenia
przed pętlami/duplikatami. Nie zastępuje tych dwóch dokumentów.

## 0. Co już istnieje (stan faktyczny w repo)

Zanim zaprojektowano cokolwiek nowego, sprawdzono kod — większość wymaganego
przepływu jest już zaimplementowana, nie tylko opisana:

- **Instrukcja dostępu** `SourceAccessInstruction` (`backend/news/models.py:116`) —
  wersjonowana, `fail-closed`: `approved` wymaga `terms_url`, `reviewed_at`,
  `reviewed_by`, `evidence`, min. 3 s odstępu.
- **Sprawa recovery** `SourceRecoveryCase` (`backend/news/models.py:178`) —
  stany `detected → triage → cooldown/auditing → dry_run → repaired/
  manual_review/contact_required/retired → closed`, limit 2 prób na hipotezę,
  `repaired` wymaga zatwierdzonej instrukcji i dodatniego dry-run.
- **Karta kontaktowa** `SourceContactCard` (`backend/news/models.py:234`) —
  tylko szkic; wysyłka wymaga `approval_by`/`approval_at` człowieka.
- **Kolejka** `ArchiveJob` (`backend/news/models.py:497`) z polami `priority`,
  `attempts`, `available_at` (backoff), unikalnym `url` (dedup na poziomie DB,
  `bulk_create(..., ignore_conflicts=True)` w `backend/scraper/archive.py:263`).
- **Per-domenowy circuit breaker i limiter** w `backend/scraper/archive.py:32-58,
  188-235`: `_HOST_STATES` (blokada `Lock()`, `next_allowed`, `circuit_until`),
  nieblokujące pobranie locka (`SourceDelay` zamiast czekania), `crawl_delay`
  z `robots.txt`, min. 3 s, otwarcie sprawy recovery po 3 błędach na hosta.
- **Priorytetyzacja i rozdział obciążenia** w `run_batch`/`run_parallel_batch`
  (`backend/scraper/archive.py:335-465`): co 4. slot dla żądań redakcyjnych/
  wyszukiwania (`priority>0`), rotacja źródeł, żeby mały nowo włączony
  publisher nie czekał za dużym, grupowanie wątków po `source_id` tak, by
  jedno źródło nie było przetwarzane równolegle przez dwa wątki.
- **Audytor i backlog** w praktyce: `docs/SOURCE_AUDITOR_CHECKLIST.md`
  (kolejność kanałów), `docs/SOURCE_RECOVERY_WORKFLOW.md` (pełny stanowy
  proces diagnosty), `docs/SOURCE_RECOVERY_BACKLOG_AUDIT_B_2026-09-14.md`
  (przykładowa kwalifikacja realnego backlogu bez sieci).
- Znana duplikacja mechanizmów pozyskiwania dla jednego typu źródła: WordPress
  ma dwie równoległe ścieżki — aktywny `wordpress_backfill.py`/
  `wordpress_cycle` oraz nowszy, katalogowany `wordpress_rest_adapter.py`
  (zmostkowany do `ArchiveJob` przez `wordpress_rest_bridge.py`). To wzorzec
  ryzyka, który poniższy projekt wprost adresuje (Ryzyko 1).

Wniosek: brakuje nie tyle mechanizmu, co **jednego zintegrowanego widoku
stanowego** łączącego audytora, pilota, harvestera i lekarza źródła w jeden
cykl życia, oraz **kilku konkretnych zabezpieczeń brzegowych** (patrz sekcja 6
i 7) — dokument poniżej się na tym skupia zamiast powtarzać już opisane kroki.

## 1. Maszyna stanów cyklu życia źródła i role agentów

```
[Audytor źródeł]                (docs/SOURCE_AUDITOR_CHECKLIST.md — bez zmian)
   candidate
     → audited (kanał, zakres, limity, dowód zapisane; brak podstawy → contact_required)
     → instruction_draft (SourceAccessInstruction.status=draft)

[Pilot]                          (nowa, mała, jawna rola — patrz 1a)
     → piloted (≤3 URL, ≥3 s/host, tylko metadane chyba że zakres pozwala więcej)
         sukces  → instruction_review
         porażka → audited (nowa hipoteza) albo contact_required

[Redakcja / właściciel]
     instruction_review
         zatwierdzenie → SourceAccessInstruction.status=approved
         odrzucenie    → audited

[Harvester]                      (docs istniejący kod: scraper/archive.py)
     approved → active (ArchiveJob w normalnym harmonogramie, per-host gate)
         błąd przejściowy → cooldown → active
         próg błędów (3 bez nowego boxa / 10 w 30 min) → SourceRecoveryCase.detected

[Lekarz źródła / diagnosta]      (docs/SOURCE_RECOVERY_WORKFLOW.md — bez zmian)
     detected → triage → auditing → dry_run
         repaired_instruction → instruction_review (powrót przez Pilota, nie od razu do harvestera)
         manual_review        → redakcja
         contact_required     → [Agent korespondencji]
         retired               → closed (uzasadnienie redakcyjne)

[Agent korespondencji]
     contact_required → SourceContactCard.draft → ready_for_review
         redakcja: approved_to_send (człowiek, approval_by+approval_at)
         → sent (ręcznie) → answered/declined
         answered z nowym zakresem → nowa SourceAccessInstruction.draft → instruction_review
```

### 1a. Dlaczego osobny „Pilot”, skoro audytor i recovery już mają dry-run

`SOURCE_AUDITOR_CHECKLIST.md` mówi „audytor nie wykonuje masowego
pobierania”, ale nie definiuje explicite małego pilota jako oddzielnego,
nazwanego kroku bramkującego *pierwsze* włączenie źródła — tylko
`SOURCE_RECOVERY_WORKFLOW.md` ma to sformalizowane dla *naprawy*. Zadanie 016
wymaga tego samego bramkowania dla nowego źródła. Proponowane doprecyzowanie:
**każde przejście `draft → approved` przechodzi przez ten sam ograniczony test,
niezależnie czy to pierwsza konfiguracja czy naprawa** — jedna implementacja
(`dry_run_result` już istnieje w modelu `SourceRecoveryCase`; dla nowych źródeł
wystarczy ten sam kształt zapisu bez tworzenia nowej tabeli).

### Role agentów

| Rola | Wejście | Wyjście | Automatyzacja |
|---|---|---|---|
| Audytor źródeł | katalog kandydatów | `audited` + `instruction_draft` | zbieranie dowodów automatyczne; decyzja „jest podstawa / nie ma” wymaga człowieka przy pierwszym źródle danego wydawcy |
| Pilot | `instruction_draft` | `piloted` z `dry_run_result` | w pełni automatyczny, ale twardo ograniczony (≤3 URL, 1 request/3s/host) |
| Redakcja/właściciel | `piloted`/`repaired_instruction`/`contact_required→sent` | `approved`/`odrzucone`/wysyłka | zawsze człowiek — to jedyna bramka z realnym skutkiem prawnym |
| Harvester | `approved` | boxy w `ArchiveJob`/`Article` | w pełni automatyczny w granicach instrukcji |
| Lekarz źródła | `detected` | jedna decyzja z zamkniętego zbioru | automatyczna diagnoza i dry-run; decyzja `repaired`/`retired`/`contact_required` wymaga potwierdzenia człowieka gdy dowód niejednoznaczny (już tak w modelu: `manual_review`) |
| Agent korespondencji | `contact_required` | szkic karty | automatyczny szkic; wysyłka zawsze ręczna |

## 2. Automatyczne vs. wymagające człowieka

**Automatyczne:** zbieranie dowodów kanału (API/eksport/RSS/sitemap/robots),
pilot ≤3 URL, harvester w granicach zatwierdzonej instrukcji, per-host circuit
breaker, tworzenie `SourceRecoveryCase` po progu błędów, dopisywanie
obserwacji do istniejącej sprawy (dedup po `failure_fingerprint`), szkic karty
kontaktowej.

**Wymaga człowieka:** zatwierdzenie `SourceAccessInstruction` (pierwsze i po
naprawie), decyzja `retired`, każda eskalacja zakresu `metadata→content→
snapshot`, `approved_to_send` i faktyczna wysyłka, każda zmiana domeny/hosta
źródła (już wymuszone w `Source.clean()`), reaktywacja źródła po `retired`.

## 3. Priorytety, równoległość, mierniki

**Priorytety (formalizacja istniejącego pola `priority`):**
- P0 — żądanie redakcyjne/wyszukiwanie na żywo (`priority=10`), gwarantowany
  co 4. slot niezależnie od wielkości backlogu.
- P1 — dry-run pilota/recovery (bounded, ≤3+1 URL, poza normalną kolejką wag).
- P2 — normalny backlog historyczny, rotacja per-źródło żeby uniknąć głodzenia
  małych publisherów przez dużych (już zaimplementowane).

**Limity równoległości:** jeden aktywny request na hosta (lock nieblokujący +
`SourceDelay`), `MAX_ARCHIVE_WORKERS` jako sufit konfiguracyjny (obecnie 64,
nie deklaracja mierzonej przepustowości), maks. 2 kontrolowane próby na
hipotezę recovery, maks. 3 URL + 1 kanał na dry-run.

**Mierniki skuteczności (nie „liczba requestów”):**
- przyrost `boxes_after - boxes_before` na naprawioną sprawę (już pole modelu);
- % znanej kolejki ukończone/oczekujące/kwarantanna (już w widoku monitoringu
  `SOURCE_RECOVERY_WORKFLOW.md` §„Widok monitoringu”);
- czas od `detected` do decyzji (SLA diagnosty, nowy miernik do dodania do
  panelu, bez zmiany modelu — pole `opened_at`/`decided_at` już istnieje);
- odsetek `SourceAccessInstruction.approved`, które nigdy nie trafiły do
  `SourceRecoveryCase` w 30 dni (jakość audytu, nie tylko naprawy);
- liczba otwartych `contact_required` starszych niż `next_review_at` (dług
  redakcyjny, nie techniczny).

## 4. Unikanie pętli, duplikatów i powtarzania błędów

Już zaimplementowane i wystarczające:
- unikalny `ArchiveJob.url` + `ignore_conflicts=True` → dedup URL-i;
- `_record_recovery_case` dopisuje do istniejącej otwartej sprawy po tym samym
  `failure_fingerprint` zamiast tworzyć kolejną (`backend/scraper/archive.py:61-80`);
- `TERMINAL_ERRORS` kończy retry natychmiast zamiast próbować w kółko;
- wykładniczy backoff z sufitem 86400 s dla błędów nieprzejściowych;
- `attempt_count`/`attempts` z twardym limitem (2 dla recovery, 5 dla joba).

Do dodania (dokumentacyjnie, bez kodu — patrz sekcja 7, Ryzyko 3 dla testu):
- audytor powinien przed konfiguracją nowego źródła sprawdzić, czy hostname
  nie pokrywa się z istniejącym aktywnym `Source` — dziś nic nie broni dwóch
  katalogowych wpisów na ten sam host z dwiema niezależnymi instrukcjami,
  co podwaja ruch na jedną domenę mimo że per-host breaker działa poprawnie
  w ramach jednego procesu;
- ten sam mechanizm musi objąć **duplikat metody pozyskiwania** dla jednego
  źródła (przypadek WordPress: backfill + REST adapter [[wordpress-rest-duplicate-mechanism]]) —
  audytor odnotowuje aktywną metodę w `evidence`, a włączenie drugiej metody
  dla tego samego `source_id` wymaga jawnej decyzji redakcyjnej, nie tylko
  technicznej migracji.

## 5. Trzy największe ryzyka i zabezpieczenia

1. **Dwa równoległe mechanizmy pozyskiwania tego samego źródła** (potwierdzony
   przypadek WordPress). Skutek: podwójny ruch do wydawcy, podwójne liczenie
   `boxes_after`, trudniejsza diagnoza która ścieżka odpowiada za błąd.
   *Zabezpieczenie:* audytor zapisuje w `evidence` jedną „aktywną metodę” per
   `source_id`; włączenie drugiej metody bez zamknięcia pierwszej blokuje się
   tak samo jak dziś blokuje się brak `SourceAccessInstruction` (fail-closed),
   plus panel recovery pokazuje obie metody obok siebie gdy współistnieją.

2. **Eskalacja zakresu bez nowego dowodu** (dry-run udany na `metadata`
   traktowany później jako milcząca zgoda na `content`/`snapshot`).
   *Zabezpieczenie:* już częściowo wymuszone w modelu (`SourceContactCard`
   test 8 w `SOURCE_RECOVERY_CASE_AND_CONTACT_CARD_MODEL.md`), do utrzymania:
   każda zmiana `allowed_scope` w górę wymaga nowej wersji instrukcji z osobnym
   `terms_url`/`evidence`, nie edycji istniejącej.

3. **Bramka per-host żyje tylko w pamięci jednego procesu** (`_HOST_STATES` w
   `backend/scraper/archive.py:32`). Dopóki harvester działa jako jeden
   proces/workery-wątki, gwarancja „1 aktywny request na domenę” trzyma się.
   W chwili skalowania do wielu procesów/instancji (np. drugi deployment,
   drugi cron) każdy proces dostaje własny, pusty `_HOST_STATES` i może
   jednocześnie odpytać tę samą domenę — złamanie kluczowego wymogu zadania
   („jeden request na domenę co najmniej 3 s”) bez żadnego widocznego błędu.
   *Zabezpieczenie:* przed jakimkolwiek skalowaniem poziomym przenieść stan
   bramki na wspólny magazyn (blokada w DB przez `select_for_update` na
   rekordzie źródła, albo blokada w cache z TTL) — **ale najpierw napisać test
   pokazujący brak** (patrz sekcja 8), zgodnie z zasadą „nie implementuj kodu
   bez testu pokazującego brak”.

## 6. Najmniejszy bezpieczny etap wdrożenia

Skoro większość infrastruktury już istnieje, najmniejszy krok to **nie**
nowy kod, tylko:

1. Dopisać do checklisty audytora (`SOURCE_AUDITOR_CHECKLIST.md`) jedno zdanie:
   sprawdzenie kolizji hosta i aktywnej metody pozyskiwania przed konfiguracją.
2. Dodać do `SOURCE_RECOVERY_CASE_AND_CONTACT_CARD_MODEL.md` sekcję 1a (Pilot)
   jako wymóg dla **nowych** źródeł, nie tylko dla naprawy — bez zmiany
   modelu, bo `dry_run_result` już istnieje.
3. Napisać (nie implementować naprawy) jeden test procesowy pokazujący, że
   `_HOST_STATES` nie jest dzielony między dwoma procesami — dopiero to jest
   podstawą do decyzji, czy i kiedy przenosić bramkę do wspólnego magazynu.
4. Dopiero po punktach 1–3: rozszerzać liczbę workerów/procesów.

## 7. Testy — stan wykonania

Środowisko wykonawcze tej sesji zablokowało uruchomienie interpretera
(`python3 -m pytest ...` i `py -3 -m pytest ...` zwróciły odmowę wymagającą
zatwierdzenia, którego nie było komu udzielić — sesja nieinteraktywna,
zadanie zabraniało też uruchamiania harvestera/requestów). **Testy nie zostały
faktycznie uruchomione w tej sesji** — poniższa lista to statyczne odczytanie
istniejącego pokrycia, nie świeży wynik:

- `backend/news/test_source_recovery_models.py` — stany i fail-closed dla
  `SourceRecoveryCase`/`SourceContactCard`.
- `backend/scraper/test_archive.py`, `test_quarantine_archive_errors.py` —
  circuit breaker, kwarantanna, tworzenie spraw recovery.
- `backend/scraper/test_queue.py` — kolejka żądań redakcyjnych.
- `backend/scraper/test_source_probe.py`, `test_wordpress_rest_bridge.py` —
  sondowanie kanałów i most WordPress REST → `ArchiveJob`.

Brakujący test (do napisania jako **następny krok**, przed jakąkolwiek zmianą
kodu bramki): symulacja dwóch niezależnych procesów Python importujących
`scraper.archive` i wywołujących `host_state()` dla tego samego hosta — dziś
nie istnieje test dowodzący, że gwarancja „jeden request na domenę” działa
tylko w obrębie jednego procesu. To jest test „pokazujący brak” wymagany
zadaniem; implementacja wspólnej blokady powinna nastąpić dopiero po nim.

## Podsumowanie zgodności z zadaniem 016

Wszystkie pięć wymaganych kroków przepływu mają już odpowiednik w kodzie lub
istniejących dokumentach; ten dokument dodaje: (a) jeden połączony widok
stanowy audytor→pilot→harvester→lekarz→kontakt, (b) formalny Pilot dla
*nowych* źródeł (dziś dry-run jest opisany tylko dla naprawy), (c) trzy
konkretne ryzyka z zabezpieczeniami, w tym jedno realne (bramka per-host w
pamięci procesu) poparte konkretnym brakującym testem zamiast kodu.
