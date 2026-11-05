# Śledczy - runda 1 (11.10.2026)

Recenzja przeszłość.today w roli „Śledczy” (docs/SLEDCZY_ROLA.md). Tylko odczyt produkcji (https://przeszlosc.today, publiczne API, najwyżej 1 zapytanie na sekundę), kod w repo do zrozumienia danych, WebSearch do konkurencji. Zrzuty: `C:\Users\User\Desktop\projekty\przeszlosc-gotowe\sledczy-runda-1\` (5 widoków × 1440 i 390, ekran i cała strona). Ocena modelu AI odgrywającego rolę, nie opinia prawdziwego dziennikarza.

## 1. Streszczenie

1. **Ocena ogólna: 4,4 / 10.** Żaden obszar nie osiąga progu 8. Fundament (identyfikatory, licencje, zastrzeżenia „kontekst, nie dowód”) jest dobry, ale dane w kluczowych miejscach są błędne albo dziurawe.
2. **Błąd kwot na produkcji:** Orlen S.A. pokazuje „1091,07 mld zł suma z ogłoszeń”, z czego 1 086 150 000 000 zł to jedno ogłoszenie TED (olej napędowy dla 2. RBLog). Brak kontroli wiarygodności kwot.
3. **Przypisanie poza okresem funkcji:** drzewo Daniela Obajtka podpina 58 zamówień Orlenu i Energi z lat 2025-2026, choć jego funkcja w Orlenie skończyła się w 2024. To ryzyko insynuacji.
4. **Wzmianki medialne nie działają dla najważniejszych osób:** Tusk 0, Obajtek 0. Silnik przeszukuje tylko 2000 najnowszych z 525 tys. artykułów i wymaga pełnego imienia i nazwiska.
5. **Brak funkcji wykonawczych:** Tusk to w profilu tylko „Poseł na Sejm RP” (bez premiera i przewodniczącego Rady Europejskiej), Kołodziejczak bez funkcji wiceministra.
6. **Graf tematu miesza kontekst z tematem:** w temacie „Kołodziejczak” (sprawa z zarzutami) pojawiają się szpitale, klub sportowy i fundacje innych polityków tylko dlatego, że coś napisali na X.
7. **Głosowania w temacie:** najwyżej 8, tylko najnowsze; reklamowany przykład „Turów: kto był za, kto przeciw” zwraca 0 głosowań i 0 osób.
8. **Brak wyszukiwarki spółek** (po nazwie, NIP, KRS). W bazie jest 800 podmiotów powiązanych z osobami publicznymi; PKO BP i dowolna spółka spoza tej listy dają 404.
9. **Alerty tylko dla osób i tematów**, nie dla spółek; brak historii zmian KRS i porównania wersji; „archiwum” to tylko odnośnik do web.archive.org.
10. **Mocne strony:** łączenie zamówień po NIP/KRS, licencje i źródła w odpowiedziach API, eksport CSV/JSON profilu, odstępstwa od klubu, dane europosłów (dochody, deklaracje), poprawna nawigacja klawiaturą i brak przewijania w poziomie.

## 2. Scenariusze śledcze

### S1. Podążaj za pieniędzmi: Orlen S.A. i zarząd
- **Pytanie:** kto zarabia na zamówieniach publicznych Orlenu, kto zarządzał spółką w tym czasie?
- **Droga:** profil Obajtka (`/api/przeszlosc/osoba/615-daniel-obajtek/`, 19,2 s na zimno) → Orlen (`/spolka/0000028860/`, 3,6 s) → drzewo (`/przeplyw/spolka:0000028860/`, `/przeplyw/osoba:615-daniel-obajtek/`, 17,2 s). Zrzuty `spolka-orlen-1440.png`, `przeplyw-obajtek-1440.png`.
- **Wynik:** 57 zamówień z TED (Orlen jako wykonawca), dopasowanie `matched_by: NIP`, każdy rekord z odnośnikiem do TED, notka „Kwoty z ogłoszeń, nie z umów”. Suma 1 091 071 590 463,71 zł. Największa pozycja: 1 086 150 000 000,00 zł (TED 157377-2026, olej napędowy 2026-2028 dla 2. Regionalnej Bazy Logistycznej), druga: 1 012 825 380 zł paliwa dla szpitala w Inowrocławiu (też podejrzana). Zamówienia obejmują tylko 2025-10-21...2026-10-06 (okno nigdzie nie podane). Osoby: tylko Obajtek (były prezes); obecnego zarządu Orlenu nie ma, bo baza zawiera tylko osoby publiczne z rejestru.
- **Drzewo osoby:** Obajtek → Orlen (2018-03-07 do 2024-03-07) → 57 zamówień z lat 2025-2026. Kod: `przeszlosc_przeplyw.finance()` nie filtruje zamówień po okresie funkcji osoby. 58 węzłów „organ” dla 52 unikalnych nazw (brak scalania zamawiających). Podpisy krawędzi na siebie nachodzą i są nieczytelne (zrzut). `signals: []` zawsze.
- **Daty:** 2018-03-07 i 2024-03-07 to najpewniej daty wpisu w KRS, nie powołania i odwołania (luty 2018 i luty 2024 wg doniesień prasowych - nie zweryfikowałem tu źródłem pierwotnym). Interfejs nie mówi, która to data.
- **Nie ustalono:** wartości umów (tylko ogłoszeń), BZP (wyłączone), dotacji (0), zarządu i rady nadzorczej w okresie zamówień.
- **Co by pomogło:** kontrola wiarygodności kwot, filtr „w okresie funkcji”, pełny skład organów z KRS (osoby niepubliczne jako „członek zarządu” bez nazwiska albo z nazwiskiem przy funkcji w spółce Skarbu Państwa), okres pokrycia źródła przy każdej sumie.

### S2. Co osoba mówiła o temacie i jak głosowała
- **Pytanie:** co Donald Tusk i Michał Kołodziejczak mówili o VAT i CPK oraz jak głosowali?
- **Droga:** `/osoba/326-donald-tusk/`, `/osoba/96-michal-kolodziejczak/`, `/temat/?q=VAT`, `/temat/?q=CPK`, `/temat/?q=Turów`.
- **Wynik:** profil daje 1557 głosowań imiennych z rozkładem (Tusk: 721 nieobecny, 488 przeciw, 341 za) i linkami do sejm.gov.pl; 28 wpisów Tuska na X. Temat VAT: 8 głosowań, wszystkie z 8.10.2026, z rozkładem klubów. CPK: 0 głosowań, 14 wpisów, 17 rekordów. Turów (przykład z `/funkcje/`): 0 głosowań, 0 osób, 20 rekordów i 99 materiałów.
- **Braki:** `topic_votes(limit=8)` bez stronicowania i zakresu dat; brak połączenia „wypowiedź osoby X w temacie” z „głosem osoby X w tym temacie” na jednym widoku; wzmianki Tuska = 0 (patrz S10); drzewo Tuska pokazuje 297 głosowań z okresu 2025-01-24...2025-04-24, a pomija 3073 nowsze (sortowanie po `-voting_id`, nie po dacie).
- **Co by pomogło:** widok „osoba × temat” (wypowiedzi, wystąpienia, głosy w jednej osi), pełna lista głosowań tematu ze stronicowaniem, sortowanie po dacie.

### S3. Kto stoi za organizacją z KRS
- **Pytanie:** kto zarządza Fundacją Agrounia i czy łączy ją coś z innymi podmiotami?
- **Droga:** nie ma wyszukiwarki podmiotów; trafiłem przez profil Kołodziejczaka → `/spolka/0000760912/`. Próby: `/spolka/7740001454/` (NIP Orlenu) 404, `/spolka/0000026438/` (PKO BP) 404.
- **Wynik:** Fundacja Agrounia: 1 osoba (Kołodziejczak, prezes zarządu 2018-12-07...2024-03-27), 0 zamówień, 0 dotacji. Brak pozostałych członków organów, adresu, wspólnych adresów, beneficjentów rzeczywistych, historii zmian.
- **Nie ustalono:** kto zarządza fundacją dziś, z kim dzieli adres, czy otrzymała pomoc publiczną (SUDOP brak).
- **Co by pomogło:** wyszukiwarka podmiotów (nazwa, KRS, NIP, REGON), pobieranie dowolnego KRS na żądanie z api-krs, pełny skład organów, CRBR, Biała lista VAT.

### S4. Oś czasu wydarzenia z tematów dnia
- **Pytanie:** jak rozwijała się sprawa Michała Kołodziejczaka (8-10.10.2026)?
- **Droga:** pasek YouTube na stronie głównej (tytuły o „narko-aferze”) → `/temat/?q=Kołodziejczak` (11,2 s) → RSS `/rss/?q=Kołodziejczak`.
- **Wynik:** 25 wpisów polityków z 9-10.10, 3 diagnozy Dr. Spina (np. „Niepotwierdzone, poważne oskarżenia...”), 99 materiałów medialnych od 2025-08-21. Oś czasu da się złożyć, ale tylko z wpisów i tytułów.
- **Problemy:** 25 podmiotów z KRS w grafie to funkcje osób, które pisały o sprawie (Elżbieta Witek → klub sportowy „Olimpia”, Bożena Żelazowska → dwa szpitale, Matecki → Ośrodek Monitorowania Antypolonizmu); 28 z 99 materiałów nie ma nazwiska w tytule, wśród nich „Kołodziejczyk: wciąż dostaję telefony...” (inna osoba); brak pierwszego źródła (kto pierwszy podał informację, jaki był oficjalny komunikat prokuratury lub partii); rekord „Alicja Łepkowska-Gołaś” (stenogram 13.11.2023) bez fragmentu, który wyjaśnia dopasowanie. RSS: `pubDate` w formacie `2026-10-10` (niezgodny z RSS 2.0), `link` kanału kieruje na spin.clinic.
- **Co by pomogło:** tryb „oś czasu wydarzenia” (pierwsza wzmianka, oficjalne komunikaty, reakcje stron) z fragmentem dopasowania; KRS w temacie tylko gdy podmiot sam występuje w temacie.

### S5. Weryfikacja twierdzenia z artykułu
- **Pytanie:** wpis Marii Koc z 28.09.2026: „W planie finansowym CPK brakuje 20 mld zł”. Czy narzędzie pozwala to sprawdzić?
- **Droga:** `/temat/?q=CPK`.
- **Wynik:** narzędzie pokazuje wpis, podobne wpisy innych polityków i diagnozę Dr. Spina nr 1072 („Realne trudności z unijnym finansowaniem CPK zinterpretowane jako całkowity paraliż”). Nie pokazuje dokumentu źródłowego (plan finansowy spółki, odpowiedź ministerstwa, budżet). Wśród 97 materiałów 59 nie ma „CPK” w tytule, m.in. „Miasteczko Gniewu i skandal z HANDLEM DZIEĆMI” i „Co po studiach? Systemy transportowe - SGH”.
- **Nie ustalono:** czy liczba 20 mld zł jest prawdziwa i skąd pochodzi.
- **Co by pomogło:** pole „twierdzenie → dokumenty pierwotne” (druki, interpelacje z odpowiedziami, sprawozdania spółek z eKRS RDF), fragment dopasowania przy każdym materiale, filtr „tylko źródła pierwotne”.

### S6. Dane do tekstu z przypisami i eksportem
- **Droga:** `?eksport=csv` i `?eksport=json` w profilu Kołodziejczaka; eksport tematu w interfejsie (kod `TopicTree.tsx`, generowany w przeglądarce); `/spolka/0000028860/?eksport=csv`.
- **Wynik:** CSV profilu (UTF-8 z BOM, średnik): 70 wierszy, w tym tylko 40 z 1557 głosowań, bez informacji o obcięciu; kolumny `data;rodzaj;treść;spin;link` - brak kolumn źródło, data pobrania, pewność powiązania, identyfikator; 10 wzmianek medialnych z profilu nie trafia do CSV; odnośniki KRS prowadzą do rejestr.io (serwis komercyjny), nie do odpisu MS. Spółka: parametr eksportu ignorowany (zwraca JSON z `Content-Type: application/json`, bez pliku). Przycisk przypisu jest w panelu wpisu tematu.
- **Co by pomogło:** pełny eksport z adnotacją o limicie, kolumny provenance, eksport spółki i drzewa (CSV węzłów i krawędzi, GraphML albo FtM dla Aleph), metodologia w pliku.

### S7. Telefon 390 px
- **Droga:** te same 5 widoków w 390 × 844 (zrzuty `*-390.png`).
- **Wynik:** brak przewijania w poziomie (scrollWidth 390), widoczny fokus, link „Przejdź do treści”. Ale: w profilu przycisk „JSON” i karta „Aktywność” są ucięte prawą krawędzią, w nagłówku „Narracja” ucięta; w siatce liczb osierocona komórka „0 artykułów”; w drzewie przepływu chipy kategorii ucięte, drzewo wymaga przewijania w dwóch osiach; 36 ze 105 celów dotyku w profilu ma mniej niż 32 px (Fitts); na `/przeszlosc?q=CPK` pierwszy ekran to pasek YouTube, wyniki tematu są niżej.
- **Co by pomogło:** pionowa lista zamiast drzewa poniżej 600 px, zawijanie przycisków, wynik wyszukiwania jako pierwszy ekran po wejściu z `?q=`.

### S8. Zmiany i alerty
- **Droga:** kod `przeszlosc_alerts.py`, przycisk „Obserwuj osobę” w profilu; nie zapisywałem się (zakaz wysyłania).
- **Wynik:** alerty e-mail raz dziennie o 7:00 dla tematu i osoby (podwójne potwierdzenie, wypisanie jednym kliknięciem); RSS tematu. Nie da się obserwować spółki ani numeru KRS/NIP. Brak widoku „co się zmieniło” (historia zmian KRS, usunięte wpisy na X, poprawione artykuły). „Kopia w archiwum” to odnośnik `web.archive.org/web/*/` i „Zapisz kopię teraz”; obiecane w `/funkcje/` „ostrzeżenie, gdy tekst zmienił się po cytowaniu” nie jest widoczne w przeszłość.today (w kodzie jest `EvidenceSnapshot` spin.clinic - nie sprawdziłem, czy działa tutaj).
- **Co by pomogło:** obserwacja podmiotu (zmiany KRS, nowe zamówienia), dziennik zmian z porównaniem wersji, automatyczny zapis kopii przy przypisie.

### S9. Porównanie z konkurencją na tym samym pytaniu („kto stoi za spółką i skąd ma pieniądze”)
| Narzędzie | Co ma lepiej | Cena (źródło, data) |
|---|---|---|
| rejestr.io | wszystkie podmioty KRS, historyczne powiązania osób, sprawozdania finansowe, status VAT, eksport, monitoring | Premium ok. 119 zł/mies., Business 249 zł/mies. (rejestr.io/cennik, kopia z 9.10.2026; cena planu Basic nieustalona) |
| OpenCorporates | spółki z wielu jurysdykcji, identyfikatory, darmowy dostęp dla dziennikarzy | API od 2250 GBP/rok, darmowe dla dziennikarzy i NGO (opencorporates.com/pricing, 10.2026) |
| OCCRP Aleph Pro | miliardy rekordów, cross-referencing, wspólne śledztwa, wizualizacja sieci, wgrywanie własnych dokumentów | darmowy dla redakcji non-profit (aleph.discourse.group, ogłoszenie z 10.2025) |
| Maltego | dowolna głębokość grafu, transformacje, wiele źródeł | Community darmowy (12 encji), Pro ok. 999 USD/rok (zestawienia 2026, nie strona producenta) |
| Hunchly | automatyczny zapis stron z hashami i znacznikami czasu, ścieżka audytu do sądu | Classic 149 EUR/rok (hunch.ly/pricing, 10.2026) |

- **Co mamy lepiej:** głosowania i odstępstwa od klubu, wpisy polityków na X z diagnozami, deklaracje europosłów, łączenie TED po NIP, wszystko bezpłatnie i po polsku, zastrzeżenia prawne w danych.
- **Czego brakuje:** pokrycia KRS (800 podmiotów wobec całego rejestru), wyszukiwarki podmiotów, sprawozdań finansowych, historii powiązań, beneficjentów rzeczywistych, zapisu dowodów (Hunchly), wgrywania własnych dokumentów i wspólnej teczki (Aleph).

### S10. Błędy i niespójności w danych
| # | Błąd | Dowód |
|---|---|---|
| 1 | Kwota 1,086 bln zł w jednym ogłoszeniu | `/spolka/0000028860/`, TED 157377-2026 |
| 2 | Zamówienia po zakończeniu funkcji podpięte pod osobę | `/przeplyw/osoba:615-daniel-obajtek/`: funkcja do 2024-03-07, zamówienia 2025-10-21...2026-10-06 |
| 3 | Wzmianki 0 dla Tuska i Obajtka | `/osoba/326-donald-tusk/` → `mentions.results: []`; kod `media_mentions.py`: `CANDIDATE_LIMIT = 2000` |
| 4 | Licznik „0 artykułów” przy 10 wzmiankach | profil Kołodziejczaka (zrzut), `activity` media 0 w 2026-10 |
| 5 | Mediana klubu KO: 0,2% w profilu, 0,0 w `/odstepstwa/` | oba profile (Tusk, Kołodziejczak) mają identyczne 0,2 i 2 głosy wbrew klubowi - do sprawdzenia |
| 6 | „Najnowsze” źródła publiczne z datą przyszłą | `/start/`: posiedzenie komisji 2026-10-20 jako najnowszy rekord |
| 7 | Zdublowane etykiety filtrów | pasek „Źródła publiczne”: „Dokument”, „Dokument” (zrzut temat-cpk-1440) |
| 8 | Imiennik w wynikach | temat „Kołodziejczak” zawiera materiał o „Kołodziejczyk” |
| 9 | Pewność „manual” dla wszystkich funkcji KRS, a w profilu `verification_method: krs_register`; węzeł ma `identifier` | `przeplyw_*.json`, `relations()` |
| 10 | Konto X przypisane Kołodziejczakowi: `@ekolodziejczak_`, 2 wpisy w 3 tygodniach („Pełna zgoda.”) | `/osoba/96-.../` - przypisanie przez Wikidata Q108391916, do ręcznej weryfikacji |
| 11 | Pisownia nazwisk: „Daniel OBAJTEK”, „Piotr MÜLLER” (dane PE) obok „Donald Tusk” | wyszukiwarka osób |
| 12 | „Oficjalny rejestr” = rejestr.io | `official_register_url` we wszystkich funkcjach KRS |
| 13 | Odnośniki do api.sejm.gov.pl (JSON) zamiast stron dla czytelnika | `/start/`, rekordy tematów |
| 14 | Funkcja „Tusk: rada Fundacji Ateny 2004 Floret Kobiet 2001-2010” | ręczne potwierdzenie bez widocznego dowodu tożsamości (KRS maskuje dane) - nie twierdzę, że błędne, ale nie da się tego zweryfikować z poziomu narzędzia |
| 15 | Pusta fraza `xqzw` trwa 11,3 s | `/temat/?q=xqzw` |

Martwych linków nie testowałem masowo (zakaz zapytań poza przeszłość.today).

## 3. Oceny 0-10

| # | Obszar | Ocena | Uzasadnienie i dowód |
|---|---|---|---|
| 1 | Szybkość | 5 | Strona 1,3-2,4 s (pomiar Playwright), ale API na zimno: osoba 5-19 s, temat 11-14 s, nawet pusty wynik 11 s; po `?q=` wyniki są pod paskiem YouTube. |
| 2 | Kompletność | 3 | 800 podmiotów, brak wyszukiwarki spółek, TED tylko od 10.2025, BZP wyłączone, dotacje 0, brak funkcji rządowych, wzmianki z 2000 artykułów, głosowania tematu najwyżej 8, Turów 0. |
| 3 | Pochodzenie i dowód | 5 | Plus: źródło, licencja, `retrieved_at`, `matched_by: NIP`. Minus: „oficjalny” link do rejestr.io, daty wpisu KRS bez opisu, krawędzie tematu bez źródła i daty, materiały bez fragmentu dopasowania, sprzeczne poziomy pewności. |
| 4 | Powiązania i przepływy | 4 | Drzewo z kategoriami i filtrem dat istnieje, ale limit zjadają głosowania (Tusk 297/300), brak filtra okresu funkcji, absurdalne sumy, nieczytelne podpisy, `signals` zawsze puste, brak scalania organów. |
| 5 | Zmiany w czasie | 3 | Alerty dzienne dla osoby i tematu, RSS (wadliwy `pubDate`); brak alertów spółek, historii zmian, porównania wersji, automatycznej kopii. |
| 6 | Eksport i cytowanie | 5 | CSV/JSON profilu i tematu, przypis; ale CSV obcięty bez ostrzeżenia, bez kolumn provenance, brak eksportu spółki i drzewa, brak formatu dla Aleph/Maltego. |
| 7 | Zaufanie, neutralność, język | 5 | Dobre notki „kontekst, nie dowód”, ta sama miara. Słabe: pierwszy ekran to sensacyjne tytuły YouTube (TV Republika 26 z 97 materiałów CPK, wPolsce24), graf tematu sugeruje związki przez funkcje KRS niezwiązane z tematem, deklaracja „Nic nie łączymy po samym nazwisku” wobec automatycznych dopasowań nazwisk w mediach. |
| 8 | Prawo i etyka | 5 | Tylko osoby publiczne, anonimizacja osób prywatnych, KW tylko legalnie. Ryzyko: Obajtek ↔ zamówienia po kadencji, kwota bilionowa przy nazwisku, brak ścieżki sprostowania na profilu i spółce (jest tylko na stronie pilota). |
| 9 | Użyteczność i dostępność | 5 | Fokus i skip link są, brak przewijania poziomego; ucięte przyciski na 390, 277 elementów drzewa bez etykiety dostępności, małe cele, dublowane etykiety filtrów. |
| 10 | Przewaga nad konkurencją | 4 | Unikalne połączenie Sejm + X + KRS + diagnozy, bezpłatnie; w podstawowym pytaniu „kto stoi za spółką” przegrywa z rejestr.io i Aleph. |
| | **Średnia** | **4,4** | |

## 4. Backlog

### P0 (blokuje zaufanie lub prawdę)
| # | Problem | Dowód | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|---|
| P0-1 | Kwoty nierealne wchodzą do sum | Orlen 1091,07 mld zł; TED 157377-2026 = 1,086 bln zł | Walidacja kwot przy imporcie TED/BZP (próg względem CPV i zamawiającego, np. > 5 mld zł albo > 100× mediany kategorii → „do weryfikacji”), takie rekordy poza sumą, z oznaczeniem | `/spolka/0000028860/` suma < 10 mld zł; rekord 157377-2026 ma flagę `amount_suspect: true` i nie wchodzi do `sums`; test jednostkowy z tym rekordem | M |
| P0-2 | Pieniądze spółki przypisane osobie poza okresem funkcji | drzewo Obajtka: funkcja do 2024-03-07, zamówienia 2025-2026 | W drzewie osoby domyślnie tylko rekordy finansowe w oknie `since...until` funkcji (+ przełącznik „pokaż całą historię spółki” z ostrzeżeniem); krawędź osoba-spółka z napisem okresu | `/przeplyw/osoba:615-daniel-obajtek/` domyślnie 0 zamówień Orlenu z 2025-2026; z przełącznikiem są, a każdy węzeł ma `outside_tenure: true` | M |
| P0-3 | Graf tematu sugeruje związki przez funkcje KRS osób, które tylko pisały o temacie | temat „Kołodziejczak”: szpitale, klub sportowy, fundacje innych polityków | KRS w grafie tematu tylko dla podmiotów, które same występują w rekordach tematu; funkcje osób przenieść do panelu osoby; w eksporcie tematu oznaczyć rodzaj „kontekst osoby” | `/temat/?q=Kołodziejczak` zawiera tylko podmioty powiązane z tematem (np. Fundacja Agrounia przez Kołodziejczaka może zostać jako osoba centralna, Olimpia Jawor nie) | S |
| P0-4 | Wzmianki medialne puste dla najważniejszych osób | Tusk 0, Obajtek 0 przy 525 tys. artykułów | Indeks wzmianek liczony w tle dla całej bazy (pełnotekstowo), dopasowanie także po samym nazwisku przy osobach o unikalnym nazwisku w rejestrze + fragment, który dopasował | Tusk ≥ 100 wzmianek z ostatnich 30 dni, każda z polem `snippet`; licznik „artykułów” w profilu równy liczbie wzmianek | M |
| P0-5 | Ścieżka sprostowania niewidoczna | brak w profilu i spółce (grep: tylko `pilot/PilotPage.tsx`) | Przycisk „Zgłoś błąd lub sprostowanie” przy każdym profilu, spółce i węźle drzewa, z identyfikatorem rekordu; publiczny rejestr poprawek | przycisk widoczny w 1440 i 390 na 3 typach stron, zgłoszenie zawiera id węzła; strona „Poprawki” istnieje | S |

### P1 (duża wartość)
| # | Problem | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|
| P1-1 | Brak wyszukiwarki podmiotów i pokrycia KRS | Tryb „Spółka” (nazwa, KRS, NIP, REGON); dociąganie dowolnego KRS z api-krs na żądanie i cache | `/spolka/7740001454/` i `/spolka/0000026438/` zwracają 200; wyszukiwarka zwraca PKO BP po „PKO” | M |
| P1-2 | Brak funkcji wykonawczych (premier, ministrowie, wiceministrowie) | Import z Wikidata (P39 z datami) i Monitora Polskiego, z źródłem | Tusk ma „Prezes Rady Ministrów” z datami; Kołodziejczak „sekretarz stanu MRiRW” | M |
| P1-3 | Głosowania w temacie: najwyżej 8, tylko najnowsze; drzewo osoby sortuje po id | stronicowanie i zakres dat; sortowanie po dacie; w drzewie osoby głosowania jako grupa, nie 297 węzłów | `/temat/?q=Turów` > 0 głosowań, jeśli w danych są; drzewo Tuska pokazuje najnowsze głosowania i ≤ 50 węzłów głosowań | M |
| P1-4 | Provenance niepełne | `official_register_url` na wyszukiwarkę KRS MS (rejestr.io jako dodatkowy), opis „data wpisu w KRS”, `snippet` dopasowania przy materiałach, jednolita pewność (`identifier`/`manual`/`name_only`) zgodna z metodą | żaden `official_register_url` nie wskazuje rejestr.io; każdy materiał ma `matched_in` + `snippet` | S |
| P1-5 | Eksport niepełny | CSV bez obcinania (albo z wierszem „pominięto N”), kolumny: źródło, data pobrania, pewność, id; eksport spółki i drzewa (CSV węzłów/krawędzi + JSON FtM) | CSV Kołodziejczaka ma 1557 głosowań lub wiersz „pominięto”; `/spolka/...?eksport=csv` zwraca plik | M |
| P1-6 | Obserwacja spółek i dziennik zmian | alert dla KRS/NIP (zmiany organów, nowe zamówienia), widok „zmiany od ostatniej wizyty” | zapis na alert spółki działa w teście; dziennik pokazuje zmianę KRS z datą i odpisem | M |
| P1-7 | Szum w dopasowaniach tematu | próg trafności, fragment dopasowania, filtr „tylko z nazwą w tytule”, wykluczanie imienników (Kołodziejczyk) | w temacie CPK ≥ 80% materiałów ma termin w tytule lub opisie widocznym w panelu | M |
| P1-8 | Pierwszy ekran po `?q=` to pasek YouTube | wynik tematu pierwszy, paski pod nim albo zwinięte | na 1440 i 390 pierwszy element pod menu to wynik tematu (pomiar ≤ 40/28 px) | S |
| P1-9 | Szybkość API | prekomputacja grafów, cache tematów, odpowiedź < 2 s | p95 `/osoba/` i `/temat/` < 2 s na zimno (10 prób) | M |

### P2 (dopracowanie)
| # | Problem | Poprawka | Kryterium odbioru | Szac. |
|---|---|---|---|---|
| P2-1 | Mobile 390: ucięte JSON, „Narracja”, karta aktywności | zawijanie przycisków, grid bez przepełnienia | `odstepy.js` bez ZLE, brak elementów poza viewportem | S |
| P2-2 | Drzewo: nieczytelne podpisy, 277 elementów bez etykiety | podpisy tylko na hover/fokus, `aria-label` węzłów, widok listy | 0 elementów interaktywnych bez nazwy dostępnej | S |
| P2-3 | RSS niezgodny | `pubDate` RFC 822, link kanału na przeszlosc.today | walidator W3C bez błędów | S |
| P2-4 | Daty przyszłe w „najnowszych” | posiedzenia planowane osobno („zaplanowane”) | `/start/` `latest` bez dat > dziś | S |
| P2-5 | Dublowane etykiety filtrów | nazwy rodzajów (komisja, głosowanie PE) | brak powtórzonych etykiet | S |
| P2-6 | Pisownia nazwisk z PE wersalikami | normalizacja do „Daniel Obajtek” | wyszukiwarka zwraca jednolitą pisownię | S |
| P2-7 | Scalanie zamawiających | jeden węzeł na NIP zamawiającego | drzewo Orlenu: liczba organów = liczba unikalnych NIP | S |
| P2-8 | Sygnały czasowe obiecane, puste | wdrożyć S1-S3 z PRZESZLOSC_ZRODLA_DANYCH z tłem statystycznym | `signals` niepuste dla co najmniej jednej spółki testowej, z etykietą „zbieżność” | L |

## 5. Co jest już świetne
- Łączenie zamówień z podmiotem po NIP z polem `matched_by` i odnośnikiem do TED; nazwy bez identyfikatora trzymane osobno jako „niepowiązane”.
- Notki prawne w samych danych („Funkcje w KRS to kontekst osoby, nie dowód winy”, „Kwoty z ogłoszeń, nie z umów”).
- Głosowania imienne z linkiem do każdego głosu i odstępstwa od klubu; dane europosłów (deklaracje, dochody z kwotami, 680 głosowań Obajtka w PE, licencja ODbL podana).
- Eksport profilu CSV/JSON z nazwą pliku z datą; przypis i odnośnik do archiwum w panelu.
- Dostępność podstawowa: `lang="pl"`, skip link, widoczny fokus, brak przewijania poziomego na 390.
- Osoby prywatne nie występują z nazwiskiem (`private_names` maskowane w drzewie).

## 6. Ryzyka prawne i etyczne
1. **Zniesławienie przez sumę i sąsiedztwo:** nazwisko byłego prezesa obok „1091 mld zł” i zamówień spoza jego kadencji (P0-1, P0-2). Wystarczy zrzut ekranu w mediach społecznościowych.
2. **Insynuacja w temacie z zarzutami karnymi:** graf „Kołodziejczak” zestawia sprawę z podmiotami innych osób (P0-3). Domniemanie niewinności wymaga oddzielenia kontekstu od tematu.
3. **Dopasowania automatyczne po nazwisku** (materiały) przy deklaracji „Nic nie łączymy po samym nazwisku” - niespójność komunikatu z praktyką; ryzyko imienników.
4. **Brak widocznej ścieżki sprostowania** (art. 31a prawa prasowego dotyczy prasy, ale RODO art. 16 i dobre praktyki wymagają łatwej drogi poprawki).
5. **Przypisanie kont X przez Wikidata** bez ręcznego potwierdzenia: błędne konto = cudze słowa w profilu i w diagnozie.
6. **Balans źródeł:** pierwszy ekran i dominujące źródła materiałów (TV Republika, wPolsce24) mogą zostać odebrane jako stronniczość narzędzia; potrzebna informacja o doborze kanałów i równowaga.
7. **Linki do rejestr.io jako „oficjalnego rejestru”** - wprowadza w błąd co do źródła i kieruje ruch do komercyjnego konkurenta.

## 7. Czego nie zweryfikowałem
- Działania alertów e-mail i treści listu (nie zapisywałem się).
- Działania przycisku przypisu i formatu przypisu w interfejsie (sprawdziłem tylko kod).
- Czy rekordy TED 157377-2026 i 728541-2025 mają w oryginale te kwoty (zapytania tylko do przeszłość.today); błąd może leżeć u źródła lub w parserze, ale w obu przypadkach narzędzie powinno go oznaczyć.
- Dat powołania i odwołania Obajtka w odpisie KRS (podaję je z pamięci prasowej) i powiązania Tuska z Fundacją „Ateny 2004 Floret Kobiet”.
- Właściciela konta X `@ekolodziejczak_`.
- Martwych linków masowo; czytników ekranu na żywo; warstwy „Wpływ na narrację” (domyślnie wyłączona, nie włączałem).
- Cennika rejestr.io w planie Basic (strona zwróciła 403, kopia Firecrawl z 9.10.2026 niejednoznaczna); ceny Maltego tylko z zestawień zewnętrznych.

Źródła konkurencji: [rejestr.io/cennik](https://rejestr.io/cennik), [OpenCorporates pricing](https://opencorporates.com/pricing/), [Aleph Pro](https://aleph.discourse.group/t/aleph-pro-powering-the-next-generation-of-investigations/224), [Maltego pricing (zestawienie)](https://ethicalhacking.ai/pricing/maltego-pricing), [Maltego plans](https://www.maltego.com/pricing-plans/), [Hunchly pricing](https://www.hunch.ly/pricing).
