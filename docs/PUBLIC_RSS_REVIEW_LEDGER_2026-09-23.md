# Rejestr przeglądu publicznych kanałów RSS — 23 września 2026

Ten rejestr dotyczy wyłącznie pobierania metadanych RSS: tytułu, adresu
oryginału, daty i streszczenia z kanału. Nie stanowi zgody na pobieranie HTML
artykułów, obrazów, załączników ani pełnych tekstów.

## Zatwierdzone po sprawdzeniu

| Źródło | Kanał | Stan | Podstawa |
|---|---|---|---|
| GIOŚ, rekord 404 | `https://www.gios.gov.pl/pl/?format=feed&type=rss` | aktywne, karta RSS v1, limit 24/dzień | [warunki GIOŚ](https://powietrze.gios.gov.pl/depoz/regulamin-i-polityka-prywatnosci/) — podanie źródła, czasu pozyskania i informacji o przetworzeniu |
| WIOŚ Warszawa, rekord 419 | `https://wios.warszawa.pl/feed/` | gotowe do uruchomienia, karta RSS v1, limit 24/dzień | [warunki WIOŚ](https://bip.warszawa.wios.gov.pl/bip/ponowne-wykorzystywanie/291%2CPonowne-wykorzystywanie-informacji-sektora-publicznego.html) — źródło, czas wytworzenia i pozyskania oraz informacja o przetworzeniu |
| Geoportal / GUGiK, rekord 32 | `https://www.geoportal.gov.pl/feed/` | gotowe do uruchomienia, karta RSS v1, limit 24/dzień | [warunki GUGiK](https://www.gov.pl/web/gugik/ponowne-wykorzystanie-informacji-sektora-publicznego) — Geoportal wskazuje GUGiK jako podmiot prowadzący; zachowujemy źródło, daty i informację o przetworzeniu |
| BIP Olsztyna, rekord 575 | `https://bip.olsztyn.eu/rss.xml` | gotowe do uruchomienia, karta RSS v1, limit 24/dzień | [warunki BIP](https://bip.olsztyn.eu/37/ponowne-wykorzystywanie-informacji-sektora-publicznego.html) — warunki dotyczą wprost informacji opublikowanych w BIP Urzędu Miasta Olsztyna |
| BIP Radomia, rekord 576 | `https://bip.radom.pl/dokumenty/rss/69-rss-o-112.rss` | gotowe do uruchomienia, karta RSS v1, limit 24/dzień | [warunki BIP](https://bip.radom.pl/ra/ponowne-wykorzystanie-informac/19412,Zasady-i-tryb-udostepniania.html) — prawo ponownego wykorzystania informacji opublikowanych w BIP Urzędu Miejskiego w Radomiu |
| NIK | `https://www.nik.gov.pl/rss/id,1.html` | nie tworzyć kolejnej karty: aktywny odpowiednik istnieje w katalogu | [warunki NIK](https://www.nik.gov.pl/kontakt/ponowne-wykorzystywanie-informacji/) |
| URE | `https://www.ure.gov.pl/dokumenty/rss/9-rss-41.rss` | nie tworzyć kolejnej karty: aktywny odpowiednik istnieje w katalogu | [warunki URE](https://bip.ure.gov.pl/bip/informacja-publiczna/1061%2CPonowne-wykorzystywanie-informacji-sektora-publicznego.html) |
| ABW | `https://www.abw.gov.pl/dokumenty/rss/24-rss-748.rss` | przygotowane do uruchomienia po ponownym świeżym audycie kanału, limit 24/dzień | [strona usługi RSS ABW](https://www.abw.gov.pl/pl/rss) wskazuje wprost dystrybucję aktualności i komunikatów w RSS, z tytułem, krótkim opisem i linkiem; karta pozostaje wyłącznie dla tych metadanych |
| BIP Torunia | `https://bip.torun.pl/rss` | przygotowane do uruchomienia po ponownym świeżym audycie kanału, limit 24/dzień | [warunki BIP Torunia](https://bip.torun.pl/artykul/7/1/name) obejmują wprost informację udostępnioną w tym BIP oraz wymagają wskazania źródła, czasu i przetworzenia |

## Pozostałe publiczne kanały — nie uruchamiać do czasu znalezienia zasad dla kanału

| Źródło | Kanał | Wynik przeglądu | Następny krok |
|---|---|---|---|
| Policja | `https://www.policja.pl/dokumenty/rss/1-rss-1.rss` | Nie znaleziono opublikowanych warunków dla tego kanału. | Ręczna weryfikacja BIP i regulaminu. |
| KZGW / Wody Polskie | `https://kzgw.gov.pl/index.php/pl/?format=feed&type=rss` | Nie znaleziono opublikowanych warunków dla kanału. | Sprawdzić BIP albo wystąpić o warunki. |
| IMGW | `https://imgw.pl/feed/` | [Regulamin danych IMGW](https://danepubliczne.imgw.pl/docs/regulamin_udostepniania_danych.pdf) dotyczy portalu danych, nie kanału aktualności. | Nie przenosić warunków danych na RSS; znaleźć zasady dla aktualności. |
| NIW | `https://niw.gov.pl/feed/` | Nie znaleziono opublikowanych warunków dla kanału. | Sprawdzić BIP. |
| BIP woj. opolskiego | `https://bip.opolskie.pl/feed/` | BIP nie zastępuje ustalenia warunków dla kanału. | Odszukać stronę o ponownym wykorzystaniu. |
| BIP Częstochowy | `https://bip.czestochowa.pl/rss` | Warunki wykorzystania są opublikowane, ale świeży audyt techniczny nie potwierdził kanału. | Nie uruchamiać; ustalić przyczynę rozbieżności przed ponowną próbą. |

Pięć wpisów bez odnalezionych warunków przeniesiono do listy roboczej
`PUBLIC_RSS_CONTACT_CANDIDATES_2026-09-23.md`. Nie oznacza to zgody na
kontakt ani uruchomienia pobierania.

## Zasada decyzji

Technicznie działający RSS nie jest samodzielną podstawą do uruchomienia
harvestera. Karta dostępu powstaje dopiero po zapisaniu źródła warunków dla
konkretnego kanału albo po uzyskaniu wyraźnej zgody. Jeżeli warunki dotyczą
innego produktu lub zbioru danych, nie rozszerzamy ich na aktualności RSS.
