# Zwiadowca rozwiązań (7.10.2026)

Cel właściciela: „mieć podłączone wszystkie najlepsze technologie”. Pętla, która bez przerwy szuka, sprawdza i kieruje do odbiorców
darmowe albo tanie modele, dane i funkcje - tak, żeby trafiały do użycia, a nie do archiwum.

## Dlaczego powstała
Badacze przegapili Inception Mercury (100 mln darmowych tokenów), bo:
- Ekspert AI (`news/ekspert_ai.py`) czyta tylko znaleziska Pielgrzyma i pyta „które modele warto egzaminować” (jakość, nie koszt);
- Technolog (`news/pracownia_osint.py`, TECH_FEEDS) czyta wydania otwartych narzędzi z zastrzeżeniem „nic, co wysyła dane na zewnątrz” -
  API dostawców są poza jego zakresem;
- Rekruter (`discover()`) widzi tylko katalogi dostawców, do których mamy klucz;
- Mechanik naprawia istniejące miejsca w Konsylium; Badacz odkrywa kanały RSS, ale nikt nie pyta go o koszty;
- żaden kontrakt pętli nie miał odbiorcy dla ustaleń „co obniża koszt lub zdejmuje limit”.

## Trzy kroki
| Krok | Kiedy | Modele AI | Co robi | Odbiorca |
|---|---|---|---|---|
| Obserwatorzy | codziennie 5:40 (`zwiadowca-daily`) | nie | OpenRouter `/api/v1/models` (modele `:free` i tanie), router Hugging Face `/v1/models` i trending, kanały RSS dostawców (Cloudflare, Google for Developers, NVIDIA, Hugging Face, Simon Willison), wydania narzędzi na GitHub (`releases.atom`) i wyszukiwanie repozytoriów po tematach (fact-checking, OSINT, entity-resolution, sanctions, polish-nlp), nowe zbiory dane.gov.pl i data.europa.eu. Różnica wobec rejestru (`council_registry.KEYS`, skład Konsylium, Inception, kanały Pracowni i Badacza). | nowy darmowy model lub dostawca = SYGNAŁ (`AgentNote` agent `rozwiazania`, kind `signal`): Rekruter, gdy mamy klucz; właściciel mailem, gdy klucz trzeba założyć; Mechanik dla nowych dostawców pod routerem HF |
| Zwiad tygodnia | poniedziałek 4:10 (`zwiadowca-weekly`) | jeden darmowy model: Inception pierwszy, potem łańcuch (`agents_common.ask_any`, poziom „rozwój”) | ocena pozycji z 7 dni według kryteriów: konkretny limit lub funkcja, legalność, regulamin (trenowanie na danych z API, treści polityczne), wysiłek S/M/L, twarde zasady; do 10 ustaleń, dowody tylko z danych wejściowych, bez powtórek | ustalenie `finding` z polem `findings[].action` |
| Odbiorcy | automatycznie | - | modele -> kolejka Rekrutera (`recruiter_candidates()` w `council_recruiter.discover`, egzamin, progi i Karta bez zmian; okres cienia wejdzie ze zleceniem Z5); pule i dostawcy -> rejestr pojemności (`capacity_lines()` w planie dnia Dyrygenta) i lista zamienników Mechanika (`fallbacks()`); narzędzia, dane, funkcje -> Architekt (`solutions` w `pracownia_osint.architekt`, jedyny autor biletów); ryzyko -> Prawnik (`pracownia_osint.prawnik`) | Raport pętli: sekcja „Nowe możliwości tygodnia”; kontrakt `rozwiazania` (odbiorca Architekt, SLA 7 dni) |

Pierwszy przebieg obserwatorów to linia bazowa: zapisuje znane pozycje bez sygnałów.

## Bezpiecznik i naprawa
`petle_bezpieczniki.scout_signals`: sygnał bez odbiorcy ponad `ZWIADOWCA_SIGNAL_SLA_H` (72 h) = ostrzeżenie w panelu i Raporcie pętli.
Naprawa przed alarmem (`petle_naprawy.scout_signals`): zamknięcie sygnałów już odebranych (egzamin w dzienniku Rekrutera, klucz dodany,
plan Architekta po ustaleniu), potem jedno ponowienie Rekrutera na dobę. Klucz dostawcy zakłada tylko właściciel (przypomnienie, bez alarmu).

## Komendy
- `python manage.py zwiadowca_start --plan` - linia bazowa bez sieci: co używamy wobec znanych darmowych alternatyw i luk w danych.
- `python manage.py zwiadowca_start` - jeden przebieg obserwatorów (pierwszy = linia bazowa).
- `python manage.py zwiadowca_start --zwiad` - zwiad tygodnia teraz.

## Zmienne środowiska
- `AGENTS_ENABLED=true` - jak inne pętle agentów.
- `GITHUB_TOKEN` (opcjonalnie) - wyższy limit zapytań GitHub (bez tokena 10 zapytań na minutę).
- `ZWIADOWCA_FEEDS` (opcjonalnie) - JSON `nazwa -> adres` dodatkowych kanałów RSS/Atom.
- `ZWIADOWCA_SIGNAL_SLA_H` (domyślnie 72).

## Zasady
Tylko udokumentowane publiczne punkty końcowe i kanały; bez logowania, bez scrapowania stron za zgodą, bez płatnych wywołań.
Zwiadowca niczego nie buduje i nie zmienia składu Konsylium: model wchodzi tylko przez egzamin Rekrutera, bilet powstaje tylko u Architekta.
