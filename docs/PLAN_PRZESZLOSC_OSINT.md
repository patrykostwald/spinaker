# przeszłość.today — plan narzędzia OSINT (stan na 5 listopada 2026)

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

## Luki ogłoszone przez samą stronę (to jest nasza lista „jeszcze do podłączenia")

Źródło: sekcje „Skąd mamy dane" i „Czego tu nie ma" na `/przeszlosc/jak-to-dziala` (stan z 13.10.2026).

**Źródła w bazie, ale ze statusem „do potwierdzenia":**
1. **BZP / e-Zamówienia** — czy włączone na produkcji, harmonogram, zakres.
2. **Parlament Europejski** — okres danych; harmonogram.
3. **Lobbing** (rejestr MSWiA, lobbing w Sejmie) — zakres i harmonogram; część stron za zabezpieczeniem antybotowym, **nie obchodzimy go**.
4. **Wpisy na X** — zakres, harmonogram, regulamin X i prawo cytatu.
5. **Media** — harmonogram i zakres; dopasowanie osób bywa automatyczne.
6. **Kilometrówki i biura posłów** — zakres; jakglosuja.pl to serwis zewnętrzny, nie rejestr urzędowy; PDF-y Kancelarii Sejmu niedostępne automatycznie.
7. **Meta (reklamy polityczne) i PKW (finanse komitetów)** — zbierane, ale **nie wiadomo, gdzie są widoczne w serwisie**.
8. **Faktyczny harmonogram odświeżania na produkcji** każdego źródła i data ostatniej aktualizacji — „brak w naszych danych".

**Źródła, których nie ma wcale:**
9. Centralny Rejestr Umów
10. Rejestr beneficjentów rzeczywistych
11. Księgi wieczyste
12. Orzeczenia sądów

**Obietnice w treści strony do dopilnowania:**
13. Procedura i terminy odpowiedzi na wnioski RODO — „do potwierdzenia".
14. Klauzula informacyjna to wersja robocza do akceptacji prawnika.
15. Zespoły: wspólne teczki tematów, eksport do publikacji z przypisami, API dla redakcji — zapowiedziane, niewdrożone.
16. Limit eksportu 20 000 wierszy na kategorię (wiersz „pominięto N").

## Rozbieżność: kod a żywa strona (ważne)

Trasy i funkcje powyżej (`/przeszlosc/*`, drzewo KRS, TED, Kohesio, FTS, PE, lobbing, odstępstwa od klubu,
alerty 7:00, rejestr poprawek) **nie występują w kodzie tego repozytorium**. Tutaj jest tylko wcześniejszy
stan: `frontend-przeszlosc` (jedna linijka `<PortalHome />`, stary motyw), backend z podstawami KRS
(`backend/news/krs.py`, `krs_agent.py`, `public_figures.py`, `political_*`) i komponenty
`packages/ui` (m.in. `PublicFigureProfile`, `PublicFigureDirectory`).
Ostatni commit kodu w repozytorium: 30 września 2026. Żywa strona zawiera pracę z października.
Repozytorium `patrykostwald/radar` to osobny produkt (analiza narracji dla instytucji) i nie zawiera
kodu przeszlosc.today; repozytorium `iapply` ma ostatnią zmianę z października 2025.

**Konsekwencja:** przed wdrażaniem funkcji trzeba ustalić, gdzie leży aktualny kod przeszlosc.today
(prawdopodobnie lokalny komputer lub niewypchnięta gałąź) i dołączyć go do repozytorium (zadanie REPO-01
z `PLAN_AKTUALNY.md`). Dopiero wtedy sensowne jest dopisywanie źródeł i funkcji.

## Proponowana kolejność prac po odzyskaniu kodu

1. **REPO-02** — wypchnąć aktualny kod przeszlosc.today na osobną gałąź (bez `.env`, baz, logów).
2. **OSINT-01** — wykaz źródeł z faktycznym stanem produkcji (włączone / harmonogram / ostatni udany import) i widoczny na stronie „Status danych"; zamiast „do potwierdzenia".
3. **OSINT-02** — pokazać w serwisie dane już zbierane, ale niewidoczne (PKW, reklamy Meta).
4. **OSINT-03** — domknąć źródła „do potwierdzenia": BZP, lobbing, kilometrówki, PE (zakres, okno dat, test, opis).
5. **OSINT-04** — nowe rejestry: Centralny Rejestr Umów, beneficjenci rzeczywiści, orzeczenia sądów, księgi wieczyste — każdy po ocenie podstawy prawnej i dostępności API; kolejność wg wartości dla dziennikarzy.
6. **OSINT-05** — funkcje dla redakcji: wspólne teczki tematów, eksport z przypisami, API z kluczami i limitami.
7. **OSINT-06** — kwestie formalne: klauzula RODO zaakceptowana przez prawnika, procedura sprzeciwu z terminami.
8. **UI-01** — spójna identyfikacja wizualna z `BRAND_AND_THEMES.md` (Noc/Dzień/Auto, jeden akcent), po ustaleniu kierunku z właścicielem.

Zasady bez zmian: tylko osoby publiczne, łączenie po identyfikatorach, jawne braki („brak w naszych danych" z
zakresem i datą), nieobchodzenie zabezpieczeń, ta sama miara dla rządzących i opozycji, wysyłka próśb do
wydawców po zatwierdzeniu właściciela.
