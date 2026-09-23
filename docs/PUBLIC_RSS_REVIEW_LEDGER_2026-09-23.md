# Rejestr przeglądu publicznych kanałów RSS — 23 września 2026

Ten rejestr dotyczy wyłącznie pobierania metadanych RSS: tytułu, adresu
oryginału, daty i streszczenia z kanału. Nie stanowi zgody na pobieranie HTML
artykułów, obrazów, załączników ani pełnych tekstów.

## Zatwierdzone po sprawdzeniu

| Źródło | Kanał | Stan | Podstawa |
|---|---|---|---|
| GIOŚ, rekord 404 | `https://www.gios.gov.pl/pl/?format=feed&type=rss` | aktywne, karta RSS v1, limit 24/dzień | [warunki GIOŚ](https://powietrze.gios.gov.pl/depoz/regulamin-i-polityka-prywatnosci/) — podanie źródła, czasu pozyskania i informacji o przetworzeniu |
| NIK | `https://www.nik.gov.pl/rss/id,1.html` | nie tworzyć kolejnej karty: aktywny odpowiednik istnieje w katalogu | [warunki NIK](https://www.nik.gov.pl/kontakt/ponowne-wykorzystywanie-informacji/) |
| URE | `https://www.ure.gov.pl/dokumenty/rss/9-rss-41.rss` | nie tworzyć kolejnej karty: aktywny odpowiednik istnieje w katalogu | [warunki URE](https://bip.ure.gov.pl/bip/informacja-publiczna/1061%2CPonowne-wykorzystywanie-informacji-sektora-publicznego.html) |

## Pozostałe publiczne kanały — nie uruchamiać do czasu znalezienia zasad dla kanału

| Źródło | Kanał | Wynik przeglądu | Następny krok |
|---|---|---|---|
| Geoportal | `https://www.geoportal.gov.pl/feed/` | Materiał o otwartych danych nie określa zasad dla kanału aktualności. | Znaleźć regulamin lub warunki dla tego RSS. |
| ABW | `https://www.abw.gov.pl/dokumenty/rss/24-rss-748.rss` | Nie znaleziono opublikowanych warunków dla kanału; charakter instytucji wymaga ostrożności. | Ręczna weryfikacja w BIP lub pisemne potwierdzenie. |
| Policja | `https://www.policja.pl/dokumenty/rss/1-rss-1.rss` | Nie znaleziono opublikowanych warunków dla tego kanału. | Ręczna weryfikacja BIP i regulaminu. |
| KZGW / Wody Polskie | `https://kzgw.gov.pl/index.php/pl/?format=feed&type=rss` | Nie znaleziono opublikowanych warunków dla kanału. | Sprawdzić BIP albo wystąpić o warunki. |
| IMGW | `https://imgw.pl/feed/` | [Regulamin danych IMGW](https://danepubliczne.imgw.pl/docs/regulamin_udostepniania_danych.pdf) dotyczy portalu danych, nie kanału aktualności. | Nie przenosić warunków danych na RSS; znaleźć zasady dla aktualności. |
| WIOŚ Warszawa | `https://wios.warszawa.pl/feed/` | Nie znaleziono opublikowanych warunków dla kanału. | Sprawdzić BIP. |
| NIW | `https://niw.gov.pl/feed/` | Nie znaleziono opublikowanych warunków dla kanału. | Sprawdzić BIP. |
| BIP woj. opolskiego | `https://bip.opolskie.pl/feed/` | BIP nie zastępuje ustalenia warunków dla kanału. | Odszukać stronę o ponownym wykorzystaniu. |
| BIP Częstochowy | `https://bip.czestochowa.pl/rss` | BIP nie zastępuje ustalenia warunków dla kanału. | Odszukać stronę o ponownym wykorzystaniu. |
| BIP Olsztyna | `https://bip.olsztyn.eu/rss.xml` | BIP nie zastępuje ustalenia warunków dla kanału. | Odszukać stronę o ponownym wykorzystaniu. |
| BIP Radomia | `https://bip.radom.pl/dokumenty/rss/69-rss-o-112.rss` | BIP nie zastępuje ustalenia warunków dla kanału. | Odszukać stronę o ponownym wykorzystaniu. |
| BIP Torunia | `https://bip.torun.pl/rss` | BIP nie zastępuje ustalenia warunków dla kanału. | Odszukać stronę o ponownym wykorzystaniu. |

## Zasada decyzji

Technicznie działający RSS nie jest samodzielną podstawą do uruchomienia
harvestera. Karta dostępu powstaje dopiero po zapisaniu źródła warunków dla
konkretnego kanału albo po uzyskaniu wyraźnej zgody. Jeżeli warunki dotyczą
innego produktu lub zbioru danych, nie rozszerzamy ich na aktualności RSS.
