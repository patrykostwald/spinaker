# Oficjalne źródła — stan i bezpieczny start

Ten dokument rozdziela trzy rzeczy: katalog kandydatów, zatwierdzony kanał
pobierania oraz materiał widoczny w Bazie. Dopiero zatwierdzony kanał może
zasilać Bazę automatycznie.

## Działa po stronie workerów

| Źródło | Zakres | Co trafia do Bazy | Harmonogram / limit |
|---|---|---|---|
| Sejm RP | lista i szczegóły głosowań oraz druki w granicach karty | oficjalne głosowania i dokumenty | zadania cykliczne, limit zapisany w karcie |
| ELI: Dziennik Ustaw i Monitor Polski | przyrostowe metadane aktów | tytuł, data, identyfikator i link do aktu; bez PDF i pełnego tekstu | co godzinę, limit zapisany w karcie |
| dane.gov.pl | sprawdzenie kontraktu katalogu | nic — tylko kontrola dostępności metadanych | raz dziennie |
| GUS BDL | sprawdzenie kontraktu API | nic — tylko kontrola dostępności metadanych | raz dziennie |

## Gotowe do pierwszego uruchomienia

### NIK

Oficjalny RSS NIK pobiera wyłącznie tytuł, adres oryginału, datę oraz opis
udostępniony w feedzie. Nie odwiedza stron artykułów, nie pobiera obrazów, PDF-
ów ani archiwum. NIK podaje, że korzystanie z materiałów jej serwisu nie wymaga
zgody, poza elementami osobno oznaczonymi jako należące do osób trzecich; przy
każdym boxie zachowujemy źródło i odnośnik.

Po pobraniu najnowszej gałęzi jednorazowy start to:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-ApprovedNIKRss.ps1
```

Potem standardowy worker odświeża ten sam RSS co godzinę przez bramkę dostępu.
Jeśli RSS przestanie spełniać warunki, źródło zostaje zablokowane zamiast
przechodzić do pobierania HTML.

## Kolejka powiększania źródeł

1. **Oficjalne kanały RSS i API instytucji** — każdy dokładny endpoint dostaje
   osobną kartę, limit i test odpowiedzi. Najpierw metadane oraz link do
   oryginału.
2. **BIP i gov.pl** — tylko wskazana sekcja oraz tylko po zapisaniu warunków
   ponownego wykorzystania. RSS jest preferowany przed HTML.
3. **Media** — tylko kanał udostępniony przez wydawcę i zakres, który on
   udostępnia; domyślnie tytuł, data, URL i ewentualny opis feedu. Pełny tekst
   nie jest pobierany bez osobnej podstawy.
4. **KRS** — możliwy wyłącznie jako osobny, wąski pilot danych już wskazanego
   podmiotu. Może uzupełnić nazwę/formę i link do wpisu. Nigdy nie wyszukuje ani
   nie łączy osób po nazwisku, PESEL-u, dacie urodzenia lub innych danych
   osobowych.

## Automatyczna kontrola kandydatów

Kontrola może sprawdzić, czy katalogowy adres, RSS lub sitemap nadal odpowiada,
ale nie zmienia aktywności źródła ani nie pobiera publikacji. Włączenie wymaga
osobno: oficjalnego operatora, dokładnego endpointu, zasad użycia, limitu,
zapisanej karty dostępu i udanego ograniczonego pilota.

Taka kolejność pozwala rozszerzać Bazę szybko, a jednocześnie nie zamieniać
katalogu linków w automat pobierający materiały bez podstawy.

## Zabezpieczenie aktywacji po audycie

Polecenie `apply_audited_feeds` nie włącza już źródła wyłącznie dlatego, że
techniczny test RSS znalazł działający kanał. Zanim kandydat zmieni status na
skonfigurowany, system sprawdza ważną kartę RSS dopasowaną do dokładnego adresu
feedu. Brak takiej karty kończy się raportem
`missing_approved_access_card` i nie powoduje żadnego pobrania publikacji.

## Powiększanie kolejki kandydatów bez importu

Dla regularnej, małej kontroli katalogu można uruchomić:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Audit-NextSourceCandidates.ps1
```

Domyślnie sprawdza 24 nieaktywne kandydatury, maksymalnie trzema równoległymi
połączeniami, zapisuje raport w `reports/` i kończy się lokalnym preflightem.
Nie pobiera publikacji, nie uruchamia harvestera i nie zmienia statusu źródeł.
Do większej paczki użyj `-BatchSize 48`; nie zwiększaj jej bez analizy raportu.

### KPRM

Oficjalna sekcja aktualności Kancelarii Prezesa Rady Ministrów może działać jako
wąski pilot metadanych. Karta obejmuje wyłącznie `www.gov.pl/web/premier`, ma
limit 24 żądań na dobę i nie pozwala zachowywać pełnej treści, PDF-ów, obrazów,
nagrań ani wideo.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-ApprovedKprmMetadataPilot.ps1
```

Podstawą jest strona KPRM o ponownym wykorzystywaniu informacji sektora
publicznego. Przy każdym boxie pozostają adres KPRM oraz czas pozyskania.

## Jeden start zatwierdzonych źródeł

Gdy działają usługi Compose, jednorazowy start dostępnych już pilotów wykonuje:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-ApprovedMvpSources.ps1
```

Uruchamia tylko ELI/dane.gov/GUS, NIK i KPRM. Sejm pozostaje oddzielnym
pilotem z własną kartą oraz własnym limitem. Skrypt nie uruchamia katalogowych
kandydatów, mediów ani KRS.


### Trybunał Konstytucyjny

Po świeżym audycie kanału RSS można uruchomić wąski pilot metadanych Trybunału
Konstytucyjnego. Karta zapisuje oficjalne warunki ponownego wykorzystywania,
dokładny adres kanału, limit 24 żądań na dobę i zakres: tytuł, data, link oraz
opis udostępniony w RSS. Nie pobiera HTML artykułów, załączników ani obrazów.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-ApprovedTkRss.ps1
```

Skrypt odmawia działania, jeśli audyt ma więcej niż dobę, RSS nie odpowiada lub
nie ma pełnego zapisu kontroli.

### KNF i IPN

Po kontroli z 23 września 2026 r. można uruchomić dwa kolejne, ograniczone
pilotaże RSS: Komisję Nadzoru Finansowego i Instytut Pamięci Narodowej.
Każdy przechowuje tylko elementy udostępnione przez RSS — tytuł, datę, link i
krótki opis — z linkiem do oryginału. Nie pobiera HTML artykułów, dokumentów,
multimediów ani pełnych archiwów.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-ApprovedKnfIpnRss.ps1
```

KNF wskazuje, że ponowne wykorzystanie informacji z BIP i strony KNF jest
bezpłatne przy podaniu adresu źródła. IPN opisuje RSS jako usługę dystrybucji
tytułów, krótkich opisów i linków. Skrypt nie uruchomi źródła bez świeżego,
poprawnego audytu RSS i zapisanej karty dostępu.

## Bieżący status harvesterów

Do odczytu lokalnego stanu workerów, zatwierdzonych kart oraz liczby boxów z
każdego aktywnego źródła służy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Get-MvpHarvesterStatus.ps1
```

Skrypt nie pobiera danych z internetu i nie zmienia bazy. Pokazuje także stan
usług Compose, dlatego jest właściwym pierwszym krokiem, gdy harvestery mają
pracować stale w tle.
