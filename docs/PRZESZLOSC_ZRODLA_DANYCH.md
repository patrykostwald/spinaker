# Źródła danych przeszłość.today - katalog dla narzędzia OSINT

Stan na 8.10.2026. Uzupełnia: `docs/PRZESZLOSC_KW_LICENCJA.md` (księgi wieczyste), `backend/news/pracownia_osint.py` (FEATURES, LEGAL),
`backend/scraper/public_records.py` i `backend/scraper/nowe_zrodla.py` (co już zbieramy), `backend/news/drzewo_pieniedzy.py` (drzewo v1).
To nie jest opinia prawna. **[P]** pewne (źródło, data), **[DP]** do potwierdzenia.

---

## 1. Podsumowanie

1. Najbardziej wartościowe dla dziennikarza śledczego jest połączenie: KRS + zamówienia (BZP, TED) + dotacje (FTS, Kohesio, lista beneficjentów, SUDOP) + nieruchomości (RCN, działki, KW wpisywane przez użytkownika).
2. Z tego mamy już: KRS (API MS, zmiany obserwowanych podmiotów), TED, BZP (adapter wyłączony), FTS, Kohesio, Sejm, lobbing, PKW, oświadczenia Sejmu (indeks), Wikidata, rejestr przejrzystości UE.
3. Największe braki o wysokiej wartości i niskim ryzyku: SUDOP (pomoc publiczna po NIP), Biała lista VAT (rachunki, statusy), REGON BIR, RCN, lista beneficjentów funduszy 2021-2027, CRU (czekamy na MF), Monitor Sądowy w KRZ (brak API).
4. Księgi wieczyste: brak legalnej drogi hurtowej (art. 36⁴ ust. 8 u.k.w.h.); model „KW przynosi użytkownik” + numery KW z dokumentów publicznych.
5. CRBR: dziś jawny, projekt MF (10-RPW-32532-2026) ogranicza dostęp do „uzasadnionego interesu” od 1.01.2027; dziennikarze zajmujący się praniem pieniędzy mają domniemanie interesu. Trzeba zbudować teraz i przygotować wniosek na 2027.
6. Klucz łączący wszystko to NIP/KRS/REGON dla podmiotów i nr działki/nr KW dla nieruchomości. PESEL nigdy.
7. Osoby: tylko osoby publiczne w związku z funkcją; osoba prywatna w drzewie jest anonimowym węzłem „osoba fizyczna”.
8. Sygnały czasowe (zmiana zarządu przed przetargiem, sprzedaż nieruchomości po dotacji) to zbieżności, nie dowody - język faktów, domniemanie niewinności, prawo do sprostowania.
9. Drzewo przepływu: układ z góry w dół, 6 typów węzłów, krawędzie z datą, kwotą i źródłem, filtry kategorii, oś czasu zmian, limity 300 węzłów.
10. Licencje: rejestry urzędowe = ponowne wykorzystanie na zasadach ustawy o otwartych danych; OpenSanctions CC BY-NC (wymaga licencji komercyjnej), OpenCorporates ODbL + warunki komercyjne, Wikidata CC0.
11. Ryzyko wysokie: KW poza ekw, EGiB z danymi właścicieli, KRZ osób fizycznych (nie-przedsiębiorców), komercyjne bazy KW, scraping portali za Incapsulą (CRU, KRZ).
12. Kolejność 6 miesięcy: miesiąc 1 identyfikatory i NIP-y (BIR, Biała lista, SUDOP), 2 nieruchomości (RCN, działki, KW użytkownika), 3 fundusze 2021-2027 i KPO, 4 orzeczenia i KRZ podmiotów, 5 CRBR i sankcje, 6 sygnały i API dla redakcji.
13. Pisma do instytucji: szkice w `Desktop\projekty\spin-clinic-maile\licencje\` (MS, MC, GUGiK, UODO wstrzymane).
14. Każde nowe źródło przechodzi przez Prawnika (LEGAL) i bramkę `scraper/access_gate.py` (zatwierdzona instrukcja dostępu).
15. Nie zweryfikowano części limitów API i licencji - lista w punkcie 7.

---

## 2. Tabela źródeł

Sortowanie: priorytet (P1 najpierw), potem wartość malejąco, ryzyko rosnąco, nakład rosnąco.
Kolumny: W = wartość dla dziennikarza 1-5; R = ryzyko prawne (n/ś/w); N = nakład podpięcia S/M/L; Repo = stan u nas.

| # | Źródło | Co zawiera | Format / API | Licencja i warunki | Aktualność, limity | RODO | Klucze do drzewa | Repo | N | W | R | Prio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | KRS - API MS (api-krs.ms.gov.pl) | odpisy aktualne i pełne podmiotów, organy, wspólnicy, Biuletyn zmian dziennych | JSON REST bez klucza; ponowne wykorzystanie także przez API (art. 4b ustawy o KRS) | ustawa o otwartych danych [P, art. 49 ustawy z 2021] | bieżąco; limity nieopisane [DP] | osoby w API zamaskowane (inicjały, długość) [P, backend/news/krs.py]; pełne dane na wniosek z podpisem (art. 4b ust. 2) | KRS, NIP, REGON, adres | jest (krs.py, krs_agent, krs_changes) | - | 5 | n | P1 |
| 2 | e-Zamówienia / BZP (UZP) | ogłoszenia, wyniki, wykonawcy, wartości od 130 tys. zł | API tablicy ogłoszeń (mo-board), JSON | informacja publiczna, ponowne wykorzystanie [DP warunki API] | dziennie | wykonawcy JDG = osoby fizyczne | NIP zamawiającego i wykonawcy, nr ogłoszenia | adapter wyłączony (bzp_backfill.py), czeka na instrukcję UZP | M | 5 | n | P1 |
| 3 | TED (UE) | zamówienia ponadprogowe, ogłoszenia o udzieleniu | API v3 search, JSON | ponowne wykorzystanie dozwolone, decyzja KE 2011/833 [DP] | dziennie | nazwy wykonawców | nr ogłoszenia, identyfikator wykonawcy (NIP/VAT) | jest (ted) | - | 5 | n | P1 |
| 4 | Financial Transparency System (KE) | beneficjenci budżetu UE zarządzanego przez KE | CSV/XLSX roczne | CC BY 4.0 [P, nowe_zrodla.py] | rocznie | osoby fizyczne częściowo ukryte | VAT, nazwa, kwota, rok | jest (fts) | - | 4 | n | P1 |
| 5 | Kohesio (KE) | projekty polityki spójności 2014-2020 (i 2021-2027 częściowo) | Socrata JSON | CC0 [P, nowe_zrodla.py] | kwartalnie [DP] | beneficjenci-podmioty | nazwa, kwota, projekt; NIP często brak (łączymy osobno jako „niepowiązane”) | jest (kohesio) | - | 4 | n | P1 |
| 6 | SUDOP (UOKiK) | pomoc publiczna i de minimis wg beneficjenta: kwota, podstawa, organ, data | wyszukiwarka www po NIP (sudop.uokik.gov.pl); eksport/API [DP] | informacja publiczna [DP licencja] | dziennie (aktualizacja nocna) [P wg poradnikprzedsiebiorcy.pl] | JDG i rolnicy = osoby fizyczne | NIP beneficjenta, organ udzielający, data | brak | M | 5 | n | P1 |
| 7 | Biała lista VAT (MF, wl-api.mf.gov.pl) | status VAT, rachunki bankowe, reprezentanci, prokurenci, data rejestracji/wykreślenia | REST JSON bez klucza | jawna z mocy ustawy o VAT art. 96b [DP] | dziennie; limity zapytań typu „search” ograniczone dziennie [DP liczby] | reprezentanci z imienia i nazwiska (bez PESEL dla osób) [DP] | NIP, REGON, KRS, nr rachunku | brak | S | 4 | n | P1 |
| 8 | REGON - GUS BIR1 | dane rejestrowe, PKD, adres, daty, jednostki lokalne | SOAP; klucz na wniosek do GUS [DP adres] | ponowne wykorzystanie, regulamin BIR [DP] | dziennie | JDG = osoby fizyczne; ograniczone | REGON, NIP, KRS, TERYT adresu | brak | S | 4 | n | P1 |
| 9 | Sejm API (api.sejm.gov.pl) | posłowie, głosowania, druki, procesy, interpelacje, wystąpienia, komisje, wideo | REST JSON | informacja publiczna, warunki Kancelarii Sejmu [P, repo] | godzinowo | osoby publiczne | id posła, nr druku, nr procesu, ELI | jest | - | 5 | n | P1 |
| 10 | Rejestr lobbingu MSWiA + lobbing w Sejmie | podmioty wykonujące lobbing, zgłoszenia | HTML/PDF | informacja publiczna | tygodniowo | lobbyści-osoby wpisani jawnie | nazwa, NIP [DP], nr druku | jest (lobby_mswia, lobby_sejm) | - | 4 | n | P1 |
| 11 | PKW - sprawozdania partii i komitetów | przychody, darczyńcy powyżej progów, wydatki kampanii | PDF/XLSX | informacja publiczna | rocznie / po wyborach | darczyńcy-osoby fizyczne jawni z mocy ustawy (imię, nazwisko, miejscowość) [DP zakres] | nazwa partii/komitetu, nr KRS partii z ewidencji | jest (pkw) | - | 4 | ś (darczyńcy) | P1 |
| 12 | Oświadczenia majątkowe Sejm | majątek, nieruchomości (bez adresów), udziały, dochody | PDF skany | jawne z mocy ustawy o wykonywaniu mandatu [DP] | rocznie | osoby publiczne | id posła, nazwy spółek (do KRS) | indeks jest (assets); bez treści | M | 5 | n | P1 |
| 13 | Rejestr Cen Nieruchomości (GUGiK, geoportal) | ceny transakcyjne, data, rodzaj, powierzchnia, działka | usługa geoportalu (WMS/WFS/GML) [DP API] | bezpłatny od 13.02.2026 (Dz.U. 2025 poz. 1542) [P, geoportal.gov.pl] | starostwa przekazują pliki; ok. 320 powiatów [P wg Interii] | bez danych stron [DP] | nr działki (TERYT.obręb.nr), data, cena | brak | M | 4 | n | P1 |
| 14 | Działki i budynki - ULDK / KIEG (GUGiK) | identyfikatory i geometria działek, budynków | REST (ULDK), WMS/WFS | bezpłatne (art. 40a ust. 2 pkt 1 lit. i, j Prawa geodezyjnego) [P]; HVD UE 2023/138 (geoprzestrzenne) [DP] | bieżąco | brak danych osobowych | nr działki, TERYT, współrzędne | brak | S | 4 | n | P1 |
| 15 | Centralny Rejestr Umów (MF, rejestrumow.gov.pl) | umowy jednostek publicznych: strony, kwoty, daty | API tylko dla publikujących; portal za Incapsulą - nie scrapujemy | wniosek o ponowne wykorzystanie wysłany 5.10 [P, pamięć cru-registry] | bieżąco | strony-osoby fizyczne (SU02) | NIP kontrahenta, nr umowy, jednostka | brak (czekamy, ok. 19.10) | M | 5 | ś | P1 |
| 16 | CRBR (MF) | beneficjenci rzeczywiści spółek: imię, nazwisko, obywatelstwo, udziały | wyszukiwarka www; API [DP] | dziś jawny; projekt 10-RPW-32532-2026: od 1.01.2027 tylko uzasadniony interes, domniemanie dla dziennikarzy zajmujących się praniem pieniędzy [P, legeartis 29.09.2026; DP termin] | bieżąco | dane osób fizycznych - wysoka wrażliwość; po 2027 możliwe wyłączenia dla zagrożonych | NIP, KRS spółki | brak | M | 5 | ś (w po 2027 bez zgody) | P2 |
| 17 | Lista beneficjentów funduszy 2021-2027 i KPO (funduszeeuropejskie.gov.pl, kpo.gov.pl) | projekty, wartości, dofinansowanie, beneficjent | XLSX okresowo [DP] | informacja publiczna; art. 49 rozp. 2021/1060 nakazuje publikację [DP] | miesięcznie [DP] | beneficjenci-podmioty | NIP, nazwa, nr projektu | brak (Kohesio tylko częściowo) | S | 5 | n | P2 |
| 18 | Mapa Dotacji UE (mapadotacji.gov.pl) | projekty na mapie, lokalizacje | www, eksport [DP] | [DP] | [DP] | jw. | nr projektu, gmina (TERYT) | brak | S | 3 | n | P3 |
| 19 | Krajowy Rejestr Zadłużonych + Monitor Sądowy i Gospodarczy | upadłości, restrukturyzacje, licytacje, dłużnicy z tytułów egzekucyjnych | brak publicznego API; MS prowadzi analizy API [P wg wyników 8.10]; portal - bez scrapingu | ponowne wykorzystanie [DP] | bieżąco | dłużnicy-osoby fizyczne - wysokie ryzyko; tylko podmioty i osoby publiczne | KRS, NIP, sygnatura | brak | L (po API) | 4 | w (osoby) / n (spółki) | P2 |
| 20 | Portal Orzeczeń Sądów Powszechnych (orzeczenia.ms.gov.pl) | zanonimizowane orzeczenia z uzasadnieniami | API standardowe portali [DP dokumentacja] | ponowne wykorzystanie [DP] | dziennie | anonimizacja po stronie sądu; nie odwracamy | sygnatura, sąd, przepisy, nazwy spółek (często nie anonimizowane) | brak | M | 4 | ś | P2 |
| 21 | SAOS (saos.org.pl) | agregator orzeczeń SP, SN, TK, NSA, KIO | REST API, dumpy | licencja serwisu [DP] | [DP; projekt może być mniej aktualny] | jw. | sygnatura | brak | S | 3 | n | P3 |
| 22 | CBOSA (NSA) | orzeczenia sądów administracyjnych | www; brak API [DP] | [DP] | dziennie | anonimizowane | sygnatura, organ | brak | M | 3 | n | P3 |
| 23 | KIO - orzeczenia | odwołania w zamówieniach | www [DP] | [DP] | bieżąco | podmioty | nr ogłoszenia, NIP | brak | M | 4 | n | P2 |
| 24 | Monitor Polski + Dziennik Ustaw (ELI) | akty, nominacje, obwieszczenia, uchwały | ELI API Sejmu / RCL | informacja publiczna | dziennie | osoby publiczne (nominacje) | ELI, data | jest (ELI) | - | 3 | n | P2 |
| 25 | Monitor Polski B / sprawozdania finansowe | sprawozdania finansowe podmiotów (historycznie MP B; dziś eKRS RDF) | eKRS - Repozytorium Dokumentów Finansowych [DP API] | [DP] | rocznie | brak | KRS | brak | M | 4 | n | P2 |
| 26 | NIK | wyniki kontroli, wystąpienia | RSS + PDF | informacja publiczna | tygodniowo | osoby publiczne (kierownicy jednostek) | nazwa jednostki, NIP [DP], temat | jest (RSS) | S | 4 | n | P2 |
| 27 | UOKiK - decyzje, rejestr klauzul, SUDOP | decyzje antymonopolowe i konsumenckie, kary | www, RSS | informacja publiczna | bieżąco | przedsiębiorcy | NIP, nr decyzji | RSS jest | S | 3 | n | P2 |
| 28 | KNF - lista ostrzeżeń publicznych, rejestry podmiotów | podmioty, wobec których złożono zawiadomienie; licencje | www, CSV [DP] | informacja publiczna | bieżąco | podmioty; osoby rzadko | KRS, NIP | RSS jest | S | 4 | n | P2 |
| 29 | KRRiT | koncesje, nadawcy, struktura właścicielska, decyzje | www, PDF | informacja publiczna | miesięcznie | podmioty | KRS, nr koncesji | brak | M | 3 | n | P3 |
| 30 | Sankcje UE (FSF) + lista MSWiA (ustawa z 13.04.2022) | podmioty i osoby objęte sankcjami | XML/CSV (FSF, wymaga logowania EU Login [DP]); MSWiA www | informacja publiczna; UE - warunki FSF [DP] | bieżąco | osoby z list sankcyjnych - podstawa prawna publikacji jest w aktach | nazwa, KRS/NIP (MSWiA) | brak | S | 4 | n | P2 |
| 31 | OpenSanctions (PEP, sankcje, agregat) | sankcje świata, PEP, powiązania | API, bulk FtM | CC BY-NC 4.0 - użycie komercyjne tylko z licencją [P, pismo 05/12 w spin-clinic-maile] | dziennie | PEP = osoby publiczne | wikidata QID, nazwy, identyfikatory | brak (pismo wysłane) | S | 4 | ś (licencja) | P2 |
| 32 | Wikidata | tożsamości osób publicznych, funkcje, identyfikatory | SPARQL | CC0 [P] | bieżąco | osoby publiczne | QID, id Sejmu, id PE | jest (wikidata) | - | 3 | n | P1 |
| 33 | OpenCorporates | spółki świata, powiązania | API z kluczem | ODbL + warunki; komercyjnie płatne [DP] | różna | podmioty, funkcjonariusze | jurysdykcja + nr rejestru | brak | M | 3 | ś | P3 |
| 34 | Open Ownership / BODS | standard beneficjentów | JSON | CC BY [DP] | - | - | format wymiany | brak | S | 2 | n | P3 |
| 35 | Rejestr przejrzystości UE | lobbyści w UE, spotkania KE | XML | ponowne wykorzystanie KE | tygodniowo | osoby kontaktowe | nazwa, id rejestru | jest (eu_transparency) | - | 3 | n | P1 |
| 36 | Integrity Watch EU, HowTheyVote | europosłowie: dochody, spotkania, głosowania | eksport, API | ODbL [P, repo] | tygodniowo | osoby publiczne | id PE | jest | - | 3 | n | P1 |
| 37 | Oświadczenia samorządowców i zarządów spółek komunalnych (BIP) | majątek radnych, wójtów, prezesów | PDF w tysiącach BIP | jawne z ustaw samorządowych [DP] | rocznie | osoby publiczne | nazwisko + funkcja + JST (TERYT) | brak | L | 4 | ś (skala, błędne dopasowania) | P3 |
| 38 | Senat - oświadczenia, rejestr korzyści | majątek i korzyści senatorów | www/PDF; senat.gov.pl zwraca 403 dla naszego serwera [P, pamięć rss-sources-blocked] | jawne | rocznie | osoby publiczne | id senatora | brak | M | 4 | n (nie obchodzimy blokady; pismo) | P2 |
| 39 | Rejestr Korzyści (Sejm) | korzyści posłów | PDF | jawny z ustawy | rocznie | osoby publiczne | id posła | częściowo (indeks oświadczeń) [DP] | S | 4 | n | P2 |
| 40 | Spółki Skarbu Państwa (KPRM/MAP, wykaz) | lista spółek z udziałem SP, rady nadzorcze | www/XLSX [DP] | informacja publiczna | rocznie | członkowie rad = osoby pełniące funkcje publiczne [DP] | KRS | brak | S | 4 | n | P2 |
| 41 | CEIDG (dane.biznes.gov.pl, API) | JDG: firma, NIP, adres, PKD, status | REST z tokenem (konto biznes.gov.pl), hurtownia danych | bezpłatne [P wg poradnikprzedsiebiorcy.pl]; warunki [DP] | dziennie | każdy wpis = osoba fizyczna; tylko gdy JDG jest stroną umowy/zamówienia | NIP, REGON | brak | S | 3 | ś | P2 |
| 42 | Rejestr Partii Politycznych (SO w Warszawie, ewidencja) | partie, statuty, organy | www [DP] | jawna | rzadko | osoby publiczne | nr ewidencyjny partii | brak | S | 3 | n | P3 |
| 43 | Rejestr Zabytków (NID) | zabytki nieruchome z działkami | dane.gov.pl CSV/WFS | ponowne wykorzystanie [DP licencja] | kwartalnie [DP] | brak | nr działki, TERYT | brak | S | 2 | n | P3 |
| 44 | TERYT (GUS) | kody gmin, ulic, adresów | API TERYT WS1 z kontem [DP] | ponowne wykorzystanie | miesięcznie | brak | TERYT | brak | S | 3 | n | P1 (infrastruktura) |
| 45 | ZUS / KRUS / NFZ agregaty | statystyki, umowy NFZ ze świadczeniodawcami | dane.gov.pl, www NFZ | ponowne wykorzystanie | różnie | NFZ: świadczeniodawcy-podmioty | NIP/REGON świadczeniodawcy, kwoty umów | brak | M | 3 | n | P3 |
| 46 | dane.gov.pl (katalog) | tysiące zbiorów JST i urzędów | API 1.4 | wg zbioru | różnie | wg zbioru | wg zbioru | jest (Zwiadowca) | - | 3 | n | P1 |
| 47 | EGiB (starostwa) | działki, budynki, właściciele | WMS, wypisy | dane bez osób - każdy, odpłatnie wg tabel; dane właścicieli tylko z interesem prawnym (art. 24 ust. 5) [P] | bieżąco | właściciele - wysokie ryzyko | nr działki, nr KW [DP] | brak | L | 4 | w (z osobami) | P4 / tylko bez osób |
| 48 | Księgi wieczyste | własność, hipoteki, ostrzeżenia | brak legalnego hurtu; „KW przynosi użytkownik” | patrz PRZESZLOSC_KW_LICENCJA.md | - | wysokie | nr KW, nr działki, KRS/NIP właściciela-podmiotu | brak | M (model użytkownika) | 5 | w (hurt) / n (użytkownik) | P2 (model użytkownika) |

---

## 3. Mapa kluczy i relacji

### Węzły
| Typ | Identyfikator główny | Pomocnicze | Źródła |
|---|---|---|---|
| Osoba publiczna | nasz id + Wikidata QID, id Sejmu/Senatu/PE | funkcja, okres | Sejm, Wikidata, KRS (dopasowanie potwierdzone ręcznie), PKW |
| Osoba fizyczna niepubliczna | brak - węzeł anonimowy „osoba fizyczna” | rola w relacji | KRS, CRBR, CEIDG - nazwiska nie pokazujemy |
| Podmiot (spółka, fundacja, partia, JST, urząd) | KRS albo NIP | REGON, VAT UE, TERYT (JST) | KRS, BIR, Biała lista, CEIDG |
| Nieruchomość | nr działki (TERYT.obręb.numer) | nr KW, adres | ULDK, RCN, BIP, użytkownik (KW) |
| Umowa / zamówienie | nr ogłoszenia BZP/TED, nr umowy CRU | CPV, wartość | BZP, TED, CRU, KIO |
| Wypłata (dotacja, pomoc, fundusz) | nr projektu / id pomocy SUDOP | program, organ | FTS, Kohesio, lista beneficjentów, SUDOP |
| Organ / instytucja | NIP / REGON jednostki | TERYT | BIP, BZP (zamawiający) |
| Dokument / zdarzenie | ELI, nr druku, sygnatura | data | Sejm, ELI, orzeczenia, NIK, UOKiK |

### Krawędzie (każda: data od-do, kwota jeśli dotyczy, źródło z URL i datą pobrania, pewność)
```
osoba ──pełni funkcję (KRS: organ, od, do)──▶ podmiot
osoba ──jest beneficjentem rzeczywistym (CRBR)──▶ podmiot
podmiot ──udziałowiec (KRS)──▶ podmiot
organ ──zamawia (BZP/TED: nr, wartość)──▶ umowa ──wykonawca──▶ podmiot
organ ──zawiera umowę (CRU: nr, kwota)──▶ podmiot
organ/program ──wypłaca (FTS/SUDOP/beneficjenci: kwota, data)──▶ podmiot
podmiot ──jest właścicielem / użytkownikiem wiecz. (KW od użytkownika, BIP)──▶ nieruchomość
nieruchomość ──transakcja (RCN: data, cena)──▶ nieruchomość (ta sama działka w czasie)
podmiot ──ma hipotekę na rzecz (KW dział IV, od użytkownika)──▶ podmiot (bank)
osoba ──głosuje / zgłasza / mówi (Sejm)──▶ dokument
podmiot ──lobbuje (rejestr)──▶ dokument
podmiot ──jest stroną (orzeczenie, KIO, decyzja UOKiK/KNF)──▶ dokument
podmiot ──współdzieli adres / rachunek (BIR, Biała lista)──▶ podmiot
```
Zasada łączenia: tylko po identyfikatorze (KRS, NIP, REGON, nr działki, nr KW, nr ogłoszenia, nr umowy). Sama nazwa = „niepowiązane”, poza sumami (tak jak w `drzewo_pieniedzy.py`). PESEL niedostępny i niezbierany.

---

## 4. Sygnały na osi czasu

Każdy sygnał to **zbieżność w czasie**, nie dowód. Pokazujemy: oba zdarzenia ze źródłem, odstęp w dniach, ile podobnych zbieżności zdarza się przypadkiem w tej samej kategorii (tło), etykieta „zbieżność - nie świadczy o naruszeniu prawa”. Bez słów „afera”, „podejrzany”, „ukrywa”. Ta sama miara dla wszystkich stron.

| # | Sygnał | Zdarzenia | Okno | Uwagi o tle |
|---|---|---|---|---|
| S1 | Zmiana zarządu lub wspólników przed przetargiem | KRS zmiana → BZP/TED wybór wykonawcy | 0-180 dni | zmiany zarządu są częste; pokazać odsetek wśród wszystkich wykonawców |
| S2 | Nowa spółka szybko wygrywa zamówienie | data rejestracji KRS/REGON → udzielenie | < 365 dni | spółki celowe są normalne w budownictwie |
| S3 | Wypłata dotacji/pomocy, potem zbycie nieruchomości | SUDOP/FTS/beneficjenci → RCN transakcja działki podmiotu albo zmiana w KW (od użytkownika) | 0-365 dni | wymaga powiązania działki z podmiotem kluczem, nie adresem |
| S4 | Umowa CRU z podmiotem powiązanym z osobą publiczną | KRS funkcja osoby → CRU umowa z jednostką, w której osoba pełni funkcję | w trakcie funkcji | powiązanie ≠ konflikt interesów; prawo do odpowiedzi |
| S5 | Zbieżność adresów lub rachunków | BIR/Biała lista: ten sam adres/rachunek u wykonawcy i innego oferenta | jednocześnie | biura rachunkowe i wirtualne biura dają fałszywe trafienia - pokazać, ile podmiotów pod adresem |
| S6 | Darowizna na partię, potem zamówienie lub dotacja | PKW darczyńca-podmiot/osoba publiczna → BZP/SUDOP | 0-730 dni | darczyńcy-osoby prywatne nie są łączone |
| S7 | Lobbing przed zmianą ustawy | rejestr lobbingu / OSR → poprawka → głosowanie | 0-180 dni | zgodnie z pilotażem lobbingu: bliźniacze teksty silniejsze niż deklaracje |
| S8 | Zmiana statusu VAT / wykreślenie po wypłacie | Biała lista → po FTS/SUDOP/CRU | 0-365 dni | wykreślenie bywa techniczne |
| S9 | Upadłość wykonawcy w trakcie umowy publicznej | KRZ (podmiot) → aktywna umowa BZP/CRU | w trakcie | tylko podmioty |
| S10 | Nominacja (MP, rada nadzorcza SSP) po decyzji, głosowaniu lub wpłacie | Sejm/PKW → KRS rada nadzorcza SSP | 0-365 dni | nominacje są jawne i polityczne z natury - pokazać tło dla wszystkich klubów |
| S11 | Wzrost wartości majątku w oświadczeniu | rok do roku | 1 rok | spadki i wzrosty dla wszystkich posłów jednakowo |

Ostrzeżenia w interfejsie: korelacja ≠ przyczynowość; domniemanie niewinności (art. 42 ust. 3 Konstytucji); każdy sygnał ma przycisk „zgłoś sprostowanie” i trafia do rejestru korekt; sygnały o osobach publicznych tylko w związku z funkcją; sygnał nigdy nie jest publikowany automatycznie w mediach społecznościowych.

---

## 5. Widok „Drzewo przepływu” - specyfikacja

**Układ.** Z góry w dół: źródło pieniędzy (program, organ, budżet UE) → kanał (umowa, zamówienie, dotacja, pomoc) → odbiorca (podmiot) → co dalej (nieruchomość, podmiot zależny, osoba publiczna z funkcją). Korzeń wybiera użytkownik: osoba publiczna, podmiot (KRS/NIP), nieruchomość (nr działki/KW) albo temat.

**Węzły** (jeden kształt i kolor na typ, Similarity): osoba publiczna (koło), osoba fizyczna anonimowa (koło szare bez podpisu), podmiot (prostokąt), nieruchomość (KW) (dom), umowa/zamówienie (dokument), wypłata (moneta), organ (budynek z kolumnami). Podpis w jednej linii, skrót nazwy, pełna nazwa w panelu.

**Krawędzie.** Strzałka w kierunku przepływu; grubość ∝ log(kwota); etykieta: data albo zakres dat i kwota; kolor szary dla relacji bez kwoty. Kliknięcie: panel z źródłem (URL, licencja, data pobrania), pewnością (identyfikator / potwierdzone ręcznie / niepowiązane) i datą ostatniej zmiany.

**Filtry kategorii** (przełączniki nad drzewem, najwyżej 6, Hick): nieruchomości · spółki · dotacje i fundusze · zamówienia publiczne · polityka i lobbing · orzeczenia. Dodatkowo: zakres dat, próg kwoty, „pokaż niepowiązane”.

**Oś czasu.** Pod drzewem, stała wysokość (strefa nie skacze); punkty zdarzeń (zmiana w KRS, umowa, wypłata, transakcja RCN, wpis KW od użytkownika, orzeczenie); suwak zakresu filtruje drzewo; sygnały S1-S11 jako łączniki między dwoma punktami z etykietą „zbieżność”.

**Wydajność.** Najwyżej 300 węzłów i 600 krawędzi naraz; powyżej - grupowanie („42 umowy z gminą X”, rozwijane); głębokość domyślnie 2, maks. 3; zapytanie poniżej 400 ms dla stopnia 1 z indeksu (Doherty), dalsze stopnie doładowywane; cache wyniku 24 h; eksport CSV/JSON/FtM.

**Wyłączniki prawne** (twarde, w kodzie, nie w UI):
1. Osoba niepubliczna nigdy z nazwiskiem; brak wyszukiwania po osobie niepublicznej.
2. Dane KW tylko z teczki użytkownika (prywatnie) albo z dokumentu publicznego z linkiem; zero pobrań z ekw przez serwer.
3. CRBR po 1.01.2027 tylko dla kont z potwierdzonym uzasadnionym interesem (jeśli przepisy wejdą).
4. KRZ: tylko podmioty i osoby w roli publicznej.
5. Źródło z licencją NC lub bez licencji - ukryte w trybie komercyjnym, dopóki nie ma umowy.
6. Każdy węzeł z prośbą o sprostowanie oznaczony; usunięcie na wniosek, gdy brak podstawy prawnej.
7. Logi dostępu do węzłów osób publicznych (rozliczalność RODO), bez profilowania czytelników.

---

## 6. Kolejność wdrażania - 6 miesięcy

| Miesiąc | Zakres | Źródła | Nakład |
|---|---|---|---|
| 1 (X 2026) | Identyfikatory: każdy podmiot w drzewie z NIP/REGON/KRS; statusy VAT i rachunki; pomoc publiczna | BIR, Biała lista, SUDOP; włączenie BZP po instrukcji UZP | 3×S + M |
| 2 (XI) | Nieruchomości: działki, ceny transakcyjne, pole „numer KW” i odpis w teczce, numery KW z BIP | ULDK, RCN, model KW użytkownika; pisma KW (MS, MC, GUGiK) | 2×M |
| 3 (XII) | Fundusze 2021-2027 i KPO; spółki Skarbu Państwa | lista beneficjentów, KPO, wykaz SSP; CRU jeśli MF da klucz | S + M |
| 4 (I 2027) | Orzeczenia i ryzyko: KIO, Portal Orzeczeń, KRZ podmiotów (gdy API), KNF ostrzeżenia, UOKiK decyzje | | 2×M |
| 5 (II) | Beneficjenci i sankcje: CRBR (zgodnie z nowymi zasadami), sankcje UE/MSWiA, OpenSanctions po licencji | | 2×M |
| 6 (III) | Sygnały S1-S11 z tłem statystycznym, panel sprostowań, API dla redakcji, eksport FtM | | L |

Po każdym miesiącu: Prawnik (LEGAL), Dziennikarz testowy (Pracownia OSINT), pomiar czasu odpowiedzi drzewa.

---

## 7. Czego nie zweryfikowano

- Limity wl-api (Biała lista) i dokładne warunki BIR (adres wniosku o klucz).
- Czy SUDOP ma eksport/API i jaką licencję.
- Dokumentacja API Portalu Orzeczeń i aktualność SAOS.
- Warunki API e-Zamówień dla pobierania hurtowego (instrukcja UZP).
- Czy RCN udostępnia usługę pobierania (WFS/GML) dla całego kraju i jakie pola.
- Format i częstotliwość listy beneficjentów 2021-2027 i KPO.
- Warunki FSF UE (logowanie) i format listy MSWiA.
- Licencje OpenCorporates, Open Ownership, SAOS, Rejestru Zabytków.
- Zakres jawnych danych darczyńców PKW i oświadczeń samorządowych.
- Etap projektu CRBR (10-RPW-32532-2026) i daty wejścia w życie (artykuł mówi o 1.01.2027, wcześniejsze wersje o 1.07.2026).
- Czy MS udostępni API KRZ i kiedy.
- Pełna lista rejestrów KNF i KRRiT z formatami.

## Źródła sprawdzone 8.10.2026

- u.k.w.h. t.j. Dz.U. 2026 poz. 1066; rozp. Dz.U. 2026 poz. 410, 411; odpowiedź MS dla RPO 9.04.2026 (szczegóły w PRZESZLOSC_KW_LICENCJA.md)
- Ustawa o otwartych danych Dz.U. 2021 poz. 1641 (art. 4-6, 39-43, art. 49 - art. 4b ustawy o KRS)
- Prawo geodezyjne t.j. Dz.U. 2024 poz. 1151 (art. 24 ust. 4-5, art. 40a); RCN: https://www.geoportal.gov.pl/aktualnosci/nowelizacja-ustawy-prawo-geodezyjne-i-kartograficzne-opublikowana-w-dzienniku-ustaw-2/
- CRBR: https://czasopismo.legeartis.org/2026/09/udostepnianie-danych-beneficjentow-rzeczywistych-crbr-wniosek-wykazanie-uzasadnionego-interesu-projekt-aml/ ; https://www.prawo.pl/prawo/crbr-koniec-jawnosci-dla-kazdego,532591.html ; https://www.gov.pl/web/finanse/centralny-rejestr-beneficjentow-rzeczywistych
- KRZ API: https://iws.gov.pl/wp-content/uploads/2024/11/2024_PrawaP_K_Switala_Rozwiazania-legislacyjno-organizacyjne-zapewniajace-udostepnienie-danych.pdf
- SUDOP: https://poradnikprzedsiebiorcy.pl/-system-udostepniania-danych-o-pomocy-publicznej-sudop-co-zawiera
- CEIDG hurtownia: https://poradnikprzedsiebiorcy.pl/-hurtownia-danych-ceidg-do-czego-sluzy
- SAOS API: https://saos.org.pl/help/index.php/dokumentacja-api
- Repo: backend/scraper/public_records.py, backend/scraper/nowe_zrodla.py, backend/news/krs.py, backend/news/drzewo_pieniedzy.py, backend/scraper/bzp_backfill.py
