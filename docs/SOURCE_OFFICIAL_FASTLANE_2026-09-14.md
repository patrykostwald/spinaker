# Oficjalne źródła — szybka ścieżka API

Stan: 14 września 2026. Raport uzupełnia fale 1–3 i celowo nie powtarza zakończonych audytów KNF, NIK, NSA/CBOSA, BZP, URE BIP, UOKiK sitemap, PKW, RCL, dane.gov.pl ani UODO. Sprawdzano wyłącznie oficjalne dokumentacje i warunki. Nie uruchomiono pobierania, nie wysłano zapytań do instytucji i nie zmieniono bazy.

## Gotowe do ograniczonego pilota adaptera

| Źródło / host | Oficjalny punkt wejścia | Prawo i atrybucja | Zakres i jawny limit | Dozwolone warstwy |
|---|---|---|---|---|
| GUS — Bank Danych Lokalnych (`bdl.stat.gov.pl`) | REST `https://bdl.stat.gov.pl/api/v1/`; dokumentacja `https://api.stat.gov.pl/Home/BdlApi/1000` | Portal BDL oznacza dane licencją CC BY 4.0. Zachować GUS/BDL jako źródło, URL zasobu, czas pozyskania i informację o przetworzeniu. | Ponad 40 tys. cech; dane od 1995 r. Anonimowo: 5/s, 100/15 min, 1000/12 h, 10 000/7 dni. Z kluczem: 10/s, 500/15 min, 5000/12 h, 50 000/7 dni. Dla nocnego pilota bez klucza przyjąć **1 żądanie / 3 s**, małe strony, cache słowników i obsługę `429`. | Metadane i wartości: tak. Pełna treść: nie dotyczy (dane strukturalne). Snapshot: prywatny JSON z hashem, tak. RAG: tylko fakty z atrybucją. Trening: wyłączony do osobnej decyzji. |
| UOKiK — SUDOP (`api-sudop.uokik.gov.pl`) | `https://api-sudop.uokik.gov.pl/sudop-api/`; instrukcja i przykłady na `https://uokik.gov.pl/sudop` | UOKiK wyraża zgodę na ponowne wykorzystanie pod warunkiem podania bezpośredniego źródła, daty pozyskania, informacji o zmienności danych, odpowiedzialności podmiotów udzielających i pomocniczym charakterze bazy. | Pomoc publiczna i de minimis z ostatnich 10 lat od 1 stycznia roku n-10; do 10 tys. wierszy na stronę; **15 zapytań/min**; dostęp bez rejestracji, wyniki kolejkowane. Pilot: najwyżej 1 żądanie / 4 s, jeden raport naraz, honorować czas przygotowania i `429`. | Metadane i rekordy: tak. Pełna treść: nie dotyczy. Snapshot: prywatny JSON/CSV z datą pozyskania i hashem, tak. RAG: wyłącznie z obowiązkowymi zastrzeżeniami. Trening: wyłączony; robots serwisu głównego blokuje nazwane boty AI. |

Robots dla hostów API nie został uznany za samodzielną podstawę uprawnienia: punkty wejścia są oficjalnymi API zaprojektowanymi do automatycznego odczytu, a ich dokumentacje podają jawne limity. Adapter nadal musi używać własnego, identyfikowalnego user-agenta i zatrzymać się, jeśli robots hosta API lub odpowiedź serwera zabroni danej ścieżki.

## Dobre kandydatury, jeszcze nie gotowe

| Źródło | Potwierdzone | Brak przed dołączeniem |
|---|---|---|
| NBP Web API (`api.nbp.pl`) | Oficjalne JSON/XML; kursy walut od 2.01.2002, ceny złota od 2.01.2013; maks. 93 dni na zapytanie | Dokumentacja nie podaje limitu częstotliwości ani jednoznacznej licencji na ponowne wykorzystanie. Nie ustawiać automatycznie 3 s i nie uruchamiać nocnego backfillu. |
| URE — infrastruktura paliw ciekłych (`api.ure.gov.pl`) | Anonimowe REST GET, JSON/XML; jawny limit 3/10 s i 25/2 min | Instrukcja odsyła do Regulaminu, którego warunków nie potwierdzono w tym audycie. Dopuścić dopiero po zapisaniu wersji Regulaminu i mapy zasobów. |
| GUS — SDG (`api.stat.gov.pl` / GitHub Statistics Poland) | Pełne dane i metadane SDG; 60 zapytań/h anonimowo, 5000/h przez GitHub z tokenem | Współdzieli host dokumentacyjny GUS i nie zwiększa liczby niezależnych domen; przed pilotem przypisać licencję repozytorium i endpointy plików. |
| GUS — REGON BIR (`api.stat.gov.pl`) | Bezpłatne dane; limity 3/s w dzień, 4/s w nocy oraz limity minutowe i godzinowe | Produkcja wymaga klucza uzyskiwanego po kontakcie i przekazaniu danych podmiotu. Nie wysyłano wiadomości; nie jest gotowe bez decyzji właściciela. |
| Otwarte API KRS (`api-krs.ms.gov.pl`) | Ministerstwo Sprawiedliwości potwierdza bezpłatny dostęp do odpisów aktualnych/pełnych i listy wpisów z dnia; dane osób są anonimizowane | Nie znaleziono jawnego limitu wywołań ani kompletnej polityki ponownego wykorzystania dla masowego archiwum. |

## Instrukcja dla integratora

1. Dodać osobne adaptery `gus_bdl` i `uokik_sudop`; nie kierować ich do importera stron ani OCR.
2. Trzymać jedną kolejkę na host. Limit globalny musi uwzględniać wszystkie workery, a nie tylko pojedynczy proces.
3. BDL: przy 3-sekundowym odstępie rzeczywistym ograniczeniem będzie limit 100/15 min, dlatego po 100 żądaniach zatrzymać host do końca okna. Nie zwiększać równoległości na tej domenie.
4. SUDOP: raporty są asynchroniczne. Zapisać token zadania i odpytywać oszczędnie; nie tworzyć duplikatu raportu podczas oczekiwania.
5. Każdy rekord zachowuje endpoint, parametry bez sekretów, czas pozyskania, wersję/licencję, hash odpowiedzi i komplet wymaganych zastrzeżeń.
6. RAG pozostaje osobną, odwracalną warstwą. Brakujące zastrzeżenie lub atrybucja blokuje indeksowanie. Trening pozostaje wyłączony.

Wynik tej fali to **2 nowe niezależne hosty gotowe do napisania pilota**, nie 12. Pozostałych nie wolno liczyć do puli 32, dopóki nie mają jednocześnie stabilnego punktu wejścia, podstawy ponownego wykorzystania, jawnego limitu i zakończonej kontroli robots.

## Dowody pierwotne

- BDL: `https://api.stat.gov.pl/Home/BdlApi/1000`, `https://bdl.stat.gov.pl/BDL/pages/Home.aspx`.
- Warunki GUS: `https://bip.stat.gov.pl/kontakt/ponowne-wykorzystywanie-informacji-sektora-publicznego/`.
- SUDOP: `https://uokik.gov.pl/sudop`, `https://api-sudop.uokik.gov.pl:9443/devportal/apis`.
- NBP: `https://api.nbp.pl/`.
- URE API: `https://api.dane.gov.pl/resources/39791,instrukcja-obslugi-api-infrastruktura-paliw-cieklych-instalacje-przeladunku/file`.
- GUS SDG i REGON: `https://api.stat.gov.pl/Home/SDGApi`, `https://api.stat.gov.pl/Home/RegonApi`.
- KRS: `https://prs.ms.gov.pl/krs`.
