# Rekonesans końca katalogu — kanały i podstawy dostępu

**Zakres:** ostatnie 82 pozycje `sources.md`, sprawdzenie 16 września 2026. To jest rekonesans dowodowy, nie decyzja prawna ani uruchomienie źródła. Karta może powstać dopiero po ponownym sprawdzeniu dokumentu, kanału i odpowiedzi transportu.

**Klasyfikacja:**

- **Możliwa karta** — znaleziono oficjalny, maszynowy kanał oraz publiczną podstawę ponownego użycia; przed aktywacją wymagany mały test adaptera i zakresu.
- **Wymaga kontaktu** — nie potwierdzono jednocześnie kanału i warunków dla automatycznego pobierania. Nie aktywować.
- **Odrzucić** — wpis jest błędnym/nieaktualnym adresem albo nie jest źródłem redakcyjno-faktograficznym dla pilota.

| Źródło | Oficjalny kanał / URL | Warunki lub licencja | Klasyfikacja | Krótki dowód / zakres |
|---|---|---|---|---|
| europarl.europa.eu | RSS: `https://www.europarl.europa.eu/rss/doc/top-stories/en.xml` | `https://www.europarl.europa.eu/legal-notice/en/` | Możliwa karta | Oficjalny RSS Parlamentu; karta wyłącznie nagłówki/metadane, oddzielnie od materiałów osób trzecich. |
| ec.europa.eu | RSS: `https://ec.europa.eu/commission/presscorner/api/rss?language=en` | `https://ec.europa.eu/info/legal-notice_en` | Możliwa karta | Oficjalny kanał Press Corner; polityka Komisji co do zasady CC BY 4.0, z wyłączeniami dla praw osób trzecich. |
| consilium.europa.eu | RSS: `https://www.consilium.europa.eu/en/press/press-releases/rss/` | `https://www.consilium.europa.eu/en/about-site/copyright/` | Możliwa karta | Oficjalny kanał komunikatów; warunki wymagają wskazania źródła i niezmieniania sensu. |
| nato.int | RSS: `https://www.nato.int/cps/en/natohq/rss.xml` | `https://www.nato.int/cps/en/natohq/terms_of_use.htm` | Wymaga kontaktu | Kanał jest oficjalny, lecz zastosowanie warunków do automatycznego archiwum wymaga sprawdzenia w karcie. |
| oecd.org | Newsroom: `https://www.oecd.org/en/newsroom.html` | `https://www.oecd.org/en/about/legal.html` | Wymaga kontaktu | Wykryto oficjalny newsroom, nie potwierdzono stabilnego RSS dla całego zakresu ani licencji na automatyczne pobranie. |
| osce.org | RSS: `https://www.osce.org/rss.xml` | `https://www.osce.org/copyright` | Wymaga kontaktu | RSS wymaga bezpośredniej walidacji; materiał może zawierać wkład stron trzecich. |
| coe.int | Portal: `https://www.coe.int/en/web/portal/news` | `https://www.coe.int/en/web/portal/legal-notice` | Wymaga kontaktu | Brak potwierdzonego pojedynczego kanału RSS dla wskazanego zakresu. |
| wojsko-polskie.pl | Oficjalny portal: `https://www.wojsko-polskie.pl/` | `https://www.gov.pl/web/gov/warunki-korzystania` | Wymaga kontaktu | Zmiana/relacja hosta z gov.pl wymaga precyzyjnej ścieżki i testu. |
| ron.mil.pl | Portal MON: `https://www.gov.pl/web/obrona-narodowa` | `https://www.gov.pl/web/gov/warunki-korzystania` | Możliwa karta | Kandydat tylko dla komunikatów MON z gov.pl; nie dla całego historycznego hosta ron.mil.pl. |
| bbm.mil.pl | Portal BBN: `https://www.bbn.gov.pl/` | `https://www.bbn.gov.pl/pl/stopka/` | Wymaga kontaktu | Brak zweryfikowanego feedu i odrębnego dokumentu ponownego użycia. |
| dwt.mil.pl | — | — | Odrzucić | Historyczny/niejednoznaczny host; najpierw potrzebne ustalenie następcy instytucjonalnego. |
| ceidg.gov.pl | Oficjalne dane: `https://www.biznes.gov.pl/pl/ceidg` | `https://www.gov.pl/web/rozwoj-technologia/ponowne-wykorzystywanie-informacji-sektora-publicznego` | Możliwa karta | Tylko API/rejestr po potwierdzeniu dokumentacji konkretnego endpointu; bez HTML katalogu. |
| organy-wladzy.pl | — | — | Odrzucić | Nie jest urzędowym rejestrem państwowym; nie nadaje się jako źródło bazowe. |
| rejestrstowarzyszen.pl | — | — | Odrzucić | Prywatny agregator, nie oficjalny rejestr. |

## Media, organizacje i branżowe serwisy (39 pozycji)

Dla niżej wymienionych wpisów w tej turze **nie znaleziono równocześnie oficjalnego RSS/API oraz jawnych warunków dopuszczających automatyczne pobieranie do archiwum**. Wspólny, bezpieczny wynik to **wymaga kontaktu**; nie wolno tworzyć karty HTML tylko na podstawie publicznej strony lub `robots.txt`.

| Źródła | Kanał w karcie teraz | Warunki | Klasyfikacja |
|---|---|---|---|
| factcheck.wp.pl; temidium.pl; lexplicata.pl; konstytucyjny.pl | brak potwierdzonego kanału maszynowego | do uzyskania od wydawcy | Wymaga kontaktu |
| tvs.pl; rdc.pl; radiomerkury.pl; kanalzero.com | brak potwierdzonego kanału maszynowego | do uzyskania od wydawcy | Wymaga kontaktu |
| naszhistoria.pl; mowia-wieki.pl; historia.org.pl; teologiapolityczna.pl; wiez.pl; res-publica.eu | brak potwierdzonego kanału maszynowego | do uzyskania od wydawcy | Wymaga kontaktu |
| termedia.pl; pulsmedycyny.pl; gazetalekarska.pl | brak potwierdzonego kanału maszynowego | do uzyskania od wydawcy | Wymaga kontaktu |
| agropolska.pl; topagrar.pl; agrofakt.pl; fermer.pl | brak potwierdzonego kanału maszynowego | do uzyskania od wydawcy | Wymaga kontaktu |
| muratorplus.pl; rynekpierwotny.pl; nieruchomosci-online.pl; propertynews.pl; eurologistics.pl | brak potwierdzonego kanału maszynowego | do uzyskania od wydawcy | Wymaga kontaktu |
| transport-publiczny.pl; rynek-kolejowy.pl; rynek-lotniczy.pl | brak potwierdzonego kanału maszynowego | do uzyskania od wydawcy | Wymaga kontaktu |
| portalspozywczy.pl; wiadomoscihandlowe.pl; retailnet.pl; handelextra.pl; wprawo.pl; elektroonline.pl | brak potwierdzonego kanału maszynowego | do uzyskania od wydawcy | Wymaga kontaktu |
| sdp.pl; dziennikarzerp.pl; reporterzy.info; fundacjatrust.pl | brak potwierdzonego kanału maszynowego | do uzyskania od podmiotu | Wymaga kontaktu |

## Biuletyny Informacji Publicznej (29 pozycji)

Każdy adres jest oficjalnym BIP-em, ale **BIP jako typ strony nie stanowi jeszcze zgody na automatyczne pobieranie**. Do karty potrzebne są: dokładna ścieżka aktualności/rejestru, osobna strona o ponownym wykorzystaniu albo licencja oraz test `robots.txt`. W tej turze żadnego nie aktywowano.

| Grupa | Oficjalny kanał | Warunki | Klasyfikacja |
|---|---|---|---|
| bip.dolnyslask.pl; bip.kujawsko-pomorskie.pl; bip.lubelskie.pl; bip.lubuskie.pl; bip.lodzkie.pl; bip.malopolska.pl; bip.mazovia.pl; bip.opolskie.pl | odpowiedni BIP — ścieżka do ustalenia osobno | strona ponownego wykorzystywania danego urzędu — do ustalenia | Wymaga kontaktu / weryfikacji |
| bip.podkarpackie.pl; bip.podlaskie.pl; bip.pomorskie.pl; bip.slaskie.pl; bip.swietokrzyskie.pl; bip.warmia.mazury.pl; bip.wielkopolska.pl; bip.zachodniopomorskie.pl | odpowiedni BIP — ścieżka do ustalenia osobno | strona ponownego wykorzystywania danego urzędu — do ustalenia | Wymaga kontaktu / weryfikacji |
| bip.katowice.eu; bip.bydgoszcz.pl; bip.lublin.eu; bip.bialystok.pl; bip.czestochowa.pl; bip.gdynia.pl; bip.gliwice.eu; bip.kielce.eu; bip.olsztyn.eu; bip.radom.pl; bip.rzeszow.pl; bip.szczecin.pl; bip.torun.pl | odpowiedni miejski BIP — ścieżka do ustalenia osobno | strona ponownego wykorzystywania danego miasta — do ustalenia | Wymaga kontaktu / weryfikacji |

## Następny bezpieczny ruch

1. Najpierw test adapterów i kart dla EP, Komisji, Rady UE, CEIDG oraz zawężonego MON — osobno dla każdego hosta i kanału.
2. Następnie powstaje lista kontaktowa dla 39 mediów/organizacji oraz dla BIP-ów, przy których nie da się potwierdzić ścieżki i warunków.
3. Nie traktować `TRUE` w katalogu jako zgody ani nie uruchamiać harvestera dla pozycji oznaczonych „wymaga kontaktu”.

## Źródła dowodowe

- Komisja Europejska: `https://ec.europa.eu/info/legal-notice_en` oraz `https://digital-strategy.ec.europa.eu/en/news/rules-reuse-commission-information`
- Rada UE: `https://www.consilium.europa.eu/en/about-site/copyright/`
- Parlament Europejski: `https://www.europarl.europa.eu/legal-notice/en/`
- MON/gov.pl: `https://www.gov.pl/web/gov/warunki-korzystania`
- CEIDG: `https://www.biznes.gov.pl/pl/ceidg`

