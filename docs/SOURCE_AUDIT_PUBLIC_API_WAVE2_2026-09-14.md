# Audyt oficjalnych API i danych publicznych — fala 2

**Data:** 14 września 2026 r.  
**Cel:** poszerzyć pulę legalnych źródeł kontekstu dla spin.clinic. To jest
audyt dokumentacji i warunków dostępu — nie uruchamia harvestera, nie pobiera
archiwum i nie zmienia katalogu aktywnych źródeł.

## Zasada kwalifikacji

Źródło może wejść do puli dopiero po potwierdzeniu jednocześnie: oficjalnego
operatora, stabilnego punktu dostępu, dozwolonego zakresu ponownego użycia,
limitu zapytań (lub konserwatywnego limitu pilotażowego) oraz zgodności z
modelem danych. Sam fakt, że API jest publicznie osiągalne, nie wystarcza.
Do czasu takiej kontroli zapisujemy wyłącznie metadane i link źródłowy; pełny
tekst, zrzuty i uczenie są wyłączone.

| # | Źródło / domena | Metoda | Stan | Uzasadnienie i następny krok |
|---:|---|---|---|---|
| 1 | Sejm RP — `api.sejm.gov.pl` | udokumentowane JSON API: posłowie, głosowania, druki, interpelacje, komisje | **warunkowy kandydat** | Oficjalna dokumentacja potwierdza paginację, dane bieżącej kadencji i archiwalne kadencje. Nie znaleziono w tym audycie odrębnej, jednoznacznej licencji ponownego użycia ani limitu. Sprawdzić regulamin/robots i ustalić pojedynczy adapter metadanych z interwałem co najmniej 3 s. [Dokumentacja Sejm API](https://api.sejm.gov.pl/sejm.html) |
| 2 | ELI / Dziennik Ustaw i Monitor Polski — `api.sejm.gov.pl` | udokumentowane JSON API aktów prawnych | **warunkowy kandydat; ten sam host co #1** | Oficjalne API publikuje listy dzienników i zakresy roczników, w tym Dz.U. od 1918 r. oraz Monitor Polski od 1930 r. Nie liczyć go jako osobnej domeny do celu „32 źródła”. Przed aktywacją sprawdzić warunki ponownego użycia i zakres dozwolony dla metadanych. [ELI API](https://api.sejm.gov.pl/eli_pl.html) |
| 3 | Narodowy Bank Polski — `api.nbp.pl` | REST API kursów walut | **warunkowy kandydat** | Oficjalna dokumentacja opisuje endpointy, format ISO dat i zakresy tabel A/B/C. To materiał faktograficzny, przydatny jako dowód kontekstu ekonomicznego, lecz nie źródło newsów. Brakuje w tym audycie potwierdzenia licencji i limitów; wymagane przed włączeniem. [NBP Web API](https://api.nbp.pl/en.html) |
| 4 | Portal Otwarte Dane — `api.dane.gov.pl` | API katalogu zbiorów danych | **do doprecyzowania** | Oficjalna dokumentacja techniczna potwierdza API katalogu, lecz każdy zbiór ma własnego dostawcę i warunki. Nie wolno traktować całego katalogu jako jednego automatycznie dozwolonego źródła. Należy kwalifikować pojedyncze zbiory wraz z ich licencją. [Dokumentacja API](https://api.dane.gov.pl/media/resources/20230621/Open_Data_-_Dokumentacja_techniczna_-_API_endpoints.pdf) |
| 5 | GUS Bank Danych Lokalnych — `bdl.stat.gov.pl` / `api.stat.gov.pl` | REST API danych statystycznych | **już zweryfikowany kandydat, nie dublować** | Jest już w `backend/scraper/data/verified_official_api_candidates.json` z CC BY 4.0 i opublikowanymi limitami. Nie tworzono drugiego wpisu. Pozostaje wyłączony do czasu ograniczonego pilotażu. [Dokumentacja BDL](https://api.stat.gov.pl/Home/BdlApi/1000) |
| 6 | UOKiK SUDOP — `api-sudop.uokik.gov.pl` | oficjalne API pomocy publicznej | **już zweryfikowany kandydat, nie dublować** | Jest już w katalogu zweryfikowanych kandydatów z warunkiem 15 żądań/min. Wymaga adaptera z atrybucją i ograniczeniami wskazanymi przez operatora. [Informacja UOKiK](https://uokik.gov.pl/sudop) |
| 7 | Geoportal / GUGiK — `mapy.geoportal.gov.pl` | WFS / ATOM / WMS, m.in. granice administracyjne | **warunkowy kandydat** | GUGiK publikuje endpointy usług INSPIRE i jawne limity obiektów dla wybranych WFS. To wzbogacenie geograficzne, nie źródło artykułów. Przed włączeniem potwierdzić warunki danego zestawu i używać tylko WFS/ATOM, nie obrazów WMS. [Usługi INSPIRE](https://www.geoportal.gov.pl/pl/usluga/uslugi-inspire/) |
| 8 | Krajowy Rejestr Sądowy — `prs.ms.gov.pl` | OpenAPI KRS | **zablokowany dla projektu** | Ministerstwo informuje, że automatyczny dostęp przez API jest przeznaczony dla podmiotów publicznych oraz podmiotów realizujących zadania publiczne na podstawie decyzji Ministra. spin.clinic nie spełnia obecnie tego warunku. Nie próbować obejść dostępu; ewentualnie złożyć formalny wniosek w przyszłości. [Komunikat MS](https://www.gov.pl/web/sprawiedliwosc/uruchomienie-otwartego-api-krajowego-rejestru-sadowego) |
| 9 | GIOŚ — dane jakości powietrza | publiczne interfejsy danych środowiskowych | **wymaga odrębnego audytu** | Nie potwierdzono w tym ograniczonym audycie aktualnej oficjalnej dokumentacji, zasad automatycznego pobierania i stabilnego endpointu. Nie kwalifikować na podstawie nieoficjalnych przykładów kodu. |
| 10 | Senat RP — dane legislacyjne i posiedzenia | potencjalne publikacje WWW/RSS | **wymaga odrębnego audytu** | Nie potwierdzono publicznego, udokumentowanego API ani warunków maszynowego pobierania. Dopóki nie będzie potwierdzenia, pozostaje poza pulą. |

## Wynik dla puli 32 równoległych źródeł

Ta fala nie dodaje automatycznie żadnej nowej domeny do pracy harvestera.
Wykazała trzy użyteczne kierunki do zamknięcia w kolejnym kroku: Sejm/ELI,
NBP oraz Geoportal. Sejm i ELI są jednak jednym hostem, więc nie zwiększają
liczby równoległych domen. GUS i UOKiK są już w katalogu kandydatów, ale nadal
wyłączone. KRS jest wyraźnie niedostępny bez decyzji właściwego organu.

## Zalecana kolejność

1. Sprawdzić regulamin i `robots.txt` dla Sejm, NBP i Geoportal oraz zapisać
   datę kontroli i dowód warunków ponownego użycia.
2. Zbudować małe, osobne adaptery wyłącznie dla metadanych; każdy z limitem
   początkowym co najmniej 3 s na host.
3. Uruchomić pojedynczy, ograniczony pilotaż i porównać kompletność oraz
   stabilność z danymi źródłowymi.
4. Dopiero po akceptacji dodać daną domenę do zatwierdzonej puli dynamicznej.

Nie utworzono pliku kandydatów JSON: w tej fali żaden nowy host nie spełnił
wszystkich warunków kwalifikacji bez dodatkowej kontroli warunków ponownego
użycia i limitów.
