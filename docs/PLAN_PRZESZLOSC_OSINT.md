# przeszłość.today — plan narzędzia OSINT (stan na 5 listopada 2026, po scaleniu gałęzi)

Ten dokument **zastępuje** opis przeszlosc.today jako „alternatywnego brandu" z `PLAN_AKTUALNY.md`,
`project.md`, `roadmap.md` i `docs/CONTEXT_ARCHIVE_PRODUCT.md`. Powstał z przeglądu żywej strony
(https://przeszlosc.today, podstrony `/przeszlosc`, `/przeszlosc/funkcje`, `/przeszlosc/jak-to-dziala`)
oraz kodu w tym repozytorium. Operator serwisu: iapply sp. z o.o., Poznań (kontakt@iapply.pl).

## Czym jest dziś przeszlosc.today

Narzędzie OSINT dla dziennikarzy, badaczy i redakcji: wpisujesz **temat, osobę albo numer KRS** i dostajesz
„kto, co i kiedy" — oś czasu, drzewo powiązań, głosowania Sejmu, funkcje w KRS, ślad pieniędzy publicznych.
Tylko osoby i podmioty publiczne. Każde powiązanie ma źródło i ślad do oryginału. Powiązania budowane są z
identyfikatorów (ID Sejmu, KRS, NIP, REGON), nigdy z samego podobieństwa nazw; wzmianki w artykułach są
oznaczone jako „automatyczne". Diagnozy Dr. Spina (spin.clinic) są domyślnie ukryte (przełącznik
„Wpływ na narrację").

Skala bazy (ze strony głównej, 5.11.2026): 775 osób publicznych, 800 spółek i fundacji z KRS,
2 511 739 dokumentów Sejmu, 22 712 wpisów polityków, 553 938 artykułów z mediów.

## Funkcje widoczne na żywej stronie

| Funkcja | Adres / miejsce |
|---|---|
| Kto, co i kiedy w temacie (oś czasu) | `/przeszlosc?q=TEMAT` |
| Drzewo powiązań (osoba → wpis → diagnoza / KRS) | wynik tematu |
| Głosowania Sejmu w temacie, wynik klubów i posłów | wynik tematu |
| Profil osoby publicznej (X, interpelacje, wystąpienia, głosowania, artykuły) | `/przeszlosc?tryb=osoba` |
| Odstępstwa od klubu (definicje i progi jawne) | `/przeszlosc/odstepstwa` |
| Wspólne mianowniki (z kim w tematach / spółkach / głosowaniach) | dół profilu |
| Funkcje w KRS (zarządy, rady, daty od–do) | profil |
| Ślad pieniędzy z UE (Kohesio, FTS) | wynik tematu |
| Drzewo przepływu pieniędzy (KRS + TED + BZP + UE, łączenie tylko po NIP/KRS/REGON) | profil |
| Alerty e-mail (codziennie 7:00) | `/przeszlosc/alerty` |
| Eksport CSV i JSON (z linkiem do oryginału, kolumna `data_pobrania`) | profil, temat |
| Gotowy przypis do cytowania | przy wpisie |
| Kopia źródła w Internet Archive + ostrzeżenie o zmianie tekstu | panel wpisu |
| Wystąpienia z nagrań Sejmu (sekunda nagrania) | profil |
| Europosłowie z Polski (głosowania PE, deklaracje, lobbyści) | profil |
| Kilometrówki i biura posłów | profil |
| Kanał RSS tematu | okno „Obserwuj" |
| Tematy dnia (automat, bez AI) | pod wyszukiwarką |
| Zgłoszenie błędu, rejestr poprawek, informacja RODO art. 14 + sprzeciw | `/przeszlosc/poprawki` |
| Dla redakcji: pilotaż, wspólne teczki, API (zapowiedź) | `/przeszlosc/pilot`, `/przeszlosc/funkcje` |

## Gdzie jest kod i co zostało scalone (ustalone 5.11.2026)

Kod przeszlosc.today jest **wspólny ze spin.clinic** (jedna aplikacja, jeden backend, jedna baza), w tym repozytorium.
Strona to trasy `frontend-spin/app/przeszlosc/*`; `frontend-przeszlosc/` to tylko wariant marki. Backend:
`backend/news/przeszlosc*.py`, `drzewo_pieniedzy.py`, `pracownia_osint.py`, `krs*.py`; źródła: `backend/scraper/public_records.py`,
`nowe_zrodla.py`, `access_gate.py`.

`main` jest nieaktualny (stan z września). Praca z października leżała na gałęziach, które odeszły od wspólnego punktu `b1f33e03`:

- `cloud/integracja-2310` (23.10; 33 własne commity): Stan danych (`/przeszlosc/dane`), przepływy pieniędzy v2, pokrycie KRS (nocna kolejka), Korektor, osoby z X, poprawki po recenzji.
- `codex/mvp-public-frontend` (31.10; 6 własnych commitów): Rada (Nemotron/NIM), dziennik głosów, załączniki uwag „zbudujmi" (głównie spin.clinic).

Obie gałęzie zostały scalone do gałęzi roboczej `claude/upbeat-noether-7k08ac` (PR #29). Scalenie nie dało konfliktów w kodzie;
konflikt w `CLAUDE.md` rozwiązano zachowując zasady właściciela i dopisując sekcję zasad nadrzędnych. Powstała migracja
scalająca `0172_merge_0170_clientnote_file_0171_krs_kolejka` (pusta; obie gałęzie dodały równoległe migracje 0170).
Gałęzie źródłowe pozostały nietknięte. Nie sprawdzono, który wariant działa dziś na produkcji (VPS, `/srv/spin-clinic`).

## Lista dalszych podłączeń (źródło: `docs/PRZESZLOSC_ZRODLA_DANYCH.md`, 8.10.2026)

Pełna tabela 25+ źródeł z licencjami, ryzykiem, kluczami łączenia i priorytetem jest w tym dokumencie; poniżej skrót kolejki
(oznaczenia z katalogu: [P] pewne, [DP] do potwierdzenia). Każde nowe źródło przechodzi przez Prawnika (`pracownia_osint.py: LEGAL`)
i bramkę `scraper/access_gate.py`.

**Już zbierane:** KRS (API MS), TED, FTS, Kohesio, Sejm, lobbing (MSWiA, Sejm), PKW, oświadczenia Sejmu (indeks, bez treści), Wikidata, rejestr przejrzystości UE.
**Zbierane, ale wyłączone:** BZP / e-Zamówienia (`bzp_backfill.py`, czeka na instrukcję UZP).

**Kolejność z katalogu (6 miesięcy):**
1. Miesiąc 1, identyfikatory i NIP-y: REGON (GUS BIR), Biała lista VAT (MF), SUDOP (pomoc publiczna UOKiK); włączenie BZP.
2. Miesiąc 2, nieruchomości: Rejestr Cen Nieruchomości, działki (ULDK/KIEG), numery KW podawane przez użytkownika.
3. Miesiąc 3: lista beneficjentów funduszy 2021–2027 i KPO.
4. Miesiąc 4: orzeczenia sądów (Portal Orzeczeń, SAOS, CBOSA, KIO) i KRZ (tylko podmioty).
5. Miesiąc 5: CRBR (jawny do 31.12.2026, potem ograniczony; wniosek na 2027) i sankcje.
6. Miesiąc 6: sygnały i API dla redakcji.

**Czekają na decyzje zewnętrzne:** Centralny Rejestr Umów (wniosek do MF z 5.10, brak odpowiedzi w dokumentach), licencje (MS, MC, GUGiK; szkice na komputerze właściciela w `Desktop\projekty\spin-clinic-maile\licencje\`, UODO wstrzymane).
**Bez legalnej drogi hurtowej:** księgi wieczyste (model „KW przynosi użytkownik", `docs/PRZESZLOSC_KW_LICENCJA.md`, wymaga prawnika).

**Luki ogłoszone na żywej stronie (`/przeszlosc/jak-to-dziala`, stan 13.10)** i status „do potwierdzenia" dla: BZP, Parlamentu Europejskiego (okres),
lobbingu, wpisów X, mediów, kilometrówek i biur posłów oraz miejsc widoczności danych PKW i reklam Meta. Brakuje też publicznej informacji
o faktycznym harmonogramie odświeżania źródeł na produkcji. Strona **Stan danych** z integracji 23.10 częściowo to adresuje; należy zweryfikować,
czy pokrywa wszystkie źródła.

**Formalne:** klauzula RODO (art. 14) to wersja robocza do akceptacji prawnika; procedura sprzeciwu i terminy odpowiedzi „do potwierdzenia";
zapowiedziane dla zespołów: wspólne teczki tematów, eksport z przypisami, API (niewdrożone).

## OSINT-01: wynik weryfikacji Stanu danych (5.11.2026)

**Sprawdzone w kodzie (`backend/news/przeszlosc_stan.py`, `frontend-spin/app/przeszlosc/dane/`):**
- Stan danych pokrywa **wszystkie 22 zbieracze** z `scraper/public_records.py` (m.in. lobbing MSWiA i Sejmu, PKW, Parlament Europejski: HowTheyVote i Integrity Watch, Wikidata, kilometrówki, rejestr UE, reklamy Meta, TED, FTS, Kohesio), **BZP**, NIW, wykaz OPP oraz 7 zbiorów (głosowania, druki, oświadczenia, RCL, wpisy X, podmioty KRS, wzmianki w mediach) i pokrycie KRS.
- Dla każdego źródła pokazuje: włączone / wyłączone, liczbę rekordów, datę ostatniego udanego pobrania, ostatni błąd, znane braki; zaległość po 48 h (zbiory mają własne progi). To dokładnie ta informacja, której strona „Jak to działa" nie ma („faktyczny harmonogram na produkcji: brak w naszych danych").
- Strona jest podlinkowana w stopce (`ui.tsx`). Testy backendu tego modułu przechodzą w pełnym przebiegu (5.11).

**Sprawdzone na żywej produkcji (5.11.2026):**
- Przed wdrożeniem: `https://przeszlosc.today/przeszlosc/dane` i `https://przeszlosc.today/api/przeszlosc/stan-danych/` zwracały 404. Po wdrożeniu przez właściciela (5.11, wieczorem; migracje 0170, 0171, 0172 zastosowane) obie działają.
- Wniosek: **dotychczas wdrożona wersja nie zawierała Stanu danych**, czyli jest sprzed integracji z 23.10 (zgodne z tym, że `codex/mvp-public-frontend` też go nie ma). Strona Next.js zwraca 404, więc nie jest to efekt flagi `PRZESZLOSC_ENABLED` po stronie API.

**Prawdziwy stan produkcji po wdrożeniu (odczyt z `/api/przeszlosc/stan-danych/`, 5.11.2026 21:31 UTC):** 15 źródeł OK, 14 zaległych, 2 puste, 1 wyłączone (przed poprawką progu, patrz niżej).

- **Fałszywe alarmy (naprawione w kodzie, wymaga kolejnego wdrożenia):** strona oznaczała wszystko jako „zaległe" po sztywnych 48 h, mimo że część źródeł odświeża się rzadziej. Dotyczyło: PKW, lobbing MSWiA, rejestr przejrzystości UE, Wikidata, Integrity Watch (interwał tygodniowy, ostatnie pobranie 3.11) i kilometrówek (miesięczny, 7.10). Teraz próg to 2 x własny interwał źródła (nie mniej niż 48 h), a wiersz API ma pola `refresh_hours` i `stale_after_hours`. Szacunek po poprawce na tych samych danych: 7 zaległych zamiast 14.
- **Realne problemy do zbadania w logach serwera (nie zgadywać przyczyn):**
  1. `krs_changes`: zaległe od 8.10, ostatni błąd `JSONDecodeError` (api-krs zwraca nie-JSON?).
  2. `assets` (indeks oświadczeń majątkowych): 0 rekordów, błąd `request_limit_or_host_interval`, ostatnia próba 5.10; zbiór „Oświadczenia majątkowe posłów" pusty.
  3. `fts` (budżet UE): włączone, ale nigdy nie pobrane, 0 rekordów.
  4. `kohesio`: pobrane 1.11, ale 0 rekordów.
  5. `interpellations` (ostatnie 22.10) i `questions` (10.10): interwał 6 h, a nie odświeżają się od tygodni.
  6. `niw` i `mf_opp`: ostatnie pobranie 13.10; po tym wdrożeniu mają harmonogram tygodniowy (beat `przeszlosc-niw-weekly`, `przeszlosc-opp-weekly`), więc po najbliższej niedzieli powinny się odświeżyć; zweryfikować.
  7. `bzp`: włączone, tylko 9 rekordów, ostatnie pobranie 6.10.
- **Zgodne z oczekiwaniami:** `meta_ads` wyłączone (archiwum kończy się 5.10.2025); ok: głosowania, druki, RCL, wpisy X (22 784), media (554 073), TED (142 671), Sejm (wypowiedzi, komisje, procesy), HowTheyVote, wideo, lobbing Sejmu.
- Pokrycie KRS: 775 z 775 osób sprawdzonych, 507 z podmiotem, 1043 potwierdzone relacje, 674 z 803 podmiotów z NIP, kolejka pusta.

**Po wdrożeniu poprawek (5.11.2026, 23:22 UTC; commit `1fce169` na serwerze, zweryfikowane z zewnątrz):** 22 źródła OK, 7 zaległych, 2 puste, 1 wyłączone
(przed poprawką progu: 15 / 14 / 2 / 1; wynik zgodny z prognozą). Zaległe po poprawce: `interpellations` (stoi od 22.10, interwał 6 h), `questions` (od 10.10), `niw` i `mf_opp` (od 13.10;
próg 336 h), `krs_changes` (od 8.10, `last_error` już pusty), `bzp` (9 rekordów od 6.10), `assets` (próg 336 h). Puste: `fts` (nigdy nie pobrane) i zbiór „Oświadczenia majątkowe".
- `assets`: ostatni błąd to **`bot_protection`**. Kolektor respektuje zabezpieczenie antybotowe i go nie obchodzi (zasada portalu). Oświadczeń majątkowych nie zbierzemy automatycznie z tego hosta;
  potrzebna oficjalna droga (pismo/API), nie poprawka kodu.
- `kohesio`: status „OK", ale 0 rekordów. To wada logiki statusu (pobranie bez błędu = OK nawet przy zerze rekordów); do zmiany: włączone źródło z zerem rekordów = „puste".
- Odstępstwa: backend ucina listę klubu do 30 pozycji (`CLUB_REBELLIONS`), np. „pokazujemy 30 z 187"; pełna lista wymaga eksportu (do zrobienia).

**Diagnoza źródeł z polecenia na serwerze (5.11.2026, ~23:30 UTC; `PublicCollectionState` + kod `scraper/public_records.py`, `scraper/nowe_zrodla.py`):**
- `assets` (oświadczenia majątkowe): status `blocked_access_review`, błąd `bot_protection`; kolektor celowo wstrzymuje się na `BOT_WALL_PAUSE_HOURS` (domyślnie 24 h) i nie obchodzi zabezpieczenia. Wymaga oficjalnej drogi dostępu (pismo/API); decyzja właściciela, czy wyłączyć źródło, żeby nie odpytywać strony codziennie.
- `kohesio`: cykl zakończony poprawnie 1.11 (75 zapytań, 0 rekordów). **Przyczyna po stronie źródła:** zbiór Komisji ma 102 721 projektów z Polski i **0 z nazwą beneficjenta** (zweryfikowane zapytaniem do `cohesiondata.ec.europa.eu`, 5.11); parser zgodnie z zasadą „tylko podmioty" odrzuca wiersze bez nazwy. Beneficjentów trzeba brać z innego źródła (lista projektów 2014-2020 i 2021-2027, katalog poz. 17). Zmiana w kodzie: włączone źródło z 0 rekordów ma status „puste" (nie „OK"), a „Stan danych" i „Jak to działa" mówią o tym wprost.
- `fts`, `interpellations`, `questions`, `krs_changes`: status `deferred`, `last_error` pusty, uruchamiane co minutę bez zapytań. W kodzie `deferred` bez błędu oznacza: są zadania oczekujące, ale **wszystkie w odroczeniu po wcześniejszych błędach** (`retry_at` rosnące do 24 h). Prawdziwe powody są zapisane **przy zadaniach** (`PublicCollectionJob.last_error`, `failures`), nie w stanie źródła. Do odczytania kolejnym poleceniem (tylko odczyt). Hipoteza robocza (niepotwierdzona): jedno trwale błędne zadanie na froncie kolejki blokuje cały cykl, bo kolejne strony powstają dopiero po sukcesie poprzedniej.

**Przyczyny z błędów zadań (`PublicCollectionJob`, serwer 5.11 ~23:50 UTC):**
- `interpellations` (18 błędów) i `questions` (29): `HTTPError` na `.../interpellations?sort_by=num&modifiedSince=2026-09-27`. **Przyczyna potwierdzona na `api.sejm.gov.pl`:** `modifiedSince` przyjmuje tylko datę z godziną (`2026-09-27T00:00:00` daje 200), sama data daje 404. Naprawione w `scraper/public_records.py` (jak już robi to źródło `processes`), test dodany. **Uwaga wdrożeniowa:** zadanie z błędnym adresem jest zapisane w bazie i po wdrożeniu nadal będzie ponawiane; trzeba jednorazowo usunąć oczekujące zadania tych dwóch źródeł (kolejny cykl założy je od nowa z poprawnym adresem; rekordy są wstawiane idempotentnie).
- `krs_changes`: 82 zadania `krs_extract`, każde 33 błędy `JSONDecodeError`. **Przyczyna potwierdzona poleceniem z serwera (6.11):** API KRS zwraca dla tych numerów **HTTP 204 bez treści** przy `rejestr=P` (Orlen: 200, JSON). 204 znaczy „podmiotu nie ma w tym rejestrze" (P: przedsiębiorcy, S: stowarzyszenia i fundacje); zbieracz czytał JSON z pustej odpowiedzi. Naprawione w `scraper/public_records.py`: pusta odpowiedź = próba drugiego rejestru, a gdy i on pusty, zadanie kończy się bez błędu; test dodany. Nieobecne w którymkolwiek rejestrze podmioty są pomijane.
- `fts`: 3 zadania `fts_year`, 33 błędy `fts_header_missing`. **Przyczyna potwierdzona na nagłówku pliku (6.11):** kolumna kraju nazywa się „Beneficiary country", a parser szukał „Country / Territory" lub „Country". Naprawione w `scraper/nowe_zrodla.py` (dodana nazwa, stare zachowane); test na prawdziwym nagłówku.

**Czego nadal nie da się ustalić bez decyzji lub logów (nie zgadywać):** przyczyny awarii z listy wyżej oraz zakresy oznaczone w `jak-to-dziala/tresc.ts` jako „do potwierdzenia" (pole `tbc`, lista do prawnika). Wypełnienie ich wymaga danych ze Stanu danych na produkcji i, tam gdzie dotyczy prawa (Regulamin X, prawo cytatu), decyzji prawnika.

**Kolejne kroki OSINT-01:** (a) wdrożyć poprawkę progu zaległości (kod w tej gałęzi), (b) właściciel dostarcza z serwera logi worker/beat dla źródeł z listy realnych problemów (polecenia poda agent), (c) po naprawie uzupełnić „do potwierdzenia" w `jak-to-dziala/tresc.ts` faktycznymi danymi (zakres, odświeżanie) i dopisać tam odnośnik do Stanu danych; elementy prawne (Regulamin X, prawo cytatu) do decyzji prawnika.

## Pętla person (od 5.11.2026)

Dziesięć person-użytkowników przechodzi przez żywy portal, ocenia go i zgłasza braki. Wyniki rundy 1, zbiorcza lista wniosków,
nowe propozycje źródeł i szybkie poprawki: `docs/PERSONY_PRZESZLOSC_RUNDA1.md`. Średnia rundy 1: 4,2/10 (zaniżona przez limity
zapytań i ładowanie przez narzędzie bez przeglądarki; nie używać jako wskaźnika postępu). Cel: średnia co najmniej 7, żadna persona poniżej 6.

## Następne kroki

1. **OSINT-00 (w toku):** testy backendu i build frontendu na scalonej gałęzi; wynik w `HANDOFF_AI.md`.
2. **OSINT-01 (w toku):** wdrożone 5.11; poprawka progu zaległości gotowa do wdrożenia; 7 realnych problemów ze źródłami do zbadania w logach (lista w sekcji OSINT-01).
3. **OSINT-02:** pokazać dane już zbierane, a niewidoczne (PKW, reklamy Meta).
4. **OSINT-03:** włączyć BZP po uzyskaniu instrukcji UZP; domknąć status „do potwierdzenia" (lobbing, PE, kilometrówki).
5. **OSINT-04:** źródła P1 z katalogu: BIR, Biała lista, SUDOP; potem RCN i ULDK.
6. **OSINT-05:** funkcje dla redakcji (teczki tematów, eksport z przypisami, API z kluczami i limitami).
7. **OSINT-06:** formalne: klauzula RODO zaakceptowana przez prawnika, procedura sprzeciwu.
8. **GIT-01:** przejrzeć i zdecydować o pozostałych gałęziach `cloud/*` (m.in. `design-przeszlosc`, `spolki-mobile-wersja`, `szybkosc-skroty`, `testy-pelne`, `spina3-s2`) oraz otwartych PR #21–#28.
9. **UI-01:** spójna identyfikacja wizualna po ustaleniu kierunku z właścicielem (`docs/BRAND_AND_THEMES.md`, gałąź `kit/design`).

Zasady bez zmian: tylko osoby publiczne, łączenie po identyfikatorach (nigdy po nazwie, PESEL nigdy), jawne braki („brak w naszych danych" z zakresem i datą),
nieobchodzenie zabezpieczeń, ta sama miara dla rządzących i opozycji, wysyłka próśb o licencje tylko po zatwierdzeniu właściciela.


## Runda person 2 (6.11.2026) i kolejne kroki
Wyniki: `docs/PERSONY_PRZESZLOSC_RUNDA2.md` (obywatel 7, compliance 5, radny 3; średnia 5,0, próg 7). Następne: widok „podmiot po NIP” dla jednostek bez KRS (wniosek 1), domyślny widok „całość projektu ustawy” w głosowaniach posła, widok finansów partii (PKW; czeka na odczyt danych z serwera), pełna runda 10 person po wdrożeniu poprawek.
