# YouTube — instrukcja krok po kroku

Ten klucz pozwala wyszukiwać publiczne filmy i pobierać ich metadane. Nie daje
dostępu do Twojego kanału ani konta YouTube.

1. Otwórz: <https://console.cloud.google.com/>.
2. Zaloguj się kontem Google.
3. U góry kliknij wybór projektu, potem **New project**. Nazwij go
   `spin-clinic` i kliknij **Create**.
4. W lewym menu otwórz **APIs & Services → Library**.
5. Wyszukaj **YouTube Data API v3**, otwórz ją i kliknij **Enable**.
6. Otwórz **APIs & Services → Credentials**.
7. Kliknij **Create credentials → API key**. Skopiuj utworzony klucz.
8. Kliknij **Restrict key**. Wybierz ograniczenie do **YouTube Data API v3**.
   Gdy portal będzie wdrożony, dodamy także ograniczenie do IP serwera.
9. Otwórz lokalny plik `.env` i na samym dole wklej:

   ```dotenv
   YOUTUBE_ENABLED=true
   YOUTUBE_API_KEY=TU_WKLEJ_KLUCZ
   YOUTUBE_DAILY_REQUEST_LIMIT=50
   ```

10. Zapisz plik. Klucza nie wklejaj do czatu ani do kodu.
11. Napisz mi tylko: **„YouTube skonfigurowany”**. Sprawdzę połączenie i
    dodamy pierwszy materiał testowy.
