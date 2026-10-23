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

Wyniki pełnego zestawu i recenzji: sekcja 6 (dopisywana po przebiegu).
