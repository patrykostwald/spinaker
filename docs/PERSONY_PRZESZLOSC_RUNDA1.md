# przeszłość.today: pętla person, runda 1 (5.11.2026)

Dziesięć person-agentów przeszło przez żywy portal (https://przeszlosc.today) jak potencjalni użytkownicy, każda z własnym celem
i wymiarem oceny. Raporty (journey, ocena 1-10, braki, błędy, ryzyka) zostały zebrane tutaj. Cel pętli: powtarzać rundy po
wdrożeniu poprawek, aż średnia ocena osiągnie próg (propozycja: średnia co najmniej 7, żadna persona poniżej 6).

## Ważne zastrzeżenie metodologiczne

Runda 1 jest **zaniżona i nie nadaje się do mierzenia postępu**:
- Persony czytały portal przez Firecrawl (bez wykonywania skryptów JS tak jak przeglądarka), a pierwsze ładowanie dynamicznych widoków trwa kilka sekund. Persona 1 po wydłużeniu czasu oczekiwania do 8 s zobaczyła wynik, który wcześniej był „Nie udało się pobrać".
- Dziesięć person działało jednocześnie z jednego adresu; persona 2 dostała **HTTP 429** (`Retry-After: 7 s`). API ma limit 100 zapytań/min na adres (`backend/config/settings.py`).
- Weryfikacja: `/przeszlosc/odstepstwa` i karta spółki Orlen (`/przeszlosc/spolka/0000028860`, 61 zamówień TED, 4,02 mld zł) ładują się u agenta prowadzącego w pełni, mimo że persony zgłosiły błąd lub brak karty.
- **Zasada na kolejne rundy:** uruchamiać persony po 2-3 naraz, czas oczekiwania co najmniej 8-10 s, oceny z powodu „błąd ładowania" nie liczyć jako usterki portalu.

## Oceny (surowe)

| # | Persona | Cel | Ocena |
|---|---|---|---|
| 1 | Dziennikarz śledczy | spółki SP, rady, przetargi (Orlen) | 4 |
| 2 | Dziennikarz danych | eksport, API, przypisy, metodologia | 6 |
| 3 | Analityk NGO (watchdog) | odstępstwa, lobbing, finanse partii | 4 |
| 4 | Radny / aktywista lokalny | gmina, spółki komunalne, fundusze UE | 3 |
| 5 | Badacz (politolog) | dyscyplina klubowa, replikowalność | 6 |
| 6 | Compliance / KYC | due diligence spółki SP | 3 |
| 7 | Public affairs | proces legislacyjny, alerty, brief | 4 |
| 8 | Wykonawca (przetargi) | konkurencja, zamówienia, dotacje | 3 |
| 9 | Obywatel (telefon) | „jak głosował mój poseł" | 3 |
| 10 | Asystent posła (podmiot danych) | profil szefa, sprostowania | 6 |
| | **Średnia** | | **4,2** |

Najwyżej oceniane: strona „Jak to działa" (metodologia, uczciwe luki; 6-8/10) i „Stan danych" (6-7/10), ślad źródła przy każdym wpisie,
przypisy, archiwum, brak oceniania („odstępstwo nie jest zarzutem").

## Wnioski powtarzające się u wielu person (priorytet według liczby person)

**A. Odnajdywalność wejść (pięć+ person)**
1. Karta spółki od NIP/KRS: istnieje (`/przeszlosc/spolka/[krs]`), ale **nikt z person jej nie znalazł**. Strona główna nie mówi, że służy też do spółek i zamówień. (P1, P4, P6, P8)
2. „Mój poseł": wyszukiwarka po nazwisku/okręgu z kartą „jak głosował". Dane są, brakuje wejścia. (P3, P7, P9, P10)
3. Strona główna nie tłumaczy jednym zdaniem, do czego służy; pierwszy ekran to filmy YouTube i posiedzenia komisji. (P1, P3, P6, P8, P9)

**B. Dane są w bazie, brakuje widoku**
4. Imienne głosy posła w profilu (cała kadencja, frekwencja) i macierz klub x głosowanie; dziś tylko sumy. (P3, P7, P9, P10)
5. Oś „projekt ustawy": druk, etapy, komisje, czytania, Senat, podpis. (P7)
6. Finanse partii (PKW, 969 rekordów) i rejestr lobbingu (666 + 7): zebrane, niewidoczne w UI. (P3)
7. Tagi tematyczne głosowań (obronność, budżet, UE). (P2)
8. Zbiorczy eksport (poseł x głosowanie x głos x głos większości klubu) i udokumentowane API; dziś „CSV z widocznych wierszy". (P2, P3, P5)

**C. Źródła zebrane niepoprawnie lub puste** (zgodne z diagnozą OSINT-01)
9. Kohesio i FTS: 0 rekordów; oświadczenia majątkowe: 0; BZP: 9; zmiany KRS: `JSONDecodeError`. (P1, P3, P4, P6, P8, P10)

**D. Błędy i niejasności do sprawdzenia w kodzie**
10. Tytuł i OG strony to „spin.clinic - pokazujemy, jak zbudowany jest przekaz" zamiast przeszłość.today (7 person: P2, P3, P5, P6, P7, P9, P10).
11. Ogłoszenia TED pod nagłówkiem „Ścieżka w Sejmie" (P8, P9; potwierdzone osobno).
12. Okno „90 dni" w Odstępstwach pokazuje zakres 5-21.10 (17 dni) i „liczone 4 listopada"; dwie liczby (1124 na stronie głównej, 187 na liście) bez wyjaśnienia; lista pokazuje 6 z 187 bez filtra po klubie/pośle i bez CSV. (P2, P3, P5, P10)
13. Pomyłka dopasowania po nazwisku: artykuł o Marcinie Bosackim w profilu Krzysztofa Bosaka. (P10)
14. Nagłówek „Głosowania w Sejmie w temacie X" w profilu osoby pokazuje głosowania **o** osobie, nie jej głosy. (P10)
15. Do „Liczby wpisów według obozu" wliczane cudze wpisy (odpowiedzi innych osób, konto partii). (P10)
16. „Kto" przy temacie krajowym (MON) zawiera posłów do PE, a nie posłów Sejmu. (P9)
17. Funkcje w KRS bez dat od-do w niektórych wynikach. (P10)
18. Niespójne liczniki (22 784 vs 22 786 wpisów); odnośnik „Odstępstwa" w Funkcjach prowadzi do kotwicy zamiast `/odstepstwa`. (P2)

**E. Niezawodność**
19. Komunikat „Nie udało się pobrać ..." bez przycisku „Spróbuj ponownie", bez ponowienia i bez zapasowych danych; limit 100 zapytań/min na adres, a w razie braku zaufanego proxy (`TRUSTED_PROXY_COUNT`) wszyscy użytkownicy mogą dzielić jeden limit (do sprawdzenia na serwerze). (P1, P2, P4, P6, P7, P9)

**F. Prawo i zaufanie (do decyzji prawnika, nie kodu)**
20. Klauzula RODO art. 14 to wersja robocza; procedura sprzeciwu i terminy „do potwierdzenia"; Regulamin X i prawo cytatu „do potwierdzenia". (P1, P2, P3, P6, P9, P10)
21. Kwoty z ogłoszeń to nie kwoty z umów; ostrzeżenie jest, ale nie przy wierszu. (P1, P4)
22. KYC/bank: agregator z zaległymi zbieraczami nie może być źródłem pierwotnym; OpenSanctions (licencja niekomercyjna) i CRBR (od 2027 uzasadniony interes) blokują zastosowania komercyjne. (P6)
23. Imiennicy w dopasowaniu mediów, szczególnie dla radnych (większe ryzyko niż przy posłach). (P4, P10)

## Nowe propozycje źródeł i funkcji (poza katalogiem 8.10)

Oznaczenia: [DP] do potwierdzenia dostępności, licencji i podstawy prawnej przed jakąkolwiek implementacją.
- Karta jednostki samorządu (gmina/powiat) po TERYT: spółki komunalne, zamówienia, dotacje (P4; TERYT i BIR w katalogu jako infrastruktura).
- Spółki Skarbu Państwa z pełnymi radami i zarządami (P1, P6; wykaz SSP jest w katalogu poz. 40; uwaga: API KRS maskuje osoby, więc to decyzja prawna co do pokazywania pełnych składów).
- Ogłoszenia o udzieleniu zamówienia (zwycięzca, liczba ofert, cena vs szacunek), filtr po CPV i regionie (P8) [DP].
- Historia przynależności klubowej posła w kadencji (Sejm API, Wikidata) (P5).
- Wskaźniki dyscypliny klubów (np. indeks Rice'a) i podział głosowań na końcowe i proceduralne (P5, P7).
- Podpisy i weta prezydenta, głosowania Senatu (prezydent.pl, senat.gov.pl; Senat blokuje nasz serwer, 403) (P9) [DP].
- Kalendarze i rejestry spotkań polityków z lobbystami w Polsce (P3) [DP].
- Wyniki wyborów samorządowych / lista radnych (PKW) jako tożsamość (P4) [DP].
- Alerty na projekt ustawy / druk z progami zmian etapu i alert „nowy przetarg w moim CPV" (P7, P8).
- Eksport briefu (PDF/DOCX) z przypisami, teczki tematu do współdzielenia (P7; zapowiedziane na stronie).

## Szybkie poprawki (mały nakład, duży efekt)

1. Meta/OG tytuł i opis dla tras `/przeszlosc/*` (zamiast spin.clinic). (#10)
2. Nagłówek „Ścieżka w Sejmie": nie wkładać pod niego ogłoszeń TED albo zmienić nazwę sekcji. (#11)
3. Odstępstwa: poprawna etykieta okna, wyjaśnienie dwóch liczb, filtr po klubie/pośle, CSV. (#12)
4. „Spróbuj ponownie" i jedno automatyczne ponowienie przy błędzie pobierania i HTTP 429. (#19)
5. Jedno zdanie „do czego służy" i wyraźne wejścia „Spółka (NIP/KRS)" i „Poseł" na stronie głównej. (#1-3)
6. Poprawka nagłówka „Głosowania w temacie X" w profilu osoby. (#14)

## Kolejna runda

Po wdrożeniu poprawek: powtórzyć z tymi samymi personami, po 2-3 naraz, z wydłużonym czasem oczekiwania; porównać oceny z tą tabelą.
Dodać persony: osoba z mniejszej redakcji lokalnej, działacz antykorupcyjny z doświadczeniem OSINT, student prawa.
