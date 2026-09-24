# Audyt źródeł instytucjonalnych — fala 4 (2026-09-14)

## Cel i granice

To jest wyłącznie audyt kandydatów. Nie dodano żadnego wpisu do katalogu, nie
włączono adaptera i nie pobierano korpusu publikacji. Kryterium pozytywne było
łączne: oficjalny podmiot, opisany mechanizm techniczny oraz jednoznaczna
podstawa ponownego wykorzystania dla planowanego zakresu. Sama dostępność
strony lub istnienie przepisów nie jest zgodą na automatyczne archiwizowanie.

Przy każdym przyszłym włączeniu trzeba ponownie odczytać `robots.txt`, wskazany
mechanizm indeksu/API i warunki z dnia aktywacji. Materiały audiowizualne,
zdjęcia oraz pełny tekst pozostają poza zakresem tego audytu, chyba że dana
licencja i decyzja redakcji wyraźnie obejmą ich użycie.

## Wynik

Nie ma nowego źródła, które można dziś bez dodatkowej weryfikacji dodać do
aktywnej puli archiwum. Powstaje więc **brak pliku JSON kandydatów**. Najbliżej
spełnienia warunków jest wspólny host `www.gov.pl`, ale należy traktować go jako
jeden host z różnymi jednostkami, a nie wiele niezależnych źródeł do równoległego
pobierania.

## Kandydaci wymagający dalszej, ręcznej walidacji

| Podmiot / host | Mechanizm widoczny w źródle pierwotnym | Podstawa i dopuszczalny zakres | Stan |
| --- | --- | --- | --- |
| Portal Gov.pl / `www.gov.pl` | Portal pokazuje aktualności i linki do stron jednostek; konkretnego stabilnego indeksu archiwalnego nie potwierdzono w tym audycie. | Stopka portalu stanowi, że teksty (z wyjątkiem audiowizualnych) są na CC BY-SA 4.0; zdjęcia, audio i wideo mają odrębny, ograniczający warunek CC BY-NC-ND 4.0. Ewentualny pilot: wyłącznie URL, tytuł, data, autor i tekst objęty licencją; atrybucja, link do oryginału i zgodność z SA obowiązkowe. | **Nie aktywować** przed testem robots, odnalezieniem stabilnego indeksu/RSS dla wybranego działu oraz oceną kompatybilności CC BY-SA z publicznym wykorzystaniem. |
| Ministerstwo Nauki i Szkolnictwa Wyższego / `gov.pl/web/nauka` | Publikacje są na wspólnym hoście Gov.pl. | Jednostka opisuje warunki: dla informacji BIP/portalu danych bez innych warunków należy podać źródło i czas wytworzenia/pozyskania oraz zaznaczyć przetworzenie. | **Nie aktywować osobno** — dzieli host i mechanizm z Gov.pl; potrzebne potwierdzenie zakresu dla konkretnych publikacji i indeksu. |
| Ministerstwo Rodziny, Pracy i Polityki Społecznej / `gov.pl/web/rodzina` | Publikacje są na wspólnym hoście Gov.pl. | Warunki wymagają źródła, czasu wytworzenia/pozyskania oraz informacji o przetworzeniu; dodatkowe warunki mogą zostać określone indywidualnie. | **Nie aktywować osobno** — brak potwierdzenia indeksu i brak domniemania dla pełnej treści. |
| Ministerstwo Sprawiedliwości / `gov.pl/web/sprawiedliwosc` | Publikacje są na wspólnym hoście Gov.pl. | Wskazano źródło, czas wytworzenia/pozyskania i informację o przetworzeniu; jednostka może określać dodatkowe warunki dla utworów lub baz danych. | **Nie aktywować** — dodatkowe warunki mogą być relewantne dla konkretnej publikacji. |
| Rządowa Agencja Rezerw Strategicznych / `gov.pl/web/rars` | Publikacje są na wspólnym hoście Gov.pl. | Warunki wymagają pełnej nazwy źródła, czasu i zakazują modyfikacji; fragment ma być cytatem z przypisem. | **Wykluczone z automatycznego korpusu** — warunek zakazu modyfikacji nie daje bezpiecznej podstawy dla planowanego przetwarzania/segmentacji. |
| Ministerstwo Rolnictwa i Rozwoju Wsi / `gov.pl/web/rolnictwo` | Publikacje są na wspólnym hoście Gov.pl. | Wymagane: źródło, daty, zakaz modyfikacji i cytowanie fragmentu z przypisem. | **Wykluczone z automatycznego korpusu** z tego samego powodu; możliwy wyłącznie redakcyjny link/cytat po odrębnej decyzji. |
| Sejm API / `api.sejm.gov.pl` | Oficjalna dokumentacja opisuje paginowane endpointy dla posłów, głosowań, druków, interpelacji, posiedzeń i wypowiedzi. | Dokumentacja potwierdza istnienie API, ale w tym audycie nie znaleziono osobnej licencji/warunków dla całego API. Ustawa o otwartych danych opisuje re-use, lecz nie zastępuje warunków konkretnego podmiotu/zasobu. | **Nie jest nowym kandydatem** — istniejąca integracja danych parlamentarnych powinna pozostać ograniczona do już zatwierdzonego modelu `OfficialRecord`; nie rozszerzać do pełnych tekstów bez warunków. |
| Senat RP / `www.senat.gov.pl` | Serwis opisuje procedurę wniosków o dostęp i ponowne wykorzystanie. | Materiał proceduralny wskazuje, że warunki/opłaty mogą być określane w odpowiedzi na wniosek; nie jest to ogólna licencja dla archiwum. | **Wykluczone na teraz** — brak udokumentowanego API/RSS/sitemap i ogólnego zakresu reuse. |
| NBP API / `api.nbp.pl` | Oficjalna strona API istnieje, lecz w ograniczonym audycie nie potwierdzono warunków ponownego wykorzystania ani mechanizmu publikacji typu box. | API dotyczy przede wszystkim danych tabelarycznych, nie archiwum publikacji; brak potwierdzonej podstawy licencyjnej w tym audycie. | **Wykluczone jako źródło boxów**; może być odrębnym źródłem danych referencyjnych po osobnym audycie. |
| GUS BDL / `bdl.stat.gov.pl` | Publiczne API statystyczne; model danych to serie i wymiary statystyczne. | Brak potwierdzonego w tym audycie zestawu warunków dla automatycznego reuse oraz brak jednostek odpowiadających publikacyjnym boxom. | **Wykluczone jako źródło boxów**; nie mieszać danych statystycznych z korpusem artykułów. |

## Dowody pierwotne

1. [Portal Gov.pl — stopka i warunki licencji](https://www.gov.pl/) — teksty: CC BY-SA 4.0; materiały audiowizualne: CC BY-NC-ND 4.0, o ile nie zaznaczono inaczej.
2. [MNiSW — ponowne wykorzystywanie](https://www.gov.pl/web/nauka/ponowne-wykorzystywanie-informacji-sektora-publicznego).
3. [MRPiPS — ponowne wykorzystywanie](https://www.gov.pl/web/rodzina/bip-zasady-ponownego-wykorzystywania-informacji-sektora-publicznego).
4. [Ministerstwo Sprawiedliwości — ponowne wykorzystywanie](https://www.gov.pl/web/sprawiedliwosc/ponowne-wykorzystywanie).
5. [RARS — warunki ponownego wykorzystania](https://www.gov.pl/web/rars/ponowne-wykorzystywanie-informacji-sektora-publicznego).
6. [MRiRW — warunki ponownego wykorzystywania](https://www.gov.pl/web/rolnictwo/ponowne-wykorzystywanie).
7. [Sejm API — oficjalna dokumentacja](https://api.sejm.gov.pl/sejm.html).
8. [Senat — dostęp do informacji publicznej i reuse](https://www.senat.gov.pl/o-senacie/wybrane-akty-prawne/dostep-do-informacji-publicznej1/).
9. [Ustawa o otwartych danych — tekst w oficjalnym ELI](https://api.sejm.gov.pl/eli/acts/DU/2019/1446/text.html).

## Zalecenie operacyjne

Kolejny audyt powinien skupiać się na pojedynczym, wskazanym przez instytucję
zbiorze w `dane.gov.pl` z licencją/warunkami przy zbiorze, lub na jednostce,
która jednocześnie publikuje RSS/API, robots i warunki ponownego wykorzystania.
Nie należy próbować zwiększać liczby aktywnych workerów przez rozbicie sekcji
Gov.pl na pozornie niezależne domeny — wspólny host wymaga wspólnego limitera.
