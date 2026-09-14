# Ciągły audyt legalnych źródeł A — 14 września 2026

## Zakres i decyzja

To jest **audyt kwalifikacyjny**, a nie zgoda na pobranie. Sprawdzono osiem
instytucjonalnych źródeł ważnych dla kontekstu publicznego. Nie pobierano
korpusu, nie wykonywano snapshotów, nie utworzono zadań harvestera i nie
zmieniono katalogu aktywnych źródeł.

Wynik: **żaden host nie jest dziś automatycznie aktywowany**. Cztery hosty
(NIK, KNF, URE i RCL) mają widoczną podstawę ponownego wykorzystania i nadają
się do kontrolowanego pilotażu metadanych po odczycie `robots.txt`, znalezieniu
oficjalnego indeksu oraz teście pojedynczego rekordu. Cztery pozycje na
`gov.pl` nie zwiększają liczby domen i pozostają do kwalifikacji per dział.

## Zasada dla przyszłego adaptera

Przed przejściem do harvestera musi powstać decyzja źródłowa z: publicznym
adresem warunków, datą kontroli, wynikiem `robots.txt`, wybraną metodą,
dopuszczonym zakresem (wyłącznie metadane lub szerszy zakres), atrybucją oraz
limitem. Pierwszy przebieg ma pobrać tylko URL, tytuł, datę, autora/opis i
link do oryginału; jedna prośba na host i nie częściej niż co 3 s. Brak
jednego z tych elementów oznacza **kontakt / ręczną kontrolę**, nie próbę
obejścia.

| Podmiot / host | Publiczna podstawa i techniczny punkt wejścia | Rekomendacja | Następny krok |
| --- | --- | --- | --- |
| Najwyższa Izba Kontroli — `www.nik.gov.pl`, `bip.nik.gov.pl` | NIK podaje, że informacje na swoich stronach i BIP mogą być wykorzystywane bezpłatnie przy wskazaniu źródła, czasu wytworzenia/pozyskania i informacji o przetworzeniu. BIP ma publiczną wyszukiwarkę wyników kontroli oraz metryczki dokumentów. | **Kontrolowany pilot metadanych po walidacji technicznej.** | Ręcznie odczytać `robots.txt`, ustalić stabilny, oficjalny indeks wyników kontroli i wykonać dry-run jednego rekordu. Nie pobierać PDF/pełnej treści bez osobnej decyzji zakresowej. |
| Komisja Nadzoru Finansowego — `www.knf.gov.pl`, `bip.knf.gov.pl` | KNF wyraźnie dopuszcza bezpłatne ponowne wykorzystanie informacji z obu serwisów przy podaniu źródła. Publiczna wyszukiwarka zwraca listy publikacji, daty i kategorie. | **Kontrolowany pilot metadanych po walidacji technicznej.** | Sprawdzić `robots.txt` i parametry oficjalnej wyszukiwarki; indeksować wyłącznie jej wyniki, bez dokumentów załączonych. |
| Urząd Regulacji Energetyki — `www.ure.gov.pl`, `bip.ure.gov.pl` | BIP publikuje warunki ponownego wykorzystywania oraz materiały regulatora; w audycie nie ustalono jednak stabilnego feedu/API ani dokładnego zakresu warunków dla automatu. | **Ręczna kontrola przed pilotem.** | Ustalić oficjalny indeks aktualności/BIP i aktualny `robots.txt`. Gdy warunki potwierdzą zakres metadanych, przygotować mały adapter indeksu. |
| Rządowe Centrum Legislacji — `bip.rcl.gov.pl` | BIP RCL publikuje procedurę ponownego wykorzystania oraz kanał kontaktowy dla wniosków. Nie znaleziono w tym audycie udokumentowanego API/RSS dla publikacji. | **Kontakt lub ręczna kontrola.** | Zweryfikować istniejący indeks BIP i `robots.txt`; jeśli brak stabilnego mechanizmu, dodać do backlogu zgody z prośbą o RSS/API albo eksport metadanych. |
| Ministerstwo Cyfryzacji — `www.gov.pl/web/cyfryzacja` | Dział deklaruje CC BY 3.0 PL, o ile przy publikacji nie wskazano inaczej. To wspólny host `www.gov.pl`; warunki trzeba czytać przy konkretnych publikacjach. | **Nie aktywować osobno.** | Kwalifikować wyłącznie jako sekcję wspólnego adaptera Gov.pl po sprawdzeniu indeksu i `robots.txt`; nie liczyć jako osobnej domeny. |
| Główny Inspektorat Ochrony Środowiska — `www.gov.pl/web/gios` | Publikuje procedurę re-use, z możliwością indywidualnych warunków i opłat dla dostępu stałego w czasie rzeczywistym. | **Kontakt / ręczna kontrola.** | Nie traktować ogólnej procedury jako zgody na ciągły automat. Zidentyfikować konkretny otwarty zestaw/API z licencją albo wystąpić o warunki. |
| Ministerstwo Obrony Narodowej — `www.gov.pl/web/obrona-narodowa` | Warunki wskazują obowiązek podania źródła oraz czasu wytworzenia i pozyskania; host jest współdzielony z Gov.pl. | **Ręczna kontrola per publikacja.** | Ze względu na możliwe wyłączenia i wspólny host: tylko indeks metadanych po pełnej walidacji, żadnych automatycznych snapshotów ani załączników. |
| Ministerstwo Spraw Zagranicznych — `www.gov.pl/web/dyplomacja` | Procedura wskazuje, że informacje na stronie podlegają zasadom ponownego wykorzystania, ale nie potwierdzono w tym audycie kanału maszynowego ani kompletnego zakresu dla archiwum. | **Kontakt / ręczna kontrola.** | Ustalić kanał RSS/API lub wystąpić o dozwolony eksport metadanych; nie tworzyć adaptera HTML na podstawie samej dostępności strony. |

## Dowody pierwotne

1. [NIK — warunki ponownego wykorzystania](https://www.nik.gov.pl/kontakt/ponowne-wykorzystywanie-informacji/)
2. [NIK BIP — wyniki kontroli](https://bip.nik.gov.pl/kontrole/wyniki-kontroli-nik/prosta/stronakontrole%2C482.html)
3. [KNF — warunki ponownego wykorzystania](https://bip.knf.gov.pl/bip_portal/uknf/ponowne_wykorzystanie_informacji_sektora_publicznego)
4. [KNF — publiczna wyszukiwarka publikacji](https://www.knf.gov.pl/wyniki_wyszukiwania?pageNumber=1&pageSize=50&searchText=Strona)
5. [URE BIP — warunki](https://bip.ure.gov.pl/bip/informacja-publiczna/1061%2CPonowne-wykorzystywanie-informacji-sektora-publicznego.pdf)
6. [RCL BIP — ponowne wykorzystanie](https://bip.rcl.gov.pl/rcl/ponowne-wykorzystywanie/3122%2CPonowne-wykorzystywanie.pdf)
7. [Ministerstwo Cyfryzacji — CC BY 3.0 PL](https://www.gov.pl/web/cyfryzacja/ponowne-wykorzystywanie)
8. [GIOŚ — warunki i dostęp w czasie rzeczywistym](https://www.gov.pl/web/gios/ponowne-wykorzystywanie)
9. [MON — warunki](https://www.gov.pl/web/obrona-narodowa/ponowne-wykorzystywanie-informacji)
10. [MSZ — ponowne wykorzystanie](https://www.gov.pl/web/dyplomacja/ponowne-wykorzystanie-informacji-sektora-publicznego)

## Przekazanie do kolejnych ról

* **Harvester:** żadnego automatycznego uruchomienia na podstawie tej notatki.
  Po pozytywnej walidacji ma dostać pojedynczy adapter indeksu, pozwolony
  zakres metadanych, wymaganą atrybucję i limiter >=3 s na host.
* **Agent korespondencji:** RCL, GIOŚ i MSZ są kandydatami do listy kontaktowej
  z prośbą o stabilny RSS/API/eksport metadanych i pisemne potwierdzenie zakresu.
  Nie wysyłać wiadomości bez akceptacji redakcyjnej.
