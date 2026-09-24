# Weryfikacja archiwow zrodel ogolnopolskich

Stan: 14 wrzesnia 2026. Kontrola byla ograniczona do robots.txt, jawnych sitemap, indeksow sitemap, kilku map oraz publicznego HTML strony glownej. Nie pobierano stron artykulow, pelnych tekstow ani RSS jako monitoringu. Kody HTTP nie sa raportowane jako potwierdzone, poniewaz obserwacja przegladarkowa nie udostepnila statusu odpowiedzi; `zaladowane` oznacza tylko udany odczyt dokumentu.

Weryfikacja nie zapisala danych do Supabase, Source, Article ani ArchiveJob. Nie uruchomiono backfillu.

## Wyniki

### PAP

- Lokalny ID: nie ustalono, terminal i lokalna baza nie byly dostepne.
- Domena: `www.pap.pl`.
- Robots: `https://www.pap.pl/robots.txt`, dokument zaladowany; brak jawnej deklaracji sitemap.
- HTML strony glownej: nie znaleziono jawnego linku sitemap, archiwum ani feedu w ograniczonym odczycie.
- Wynik: `needs_review`.
- Powod: brak potwierdzonego mechanizmu cofania; robots blokuje wiele botow AI poza `/mediaroom`, co nie jest dowodem prawa do backfillu.

### Onet Wiadomosci

- Lokalny ID: nie ustalono.
- Domena: `wiadomosci.onet.pl`.
- Robots: `https://wiadomosci.onet.pl/robots.txt`, dokument zaladowany.
- HTML ujawnia `https://wiadomosci.onet.pl/.feed`.
- Wynik: `needs_review`.
- Powod: znaleziono feed, ale nie potwierdzono sitemap ani paginowanego archiwum; krotki RSS nie wystarcza do benchmarku.

### WP Wiadomosci

- Lokalny ID: nie ustalono.
- Domena: `wiadomosci.wp.pl`.
- Robots: `https://wiadomosci.wp.pl/robots.txt`, dokument zaladowany.
- HTML ujawnia `https://wiadomosci.wp.pl/rss/aktualnosci`.
- Wynik: `needs_review`.
- Powod: feed bez potwierdzonej drogi do starszych publikacji; nie zgadywano sitemap.

### TVN24

- Lokalny ID: nie ustalono.
- Domena: `tvn24.pl`.
- Robots: `https://tvn24.pl/robots.txt`, dokument zaladowany; brak jawnej sitemap.
- HTML strony glownej nie ujawnil sitemap, feedu ani paginowanego archiwum w ograniczonym odczycie.
- Wynik: `needs_review`.
- Powod: brak dowodu obslugiwanej metody backfillu.

### Interia

- Lokalny ID: `6` (`https://fakty.interia.pl/feed`).
- Domena: `wydarzenia.interia.pl`.
- Robots: `https://wydarzenia.interia.pl/robots.txt` deklaruje `https://wydarzenia.interia.pl/sitemap/wydarzenia.interia.pl-sitemap-index.xml.gz`.
- Indeks gzip zostal poprawnie pobrany, zdekompresowany i sparsowany; zawiera dziewiec segmentow.
- Probki map tresci obejmuja 78 URL z segmentu 2026-09-13 oraz 108 URL z segmentu 2021-01-01.
- Wynik: `verified`, `can_backfill=true`.
- Ograniczenie: data z mapy nie zastepuje daty publikacji odczytanej z metadanych materialu.

### Polsat News

- Lokalny ID: nie ustalono.
- Domena: `www.polsatnews.pl`.
- Robots: deklaruje `https://www.polsatnews.pl/sitemap.xml`.
- Indeks sitemap zawiera siedem map `sitemap0.xml`-`sitemap6.xml`.
- `sitemap0.xml`: 246 URL, daty lastmod 2026-09-13 do 2026-09-14.
- `sitemap6.xml`: 7930 URL, daty lastmod 2016-06-06 do 2016-07-06.
- Wynik: `verified` dla mechanizmu sitemap index; kandydat do backfillu po lokalnym przypisaniu ID.
- Ograniczenie: `lastmod` nie jest data publikacji; daty publikacji trzeba potwierdzac na metadanych stron dopiero w limitowanym backfillu.

### RMF24

- Lokalny ID: nie ustalono.
- Domena: `www.rmf24.pl`.
- Robots deklaruje `https://www.rmf24.pl/sitemap.xml`.
- Indeks zaladowany; 278 map dziennych, od mapy z 2026-09-14 do map z 2006 roku.
- Widoczny zakres lastmod probki: 2006-01-31 do 2026-09-14.
- Wynik: `verified` dla sitemap index; kandydat do backfillu po lokalnym przypisaniu ID.
- Ograniczenie: zakres dat wynika z map i lastmod, nie z dat publikacji rekordow.

### Rzeczpospolita

- Lokalny ID: nie ustalono.
- Domena: `www.rp.pl`.
- Robots deklaruje glowny indeks i news-sitemap.
- Glowny indeks zawiera 237 miesiecznych map od `sitemap.200701.xml` do `sitemap.202609.xml`.
- Mapa 202609: 1221 URL, lastmod 2026-09-01 do 2026-09-14.
- News-sitemap: 106 URL, lastmod 2026-09-12 do 2026-09-14; zawiera `news:publication_date`.
- Wynik: `verified` dla sitemap index; kandydat do backfillu po lokalnym przypisaniu ID.
- Ograniczenie: news-sitemap obejmuje tylko biezacy wycinek; glowna mapa jest wlasciwa dla historii.

### Dziennik Gazeta Prawna

- Lokalny ID: nie ustalono.
- Domena: `www.gazetaprawna.pl`.
- Robots: dokument zaladowany, bez jawnej sitemap.
- HTML strony glownej ujawnia `https://www.gazetaprawna.pl/.feed`.
- Wynik: `needs_review`.
- Powod: feed nie potwierdza cofania do starszych publikacji; nie zgadywano archiwum.

### TVP Info

- Lokalny ID: `12` (`https://www.tvp.info/rss/wiadomosci`).
- Domena: `tvp.info`.
- Robots deklaruje `https://tvp.info/sitemap-full_index.xml`.
- Indeks zawiera roczne/czastkowe mapy od 2024 do 2026.
- Probka `sitemap-full-2026-1.xml` zawiera 19 787 URL i rekordy do 2026-09-13; sprawdzono takze segment `2026-2`.
- Wynik: `verified`, `can_backfill=true` dla stalego cutoffu 2026-09-14.
- Ograniczenie: `lastmod` nie zastepuje daty publikacji odczytanej z metadanych materialu.

### Radio ZET

- Lokalny ID: nie ustalono.
- Domena: `radiozet.pl`.
- Robots zawiera jawne zastrzezenie przeciw eksploracji tekstow i danych oraz brak sitemap.
- HTML strony glownej nie ujawnil archiwum ani sitemap.
- Wynik: `blocked` dla tego zastosowania.
- Powod: brak podstawy do backfillu przy jawnym zastrzezeniu TDM; nie obchodzono go.

### Polskie Radio

- Lokalny ID: nie ustalono.
- Domena: `www.polskieradio.pl`.
- Odczyt `/robots.txt` nie dostarczyl robots; strona przekierowala/zwracala strone glowna i zarejestrowala zdarzenie 404.
- HTML pokazuje etykiety i linki archiwalnych podcastow, ale nie potwierdza paginowanego archiwum publikacji dla backfillu boxow.
- Wynik: `needs_review`.
- Powod: archiwalne nazwy audycji nie sa same w sobie obslugiwanym mechanizmem cofania.

## Istniejacy kandydaci

- Zero.pl, lokalny ID 150: istnieje katalogowy dowod oficjalnego sitemap index; nie wykonywano pelnego importu. Zachowany jako `verified` mechanizmu, zakres dat do potwierdzenia w osobnym pilocie.
- TV Republika, lokalny ID 151: istnieje dowod indeksu 107 map, ale brak potwierdzenia bezpiecznej biezacej sciezki do starszych rekordow. Zachowany jako `needs_review`; nie wykonywano pelnego importu.

## Rekomendacja

Do ograniczonego pilota mozna przygotowac Interie, Polsat News, RMF24, TVP Info i Rzeczpospolita. Zero.pl zachowuje wczesniejszy status kandydata, lecz jego zakres dat trzeba zmierzyc w pilocie. Pozostale zrodla wymagaja dowodu sitemap, API albo jawnego paginowanego archiwum. Rzeczywista liczba rownoleglych workerow nie przekroczy liczby zrodel z gotowymi zadaniami.
