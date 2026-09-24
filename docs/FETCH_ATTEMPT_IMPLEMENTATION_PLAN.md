# Plan wdrożenia `FetchAttempt` — uzgodnienie audytów

Aktualizacja: 15 września 2026.

Ten dokument łączy statyczny audyt wykonany w starszym worktree z aktualnym kodem. Nie jest deklaracją, że wszystkie ścieżki są już objęte bramką.

## Stan aktualnej gałęzi

`SourceAccessInstruction` istnieje i bramkuje aktualne ścieżki RSS, sitemap/HTML archiwum oraz oficjalne API. Instrukcja jest przypisana do źródła, kanału, endpointu, zakresu i daty ważności. Nie oznacza to jeszcze pełnego pokrycia transportu.

Brakuje append-only `FetchAttempt`, który udowadniałby każdą blokadę i każdą realną próbę wyjścia do sieci. Część integracji nadal ma własne wywołania HTTP albo należy do późniejszego zakresu produktu.

## Podział ścieżek

### Pilot archiwum — objąć najpierw

- `scraper.utils.fetch_feed`: wspólny transport RSS, sitemap i HTML;
- `scraper.archive`: robots, discovery i strony archiwalne;
- `scraper.rss_scraper`;
- `scraper.html_archive` i `scraper.wordpress_backfill`, jeżeli dostaną osobne zatwierdzone instrukcje;
- `scraper.official`: oficjalne API Sejmu i ELI.

### Po pilocie albo poza zakresem archiwum medialnego

- GDELT i NewsAPI — zewnętrzne API, wymagają osobnej decyzji dostawcy i budżetu;
- X — integracja późniejsza, z osobnymi kanałami identity i posts;
- `ProbeNetwork` — narzędzie audytowe. Musi otrzymać jawny tryb `probe` albo pozostać technicznie odseparowane od harvestera.

## Kontrakt bramki

Przed siecią adapter przekazuje źródło, zatwierdzoną instrukcję, kanał, URL, bezpieczny cel operacji oraz limit odpowiedzi. Bramka sprawdza kanał, endpoint, ważność i host; odmowa tworzy `blocked_before_network` bez DNS ani socketu.

Każda próba tworzy niezmienny rekord z czasem, źródłem, instrukcją i wersją, kanałem, hostem, bezpiecznym fingerprintem URL, wynikiem, statusem HTTP, rozmiarem, czasem trwania, liczbą przekierowań i kontrolowanym kodem błędu. Nie zapisujemy tokenów, cookies, pełnego query, treści odpowiedzi ani surowego `Location`.

## Kolejność implementacji

1. Model `FetchAttempt`, migracja i test append-only.
2. Bramka na istniejącym `fetch_feed`; RSS i `archive.process` jako pierwsze objęte kanały.
3. Robots, listingi HTML i WordPress, zachowując dodatkowe ograniczenia adapterów.
4. Oficjalne API.
5. Jednoznaczna decyzja dla `ProbeNetwork`.
6. Dopiero po tym zewnętrzne API oraz X.

## Dowody przed uruchomieniem pilota

- brak instrukcji, zły kanał, endpoint poza zakresem i wygaśnięcie nie uruchamiają sieci;
- sukces, błąd HTTP, błąd sieci i blokada tworzą po jednym rekordzie;
- RSS i archiwum przechodzą przez tę samą bramkę;
- w żadnym rekordzie ani logu nie ma sekretu lub pełnej odpowiedzi;
- statyczna kontrola wykrywa nowe bezpośrednie użycie klienta HTTP poza zatwierdzonym transportem.
