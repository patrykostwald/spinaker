# Źródła płatne i licencjonowane dla przeszłość.today: wstępny przegląd (6.11.2026)

Status: **wstępny, niepełny**. Agent badawczy miał tylko wyniki wyszukiwarki (fragmenty stron); domeny rejestr.io, opensanctions.org, opencorporates.com nie były osiągalne z sieci sesji, a Firecrawl bez kredytów do 7.11.2026 15:54 UTC. **Żadnego cennika nie przeczytano w całości.** Nic nie kupiono, żadnych kont ani formularzy. Do powtórzenia po przywróceniu dostępu do sieci/kredytów (sprawdzić cenniki i regulaminy na stronach dostawców).

## Fakty ze źródłami (z fragmentów, do potwierdzenia na stronach dostawców)
- **KRS, nowelizacja ustawy (26.09.2025; źródła wtórne: ifirma.pl, rp.pl, legeartis.org):** art. 4c-4m: dostęp do danych przez usługi sieciowe (API) tylko decyzją Ministra Sprawiedliwości, dla podmiotów publicznych/wykonujących zadania publiczne; „Full API” z danymi osobowymi tylko dla wybranych podmiotów publicznych, otwarte API KRS według jednego omówienia „bez zmian”; **art. 60a: nieuprawniony dostęp przez usługi sieciowe jest przestępstwem (do 2 lat)**. Opłata za dokument KRS: 50 zł (źródło z 2018 r., nieaktualne?). Oficjalnego cennika hurtowego MS nie znaleziono. **Do oceny Prawnika przed dalszym użyciem API KRS: czy nasze zapytania do otwartego API mieszczą się w „otwartym” zakresie.**
- **rejestr.io (Fundacja Moje Państwo):** API prepaid („Kredyt”, cena żądania w Cenniku, załącznik 1 do regulaminu; kwoty nie ustalono), przepada po 24 mies., limit 100 żądań/min, użycie tylko w EOG; licencja na publiczne wyświetlanie niejasna (atrybucja „Źródło: rejestr.io” w starszej wersji). https://rejestr.io/regulamin/api
- **Transparent Data:** KRS API, „Business Registers 360” (repliki KRS, CEIDG, CRBR, REGON, Biała lista); cena tylko na zapytanie.
- **GDELT:** dane do swobodnego użytku także komercyjnego, redystrybucja z cytowaniem; słabe pokrycie polskich mediów (ocena).
- **Newspoint:** ok. 1100 tytułów prasy, 200 stacji RTV (SourceForge); cena i licencja nieustalone. **Press-Service:** wymaga licencji wydawców. Brand24, Pressto, NewsAPI, Event Registry, Mediaboard: nieustalone.
- **OpenSanctions (sankcje, PEP):** niekomercyjnie CC BY-NC 4.0; komercyjnie licencja (wpis z 2022: 595 EUR/mies. dane hurtowe, możliwe nieaktualne; zniżki dla nowych produktów); publiczny serwis prawdopodobnie jest użyciem komercyjnym.
- **OpenCorporates:** plan API od ok. 225 GBP/mies. (fragment cennika, niespójny); klucze darmowe tylko przy share-alike (nasze dane wynikowe trzeba by otworzyć).
- **ICIJ Offshore Leaks:** ODbL/CC BY-SA, atrybucja ICIJ, obecność w bazie nie oznacza przestępstwa, imiona się powtarzają: tylko dopasowanie po twardym identyfikatorze.
- **Księgi wieczyste:** przeglądanie w EKW bezpłatne, odpis płatny (stawki sprzeczne w źródłach: 60/75/90 zł); brak API hurtowego; dane osób fizycznych: nie polecane.

## Ocena (agenta, nie fakt) i ranking na start
1. rejestr.io API (przydatność 5): poprosić o cennik i pisemne zasady wyświetlania publicznego.
2. Transparent Data (4): zapytanie o cenę i licencję (bezpłatne).
3. OpenSanctions (4): zapytanie o zniżkę dla nowego produktu; prototyp poza publicznym serwisem na licencji niekomercyjnej.
4. GDELT (3, 0 zł) uzupełnienie korpusu RSS (tytuł, link, data).
5. ICIJ Offshore Leaks (3, 0 zł) z zastrzeżeniem i tylko po twardych identyfikatorach.

## Niepewne (przed jakimkolwiek zakupem)
Kwoty (rejestr.io, OpenSanctions dziś, Transparent Data, dostawcy prasy), licencja na publiczne wyświetlanie u każdego dostawcy, status i skutki nowelizacji KRS dla naszego klienta otwartego API, RODO dla powiązań osób fizycznych (podstawa prawna, sprzeciw, retencja), niesprawdzeni: Companies House, BRIS, Dow Jones, World-Check, D&B, Creditreform, KRD, EMIS, Infoveriti.
