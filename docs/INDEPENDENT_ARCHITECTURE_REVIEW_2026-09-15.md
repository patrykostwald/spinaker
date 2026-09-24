# Niezależny przegląd architektury archiwum — decyzje wdrożeniowe

## Zakres

Przegląd niezależnego modelu został wykonany na dokumentacji i pakiecie kodu
15 września 2026 r. Nie był opinią prawną ani podstawą do aktywacji źródeł.
Nie uruchamiał pobierania, nie używał sekretów i nie zmieniał danych.

## Ustalenia przyjęte do projektu

1. **Jedna bramka polityki.** Każda ścieżka sieciowa i zapisu — API, RSS,
   sitemap, discovery, WordPress, recovery i przyszłe adaptery — musi przed
   żądaniem otrzymać jawną decyzję `allow` albo `deny` dla konkretnej
   instrukcji, kanału i zakresu. Filtr w pojedynczym importerze nie wystarcza.
2. **Pilot wymaga własnego dopuszczenia.** Szkic instrukcji nie daje prawa do
   testu sam z siebie. Przed pilotem człowiek zatwierdza wąskie dopuszczenie
   testowe. Budżet pilota to najwyżej trzy żądania HTTP łącznie, wliczając
   kanał, przekierowania i retry, z odstępem minimum trzech sekund na host.
3. **Sukces nie znaczy nowy box.** Pilot i recovery mogą zakończyć się
   sukcesem technicznym przy istniejącym materiale albo `304 Not Modified`.
   Kryterium sukcesu to zgodna z instrukcją, poprawnie zwalidowana odpowiedź,
   nie wzrost licznika rekordów.
4. **Historia wymaga kwalifikacji.** Materiały bez udokumentowanej podstawy
   dostępu nie mogą być publikowane ani trafiać do AI, RAG, OCR, embeddingów
   lub treningu do czasu ich sklasyfikowania. Nie dorabiamy wstecz dowodów ani
   zgód; zapisujemy stan dowodu i decyzję o dalszym użyciu albo retencji.
5. **Bramka hosta ma granicę jednego procesu.** Obecne `_HOST_STATES` chroni
   tylko jeden proces. Do czasu testów i wdrożenia współdzielonej koordynacji
   ruch sieciowy pozostaje w jednym procesie. Parsery i procesory danych mogą
   działać równolegle bez własnego dostępu do sieci.
6. **Pochodzenie opisuje także podstawę i transformację.** Docelowa historia
   materiału obejmuje wersję instrukcji i decyzji, dowód warunków, URL żądany
   i końcowy, przekierowania, status HTTP, czasy UTC, metodę, zakres, hash,
   wersję parsera/OCR/modelu oraz zależne artefakty.

## Zweryfikowana luka i jej stan

Statyczne czytanie pełnego repozytorium potwierdziło, że `rss_scraper.py` i
`official.py` nie korzystały z `SourceAccessInstruction`, podczas gdy
`backfill.py` i `archive_cycle()` były nią objęte. Naprawa z 15 września
2026 r. wprowadziła wspólną bramkę dla RSS, API Sejmu/ELI oraz schedulerów
tych kanałów. Testy potwierdzają odmowę przed transportem przy braku zgody i
przy nowszej instrukcji wstrzymującej poprzednią zgodę.

Drugi niezależny przegląd potwierdził także lukę między sitemap a HTML.
Naprawa z tego samego dnia przeniosła kontrolę do `archive.process()` — tuż
przed transportem — i rozdzieliła kanały: job `sitemap` wymaga instrukcji
`sitemap`, a job `page` osobnej instrukcji `html`. Goły tekst zakresu nie
jest już wystarczający do uruchomienia pobrania ani zapisu strony.

Discovery sprawdza już instrukcję `sitemap` przed odczytem `robots.txt`, więc
nie wykorzysta nieautoryzowanej sondy technicznej do zasilenia kolejki.
WordPress backfill i uśpiony mostek REST wymagają zaś instrukcji `api`
bezpośrednio przed transportem albo zapisem kolejki. Pole katalogowe
`archive_verification` pozostało dowodem technicznym; samo nie autoryzuje pracy.

To nadal etap częściowy: recovery i każdy przyszły adapter wymagają podłączenia
do tej samej decyzji, a każda próba pobrania musi zapisywać wersję instrukcji
i pełną proweniencję. Harvestery pozostają zatrzymane do domknięcia tej listy.

## Minimalna kolejność pracy

1. Napisać testy odmowy dla recovery i każdego przyszłego adaptera:
   brak, wygaśnięcie lub cofnięcie instrukcji oznacza zero wywołań transportu.
2. Utrzymywać wspólną funkcję decyzji polityki na granicy każdego nowego
   adaptera; nie aktywować żadnego źródła w tej zmianie.
3. Dodać test pilota z twardym budżetem trzech żądań, gdzie retry i redirect
   także go zużywają.
4. Rozdzielić `FetchAttempt`, wersję dozwolonego materiału i artefakty
   pochodne jako następny etap modelu pochodzenia.
5. Przed wieloprocesowym skalowaniem napisać testy współdzielonej bramki hosta
   dla utraty procesu, wygasłej dzierżawy i przejęcia pracy.

## Granice

Ten dokument nie zastępuje analizy prawnej konkretnych licencji, warunków
wydawcy, praw do baz danych, publikacji prasowych, zdjęć i danych osobowych.
Stanowi jednak wymóg techniczny: gdy podstawa nie jest jednoznaczna, system
odmawia pobrania i kieruje sprawę do ręcznej decyzji lub karty kontaktu.
