# Pochodzenie i rzetelność danych

## Co oznacza rekord

Materiał ma oryginalny URL, źródło, tytuł, dostępny opis, autora jeśli podany, kategorię i sposób pozyskania. Komentarz redakcji jest osobnym polem nitki. `category_reviewed` dotyczy kategorii, nie prawdziwości wszystkich twierdzeń.

RSS i agregatory mogą przekazywać błędne lub niepełne metadane. Import nie zastępuje redakcyjnej oceny źródła. Publikacja polityka lub urzędu może zawierać ocenę polityczną; przypisujemy ją autorowi, nie przedstawiamy jako własnego ustalenia.

## Daty

- Nieznana data lub nieznana strefa czasu pozostaje pusta. Nie podstawiamy czasu pobrania.
- GDELT `seendate` zapisujemy jako `discovered_at`. Nie jest to data publikacji.
- Czas głosowania z API Sejmu interpretujemy w strefie Europe/Warsaw, z uwzględnieniem czasu letniego.
- ELI `promulgation` to dzień ogłoszenia; druk sejmowy `deliveryDate` to dzień doręczenia. `date_precision=day` ukrywa godzinę w UI; techniczne północne znaczniki służą wyłącznie porządkowaniu.
- Wyniki bez daty są na końcu. Zakres dat obejmuje całe dni w Warszawie.

## Oficjalne dane

Źródła: [API Sejmu](https://api.sejm.gov.pl/sejm.html), [ELI](https://api.sejm.gov.pl/eli_pl.html).

`OfficialRecord` zachowuje surową odpowiedź i URL API oraz czas pobrania. Zmiana odpowiedzi archiwizuje wcześniejszą wersję w `OfficialRevision`. `ParliamentaryVoting` zawiera dokładny przedmiot głosowania, kadencję, posiedzenie i numer; `Ballot` — ID posła w kadencji, pełne nazwisko, klub z konkretnego głosowania i kod głosu. Nie zamieniamy „przeciw ponownemu uchwaleniu ustawy” na uproszczony, niejednoznaczny „przeciw ustawie”.

Import imiennej listy jest atomowy. Nieznany kod, duplikat posła lub liczba głosów niezgodna z urzędowymi sumami przerywa zastąpienie tej listy. Niepełna odpowiedź nie usuwa wcześniejszych danych. Opis wniosku pochodzi z `description`, a gdy go nie ma — z `topic`.

Dokumenty prawne nie są automatycznie interpretowane jako obowiązujące: wyświetlany status pochodzi z ELI i ma czas pobrania. Lista druków i roczne listy aktów obejmują metadane; nie twierdzimy, że odczytaliśmy pełne PDF-y.

## Wyszukiwanie i powiązania

Wyszukiwarka wymaga wystąpienia każdego słowa w tytule, opisie, nazwisku uczestnika głosowania lub udokumentowanym powiązaniu. To wyszukiwanie fragmentów słów, bez polskiego stemmera i bez semantycznego AI. Nie przeszukuje pełnych artykułów. Maksymalnie pokazuje 500 materiałów i jawnie sygnalizuje ucięcie.

`EvidenceLink` pozwala redakcji przypisać frazę do konkretnego materiału wraz z URL dowodu i wyjaśnieniem. Nie ma automatycznego przypisywania firm do polityków. Wstępne dwa powiązania „zondacrypto” dotyczą konkretnych głosowań 10/46/75 i 10/55/13 i odwołują się do [komunikatu KPRM z 17.04.2026](https://www.gov.pl/web/premier/prezydent-nie-stanal-po-stronie-polakow-weto-w-sprawie-kryptowalut-utrzymane). Komunikat stanowi dowód kontekstu debaty, nie potwierdzenie jego zarzutów ani motywacji głosujących. Powiązania można przeglądać i edytować w panelu artykułu.

Samo „Gosek” może wskazywać więcej niż jednego posła — wyniki pokazują pełne imiona i nazwiska. Dodanie „Mariusz” zawęża prezentowane głosy.

## Harmonogramy

Wymagają aktywnego worker + Beat i Redis:

- GDELT: co 2 godziny, 30 tematów rozłożonych w czasie.
- RSS mediów: co godzinę; instytucji: co 4 godziny.
- X: co 2 godziny, gdy świadomie włączono integrację i dodano token.
- NewsAPI: 06:30, 12:30, 18:00; skonfigurowany Business/Advanced co 15 minut.
- Sejm, ostatnie głosowania: co 15 minut z nakładającym się zakresem 7 dni.
- Druki Sejmu i zmiany ELI: co godzinę. Po przerwie punktem wznowienia jest ostatni udany import, nie bieżąca data.

Import cykliczny nie oznacza pełnego historycznego archiwum. Starsze okresy zasilamy poleceniami importu. Korekty starszych głosowań wymagają ponowienia odpowiedniego zakresu. Błędy źródeł są zapisywane; dla urzędowych zadań panel pokazuje ostatni start, sukces i błąd.

## Koszty i integracje

X korzysta z oficjalnego API; scraping stron X nie jest wdrożony. Rozwiązujemy ID kont przez bieżące API, paginujemy posty, zachowujemy kursor przy błędzie i ograniczamy odczyty budżetem. Token, aktywacja i limit muszą być ustawione przed użyciem. Budżet aplikacji nie zastępuje limitu wydatków u dostawcy. Lista wejściowa ma 40 kont; nie dopisano fikcyjnych danych dla pozostałych parlamentarzystów.

NewsAPI nie obsługuje kodu języka `pl`; zapytania ograniczamy do polskich domen. Darmowy plan służy do developmentu, nie do publicznego portalu. Katalog wejściowy zawiera 43 RSS mediów (mimo liczby 42 w briefie) i 16 instytucji. Dostępność każdej pozycji należy obserwować: źródło może zmienić adres albo przestać publikować RSS.

Pełnotekstowe archiwum jest osobnym etapem: wymaga ustalenia zasad przechowywania dla wydawców, ekstrakcji, wersjonowania tekstów i indeksu. Na razie zachowujemy metadane i link do źródła.


Aktualne poprawki adresów RSS są udokumentowane w `backend/scraper/data/feed_corrections.json`. Nie nadpisują częstotliwości ani własnych zamienników ustawionych przez redakcję. Osiągnięcie limitu 250 wyników GDELT jest oznaczane jako możliwy niekompletny zakres, a nie pełny sukces. NewsAPI paginuje i zachowuje ostatni udany punkt importu, gdy limit lub błąd przerwie pobieranie.
