# Audyt szybkiej ścieżki: media regionalne i branżowe — 2026-09-14

Audyt jest kandydacki i nie uruchamia pobierania. Sprawdzenie wykonano 14 września 2026 r. na pierwotnych zasobach wydawców. Dostępność techniczna nie jest traktowana jako licencja. Proponowany limit 20 żądań na minutę oznacza co najmniej 3 sekundy między żądaniami do hosta, adaptacyjne spowolnienie po 429/5xx oraz respektowanie `Retry-After`; wydawcy nie zadeklarowali własnego `Crawl-delay` na sprawdzonych ścieżkach.

| Źródło | Wejście techniczne i zakres | Robots | Metadane / wyszukiwarka | Pełny tekst / snapshot | RAG | Trening | Decyzja |
|---|---|---|---|---|---|---|---|
| LoveKraków.pl | indeks 37 stronicowanych map, bieżący `lastmod` | `Allow: /`; `search=yes`, `use=reference`, `ai-train=no`; boty AI wyłączone | dozwolone przez Content-Signal dla linków i krótkich fragmentów | brak zgody | brak sygnału `ai-input`, więc wyłączone | zabronione | najlepszy kandydat do późniejszego metadata-only |
| Radio Lublin | aktualny RSS; indeks 423 map różnych typów | ścieżki feed/map nie są wyłączone | niejednoznaczne | wymaga zgody; osobno wykluczyć materiały PAP/AFP | wymaga zgody | wymaga zgody | technicznie gotowy, prawnie wstrzymany |
| Rzeszów News | aktualny RSS, news sitemap, indeks 49 map | tylko `/wp-admin/` wyłączone; mapy zadeklarowane | wymaga osobnej oceny dozwolonego zakresu | regulamin zabrania pobierania całości lub istotnej części do ponownego wykorzystania/przetwarzania | bez osobnej podstawy wyłączone | bez osobnej podstawy wyłączone | nie dopuszczać do backfillu bez zgody |
| CyberDefence24 | aktualny RSS `_rss`; 139 map, w tym miesięczne mapy artykułów | `Allow: /`, oficjalna mapa zadeklarowana | niejednoznaczne | brak znalezionej licencji na archiwizację | wymaga zgody | wymaga zgody | technicznie gotowy, prawnie wstrzymany |
| Energetyka24 | aktualny RSS `_rss`; 168 map, w tym miesięczne mapy artykułów | `Allow: /`, oficjalna mapa zadeklarowana | niejednoznaczne | brak znalezionej licencji na archiwizację | wymaga zgody | wymaga zgody | technicznie gotowy, prawnie wstrzymany |
| Radio Wrocław | robots dostępny; standardowe `/feed/`, `/sitemap.xml` i `/wp-sitemap.xml` zwracają 404 | artykuły ogólnie dozwolone, ścieżki interakcji wyłączone | regulamin opisuje odbiór przez kanały RSS, ale kanału nie ustalono | brak zgody na archiwizację | wymaga zgody | wymaga zgody | odrzucony z szybkiej ścieżki: brak stabilnego wejścia |
| Radio Kraków | robots dostępny; standardowe `/feed/`, `/sitemap.xml` i `/wp-sitemap.xml` zwracają 404 | ograniczone wyszukiwanie i pliki pobierania | nieustalone | nieustalone | nieustalone | nieustalone | odrzucony z szybkiej ścieżki: brak stabilnego wejścia |

## Dowody pierwotne

- LoveKraków: <https://lovekrakow.pl/robots.txt>, <https://lovekrakow.pl/sitemap.xml>
- Radio Lublin: <https://radio.lublin.pl/robots.txt>, <https://radio.lublin.pl/feed/>, <https://radio.lublin.pl/sitemap_index.xml>, <https://cdn.radio.lublin.pl/regulaminy/>
- Rzeszów News: <https://rzeszow-news.pl/robots.txt>, <https://rzeszow-news.pl/feed/>, <https://rzeszow-news.pl/sitemap_index.xml>, <https://rzeszow-news.pl/news-sitemap.xml>, <https://rzeszow-news.pl/regulamin-portalu/>
- CyberDefence24: <https://cyberdefence24.pl/robots.txt>, <https://cyberdefence24.pl/_rss>, <https://cyberdefence24.pl/sitemap.xml>, <https://cyberdefence24.pl/regulaminy/regulamin-newslettera>
- Energetyka24: <https://energetyka24.com/robots.txt>, <https://energetyka24.com/_rss>, <https://energetyka24.com/sitemap.xml>, <https://cyberdefence24.pl/regulaminy/regulamin-newslettera>
- Radio Wrocław: <https://www.radiowroclaw.pl/robots.txt>, <https://www.radiowroclaw.pl/articles/view/20084/regulamin-portalu-internetowego-radia-wroclaw>
- Radio Kraków: <https://www.radiokrakow.pl/robots.txt>

## Rekomendacja integracyjna

1. LoveKraków można później skonfigurować jako wyłączone źródło `metadata_only`, z tytułem, datą, autorem, canonical URL i krótkim fragmentem z mapy/strony, bez zapisu pełnej treści, prywatnego snapshotu, RAG i treningu. Przed aktywacją parser musi wysyłać własny identyfikowalny user-agent, stosować limit hosta i ponownie odczytać Content-Signal.
2. Radio Lublin, Rzeszów News, CyberDefence24 i Energetyka24 są gotowe do testów parserów na lokalnych fixture, ale pozostają wyłączone w ruchu sieciowym do rozstrzygnięcia prawnego zakresu metadanych lub uzyskania zgody.
3. Nie przeznaczać osobnego workera dla Radia Wrocław ani Radia Kraków, dopóki pierwotna strona wydawcy nie wskaże stabilnego RSS/API/mapy.

Żaden z wpisów w katalogu kandydackim nie jest aktywny i żaden nie stanowi zgody na nocny backfill.
