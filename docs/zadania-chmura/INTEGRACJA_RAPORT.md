# Integracja 23.10 - raport (gałąź `cloud/integracja-2310`)

## 1. Scalenie
- `cloud/osoby-x`, `cloud/korektor`, `cloud/przeszlosc-rozwoj` scalone do `cloud/baza-2310` bez konfliktów w plikach.
- Migracje: `0170_krs_kolejka` przenumerowana na `0171_krs_kolejka` z zależnością od `0170_konta_oboz_inni_zespol`;
  `makemigrations --check`: bez zmian.
- Błędy styku gałęzi naprawione:
  - test Korektora zakładał brak `osoby_x.csv` (plik przyszedł z osoby-x); `monkeypatch` nie działał, bo ścieżka była
    domyślnym argumentem funkcji - teraz czytana przy wywołaniu;
  - Korektor dopasowywał konta z `osoby_x.csv` tylko po numerze profilu, a plik ma klucz osoby (`parliamentary:ep:23788`) -
    lista braków X byłaby zawsze pusta; teraz numer albo `import_key`.

## 2. Konflikty Strażnika w raporcie Korektora
`korektor.do_decyzji()` dokleja `account_warden.conflicts_for_report()` (ostatnia noc Strażnika), bez powtórzeń konta
z kolejki kandydatur; w mailu: konto, osoba, „Strażnik ostatniej nocy”, propozycja i link do źródła. Test w `test_korektor.py`.

## 3. Poprawki Śledczego (runda 3)
| # | Stan |
|---|---|
| P0-11 | Z gałęzi: kwota ogłoszenia z kilkoma wykonawcami poza sumami. Tu: boks „Wpływy” rozdzielony na „Wygrane zamówienia” (wartość z ogłoszeń TED) i „Dotacje i 1,5% podatku”; „Wydatki” -> „Udzielone zamówienia”; API `sums.in_contracts`, `sums.in_grants` |
| P0-12 | Z gałęzi: ścieżka KRS wymaga przeczytanego źródła. Tu: zamknięta druga furtka - „dwa niezależne źródła” liczą tylko przeczytane strony (wcześniej dwa adresy z wyników Gemini wystarczały); powód oczekiwania w `evidence_note` |
| P0-13 | Stan danych: nowa sekcja „Zbiory na profilach” (głosowania Sejmu, druki, oświadczenia, RCL, wpisy X, podmioty KRS, wzmianki) z licznikiem i datą z własnej tabeli; bez opisu braków pisze „Braki nieopisane.”; źródło z udanym pobraniem workera w ostatnich 48 h nie jest „wyłączone”, nawet gdy env procesu web mówi inaczej |
| P1-21 kolejka KRS | Z gałęzi (test `test_org_without_nip_does_not_return_every_night`) - sprawdzone |
| P1-22 „NIP bez KRS” | Z gałęzi: opis neutralny „Biała lista nie podaje numeru KRS dla tego NIP”, ponowienie po 90 dniach - sprawdzone |
| Ucinane opisy 390 | Stan danych: nazwy i braki zawijane (2 linie na komputerze, w całości na telefonie), bez treści tylko w `title` |
| Odmiana | „1 funkcja / 5 funkcji”, „z 1 osoby / z 5 osób”, „1 rekord / 2 rekordy”, „1 pozycja / 2 pozycje” (wspólne `plural()` z `ui.tsx`) |

Zrzuty 1440 i 390 (dane demo): boksy przepływów równe (112 px, 4 w rzędzie; 2 przy <1100 px; 1 na telefonie), bez
poziomego przewijania; na telefonie żaden tekst nie jest ucinany.

## 4. Katalog X (`scraper/catalog.py`)
Wikidata i strony gov.pl/sejm.gov.pl były z sesji niedostępne (proxy 403), więc sprawdzenie po `osoby_x.csv` (oficjalne linki),
migracjach 0052/0056, `account_warden_sources.py` i wyszukiwarce.
- `sjnowacka` (podpis „Szymon Hołownia”): żadne źródło nie wskazuje właściciela - **usunięte** z listy (lepiej brak niż zła dana).
  Konto Hołowni to najpewniej `@szymon_holownia` (Polskie Radio, TVP World), ale bez źródła oficjalnego - `[DP]`, nie dodane.
- Potwierdzone oficjalnym źródłem (osoby_x.csv): donaldtusk, RobertBiedron, sikorskiradek, kosiniakkamysz, KGawkowski,
  BeataSzydlo, MBlaszczak, jbrudzinski, dariusz_jonski, MichalSzczerba, joankasw, D_Tarczynski, ZandbergRAZEM,
  wlodekczarzasty, Kpelczynska; partie Platforma_org, pisorgpl.
- `[DP]` - repo wskazuje inne konta jako oficjalne: `Polska2050` (repo: `PL_2050`), `psl_pl` (`nowePSL`), `NowaLewica`
  (`__Lewica`), `konf_liberty` (`KONFEDERACJA_`). Źródła w repo też są słabe (PDF z 2021, „wymaga dodatkowego potwierdzenia”),
  więc nie podmieniałem - do decyzji z sesji, która ma dostęp do Wikidata/stron partii.
- `[DP]` bez źródła w repo: AndrzejDuda, morawieckim, KrzysztofBosak, SlawomirMentzen, AdamBodnar, domaski_andrzej (możliwa
  literówka w nazwie konta), IzabelaLeszczyna, beatakempa, franciszekst, K_Smiszek, PMatysiak_, Grzegorz_Braun, JkmMikke,
  konradberkowicz, JacekOzdoba, SebastianKaleta, partiarazem, BarbaraNowacka_ (jedno nieoficjalne źródło podaje `barbaraanowacka`).
- Uwaga: podpis z katalogu nie trafia do publikacji - scraper bierze nazwę z API X; podpis używa tylko Korektor (rozpoznanie kont partii).

## 5. Testy
`test_spina_v3.py::test_rejected_step_rules` - naprawione bez zmiany zachowania. Przyczyna: korpus materiałów zawiera datę
wpisu (np. `2026-10-23`), więc liczba „23” była „obecna w materiałach” i test padał 23. dnia miesiąca. Test używa teraz liczby,
która nie może być datą. Zauważona słabość (bez zmiany): każda liczba równa dniowi, miesiącowi lub rokowi wpisu przechodzi
przez fact-checkera łańcucha - do decyzji, czy wyłączyć daty z puli liczb.

## 6. Pełne testy
`news` + `scraper` (SQLite, 4 procesy): 3721 zaliczonych, 9 błędów w pierwszym przebiegu. 1 to `test_rejected_step_rules`
(naprawiony wyżej). Pozostałe 8 padają identycznie na `cloud/baza-2310` (sprawdzone osobno), nie są skutkiem integracji:
`test_editorial.py` (4), `test_profiles_topics.py` (2), `test_portal.py::test_editorial_slots_only_published`,
`test_social_panel.py::test_all_staff_and_admin_routes_deny_social` - testy starego panelu redakcji (`/api/editor/...`
zwraca 404, trasy nie ma w `urls`). Do osobnego zadania: usunąć te testy albo przywrócić trasy.
Drugi przebieg po poprawkach recenzji: 3728 zaliczonych, 11 błędów - te same 8 oraz `tests.py::test_drafts_domain_and_views`,
`tests.py::test_thread_positions_and_slug_collision`, `test_audyt_petli.py::test_thread_review_enqueue_runs_in_own_transaction`;
wszystkie 11 padają tak samo na `cloud/baza-2310` uruchomione osobno (te 3 w pierwszym przebiegu przeszły tylko przez
kolejność testów w procesach równoległych). Żaden błąd nie dotyczy plików zmienionych w integracji.

## 7. Niezależna recenzja kodu (agent recenzent) i poprawki
| # | Uwaga | Poprawka |
|---|---|---|
| 1 | Korektor podmieniał gościa na osobę z tytułu („Bosak: Tusk musi odejść” -> Tusk) | nazwisko gościa obecne w tytule zostaje; nadpisanie tylko pustego pola albo osoby z rejestru urzędów; test |
| 2 | Fałszywe błędy urzędu: „Andrzej Duda, prezydent Karol Nawrocki”, „Hołownia, marszałek Sejmu Czarzasty”, „premier w latach 2017-2023”, „Piotr Duda, prezydent związku” | wzorzec „osoba, urząd” nie trafia, gdy po urzędzie jest inna osoba, okres albo inna instytucja; samo nazwisko z innym imieniem to imiennik; testy; zalecenie `KOREKTOR_NAPRAW=false` na 3 dni |
| 3 | Ponowne sprawdzenie agenta KRS bez przeczytanego źródła (np. błąd sieci) zdejmowało potwierdzoną relację | potwierdzona relacja zostaje bez zmian; test |
| 4 | SSRF: pobieranie stron źródeł z adresów od modelu, z przekierowaniami | tylko http(s) do publicznych adresów IP, każde przekierowanie sprawdzane; test |
| 5 | Profil osoby: boksy „Wygrane zamówienia” i „Dotacje” zawsze puste | sumy liczone po podmiotach osoby; test |
| 6 | Odpis pełny KRS mógł zamienić potwierdzoną relację na odrzuconą przez zespół | odrzucony „bliźniak” blokuje zmianę, niepotwierdzony ustępuje; test |
| 7 | Wstrzymany przez Korektora przekaz dnia tracił treść przy nieudanym ponownym wygenerowaniu | treść zostaje w wierszu `failed` (do decyzji człowieka) |
| 8 | Raport Korektora liczył konta o średniej pewności i nieaktualne | ten sam filtr co import: `wysoka` + `aktualne` |
| 9 | `/glosowania/?rodzaj=pe` czytało pełne dane wszystkich głosowań PE | najpierw tylko numer i wynik, pełne rekordy dla jednej strony; test |
