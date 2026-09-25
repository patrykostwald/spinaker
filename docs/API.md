# API spin.clinic

Interaktywna dokumentacja: `/api/docs/`. Schemat: `/api/schema/` oraz [`openapi.yaml`](openapi.yaml) — generowany poleceniem
`python manage.py spectacular --file docs/openapi.yaml --validate --fail-on-warn` (bez ostrzeżeń).

Każdy materiał ma źródło, datę publikacji (albo jawny brak daty) i odnośnik do oryginału. API nie ocenia prawdziwości treści.

## Portal (odczyt publiczny)

- `GET /api/feed/` — pasek materiałów. `mode=latest` (wszystkie aktywne źródła) albo `mode=top` (dzisiejsze materiały wiodących mediów). Filtry: `q`, `match=words`, `categories`, `topics`, `sources`, `platforms=youtube`, `page`, `page_size` (1–40). Wynik: `results`, `total`, `next_page`, `top_sources`, `selection_note`.
- `GET /api/portal/config/` — kategorie, tematy, katalog źródeł (bez wykluczonych), liczniki katalogu, nitki „Przekaz dnia”.
- `GET /api/portal/topic-of-day/` — automatyczny temat dnia (hasło, liczba źródeł i materiałów) albo `mode=unavailable`.
- `GET /api/articles/{id}/context/?page=N` — materiały powiązane z boxem po słowach kluczowych, pogrupowane według dat, z licznikami kategorii.
- `GET /api/context/counts/?ids=1,2` — liczniki powiązanych materiałów dla 1–4 boxów.

### Grupy źródeł

Każde źródło w odpowiedziach ma pole `portal_group`:

| wartość | znaczenie |
|---|---|
| `top` | wiodące media — lista redakcyjna w `backend/news/source_groups.py` (`TOP_MEDIA`, 12 marek) |
| `publiczne` | instytucje publiczne (`source_type = institution`) |
| `media` | pozostali wydawcy |

## Materiały, wyszukiwanie, nitki

- `GET /api/search/?q=…` — opcjonalnie `categories`, `from_date`, `to_date` (YYYY-MM-DD). Wynik: `total`, `returned`, `truncated`, `timeline` pogrupowane datami malejąco; `undated` na końcu.
- `GET /api/articles/{id}/` — materiał, źródło (z `portal_group`), pochodzenie, urzędowe metadane i głosowanie.
- `GET /api/articles/{id}/related/` — do 10 materiałów o podobnym tytule w zakresie ±7 dni (heurystyka, nie dowód związku).
- `GET /api/articles/{id}/ballots/?q=…`, `GET /api/articles/{id}/official/` — głosy imienne i oryginalny rekord urzędowy.
- `GET /api/threads/?featured=true`, `GET /api/threads/{slug}/` — opublikowane nitki kontekstowe.

## Reakcje i komentarze

- `GET /api/articles/{id}/opinions/` — liczniki `positive` / `negative`, komentarze (stronicowane osobno dla obu stron), własna reakcja zalogowanego użytkownika.
- `POST` tamże — jedna reakcja (`polarity`: `positive` | `negative`) z opcjonalnym komentarzem (`body`); `PATCH` pozwala raz dopisać komentarz. Wymaga zalogowania.
- `GET/POST/PATCH /api/threads/{slug}/opinions/` — to samo dla nitek kontekstowych.
- `POST /api/comments/reports/` — zgłoszenie komentarza.

## Osoby publiczne

- `GET /api/public-figures/?q=&role_category=&status=&page=&page_size=` — rejestr (do 100 na stronę).
- `GET /api/public-figures/{id}/` — profil: funkcja, potwierdzone relacje z podmiotami, głosowania.
- `GET /api/public-figures/{id}/dossier/` — oś czasu, relacje, luki w danych; wyłącznie rekordy z publicznym dowodem.
- `GET /api/public-figures/{id}/context/`, `GET /api/public-offices/`.

## Konto

`/api/account/register/`, `/api/account/login/`, `/api/account/logout/`, `/api/account/me/`, `/api/account/profile/`, ulubione (`favorites`, `article-favorites`), prywatne nitki kontekstowe (`context-threads`), paski tematów (`topics`), historia. Szczegóły pól — w `openapi.yaml`.

## Sesja redakcji i zapisy

`GET /api/auth/csrf/` ustawia cookie i zwraca `csrfToken`; `POST /api/auth/login/` (JSON `username`, `password`, nagłówek `X-CSRFToken`). Po logowaniu pobierz nowy token przed kolejnym zapisem. Logowanie redakcji: 10 prób / 5 minut na adres.

- `POST /api/editor/preview-url/` — metadane adresu do przeglądu (blokada adresów prywatnych, limity czasu i rozmiaru).
- `POST /api/editor/articles/`, `GET/POST /api/editor/threads/`, `GET/PATCH/PUT /api/editor/threads/{slug}/` — materiały i nitki redakcyjne (1–100 materiałów, kolejność według chronologii publikacji).
- `/api/editor/sources/…` — katalog źródeł redakcji; `/api/ai/research/…`, `/api/editor/draft-thread/` — szkice AI dla redakcji (zawsze do sprawdzenia przez człowieka).

## Katalog źródeł — polecenia serwisowe

Wszystkie bez `--apply` tylko pokazują plan; `--restore --apply` cofa zmianę. Nigdy nie ruszają źródeł aktywnych ani skonfigurowanych.

- `python manage.py exclude_off_profile_sources --apply` — wyklucza kandydatury spoza profilu tematycznego (kulinaria, plotki, sport, motoryzacja…).
- `python manage.py dedupe_source_catalog --apply` — zostawia jedną kartę na wydawcę (duplikaty host / kanał RSS).

Limity: 100 zapytań odczytu na minutę na klienta. `/api/patronite/webhook/` zwraca 501 (brak obsługi płatności).
