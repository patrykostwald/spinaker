# Śledczy - runda 2b: weryfikacja po wdrożeniu (11.10.2026, ok. 17:20-17:45)

Rola: docs/SLEDCZY_ROLA.md. Tylko odczyt https://przeszlosc.today (publiczne API, odstęp 1 s między zapytaniami, niewidoczny Playwright). Zrzuty 1440 i 390 z pomiarem (`scripts/sledczy_zrzuty.js`): `C:\Users\User\Desktop\projekty\przeszlosc-gotowe\sledczy-runda-2b\` (osoba Tusk, spółka Orlen, drzewo Obajtka, temat CPK, Poprawki, wyszukiwarka spółek „PKO” i „7740001454”, panel węzła drzewa). Ocena modelu AI w roli, nie opinia prawdziwego dziennikarza.

## 1. Streszczenie

1. **Wdrożenie potwierdzone** sondami: `?cala_historia=5` → 400, Orlen `suspect_count: 2`, `/api/przeszlosc/poprawki/` 200. Ale `/api/przeszlosc/wersja/` ma puste `commit`, `built_at` i `source` - w kontenerze brak zmiennej `GIT_COMMIT` i brak repozytorium git (P2-9 niezaliczone).
2. **P0: 8 z 8 zaliczonych** według kryteriów odbioru (P0-1..P0-8). Suma Orlenu 3,91 mld zł zamiast 1091 mld; drzewo Obajtka bez zamówień spoza kadencji; graf „Kołodziejczak” bez Olimpii Jawor; Tusk 100 wzmianek ze `snippet`.
3. **Nowy P0:** temat CPK pokazuje „17 dokumentów Sejmu”, a to 14 ogłoszeń TED, 1 wpis z unijnego rejestru przejrzystości i 2 posiedzenia komisji; RSS podpisuje ogłoszenia TED jako „Sejm · notice”. Błędne źródło w narzędziu, które obiecuje pochodzenie.
4. **Nowy P0:** wzmianki 0 u Morawieckiego i Bodnara bez wyjaśnienia. Bodnar ma dwa rekordy (505 „former” i 686 „current”, oba senator), tak samo Ziemniak (553/782) - duplikat blokuje dopasowanie jako „imiennik”.
5. P1: zaliczone P1-4, P1-5, P1-8, P1-12; częściowo P1-1 (PKO i dociąganie KRS nie działa, REGON 9 cyfr nie działa), P1-3 (drzewo Tuska domyślnie nadal 297 głosowań z 2025-04..07), F9 (2 z 12 odnośników z wstawionym numerem); niezaliczone P1-9, P1-11.
6. **Szybkość:** mediana na zimno dobra (osoba 1,1 s, temat 0,6 s), ale ogon nie: p95 osoba 19,3 s (Obajtek), temat 3,1 s, spółka 3,1 s; ciepło p95 0,6 / 0,6 / 0,5 s. Drzewo „cała historia” 23,4 s, eksport drzewa 16,3 s.
7. **Telefon 390:** brak przewijania poziomego, ale treść jest ucinana: 309 elementów poza ekranem na profilu Tuska, 284 na Orlenie; uciekają przycisk „Obserwuj osobę”, JSON, prawa kolumna liczb, „Narracja” w nagłówku.
8. Liczniki: „100 artykułów” to limit zapytania (Tusk: 100 wzmianek z 3 dni), nie liczba artykułów.
9. Pewność „medium” (samo nazwisko) jest w API, ale nie w interfejsie; strona główna dalej mówi „Nic nie łączymy po samym nazwisku”.
10. **Średnia: 5,6 / 10** (R1 i R2: 4,4). Najniżej: kompletność 4, zmiany w czasie 4.

## 2. Wyniki P0

| # | Kryterium odbioru | Wynik | Dowód (produkcja) |
|---|---|---|---|
| P0-1 | Orlen suma < 10 mld zł; TED 157377-2026 z `amount_suspect`, poza `sums` | **TAK** | `/spolka/0000028860/`: `sums 3 909 475 083,71 PLN`, `suspect_count 2` (157377-2026 i 728541-2025); UI „3,91 mld zł … bez 2 kwot do weryfikacji”; CSV: „(do weryfikacji, poza sumami)” |
| P0-2 | drzewo Obajtka domyślnie 0 zamówień 2025-2026; z przełącznikiem są z `outside_tenure` | **TAK** | domyślnie 25 węzłów, 0 zamówień; `?cala_historia=1`: 59 zamówień 2025-2026, każde `meta.outside_tenure: true`; `?cala_historia=5` → 400 |
| P0-3 | temat Kołodziejczak tylko podmioty związane | **TAK** | 5 podmiotów: Agrounia, Unia Warzywno-Ziemniaczana, Nowoczesny Rolnik, Startup Rolniczy, Przyjaciół Ziemi Sieradzkiej (funkcje osoby będącej tematem); brak Olimpii Jawor, szpitali, KUKE |
| P0-4 | Tusk ≥ 100 wzmianek z 30 dni ze `snippet`; licznik = liczba wzmianek | **TAK** (z uwagą) | 100 wzmianek 2026-10-08..11, 100/100 ze `snippet` z nazwiskiem; licznik 100 = `len`. Uwaga: 100 to sufit, nie liczba (P1-13) |
| P0-5 | przycisk 1440 i 390 na 3 typach stron; strona Poprawki | **TAK** | „Zgłoś błąd lub sprostowanie”: profil i spółka 1440/390, panel węzła drzewa 1440 (`przeplyw-wezel-1440.png`); `/przeszlosc/poprawki` 200 (pusta lista). Na 390 klik w węzeł drzewa się nie udał w teście (nie rozstrzygam) |
| P0-6 | wdrożenie | **TAK** | sondy jw. |
| P0-7 | „Premier Tusk”, „Donalda Tuska”, „PUPIL TUSKA” trafiają | **TAK** | „…zamach na premiera Donalda Tuska” (high), „groził Tuskowi” (medium), tytuły wersalikami TV Republika w wynikach |
| P0-8 | `snippet` przy każdej wzmiance; licznik; `/przeszlosc/poprawki` | **TAK** | 1300 wzmianek w 13 profilach (z 15 sprawdzonych), 0 bez `snippet` |

## 3. Wyniki P1, F i P2

| # | Wynik | Dowód |
|---|---|---|
| P1-1 wyszukiwarka spółek | **częściowo** | działa: „Orlen”, „orlen s.a.”, KRS 0000028860, NIP 7740001454 i 774-000-14-54, „ławecz”; `/spolka/7740001454/` 200. Nie działa: „PKO” (brak w 800 podmiotach), dociąganie KRS 0000026438 (PKO BP) i 0000009831 (PZU) → „nie znaleźliśmy w rejestrze”, `/spolka/0000026438/` 404; REGON 9-cyfrowy 610188201 (w bazie zapisany 14-cyfrowy) → brak; „PL7740001454” traktowany jako nazwa; komunikat „po nazwy”, „po numeru KRS” (błąd odmiany) |
| P1-3 głosowania | **częściowo** | `/temat/glosowania/?q=VAT`: 16, 2 strony, zakres, filtr od/do, 400 dla złej daty - dobrze. Turów 0, „Centralny Port Komunikacyjny” 0, CPK 0, choć RSS CPK pokazuje wpis Kancelarii Sejmu o rządowym projekcie zmiany ustawy o CPK (odmiana i skróty - P1-14). Drzewo Tuska domyślnie: 297 węzłów głosowań z 2025-04-24..2025-07-25, `truncated`; dopiero `?od=2026-01-01` daje 50 najnowszych |
| P1-4 provenance | **TAK** | link urzędowy do wyszukiwarki KRS MS, rejestr.io jako „dodatkowy”, `snippet` wszędzie. Brak etykiety pewności w UI - P1-15 |
| P1-5 eksport | **TAK** | CSV Kołodziejczaka: 1557 głosowań (794+665+80+8+6+4), kolumny źródło/data pobrania/pewność/identyfikator, przypis do cytowania, ochrona przed formułami (`'`); spółka CSV/JSON; drzewo CSV. Do sprawdzenia: `data_pobrania` = data eksportu w 1565 wierszach, także przy wpisach sprzed tygodni |
| P1-8 kolejność po `?q=` | **TAK** | pierwszy element pod menu 21 px (1440) i 20 px (390); nagłówek tematu przed paskami |
| P1-9 szybkość | **NIE** | p95 na zimno: osoba 19,3 s (n=15; mediana 1,1 s), temat 3,1 s (n=12; mediana 0,6 s), spółka 3,1 s (n=12; puste spółki 2 KB też 2,5-3 s). Ciepło p95: 0,59 / 0,57 / 0,47 s. Duplikaty senatorów 7,8-12,2 s przy 7 KB odpowiedzi. Tusk na zimno nie do zmierzenia (był w cache, 0,6 s) |
| P1-11 spójność flag | **NIE** | TED 728541-2025 (1,01 mld zł): w `/spolka/` `amount_suspect: true`, w `/przeplyw/` kwota bez flagi |
| P1-12 pusty temat | **TAK** | `xqzw8b`, `zzqv41`: 0,22 s na zimno |
| F2 strażnik cytatu | **nie potwierdzone** | kod i etykieta są, ale 0 z 1300 materiałów i wzmianek ma `text_changed` - albo nikt nie poprawił tekstu, albo wykrywacz nie działa |
| F5-minimum | **TAK w zakresie widocznym z zewnątrz** | sesja z `?q=`: tylko zapytania GET do własnego API, 0 skryptów i żądań zewnętrznych, 0 POST z treścią zapytania; Caddy bez dyrektywy `log`, gunicorn bez `--access-logfile`. Uwagi: Sentry (`send_default_pii=False`) i tak zapisuje URL z `?q=` przy błędzie; CSP bez `default-src`/`script-src` |
| F9 przybornik | **częściowo** | 12 odnośników przy spółce, 9 przy osobie, ale numer wstawiony tylko w 2 (odpis API MS, rejestr.io); reszta „wpisz NIP”. Kryterium „≥ 8 z wstawionym NIP/KRS” niespełnione. Odpis API zawsze `rejestr=P` - dla fundacji (rejestr S) błąd |
| P2-1 390 | **NIE** | `pomiar.json`: elementy poza ekranem 309 (Tusk), 284 (Orlen), 317 (CPK), 123 (drzewo); zrzuty `*-390.png` |
| P2-2 etykiety | **TAK** | 0 elementów interaktywnych bez nazwy na 6 stronach |
| P2-3 RSS | **TAK** | `pubDate` RFC 822, link kanału przeszlosc.today; nowy błąd: TED jako „Sejm · notice” (P0-10) |
| P2-4 daty przyszłe | **TAK** | `/start/` `latest` 0 dat > dziś, osobne `scheduled` |
| P2-5 etykiety filtrów | **TAK** | brak powtórzeń w filtrach tematu |
| P2-6 wersaliki | **częściowo** | profil i wyszukiwarka „Daniel Obajtek”; drzewo i jego CSV nadal „Daniel OBAJTEK” |
| P2-9 wersja | **NIE** | `commit: ""`, `built_at: ""`, `source: ""` |

## 4. Czas odpowiedzi API (11.10, 17:20-17:40, odstęp 1 s)

| Zapytanie | Zimno (pierwsze wejście) | Ciepło | Uwagi |
|---|---|---|---|
| `/osoba/` 15 osób | 0,5-19,3 s; mediana 1,1; p95 19,3 | 0,16-0,59 s | najwolniej: Obajtek 19,3, Bodnar 9,7, Siemoniak 7,8, Czarzasty 7,8, Ziobro 7,4 |
| `/temat/` 12 tematów | 0,22-3,1 s; mediana 0,6; p95 3,1 | 0,13-0,57 s | CPK 3,1 (część mogła być w cache) |
| `/spolka/` 11 spółek | 1,5-3,1 s; p95 3,1 | 0,15-0,47 s | stały koszt ok. 2,5 s także dla pustych |
| `/przeplyw/` Obajtek `?cala_historia=1` | 23,4 s | - | |
| eksport drzewa Obajtka CSV | 16,3 s | - | eksport spółki 5,6 s |
| `/spolki/?q=` | 0,15-0,5 s; z dociąganiem KRS 1,1-1,5 s | - | |

## 5. Oceny 0-10

| # | Obszar | R1 | R2 | R2b | Zmiana | Uzasadnienie |
|---|---|---|---|---|---|---|
| 1 | Szybkość | 5 | 5 | 6 | +1 | mediany < 1,2 s, ciepło < 0,6 s, pusty temat 0,2 s; ogon osoby 19 s i drzewo 23 s |
| 2 | Kompletność | 3 | 3 | 4 | +1 | wzmianki 100 u większości, wyszukiwarka spółek; ale 800 podmiotów, brak PKO/PZU i nie działa dociąganie KRS, Sikorski 0 głosowań i 0 wpisów na X, Morawiecki i Bodnar 0 wzmianek, CPK 0 głosowań, brak funkcji premiera |
| 3 | Pochodzenie i dowód | 5 | 5 | 6 | +1 | `snippet`, link KRS MS, kolumny provenance; minus TED jako „dokumenty Sejmu”, pewność niewidoczna, `data_pobrania` wątpliwa |
| 4 | Powiązania i przepływy | 4 | 4 | 6 | +2 | P0-1, P0-2, P0-3 działają; drzewo Tuska domyślnie 297 starych głosowań, flaga kwot niespójna, wersaliki |
| 5 | Zmiany w czasie | 3 | 3 | 4 | +1 | RSS poprawny, strażnik cytatu w kodzie; 0 zmian widocznych, brak wersji wdrożenia, brak dziennika zmian KRS |
| 6 | Eksport i cytowanie | 5 | 5 | 7 | +2 | pełne CSV z wierszem „pominięto”, przypis, eksport spółki i drzewa; eksport drzewa 16 s |
| 7 | Zaufanie, neutralność, język | 5 | 5 | 6 | +1 | wynik tematu przed YouTube, graf bez obcych podmiotów; ale „Nic nie łączymy po samym nazwisku” obok automatycznych dopasowań, „100 artykułów” jako sufit, błędna etykieta Sejm |
| 8 | Prawo i etyka | 5 | 5 | 7 | +2 | sprostowanie i strona Poprawki, flagowane kwoty, okres funkcji, F5-minimum; minus: brak etykiety „samo nazwisko”, duplikaty osób |
| 9 | Użyteczność i dostępność | 5 | 5 | 5 | 0 | etykiety drzewa poprawione, ale ucinanie treści na 390 na 4 typach stron, 30-70 celów < 44 px, zagnieżdżone `<main>`, strona 404 po angielsku z logo spin.clinic |
| 10 | Przewaga nad konkurencją | 4 | 4 | 5 | +1 | wyszukiwarka spółek, przybornik, eksport z provenance; w pytaniu „kto stoi za PKO BP” nadal przegrywamy z rejestr.io |
| | **Średnia** | **4,4** | **4,4** | **5,6** | **+1,2** | |

## 6. Backlog - nowe pozycje

Otwarte z poprzednich rund: P1-1 (część), P1-2, P1-3 (część), P1-6, P1-7, P1-9, P1-10 (do potwierdzenia pomiarem Tuska na zimno), P1-11, P2-1, P2-6 (część), P2-7, P2-8, P2-9, F2 (potwierdzenie), F9 (część).

### P0 (blokuje zaufanie lub prawdę)
| # | Problem | Dowód | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|---|
| P0-9 | Wzmianki 0 bez wyjaśnienia u kluczowych osób; duplikaty osób w rejestrze | Morawiecki 0, Bodnar 505 i 686 po 0; Bodnar i Ziemniak po dwa rekordy (senator „former” i „current”) - ta sama osoba liczona jako imiennik | scalić duplikaty (ten sam identyfikator Senatu/Wikidata → `merged_into`); gdy wzmianki = 0 z powodu imiennika lub wykluczenia, zwracać `mentions.reason` i pokazać go w UI („wstrzymane: w rejestrze 2 osoby o tym nazwisku”); sprawdzić przyczynę u Morawieckiego | `osoby/?q=Bodnar` zwraca jednego Adama Bodnara; Morawiecki ≥ 50 wzmianek z 30 dni; każdy profil z 0 wzmiankami ma niepusty `mentions.reason` | S |
| P0-10 | Ogłoszenia TED i wpisy rejestru UE podpisane jako „dokumenty Sejmu” | temat CPK: „17 dokumentów Sejmu”, „W Sejmie: 17 dokumentów” = 14 TED + 1 Transparency Register + 2 komisje; RSS „Sejm · notice: Polska – Roboty budowlane…” z linkiem ted.europa.eu | etykieta i licznik według źródła rekordu (TED, rejestr UE, Sejm), w nagłówku tematu osobne liczby; RSS z nazwą źródła | temat CPK: licznik „dokumentów Sejmu” = liczba rekordów z `api.sejm.gov.pl`; 0 pozycji RSS z „Sejm” i linkiem spoza sejm.gov.pl | S |

### P1 (duża wartość)
| # | Problem | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|
| P1-13 | Licznik „100 artykułów” to sufit zapytania | liczyć `articles_total` osobno (count bez limitu, cache) albo pisać „100+ (ostatnie 100)” | Tusk: licznik > 100 albo z oznaczeniem „100+”; test z osobą < 100 wzmianek pokazuje dokładną liczbę | S |
| P1-14 | Wyszukiwanie głosowań i tematów bez odmiany i skrótów | słownik skrótów (CPK, KPO, NFZ, SAFE…) i dopasowanie form (Centralny Port Komunikacyjny / Centralnym Porcie Komunikacyjnym), np. lematy lub `pg_trgm` na tytułach głosowań | `/temat/glosowania/?q=CPK` > 0, jeśli w danych jest głosowanie nad ustawą o CPK z kadencji 10; test jednostkowy z formą miejscownika | M |
| P1-15 | Pewność dopasowania niewidoczna w interfejsie; strona główna obiecuje „Nic nie łączymy po samym nazwisku” | etykieta przy wzmiance „samo nazwisko” (medium) i „imię i nazwisko” (high), filtr „tylko pełne imię i nazwisko”; zmienić zdanie na stronie głównej na zgodne z metodą | każda wzmianka `medium` ma widoczną etykietę na 1440 i 390; tekst strony głównej nie przeczy `match_method: name_only` | S |
| P1-16 | Dociąganie KRS na żądanie nie działa; błędy sieci zgłaszane jako „brak w rejestrze” | sprawdzić połączenie serwera z api-krs.ms.gov.pl (log `KRS … http`), rozdzielić `None` dla 404 od błędu sieci w `krs.fetch`, przy błędzie komunikat „rejestr nie odpowiada” | `spolki/?q=0000026438` zwraca PKO BP z `fetched: true`; `/spolka/0000026438/` 200; test: timeout → status `error`, nie `missing` | S |
| P1-17 | REGON 9-cyfrowy i NIP z prefiksem PL nie znajdują podmiotu | porównywać REGON po pierwszych 9 cyfrach (`regon__startswith`), zdejmować prefiks `PL`; poprawić odmianę w komunikacie („po nazwie”, „po numerze KRS”) | `spolki/?q=610188201` i `?q=PL7740001454` zwracają Orlen; komunikat bez „po nazwy” | S |
| P1-18 | Drzewo osoby domyślnie bez limitu i sortowania głosowań | zastosować w domyślnym widoku tę samą ścieżkę co przy `?od=` (najnowsze, ≤ 50) | `/przeplyw/osoba:326-donald-tusk/` bez parametrów: ≤ 50 węzłów `vote`, najnowsza data = najnowsze głosowanie Tuska | S |
| P1-19 | Ucinanie treści na 390 (rozszerzenie P2-1 do P1) | kontener profilu, spółki i tematu `max-width: 100%`, siatka liczb 2 kolumny, przyciski zawijane, nagłówek bez „Narracja” lub w menu | `pomiar.json` 390: `overflowing` = 0 na profilu, spółce, temacie i drzewie; „Obserwuj osobę” i JSON w całości na ekranie | S |
| P1-20 | Luki danych u członków rządu | Sikorski: 0 głosowań, 0 wpisów na X, brak mandatu posła X kadencji; łączy się z P1-2 | uzupełnić mandaty kadencji 10 dla ministrów-posłów i konta X z Wikidata | Sikorski ma głosowania X kadencji i konto X; lista ministrów-posłów bez głosowań = 0 | M |

### P2 (dopracowanie)
| # | Problem | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|
| P2-10 | `data_pobrania` w eksporcie = data eksportu | brać `retrieved_at`/`source_checked_at` rekordu; gdy brak, pusta kolumna, nie dzisiejsza data | wpis X z 2026-10-02 ma datę pobrania ≤ data pierwszego zapisu u nas | S |
| P2-11 | Przybornik: numer wstawiony tylko w 2 z 12 linków; odpis API zawsze `rejestr=P` | głębokie linki z parametrem tam, gdzie urząd je przyjmuje (Biała lista API, KRZ, RDF), `rejestr=S` dla fundacji i stowarzyszeń | ≥ 8 linków z wstawionym numerem; Fundacja Agrounia: odpis z `rejestr=S` zwraca 200 | S |
| P2-12 | Strona 404 w domenie przeszlosc.today: logo spin.clinic, tekst angielski | własna strona 404 przeszłość.today po polsku z polem wyszukiwania | `https://przeszlosc.today/przeszlosc/nieistnieje` → 404 z marką przeszłość.today i polskim tekstem | S |
| P2-13 | Zagnieżdżone `<main>` (aplikacja i widok) | jeden `main` na stronę | 1 element `main` na 6 stronach testowych | S |
| P2-14 | Głosowania tematu: 8 pozycji = 214 KB (pełne listy posłów) | listy posłów doładowywane po rozwinięciu | `/temat/glosowania/?q=VAT` < 40 KB | S |
| P2-15 | `/wersja/` pusta (P2-9 dalej otwarte) | `GIT_COMMIT` i `BUILD_TIME` jako `ARG`/`ENV` w Dockerfile przy budowie | `commit` = hash wdrożonej gałęzi, `source: env` | S |

## 7. Co jest już świetne
- Poprawki P0 działają na produkcji i zachowują dowód: rekordy z nierealną kwotą są widoczne, oznaczone i poza sumą, także w CSV.
- Eksport profilu jest pełny (1557 głosowań), z przypisem do cytowania i ochroną przed formułami w arkuszu.
- Wzmianki: 100 świeżych pozycji u większości polityków, każda z fragmentem dopasowania.
- Pusty temat 0,2 s, wyszukiwarka spółek 0,15-0,5 s, ciepła pamięć 0,1-0,6 s.
- Strona Poprawki i przycisk sprostowania przy profilu, spółce i węźle drzewa.

## 8. Ryzyka prawne i etyczne
- „Dokumenty Sejmu”, które są ogłoszeniami przetargowymi (P0-10), to błąd źródła w cytowalnym liczniku - redaktor przepisze go do tekstu.
- Dopasowania po samym nazwisku bez etykiety (P1-15) przy deklaracji „nic nie łączymy po samym nazwisku” - rozjazd obietnicy i metody, łatwy do wytknięcia.
- Duplikaty osób (P0-9): ta sama osoba z dwoma profilami i różnymi danymi; ryzyko sprzecznych twierdzeń o funkcji („former” i „current”).
- F5: zapytania nie trafiają do analityki ani do stron trzecich, ale błąd aplikacji wysyła URL z `?q=` do Sentry - przed obietnicą „trybu bezpiecznego” wyczyścić `q` w `before_send`.

## 9. Czego nie zweryfikowałem
- Przyczyny niedziałania dociągania KRS (połączenie z api-krs z serwera) - zgodnie z zasadą nie pytałem api-krs bezpośrednio.
- Logów serwera (F5) - ocena tylko z konfiguracji w repo i ruchu przeglądarki.
- Czy Turów i Lex Tusk mają głosowania w danych (możliwe, że baza obejmuje tylko X kadencję).
- Czasu na zimno dla Tuska, CPK i Kołodziejczaka (były w cache po wdrożeniu); znane wcześniej 8,7 s dla Tuska.
- Działania strażnika cytatu (0 przypadków na produkcji).
- Martwych linków przybornika (zakaz zapytań poza przeszłość.today).
- Wysyłki formularza sprostowania (zakaz wysyłania).

## 10. Mapa funkcji do dodania
Nowe pozycje (bez powtórzeń z SLEDCZY_FUNKCJE_1.md): docs/SLEDCZY_FUNKCJE_2.md.
