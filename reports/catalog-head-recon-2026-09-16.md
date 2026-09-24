# Rekonesans początkowej części katalogu źródeł

Stan: 2026-09-16. Zakres: pierwsze 32 pozycje `sources.md`; tylko rekonesans
oficjalnych stron, bez aktywowania źródła, bez zmiany kart i bez pobierania
materiałów. Pozycje już objęte działającą, węższą konfiguracją (Sejm/ELI, NIK,
GUS i Prokuratura Krajowa) nie są tutaj kandydatami do ponownego uruchomienia.

Klasyfikacja **możliwa karta** oznacza jedynie, że istnieje wystarczający
oficjalny kanał i publiczny dowód warunków, by przygotować wąską kartę do
wewnętrznego zatwierdzenia. Nie oznacza automatycznego włączenia harvestera.
**Wymaga kontaktu** oznacza brak jednoznacznego kanału albo brak jasnego
ogólnego warunku dla planowanego sposobu pobierania. **Odrzucić** oznacza, że
pozycja jest katalogiem lub agregatem, a nie jednym wydawcą materiałów.

| Pozycja z katalogu | Kanał i dokładny URL | Dowód warunków / licencji | Klasyfikacja | Krótki dowód i następny krok |
|---|---|---|---|---|
| Senat RP | RSS: `https://www.senat.gov.pl/rss/aktualnosci.xml` | `https://www.senat.gov.pl/o-senacie/wybrane-akty-prawne/dostep-do-informacji-publicznej1/` | Wymaga kontaktu | Oficjalna strona opisuje obsługę wniosków o ponowne wykorzystanie i możliwość wskazania warunków; nie znalazłem ogólnego zezwolenia automatycznego dla tego RSS. Przygotować krótkie zapytanie o RSS/metadane. |
| Kancelaria Prezydenta RP | RSS: `https://www.prezydent.pl/rss/` | `https://www.prezydent.pl/kancelaria/ponowne-wykorzystywanie-informacji-sektora-publicznego` | Możliwa karta | Oficjalna strona wskazuje informacje udostępnione w systemie Kancelarii i BIP jako zasób ponownego wykorzystywania, z ustawowymi ograniczeniami. Karta: RSS, metadane i link, bez pełnych snapshotów. |
| KPRM / premier.gov.pl | RSS: `https://www.gov.pl/web/premier/rss` | `https://www.gov.pl/web/gov/warunki-korzystania` | Możliwa karta | Warunki gov.pl określają CC BY-SA 4.0 dla tekstów (z wyłączeniami dla audio/wideo). Karta ma obejmować wyłącznie feed i tekstowe metadane, z atrybucją. |
| bip.gov.pl | Brak pojedynczego kanału wydawcy | `https://www.gov.pl/web/bip/kontakt4` | Odrzucić | To katalog/portal BIP, nie jeden podmiot publikujący. Karty trzeba robić dla konkretnego urzędu i jego konkretnego kanału. |
| PRS MS | Brak zweryfikowanego kanału aktualności | — | Wymaga kontaktu | Rejestr wymaga osobnego ustalenia zakresu danych, trybu dostępu i warunków. Nie wolno tworzyć karty z samej strony startowej. |
| eKRS MS | Brak zweryfikowanego kanału aktualności | — | Wymaga kontaktu | Jak wyżej: rejestr, nie serwis aktualności; najpierw potrzebny oficjalny opis API/eksportu. |
| ngo.pl | Brak oficjalnego API/RSS potwierdzonego dla automatycznego użycia | — | Wymaga kontaktu | Prywatny portal; wpis katalogowy nie jest zgodą na automatyczne pobieranie. |
| Trybunał Konstytucyjny | Oficjalna strona HTML: `https://trybunal.gov.pl/` | `https://trybunal.gov.pl/informacja-publiczna-media/ponowne-wykorzystywanie` | Wymaga kontaktu | Jest oficjalna strona o ponownym wykorzystaniu, lecz nie ustalono stabilnego kanału RSS/API ani precyzyjnego zakresu HTML. Najpierw wytypować jeden wykaz aktualności lub wystąpić o wskazanie kanału. |
| Dziennik Ustaw | ELI: `https://api.sejm.gov.pl/eli` | `https://www.sejm.gov.pl/Sejm10.nsf/page.xsp/dane_publiczne` | Możliwa karta — duplikat | Zakres powinien pozostać w istniejącej, wąskiej karcie ELI; nie tworzyć drugiego harvestera od strony WWW. |
| Monitor Polski | ELI: `https://api.sejm.gov.pl/eli` | `https://www.sejm.gov.pl/Sejm10.nsf/page.xsp/dane_publiczne` | Możliwa karta — duplikat | Jak wyżej: jeden kontrolowany adapter ELI zamiast osobnego HTML. |
| ISAP | Brak ustalonego w tym rekonesansie API/RSS dla bieżących zmian | — | Wymaga kontaktu | Nie rozszerzać automatycznie z ELI na ISAP: to odrębny host i zakres. |
| RPO | Kandydat RSS z katalogu: `https://bip.brpo.gov.pl/rss` | — | Wymaga kontaktu | RSS jest wskazany w katalogu, ale nie potwierdzono na oficjalnej stronie warunków jego maszynowego ponownego użycia. Przygotować pytanie o metadane RSS. |
| UOKiK | HTML komunikatów: `https://www.uokik.gov.pl/public/komunikaty?page=1` | — | Wymaga kontaktu | Oficjalny wykaz istnieje, lecz brak potwierdzonej ogólnej licencji/warunków dla tego kanału. Nie stosować HTML przed odpowiedzią albo jawną informacją o warunkach. |
| UODO | Brak zweryfikowanego kanału | — | Wymaga kontaktu | Do dalszego rekonesansu potrzebny konkretny RSS/API lub wskazanie oficjalnego wykazu. |
| KNF | Oficjalny wykaz/HTML: `https://www.knf.gov.pl/wyniki_wyszukiwania?pageNumber=1&pageSize=50` | `https://bip.knf.gov.pl/bip_portal/uknf/ponowne_wykorzystanie_informacji_sektora_publicznego` | Możliwa karta | KNF wprost podaje bezpłatne ponowne wykorzystanie informacji z własnych serwisów, z obowiązkiem wskazania źródła. Potrzebny mały adapter wyłącznie dla jednego stabilnego wykazu komunikatów, nie ogólna wyszukiwarka. |
| KRRiT | Brak zweryfikowanego kanału | — | Wymaga kontaktu | Brak kanału i dowodu warunków w tym przebiegu. |
| PKW | Brak zweryfikowanego kanału publikacji aktualności | — | Wymaga kontaktu | Wyniki wyborcze i aktualności wymagają osobno ustalonego, oficjalnego eksportu/API oraz zakresu. |
| NBP | Katalog wskazuje stronę główną, nie kanał | — | Wymaga kontaktu | NBP ma odrębne dane i komunikaty; karta musi rozdzielić ewentualne API danych od tekstów redakcyjnych. |
| IPN | Brak zweryfikowanego kanału | — | Wymaga kontaktu | Nie uruchamiać ze strony głównej; potrzebny dokładny kanał i warunki. |
| BIP Warszawy, Krakowa, Wrocławia, Poznania, Gdańska i Łodzi | Brak jednego wspólnego kanału | — | Odrzucić jako grupa | Każdy BIP jest odrębnym wydawcą i zakresem. Należy rozbić ten wpis na konkretne jednostki oraz konkretne wykazy/RSS. |
| dane.gov.pl | Dokumentacja API: `https://api.dane.gov.pl/doc` | `https://dane.gov.pl/` | Możliwa karta | Oficjalna dokumentacja API istnieje. Karta powinna obejmować wyłącznie metadane katalogowe/API, a licencję weryfikować per zbiór; nie pobierać automatycznie danych z zasobów wskazanych przez zewnętrznych wydawców. |
| Geoportal | Usługi: `https://www.geoportal.gov.pl/pl/usluga/` | `https://www.geoportal.gov.pl/pl/usluga/usluga-api/` | Wymaga kontaktu | Oficjalna strona dokumentuje WMS/WMTS/WFS, a usługa API odsyła do regulaminu. Nie jest to kanał aktualności; przed kartą trzeba wybrać konkretną usługę i jej regulamin. |

## Wnioski operacyjne

1. Do przygotowania jako następne, wąskie karty: **Kancelaria Prezydenta,
   KPRM, KNF i dane.gov.pl**. Każda karta musi ograniczać się do wskazanego
   kanału i metadanych/linków; nie może dziedziczyć zgody na całą domenę.
2. Do listy kontaktowej: **Senat, Trybunał Konstytucyjny, RPO, UOKiK, UODO,
   KRRiT, PKW, NBP, IPN, PRS/eKRS i ngo.pl**.
3. Do rozbicia, a nie masowego harvestingu: **bip.gov.pl** i miejska grupa
   BIP. Następny rekonesans powinien brać pojedynczą instytucję wraz z jej
   kanałem, warunkami i zakresem.

