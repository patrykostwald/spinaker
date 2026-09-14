# Instrukcja dostępu do danych referencyjnych: Sejm API i ELI (v1.0)

**Status:** wersja robocza, fail-closed  
**Data audytu:** 2026-09-14  
**Zakres:** dane referencyjne dla kontekstu, nie archiwum newsów i nie korpus pełnych tekstów.

## Decyzja

Można utrzymywać wersjonowaną instrukcję dostępu dla obu interfejsów, ale nie wolno traktować samej dokumentacji technicznej jako nieograniczonej licencji na kopiowanie całej zawartości.

Istniejąca integracja jest odpowiednia dla wąskiego zakresu:

| Dostawca | Dozwolony roboczy zakres | Poza zakresem bez odrębnej decyzji |
| --- | --- | --- |
| API Sejmu | metadane głosowań, imienne wyniki głosowań, druki sejmowe i ich metadane; rekordy potrzebne do odtworzenia konkretnego działania parlamentarnego | zdjęcia posłów, nagrania video, PDF-y/załączniki, pełne interpelacje i odpowiedzi, masowy eksport całych kolekcji bez potwierdzenia warunków |
| ELI | metadane aktów DU i MP: trwały identyfikator, tytuł, publikator, data ogłoszenia, status zwrócony przez API oraz URL urzędowy | PDF i HTML aktu, fragmenty tekstu, struktura całego aktu i hurtowe budowanie pełnotekstowego korpusu bez odrębnego audytu/licencji |

## Co już istnieje w repozytorium

1. Adapter w backend/scraper/official.py zapisuje URL API, surową odpowiedź JSON i czas pobrania w OfficialRecord.
2. Zmiana odpowiedzi tworzy poprzednią wersję w OfficialRevision; jest to przydatne dla audytowalności korekt urzędowych.
3. Dla głosowań importer wymaga zgodności kadencji, posiedzenia i numeru, kompletnej listy głosów oraz zgodności sum. Niepełna odpowiedź nie zastępuje poprzedniej listy.
4. ELI jest paginowane po offset i importer wykrywa niekompletne albo powtarzające się strony.
5. Polecenie import_official nie tworzy nitek redakcyjnych. Testy używają syntetycznych odpowiedzi, nie danych produkcyjnych.

## Dowody techniczne

- Dokumentacja Sejmu opisuje JSON API, paginację przez offset i limit oraz kody 200/400/404.
- API Sejmu udostępnia głosowania, druki, kluby, komisje, interpelacje i materiały dodatkowe. To nie oznacza zgody na przechowywanie każdego z tych typów.
- Dokumentacja ELI opisuje trwałe URI aktów, metadane w formacie maszynowym, listę aktów, wyszukiwanie z offset/limit oraz status i dane publikacyjne aktu.
- Dokumentacja ELI odróżnia metadane od plików text.pdf, text.html i fragmentów tekstu. Te drugie pozostają wyłączone z tego profilu.
- Ustawa o otwartych danych ustanawia ramę ponownego wykorzystywania informacji sektora publicznego, ale przy zasobie udostępnionym w innym systemie teleinformatycznym bez podanych warunków przewiduje tryb wniosku. Dla stałego szerszego wykorzystania należy zachować dowód warunków konkretnego zasobu lub zwrócić się do Kancelarii Sejmu.

## Obowiązkowa provenance i atrybucja

Każdy rekord musi przechowywać co najmniej:

- dostawcę: sejm albo eli;
- stabilną tożsamość z API: kadencja/posiedzenie/numer głosowania, numer druku albo ELI;
- dokładny adres API i publiczny URL dla człowieka;
- czas pobrania UTC oraz czas zdarzenia z jego znaczeniem;
- hash kanonicznej odpowiedzi JSON lub jej wersjonowany odpowiednik;
- wersję adaptera, profil dostępu reference-metadata-v1 i decyzję dostępową;
- oznaczenie źródła widoczne w produkcie: „Kancelaria Sejmu — API Sejmu” albo „ELI / Kancelaria Sejmu — Dziennik Ustaw lub Monitor Polski”;
- informację, czy materiał jest metadanymi, a nie pełnym tekstem.

Obecne modele zapisują URL, payload i czas pobrania; hash, profil dostępu oraz URL dowodu warunków są zalecanym rozszerzeniem przed produkcyjnym backfillem.

## Minimalny dry-run

Dry-run ma być ręcznie zatwierdzonym pojedynczym odczytem na dostawcę — bez uruchamiania harmonogramu i bez pełnego rocznika.

### Sejm

1. Odczytać dokumentację i aktualne warunki/stronę ponownego wykorzystania w dniu testu.
2. Pobrać jeden wskazany przez dokumentację rekord głosowania JSON.
3. Sprawdzić HTTP 200, zgodność term/sitting/votingNumber, niepusty tytuł i opis/temat, kompletność listy głosów oraz sum.
4. Zapisać jeden rekord w transakcji; nie pobierać zdjęć, załączników ani PDF.
5. Ponowić ten sam odczyt i sprawdzić brak duplikatu; ewentualna zmiana ma utworzyć wersję poprzedniego payloadu.
6. Zapisać dowód dokumentacji, czas, hash i wymagane oznaczenie źródła.

### ELI

1. Odczytać dokumentację ELI i aktualne warunki/wyjaśnienie ponownego wykorzystania.
2. Pobrać jeden rekord JSON aktu DU lub MP, bez wywoływania text.pdf, text.html ani struct.
3. Zweryfikować publisher, year, pos, tytuł, datę ogłoszenia i ELI.
4. Zapisać rekord metadanych z URL API oraz publicznym URL ELI.
5. Powtórzyć odczyt, sprawdzić idempotencję i wersjonowanie zmiany.
6. Jeżeli API zwraca brak, niepoprawny JSON, inną tożsamość albo powtarzającą się stronę: przerwać bez przesuwania checkpointu.

## Limity i harmonogram

Dokumentacje opisują stronicowanie, ale w audycie nie znaleziono publicznej gwarancji RPM. Do czasu pisemnej informacji należy stosować konserwatywnie:

- jeden proces na host api.sejm.gov.pl;
- co najmniej 3 sekundy między żądaniami do hosta;
- jedno żądanie na raz;
- dla list: limit 100, pełne przejście tylko z rosnącym offsetem i detekcją powtórzeń;
- przy 429/5xx: zatrzymać tylko ten kanał, zapisać błąd i nie mnożyć retry;
- bez automatycznego pobierania plików binarnych.

Ten limit nie jest twierdzeniem o limicie dostawcy — to ograniczenie ochronne spin.clinic.

## Otwarta kwestia prawna

Dokumentacja API nie zawiera w odnalezionej części jednoznacznej licencji obejmującej pełny zakres trwałego, komercyjnego reużycia. Wniosek do Kancelarii Sejmu powinien opisać: zakres metadanych, nazwy endpointów, częstotliwość, atrybucję, retencję surowego JSON, brak obrazów/PDF/pełnego tekstu oraz planowane publiczne linkowanie do źródła.

Do uzyskania jasnej odpowiedzi profil pozostaje: **referencyjne metadane o wysokiej wartości, ostrożny dry-run, pełne provenance, bez pełnotekstowego korpusu**.

## Źródła pierwotne

1. [Sejm API — dokumentacja](https://api.sejm.gov.pl/sejm.html)
2. [ELI API — dokumentacja](https://api.sejm.gov.pl/eli_pl.html)
3. [ELI — ustawa o otwartych danych i ponownym wykorzystywaniu](https://api.sejm.gov.pl/eli/acts/DU/2021/1641/text.html)
4. [Oficjalny tekst ustawy dostępny przez ELI](https://api.sejm.gov.pl/eli/acts/DU/2019/1446/text.html)


