# Autobudowa przeszłość.today (od 16.11.2026)

Właściciel 16.11.2026: „zautomatyzuj rozwój portalu”. Codziennie w nocy rutyna w chmurze (Claude Code, routine) bierze **jedną** kolejną
pozycję z kolejki poniżej, buduje ją z testami na osobnej gałęzi i otwiera PR do gałęzi integracyjnej. **Scalenie i wdrożenie robi właściciel.**
Zasilanie danymi i raport doby działają osobno na serwerze (`backend/news/przeszlosc_samorozwoj.py`, zadanie `przeszlosc-doba`).

## Zasady dla rutyny (czytaj w całości przed pracą)

1. Gałąź bazowa: `main` (od 17.11.2026 odzwierciedla produkcję). Pracujesz od niej i do niej otwierasz PR; nigdy nie wypychasz bezpośrednio na `main`. Commity po angielsku, krótkie (CONTRIBUTING.md).
2. **Jedna pozycja naraz.** Jeśli istnieje otwarty PR z gałęzi `auto/przeszlosc-*`, nic nie buduj: zakończ z jednym zdaniem „czeka PR #N”.
3. Wybór pozycji: najpierw otwarte Issues z etykietami `sprint` i `area:przeszlosc` (najstarsze), potem pierwsza pozycja z tabeli ze stanem `do zrobienia`.
   Pomiń pozycję, dla której istnieje zamknięty bez scalenia PR `auto/przeszlosc-<id>` (właściciel ją odrzucił).
4. Najpierw sprawdź w kodzie, czy pozycja nie jest już zrobiona. Jeśli jest: PR zmienia tylko jej stan w tabeli na `zrobione wcześniej` z dowodem (plik, test).
5. Gałąź `auto/przeszlosc-<id>-<krótki-opis>`. W tym samym PR zmień stan pozycji w tabeli na `w PR`.
6. Testy: backend `cd backend && pip install -r requirements.txt && pytest news/test_<moduł>.py -q` (SQLite, bez sieci; testy nie mogą łączyć się
   z żadnym zewnętrznym hostem). Front: `npm ci && npm run build` w `frontend-spin` przy zmianach UI. PR tylko z zielonymi testami dotkniętych modułów;
   jeśli coś nie przechodzi z innego powodu, opisz to w PR.
7. Opis PR po polsku: co zmieniono, kryterium odbioru z tabeli i jak je sprawdzono, lista plików, ryzyka, „Wdrożenie: właściciel”. Bez długich myślników.
8. Design według `CLAUDE.md` w repo (boksy, 1440 i 390 px, cele 44 px). Treści po polsku, prostym językiem.

## Czego rutyna NIGDY nie robi (bramki człowieka)

- Nie scala PR, nie wdraża, nie loguje się na serwer, nie czyta ani nie zmienia `.env*`, nie dodaje sekretów.
- Nie dodaje nowych źródeł danych, nie zmienia kart dostępu ani `scraper/access_gate.py`, nie włącza flag (to Prawnik i właściciel; kolejka źródeł
  prowadzi się sama w `przeszlosc_samorozwoj.KOLEJKA`).
- Nie zmienia reguł łączenia i potwierdzania tożsamości osób (`krs_agent`, weryfikacja imienników, `matched_by`), nie publikuje doniesień ani powiązań
  bez kolejki przeglądu, nie pokazuje danych osób prywatnych (osoba prywatna = anonimowy węzeł, PESEL nigdy).
- Nie usuwa danych ani migracji; migracje tylko dodające (nowe tabele i pola), opisane w PR.
- Nie wysyła maili ani wiadomości, nie publikuje na zewnątrz.
- Pozycja, która wymaga którejś z tych rzeczy: zmień jej stan na `wymaga decyzji` z jednym zdaniem dlaczego (w PR) i weź następną.

## Kolejka (kolejność = priorytet; źródło: `docs/SLEDCZY_RUNDA_3.md`, `docs/PERSONY_PRZESZLOSC_RUNDA2.md`)

| id | Pozycja | Kryterium odbioru | Rozmiar | Stan |
|---|---|---|---|---|
| A00 | Dwa czerwone testy na gałęzi integracyjnej (pełny przebieg 16.11): `news/test_niw_dotacje.py::test_identifier_matching_company_view_notes_and_export` (test oczekuje pustej notki, widok podmiotu zwraca notkę o niepełnym składzie organów) i `scraper/test_rcl_client.py::test_robots_rule_for_our_agent_is_followed_and_override_is_explicit` (nie rzuca `RclStop`) | ustal, czy błędny jest test, czy kod (nie osłabiaj reguły robots w RCL: zasada RCL obowiązuje); oba testy zielone; opis przyczyny w PR | S | do zrobienia |
| A01 | P1-23: przepływy osoby liczą ten sam rekord dwa razy, gdy osoba ma funkcję w zamawiającym i w wykonawcy | deduplikacja po rekordzie przed sumami i sankey; jeden wiersz z dwiema etykietami; test | S | do zrobienia |
| A02 | P1-24: węzły sankey i sumy kontrahentów kluczowane NIP-em, nie nazwą z ogłoszenia | klucz węzła = NIP (nazwa z najnowszego rekordu); bez NIP osobny węzeł z dopiskiem; osoby fizyczne nie w jednym węźle po nazwie; test | S | do zrobienia |
| A03 | P1-25: eksport przepływów CSV i JSON z przypisem | kolumny: data, od (NIP), do (NIP), kwota, waluta, rodzaj, źródło, link, `matched_by`, `amount_suspect`, `outside_tenure`, data pobrania; test | M | do zrobienia |
| A04 | P1-26: daty roczne (FTS, 1,5%) a okres funkcji | rok częściowo w okresie funkcji = „w roku funkcji” z etykietą, nie 31.12; test na obu brzegach | S | do zrobienia |
| A05 | P2-17: odmiana liczebników („1 funkcji”, „0 z 1 osób”) | funkcja `plural()`; test dla n = 0, 1, 2, 5, 22 | S | do zrobienia |
| A06 | P2-16: Stan danych na 390 px bez ucinania wielokropkiem | zawijanie do 2 linii, braki źródeł w całości pod spodem; 0 elementów z `text-overflow: ellipsis` na 390 | S | do zrobienia |
| A07 | P2-18: licencja i „łączone po NIP/KRS” widoczne, nie tylko w `title` | druga linia albo rozwinięcie wiersza; dostępne klawiaturą i dotykiem | S | do zrobienia |
| A08 | P2-19: sankey z klawiatury i dotyku, etykiety nie nachodzą na wstęgi | Tab przechodzi przez węzły i podświetla wstęgi; na 1440 etykiety poza wstęgami | S | do zrobienia |
| A09 | P2-20: „Osoby sprawdzone w KRS 0%” obok „Osoby z podmiotem 1” | jedna spójna miara albo podpis „sprawdzone przez agenta KRS”; test | S | do zrobienia |
| A10 | P2-21: źródło wyłączone z dawnymi rekordami | stan „wyłączone, dane do RRRR-MM-DD”; test w `test_przeszlosc_stan.py` | S | do zrobienia |
| A11 | Persony R2: domyślny widok „całość projektu ustawy” w głosowaniach posła | domyślnie głosowanie nad całością, przełącznik „wszystkie głosowania”; test | S | do zrobienia |
| A12 | P1-14/G3: skróty i odmiana w wyszukiwarce tematów | zapytania „CPK”, „Turów”, „Orlenu” znajdują temat; test z listą przypadków | M | do zrobienia |
| A13 | P1-6: dziennik zmian spółki z kolejnych odpisów KRS (bez osób fizycznych z imienia) | sekcja „Zmiany w KRS” na profilu podmiotu: data, rodzaj zmiany, link do odpisu; test | M | do zrobienia |
| A14 | P1-10: indeks wzmianek w mediach (szybkie wyszukiwanie osoby w artykułach) | zapytanie o osobę korzysta z indeksu; pomiar przed i po w opisie PR; test | M | do zrobienia |

Nowe pozycje dopisuje sesja Claude po kolejnej rundzie Śledczego lub person (na końcu tabeli, kolejny id).
