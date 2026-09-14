# Ciągły audyt źródeł — partia B (2026-09-14)

## Cel i granice

To jest audyt kandydatów do legalnego, odtwarzalnego pozyskiwania **metadanych lub danych referencyjnych**. Nie włączono źródeł do harvestera, nie pobrano korpusu, HTML, obrazów ani snapshotów. Wynik dodatni dla technicznego API nie oznacza jeszcze, że jest ono źródłem artykułów: dane transportowe, statystyczne i rejestrowe mają pozostać osobną klasą danych referencyjnych, a nie być sztucznie zamieniane w redakcyjne boxy.

Warunkiem aktywacji jest jednocześnie: potwierdzony przez podmiot kanał, aktualny `robots.txt` dla konkretnej ścieżki (gdy kanał jest HTTP), warunki ponownego wykorzystania dla konkretnego zasobu oraz pojedynczy test dry-run. Wszystkie decyzje są fail-closed: niejasność oznacza brak automatycznego pobierania oraz kartę do ręcznej kontroli lub kontaktu.

## Wynik

**Nie ma nowego automatycznie aktywowanego źródła.** Dwa repozytoria danych otwartych są obiecujące jako osobna, późniejsza warstwa danych referencyjnych, ale wymagają wskazania konkretnych zbiorów i ich warunków. Pozostałe pozycje otrzymały kartę ręcznej kontroli lub kontaktu.

| Podmiot / host | Kanał publiczny | Dowód warunków i ograniczenia | Decyzja | Następny krok |
| --- | --- | --- | --- | --- |
| **Otwarte Dane Wrocław** / `opendata.cui.wroclaw.pl` | Portal katalogowy Open Data; podmiot opisuje dane jako dostępne w formatach czytelnych dla systemów. | Portal deklaruje możliwość wykorzystania danych, ale odsyła do warunków **każdego zbioru**; jego ogólne warunki wymagają poszanowania praw osób trzecich. | **Ręczna kwalifikacja zasobu** | Wybrać pojedynczy zbiór z licencją/warunkami i dopiero wtedy zaimplementować adapter katalogu lub API. Nie traktować artykułów portalu jako zgody na archiwum. |
| **Otwarte Dane Warszawy** / `dane.um.warszawa.pl`, `api.um.warszawa.pl` | Miasto publicznie wskazuje nowy portal danych i wygaszanie starszego API. | Oficjalna strona potwierdza migrację, więc nie wolno wiązać trwałego harvestera ze starym endpointem. W tym audycie nie potwierdzono warunków konkretnego zbioru ani aktualnego kontraktu API. | **Wstrzymane — migracja** | Po ustabilizowaniu nowego portalu sprawdzić licencję, OpenAPI/eksport i `robots.txt`; potem wybrać tylko dane referencyjne o jasnym reuse. |
| **Otwarty Gdańsk / ZTM Gdańsk** / `ckan.multimediagdansk.pl` | Repozytorium danych ZTM, pliki/eksporty publikowane przez portal Otwarty Gdańsk. | Regulamin opisuje nieodpłatne korzystanie z danych publicznych oraz wymaga podania nazwy źródła i dat wytworzenia/pozyskania. Dotyczy konkretnie danych ZTM, nie całego serwisu ani artykułów. | **Kandydat do danych referencyjnych po dry-run** | Ustalić jeden otwarty zasób oraz jego format/licencję; pobierać tylko z oficjalnego eksportu/API, z atrybucją i datami. Nie dodawać do kolejki boxów. |
| **Portal danych dane.gov.pl** / `dane.gov.pl` | Katalog krajowych zbiorów oraz walidator zgodności API dla partnerów. | Serwis promuje bezpłatne użycie także komercyjne, ale podstawa i warunki są przypisane do pojedynczego zasobu. Strona katalogu wymaga JavaScript, więc nie należy opierać automatu na nieudokumentowanym renderowaniu. | **Ręczna kwalifikacja zasobu** | Wybierać tylko rekordy z jednoznaczną licencją, linkiem do oficjalnego eksportu/API i zapisanym dowodem warunków; katalog metadanych może później mieć własny adapter. |
| **GUS — API DBW** / `api-dbw.stat.gov.pl` | Oficjalny katalog `dane.gov.pl` wskazuje API DBW oraz adres definicji OpenAPI. | Potwierdzony standard techniczny OpenAPI, ale brak w tym audycie decyzji o konkretnym zbiorze, licencji i mapowaniu na model spin.clinic. | **Ręczna kwalifikacja danych statystycznych** | Osobny adapter referencyjny: wskaźniki/serie, bez tworzenia boxów artykułowych; najpierw odczytać warunki dla wybranego endpointu i zrobić dry-run. |
| **Ministerstwo Finansów — Trezor API** / `trezor-api.mf.gov.pl` | Oficjalny katalog partnerów Otwarte Dane Plus wymienia Trezor API. | Potwierdzono istnienie API, nie potwierdzono w tym audycie zakresu, licencji danych ani potrzeby dla MVP. | **Wstrzymane — poza bieżącym zakresem** | Wrócić wyłącznie, gdy moduł referencyjny potrzebuje danych finansów publicznych; wtedy audyt endpointu i warunków per zasób. |
| **Ministerstwo Sportu i Turystyki — API rejestrów** / `api.turystyka.gov.pl` | Oficjalny katalog partnerów Otwarte Dane Plus wymienia API rejestrów turystycznych. | Techniczne API nie odpowiada obecnemu celowi archiwum wiadomości; w audycie brak sprawdzenia warunków konkretnego endpointu. | **Wstrzymane — poza zakresem** | Zachować jako kandydat na późniejszą bazę referencyjną, bez harvestera i bez snapshotów. |
| **Regionalna Izba Obrachunkowa w Warszawie — BIP** / `bip.warszawa.rio.gov.pl` | BIP ma aktualności, archiwum i dedykowaną stronę o ponownym wykorzystaniu. | Nie znaleziono w tym audycie stabilnego RSS/API/sitemap ani jednoznacznej automatycznej ścieżki dla publikacji. Strona ujawnia redakcję BIP — to właściwy kanał wyjaśnienia zakresu. | **Karta do kontaktu** | Przygotować wniosek o ponowne wykorzystanie dla metadanych uchwał/aktualności, wskazać wymagany format (RSS/API/CSV), częstotliwość i brak pełnotekstowych snapshotów bez zgody. |

## Instrukcja dla przyszłego harvestera

1. Dla danych otwartych pobierać wyłącznie udokumentowany eksport/API danego zasobu, przy maksymalnie jednym żądaniu na host i odstępie co najmniej 3 s.
2. Zawsze zapisać: `source_url`, identyfikator zasobu, kanał (`api` / `export`), URL dowodu warunków, datę sprawdzenia, wymagane oznaczenie źródła oraz datę pozyskania. Nie zapisywać pełnej treści, HTML ani zrzutów bez osobnej decyzji.
3. Dry-run ma objąć jeden rekord i sprawdzić deduplikację, atrybucję, format, limiter i możliwość ponownego odtworzenia wyniku.
4. Błąd 4xx/5xx, brak licencji, migracja API lub konflikt warunków oznaczają zatrzymanie tylko tego źródła; nie wolno tworzyć pętli retry ani próbować alternatywnej, niezatwierdzonej ścieżki.

## Karty kontaktowe

* **RIO Warszawa:** prośba o wskazanie oficjalnego eksportu/API/RSS dla metadanych publikacji BIP, zakresu automatycznej aktualizacji oraz warunków ponownego wykorzystania i snapshotów.
* **Właściciele konkretnych zbiorów Wrocław/Warszawa:** tylko gdy licencja lub opis zasobu nie rozstrzyga danych potrzebnych dla projektu. Pytanie ma wskazywać zestaw, pola, częstotliwość, atrybucję i fakt, że pełny tekst oraz obrazy nie są objęte prośbą.

## Źródła pierwotne

1. [Otwarte Dane Wrocław — o serwisie](https://opendata.cui.wroclaw.pl/pages/o-serwisie)
2. [Otwarte Dane Wrocław — warunki korzystania](https://open-data.cui.wroclaw.pl/tresc/warunki-korzystania-z-danych/)
3. [Warszawa 19115 — Dane po warszawsku](https://warszawa19115.pl/web/guest/-/dane-po-warszawsku)
4. [ZTM Gdańsk — regulamin korzystania z danych](https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource/09cafa1b-604b-4408-ac48-5720319b72b7/download/regulamin_korzystania_z_danych.pdf)
5. [Dane.gov.pl — walidator API i lista partnerów](https://dane.gov.pl/tools/api-validator/)
6. [RIO Warszawa BIP — ponowne wykorzystywanie](https://bip.warszawa.rio.gov.pl/kategorie/78-dostep-do-informacji-publicznej-zasady/artykuly/181-ponowne-wykorzystywanie-informacji-publicznej-?lang=PL)
7. [KPRM — opis procedury ponownego wykorzystania](https://www.gov.pl/web/premier/ponowne-wykorzystywanie)

Ten raport jest dokumentem roboczym z dnia 2026-09-14. Przed aktywacją należy ponownie sprawdzić stan techniczny oraz warunki konkretnego zasobu.

