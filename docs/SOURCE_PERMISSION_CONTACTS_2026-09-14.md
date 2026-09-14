# Wewnętrzny rejestr źródeł wymagających wyjaśnienia lub zgody

Stan: 14 września 2026. To lista robocza. Nie wysłano żadnej wiadomości. Brak odpowiedzi nie oznacza zgody.

## Państwowa Komisja Wyborcza / Krajowe Biuro Wyborcze

- Źródła: serwis PKW, mapy stron oraz dokumenty i wyniki wyborcze.
- Potrzebne potwierdzenie: czy automatyczne, okresowe pobieranie metadanych i publicznych dokumentów, przechowywanie kopii tekstowej oraz indeksowanie do wyszukiwania i RAG jest dozwolone; wymagane warunki atrybucji i limity.
- Dowód techniczny: `https://www.pkw.gov.pl/robots.txt`, `https://www.pkw.gov.pl/sitemaps/sitemap_1.xml`.

## Rządowe Centrum Legislacji

- Źródła: RPL, PPIoP, projekty, uzasadnienia, konsultacje i OSR.
- Potrzebne potwierdzenie: oficjalny eksport lub API, dopuszczalna częstotliwość i zakres przechowywania; próba mapy została odrzucona przez zabezpieczenie i nie będzie obchodzona.
- Dowód techniczny: `https://rcl.gov.pl/robots.txt`, `https://rcl.gov.pl/wp-sitemap.xml`, `https://ppiop.rcl.gov.pl/`.

## Prezes Urzędu Ochrony Danych Osobowych

- Źródła: decyzje, komunikaty i poradniki UODO.
- Potrzebne potwierdzenie: warunki ponownego wykorzystywania opublikowanych materiałów, dostępny oficjalny indeks/API, limity oraz zasady dla przetworzonego tekstu i analizy.
- Dowód techniczny: `https://uodo.gov.pl/robots.txt`.

## Kancelaria Prezesa Rady Ministrów / dane.gov.pl i właściwi dostawcy zbiorów

- Źródła: zasoby odkrywane przez API katalogu dane.gov.pl.
- Potrzebne wyjaśnienie tylko dla zasobów bez jednoznacznej licencji: warunki pobierania, przechowywania, przetwarzania i atrybucji. Kontakt grupować według rzeczywistego dostawcy zbioru, a nie wysyłać jednego ogólnego pytania o cały katalog.
- Dowód techniczny: `https://api.dane.gov.pl/doc`, `https://api.dane.gov.pl/1.4/datasets`.
