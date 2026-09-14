# Trzecia fala audytu archiwów źródeł publicznych

Stan: 14 września 2026. Audyt dotyczył dziesięciu instytucjonalnych źródeł publicznego kontekstu. Oddzielono techniczną dostępność od prawa do pobierania, przechowywania i analizy. Sprawdzono pierwotne robots.txt, oficjalne warunki ponownego wykorzystywania, dokumentację API i małe próbki map. Nie uruchomiono importu ani backfillu.

## Jednoznacznie dozwolone w opisanym zakresie

| Źródło | Dostęp techniczny | Podstawa i warunki | Zakres / ograniczenia | Kandydat |
|---|---|---|---|---|
| KNF | `robots.txt` zezwala `User-agent: *`; oficjalna `sitemap.xml` działa | KNF zezwala bezpłatnie na ponowne wykorzystywanie informacji z `knf.gov.pl` i BIP; trzeba wskazać źródłową stronę | mapa ma strony serwisu, ale wymaga filtrowania do komunikatów, ostrzeżeń, decyzji i opracowań | adapter sitemap po dodaniu filtrów |
| URE | pusty `robots.txt`; publiczne strony i BIP | BIP URE potwierdza prawo ponownego wykorzystywania informacji opublikowanych w BIP; przy przetworzeniu trzeba je oznaczyć, a materiały osób trzecich mogą mieć odrębne prawa | brak potwierdzonej sitemap; potrzebny ograniczony adapter list BIP | adapter list BIP |
| NIK | `bip.nik.gov.pl/robots.txt` blokuje `/szukaj/`, lecz publiczne strony kontroli i dokumenty pozostają dostępne | NIK zezwala na ponowne wykorzystywanie z podaniem źródła, czasu wytworzenia i pozyskania oraz informacji o przetworzeniu | nie używać zablokowanej wyszukiwarki; oprzeć adapter na jawnych stronach kontroli lub uzgodnionym eksporcie | adapter katalogu kontroli bez `/szukaj/` |
| NSA / CBOSA | robots NSA pozwala na odczyt i wskazuje sitemap; CBOSA jest oficjalną bazą zanonimizowanych orzeczeń | NSA potwierdza bezpłatne ponowne wykorzystanie stron NSA, BIP i CBOSA; dla orzeczeń wymaga daty, sądu i sygnatury, a przy przetworzeniu także jego oznaczenia i zakresu fragmentu | mapa NSA nie jest katalogiem całej CBOSA; potrzebny osobny, oszczędny adapter bazy orzeczeń | adapter CBOSA z pełną atrybucją |
| e-Zamówienia / BZP | oficjalne API BZP WebService; odczyt ogłoszeń i liczników, bez procedury integracyjnej | regulamin API określa usługę jako bezpłatną i przeznaczoną do powtarzalnego odczytu opublikowanych ogłoszeń | stosować wyłącznie odczytowy endpoint dokumentowany przez UZP; limity i paginację odczytać z aktualnej instrukcji przed pilotem | importer API BZP |
| UOKiK | oficjalny indeks sitemap z mapami stron i komunikatów | UOKiK wyraża zgodę na ponowne wykorzystywanie informacji ze swoich stron pod warunkiem dokładnego linku źródłowego i daty pozyskania | robots blokuje wskazane boty AI, w tym GPTBot i ClaudeBot; techniczny harvester musi mieć własny identyfikowalny user-agent i respektować reguły dla `*`; trening/automaty AI pozostaje wyłączony do osobnej oceny | importer sitemap wyłącznie dla dozwolonego harvestera |

## Niejednoznaczne — nie uruchamiać

| Źródło | Dostęp techniczny | Brakujący dowód |
|---|---|---|
| PKW | robots wskazuje dużą oficjalną mapę `sitemaps/sitemap_1.xml` | nie znaleziono na stronie PKW jednoznacznych warunków masowego ponownego wykorzystywania ani udokumentowanego API dla całego zakresu; potrzebna pisemna podstawa lub ograniczenie do zbiorów z własną licencją |
| RCL | robots zezwala, ale próba oficjalnej mapy WordPress została odrzucona przez zabezpieczenie serwisu | nie obchodzić zabezpieczenia; potrzebny oficjalny eksport/API albo potwierdzenie dozwolonego, limitowanego dostępu do RPL/PPIoP |
| dane.gov.pl | działa oficjalne, publiczne API i dokumentacja Swagger | licencje i warunki należą do poszczególnych zbiorów; katalog może służyć do odkrywania, lecz każdy zasób trzeba dopuścić według jego własnej licencji i podmiotu udostępniającego |
| UODO | robots dopuszcza `User-agent: *`, ale nie potwierdzono sitemap ani kompletnego archiwum/API | nie znaleziono jednoznacznej strony z warunkami automatycznego ponownego wykorzystania całego serwisu; potrzebny dowód warunków i mechanizmu archiwalnego |

## Pierwotne dowody

- KNF: `https://www.knf.gov.pl/robots.txt`, `https://www.knf.gov.pl/sitemap.xml`, `https://bip.knf.gov.pl/bip_portal/uknf/ponowne_wykorzystanie_informacji_sektora_publicznego`.
- URE: `https://www.ure.gov.pl/robots.txt`, `https://bip.ure.gov.pl/bip/informacja-publiczna/1061,Ponowne-wykorzystywanie-informacji-sektora-publicznego.html`.
- NIK: `https://bip.nik.gov.pl/robots.txt`, `https://www.nik.gov.pl/kontakt/ponowne-wykorzystywanie-informacji/`, `https://bip.nik.gov.pl/kontrole/szukaj/`.
- NSA: `https://www.nsa.gov.pl/robots.txt`, `https://www.nsa.gov.pl/sitemap.xml`, `https://www.nsa.gov.pl/bip/informacje-ogolne/2-informacje-ogolne/ponowne-wykorzystanie-informacji/`.
- e-Zamówienia: `https://ezamowienia.gov.pl/pl/regulamin/`, `https://edu.ezamowienia.gov.pl/pl/integracja/`.
- UOKiK: `https://www.uokik.gov.pl/robots.txt`, `https://www.uokik.gov.pl/sitemap.xml`, `https://uokik.gov.pl/public/index.php/bip/wnioskowanie-o-dostep-do-informacji-sektora-publicznego-w-celu-jej-ponownego-wykorzystywania`.
- PKW: `https://www.pkw.gov.pl/robots.txt`, `https://www.pkw.gov.pl/sitemaps/sitemap_1.xml`.
- RCL: `https://rcl.gov.pl/robots.txt`, `https://rcl.gov.pl/wp-sitemap.xml`, `https://ppiop.rcl.gov.pl/`.
- dane.gov.pl: `https://api.dane.gov.pl/doc`, `https://api.dane.gov.pl/1.4/datasets`.
- UODO: `https://uodo.gov.pl/robots.txt`.

## Rekomendacja dla integratora

Najpierw podłączyć API BZP. Następnie przygotować małe piloty KNF i NSA/CBOSA, ponieważ mają najjaśniejsze warunki i stabilne punkty wejścia. NIK i URE wymagają adapterów listowych respektujących wyłączenia oraz pełną atrybucję. UOKiK można podłączyć wyłącznie jako zwykły, identyfikowalny harvester; nie przekazywać jego treści do treningu lub automatycznej analizy bez osobnej oceny reguł dla botów AI.
