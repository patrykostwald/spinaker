# Niezależny przegląd transportu harvestera — 14 września 2026 (zadanie 014)

## Zakres

Przegląd lokalnego kodu `backend/scraper/utils.py::fetch_feed()` i
`backend/scraper/archive.py`, istniejących testów (`backend/scraper/tests.py`,
`test_archive.py`, `test_archive_metrics.py`) oraz mechanizmu allowlisty
źródeł (`news.models.SourceAccessInstruction`, `scraper/news_sitemaps.py`,
`scraper/backfill.py`). Nie uruchamiano harvestera ani żadnych requestów
sieciowych, nie zmieniano frontendu, Supabase ani sekretów.

**Uwaga wstępna:** zadanie 014 opisuje `fetch_feed()` jako funkcję, która
zawsze łączy się z pierwszym zwróconym IP. To już nieaktualne — commit
`db79de4` ("Fix approved archive source transport") wprowadził dokładnie
poprawkę opisaną w `docs/TRANSPORT_DIAGNOSIS_2026-09-14.md`, a kolejne
commity (`aff1762`, `b0c69c6`, `e9c6878`, `359c8db`, `f054d57`) rozbudowały
wokół niej bramkę dostępu prawnego. Ten dokument jest więc przeglądem
**już wdrożonej** poprawki, nie propozycją nowej implementacji od zera.

## 1–2. Stan obecny i ocena wobec wymagań zadania

`fetch_feed(url, *, hostname_transport=False)`:

- Walidacja `safe_url()` i rozwiązanie DNS (`socket.getaddrinfo`) z
  odrzuceniem adresów niepublicznych wykonują się **bezwarunkowo**, na
  początku każdej z maks. 4 iteracji pętli — niezależnie od
  `hostname_transport`. To poprawne: preflight chroni obie ścieżki.
- Domyślnie (arbitralny URL, `hostname_transport=False`): bez zmian —
  połączenie przypięte do zwalidowanego IP, `Host` i SNI ustawione ręcznie.
- Dla `hostname_transport=True`: `urllib3.PoolManager(...)` z pełnym URL-em,
  bez ręcznego `Host`, bez przypięcia do IP — to jest właśnie "normalne
  połączenie po hostname", o które prosi zadanie.
- Brak automatycznych redirectów w obu trybach (`redirect=False`); każdy
  `Location` wraca na początek pętli i przechodzi tę samą walidację URL/DNS
  co adres wejściowy. Limit 4 przekierowań zachowany.
- Limity zachowane w obu trybach: `connect=5s`, `read=30s`, `retries=False`,
  twardy limit 5 MB po dekompresji, jawny `User-Agent`, `cert_reqs=CERT_REQUIRED`
  z tym samym `ca_certs`.

To spełnia literę punktu 2 zadania **pod względem mechaniki transportu**.
Problem jest w tym, **kto dostaje `hostname_transport=True`**:

`archive.py` ustawia `hostname_transport=True` bezwarunkowo dla każdego joba,
którego źródło ma `catalog_stage='configured'` (`process()`, `discover()`,
`robots(..., hostname_transport=True)`). Komentarz w kodzie nazywa to
"approved publishers", ale `Source.catalog_stage` ma wprost przeciwną
adnotację we własnym modelu:

```python
help_text="Skonfigurowane nie oznacza zweryfikowanego kanału ani kompletnego archiwum."
```

Repozytorium ma już węższą, faktycznie zweryfikowaną allowlistę:
`SourceAccessInstruction` ze statusem `APPROVED`, wypełnionym
`reviewed_at`/`reviewed_by`/`terms_url`/`evidence`, której endpoint musi się
zgadzać z `archive_verification.status == 'verified'` i `can_backfill is True`
w katalogu JSON (`scraper/news_sitemaps.py::matching_catalog_row`,
`scraper/backfill.py::approved_access_instructions()`). Tej właśnie allowlisty
używa `run_backfill()` do ograniczenia zakresu pełnego tekstu
(`source_access_scopes` → `allowed_scope`), ale **nie** do ograniczenia
transportu sieciowego — `run_parallel_batch()`/`run_batch()` wywołane spoza
`run_backfill()` (czyli zwykły `archive_cycle()`/`discovery_cycle()`, bez
`source_access_scopes`) nadal przechodzą przez `process()`, który ustawia
`hostname_transport=True` dla **każdego** skonfigurowanego źródła.

**Wniosek:** mechanizm transportu jest poprawny, ale jego zasięg jest szerszy
niż "wyłącznie zweryfikowane, allowlistowane źródła" z treści zadania —
faktycznie obejmuje cały katalog `configured`, czyli operatorsko wybrane, ale
niekoniecznie prawnie/dostępowo zweryfikowane domeny. To nie jest podatność
przyjmująca dowolny URL (candidate/excluded nadal nie kwalifikują się, a
`configured` nadal wymaga ręcznej decyzji operatora w adminie), ale jest to
rozbieżność między deklarowanym zamiarem zadania a stanem kodu, i realnie
zwiększa liczbę hostów wystawionych na ryzyko z punktu 3 poniżej.

**Rekomendacja (nie wykonana w tym przeglądzie — wymaga decyzji
produktowej):** zawęzić `hostname_transport=True` w `archive.py` do źródeł
faktycznie obecnych w zweryfikowanej allowliście (ta sama definicja co
`backfill.approved_access_instructions()`), nie do samego `catalog_stage`.
Wymaga to wydzielenia tej predykaty do modułu bez cyklu importów
(`backfill.py` importuje `archive.py`, więc `archive.py` nie może importować
`backfill.py` wprost) — np. do `scraper/news_sitemaps.py` lub nowego,
lekkiego `scraper/access_review.py`. To jest sensowna, ale nie "najmniejsza"
zmiana — zostawiam ją jako rekomendację, żeby nie poszerzać zakresu przeglądu
kosztem ryzyka regresji w `archive_cycle()`, który dziś obsługuje cały
katalog `configured`.

## 3. Ryzyko DNS rebinding / TOCTOU

W trybie `hostname_transport=True` istnieje realne, choć wąskie okno TOCTOU:

1. `fetch_feed()` wykonuje `socket.getaddrinfo(hostname, port)` i odrzuca
   wynik, jeśli którykolwiek adres nie jest publiczny.
2. Zaraz potem tworzy `urllib3.PoolManager()` i wywołuje `urlopen('GET', url, ...)`
   z **pełnym URL-em zawierającym hostname**, nie z adresem IP z kroku 1.
   `PoolManager` wykonuje własne, niezależne rozwiązanie DNS w momencie
   faktycznego connect.

Jeśli atakujący kontroluje rekordy DNS zweryfikowanej domeny (np. przejęta
subdomena, złośliwy operator CDN, kompromitacja panelu DNS) i zdąży
podmienić odpowiedź dokładnie między krokiem 1 a krokiem 2, może skierować
faktyczne połączenie na adres prywatny/wewnętrzny mimo przejścia preflightu.
To jest klasyczny DNS rebinding z węższym oknem niż "brak walidacji w ogóle",
ale nie zerowym.

Ścieżka domyślna (`hostname_transport=False`, czyli wszystkie arbitralne
URL-e) **nie ma** tego problemu — łączy się dokładnie z adresem IP już
zwalidowanym w kroku 1, więc druga niezależna rezolucja DNS nigdy nie
zachodzi. To rozróżnienie trzeba utrzymać.

### Ograniczenie ryzyka bez osłabiania ścieżki dla arbitralnych URL

- **Zasięg, nie mechanizm.** Najskuteczniejsze ograniczenie to zawężenie
  `hostname_transport=True` do faktycznie zweryfikowanej allowlisty (patrz
  rekomendacja w sekcji 2) — atakujący musiałby kontrolować DNS domeny, którą
  operator już ręcznie zweryfikował i podpisał warunki dostępu, a nie każdej
  skonfigurowanej domeny.
- **Nigdy nie rozszerzać `hostname_transport=True` na URL pochodzące od
  użytkownika, kandydatów katalogu ani redirecty spoza tego samego hosta** —
  dziś tak jest (domyślnie `False`, kandydaci/wykluczeni nie przechodzą przez
  `process()`), trzeba to utrzymać jako niezmiennik przy każdej przyszłej
  zmianie.
- **Obrona w głębi (nie wykonana, propozycja na później):** podklasa
  `HTTPConnection`/`HTTPSConnection` nadpisująca `connect()`, która po
  faktycznym połączeniu sprawdza `sock.getpeername()[0]` względem
  `ipaddress.ip_address(...).is_global`, zanim handshake TLS/żądanie pójdzie
  dalej. To zamyka niemal całe okno, bo walidacja dotyczy realnego gniazda
  użytego do żądania, a nie osobnej odpowiedzi DNS. Większa zmiana niż
  "najmniejsza poprawka" wymagana w zadaniu — zostawiam jako rekomendację.
- **Nie pinować ponownie IP dla `hostname_transport`** — to zniweczyłoby cel
  poprawki (część CDN/LB odrzuca właśnie połączenia po IP), więc nie jest to
  opcja dla tej gałęzi.

## 4. Testy regresyjne

### Już istniejące (zweryfikowane przez czytanie, nie uruchamiane — patrz niżej)

- `test_private_fetch_is_rejected_before_connection` — prywatny adres
  odrzucony przed jakimkolwiek połączeniem (pula nigdy nie tworzona).
- `test_public_fetch_pins_ip_and_rejects_private_redirect` — ścieżka domyślna
  (pinned IP): redirect na prywatny adres kończy się błędem przed drugim
  połączeniem.
- `test_approved_source_uses_hostname_transport_after_public_dns_check` —
  `hostname_transport=True` faktycznie łączy się po hostname (pełny URL do
  `PoolManager.urlopen`, brak ręcznego `Host`).
- `test_host_circuit_opens_after_three_transient_failures`,
  `test_transient_retry_honors_retry_after_without_duplicate_job`,
  `test_transient_error_is_quarantined_after_bounded_attempts` —
  circuit breaker i klasyfikacja błędów przejściowych wokół `fetch_feed()`/
  `robots()` w `archive.py` już pokryte, nie wymagają nowych testów.

### Luka znaleziona i zamknięta w tym przeglądzie

Żaden istniejący test nie łączył `hostname_transport=True` z przekierowaniem
na adres prywatny — a to właśnie ten przypadek ogranicza ryzyko z sekcji 3 do
"wąskiego wyścigu", a nie "redirect prosto do sieci wewnętrznej". Dodano:

```python
@patch('scraper.utils.socket.getaddrinfo')
def test_hostname_transport_still_rejects_private_redirect(resolve):
    """hostname_transport skips IP pinning, not the per-hop public-DNS check."""
    from scraper.utils import fetch_feed
    resolve.side_effect = [[(2, 1, 6, '', ('8.8.8.8', 443))], [(2, 1, 6, '', ('10.0.0.1', 443))]]
    with patch('urllib3.PoolManager') as pool:
        pool.return_value.urlopen.return_value = MagicMock(status=302, headers={'Location': 'https://internal.example/a'})
        with pytest.raises(ValueError, match='public'):
            fetch_feed('https://source.example/a', hostname_transport=True)
        assert pool.return_value.urlopen.call_count == 1
```

w `backend/scraper/tests.py`, zaraz po istniejącym teście
`test_approved_source_uses_hostname_transport_after_public_dns_check`.

### Zaproponowane, nie wykonane (wymagają decyzji o zawężeniu zasięgu z sekcji 2)

- Test na `archive.process()`/`discover()` sprawdzający, że
  `hostname_transport=True` trafia wyłącznie do źródeł obecnych w
  `backfill.approved_access_instructions()` (lub jej odpowiedniku po
  refaktorze), a zwykłe `catalog_stage='configured'` bez zatwierdzonej
  instrukcji dostępu dostaje `False`. Ten test dziś by przeszedł tylko po
  zawężeniu zasięgu opisanym w sekcji 2 — dlatego nie jest jeszcze
  dodany, żeby nie blokować przeglądu na niewykonanej zmianie produktowej.
- Jeśli zawężenie zostanie wdrożone: test na `run_parallel_batch()` bez
  `source_access_scopes` (czyli zwykły `archive_cycle()`), potwierdzający że
  źródło bez zatwierdzonej instrukcji nadal się przetwarza, ale transportem
  przypiętym do IP, a nie hostname.

## Czego ten przegląd nie robił

Nie uruchamiał harvestera ani żadnego requestu sieciowego, nie zmieniał
frontendu, Supabase, sekretów ani aktywności/częstotliwości źródeł. Nie
zawężał zasięgu `hostname_transport` w `archive.py` — to zostawione jako
rekomendacja wymagająca właścicielskiej decyzji, bo dotyka ścieżki używanej
przez każdy regularny cykl archiwizacji, nie tylko pilotażowy backfill.

## Uruchomione testy

Środowisko przeglądu (`.local/spinaker-review`) nie ma dostępnego
interpretera Pythona w dozwolonym katalogu roboczym (piaskownica blokuje
dostęp poza katalog sesji), więc **nowy test nie został uruchomiony
lokalnie**. Logika została zweryfikowana ręcznie przez prześledzenie
kolejności operacji w `fetch_feed()` (patrz sekcja 4) i test jest zgodny z
wzorcem mockowania już istniejących testów w tym samym pliku. Właściciel
powinien uruchomić `pytest backend/scraper/tests.py -k hostname_transport`
(oraz pełny `backend/scraper/tests.py` i `test_archive_metrics.py`) przed
scaleniem.

## Zmienione pliki

- `backend/scraper/tests.py` — dodano jeden test
  (`test_hostname_transport_still_rejects_private_redirect`), bez zmian
  produkcyjnych. Nie utworzono commita (zgodnie z poleceniem tej sesji);
  zmiana czeka w drzewie roboczym do przeglądu/scalenia przez Codex lub
  właściciela.

## Ryzyka

1. Zasięg `hostname_transport=True` jest szerszy niż "zweryfikowana
   allowlista" z treści zadania (sekcja 2) — średnie ryzyko, wymaga decyzji
   produktowej, nie tylko technicznej poprawki.
2. Wąskie okno DNS rebinding/TOCTOU dla `hostname_transport=True` (sekcja 3)
   — niskie prawdopodobieństwo (wymaga kontroli nad DNS zweryfikowanej
   domeny i precyzyjnego trafienia w bardzo krótkie okno), ale niezerowe;
   największa dźwignia to zawężenie zasięgu, nie zmiana mechaniki.
3. Nowy test nie został uruchomiony w tym środowisku (brak interpretera) —
   niskie ryzyko błędu składniowego, bo wzorzec jest identyczny z istniejącym,
   przechodzącym testem, ale wymaga potwierdzenia przed scaleniem.

## Następny krok

Właściciel decyduje, czy zawężyć `hostname_transport=True` do
`backfill.approved_access_instructions()` (lub jej odpowiednika) również w
zwykłym `archive_cycle()`/`discovery_cycle()`, czy świadomie zostawić
`catalog_stage='configured'` jako granicę zaufania dla transportu sieciowego
(przy zachowaniu osobnej, węższej granicy dla treści/pełnego tekstu, która
już istnieje). Po decyzji: uruchomić `pytest backend/scraper/tests.py
backend/scraper/test_archive_metrics.py` i dopiero wtedy commitować.
