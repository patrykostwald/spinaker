# Księgi wieczyste w przeszłość.today - oficjalne drogi dostępu

Stan na 8.10.2026. Operator: iapply sp. z o.o. (kontakt@iapply.pl).

> **To nie jest opinia prawna.** To zestawienie przepisów i stanowisk urzędów z publicznych źródeł. Przed pierwszym
> wnioskiem do Ministerstwa Sprawiedliwości warto 1 godzinę konsultacji u prawnika (RODO + ustawa o otwartych danych + u.k.w.h.).

Oznaczenia: **[P]** pewne (źródło, data sprawdzenia), **[DP]** do potwierdzenia.

---

## 0. Wniosek w 10 liniach

1. Dziś każdy, kto zna numer KW, przegląda ją bezpłatnie i bez logowania - pojedynczo, ręcznie (art. 36⁴ ust. 6 u.k.w.h.; § 17 ust. 2 rozp. MS z 24.03.2026, Dz.U. 2026 poz. 411). [P, 8.10.2026]
2. **Nie istnieje żadna legalna droga masowego ani zautomatyzowanego dostępu do KW dla firmy ani redakcji.** Brak API, brak licencji hurtowej, brak trybu „dla dziennikarzy” w u.k.w.h. i rozporządzeniach. [P dla przepisów; DP, czy MS ma niepublikowane porozumienia]
3. Wyszukiwanie w Centralnej Bazie Danych KW (po osobie, po nieruchomości) mają tylko 28 kategorii podmiotów publicznych i notariusze (art. 36⁴ ust. 8). Media, NGO i firmy nie są na liście. [P]
4. MS w odpowiedzi dla RPO (9.04.2026, DL-II.41.24.2026) nazywa masowe pobieranie z KW „pozaprawnym” i zapowiada uwierzytelnianie (projekt UD310). Rozszerzenie listy uprawnionych - „wymaga pogłębionych analiz”, ewentualnie osobne prace w przyszłości. [P]
5. Wniosek o ponowne wykorzystywanie (ustawa o otwartych danych, art. 39) jest formalnie możliwy; spodziewana odmowa z powodu RODO i art. 36³ ust. 2 u.k.w.h. Odmowa = decyzja, od której przysługuje odwołanie do ministra cyfryzacji i skarga do WSA. [P co do trybu; DP co do wyniku]
6. Najmocniejszy zawężony wniosek: dane z działów I i II tylko tam, gdzie właścicielem jest Skarb Państwa, JST lub osoba prawna (RODO nie chroni osób prawnych). [DP - ocena prawnika]
7. Legalne źródła numerów KW już dziś: wykazy i ogłoszenia o zbyciu nieruchomości publicznych w BIP (art. 35 u.g.n.), obwieszczenia o licytacjach komorniczych, uchwały JST. [DP brzmienie przepisów]
8. Legalne dane obok KW: Rejestr Cen Nieruchomości bezpłatny od 13.02.2026 (Dz.U. 2025 poz. 1542), identyfikatory i geometria działek bezpłatne (art. 40a ust. 2 pkt 1 lit. i Prawa geodezyjnego). [P]
9. Dane właścicieli z EGiB tylko dla właścicieli, organów, sądów i osób z interesem prawnym (art. 24 ust. 5 Prawa geodezyjnego). Dziennikarz zwykle go nie ma. [P przepis; DP praktyka]
10. Model produktu teraz: „KW przynosi użytkownik” - dziennikarz sam wpisuje numer, sam otwiera ekw.ms.gov.pl albo dołącza kupiony odpis do prywatnej teczki; my łączymy to z danymi jawnymi. Zero pobierania z ekw przez nasze serwery.

---

## 1. Stan prawny (a) - jakie drogi istnieją

| Droga | Kto może | Masowo? | Koszt | Źródło |
|---|---|---|---|---|
| Przeglądanie KW (ekw.ms.gov.pl) | każdy, kto zna numer | nie; CI może limitować zapytania z jednego IP i wydłużać czas dostępu (§ 17 ust. 5) | 0 zł | art. 36⁴ ust. 5-7 u.k.w.h. (t.j. Dz.U. 2026 poz. 1066); § 17 rozp. Dz.U. 2026 poz. 411 [P] |
| Odpis / wyciąg elektroniczny | każdy | nie (wniosek na księgę) | odpis zwykły 30 zł, zupełny 75 zł, wyciąg 10-40 zł; papierowo 45/90 zł | § 2 rozp. MS z 24.03.2026, Dz.U. 2026 poz. 410 [P] |
| Weryfikacja pobranego odpisu (identyfikator) | każdy | nie | 0 zł | § 19 rozp. 411 [P] |
| Wyszukiwanie w CBDKW (po osobie z działu II, po nieruchomości, po numerze dziennika) | tylko art. 36⁴ ust. 8: sądy, prokuratura, KAS, organy egzekucyjne i podatkowe, komornicy, Policja, NIK, służby, ZUS, KRUS, PGRP, notariusze, KOWR, GIIF, KZN, CPK, PKP PLK, GDDKiA i inne (28 pozycji) | tak, po zgodzie MS (decyzja) | 30 zł za wniosek, wiele podmiotów zwolnionych (art. 36⁵ ust. 3) | art. 36⁴ ust. 8-15; § 20-23 rozp. 411 [P] |
| Dane działów I i II dla katastru | organy prowadzące kataster (starostowie) | tak, bez prawa udostępniania dalej | 0 zł | art. 36⁴ ust. 16 [P] |
| Akta KW (dokumenty w sądzie) | interes prawny, notariusz | nie | - | art. 36¹ [P] |
| API / hurtowy eksport / licencja | **brak w przepisach** | - | - | nie znaleziono w u.k.w.h., rozp. 410, 411, 740 [P dla tekstów; DP czy MS nie planuje] |
| Konto instytucjonalne (po UD310) | osoby prawne i organy przez Portal Rejestrów Sądowych | nie - to logowanie do przeglądania, nie hurt | 0 zł | odpowiedź MS dla RPO 9.04.2026 [P] |
| Prawo prasowe art. 4 | redakcja pyta organ o konkretną informację | nie | 0 zł | DP: u.d.i.p. art. 1 ust. 2 - odrębne ustawy (u.k.w.h.) mają pierwszeństwo, więc treści KW tą drogą raczej nie dostaniemy |
| Wniosek o informację publiczną (u.d.i.p.) | każdy | nie | 0 zł | dobry do pytań o tryby, statystyki, stan UD310; nie do treści KW [DP] |
| Wniosek o ponowne wykorzystywanie (ustawa o otwartych danych, art. 39, także ust. 2: dostęp stały w czasie rzeczywistym) | każdy | teoretycznie tak | oferta albo decyzja | Dz.U. 2021 poz. 1641, art. 39-43 [P tryb]; ograniczenia art. 6 ust. 2-3 (prywatność, ograniczenia z innych ustaw) [P]; wynik [DP] |

### Projekt UD310 (nowelizacja u.k.w.h.)
- Cel: obowiązkowe uwierzytelnienie przed przeglądaniem KW (Węzeł Krajowy - profil zaufany, mObywatel, bankowość; albo konto PRS, także instytucjonalne), raz na sesję. [P - odpowiedź MS dla RPO, 9.04.2026]
- Uzasadnienie MS: „przeciwdziałanie zjawisku masowego, nieuprawnionego pozyskiwania danych z tego rejestru przez podmioty trzecie, w szczególności przy wykorzystaniu zautomatyzowanych narzędzi”, komercyjne wyszukiwarki po osobie jako problem. [P, tamże]
- Logi: IP, PESEL, numer księgi, data i godzina - przechowywane 5 lat, dostęp dla sądów, prokuratury, Policji. [P wg prawo.pl 4.12.2025; DP w ostatecznym tekście]
- Etap: konsultacje zakończone (grudzień 2025), wystąpienie RPO 6.03.2026 (IV.7000.57.2026.MN), odpowiedź MS 9.04.2026; brak wpisu w wykazie prac RM wg Interii. [P dla dat; DP dla bieżącego etapu - sprawdzić legislacja.gov.pl]
- MS zapowiada analizy Instytutu Wymiaru Sprawiedliwości o zakresie danych w CI KW i ograniczeniu podmiotowym dostępu. [P]
- Skutek dla nas: każda automatyzacja na ekw będzie identyfikowalna i sprzeczna z celem ustawy. Potwierdza zakaz scrapingu.

### Zmiany 2026 już obowiązujące
- Dz.U. 2026 poz. 119 (ustawa z 9.01.2026, w życie 31.03.2026) - pobieranie odpisów jako dokumentów elektronicznych; nowe rozporządzenia 410 i 411 z 24.03.2026. [P]
- Dz.U. 2026 poz. 740 - nowy załącznik o strukturze KW (od 1.07.2026). [P]
- Tekst jednolity u.k.w.h.: Dz.U. 2026 poz. 1066 (stan na 21.07.2026). [P]

## 2. Kto jest właściwy (b)

| Sprawa | Komórka | Kanał | Termin ustawowy | Stan |
|---|---|---|---|---|
| Informacja publiczna (tryby, UD310, statystyki) | MS, Biuro Komunikacji i Promocji | informacja.publiczna@ms.gov.pl, ePUAP, Al. Ujazdowskie 11, 00-950 Warszawa; status: 22 23-90-384 | 14 dni, max 2 mies. (u.d.i.p. art. 13) | [P, gov.pl/web/sprawiedliwosc/kontakt-informacja-publiczna, 8.10.2026] |
| Ponowne wykorzystywanie | MS (decyzje wydaje Dyrektor BKiP z upoważnienia) | jak wyżej, wniosek z art. 39 | 14 dni, max 2 mies. (art. 40) | [P tryb; DP kto podpisuje w 2026] |
| Techniczne pytania KW | Centralna Informacja KW, Departament Informatyzacji i Rejestrów Sądowych MS | ekw@ms.gov.pl, ul. Czerniakowska 100, 00-454 Warszawa, 22 39 76 515 | brak (korespondencja) | [P, gov.pl/web/sprawiedliwosc/elektroniczna-ksiega-wieczysta-kontakt] |
| Odwołanie od odmowy ponownego wykorzystania | minister właściwy do spraw informatyzacji | przez MS (k.p.a.) | 14 dni od doręczenia | art. 43 ustawy o otwartych danych [P] |
| Skarga | WSA w Warszawie | przez organ | 30 dni; WSA rozpatruje w 30 dni | art. 43 ust. 3 [P] |
| Sądy rejonowe, wydziały KW | nie dotyczy - treść KW udostępnia CI; akta tylko z interesem prawnym | - | - | [P] |
| Naczelna Rada Notarialna | nie dotyczy - notariusze mają dostęp do CBDKW wyłącznie do czynności notarialnych, nie mogą go odstępować | - | - | [P co do art. 36⁴ ust. 8 pkt 18; DP zakaz odstępowania w regulaminach] |

**Wymagane dokumenty przy wniosku o ponowne wykorzystywanie** (art. 39 ust. 3): nazwa podmiotu zobowiązanego, dane wnioskodawcy z adresem (iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań, KRS 0001133291), wskazanie informacji, cel i rodzaj działalności (produkty, usługi), forma i format danych, sposób przekazania albo sposób i okres dostępu przy dostępie stałym. Podpis osoby reprezentującej spółkę (zalecany kwalifikowany albo profil zaufany przez ePUAP). Braki: 7 dni na uzupełnienie. [P]

## 3. Wymogi po naszej stronie (c)

- **RODO.** KW zawierają imiona, nazwiska, PESEL, dane wierzycieli i ostrzeżeń egzekucyjnych. MS przetwarza je na podstawie art. 6 ust. 1 lit. c i e RODO; my potrzebowalibyśmy własnej podstawy (lit. f, interes prawnie uzasadniony) i testu równowagi. [P stanowisko MS; DP nasza podstawa]
- **Dziennikarski wyjątek** (art. 85 RODO, art. 2 ustawy o ochronie danych osobowych 2018) dotyczy działalności dziennikarskiej. iapply jako dostawca narzędzia - raczej procesor dziennikarza dla jego teczki (umowa powierzenia), a nie administrator bazy osób. [DP - kluczowe pytanie do prawnika]
- **Osoby publiczne vs prywatne.** Ustawa o otwartych danych art. 6 ust. 2: ograniczenie z powodu prywatności nie dotyczy informacji o osobach pełniących funkcje publiczne w związku z tymi funkcjami. Majątek nieruchomy polityka jest już jawny w oświadczeniach majątkowych (bez adresów i numerów KW). [P przepis]
- **Zasady ponownego wykorzystania.** Warunki podmiotu (art. 41) mogą wymagać: wskazania źródła, daty pozyskania, zakazu modyfikacji, zakazu łączenia z danymi osobowymi z innych zbiorów. [P tryb; DP konkretne warunki MS]
- **Obowiązek informacyjny** (art. 14 RODO) przy danych z KW osób prywatnych - wyjątek „niewspółmierny wysiłek” jest wąski. Tym bardziej: osób prywatnych nie profilujemy (LEGAL w backend/news/pracownia_osint.py). [DP]
- **DPIA** przed każdym wdrożeniem funkcji z danymi KW - obowiązkowa przy łączeniu zbiorów na dużą skalę (art. 35 RODO). Konsultacja z UODO tylko gdy DPIA wykaże wysokie ryzyko szczątkowe (art. 36). [P przepis]
- **PESEL nigdy** - nie przechowujemy, nie pokazujemy, nie dopasowujemy.

## 4. Gdzie się zgłosić (d)

| # | Instytucja | Po co | Kolejność | Szkic |
|---|---|---|---|---|
| 1 | Ministerstwo Sprawiedliwości (BKiP + CI KW w DW) | tryby dostępu, UD310, warunki ponownego wykorzystania, KRZ API | teraz | `licencje/01-ms-ksiegi-wieczyste.md` |
| 2 | Minister Cyfryzacji - zespół Programu otwierania danych | czy CBDKW, KRZ, EGiB są w planie otwierania danych; organ odwoławczy | teraz | `licencje/02-mc-otwieranie-danych.md` |
| 3 | GUGiK (Główny Geodeta Kraju) | RCN i działki: API, licencja, zakres; EGiB i numery KW w ewidencji | teraz | `licencje/03-gugik-rcn-egib.md` |
| 4 | UODO | tylko po DPIA z wysokim ryzykiem szczątkowym | wstrzymane (hold) | `licencje/04-uodo-konsultacja.md` |
| 5 | Starostwa (EGiB) | dane właścicieli - wymagany interes prawny; nie piszemy, dopóki GUGiK nie odpowie | nie teraz | - |
| 6 | Sądy rejonowe, NRN | nie dotyczy | - | - |
| 7 | MS ponownie: wniosek formalny z art. 39 (zawężony) | po odpowiedzi na pkt 1 i konsultacji prawnej | ok. tydzień 4 | do przygotowania po odpowiedzi |

## 5. Harmonogram i ryzyka (f)

| Tydzień | Krok | Wynik |
|---|---|---|
| 0 | 1 h z prawnikiem: rola iapply (administrator czy procesor), zawężony zakres wniosku, art. 6 ust. 3 ustawy o otwartych danych | notatka, poprawione szkice |
| 1 | wysyłka 01-03 | daty wpływu |
| 1-3 | budowa bez KW z ekw: RCN, działki (ULDK), numery KW z BIP (wykazy u.g.n.), pole „numer KW” wpisywane przez użytkownika | działa bez ryzyka |
| 3 | odpowiedzi (14 dni) albo zawiadomienia o przedłużeniu (do 2 mies.) | |
| 4 | wniosek z art. 39 do MS: działy I i II, tylko właściciele niebędący osobami fizycznymi; ewentualnie art. 39 ust. 2 (dostęp stały) | |
| 6-12 | oferta / odmowa; przy odmowie - decyzja prawnika: odwołanie do MC (14 dni) | |
| 12-24 | ewentualna skarga do WSA; obserwacja UD310 i analiz IWS | |

Ryzyka:
- **Odmowa MS** - bardzo prawdopodobna (stanowisko z 9.04.2026). Łagodzenie: zawężenie do osób prawnych i JST, cel prasowy, brak wyszukiwania po osobie fizycznej.
- **UD310 wejdzie w życie** - koniec anonimowego przeglądania; dla „KW przynosi użytkownik” bez wpływu (użytkownik loguje się sam).
- **Dane z komercyjnych wyszukiwarek KW** - MS uznaje ich źródło za pozaprawne. Nie kupujemy, nie importujemy, nie linkujemy.
- **Łączenie zbiorów** (KW + EGiB + KRS) może stworzyć profil osoby prywatnej - wyłącznik: łączymy tylko węzły osób publicznych i podmiotów; osoba prywatna = węzeł anonimowy „osoba fizyczna” bez nazwiska.
- **Błędne dopasowanie** (te same nazwiska) - tylko klucze (nr KW, nr działki, KRS, NIP), nigdy sama nazwa.

## 6. Co budujemy od razu (legalnie)

1. Pole „numer KW” przy nieruchomości w teczce - dziennikarz wpisuje sam; link do ekw.ms.gov.pl do ręcznego otwarcia; walidacja cyfry kontrolnej numeru KW lokalnie.
2. Dołączenie odpisu (PDF kupiony przez użytkownika) do prywatnej teczki, z weryfikacją identyfikatora przez użytkownika; nigdy w bazie publicznej.
3. Numery KW z jawnych dokumentów publicznych (BIP: wykazy i przetargi nieruchomości JST i Skarbu Państwa) - cytat z linkiem do źródła.
4. RCN + działki (ULDK/KIEG) - ceny transakcyjne i geometria bez danych osobowych.

## Źródła (sprawdzone 8.10.2026)

- Odpowiedź MS dla RPO, 9.04.2026, DL-II.41.24.2026: https://bip.brpo.gov.pl/sites/default/files/2026-04/Odpowiedz_MS_ksiegi_wieczyste_projekt_dostep_9_04_2026.pdf
- u.k.w.h., t.j. Dz.U. 2026 poz. 1066: https://api.sejm.gov.pl/eli/acts/DU/2026/1066/text.pdf
- Rozp. MS z 24.03.2026 w sprawie Centralnej Informacji KW, Dz.U. 2026 poz. 411: https://eli.gov.pl/eli/DU/2026/411/ogl/pol/pdf
- Rozp. MS z 24.03.2026 w sprawie opłat CI KW, Dz.U. 2026 poz. 410
- Ustawa o otwartych danych, Dz.U. 2021 poz. 1641: https://api.sejm.gov.pl/eli/acts/DU/2021/1641/text.pdf
- Prawo geodezyjne i kartograficzne, t.j. Dz.U. 2024 poz. 1151 (art. 24, 40a); nowelizacja RCN Dz.U. 2025 poz. 1542: https://www.geoportal.gov.pl/aktualnosci/nowelizacja-ustawy-prawo-geodezyjne-i-kartograficzne-opublikowana-w-dzienniku-ustaw-2/
- prawo.pl, 4.12.2025: https://www.prawo.pl/biznes/ksiegi-wieczyste-online-ministerstwo-planuje-ograniczenia,536188.html
- prawo.pl: https://www.prawo.pl/prawo/koniec-prywatnych-przegladarek-ksiag-wieczystych-ms-pracuje-nad-przepisami,530952.html
- Interia: https://biznes.interia.pl/nieruchomosci/news-przeciagaja-sie-prace-nad-zmiana-w-dostepie-do-ksiag-wieczys,nId,8002042
- Kontakt MS: https://www.gov.pl/web/sprawiedliwosc/kontakt-informacja-publiczna ; CI KW: https://www.gov.pl/web/sprawiedliwosc/elektroniczna-ksiega-wieczysta-kontakt

## Czego nie zweryfikowano

- Aktualny etap UD310 (legislacja.gov.pl nie sprawdzony) i ostateczny zakres logów.
- Czy MS zawarł z kimkolwiek porozumienia o dostępie hurtowym (brak publicznych śladów).
- Brzmienie art. 35 u.g.n. (numer KW w wykazach) i praktyka BIP gmin.
- Czy RCN po 13.02.2026 zawiera numery KW i jakie pola udostępnia usługa GUGiK.
- Czy EGiB udostępnia numer KW działki bez interesu prawnego (różna praktyka starostw).
- Orzecznictwo: interes prawny dziennikarza w EGiB; u.d.i.p. wobec treści KW.
- Kto w MS w 2026 podpisuje decyzje w sprawach ponownego wykorzystania.
