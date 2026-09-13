# Uruchomienie i wdrożenie

## Lokalny podgląd

SQLite i Next.js wystarczają do czytania bazy i pracy redakcji. Nie są produkcyjnym zestawem dla wielu użytkowników. `DJANGO_DEBUG=true` jest potrzebne w lokalnym HTTP, ponieważ tryb produkcyjny wymaga bezpiecznych cookies HTTPS.

Dostęp do `/editor` wymaga aktywnego konta Django z `is_staff`. Konto tworzy `python backend/manage.py createsuperuser`. Nie ma publicznej rejestracji. Nie zapisuj haseł ani kluczy w repozytorium.

## Pełne środowisko Docker

Skopiuj `.env.example` do `.env` i uruchom `docker compose up --build`. To konfiguracja developerska z lokalnymi danymi PostgreSQL i Redis; nie wystawiaj jej bez zmian do Internetu. Frontend uruchamia się osobno poleceniem `pnpm dev:spin`.

Worker pobiera materiały, Beat zleca harmonogram. Uruchamiaj dokładnie jeden Beat, aby nie dublować zleceń. W środowisku produkcyjnym worker i Beat muszą mieć te same ustawienia bazy, Redis, strefy czasowej i integracji co backend.

## Railway — backend

Root projektu: katalog główny repozytorium, Dockerfile: `Dockerfile`, konfiguracja: `railway.json`. Migrations uruchamia `preDeployCommand`, a `/api/health/` sprawdza dostępność bazy i cache. Lokalnego pliku SQLite nie wdrażamy.

Utwórz PostgreSQL i Redis, a następnie trzy procesy z tego samego kodu:

1. API: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`, healthcheck `/api/health/`.
2. Worker: `celery -A config worker -l info`, bez HTTP healthcheck i bez publicznej domeny.
3. Beat: `celery -A config beat -l info`, jedna instancja, bez HTTP healthcheck i bez publicznej domeny.

Worker/Beat wymagają nadpisania komendy startowej oraz wyłączenia healthcheck API w ustawieniach ich usług. Migracje wykonuje usługa API przed uruchomieniem pozostałych. Wariant `backend/Dockerfile` służy wdrożeniom z rootem `backend`, nie należy mieszać kontekstów budowania.

Ustaw:

- `DJANGO_DEBUG=false`, losowy `DJANGO_SECRET_KEY`, dokładne `DJANGO_ALLOWED_HOSTS` bez protokołu.
- `DATABASE_URL` i `REDIS_URL` z usług Railway.
- `CORS_ALLOWED_ORIGINS` i `CSRF_TRUSTED_ORIGINS` na dokładne adresy HTTPS portalu.
- `TRUSTED_PROXY_COUNT` dopiero po sprawdzeniu łańcucha proxy — wpływa na limity zapytań. Domyślne 0 jest zachowawcze i może grupować użytkowników za proxy.
- `SEJM_TERM=10`; po rozpoczęciu nowej kadencji zmień parametr świadomie. Historyczne rekordy zachowują własną kadencję.
- Opcjonalne `SENTRY_DSN`, `PATRONITE_URL`, `BUYCOFFEE_URL`. Bez linków wsparcia przyciski są ukryte.

Ustaw limit kosztów usług i kopie PostgreSQL. Przed publicznym startem wykonaj próbne odtworzenie kopii i test pod obciążeniem na docelowym środowisku. Lokalnie nie zweryfikowano PostgreSQL/Redis/Docker ani konfiguracji kont chmurowych.

## Vercel — jeden frontend

Wystarczy `frontend-spin`. Root Directory: `frontend-spin`; włącz dostęp do plików spoza tego katalogu, aby budowanie widziało `packages/ui` i workspace lockfile. Użyj pnpm z `pnpm-lock.yaml`. `frontend-spin/vercel.json` instaluje zależności w głównym katalogu workspace.

`NEXT_PUBLIC_API_URL` ustaw na adres backendu HTTPS, bez końcowego ukośnika. Przeglądarka wysyła `/api/...` do własnej domeny; Next.js przekazuje je do backendu. Dzięki temu sesja redakcji i CSRF działają bez cookies między obcymi domenami. Po zmianie adresu API przebuduj frontend. Backend musi ufać originowi portalu dla CSRF.

Po wdrożeniu sprawdź zdrowie API, wyszukiwanie, logowanie, utworzenie szkicu, publikację i wylogowanie przez domenę portalu. Nie włączaj publicznego dostępu do panelu administracji bez poprawnego HTTPS.

## Integracje wymagające decyzji właściciela

`TWITTER_ENABLED=false` i `NEWSAPI_ENABLED=false` są domyślne. Sama obecność klucza nie uruchamia płatnych pobrań. Token X musi mieć dostęp do odczytu postów; limit `TWITTER_MONTHLY_READ_LIMIT` ogranicza liczbę postów, nie gwarantuje całkowitego rachunku dostawcy. Nie używamy dawnego podziału Free/Basic jako obietnicy darmowej produkcji. Aktualne warunki należy sprawdzić przed zakupem.

NewsAPI Free/Developer nie służy do produkcyjnego portalu. GDELT, RSS oraz urzędowe API można uruchomić bez tych kluczy. Dostępność zewnętrznych źródeł nie jest gwarantowana — obserwuj błędy i czas ostatniego sukcesu.


## Aktualizacja zakresu: X i archiwa
Nadrzędne ustalenia znajdują się w OWNER_NEXT_STEPS.md. NIE włączać TWITTER_ENABLED ani kupować API X: posty są wyłącznie odnośnikami w nitkach. Poprzedni opis tokenu X jest nieaktualny dla obecnego MVP.
Archiwa: import_archives --source-id ID --limit 10 odkrywa mapy z robots.txt. Kolejka ArchiveJob jest trwała. Celery archive_batch wykonuje partie co minutę; odkrywanie map źródeł odbywa się codziennie przez discover_archives, a archive_batch uzupełnia także kolejkę bieżących artykułów. Lokalny run_local_jobs korzysta z tych samych funkcji. Nie uruchamiać lokalnego schedulera równolegle z produkcyjnym Beat.
SQLite lokalnie korzysta z WAL i transakcji IMMEDIATE, żeby ograniczyć konflikty zapisów. Kopie tworzy backup_database przez SQLite backup API z integrity_check. Nie kopiować samego pliku otwartej bazy ręcznie z pominięciem WAL.
