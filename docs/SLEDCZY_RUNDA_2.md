# Śledczy - runda 2: weryfikacja P0 (11.10.2026, ok. 03:00)

Rola: docs/SLEDCZY_ROLA.md. Tylko odczyt https://przeszlosc.today (publiczne API, najwyżej 1 zapytanie/s, niewidoczny Playwright). Zrzuty 1440 i 390 (ekran i cała strona): `C:\Users\User\Desktop\projekty\przeszlosc-gotowe\sledczy-runda-2\` (osoba-obajtek, osoba-tusk, spolka-orlen, przeplyw-obajtek, temat-cpk, temat-kolodziejczak). Ocena modelu AI w roli, nie opinia prawdziwego dziennikarza.

## 1. Streszczenie

1. **Poprawki P0 nie są na produkcji.** Commity 109be9e, cb4bc7f, 8e5b49b, 4bb9c8f, 6e5c7c3 (11.10, 02:17-02:24) leżą lokalnie na `codex/mvp-public-frontend`, gałąź jest „ahead 6” względem `origin` - nie wypchnięta, więc nie wdrożona.
2. **Dowód wdrożeniowy (sonda):** nowy kod odrzuca `?cala_historia=5` błędem 400 (`options()` przyjmuje tylko 0/1). Produkcja zwraca 200 i identyczny graf (134 525 B) - stary kod ignoruje parametr.
3. Brak nowych pól w odpowiedziach: `amount_suspect`, `suspect_count` (spółka), `outside_tenure` (drzewo), `confidence` (wzmianki). Spółka Orlen wygenerowana 02:48 czasu PL, już po commitach - nadal stary kod.
4. **Wynik P0: 0 z 5 zaliczonych na produkcji.** Kod i testy wyglądają na zgodne z kryteriami dla P0-1, P0-2, P0-3; P0-4 i P0-5 mają luki także w samym kodzie (niżej).
5. Średnia bez zmian: **4,4 / 10**. Brak regresji (nic się nie zmieniło), ale też brak postępu.
6. Czas API na zimno nadal 6,6-19,5 s (osoba, temat); z pamięci podręcznej 0,2-0,6 s.
7. Wzmianki Tusk i Obajtek nadal 0. Przyczyna nie leży w duplikacie osoby: wyszukiwarka zwraca jeden rekord każdego. Tusk: nazwisko 4-literowe odpada na `MIN_SURNAME_LENGTH = 5` (stary kod). Obajtek: okno 2000 najnowszych artykułów i brak odmiany „Obajtka” (stary kod).
8. Nowe ryzyka w kodzie P0-4 (do sprawdzenia po wdrożeniu): „Donalda Tuska” nie pasuje (brak odmiany imienia „Donald”), a samo nazwisko „Tusk” jest za krótkie (próg 6); filtr „wielka litera przed nazwiskiem = inna osoba” odrzuca „Premier Tusk”, „Afera Obajtka” i każdy tytuł wersalikami (YouTube).
9. P0-5 w kodzie: przycisk jest, ale brak publicznej strony „Poprawki” wymaganej w kryterium.
10. Polecenie: wdrożyć paczkę (właściciel), potem runda 2b - powtórzę te same sondy w 15 minut.

## 2. Wyniki P0 (kryteria odbioru z rundy 1)

| # | Kryterium | Produkcja | Dowód | Kod (lokalnie) |
|---|---|---|---|---|
| P0-1 | `/spolka/0000028860/` suma < 10 mld zł; TED 157377-2026 z `amount_suspect: true`, poza `sums` | **NIE** | `GET /api/przeszlosc/spolka/0000028860/` (3,6 s): `contracts.sums = 1 091 072 300 463,71 PLN`, klucze `contracts`: `count, sums, results` (brak `suspect_count`); rekord `ted:99303` (TED 157377-2026) `amount: 1086150000000` bez flagi. UI: „1091,07 mld zł suma z ogłoszeń” (`spolka-orlen-1440.png`, `-390.png`). Drzewo spółki i osoby: największy węzeł nadal 1 086 150 000 000 | spełnia (próg 5 mld + 100× mediany od 1 mld, test jednostkowy). Uwaga: w drzewie (`przeszlosc_przeplyw.finance`) tylko próg bezwzględny - 1,01 mld zł Inowrocław zostanie w drzewie z kwotą, a w spółce może wypaść z sumy (niespójność, P1-11) |
| P0-2 | `/przeplyw/osoba:615-daniel-obajtek/` domyślnie 0 zamówień Orlenu z 2025-2026; z przełącznikiem są i mają `outside_tenure: true` | **NIE** | domyślnie 58 węzłów `contract` z lat 2025-2026, 0 węzłów z `outside_tenure`; `?cala_historia=1` i `?cala_historia=5` dają ten sam graf (`generated_at 2026-10-11T00:04:24Z`, sprzed commitów). UI: „Zamówienia 116” (`przeplyw-obajtek-1440.png`) | spełnia (`in_tenure`, `whole_history`, test) |
| P0-3 | `/temat/?q=Kołodziejczak` tylko podmioty związane z tematem (Agrounia tak, Olimpia Jawor nie) | **NIE** | `GET /api/przeszlosc/temat/?q=Kołodziejczak` (6,6 s): 25 węzłów `org:`, m.in. KLUB Sportowy „Olimpia” w Jaworze, Międzyleski Szpital Specjalistyczny, Ośrodek Monitorowania Antypolonizmu, Stocznia Gdynia, KUKE. Temat CPK: 5 podmiotów, w tym Fundacja Uniwersytetu Warszawskiego i „Ławeczka” | spełnia (tylko osoba centralna albo podmiot z nazwą w temacie) |
| P0-4 | Tusk ≥ 100 wzmianek z 30 dni, każda ze `snippet`; licznik „artykułów” = liczba wzmianek | **NIE** | `/api/przeszlosc/osoba/326-donald-tusk/`: `mentions.results: []`; Obajtek `[]`; Kołodziejczak ma wzmianki, ale bez pola `confidence`. Profil: „0 artykułów” u Tuska i Obajtka (`osoba-tusk-1440.png`, `osoba-obajtek-1440.png`) | **częściowo**: brak pola `snippet` (jest tylko `matched_in`), licznik „artykułów” nie zmieniony, ryzyko niskiej trafności dla Tuska (pkt 8 streszczenia) |
| P0-5 | przycisk w 1440 i 390 na 3 typach stron, zgłoszenie z id węzła; strona „Poprawki” istnieje | **NIE** | Playwright: 0 przycisków z tekstem „sprostowanie” na profilu, spółce i drzewie w 1440 i 390 (selektor `.px-fix__btn` + tekst) | **częściowo**: `Sprostowanie.tsx` w profilu, spółce i panelu węzła, `data-record` z id; brak strony „Poprawki” (publiczny rejestr) |

## 3. Czas odpowiedzi API (11.10, ok. 02:58-03:05, pojedyncze próby)

| Zapytanie | Pierwsza próba | Powtórka | Uwagi |
|---|---|---|---|
| `/osoba/326-donald-tusk/` | 7,9 s | 0,5 s | cache |
| `/osoba/96-michal-kolodziejczak/` | 19,5 s | 0,17 s | |
| `/osoba/615-daniel-obajtek/` | 0,56 s | - | już w cache (wcześniejsza próba przerwana awarią sieci po 70 s) |
| `/temat/?q=CPK` | 18,0 s | 0,26 s | |
| `/temat/?q=Kołodziejczak` | 6,6 s | - | |
| `/temat/?q=Turów` | 3,6 s | - | nadal 0 głosowań (`votes: []`) |
| `/temat/?q=xqzw7` (pusty wynik) | 7,5 s | - | pusty wynik dalej kosztuje sekundy |
| `/spolka/0000028860/` | 3,6 s | - | |
| `/przeplyw/...` | 0,3-0,6 s | - | cache 24 h |
| Strony (Playwright, DOM + sieć) | 1,0-4,5 s | - | temat CPK 4,5 s |

Wniosek: kryterium P1-9 (p95 < 2 s na zimno) nadal niespełnione; ciepła pamięć podręczna działa dobrze.

## 4. Regresje

Brak regresji - produkcja jest w stanie z rundy 1. Potwierdzone ponownie:
- Orlen: 1091,07 mld zł; Obajtek: drzewo z 58 zamówieniami spoza kadencji; nazwisko „Daniel OBAJTEK” wersalikami (P2-6).
- Tusk: tylko „Poseł na Sejm RP” (5 kadencji), bez premiera (P1-2).
- Kołodziejczak: wzmianki działają (Polsat News, RMF24 z 10.10), graf tematu z obcymi podmiotami (P0-3).
- Temat CPK i Kołodziejczak: pierwszy ekran 1440 i 390 to pasek YouTube z tytułami „Pupil Tuska skompromitowany!”, „NARKO-AFERĘ” (P1-8).
- 390 px: brak przewijania poziomego (scrollWidth 390 na 6 stronach), ale „Narracja” w nagłówku i podpis „osoba publiczna z funkcj…” w siatce liczb ucięte (`spolka-orlen-390.png`, P2-1).
- Przycisk sprostowania na 390: nie istnieje (P0-5).

## 5. Oceny 0-10 (zmiana względem rundy 1)

| # | Obszar | R1 | R2 | Zmiana | Uzasadnienie |
|---|---|---|---|---|---|
| 1 | Szybkość | 5 | 5 | 0 | zimno 6,6-19,5 s, ciepło 0,2-0,6 s |
| 2 | Kompletność | 3 | 3 | 0 | bez zmian (Turów 0, brak funkcji rządowych, wzmianki 0 u Tuska i Obajtka) |
| 3 | Pochodzenie i dowód | 5 | 5 | 0 | bez zmian; nowe wzmianki nadal bez `snippet` w kodzie |
| 4 | Powiązania i przepływy | 4 | 4 | 0 | filtr kadencji i walidacja kwot tylko lokalnie |
| 5 | Zmiany w czasie | 3 | 3 | 0 | bez zmian |
| 6 | Eksport i cytowanie | 5 | 5 | 0 | bez zmian |
| 7 | Zaufanie, neutralność, język | 5 | 5 | 0 | graf tematu dalej zestawia sprawę z podmiotami osób trzecich |
| 8 | Prawo i etyka | 5 | 5 | 0 | ryzyko zniesławienia (suma, kadencja) nadal na produkcji; brak ścieżki sprostowania |
| 9 | Użyteczność i dostępność | 5 | 5 | 0 | bez zmian |
| 10 | Przewaga nad konkurencją | 4 | 4 | 0 | bez zmian |
| | **Średnia** | **4,4** | **4,4** | **0** | |

Prognoza po wdrożeniu paczki (do potwierdzenia w rundzie 2b): obszary 4, 7, 8 o +1 do +2, średnia ok. 4,9.

## 6. Backlog - nowe pozycje (P0-1..P0-5 pozostają otwarte)

### P0
| # | Problem | Dowód | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|---|
| P0-6 | Poprawki P0 nie trafiły na produkcję | `git status`: ahead 6 wobec `origin/codex/mvp-public-frontend`; sonda `?cala_historia=5` = 200 zamiast 400 | wypchnąć gałąź, wdrożyć (komenda dla właściciela), unieważnić cache `przeszlosc:przeplyw` (24 h) i `media-mentions` | `/api/przeszlosc/przeplyw/osoba:615-daniel-obajtek/?cala_historia=5` zwraca 400; `/spolka/0000028860/` ma `contracts.suspect_count ≥ 1` | S |
| P0-7 | Wzmianki Tuska po wdrożeniu najpewniej nadal skąpe | kod 4bb9c8f: brak odmiany „Donald” w `GIVEN_NAMES`, „Tusk” (4 litery) < `MIN_SURNAME_ONLY_LENGTH = 6`; `surname_only_hit` odrzuca nazwisko po każdym wyrazie z wielkiej litery („Premier Tusk”, „Afera Obajtka”, tytuły wersalikami) | dodać odmianę imion z rejestru (co najmniej Donald, Mateusz, Jarosław, Szymon, Władysław, Krzysztof), wyjątki dla funkcji („premier”, „minister”, „prezes”, „poseł”, „afera”) i dla tytułów wersalikami; dla krótkich nazwisk z jednym nosicielem w rejestrze dopuścić samo nazwisko przy pewności „medium” | test: „Premier Tusk w Brukseli”, „PUPIL TUSKA”, „Donalda Tuska” → trafienie; produkcja: Tusk ≥ 100 wzmianek z 30 dni | S |
| P0-8 | Kryterium P0-4 i P0-5 niepełne w kodzie | brak `snippet` przy wzmiance, licznik „0 artykułów” nie liczy wzmianek; brak strony „Poprawki” | dodać `snippet` (fragment 160 znaków wokół dopasowania), licznik z `mentions`; strona `/przeszlosc/poprawki` z listą przyjętych sprostowań (bez danych zgłaszającego) | każda wzmianka ma `snippet` zawierający nazwisko; licznik = `len(mentions.results)`; `/przeszlosc/poprawki` 200 | M |

### P1
| # | Problem | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|
| P1-10 | Wydajność nowych wzmianek: `icontains` na tytule i opisie 525 tys. artykułów, ok. 10 warunków OR, bez indeksu trigramowego | indeks `pg_trgm` (GIN) na `title` i `description` albo wstępnie liczony indeks wzmianek w tle | profil Tuska na zimno < 3 s po wdrożeniu (5 prób) | M |
| P1-11 | Niespójna walidacja kwot: spółka używa progu względnego (100× mediany), drzewo tylko bezwzględnego 5 mld | jedna funkcja `mark_suspect` dla spółki i drzewa | rekord TED 728541-2025 (1,01 mld zł) ma tę samą flagę w `/spolka/` i `/przeplyw/` | S |
| P1-12 | Pusty wynik tematu trwa 7,5 s | wczesne wyjście, gdy żadne źródło nie ma trafień (licznik przed budową grafu) | `/temat/?q=xqzw7` < 1 s na zimno | S |

### P2
| # | Problem | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|
| P2-9 | Weryfikacja po wdrożeniu zależy od ręcznego sprawdzania | endpoint `/api/przeszlosc/wersja/` z hashem commita i datą wdrożenia | odpowiedź zawiera hash równy `git rev-parse HEAD` wdrożonej gałęzi | S |

## 7. Co jest już świetne
- Poprawki P0-1..P0-3 w kodzie są małe, czytelne, z testami i komentarzami odsyłającymi do kryteriów; flaga zamiast usunięcia rekordu (zachowany dowód).
- Pamięć podręczna działa: powtórne zapytania 0,2-0,6 s.
- Brak przewijania poziomego na 390 na wszystkich 6 stronach.

## 8. Ryzyka prawne i etyczne
- Do czasu wdrożenia na produkcji nadal są: suma 1,09 bln zł przy Orlenie i Obajtku oraz zamówienia spoza kadencji w drzewie osoby (ryzyko zniesławienia przez zrzut ekranu).
- Graf „Kołodziejczak” (sprawa z zarzutami) dalej zestawia ją ze szpitalami, klubem sportowym i fundacjami innych polityków.
- Po wdrożeniu P0-4: dopasowanie po samym nazwisku z pewnością „medium” musi być widoczne w interfejsie (etykieta), inaczej czytelnik uzna automat za ustalenie redakcyjne.

## 9. Czego nie zweryfikowałem
- Działania poprawek na produkcji (nie są wdrożone) - oceniłem je tylko z kodu i opisu testów, testów nie uruchamiałem.
- Czy w rejestrze są zarchiwizowane duplikaty Tuska lub Obajtka (API wyszukiwarki pokazuje tylko aktywne; zwraca po jednym rekordzie). Funkcja `mentions_data` liczy duplikaty także wśród zarchiwizowanych - jeśli taki istnieje, wzmianki będą 0 także po wdrożeniu. Do sprawdzenia w bazie: `PublicFigure.objects.filter(canonical_name__iexact='Donald Tusk', merged_into__isnull=True)`.
- Wysyłki formularza sprostowania (zakaz wysyłania).
- Mapy funkcji do dodania - w tej rundzie weryfikacyjnej bez nowych pozycji (pozostaje docs/SLEDCZY_FUNKCJE_1.md).
