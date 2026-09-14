# Kandydaci: polskie instytucje publiczne na WordPress REST API — audyt negatywny

Stan: 14 września 2026. Zadanie: znaleźć maksymalnie 5 polskich oficjalnych instytucji publicznych
istotnych dla kontekstu politycznego, których serwis ma **publiczne WordPress REST API** oraz
**jednoznaczne warunki ponownego wykorzystywania informacji sektora publicznego** — oddzielnie dla
(a) samych metadanych/linków i (b) pełnego tekstu, RAG i treningu modeli. Samo istnienie API lub
mapy witryny nie zostało potraktowane jako zgoda. Nie pobierano korpusów ani artykułów, nie
aktywowano żadnego źródła, nie zmieniono bazy `Source` ani żadnego pliku konfiguracyjnego scrapera.

**Wynik: żaden kandydat nie spełnił obu warunków jednocześnie.** Zgodnie z briefem to poprawne,
negatywne zakończenie audytu — do `backend/scraper/data/verified_local_sources.json` ani do
`backend/scraper/catalog.py` (`INSTITUTIONS`) nie dodano żadnego wpisu.

## Sprawdzone wcześniej źródła (żeby nie powielać)

Przejrzano `docs/SOURCE_CATALOG.md`, `docs/SOURCE_EXPANSION.md`,
`docs/SOURCE_ARCHIVE_AUDIT_2026-09-14.md` (fala 1–3), `backend/scraper/catalog.py` (`INSTITUTIONS`,
RSS-only, żadna pozycja nie deklaruje WordPress) i
`backend/scraper/data/verified_local_sources.json` (22 wpisy, mechanizm wyłącznie
`sitemap_index`; żaden wpis nie deklaruje `mechanism: "wordpress_rest"` — adapter
`backend/scraper/wordpress_rest_adapter.py` jest więc obecnie nieaktywny dla całego katalogu).
Sejm/ELI (`backend/scraper/official.py`) korzystają z własnego, niededykowanego WordPressowi API
`api.sejm.gov.pl` i nie są przedmiotem tego audytu.

## Metoda

Dla każdej instytucji: (1) wyszukiwanie `site:<domena> wp-content OR wp-json` jako pierwszy sygnał
techniczny, (2) przy pozytywnym sygnale — pojedyncze zapytanie do `wp-json/wp/v2/posts` (tylko
metadane, `per_page=1`) i odczyt `robots.txt`, (3) wyszukiwanie jawnej strony/wpisu o „ponownym
wykorzystywaniu informacji sektora publicznego" lub licencji na domenie głównej i na powiązanym BIP.
Statusy: `potwierdzone`, `niejednoznaczne`, `brak`/`odrzucone`.

## Wyniki

### Rzecznik Praw Dziecka (`brpd.gov.pl`)

- **Endpoint techniczny**: `potwierdzone`. `https://brpd.gov.pl/wp-json/wp/v2/posts?per_page=1`
  zwrócił poprawny JSON WordPress (post `id: 20524`, `date`, `link`, `title.rendered`) — publiczne,
  niewymagające uwierzytelnienia REST API `wp/v2`.
- **Robots**: `https://brpd.gov.pl/robots.txt` — tylko `Disallow: /wp-admin/` (z wyjątkiem
  `admin-ajax.php`) i `Sitemap: https://brpd.gov.pl/wp-sitemap.xml`. Brak wpisów dla botów AI
  (GPTBot, CCBot, Google-Extended itd.) — czyli robots nie blokuje, ale też nie stanowi zgody.
- **Prawny — metadane/linki**: `niejednoznaczne`. Nie znaleziono na domenie głównej (`brpd.gov.pl`)
  żadnej stopki/strony z regulaminem czy notą o ponownym wykorzystaniu; jedyny znaleziony zapis jest
  na osobnym systemie BIP (`https://bip.brpd.gov.pl/ponowne-wykorzystanie-informacji-publicznej/`):
  „Informacje zawarte w BIP mogą być wykorzystane ponownie na dowolnych środkach eksploatacji w
  dowolnym celu za podaniem źródła." Zapis dotyczy wprost „informacji zawartych w BIP" — czyli
  rejestru wymaganego ustawowo (akty, majątek, struktura), a nie treści publikowanych przez osobny
  system WordPress na `brpd.gov.pl` (aktualności, oferty pracy). Nie znaleziono deklaracji, że ta
  zasada rozciąga się na serwis WordPress.
- **Prawny — pełny tekst / RAG / trening**: `brak`. Zapis BIP nie wspomina eksploracji tekstu i
  danych, systemów AI ani treningu modeli; nie ma też oddzielnej licencji (np. CC BY) dla treści
  WordPress. Sam fakt istnienia publicznego REST API nie jest tu traktowany jako zgoda.
- Dowody: `https://brpd.gov.pl/wp-json/wp/v2/posts?per_page=1`,
  `https://brpd.gov.pl/robots.txt`, `https://bip.brpd.gov.pl/ponowne-wykorzystanie-informacji-publicznej/`
  — sprawdzone 2026-09-14.
- **Wniosek**: nie dodano. Warstwa prawna niejednoznaczna nawet dla samych metadanych/linków, a dla
  pełnego tekstu/RAG/treningu — brak jakiejkolwiek deklaracji.

### Rzecznik Finansowy (`rf.gov.pl`)

- **Endpoint techniczny**: `potwierdzone`. `https://rf.gov.pl/wp-json/wp/v2/posts?per_page=1`
  zwrócił poprawny JSON WordPress (post `id: 26083`, `link`, `title.rendered`, `date`).
- **Robots**: `https://rf.gov.pl/robots.txt` — `Disallow: /wp-admin/` (wyjątek
  `admin-ajax.php`), blok wtyczki WPForms (`Disallow: /wp-content/uploads/wpforms/`) i
  `Sitemap: https://rf.gov.pl/sitemap_index.xml`. Sitemap index (`wp-sitemap.xml`, sprawdzony
  osobno) pokazuje typowy zestaw WordPressa (post-sitemap 1–4, oferty pracy, webinaria, kary
  pieniężne itd.) — dojrzała, aktywna instalacja. Brak wpisów dla botów AI.
- **Prawny — metadane/linki**: `brak`. Domena główna nie ma jawnej strony o ponownym
  wykorzystaniu; osobny BIP (`https://bip.rf.gov.pl/`) istnieje, ale sprawdzona strona główna BIP nie
  zawiera linku ani tekstu o ponownym wykorzystaniu informacji publicznej — w przeciwieństwie do RPD
  nie znaleziono nawet ogólnikowej deklaracji.
- **Prawny — pełny tekst / RAG / trening**: `brak`. Nie znaleziono żadnej deklaracji.
- Dowody: `https://rf.gov.pl/wp-json/wp/v2/posts?per_page=1`, `https://rf.gov.pl/robots.txt`,
  `https://rf.gov.pl/wp-sitemap.xml`, `https://bip.rf.gov.pl/` — sprawdzone 2026-09-14.
- **Wniosek**: nie dodano. Endpoint techniczny potwierdzony, ale zerowa podstawa prawna.

### Instytucje sprawdzone i odrzucone na etapie technicznym (brak sygnału WordPress)

Dla poniższych sprawdzono `site:<domena> wp-content OR wp-json`, a w przypadkach granicznych
dodatkowo `robots.txt`; żadna nie dała dowodu na WordPress, więc nie sprawdzano dalej warstwy
prawnej:

| Instytucja | Domena | Obserwacja |
| --- | --- | --- |
| Trybunał Konstytucyjny | `trybunal.gov.pl` | brak sygnału wp-content/wp-json |
| Krajowa Rada Radiofonii i Telewizji | `krrit.gov.pl` | brak sygnału; archiwum na osobnej domenie `archiwum.krrit.gov.pl` |
| Instytut Pamięci Narodowej | `ipn.gov.pl` | brak sygnału |
| Przystanek Historia (portal edukacyjny IPN) | `przystanekhistoria.pl` | brak sygnału |
| Państwowa Komisja Wyborcza | `pkw.gov.pl` | brak sygnału |
| Krajowe Biuro Wyborcze / delegatury | `kbw.gov.pl` | brak sygnału |
| Urząd Ochrony Danych Osobowych | `uodo.gov.pl` | brak sygnału |
| Centralne Biuro Antykorupcyjne | `cba.gov.pl` / `bip.cba.gov.pl` | brak sygnału (BIP, nie WordPress) |
| Naczelny Sąd Administracyjny | `nsa.gov.pl` | brak sygnału |
| Sąd Najwyższy | `sn.pl` | brak sygnału |
| Senat RP | `senat.gov.pl` | brak sygnału |
| Rzecznik Praw Obywatelskich | `rpo.gov.pl` | przekierowuje (302) na `bip.brpo.gov.pl`, platforma BIP, nie WordPress |
| Rzecznik Małych i Średnich Przedsiębiorców | `rzecznikmsp.gov.pl` | brak sygnału |
| Urząd Zamówień Publicznych | `uzp.gov.pl` | brak sygnału (przeniesiony na platformę `gov.pl`) |
| Państwowa Inspekcja Pracy | `pip.gov.pl` | brak sygnału |
| Krajowa Rada Sądownictwa | `krs.pl` | `robots.txt` ujawnia Joomlę (`/administrator/`, `/components/` itd.), nie WordPress |

Ministerstwa i większość urzędów centralnych (KPRM, resorty, GUS, NBP, NIK, Kancelaria Prezydenta)
korzystają z ujednoliconej platformy `gov.pl`, która nie jest WordPressem — potwierdzone już
pośrednio przez `backend/scraper/catalog.py` (`INSTITUTIONS`, wyłącznie RSS) i nieobjęte tu ponowną
kontrolą technologii.

## Dlaczego zero dodań do pliku danych

Brief wymagał dodania kandydata do pliku danych wyłącznie, gdy **jednocześnie**: (1) technika —
publiczne, nieuwierzytelnione WordPress REST API — jest potwierdzona, oraz (2) zakres dozwolonego
wykorzystania jest jednoznacznie potwierdzony **osobno** dla metadanych/linków i dla pełnego
tekstu/RAG/treningu, z pominięciem samego istnienia API/mapy jako dowodu zgody. Oba potwierdzone
technicznie przypadki (RPD, Rzecznik Finansowy) nie mają takiej jednoznacznej podstawy prawnej —
w RPD zapis BIP dotyczy innego korpusu niż treści WordPress, a w Rzeczniku Finansowym nie znaleziono
żadnego zapisu. Żadna sprawdzona instytucja bez BIP-owego zastrzeżenia AI/eksploracji danych nie
została uznana za "dozwoloną" wyłącznie na podstawie ogólnej ustawy o otwartych danych i ponownym
wykorzystywaniu informacji sektora publicznego (2021) — ustawowe domniemanie dostępności nie jest
tu traktowane jako instytucjonalnie potwierdzona, jednoznaczna zgoda wymagana przez brief.

## Ryzyka i ograniczenia

- Wyszukiwarka (`site:` + `WebSearch`) zależy od indeksowania przez wyszukiwarkę; brak wyniku nie
  jest dowodem nieistnienia WordPressa — mniejsze/rzadziej cytowane instytucje mogły zostać pominięte
  fałszywie negatywnie. Rekomendacja: przy kolejnej turze użyć bezpośredniego sprawdzenia
  `HEAD /wp-json/` dla instytucji, które nie trafiły do indeksu wyszukiwarki.
  - Sprawdzono tylko krajowe organy centralne istotne dla kontekstu politycznego (trybunały, RPO/RPD,
  KRRiT, PKW/KBW, CBA, NSA/SN, regulatorzy). Nie sprawdzono samorządów wojewódzkich, wojewodów ani
  mniejszych agencji — poza zakresem "istotne dla kontekstu politycznego" przyjętym w tym audycie.
- Odczyt treści stron BIP i robots.txt wykonano narzędziem do pobierania stron (renderowanym przez
  mały model pośredniczący); nie zweryfikowano bajt-po-bajcie przez `curl`. Dla ewentualnej przyszłej
  aktywacji zalecana jest niezależna weryfikacja `curl -s https://<domena>/robots.txt` i pełnej treści
  strony o ponownym wykorzystaniu przed jakąkolwiek zmianą `verified_local_sources.json`.

## Następny krok

Jeśli priorytetem pozostaje pozyskanie instytucji publicznych z jednoznaczną zgodą, dwie możliwe
ścieżki: (a) wysłać zapytanie o ponowne wykorzystanie informacji sektora publicznego bezpośrednio do
RPD i Rzecznika Finansowego z prośbą o pisemne potwierdzenie, że zasada „dowolny cel, podanie źródła"
obejmuje też treści z serwisu WordPress (aktualności), nie tylko rejestr BIP; (b) rozszerzyć listę
kandydatów o instytucje szczebla wojewódzkiego/samorządowego, jeśli mieszczą się w zakresie „kontekst
polityczny" — tam WordPress jest częstszy, ale wymaga osobnej decyzji właściciela co do zakresu tego
audytu.
