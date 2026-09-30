Zlecenie 053 — konta i wejście do serwisu, 30 września 2026

Wdrożono backend i formularze wejścia, bez przebudowy panelu `/konto`.

Audyt przeprowadzono równolegle dla formularzy, tożsamości Google oraz obserwowania i publikacji. Istniejący dialog miał obsługę fokusu i CSRF, ale brakowało obowiązkowego e-maila, zgód, potwierdzenia adresu i odzyskiwania hasła. Zachowano sesje, komponenty, tokeny `--sc-*` i dotychczasowe modele nitek. Nie zmieniano diagnoz AI ani reguł traktowania obozów politycznych.

**Wykonanie**

- Rejestracja: wymagany e-mail, publiczna nazwa użytkownika, wersje obu dokumentów i data akceptacji. Nowy adres i adres już użyty otrzymują ten sam komunikat; rejestracja nie loguje automatycznie. Obie ścieżki wykonują hashowanie hasła i zlecają zadanie pocztowe.
- Podpisany, jednorazowy link potwierdzenia ważny 48 godzin. Ponowna wysyłka ograniczona do 5 minut, dodatkowo działają limity API. Niepotwierdzone konto może korzystać prywatnie; publikacja nitek oraz opinii o artykułach, nitkach i diagnozach jest blokowana.
- Logowanie nazwą albo e-mailem. Reset ma identyczną odpowiedź dla istniejącego i nieistniejącego adresu, token Django ważny godzinę, kontrolę siły hasła oraz unieważnienie wcześniejszych sesji po zmianie hasła.
- Google OIDC: state, nonce, PKCE, kontrola odbiorcy, wystawcy, dat i potwierdzenia e-maila. Brak automatycznego łączenia z istniejącym kontem na podstawie adresu. Tokeny Google nie są przechowywane. Bez konfiguracji przycisk jest ukryty.
- `Follow`, `Notification`, `NotificationSettings` i trwała kolejka `NotificationEvent`. Hooki obejmują zapis opublikowanej diagnozy, pierwszą publikację nitki i nową opinię pod nitką. Publikacja nie czeka na broker, SMTP ani push. Osoby publiczne są rozpoznawane przez istniejące, jawne powiązania kont.
- `news.notify.notify(user, kind, title, url)` jest jedynym punktem dostarczania powiadomień; opcjonalnie importuje `news.push.send_to_user`. Respektuje flagę push i preferencje użytkownika.
- Celery przetwarza kolejkę co minutę, a co godzinę sprawdza należne maile dzienne/tygodniowe. Digest domyślnie wyłączony, wysyłany tylko na potwierdzony adres przez istniejące `SOURCE_MAIL_SMTP_*`.
- Eksport JSON obejmuje konto, zgody, nitki z elementami, wszystkie cztery rodzaje opinii, ulubione i obserwowanych. Usunięcie wymaga hasła i dokładnego `USUŃ`; usuwa konto, prywatne i publiczne nitki oraz powiązane dane. Usuwane są też powiadomienia innych osób wskazujące na usuwane nitki.
- Rozbudowano `AccountDialog`; dodano `/konto/potwierdz`, `/konto/nowe-haslo`, `/konto/usun`. Błędy przy polach, etykiety, przenoszenie fokusu i pola dotykowe minimum 44 px. Starsze konta uzupełniają adres i zgody na stronie potwierdzenia.

**Przekazanie do 054 i 055**

- Endpointy zgodne ze ścieżkami kontraktu w `news/account_urls.py`.
- `GET /api/account/follows/` zwraca tablicę `{id, kind, target_id, label, url}`; POST zwraca pojedynczy obiekt. `thread` oznacza `PersonalContextThread`. Własność obserwowania i odczytu powiadomień sprawdzana jest po stronie serwera.
- `GET/PATCH /api/account/me/` zachowuje strukturę `{authenticated, user, csrfToken}`; nowe pola to `user.email`, `user.email_verified`, `user.accepted_terms_version`; dostępność Google jest w `google_enabled` na poziomie odpowiedzi. PATCH przyjmuje `email`, aktualne `password`, `accepted_terms`, `accepted_privacy`. Zmiana adresu wymaga ponownego potwierdzenia.
- Panel 055 powinien podlinkować `/konto/usun` oraz obsłużyć ustawienia, obserwowanych i powiadomienia. Panel nie był edytowany w 053.
- Konto Google bez lokalnego hasła ustawia je przez reset e-mailem przed usunięciem konta.

**Sprawdzenie**

- Główny zestaw: 75 testów zaliczonych, 1 pominięty z powodu braku `cryptography` w venv. Obejmuje konta, cykl życia, Google, powiadomienia, prywatne nitki i community. Testy dostawców i poczty używają mocków.
- TypeScript: `npx --no-install tsc --noEmit -p .` w `frontend-spin` zaliczony; dodatkowo sprawdzono lokalne źródła `packages/ui`.
- `manage.py check`, `makemigrations --check --dry-run` oraz `git diff --check` zaliczone.
- Dodatkowy zestaw `test_profiles_topics.py` ujawnił istniejący problem: `test_source_selection_includes_beyond_top_ten_and_hides_inactive`. Niezmieniony `portal_config` także w HEAD wybiera katalog bez filtra `is_active`; test oczekuje wykluczenia nieaktywnych źródeł. Nie zmieniano katalogu w zleceniu 053.
- Nie uruchamiano serwera, nie wykonywano prawdziwego logowania Google ani wysyłki SMTP, nie instalowano pakietów, nie czytano `.env`, nie wykonywano commitów ani płatnych zapytań. Konfiguracja testów pomija wczytywanie `.env`. TypeScript korzysta z ignorowanych junction do już istniejących zależności głównego checkoutu.

**Do uruchomienia przez właściciela**

1. Zastosować migracje `0096_account_identity` i `0097_notifications`; uruchomić worker i beat Celery oraz istniejący broker/cache. Migracje zostały sprawdzone na bazie testowej, nie na produkcji.
2. Ustawić `ACCOUNT_PUBLIC_URL` na publiczny adres HTTPS oraz istniejącą konfigurację `SOURCE_MAIL_SMTP_*`. Przeprowadzić rzeczywisty test dostarczalności maili.
3. Dodać `GOOGLE_OAUTH_CLIENT_ID` i `GOOGLE_OAUTH_CLIENT_SECRET`. W Google Console wpisać dokładny callback `{ACCOUNT_PUBLIC_URL}/api/account/google/callback/` i skonfigurować ekran zgody.
4. Uzgodnić i utrwalić wersje dokumentów w `ACCOUNT_TERMS_VERSION` i `ACCOUNT_PRIVACY_VERSION` (wartości startowe: `2026-09-30`) zgodnie z opublikowanymi dokumentami.
5. Świadomie włączyć `ACCOUNTS_ENABLED` / `NEXT_PUBLIC_ACCOUNTS_ENABLED` oraz, dla publikacji nitek, `THREADS_ENABLED` / `NEXT_PUBLIC_THREADS_ENABLED`. Domyślnie wyłączone. Push pozostaje wyłączony do integracji 054.
6. Dla aplikacji mobilnych potrzebne będą konta organizacji iapply sp. z o.o. w Apple Developer i Google Play Console. Apple nie jest implementowane w 053. Dla planowanej aplikacji iOS z Google należy zaplanować Sign in with Apple: aktualna reguła 4.8 wymaga równoważnej opcji logowania ograniczającej dane i umożliwiającej ukrycie e-maila, z wyjątkami opisanymi przez Apple. Źródło: [Apple App Review Guidelines 4.8](https://developer.apple.com/app-store/review/guidelines/#login-services).

**Ograniczenia operacyjne**

W tym venv nie ma `cryptography`, więc Google użyje dopuszczonego w zleceniu tokeninfo. Google opisuje tę ścieżkę jako narzędzie diagnostyczne; przed większym ruchem warto zapewnić bibliotekę w obrazie wdrożeniowym i sprawdzić ścieżkę JWKS. Źródło: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect).

Wysyłka linków wymaga działającego brokera i SMTP. Niedostępny broker nie ujawnia istnienia adresu w odpowiedzi; użytkownik może ponowić wysyłkę. Digest ponawia nieudaną dostawę przy kolejnym przebiegu. Wizualnego sprawdzenia w uruchomionej aplikacji nie wykonywano zgodnie z zakazem uruchamiania serwera.

Wywiady `ClinicInterview` nie mają relacji do osoby publicznej; nie przypisujemy powiadomień przez zgadywanie nazwiska. Obecny hook diagnoz dotyczy `SpinDiagnosis` i jawnych powiązań osoby z kontem źródłowym.
