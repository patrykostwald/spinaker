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
