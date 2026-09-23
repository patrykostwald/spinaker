# X i YouTube — uruchomienie źródeł

Ten dokument opisuje konfigurację produkcyjną. Sekrety pozostają wyłącznie w
`.env` lub w magazynie sekretów hostingu. Nie wolno wkleić ich do kodu,
`NEXT_PUBLIC_*`, zrzutu ekranu ani wiadomości e-mail.

## X: posty potwierdzonych kont politycznych

1. Zaloguj się do [X Developer Console](https://developer.x.com/en/portal/dashboard),
   utwórz Project i App dla `spin.clinic` oraz wybierz plan, który daje odczyt
   endpointu `GET /2/users/:id/tweets`. Cennik i dostępność planów X zmieniają
   się w panelu, dlatego ostateczną cenę potwierdzamy tam przed zakupem.
2. Włącz rozliczenia dla wybranego planu i utwórz **Bearer Token** aplikacji.
3. W pliku `.env` ustaw najpierw bezpieczny pilotaż:

   ```dotenv
   X_POLITICAL_POLLING_ENABLED=true
   X_POLITICAL_BEARER_TOKEN=wklej-token-tylko-tutaj
   X_POLITICAL_PAGE_SIZE=10
   X_POLITICAL_DAILY_POST_LIMIT=100
   X_POLITICAL_DAILY_REQUEST_LIMIT=100
   X_POLITICAL_MONTHLY_USD_LIMIT=5
   X_POLITICAL_INITIAL_LOOKBACK_HOURS=24
   ```

4. Uruchom procesy `worker` i `beat`. Aplikacja pobiera wyłącznie publiczne
   posty z kont, które redaktor wcześniej dodał, potwierdził źródłem i włączył
   w panelu administracyjnym. Każdy odczyt rezerwuje budżet przed wywołaniem.
5. Zweryfikuj wynik w `/api/political/status/` jako administrator. Pierwszy
   test wykonujemy na jednym potwierdzonym koncie i obserwujemy budżet przez
   dobę, zanim dodamy pełną listę.

Posty z X są materiałem źródłowym. Nie są automatycznie publikowane w Bazie
ani oceniane. Redakcja tworzy z nich szkic dla: przekazu obozu rządzącego,
przekazu opozycji albo propozycji Dr Spina. Propozycja ma cytat, linki,
materiały potwierdzające i przeczące oraz niepewność; publikacja wymaga decyzji
redaktora.

## YouTube: metadane filmów

1. W [Google Cloud Console](https://console.cloud.google.com/) utwórz albo
   wybierz projekt.
2. Włącz **YouTube Data API v3**, utwórz klucz API i ogranicz go do adresu IP
   serwera backendu oraz do tej usługi API.
3. W `.env` wpisz:

   ```dotenv
   YOUTUBE_ENABLED=true
   YOUTUBE_API_KEY=wklej-klucz-tylko-tutaj
   YOUTUBE_DAILY_REQUEST_LIMIT=50
   ```

4. Zrestartuj backend. Wyszukiwanie YouTube zapisuje tytuł, kanał, datę,
   miniaturę i adres filmu jako materiał typu „Film”; nie pobiera wideo ani
   transkrypcji.

Limit w aplikacji jest celowo niższy od limitu platformy. Po tygodniu
obserwacji podnosimy go na podstawie realnego użycia.
