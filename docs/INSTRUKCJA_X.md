# X — instrukcja krok po kroku

Robisz to tylko raz. Nie wysyłaj nikomu tokenu — to jest hasło do płatnego API.

1. Otwórz: <https://developer.x.com/en/portal/dashboard>.
2. Zaloguj się kontem X, które ma być właścicielem integracji.
3. Kliknij utworzenie konta deweloperskiego, jeśli X o to poprosi. W opisie
   użycia wpisz: „Odczyt publicznych postów potwierdzonych kont polityków do
   redakcyjnej weryfikacji źródeł. Bez automatycznej publikacji.”
4. Utwórz **Project**, a w nim **App**. Nazwij je np. `spin-clinic`.
5. Wybierz płatny plan, który wprost obejmuje odczyt `GET /2/users/:id/tweets`.
   Cena i dostępność są pokazane przed finalnym potwierdzeniem płatności.
6. W ustawieniach aplikacji znajdź **Bearer Token** i skopiuj go.
7. Otwórz lokalny plik projektu `.env` i na samym dole wklej:

   ```dotenv
   X_POLITICAL_POLLING_ENABLED=true
   X_POLITICAL_BEARER_TOKEN=TU_WKLEJ_TOKEN
   X_POLITICAL_PAGE_SIZE=10
   X_POLITICAL_DAILY_POST_LIMIT=100
   X_POLITICAL_DAILY_REQUEST_LIMIT=100
   X_POLITICAL_MONTHLY_USD_LIMIT=5
   X_POLITICAL_INITIAL_LOOKBACK_HOURS=24
   ```

8. Zapisz plik. Nie wklejaj tokenu do czatu ani nie rób jego zrzutu ekranu.
9. Napisz mi tylko: **„X skonfigurowany”**. Sprawdzę status, dodamy jedno
   konto testowe i potwierdzimy, że limit kosztów działa.

Nie włączamy od razu wszystkich kont. Pierwszy dzień to test jednego konta i
obserwacja licznika kosztów.
