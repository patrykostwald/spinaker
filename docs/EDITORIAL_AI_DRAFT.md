# Dr Spin: redakcyjny szkic kontekstu

Endpoint `POST /api/editor/draft-thread/` wymaga aktywnej sesji redaktora (`is_staff`) oraz CSRF. Nie tworzy ani nie publikuje nitki. Zwraca propozycję materiałów do edytora.

Wejście: `topic` (1–500 znaków) i `article_ids` (1–60 różnych identyfikatorów istniejących materiałów; posty X wykluczone). Wyjście: `article_ids`, `items` w formacie ArticleSerializer, `requires_review: true`, `basis: stored_metadata`, `limitation`, `undated_article_ids`. Datowane materiały sortuje serwer od najstarszego; brak daty pozostaje jawny i trafia na koniec. Model może wybrać 0–15 rekordów.

## Konfiguracja po stronie serwera

- `OPENAI_API_KEY`: klucz projektu API (nie abonament ChatGPT); nigdy zmienna publiczna frontendu.
- `DR_SPIN_MODEL`: identyfikator modelu z obsługą Responses i Structured Outputs. Brak domyślnego modelu: właściciel wybiera dostępny model i sprawdza jego koszty przed włączeniem.
- `DR_SPIN_DAILY_CALL_LIMIT`: domyślnie 20 prób na dobę UTC dla całego portalu; 0 wyłącza wywołania; górne ograniczenie 1000. Nieprawidłowa wartość blokuje wywołania.

Bez klucza lub modelu endpoint zwraca 503 `disabled` i nie wywołuje API. Nie wymaga nowych zależności ani migracji. Limit dobowy zapisuje w istniejącym ImportState `editorial-ai-daily-budget`, transakcyjnie przed żądaniem. Błędy i przerwane wywołania też zużywają próbę. Limit liczby prób nie jest limitem kwoty w USD: należy dodatkowo ustawić kontrolę wydatków w projekcie dostawcy. Ochrona pomocnicza: 10 żądań na godzinę/redaktora oraz blokada równoległości w cache. W środowisku wieloprocesowym cache powinien być współdzielony; trwały limit dobowy pozostaje w bazie.

## Granice działania i rzetelności

Model otrzymuje temat oraz ID, tytuł, źródło, kategorię i datę publikacji kandydatów. Nie przekazujemy pełnej treści, opisu ani prywatnych notatek redakcyjnych. Tytuły i temat są traktowane jako niezaufane dane. Polecenie wymaga niezależności źródeł, dopuszcza materiały podważające tezę, zabrania ocen prawdziwości, spinu, przyczynowości i zgadywania popularności.

Wynik to wyłącznie ID ograniczone schematem i ponownie walidowane przez serwer. Nie przyjmujemy wymyślonych identyfikatorów, duplikatów, tekstu ani dat. Dobór AI nie jest gwarancją bezstronności; redakcja ocenia trafność przed publikacją. Zewnętrzne wyniki muszą najpierw przejść oddzielny proces zapisania materiału, aby dostać ID bazy.

Jedna próba to jedno wywołanie bez ponowień, bez narzędzi i pobierania stron przez model. `store: false`, maksymalnie 1200 tokenów wyjściowych, maksymalnie 60 kandydatów, limit odpowiedzi 128 KiB. Połączenie 5 s, timeout odczytu 45 s, dodatkowa kontrola czasu 60 s między blokami odpowiedzi. Brak automatycznej publikacji. `store: false` nie jest deklaracją braku wszystkich technicznych logów dostawcy.

Dokumentacja wykorzystana przy implementacji: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). Testy używają wyłącznie atrap HTTP, bez płatnych wywołań. Jakość realnego modelu wymaga pilotażu na rzeczywistych tematach po konfiguracji.
