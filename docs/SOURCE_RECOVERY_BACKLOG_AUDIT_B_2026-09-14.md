# Audyt B: źródła z największą kolejką archiwum

Data: 14 września 2026. Ten audyt używa wyłącznie lokalnego katalogu źródeł,
statystyk kolejki i wcześniejszych kart w repozytorium. Nie wykonano połączeń
z siecią, nie pobrano treści, nie zmieniono danych źródeł ani nie uruchomiono
harvestera. Brak zewnętrznej weryfikacji w tej partii oznacza **fail-closed**:
żadna pozycja nie jest zatwierdzeniem do aktywacji.

## Co oznacza „największy backlog”

Kolejka URL nie jest dowodem legalnego zakresu ani gwarancją, że adresy są
poprawnymi materiałami. Jest jedynie priorytetem dla diagnosty: przy dużej
liczbie oczekujących adresów błąd adaptera może marnować najwięcej pracy.

W momencie odczytu największe kolejki miały: Rzeczpospolita (756 355),
Infor.pl (384 870), RMF24 (382 511), Gazeta Krakowska (269 451), Gazeta
Wrocławska (217 525), Głos Wielkopolski (212 712), TV Republika (212 599),
Dziennik Bałtycki (176 259), Polityka (152 384), PortEl.pl (149 692),
wPolityce.pl (127 705), e-Sochaczew (105 752) i Spider’s Web (82 675).

## Decyzje kwalifikacyjne

| Priorytet | Źródło / lokalny kanał | Obserwacja lokalna | Decyzja | Następny dozwolony krok |
| --- | --- | --- | --- | --- |
| 1 | Rzeczpospolita / `rp.pl/rss/1019.xml` | 756 355 URL, 6 450 błędów; obecna konfiguracja wskazuje RSS. | `recovery` | Sprawdzić warunki, robots i aktualność wskazanego RSS. Jeśli kanał jest nadal oficjalny i dozwolony, dry-run maks. 3 wpisów wyłącznie metadanych. W przeciwnym razie `contact_required`. |
| 2 | Infor.pl / `infor.pl/rss/wiadomosci.xml` | 384 870 URL, 6 485 błędów; lokalna karta ma błąd „nieprawidłowy lub niedostępny RSS”. | `recovery` | Nie próbować starego feedu w pętli. Szukać wyłącznie opublikowanego przez wydawcę RSS/API/eksportu lub jawnie dozwolonego indeksu. Bez takiego dowodu: `contact_required`. |
| 3 | RMF24 / `rmf24.pl/fakty/feed` | 382 511 URL, 6 454 błędów; konfiguracja istnieje. | `recovery` | Najpierw diagnoza transportu i ważności oficjalnego feedu, bez zmiany na HTML. Gdy feed/warunki nie są jednoznaczne: ręczna kontrola lub kontakt. |
| 4 | TVP Info / `tvp.info/tvp.info/rss+xml.php` | 23 828 URL, ale 7 818 błędów — najwyższy udział błędów w grupie. | `recovery` | Zbadać wyłącznie aktualny oficjalny feed/API i status wcześniejszego endpointu. Nie zwiększać limitu ani nie przechodzić na crawl stron artykułów bez niezależnego dowodu. |
| 5 | NaTemat / `natemat.pl/rss/wszystkie` | 47 321 URL, 6 692 błędów. | `recovery` | Udokumentować aktualność feedu i warunki automatycznego pozyskiwania metadanych. Brak potwierdzenia = `contact_required`. |
| 6 | OKO.press / `oko.press/feed/` | 20 423 URL, 6 508 błędów. | `recovery` | Rozdzielić błąd transportu od błędu feedu. Test tylko po weryfikacji warunków oraz z 3-sekundowym limiterem; brak sukcesu po dry-run = ręczna kontrola. |
| 7 | Polityka / `polityka.pl/rss/articles.xml?list=517` | 152 384 URL, 1 441 błędów; lokalny katalog zawiera dwa feedy. | `manual_review` | Nie przełączać automatycznie między feedami. Najpierw udokumentować, który jest oficjalny, jego zakres i warunki; potem pojedynczy dry-run. |
| 8 | Gazeta Krakowska, Gazeta Wrocławska, Głos Wielkopolski, Dziennik Bałtycki / RSS | Łącznie 875 947 URL, pojedyncze błędy (2–4 na źródło). Brak osobnych lokalnych kart podstawy dostępu. | `manual_review` | Niski udział błędów nie zastępuje dowodu warunków. Zrobić wspólny audyt wydawcy/warunków oraz dokładnie jednego oficjalnego kanału per domena. Do tego czasu nie zwiększać skali. |
| 9 | TV Republika / sitemap | 212 599 URL, 0 błędów; lokalna notatka potwierdza indeks sitemap, ale nie zawiera podstawy automatycznego reuse. | `manual_review` | Sprawdzić warunki, robots i zakres metadanych. Techniczna dostępność sitemap nie jest zgodą na archiwum lub snapshot. |
| 10 | PortEl.pl, e-Sochaczew i lokalne portale | duże kolejki, konfiguracje oparte na dawnych kandydaturach/katalogu lokalnych mediów. | `manual_review` | Najpierw każda domena wymaga aktualnego dowodu kanału i warunków. Nie uznawać starej notatki kandydata za automatyczną zgodę. |
| 11 | wPolityce.pl i Spider’s Web | duże kolejki, 0 bieżących błędów, konfiguracja RSS. | `manual_review` | Utrzymać poza automatyczną eskalacją do czasu osobnej kwalifikacji podstawy dostępu. Sprawdzić tylko oficjalny kanał i warunki, bez alternatyw HTML. |

## Kolejność odzyskiwania

1. **TVP Info, Infor.pl, RMF24, Rzeczpospolita, NaTemat i OKO.press**:
   powód to duży bezwzględny licznik błędów. Każde źródło otrzymuje osobną
   sprawę `SourceRecoveryCase`; nie łączyć ich w jedną „naprawę RSS”.
2. **Grupa regionalna wydawcy Polska Press** (cztery domeny): najpierw
   dokumentacja warunków i kanałów, potem niezależna decyzja dla każdej domeny.
3. **TV Republika, PortEl.pl, e-Sochaczew, wPolityce.pl, Spider’s Web**:
   brak bieżącego błędu nie pozwala kontynuować bez podstawy. To audyt
   kwalifikacyjny, nie priorytet masowego harvestera.

## Wymagana instrukcja po odzyskaniu

Każda pozytywna sprawa musi wytworzyć wersjonowaną instrukcję z:

- oficjalnym URL-em kanału, `channel=api|rss|export|oai_pmh|sitemap|html`;
- URL-em warunków/licencji i datą ich sprawdzenia;
- wynikiem `robots.txt` dla konkretnej ścieżki, gdy dotyczy;
- zakresem `metadata` / `content` / `snapshot` — domyślnie tylko `metadata`;
- limitem: jeden aktywny request na domenę i interwał nie krótszy niż 3 s;
- limitem dry-run: kanał + do 3 materiałów oraz mierzalnym przyrostem boxów;
- regułą kwarantanny po 3 błędach bez boxa.

Niepowodzenie dry-run albo brak jednego dowodu kończy sprawę jako
`manual_review` lub `contact_required`. Karta kontaktowa ma prosić o RSS/API
lub eksport metadanych i pisemne określenie zakresu; nie wysyłać jej bez
osobnej decyzji redakcyjnej.

## Przekazanie

- **Agent recovery:** bierze wyłącznie jeden `source_id` naraz, przechodzi
  sekwencję z `SOURCE_RECOVERY_WORKFLOW.md` i nie uruchamia masowej kolejki.
- **Harvester:** dostaje wyłącznie instrukcje `approved` po dodatnim dry-run.
- **Agent korespondencji:** otrzymuje tylko rekordy `contact_required` wraz z
  dowodami i szkicem zakresu prośby.

Wniosek: obecny backlog ma wartość diagnostyczną, lecz największą szansę na
realny, legalny przyrost daje naprawa pojedynczego kanału potwierdzona testem,
a nie zwiększanie liczby równoległych prób.

