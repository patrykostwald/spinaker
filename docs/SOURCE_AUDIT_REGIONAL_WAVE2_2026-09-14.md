# Audyt regionalnych źródeł — fala 2 (2026-09-14)

## Cel i granice

To jest audyt kandydatów do **archiwizacji metadanych**, a nie zgoda na
pobieranie publikacji. Nie dodano źródła do wspólnego katalogu, nie uruchomiono
adaptera, nie pobrano korpusu artykułów ani materiałów audio/wideo. Dla
pozytywnej kwalifikacji wymagane są łącznie: publiczny, stabilny kanał
RSS/API/sitemap; aktualne `robots.txt` pozwalające na wskazany zakres; oraz
jednoznaczne warunki użycia zgodne z przechowywaniem metadanych, linku do
oryginału i późniejszym przetwarzaniem.

Nie zakładamy, że publiczność strony, technologia WordPress lub sam RSS są
zgodą na automatyczne archiwizowanie. W czasie tego audytu środowisko nie mogło
odczytać na żywo plików `robots.txt` (połączenia wychodzące do hostów były
zablokowane), dlatego żaden kandydat nie przeszedł progu aktywacji.

## Wynik

**Nie utworzono pliku JSON kandydatów i nie ma nowego źródła do aktywnej
puli.** Poniższa lista jest kolejką ręcznej, odtwarzalnej weryfikacji. Każdy
host musi pozostać oddzielny dla limitera: maksymalnie jedno żądanie na domenę
i odstęp co najmniej 3 s.

| Domena / podmiot | Widoczna metoda | `robots.txt` i warunki | Status | Powód decyzji |
| --- | --- | --- | --- | --- |
| `radio.lublin.pl` — Radio Lublin | Publiczne strony aktualności działające na WordPress; technicznie możliwy kanał RSS/indeks WP wymaga potwierdzenia. | W tym audycie nie odczytano aktualnego `robots.txt` ani regulaminu dla automatycznego pobierania metadanych. Dostępny regulamin dotyczy użycia logo, nie publikacji. | **Wstrzymane** | Nie wolno domniemywać zgody z WordPressa ani z publicznego artykułu. |
| `radio.bialystok.pl` — Polskie Radio Białystok | Serwis publicznie wskazuje kanały RSS podcastów; kanał aktualności i stabilność indeksu wymagają osobnego sprawdzenia. | Jest publiczny regulamin portalu, ale nie potwierdzono w nim zakresu automatycznego archiwizowania ani bieżącego `robots.txt`. | **Wstrzymane** | RSS podcastu nie jest zgodą dla newsów; potrzebny konkretny feed/news sitemap oraz warunki. |
| `radio.gdansk.pl` — Radio Gdańsk | Publiczne aktualności; potencjalny RSS/sitemap do sprawdzenia. | Brak odczytu aktualnego `robots.txt` i warunków reuse w tym audycie. | **Wstrzymane** | Brak kompletu dowodów technicznych i prawnych. |
| `radiokielce.pl` — Radio Kielce | Publiczne aktualności; potencjalny RSS/sitemap do sprawdzenia. | Brak odczytu aktualnego `robots.txt` i warunków reuse w tym audycie. | **Wstrzymane** | Publiczny serwis nie jest sam w sobie zgodą na automat. |
| `radiopoznan.fm` — Radio Poznań | Publiczne aktualności; potencjalny RSS/sitemap do sprawdzenia. | Brak odczytu aktualnego `robots.txt` i warunków reuse w tym audycie. | **Wstrzymane** | Brak potwierdzonego kanału metadanych oraz licencji/warunków. |
| `radioszczecin.pl` — Radio Szczecin | Publiczne aktualności; potencjalny RSS/sitemap do sprawdzenia. | Brak odczytu aktualnego `robots.txt` i warunków reuse w tym audycie. | **Wstrzymane** | Konieczna ręczna walidacja przed jakimkolwiek zadaniem archiwum. |
| `radioolsztyn.pl` — Radio Olsztyn | Publiczne aktualności; potencjalny RSS/sitemap do sprawdzenia. | Brak odczytu aktualnego `robots.txt` i warunków reuse w tym audycie. | **Wstrzymane** | Nie potwierdzono dopuszczalnego sposobu automatyzacji. |
| `radiokrakow.pl` — Radio Kraków | Publiczne aktualności; potencjalny RSS/sitemap do sprawdzenia. | Brak odczytu aktualnego `robots.txt` i warunków reuse w tym audycie. | **Wstrzymane** | Nie kwalifikować na podstawie samej dostępności treści. |
| `radio.opole.pl` — Radio Opole | Publiczne aktualności; potencjalny RSS/sitemap do sprawdzenia. | Brak odczytu aktualnego `robots.txt` i warunków reuse w tym audycie. | **Wstrzymane** | Brak potwierdzonych warunków dla metadanych. |
| `radio.rzeszow.pl` — Radio Rzeszów | Publiczne aktualności; potencjalny RSS/sitemap do sprawdzenia. | Brak odczytu aktualnego `robots.txt` i warunków reuse w tym audycie. | **Wstrzymane** | Wymagany dowód dla dokładnego hosta i ścieżki kanału. |

## Dowody, które należy odczytać przy następnej walidacji

1. [Radio Lublin — serwis aktualności](https://radio.lublin.pl/)
2. [Radio Białystok — serwis aktualności](https://www.radio.bialystok.pl/)
3. [Radio Białystok — przykład strony kanału RSS](https://www.radio.bialystok.pl/podcasty/index/id/215077/resguid/208470)
4. [Radio Gdańsk](https://radio.gdansk.pl/)
5. [Radio Kielce](https://radiokielce.pl/)
6. [Radio Poznań](https://radiopoznan.fm/)
7. [Radio Szczecin](https://radioszczecin.pl/)
8. [Radio Olsztyn](https://radioolsztyn.pl/)
9. [Radio Kraków](https://radiokrakow.pl/)
10. [Radio Opole](https://radio.opole.pl/)
11. [Radio Rzeszów](https://radio.rzeszow.pl/)

## Procedura przed ewentualnym włączeniem

1. Odczytać `https://HOST/robots.txt` oraz dokładny regulamin/warunki danego
   hosta w dniu decyzji i zapisać adresy dowodów.
2. Odkryć **oficjalny** RSS/API/sitemap, ograniczony do URL, tytułu, daty,
   autora i linku do oryginału. Nie pobierać pełnego tekstu, obrazów ani audio.
3. Przetestować pojedynczy rekord w trybie dry-run i potwierdzić deduplikację,
   atrybucję oraz limiter: jedna aktywna prośba na domenę, >=3 s.
4. Jeżeli warunki są niejednoznaczne albo robots zabrania ścieżki, zapisać
   źródło do backlogu zgody. Nie szukać obejścia technicznego.

Ta fala nie zwiększa liczby workerów. Zwiększenie aktywnej puli następuje
dopiero po pełnej kwalifikacji źródła i ponownym przeglądzie przez redakcję.
