# Odzyskiwanie źródeł z błędami

Ten proces oddziela awarię pojedynczego źródła od pracy zdrowej puli
harvesterów. Jego celem nie jest „próbowanie do skutku”, lecz znalezienie
jednej udokumentowanej, legalnej metody pobrania albo jasne zakończenie sprawy
decyzją redakcyjną lub kontaktem z wydawcą.

Nie wolno uruchamiać w nim masowego pobierania, obchodzić zabezpieczeń,
zmieniać nagłówków w celu ominięcia ograniczeń, używać proxy ani pobierać
korpusu, screenshotów lub PDF bez zakresu dostępu zatwierdzonego dla źródła.

## Przepływ pracy

1. **Wykrycie.** Harvester zapisuje jeden znormalizowany błąd wraz z identyfikatorem
   źródła, kanałem, URL-em i licznikiem prób. Po przekroczeniu progu źródło
   jest wyłączane tylko z aktywnej kolejki, a nie usuwane z katalogu.
2. **Triaging.** Diagnosta sprawdza ostatnie błędy, aktywną instrukcję harvestera,
   jej wersję i wskaźnik nowych boxów. Najpierw rozróżnia problem przejściowy
   (429/5xx/timeout), zmianę techniczną parsera, brak uprawnienia oraz błąd
   konfiguracji lokalnej.
3. **Audyt bez masowego pobierania.** Przegląda warunki, `robots.txt`,
   dokumentację i publicznie wskazane kanały: oficjalne API, RSS/Atom,
   otwarty eksport (JSON/XML/CSV/ZIP), OAI-PMH, sitemap oraz — jako ostatnią
   opcję — jawnie dozwolony HTML. Zapisuje linki do dowodów i datę kontroli.
4. **Jedna hipoteza, jeden dry-run.** Dla najbardziej restrykcyjnej legalnej
   metody przygotowuje instrukcję i testuje najwyżej jeden adres katalogowy
   oraz najwyżej trzy publicznie wskazane URL-e materiałów. Dry-run zapisuje
   wyłącznie metadane oraz wynik; nie zapisuje korpusu ani snapshotu, jeśli
   zakres źródła tego nie dopuszcza.
5. **Decyzja.** Wynik może być tylko jeden:
   - `repaired_instruction` — nowa wersjonowana instrukcja i ograniczony
     test zdrowia przed przywróceniem do puli;
   - `manual_review` — brakuje jednego potwierdzenia lub wynik testu jest
     niejednoznaczny;
   - `contact_required` — nie ma bezpiecznej podstawy albo wydawca musi
     wskazać kanał/zakres współpracy;
   - `retired` — źródło nie jest już aktualne lub jego materiały nie leżą w
     zakresie projektu. Ta decyzja wymaga redakcyjnego uzasadnienia.
6. **Powrót do harvestera.** Tylko `repaired_instruction` może przywrócić
   źródło. Najpierw przechodzi próbę maksymalnie 10 adresów, z jednym aktywnym
   żądaniem do domeny i z zapisanym przyrostem poprawnych boxów. Dopiero wtedy
   zostaje włączone do normalnego harmonogramu.

## Minimalny model danych

`SourceRecoveryCase` jest trwałą sprawą diagnostyczną powiązaną ze źródłem;
nie zastępuje katalogu źródeł ani historii pobrań.

| Pole | Znaczenie |
|---|---|
| `id`, `source_id`, `opened_at`, `closed_at` | identyfikacja i czas sprawy |
| `status` | stan z tabeli poniżej |
| `trigger` | np. `no_new_boxes`, `terminal_error`, `quality_drift`, `manual` |
| `active_method`, `active_instruction_version` | metoda, która zawiodła |
| `failure_fingerprint`, `sample_error` | znormalizowana sygnatura, bez sekretów i pełnych treści |
| `last_success_at`, `boxes_before`, `boxes_after` | mierzalny efekt naprawy |
| `access_basis`, `terms_evidence_url`, `robots_evidence_url`, `reviewed_at` | audyt podstawy i dowodów |
| `proposed_method`, `proposed_instruction_version` | propozycja diagnosty |
| `dry_run_urls`, `dry_run_result`, `dry_run_at` | mała, odtwarzalna próba |
| `decision`, `decision_reason`, `reviewer` | końcowa decyzja i odpowiedzialność |
| `contact_card_id` | odnośnik do karty przyszłej korespondencji, gdy jest potrzebna |

`SourceAccessInstruction` powinien być wersjonowany i niezmienny po użyciu.
Przechowuje: kanał (`api`, `rss`, `export`, `oai_pmh`, `sitemap`, `html`),
dozwolony zakres (`metadata`, `content`, `snapshot`), źródłowy adres kanału,
interwał domeny, limity partii, dowód warunków, datę kontroli, autora decyzji
i status `draft`/`approved`/`superseded`/`revoked`.

Każdy utworzony box zachowuje już w rejestrze pochodzenia identyfikator
instrukcji, kanał, URL, czas, wersję parsera i hash odpowiedzi. Nie wolno
nadpisywać tej historii po zmianie instrukcji.

## Statusy i przejścia

| Status | Znaczenie | Dozwolone następne stany |
|---|---|---|
| `detected` | harvester odłączył źródło od puli | `triage` |
| `triage` | klasyfikacja błędu | `auditing`, `cooldown`, `manual_review` |
| `cooldown` | wyłącznie dla przejściowego 429/5xx/timeout | `triage`, `manual_review` |
| `auditing` | kontrola kanałów i warunków | `dry_run`, `contact_required`, `manual_review` |
| `dry_run` | ograniczona próba jednej instrukcji | `repaired_instruction`, `manual_review`, `contact_required` |
| `repaired_instruction` | test zdrowia ukończony; można przywrócić źródło | `closed`, `detected` |
| `manual_review` | wymaga decyzji redakcji | `auditing`, `contact_required`, `retired` |
| `contact_required` | czeka na przyszłą zgodę/partnerstwo | `auditing`, `closed` |
| `retired` | źródło kończy obsługę | `closed` |
| `closed` | pełna historia zostaje zachowana | `detected` tylko dla nowej, osobnej awarii |

## Limity i bezpieczniki

- Harvester otwiera sprawę po **3 kolejnych błędach bez nowego boxa** albo po
  **10 błędach w 30 minutach** dla danego źródła. Źródło nie może wtedy dalej
  generować retry w głównej kolejce.
- Przejściowe błędy mają co najwyżej **2** kontrolne wznowienia z rosnącą
  przerwą. Następna awaria otwiera `manual_review`; nie ma nieskończonych retry.
- Diagnosta może wykonać maksymalnie **1 audyt konfiguracji na 24 godziny** i
  **1 dry-run na proponowaną wersję instrukcji**. Zmiana hipotezy tworzy nową
  wersję, a nie kolejną próbę tej samej instrukcji.
- Dry-run: maksymalnie **3 URL-e materiałów + 1 URL kanału**, jeden aktywny
  request na domenę, z interwałem co najmniej takim jak instrukcja źródła
  (nigdy krótszym niż 3 sekundy).
- Źródło wraca do puli dopiero przy dodatnim przyroście poprawnych boxów,
  braku błędów terminalnych i zgodności metadanych dla próby maksymalnie 10 URL-i.
- Brak jasnej podstawy dostępu zawsze kończy się `contact_required`; snapshot,
  OCR i pełny tekst pozostają wyłączone.

## Widok monitoringu

Monitor archiwum powinien rozdzielać zdrowe pobieranie od odzyskiwania:

```
ARCHIWUM: zapisane boxy / wszystkie boxy / przyrost od poprzedniego pomiaru
KOLEJKA: ukończone / oczekujące / retry / kwarantanna / % znanej kolejki
ŹRÓDŁA: aktywne zdrowe / w cooldownie / w recovery / do kontaktu
RECOVERY: otwarte sprawy | ostatnia decyzja | ostatni dry-run | boxy po naprawie
```

Przy każdej sprawie monitor pokazuje domenę, status, rodzaj błędu, ostatni
udany box, aktualną metodę, następny dozwolony krok i czas następnej kontroli.
Nie pokazuje sekretów, pełnego HTML ani prywatnych snapshotów.

## Lista do kontaktu

`contact_required` tworzy kartę, nie wysyła maila. Karta obejmuje wydawcę,
domenę, interesujący zakres, znalezione kanały, dowody ograniczeń, propozycję
współpracy, roboczy szkic wiadomości oraz historię późniejszego kontaktu.
Wysyłka wymaga osobnej decyzji właściciela/redakcji.

## Kryterium powodzenia

Proces jest skuteczny tylko wtedy, gdy liczba retry maleje, zdrowe źródła
tworzą nowe boxy, a każda przywrócona domena ma odtwarzalną instrukcję i dowód
legalnego zakresu. Liczba prób sama w sobie nie jest miarą postępu.
