# Zlecenie 057 — podgląd fazy 2

Wdrożono wejście przez tajny link, podpisane ciasteczko na 30 dni, wyjście, flagi żądania, stronę `/podglad` i pasek podglądu. Publiczne flagi pozostają domyślnie wyłączone. Nie ma nowych uprawnień personelu ani migracji bazy.

## Jak włączyć

1. W produkcyjnym `.env.production` ustaw `PREVIEW_KEY` na losowy sekret, np. wynik `secrets.token_urlsafe(32)` wygenerowany przez właściciela w bezpiecznym miejscu. Nie dodawaj go do repozytorium ani zmiennych `NEXT_PUBLIC_*`.
2. Wdróż backend i frontend, odtwórz kontenery backendu i workera z nowym środowiskiem oraz przeładuj zmieniony Caddyfile. Sam restart istniejącego kontenera nie aktualizuje wartości z `env_file`.
3. Pozostaw `ACCOUNTS_ENABLED`, `THREADS_ENABLED`, `PUSH_ENABLED` oraz odpowiadające im `NEXT_PUBLIC_*` i `NEXT_PUBLIC_APP_ENABLED` wyłączone.
4. Przy jedynym zaufanym proxy Caddy przed Django ustaw `TRUSTED_PROXY_COUNT=1`. Dla innej topologii dopasuj liczbę zaufanych proxy. Limit wejść to 10 na godzinę na IP, również dla poprawnego klucza. Produkcja korzysta ze wspólnego cache Redis; przy wartości 0 Django liczy adres bezpośredniego połączenia.
5. Otwórz bezpośrednio adres HTTPS domeny głównej:

   `https://spin.clinic/api/preview/?klucz=<PREVIEW_KEY>`

   Przekaż ten link testerowi prywatnie. Dla sekretów z innymi znakami niż URL-safe zakoduj wartość parametru. Wejście przekierowuje na `/podglad` bez klucza w adresie docelowym.

Brak lub pusta wartość `PREVIEW_KEY` wyłącza wejście. Rotacja klucza i odtworzenie backendu/workera unieważniają dotychczasowe podpisy. „Wyjdź z podglądu” usuwa oba ciasteczka, ale nie wylogowuje z konta czytelnika.

## Pliki

- `backend/news/preview.py`, `features.py`, `test_preview.py`: podpis, middleware z `ContextVar`, limit IP, wejście/wyjście/status i testy.
- `backend/config/settings.py`, `urls.py`: zmienna środowiskowa i rejestracja middleware/tras.
- `backend/news/account_security.py`, `accounts.py`, `account_lifecycle.py`, `community.py`, `notification_api.py`, `push_api.py`: bramki żądań korzystają ze wspólnych flag. Google korzysta z istniejącego `AccountEnabled`.
- `backend/news/notification_tasks.py`: zadania zbiorcze nadal odczytują wyłącznie ustawienia. Testy istniejących nitek i powiadomień przełączają teraz ustawienia Django zamiast zmieniać środowisko po jego załadowaniu.
- `packages/ui/src/lib/features.ts`, `account.ts`, `personal.ts` i komponenty konta, nitek, reakcji, obserwowania oraz nagłówka: `useFeature` z `useEffect`, zgodny pierwszy render serwera i przeglądarki.
- `frontend-spin/lib/features.ts`, strony `konto/**`, `nitki/**`, `profile/**`: bramki Next uwzględniają ciasteczko podglądu.
- `frontend-spin/app/podglad/page.tsx`, `PreviewControls.tsx`, `preview.css`, `layout.tsx`, `PwaControls.tsx`: strona z noindex, pasek, stopka, instalacja i ustawienia push.
- `frontend-spin/tests/preview.test.cjs`: testy SSR i przekazywania podpisu do Django.
- `Caddyfile`, `deploy/Caddyfile`, `backend/gunicorn.conf.py`: ochrona parametrów linku w logach proxy i opcjonalnych logach dostępu Gunicorn.

## Weryfikacja

- Backend: 117 testów zaliczonych łącznie w sprawdzonych zestawach, 1 istniejący test pominięty z powodu braku `cryptography`. Pierwszy przebieg wykazał usunięty import `os`; po poprawce wszystkie 8 testów `test_community.py` przeszło. Końcowy zestaw podglądu: 23/23.
- Frontend: `node --test tests/preview.test.cjs` — 3/3. Sprawdza zgodność SSR/pierwszego renderu także przy obecnym ciasteczku oraz bramki i weryfikację podpisu po stronie Next.
- `npx --no-install tsc --noEmit -p .` w `frontend-spin` — bez błędów.
- Bez uruchamiania serwera, instalowania pakietów, odczytu plików `.env`, commitowania i wdrażania. Nie wykonywano testów wizualnych ani instalacji PWA na telefonie. Caddy nie jest zainstalowany lokalnie, więc jego konfiguracja wymaga walidacji przy wdrożeniu.

## Istotne ograniczenia

- `sc_preview` to wskazówka interfejsu, nie autoryzacja. API ufa wyłącznie ważnemu podpisowi; `/podglad` dodatkowo weryfikuje podpis w Django przez `API_INTERNAL_URL`. Po rotacji klucza stary znacznik UI może pozostać do następnego żądania API, które usuwa ciasteczka. Nie zapewnia dostępu do danych.
- Konta i publikacje testerów są rzeczywiste. Nadal wymagane są e-mail, zgody, weryfikacja publikującego użytkownika i dotychczasowe uprawnienia.
- Potwierdzenie e-maila i reset hasła potrzebują działającego workera, brokera i SMTP. Tylko te wiadomości transakcyjne otrzymują podpisane upoważnienie z obsłużonego żądania podglądu; działa ono także po zakończeniu żądania i wygasa przy zmianie klucza. Zwykłe wywołanie zadania bez upoważnienia przy wyłączonych kontach nic nie wysyła.
- Podgląd pozwala skonfigurować subskrypcję push, jeżeli skonfigurowano VAPID. Nie włącza wysyłki push, zbiorczych e-maili ani produkowania powiadomień przez wyłączone zadania w tle.
- Wdrożenie wymaga także konfiguracji logowania z tego zlecenia. Django usuwa parametr przed dalszą obsługą, Gunicorn loguje ścieżkę bez zapytania, a filtry Caddy obejmują również logi błędów. Jeżeli poza repozytorium istnieje dodatkowy CDN, WAF, proxy lub monitoring żądań, trzeba tam również wyłączyć zapis `klucz`, pełnego URL i nagłówka Referer. Filtry skonfigurowano według [dokumentacji Caddy](https://caddyserver.com/docs/caddyfile/directives/log#filter) i [globalnego loggera](https://caddyserver.com/docs/caddyfile/options#log).
- Link daje dostęp każdemu, kto go otrzyma, do czasu rotacji klucza. Ciasteczka wymagają HTTPS. E-mail potwierdzający należy otworzyć w przeglądarce z aktywnym podglądem; na innym urządzeniu trzeba najpierw użyć zaproszenia.
