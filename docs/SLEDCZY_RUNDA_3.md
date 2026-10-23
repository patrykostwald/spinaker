# Śledczy - runda 3: przepływy pieniędzy, pokrycie KRS, stan danych (23.10.2026)

Rola: docs/SLEDCZY_ROLA.md. **Ta runda NIE miała dostępu do produkcji** (sesja w chmurze, bez https://przeszlosc.today i bez bazy produkcyjnej). Oceniam: kod z commitów 48f20ce..d25a9f8 (gałąź `cloud/przeszlosc-rozwoj`), testy uruchomione lokalnie i zrzuty 1440/390 na **danych demonstracyjnych** (`spolka-*`, `osoba-*`, `dane-*` w scratchpadzie sesji). Wszystkie liczby z produkcji w tym raporcie pochodzą z R2b (11.10); nowych liczb z produkcji nie ma. Oceny R3 są warunkowe: „zaliczone w kodzie” to nie „zaliczone na produkcji”. Ocena modelu AI w roli, nie opinia prawdziwego dziennikarza.

Zakres zmian: `krs_pokrycie.py` (kolejka KRS, Biała lista MF -> api-krs, odpis pełny), `krs_agent.py` (imiennicy), `przeszlosc_przeplywy.py` + `Przeplywy.tsx` (przepływy v1, sankey, tabela), `przeszlosc_stan.py` + `dane/StanDanych.tsx` (G4), NIW i 1,5% OPP w harmonogramie, migracja `0170_krs_kolejka`.

## 1. Streszczenie

1. **Testy:** 13 nowych (`test_krs_pokrycie`, `test_przeszlosc_przeplywy`, `test_przeszlosc_stan`) i 76 w plikach KRS/drzewo/przepływ - wszystkie przechodzą (lokalnie, 23.10).
2. **Główna obietnica spełniona w kodzie:** przepływy pieniędzy „skąd do kogo” z datą, kwotą, źródłem, sposobem łączenia (NIP/KRS) i okresem funkcji osoby; kwoty do weryfikacji w tabeli, poza sumą i wykresem. To realna przewaga, jeśli dane zaczną płynąć.
3. **Diagnoza „pustych przepływów” w inwentarzu jest uczciwa i trafna** (brak funkcji KRS, brak NIP, wyłączone źródła, TED w jedną stronę). Kolejka KRS adresuje dwie pierwsze przyczyny; trzecia (flagi `PUBLIC_RECORDS_TED/FTS_ENABLED` domyślnie wyłączone) zostaje decyzją wdrożeniową.
4. **Nowy P0 - „Wpływy” to suma wartości ogłoszeń TED, nie pieniędzy otrzymanych:** `drzewo_pieniedzy.contracts` bierze `data['value']` całego ogłoszenia, także przy wielu wykonawcach i częściach; boks nazywa to „Wpływy”. Zastrzeżenie jest tylko w stopce drobnym drukiem.
5. **Nowy P0 - furtka w zaostrzeniu imienników:** agent KRS potwierdza automatycznie przy „co najmniej jednym sprawdzonym źródle”, ale `_checked_sources` przepuszcza źródło `grounded` (adres był w wynikach wyszukiwania Gemini) bez sprawdzenia, że strona wymienia osobę i podmiot.
6. **Nowy P0 - Stan danych zaniża zasób:** strona liczy tylko `PublicRecord`; głosowania (`ParliamentaryVoting`), oświadczenia (`AssetDeclaration`), RCL, wzmianki, wpisy X nie mają własnego wiersza. Wiersz „Głosowania imienne” może pokazać „wyłączone, 0” obok profilu z 1557 głosowaniami (R2b). Domyślny tekst „Brak znanych braków.” przy 20 źródłach to twierdzenie bez pokrycia.
7. **Błąd kolejki KRS (P1):** podmioty, które legalnie nie mają NIP/REGON/formy w odpisie (częste w fundacjach), wracają co noc do kolejki z priorytetem 0 i nadpisaną datą ponowienia - zjadają limit 200 odpisów przed NIP-ami z TED/BZP/FTS i co noc odpytują api-krs o to samo.
8. **„NIP bez KRS” źle nazwany (P1):** Biała lista to wykaz podatników VAT; NIP spoza VAT (wiele NGO) dostaje trwały stan `no_krs` z opisem „np. działalność osoby fizycznej” i nigdy nie wraca.
9. **Telefon:** nowe sekcje na 390 bez poziomego przewijania, sankey z listą zamiast etykiet - dobrze; ale na Stanie danych opisy boksów i braki źródeł ucinane wielokropkiem (treść tylko w `title`, niedostępna dotykiem), błędy odmiany „1 funkcji”, „0 z 1 osób”. Stare widoki (P1-19) bez zmian.
10. **Średnia R3: 6,1 / 10 (warunkowa)**, R2b 5,6. Wzrost wynika z kodu, nie z produkcji; po sondzie może spaść, jeśli kolejka KRS i źródła pieniędzy nie ruszą.

## 2. Wyniki względem backlogu

### 2a. Zaliczone w kodzie (dowód: kod i test; produkcja niesprawdzona)

| # | Wynik w kodzie | Dowód |
|---|---|---|
| G4 stan danych | **częściowo** | `/api/przeszlosc/stan-danych/`, `/przeszlosc/dane`: 25 źródeł (22 + BZP, NIW, OPP), stan off/empty/stale/ok, próg 48 h, licznik, ostatni błąd, pokrycie KRS; test `test_statuses`. Braki: patrz P0-13 |
| Przepływy (obietnica 6.10) | **TAK v1** | `przeszlosc_przeplywy.py`: TED w obie strony, BZP bez kwoty, FTS, NIW, 1,5%; `sums` po walucie bez `amount_suspect`; sankey jednej waluty; `outside_tenure`; `empty_reason` dla osoby bez funkcji; test `test_org_flows_directions_and_sums`, `test_person_flows_only_in_tenure_and_empty_reason` |
| P1-11 spójność flagi kwot | **TAK** | przepływy używają `money.mark_suspect`; w demo 9 mld zł z etykietą „do weryfikacji”, poza sumą 15,8 mln zł |
| P1-16 błąd sieci ≠ brak w rejestrze | **TAK** | `krs.fetch_status` → ok/missing/error, P i S; kolejka: `error` z ponowieniem 2^n h (do 7 dni), `missing` osobno; test `test_network_error_is_retried_not_missing` |
| P2-11 (część) odpis rejestru S | **TAK dla pobierania** | `fetch_status` próbuje P, potem S. Linki przybornika (`rejestr=P`) - niesprawdzone w tej rundzie |
| Imiennicy (agent KRS) | **częściowo** | bez źródła relacja czeka na weryfikację zespołu (`pending_review`), test `test_agent_without_source_waits_for_editor`; furtka `grounded` - P0-12 |
| Daty wykreślenia z odpisu pełnego | **TAK** | `refresh_relations`: zamyka relację tylko gdy wszystkie zgodne maski mają datę końca; inaczej nic nie zmienia; test `test_full_extract_closes_relation_when_person_left_organ` |
| Osoby fizyczne w przepływach | **TAK** | wykonawca-osoba: „osoba fizyczna prowadząca działalność”, bez nazwy i NIP; kolejka nie bierze ich identyfikatorów; test `test_zasil_takes_only_identifiers_and_skips_natural_persons` |
| Biała lista - minimalizacja | **TAK w kodzie** | z odpowiedzi brane tylko `nip` i `krs`; test `test_biala_lista_keeps_only_krs` |
| NIW i 1,5% w harmonogramie | **TAK w kodzie** | `przeszlosc-niw-weekly`, `przeszlosc-opp-weekly`, flagi domyślnie włączone |

Pozycje oznaczone w inwentarzu jako zrobione wcześniej (P0-9, P0-10, P1-1/P1-16, P1-3/P1-18, P1-13, P1-15, P1-17) - **nie weryfikowałem** w tej rundzie; status „zrobione” przyjmuję z inwentarza do potwierdzenia sondą.

### 2b. Wymaga sondy na produkcji (kryterium odbioru)

| Sonda | Kryterium odbioru |
|---|---|
| S1 migracja i harmonogram | `0170_krs_kolejka` zastosowana; w Celery beat są `krs-pokrycie-night`, `przeszlosc-niw-weekly`, `przeszlosc-opp-weekly`; po pierwszej nocy `przeszlosc_krs_pokrycie --json` ma `kolejka.wedlug_stanu.ok` > 0 |
| S2 pokrycie KRS | po 7 nocach: odsetek podmiotów z NIP rośnie co noc; `bledy` < 5% przetworzonych; liczba `biala_lista_zapytania` na dobę ≤ 10 |
| S3 przepływy Orlenu i PKO BP | `/api/przeszlosc/przeplywy/spolka:0000028860/` 200, `suspect_count` ≥ 2 (TED 157377-2026 i 728541-2025, jak w R2b), suma `in` < 10 mld zł; PKO BP 0000026438 200 |
| S4 przepływy osoby | Obajtek: niepusta tabela z `via` = Orlen i 0 pozycji z datą spoza okresu funkcji bez `?cala_historia=1`; osoba bez funkcji ma `empty_reason` |
| S5 Stan danych zgodny z flagami workera | dla 3 źródeł stan na stronie = faktyczna flaga w kontenerze Celery (strona czyta env procesu web) |
| S6 czasy | `/przeplywy/` p95 na zimno < 3 s dla Orlenu i Obajtka; `/stan-danych/` < 1 s (10 zapytań z odstępem 1 s) |
| S7 dostęp | `/przeplywy/` nie zwraca 403 publicznie w becie (bramka `money_trail` jest w `PRO`) |
| S8 stopka | odnośnik „Stan danych” widoczny w stopce: jest w `ui.tsx`, ale **nie ma go na zrzucie `dane-1440.png`** (zrzut sprzed d25a9f8 albo stary build) |

## 3. Oceny 0-10

R3 = ocena kodu, testów i zrzutów demo; bez pomiaru produkcji.

| # | Obszar | R1 | R2 | R2b | R3 | Zmiana | Uzasadnienie |
|---|---|---|---|---|---|---|---|
| 1 | Szybkość | 5 | 5 | 6 | 6 | 0 | przepływy ładowane leniwie (IntersectionObserver), cache 6 h, stan danych 10 min; brak pomiaru; `org_flows` bez limitu przed cięciem do 500, osoba z wieloma podmiotami liczy każdy osobno |
| 2 | Kompletność | 3 | 3 | 4 | 5 | +1 | kolejka KRS z TED/BZP/FTS/NIW, TED w obie strony, NIW i OPP automatycznie; minus: TED/FTS dalej za flagami, starvation kolejki (P1-21), NIP spoza VAT bez drogi do KRS (P1-22) |
| 3 | Pochodzenie i dowód | 5 | 5 | 6 | 7 | +1 | każda pozycja z linkiem do rekordu, źródłem, licencją i `matched_by`; strona stanu danych; minus: licencja i „łączone po” tylko w `title`, Stan danych zaniża zasób (P0-13) |
| 4 | Powiązania i przepływy | 4 | 4 | 6 | 7 | +1 | sankey płatnik→odbiorca, dwa kierunki, okres funkcji, „przez: podmiot”; minus: „Wpływy” = wartość ogłoszeń (P0-11), węzły sankey po nazwie („Gmina” i „Gmina Miasto Demo” osobno w demo), podwójne liczenie u osoby (P1-23) |
| 5 | Zmiany w czasie | 3 | 3 | 4 | 5 | +1 | odpis pełny zamyka relacje datą wykreślenia; data ostatniego pobrania i stan „zaległe” per źródło; brak dziennika zmian i alertów spółki (P1-6) |
| 6 | Eksport i cytowanie | 5 | 5 | 7 | 7 | 0 | przepływy bez CSV/JSON i bez przypisu do cytowania; reszta jak w R2b |
| 7 | Zaufanie, neutralność, język | 5 | 5 | 6 | 6 | 0 | dobre zdania „osoba nie jest płatnikiem ani odbiorcą; funkcja to kontekst, nie dowód”, „brak w naszych danych, nie w świecie”; minus: „Wpływy”, „Brak znanych braków.”, odmiana „1 funkcji” |
| 8 | Prawo i etyka | 5 | 5 | 7 | 7 | 0 | osoby fizyczne bez nazw, Biała lista tylko pole `krs`, imiennicy do weryfikacji zespołu; minus: furtka `grounded` (P0-12), brak wpisu Białej listy i odpisu pełnego w rejestrze czynności |
| 9 | Użyteczność i dostępność | 5 | 5 | 5 | 5 | 0 | nowe sekcje 390 bez przewijania, lista zamiast etykiet (rozmiaru celów nie mierzyłem); minus: ucinanie na Stanie danych 390, wykres `aria-hidden` z danymi tylko w tabeli (dobrze) ale wstęgi tylko myszą; stare widoki bez zmian |
| 10 | Przewaga nad konkurencją | 4 | 4 | 5 | 6 | +1 | przepływy po identyfikatorach z oknem kadencji i flagą kwot to coś, czego nie widzę w znanych mi narzędziach PL w tej formie (do potwierdzenia w pętli Research); na produkcji niepotwierdzone |
| | **Średnia** | **4,4** | **4,4** | **5,6** | **6,1** | **+0,5** | warunkowa |

## 4. Nowy backlog

Otwarte z poprzednich rund: P1-2 (funkcje wykonawcze), P1-6 (obserwacja spółek, dziennik zmian), P1-7 (szum w temacie), P1-9 (szybkość - pomiar), P1-10 (indeks wzmianek), P1-14/G3 (skróty i odmiana), P1-19/P2-1 (ucinanie 390, stare widoki), P1-20 (luki ministrów, częściowo), P2-6 (wersaliki w drzewie), P2-7 (scalanie zamawiających - teraz też w sankey), P2-8 (sygnały czasowe), P2-10, P2-11 (linki przybornika), P2-12, P2-13, P2-14, P2-15 (`/wersja/`), F2 (strażnik cytatu - potwierdzenie), G1 (karta tożsamości - częściowo), G2, G5-G10.

### P0 (blokuje zaufanie lub prawdę)
| # | Problem | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|
| P0-11 | Boks „Wpływy” sumuje wartość całych ogłoszeń TED (`data['value']`), także przy wielu wykonawcach i częściach; „Wydatki” przy `ted_out` z „N wykonawców” tak samo. Dziennikarz przepisze to jako „spółka dostała X” | nazwać boksy „Wartość zamówień (z ogłoszeń TED)” i „Dotacje i 1,5%” osobno; przy >1 wykonawcy brać wartość części, jeśli ogłoszenie ją podaje, inaczej pozycja z flagą `shared_value` poza sumą; to samo w sankey | test: ogłoszenie z 2 wykonawcami nie podwaja sumy; na 1440 i 390 żaden boks nie nazywa wartości ogłoszeń „wpływami”; Orlen: suma TED ≠ suma dotacji (osobne liczby) | S |
| P0-12 | Automatyczne potwierdzenie relacji osoba-podmiot przy imiennikach opiera się na źródle `grounded` (adres z wyników wyszukiwania Gemini) bez sprawdzenia treści strony | w `_checked_sources` zawsze `page_mentions(url, nazwisko, podmiot)`; `grounded` tylko jako wskazówka; powód w `evidence_note` | test: źródło `grounded=True`, strona bez nazwiska → relacja `pending_review`; sonda: 0 relacji `krs_register` potwierdzonych po 23.10 bez źródła z dopasowaną treścią | S |
| P0-13 | Stan danych nie obejmuje głównych tabel (głosowania `ParliamentaryVoting`, druki `OfficialRecord`, oświadczenia `AssetDeclaration`, RCL, wzmianki, wpisy X, podmioty KRS); 20 źródeł z domyślnym „Brak znanych braków.” | wiersze dla każdego zbioru widocznego na profilu (licznik i ostatnia data z jego tabeli); bez znanego opisu braków pisać „braki nieopisane”; stan flag brać z zapisu workera (`PublicCollectionState`), nie z env procesu web | każda sekcja profilu osoby ma odpowiadający wiersz; „Głosowania” pokazują liczbę zgodną z sumą głosowań na profilach; 0 wierszy „Brak znanych braków.” bez opisu metodologii | M |

### P1 (duża wartość)
| # | Problem | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|
| P1-21 | Kolejka KRS: podmiot bez NIP/REGON/formy w odpisie wraca co noc (`_enqueue` resetuje `next_try_at` i daje priorytet 0) - zjada limit i odpytuje api-krs o to samo | w `zasil()` pomijać pozycje `ok` z `checked_at` młodszym niż `KRS_POKRYCIE_DNI`; brak NIP w odpisie zapisywać jako stan „KRS bez NIP” | test: dwa przebiegi `zasil()` jednej nocy i następnej nie zmieniają `next_try_at` pozycji `ok` sprzed < 90 dni; sonda: liczba odpisów `org` na noc spada do zera po pierwszym tygodniu | S |
| P1-22 | Biała lista obejmuje podatników VAT; NIP spoza VAT dostaje trwałe `no_krs` z opisem „np. działalność osoby fizycznej” i nie wraca | stan „brak w wykazie VAT” zamiast „NIP bez KRS”; ponowienie po 90 dniach; druga droga: KRS z NIW/OPP/odpisu, gdy NIP się zgadza | opis stanu nie sugeruje osoby fizycznej; pozycja `no_krs` wraca do kolejki po `KRS_POKRYCIE_DNI` | S |
| P1-23 | Przepływy osoby: ten sam rekord liczony dwa razy, gdy osoba ma funkcję w zamawiającym i w wykonawcy (`id@pk` różne) | deduplikacja po `record` przed `sums` i sankey; w tabeli jeden wiersz z dwiema etykietami „przez” | test: osoba z funkcją w obu stronach jednego TED - suma = 1 × kwota | S |
| P1-24 | Węzły sankey i sumy kontrahentów kluczowane nazwą z ogłoszenia, nie NIP („Gmina” i „Gmina Miasto Demo” osobno; wszystkie osoby fizyczne w jednym węźle) - rozszerza P2-7 | klucz węzła = NIP, nazwa z naszej bazy lub najczęstsza z ogłoszeń; osoby fizyczne bez agregacji w jeden „podmiot” (osobny węzeł zbiorczy z liczbą pozycji) | sankey Orlenu: liczba węzłów płatników = liczba unikalnych NIP zamawiających | S |
| P1-25 | Przepływy bez eksportu i przypisu | CSV/JSON z kolumnami: data, od (NIP), do (NIP), kwota, waluta, rodzaj, źródło, link, `matched_by`, `amount_suspect`, `outside_tenure`, data pobrania; przypis do cytowania | eksport Orlenu: liczba wierszy = `count`; kolumna flagi obecna; ochrona przed formułami jak w eksporcie profilu | S |
| P1-26 | Daty roczne (FTS, 1,5%) zamieniane na 31.12 przy ocenie okresu funkcji - dotacja z roku, w którym funkcja skończyła się w czerwcu, wypada „poza okresem”, a z roku, w którym zaczęła się w grudniu, wchodzi | rok częściowo pokryty = osobna etykieta „rok częściowo w okresie funkcji”, pokazywana domyślnie z oznaczeniem | test: funkcja 01.01-30.06.2024, dotacja 2024 → widoczna z etykietą, nie ukryta i nie „w okresie” | S |

### P2 (dopracowanie)
| # | Problem | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|
| P2-16 | Stan danych 390: opisy boksów i braki źródeł ucinane wielokropkiem; treść tylko w `title` | zawijanie do 2 linii, krótsze etykiety („Sprawdzone w KRS”), braki pod spodem w całości | `odstepy.js` i pomiar 390: 0 elementów z `text-overflow` ucinającym treść informacyjną | S |
| P2-17 | Odmiana liczebników: „1 funkcji”, „0 z 1 osób”, „1 pozycji z kwotą” | funkcja `plural()` w `ui.tsx` dla funkcja/osoba/pozycja/podmiot/rekord | 0 błędów odmiany dla n = 0, 1, 2, 5, 22 w teście komponentu | S |
| P2-18 | Licencja i „łączone po NIP/KRS” tylko w atrybucie `title` linku źródła | widoczna druga linia albo rozwinięcie wiersza | na 390 i klawiaturą widać licencję i sposób łączenia każdej pozycji | S |
| P2-19 | Wstęgi sankey podświetlają się tylko myszą; etykiety na 1440 nachodzą na wstęgi | fokus klawiaturą lub dotyk na węźle/wierszu legendy podświetla wstęgi; etykiety poza obszarem wstęg albo z tłem | test klawiatury: Tab przechodzi przez węzły; kontrast etykiety ≥ 4,5:1 na wstędze | S |
| P2-20 | „Osoby sprawdzone w KRS 0%” obok „Osoby z podmiotem 1” - dwie miary wyglądają sprzecznie | podpis „sprawdzone przez agenta KRS” albo liczyć osobę z potwierdzoną relacją jako sprawdzoną | na demo obie liczby nie przeczą sobie; podpis wyjaśnia miarę | S |
| P2-21 | „wyłączone” przy źródle z rekordami sprzed doby (TED 18 rekordów, 22.10 w demo) - nie wiadomo, czy dane są świeże | stan „wyłączone - dane do RRRR-MM-DD” | wiersz wyłączonego źródła z rekordami pokazuje datę, do której dane są | S |

## 5. Ryzyka prawne i etyczne

- **Biała lista MF:** wykaz podatników VAT z ustawy o VAT; odpowiedź zawiera też dane osób (reprezentanci, prokurenci, wspólnicy). Kod bierze tylko `nip` i `krs`, ale samo pobranie to przetwarzanie (art. 4 pkt 2 RODO) - wpisać do rejestru czynności z podstawą (art. 6 ust. 1 lit. e/f) i zakazem logowania treści odpowiedzi. Limit dzienny zapytań wyszukiwania (według mojej wiedzy 10 zapytań po najwyżej 30 podmiotów - do potwierdzenia w specyfikacji API MF): uruchomienie komendy ręcznie w dniu nocnego przebiegu może przekroczyć limit; ponowienie traktuje to jak błąd sieci. Celu „budowa bazy powiązań” nie konsultowano z Prawnikiem [DP].
- **Odpis pełny KRS:** zawiera historię organów (w api-krs dane osób częściowo zamaskowane). Nie zapisujemy osób - dobrze; ale zamknięcie relacji na podstawie maski (inicjał, długość) przy imienniku w tym samym organie mogłoby dać fałszywą datę - kod jest ostrożny (nie zmienia, gdy któraś zgodna maska jest aktywna), zostawić test na ten przypadek.
- **Imiennicy:** P0-12 - jedyna automatyczna furtka do przypisania pieniędzy spółki osobie publicznej; błąd = twierdzenie o konkretnej osobie z kwotami. Do czasu poprawki: wyłączyć automatyczne potwierdzenie `krs_register` z samym `grounded`.
- **Kwoty jako „wpływy”** (P0-11): wartość ogłoszenia ≠ zapłata; przy wielu wykonawcach przypisanie całości jednemu - ryzyko naruszenia dóbr osobistych podmiotu i sprostowania.
- **Kontekst osoby:** zdanie „osoba nie jest płatnikiem ani odbiorcą” jest, ale tylko w stopce; nagłówek „Wpływy do podmiotów osoby” na profilu polityka z sumą w milionach łatwo czytać jako zarzut. Etykieta kontekstu powinna stać przy liczbach.
- **Osoby fizyczne-wykonawcy:** bez nazw - dobrze; zbiorczy węzeł nie może pozwolić na odtworzenie osoby (np. jedna osoba fizyczna u małego zamawiającego z datą i kwotą). Przy n = 1 rozważyć pominięcie kwoty w widoku publicznym [DP].
- **Stan danych** (P0-13): strona wiarygodności, która zaniża zasób, podważa każdy inny licznik.

## 6. Czego nie zweryfikowałem

- **Niczego na produkcji:** brak dostępu (sesja w chmurze). Nie wiem, czy commity są wdrożone, czy migracja przeszła, czy harmonogram działa, czy api-krs i wl-api odpowiadają z serwera.
- Liczb pokrycia KRS, liczby podmiotów, stanu kolejki, liczby relacji `pending_review` - tylko dane demo (1 osoba, 1 podmiot).
- Czasów odpowiedzi nowych endpointów.
- Pozycji oznaczonych w inwentarzu jako zrobione przed tą rundą (P0-9, P0-10, P1-13, P1-15, P1-17, P1-18) - nie testowałem ich ani na produkcji, ani tu.
- Zgodności zrzutów z bieżącym kodem: na `dane-1440.png` brak odnośnika „Stan danych” w stopce, który jest w kodzie. Zrzuty 390 mają szerokość 326 px (wycinek elementu), więc nie mierzyłem marginesów strony ani `odstepy.js`.
- Limitów i regulaminu Białej listy MF - podaję z wiedzy, bez sprawdzenia u źródła (zasada: bez zapytań poza przeszłość.today).
- Struktury rzeczywistych ogłoszeń TED z wieloma częściami (czy parser zapisuje wartości części) - P0-11 opisuje to, co robi kod, nie to, jak często zdarza się w danych.
- Komponentów frontu w przeglądarce z klawiaturą i czytnikiem ekranu.

## 7. Kolejność na następną sesję

1. **P0-12** (furtka `grounded`) - przed włączeniem agenta i kolejki na produkcji; S.
2. **P0-11** (nazwy i sumy boksów, wartość wspólna wielu wykonawców) - przed pokazaniem przepływów publicznie; S.
3. **P1-21, P1-22** (kolejka KRS) - przed pierwszą nocą na produkcji, żeby nie spalić limitów api-krs i Białej listy; S.
4. Wdrożenie i **sondy S1-S8** z kryteriami z sekcji 2b; wynik do R3b (pomiar jak w R2b, odstęp 1 s).
5. **P0-13** (Stan danych dla wszystkich zbiorów) - M.
6. **P1-23, P1-24, P1-25** (deduplikacja, węzły po NIP, eksport przepływów).
7. Prawnik: Biała lista i odpis pełny w rejestrze czynności, węzeł osób fizycznych przy n = 1.
8. Dalej otwarte: P1-14/G3, P1-19, P1-9 (pomiar), P1-2, P1-6.

## Po rundzie (23.10, ta sama sesja, commit 16ecd2b)
Naprawione w kodzie zaraz po ocenie, z testami (do potwierdzenia sondą na produkcji):
- **P0-11** - ogłoszenie TED z kilkoma wykonawcami: kwota w tabeli z etykietą „kilku wykonawców”, poza sumami i wykresem (`amount_shared`).
- **P0-12** - agent KRS potwierdza automatycznie tylko ze źródłem, które sami pobraliśmy i które wymienia osobę i podmiot (`read`); sam adres z wyników Gemini nie wystarcza.
- **P1-21** - podmiot bez NIP w odpisie wraca do kolejki dopiero po okresie odświeżania (90 dni), nie co noc.
- **P1-22** - stan `no_krs` opisany neutralnie: „Biała lista nie podaje numeru KRS dla tego NIP”.
Otwarte bez zmian: P0-13, P1-23..P1-26, P2-16..P2-21.
