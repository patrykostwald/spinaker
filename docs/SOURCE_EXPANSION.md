# Kolejne źródła — propozycje, nie aktywne importy

Potwierdzono istnienie poniższych oficjalnych zasobów. Każdy nowy importer wymaga osobnego sprawdzenia sposobu pobierania, dat i zakresu archiwum. Nie dopisano niezweryfikowanych kanałów RSS do aktywnego katalogu.

1. Rządowe Centrum Legislacji: projekty, uzasadnienia, konsultacje i oceny skutków regulacji. https://rcl.gov.pl/legislacja/proces-legislacyjny-w-polsce/
2. NIK: pełne wyniki kontroli i wystąpienia, oprócz aktualności już obecnych w katalogu. https://www.nik.gov.pl/kontrole/wyniki-kontroli-nik/
3. PKW: wyniki i dokumenty wyborcze, sprawozdania finansowe partii i komitetów. https://wybory.pkw.gov.pl/finansowanie-polityki/finansowanie-partii-politycznych/sprawozdania-finansowe-partii-politycznych-za-rok-2024
4. BZP/e-Zamówienia: ogłoszenia o zamówieniach. Dokumentacja wskazuje API; wariant produkcyjnego endpointu wymaga jeszcze próby. https://ezamowienia.gov.pl/pl/regulamin/
5. NSA/WSA: orzeczenia z oficjalnej, zanonimizowanej bazy. https://www.nsa.gov.pl/dostep-elektroniczny/baza-orzeczen/
6. UOKiK: komunikaty i decyzje jako osobne rodzaje dokumentów. https://www.uokik.gov.pl/public/komunikaty?page=1
7. dane.gov.pl: katalog dodatkowych zbiorów administracji i API. https://api.dane.gov.pl/doc

Do dalszego rozpoznania: BIP samorządów (uchwały, budżety, protokoły, konsultacje), wojewódzkie dzienniki urzędowe, KNF, URE, UODO, raporty spółek oraz EUR-Lex i dane instytucji UE. To kandydaci — nie potwierdzenie działających integracji.

Audyt fali 3 z 14 września 2026 potwierdził jasne warunki ponownego wykorzystania dla KNF, URE, NIK, NSA/CBOSA, API BZP i stron UOKiK, z warunkami opisanymi w `SOURCE_ARCHIVE_AUDIT_WAVE3_2026-09-14.md`. PKW, RCL, UODO oraz zbiory dane.gov.pl bez własnej jednoznacznej licencji pozostają nieaktywne; zakres pytań zebrano w `SOURCE_PERMISSION_CONTACTS_2026-09-14.md`.

Szybka ścieżka API potwierdziła dodatkowo dwa nieaktywne, gotowe do napisania pilota źródła na odrębnych hostach: GUS Bank Danych Lokalnych oraz UOKiK SUDOP. Limity, atrybucję i rozdział warstw zapisano w `SOURCE_OFFICIAL_FASTLANE_2026-09-14.md`, a maszynowy katalog w `backend/scraper/data/verified_official_api_candidates.json`. Nie liczyć ich jako działających workerów przed wdrożeniem i przeglądem adapterów.

Zasada: agregujemy dokument i jego pochodzenie. Komunikat instytucji nie zastępuje pełnej decyzji, a informacja o zarzutach nie jest wyrokiem. Autor nitki komentuje oddzielnie. Wersje i sprostowania zachowujemy z własnymi datami; nie poprawiamy po cichu oryginału. Kontroler jakości zapisuje jedynie flagi w QualityIssue, nie zmienia Article.
