# API MVP

Interaktywna dokumentacja: `/api/docs/`. Schemat: `/api/schema/` i `openapi.yaml`.

## Odczyt publiczny

- `GET /api/search/?q=krypto+Gosek` — słowa zapytania, opcjonalnie `categories=voting,legislation`, `from_date=YYYY-MM-DD`, `to_date=YYYY-MM-DD`. Wynik: `total`, `returned`, `truncated`, `timeline` pogrupowane datami malejąco; `undated` na końcu.
- `GET /api/articles/{id}/` — materiał, źródło, pochodzenie, ewentualne urzędowe metadane i głosowanie.
- `GET /api/articles/{id}/ballots/?q=Mariusz+Gosek&page=1` — stronicowane głosy konkretnego głosowania, pełne nazwiska i oryginalne kody. Samo nazwisko może pasować do kilku osób.
- `GET /api/articles/{id}/official/` — zachowany oryginalny rekord API i czas pobrania.
- `GET /api/articles/{id}/related/` — heurystyczne podobieństwo słów w tytule w zakresie ±7 dni, nie dowód związku wydarzeń.
- `GET /api/threads/?page=1&featured=true` — opublikowane nitki z materiałami; wyróżnione pierwsze.
- `GET /api/threads/{slug}/` — nitka. Licznik to liczba pobrań szczegółu, nie liczba unikalnych czytelników.
- `GET /api/me/`, `GET /api/health/`.

Limit odczytu: 100 zapytań/minutę na identyfikator klienta. Wyniki wyszukiwania mają cache 5 minut z unieważnieniem przy zmianach materiałów i powiązań. PostgreSQL i Redis są konfiguracją docelową; SQLite używa pamięci procesu do lokalnych limitów/cache.

## Sesja redakcji

`GET /api/auth/csrf/` ustawia cookie i zwraca `csrfToken`. `POST /api/auth/login/` przyjmuje JSON `username`, `password` i nagłówek `X-CSRFToken`. Wysyłaj cookies wraz z zapytaniem. Po logowaniu token się zmienia; pobierz nowy przed kolejnym zapisem. `POST /api/auth/logout/` również wymaga CSRF. Login jest ograniczony do 10 prób/5 minut na adres połączenia. Konta bez uprawnień redakcji nie mogą się zalogować tym formularzem.

## Zapisy administratora

- `POST /api/editor/preview-url/` z `url` — metadane do przeglądu albo `existing` z materiałem, który już jest w bazie. Nie zapisuje nowego materiału. Żądania do prywatnych adresów i przekierowania do nich są blokowane; pobranie ma limity czasu, rozmiaru i przekierowań.
- `POST /api/editor/articles/` — `title`, `url`, `source_name`, `category`; opcjonalne `published_date` (null gdy nieznana), `author`, `description`, `evidence_note`. Data wysyłana z offsetem strefy czasu. Zwraca materiał.
- `GET/POST /api/editor/threads/`, `GET/PATCH/PUT /api/editor/threads/{slug}/`. Zapis: `title`, `description`, `published`, `is_featured`, `items` (1–100 różnych `article_id`, każde z opcjonalnym `editorial_note`). Kolejność ustala chronologia publikacji, nie kolejność kliknięć.
- `POST /api/admin/google-news/` z `q` — zleca pobranie RSS Google News na żądanie; wymaga aktywnego worker i Redis.

Nie ma publicznego endpointu głosowania na nitki, rejestracji użytkowników ani oceny AI. `/api/patronite/webhook/` zwraca 501 i nie obsługuje płatności. Zwykłe linki wsparcia nie wymagają webhooka.
