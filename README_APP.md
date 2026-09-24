# spin.clinic — context before content

Jeden portal i jedna baza źródeł. Publiczne czytanie i wyszukiwanie bez konta i bez premium. Administrator łączy materiały w chronologiczne nitki; strona główna pokazuje poziome osie czasu, wyszukiwarka — paski dat od najnowszej.

## Co działa

- Wyszukiwanie w tytułach, dostępnych opisach, nazwiskach posłów oraz jawnych, udokumentowanych powiązaniach tematycznych.
- Filtry kategorii i dat. Materiały bez daty pozostają bez daty; data wykrycia nie udaje publikacji.
- Nitki redakcyjne: szkic, publikacja, wyróżnienie, komentarz do każdego źródła.
- Dodawanie materiału z bazy lub po URL. Pobranie metadanych nie zapisuje materiału; administrator sprawdza i zapisuje formularz.
- Imienne głosowania Sejmu, druki sejmowe, Dziennik Ustaw i Monitor Polski. Dokładny przedmiot głosowania, głosy posłów, metadane oryginalne, historia korekt.
- Importery RSS, GDELT, NewsAPI i oficjalnego API X; ostatnie dwa wymagają kluczy i są domyślnie wyłączone.
- Panel Django `/admin/`, warsztat `/editor`, dokumentacja API `/api/docs/`.

Nie włączono publicznego tworzenia nitek, głosowania użytkowników ani automatycznych ocen AI. Baza zawiera materiały źródłowe, których obecność sama w sobie nie potwierdza wszystkich twierdzeń. Nie ma sztucznych nitek demonstracyjnych.

## Struktura

`backend` — Django, REST API, Celery; `frontend-spin` — główny portal Next.js; `packages/ui` — wspólny interfejs. `frontend-przeszlosc` zachowano jako opcjonalny wariant marki. Nie wymaga drugiego wdrożenia ani osobnej bazy. Nagłówek domeny nie filtruje już treści.

## Uruchomienie lokalne w Windows

Wymagane: Python 3.11+ i Node 20+. Polecenia wykonuj w katalogu projektu. Na tym komputerze środowisko `.venv` i zależności frontendu są już przygotowane.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:USE_SQLITE='true'
$env:DJANGO_DEBUG='true'
.\.venv\Scripts\python.exe backend/manage.py migrate
.\.venv\Scripts\python.exe backend/manage.py createsuperuser
.\.venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000
```

W osobnym terminalu:

```powershell
pnpm install --frozen-lockfile
pnpm dev:spin
```

Portal: http://localhost:3000, redakcja: http://localhost:3000/editor, administrator bazy: http://127.0.0.1:8000/admin/.

SQLite służy do lokalnego podglądu. Samo uruchomienie stron nie uruchamia cyklicznego pobierania. Produkcyjny import wymaga PostgreSQL, Redis, procesu Celery worker i jednego Celery Beat — zobacz [wdrożenie](docs/DEPLOYMENT.md).

## Dane i import

```powershell
$env:USE_SQLITE='true'
.\.venv\Scripts\python.exe backend/manage.py seed_sources
.\.venv\Scripts\python.exe backend/manage.py import_official --title krypto
.\.venv\Scripts\python.exe backend/manage.py import_official --all-prints
.\.venv\Scripts\python.exe backend/manage.py import_official --journal DU --year 2026
.\.venv\Scripts\python.exe backend/manage.py import_official --journal MP --year 2026
.\.venv\Scripts\python.exe backend/manage.py import_evidence_links
```

Polecenia można ponowić bez duplikowania adresów. `seed_sources` zapisuje katalog źródeł, nie generuje newsów. Historia głosowań: `import_official --term 10 --from-date 2023-11-13 --to-date 2026-09-08`. Duże zakresy mogą wymagać długiego pobierania; import nie jest deklaracją kompletności całego archiwum.

Szczegóły pochodzenia, kategorii i ograniczeń: [DATA.md](docs/DATA.md). API: [API.md](docs/API.md), [OpenAPI](docs/openapi.yaml). Fundament przyszłego asystenta: [AI.md](docs/AI.md). Bieżący stan prac: [PROGRESS.md](docs/PROGRESS.md).

## Weryfikacja

```powershell
$env:USE_SQLITE='true'
.\.venv\Scripts\python.exe -m pytest backend -q
.\.venv\Scripts\python.exe backend/manage.py spectacular --file docs/openapi.yaml --validate --fail-on-warn
pnpm build
```

Testy importu używają izolowanej bazy i danych testowych; dane testowe nie są ładowane do portalu.
