# Minimalny model operacyjny: recovery źródeł i karty kontaktowe

Ten dokument jest specyfikacją kolejnej małej migracji backendu. Nie zmienia
obecnych modeli ani nie uruchamia pobierania. Jest zgodny z istniejącym
`SourceAccessInstruction`: to właśnie zatwierdzona instrukcja pozostaje
jedyną bramą dla automatycznego harvestera.

## Zasada

`Source` opisuje podmiot w katalogu. `SourceAccessInstruction` opisuje
jedną, wersjonowaną i zatwierdzoną metodę automatycznego dostępu.
`SourceRecoveryCase` dokumentuje awarię i jej rozpoznanie.
`SourceContactCard` dokumentuje brak zgody albo kanału oraz przygotowuje
przyszły kontakt. Żaden z dwóch nowych modeli nie może sam włączyć źródła,
ustawić `scrape_enabled` ani tworzyć `ArchiveJob`.

## Pilot nowego źródła

Przed pierwszym zatwierdzeniem każdej instrukcji dostępu działa ograniczony
pilot. Sprawdza wyłącznie jeden udokumentowany kanał i najwyżej trzy URL-e,
z odstępem co najmniej trzech sekund na host. Zapisuje wynik, użyty kanał,
zakres i liczbę poprawnie utworzonych boxów; nie uruchamia masowego pobierania.
Udany pilot jest dowodem technicznym, lecz nie zastępuje decyzji redakcyjnej o
zatwierdzeniu podstawy dostępu. Taka sama bramka obowiązuje po naprawie źródła.

## SourceRecoveryCase

### Pola

| Pole | Typ / reguła | Cel |
| --- | --- | --- |
| `id`, `source` | PK, FK do `Source` | Jedna sprawa dotyczy jednej domeny. |
| `status` | enum, domyślnie `detected` | Stan pracy diagnostycznej. |
| `trigger` | enum | `no_new_boxes`, `terminal_error`, `retry_threshold`, `quality_drift`, `manual`. |
| `failure_fingerprint` | krótki hash/tekst | Znormalizowana sygnatura błędu, bez sekretów, cookies i pełnych odpowiedzi. |
| `sample_error` | tekst ograniczony | Krótkie wyjaśnienie techniczne dla redakcji. |
| `failed_instruction` | nullable FK do `SourceAccessInstruction` | Dokładna wersja kanału, która zawiodła. |
| `opened_at`, `last_observed_at`, `closed_at` | daty | Odtwarzalna historia sprawy. |
| `last_success_at` | nullable data | Ostatni udany box sprzed awarii. |
| `boxes_before`, `boxes_after` | liczby nieujemne | Mierzalny efekt naprawy; nie licznik samych prób. |
| `attempt_count` | liczba, max 2 na hipotezę | Broni przed pętlą retry. |
| `audit_evidence` | JSON | URL-e warunków, robots, dokumentacji kanału, daty kontroli oraz krótkie fakty. |
| `proposed_instruction` | nullable FK do `SourceAccessInstruction` | Nowy szkic instrukcji, nigdy samoczynnie zatwierdzony. |
| `dry_run_result` | enum/JSON | Liczba URL-i, wynik, przyrost boxów, powód niepowodzenia; bez korpusu. |
| `decision_reason` | tekst | Uzasadnienie końcowej decyzji. |
| `decided_by`, `decided_at` | nullable | Odpowiedzialność człowieka/agenta redakcyjnego. |
| `contact_card` | nullable one-to-one | Łączy sprawę z kartą kontaktową, jeśli nie ma podstawy. |

### Statusy i przejścia

```
detected → triage → auditing → dry_run → repaired → closed
                    ↘ manual_review
                     ↘ contact_required → closed
triage → cooldown → triage
manual_review → auditing | contact_required | retired → closed
```

- `detected`: automatycznie utworzone po progu błędów; źródło jest wyłączone
  wyłącznie z aktywnej puli.
- `triage`: rozdziela awarię przejściową od błędu konfiguracji lub dostępu.
- `cooldown`: tylko 429/5xx/timeout; maksymalnie dwa kontrolne wznowienia.
- `auditing`: sprawdzenie warunków i kanałów bez masowego pobierania.
- `dry_run`: maksymalnie kanał + trzy URL-e materiałów, jeden request na
  domenę, interwał z instrukcji i nigdy krótszy niż 3 sekundy.
- `repaired`: istnieje nowa instrukcja `approved` i dodatni, mały test.
- `manual_review`: decyzja niejednoznaczna.
- `contact_required`: brak wystarczającej podstawy lub kanału.
- `retired`: trwałe wyłączenie z uzasadnieniem redakcyjnym.
- `closed`: historia jest zachowana; kolejna awaria tworzy nową sprawę.

## SourceContactCard

Karta nie jest wysyłką maila. Powstaje tylko z `contact_required` albo z
ręcznej decyzji redakcji.

| Pole | Typ / reguła | Cel |
| --- | --- | --- |
| `id`, `source`, `recovery_case` | PK, FK, nullable one-to-one | Kontekst podmiotu i powodu kontaktu. |
| `status` | `draft`, `ready_for_review`, `approved_to_send`, `sent`, `answered`, `declined`, `agreement_recorded`, `closed` | Rozdziela przygotowanie od faktycznej korespondencji. |
| `publisher_name`, `contact_url` | tekst/URL | Podmiot i publiczny kanał kontaktu. |
| `requested_scope` | lista | Tylko `metadata`, `content`, `snapshot`; domyślnie `metadata`. |
| `requested_channels` | lista | Np. RSS, API, eksport CSV/JSON/XML, OAI-PMH. |
| `technical_findings` | JSON | Znalezione kanały, ograniczenia i dowody. |
| `reason_for_contact` | tekst | Co blokuje automatyzację. |
| `message_draft` | tekst | Szkic do późniejszej redakcji; nie jest wysyłany przez system. |
| `approval_by`, `approval_at` | nullable | Wyraźna zgoda na wysyłkę. |
| `sent_at`, `delivery_reference` | nullable | Uzupełniane wyłącznie po ręcznej wysyłce. |
| `reply_summary`, `reply_evidence_url` | nullable | Ślad odpowiedzi i jej dowód. |
| `granted_instruction` | nullable FK | Zatwierdzona instrukcja po pozytywnej odpowiedzi. |
| `next_review_at` | nullable data | Termin ponownej kontroli bez nękania podmiotu. |

## Warunki fail-closed

1. `SourceAccessInstruction.status='approved'` nadal wymaga `terms_url`,
   `reviewed_at`, `reviewed_by`, `evidence` oraz minimum 3 sekund.
2. `SourceRecoveryCase.status='repaired'` wymaga wskazanej zatwierdzonej
   instrukcji, udanego dry-run i `boxes_after > boxes_before`.
3. Utworzenie albo edycja recovery/contact card nie może modyfikować
   `Source.is_active`, `Source.scrape_enabled` ani tworzyć kolejki.
4. `contact_required` nie daje zgody na HTML, treść, snapshot, OCR ani
   ponowne próby masowe.
5. `SourceContactCard.approved_to_send` wymaga człowieka w
   `approval_by` i `approval_at`; żadna automatyczna funkcja nie wysyła
   wiadomości.
6. Odpowiedź wydawcy nie zmienia źródła automatycznie: najpierw powstaje nowa
   instrukcja dostępu i przechodzi zwykłe zatwierdzenie oraz dry-run.

## Minimalne testy

1. **Brak zatwierdzonej instrukcji:** sprawa i karta kontaktowa nie mogą
   przywrócić źródła ani zaplanować zadania.
2. **Próg błędów:** po 3 kolejnych błędach bez nowego boxa tworzy się jedna
   otwarta sprawa; kolejne błędy dopisują obserwację, nie mnożą spraw.
3. **Retry:** po dwóch kontrolnych wznowieniach `cooldown` nie może uruchomić
   trzeciej próby bez `manual_review`.
4. **Dry-run bez efektu:** wynik 0 nowych poprawnych boxów nie pozwala na
   status `repaired`.
5. **Niepełne dowody:** instrukcja bez warunków, daty, osoby lub evidence nie
   może zostać `approved`.
6. **Kontakt:** status `approved_to_send` bez osoby i daty zatwierdzenia
   jest odrzucony; model nie wykonuje żadnej wysyłki.
7. **Historia:** zatwierdzenie nowej instrukcji nie usuwa ani nie nadpisuje
   `failed_instruction` w starej sprawie.
8. **Zakres:** karta z zakresem `metadata` nie może uzyskać instrukcji
   `content` lub `snapshot` bez nowej, jawnej decyzji i dowodu.

## Minimalny widok redakcyjny

Lista recovery pokazuje: źródło, status, sygnaturę błędu, ostatni udany box,
liczbę nowych boxów po teście, obowiązującą instrukcję i kolejny krok.
Lista kontaktowa pokazuje: podmiot, zakres prośby, status przygotowania,
dowody i termin kolejnego przeglądu. Pełne HTML, prywatne snapshoty, dane
logowania i treść odpowiedzi nie są widoczne publicznie.

## Kolejność wdrożenia

1. Migracje i modele bez podpinania do harvestera.
2. Testy fail-closed oraz panel tylko do odczytu/statusów.
3. Jeden ręcznie utworzony case na źródle kontrolnym.
4. Dopiero potem automatyczne tworzenie spraw po progu błędów.
5. Osobna decyzja przed automatycznym przywracaniem źródeł do puli.
