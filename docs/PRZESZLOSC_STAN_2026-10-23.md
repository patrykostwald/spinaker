# przeszłość.today - inwentarz danych i przepływów (23.10.2026)

Gałąź `cloud/przeszlosc-rozwoj`. Stan kodu, nie produkcji (sesja w chmurze nie ma dostępu do serwera). Liczby z produkcji
po wdrożeniu da komenda `python manage.py przeszlosc_krs_pokrycie` i strona `/przeszlosc/dane`.

## 1. Dlaczego „nie ma danych” i „nie ma przepływów” (diagnoza)

Kod przepływów istnieje od 6-11.10 (`drzewo_pieniedzy.py`, `przeszlosc_przeplyw.py`), ale prawie zawsze był pusty, bo:
1. **Osoba nie ma spółek** - pieniądze łączymy z osobą tylko przez potwierdzone funkcje w KRS. Jedyne źródło tych funkcji to agent
   KRS (`krs_agent.py`), który działa tylko przy `KRS_AGENT_ENABLED=true` i kluczu Gemini, 10 osób na dobę.
2. **Podmiot nie ma NIP** - zamówienia i dotacje łączymy po NIP; NIP brał się tylko z odpisu KRS przy pracy agenta, przy wejściu
   w spółkę na żądanie albo ze zbieracza `krs_changes`. Nikt nie uzupełniał braków.
3. **Źródła pieniędzy wyłączone lub ręczne** - TED, FTS, Kohesio za flagami `PUBLIC_RECORDS_*_ENABLED` (domyślnie wyłączone),
   BZP za `BZP_API_ENABLED`, NIW i 1,5% OPP tylko z ręcznej komendy.
4. **TED tylko w jedną stronę** - pokazywaliśmy podmiot jako wykonawcę; podmiot publiczny jako zamawiający (jawny NIP
   zamawiającego z TED) nie miał przepływów.

## 2. Źródła

| Źródło | Kod | Gdzie zapis | Harmonogram | Flaga | Stan po sprincie |
|---|---|---|---|---|---|
| KRS - odpisy (api-krs.ms.gov.pl) | `krs.py` | `RegisteredOrganisation` | **nowe:** `krs-pokrycie-night` 1:47 | `KRS_POKRYCIE_ENABLED` (domyślnie tak) | kolejka uzupełnień, odpis aktualny + pełny |
| Biała lista MF (NIP -> KRS) | **nowe:** `krs_pokrycie.biala_lista` | tylko numer KRS w kolejce | w tym samym zadaniu | `BIALA_LISTA_ZAPYTAN` (10 zapytań po 30 NIP) | zbudowane |
| Funkcje osób w KRS (agent) | `krs_agent.py` | `PublicFigureOrganisationRelation` | `krs-agent-night` 0-6:10 | `KRS_AGENT_ENABLED` + Gemini | **zaostrzone** - imiennicy do redakcji |
| Zmiany w KRS | `collect_public_krs_changes` | `PublicRecord krs_changes` | co 15 min | `PUBLIC_RECORDS_KRS_CHANGES_ENABLED` | bez zmian |
| TED | `collect_public_ted` | `PublicRecord ted/notice` | co 15 min | `PUBLIC_RECORDS_TED_ENABLED` | **przepływy w obie strony** |
| BZP | `scraper/bzp_backfill.py` | `PublicRecord bzp/notice` | `bzp-metadata-3m` | `BZP_API_ENABLED` | bez kwot i wykonawców (BZP nie podaje) |
| FTS (budżet UE) | `nowe_zrodla` | `PublicRecord fts/eu_grant` | co 15 min | `PUBLIC_RECORDS_FTS_ENABLED` | w przepływach |
| Kohesio | `nowe_zrodla` | `PublicRecord kohesio` | co 15 min | `PUBLIC_RECORDS_KOHESIO_ENABLED` | tylko po nazwie - poza sumami |
| NIW-CRSO | `niw_dotacje.py` | `PublicRecord niw/grant_pl` | **nowe:** `przeszlosc-niw-weekly` nd 2:50 | `PRZESZLOSC_NIW_AUTO` (domyślnie tak) | było tylko ręcznie |
| 1,5% OPP (MF) | `opp_podatek.py` | `PublicRecord mf_opp` | **nowe:** `przeszlosc-opp-weekly` nd 3:05 | `PRZESZLOSC_OPP_AUTO` (domyślnie tak) | było tylko ręcznie |
| Sejm: głosowania, druki, ELI | `import_official_task` | `ParliamentaryVoting`, `OfficialRecord` | co 15 min / godz. | bez flagi | działa |
| Sejm: wypowiedzi, interpelacje, zapytania, procesy, komisje, wideo | `collect_public_*` | `PublicRecord` | co 15 min | `PUBLIC_RECORDS_*_ENABLED` | bez zmian |
| Lobbing MSWiA i Sejm, PKW, Meta Ads | `collect_public_*` | `PublicRecord` | co 15 min | `PUBLIC_RECORDS_*_ENABLED` | bez powiązania z osobą |
| Oświadczenia majątkowe | `collect_public_assets` + komenda `oswiadczenia` | `AssetDeclaration` | indeks tak, komenda nie | `ASSETS_DECLARATIONS_ENABLED` | tylko w kodzie (komenda ręczna) |
| Wikidata, HowTheyVote, Integrity Watch, kilometrówki, rejestr UE | `nowe_zrodla` | `PublicRecord` | co 15 min | `PUBLIC_RECORDS_*_ENABLED` | bez zmian |
| RCL | `rcl_harvest.py` | `LegislativeProject` | noc 1-5 | `RCL_FETCH_ENABLED` | poza profilem osoby |
| Rejestr korzyści posłów | - | - | - | - | nie ma w kodzie (G2) |

Wzorzec `weryfikator_tozsamosci` z zadania nie istnieje w repozytorium (żadna gałąź). Zastosowaliśmy jego zasadę w istniejącym
kodzie: osoba-spółka tylko po twardym identyfikatorze albo z potwierdzeniem.

## 3. Sekcje profilu i dlaczego mogą być puste

**Osoba** (`przeszlosc_osoba.profile`, front `PersonProfile.tsx`):

| Sekcja | Pusta, gdy |
|---|---|
| Funkcje w KRS | brak potwierdzonej relacji: agent wyłączony, kandydat odrzucony, relacja czeka na redakcję (`pending_review`) |
| Pieniądze powiązanych spółek, **Przepływy pieniędzy (nowe)** | brak funkcji w KRS; podmiot bez NIP (teraz uzupełnia kolejka KRS); źródła pieniędzy wyłączone; pozycje spoza okresu funkcji ukryte (przełącznik) |
| Dokumenty Sejmu, komisje, głosowania | brak oficjalnego id posła (nigdy po nazwisku) albo zbieracz wyłączony; komisje tylko kadencja 10 |
| Konta X i wpisy | brak konta z dowodem i potwierdzeniem redaktora |
| Otwarte dane (PE, kilometrówki) | flaga źródła wyłączona; brak id PE lub Sejmu |
| Oświadczenia | `ASSETS_DECLARATIONS_ENABLED` wyłączone albo komenda nie uruchomiona |
| Wzmianki | imiennik w rejestrze (powód pokazany od P0-9) |
| Sieć | `PRZESZLOSC_NETWORK_ENABLED` wyłączone |

**Podmiot** (`drzewo_pieniedzy.tree`, front `DrzewoPieniedzy.tsx`): zamówienia, dotacje i 1,5% są puste bez NIP/KRS albo przy
wyłączonych źródłach; osoby - bez potwierdzonych relacji (podmiot dociągnięty na żądanie nie ma osób); BZP nigdy nie ma kwot.

## 4. Co zbudowano w tym sprincie

1. **Pokrycie KRS** (`news/krs_pokrycie.py`, model `KrsKolejka`, migracja `0170_krs_kolejka`):
   - `zasil()` - do kolejki: podmioty bez NIP/REGON/formy albo z odpisem starszym niż 90 dni, KRS z listy NIW, NIP-y z TED
     (wykonawcy-organizacje i zamawiający), BZP i FTS. Bez nazw, bez osób fizycznych.
   - `uzupelnij()` - NIP -> KRS z Białej listy MF (z odpowiedzi tylko pole `krs`), odpis aktualny z api-krs, zapis tylko gdy NIP
     odpisu = NIP z kolejki; odpis pełny dla podmiotów z relacjami KRS (data wykreślenia osoby z organu zamyka relację).
     Odstęp 1 s, limit partii, ponowienie błędu po 2^n godz. (do 7 dni), „brak w rejestrze” osobno od błędu.
   - `raport()` + komenda `przeszlosc_krs_pokrycie [--zasil] [--uzupelnij --limit N] [--json]`.
2. **Imiennicy**: agent KRS potwierdza automatycznie tylko, gdy obok zgodnej maski w KRS jest co najmniej jedno sprawdzone źródło,
   które wymienia osobę i podmiot; inaczej relacja czeka na redaktora.
3. **Przepływy pieniędzy v1**: API `GET /api/przeszlosc/przeplywy/<osoba:slug|spolka:KRS>/` (`przeszlosc_przeplywy.py`) i sekcja
   na profilu osoby i podmiotu (`Przeplywy.tsx`): trzy boksy (wpływy, wydatki, pozycje), sankey jednej waluty, tabela
   data / od / do / kwota / rodzaj i źródło, filtr rodzaju, „pokaż spoza okresu funkcji”.
4. **Stan danych** (Śledczy G4): API `/api/przeszlosc/stan-danych/` i strona `/przeszlosc/dane` (odnośnik w stopce).
5. NIW i 1,5% OPP w harmonogramie.

## 5. Backlog Śledczego - stan

| Pozycja | Stan |
|---|---|
| P0-1..P0-8 | zrobione (R2b) |
| P0-9 duplikaty i powód 0 wzmianek | zrobione w kodzie (a43fda5, b1fd576) |
| P0-10 TED jako „dokumenty Sejmu” | zrobione (d96ce99) |
| P1-1 wyszukiwarka spółek / P1-16 dociąganie KRS | zrobione (1372c1e: nazwa z odpisu aktualnego) |
| P1-3 / P1-18 drzewo osoby - najnowsze głosowania, ≤ 50 | zrobione (db0baf9) |
| P1-9 szybkość | częściowo (be9aaaa), do pomiaru na produkcji |
| P1-11 spójność flagi kwot | zrobione (przepływy i drzewo używają tej samej `mark_suspect`) |
| P1-13 licznik 100 z N, P1-15 etykieta pewności | zrobione (b1fd576) |
| P1-17 REGON 9 cyfr, NIP z PL | zrobione w kodzie (`przeszlosc_spolki.classify`, `regon__startswith`) |
| P1-20 luki ministrów | częściowo (60e3346: kandydaci do scalenia) |
| P1-14 / G3 skróty i odmiana | nie zrobione |
| P1-19 / P2-1 ucinanie na 390 | nie zrobione dla starych widoków (nowe sekcje: 0 elementów poza ekranem) |
| P2-10..P2-15 | nie zrobione |
| G1 karta tożsamości | częściowo (scalanie) |
| G4 stan danych | **zrobione w tym sprincie** |
| G2, G5-G10 | nie zrobione |
| Przepływy pieniędzy (obietnica właściciela 6.10) | **v1 zrobione w tym sprincie** |
