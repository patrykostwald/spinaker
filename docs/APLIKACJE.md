# Aplikacje spin.clinic — wdrożenie i publikacja

Operator: iapply sp. z o.o. Instrukcja z 30.09.2026. W tym zleceniu przygotowano PWA, Web Push i powiązania domeny ze sklepami. Nie utworzono kont sklepowych, projektów natywnych ani podpisanych paczek.

## Decyzje po audycie ścieżki użytkownika

Instalacja jest dostępna w stopce („Więcej → Aplikacja”). Mały baner można ukryć na 30 dni; link pozostaje dostępny. Okno działa z klawiaturą i zamyka się Escape. Android korzysta z systemowego zaproszenia, iOS otrzymuje instrukcję Safari. Zgoda na push następuje dopiero po wyborze tematów i kliknięciu „Zapisz i włącz”. Domyślnie nic nie jest zaznaczone. Odmowa, brak obsługi, wyłączona usługa i brak internetu mają osobne komunikaty. Konto nie jest wymagane dla spinu dnia i nitek Dr. Spina.

PWA przechowuje powłokę offline, ikony i odwiedzone zasoby statyczne. API ma strategię network-first z limitem oczekiwania 3 sekundy i fallbackiem do 5 minut, wyłącznie dla anonimowych publicznych `/api/clinic/spins/` i `/api/clinic/stats/`. Prywatne API, konto, formularze i dokumenty HTML nie trafiają do cache. Nie oznacza to pełnego archiwum artykułów offline. Service worker rejestruje się tylko w buildzie produkcyjnym i aktualizuje po zamknięciu starych okien aplikacji.

## Uruchomienie PWA i push

1. Wykonać standardowy build serwera z `backend/requirements.txt` (dodano `pywebpush`; zależności dostarczą również kryptografię), migracje `python manage.py migrate`, restart backendu, Celery worker i Celery beat oraz build frontendu.
2. W środowisku serwera wykonać `python manage.py vapid_keys`. Komenda wypisuje `VAPID_PUBLIC_KEY` i `VAPID_PRIVATE_KEY`, nie zapisuje plików. Bez biblioteki `cryptography` zwraca czytelny błąd. Nie umieszczać prywatnego klucza w kodzie, logach CI ani zmiennych `NEXT_PUBLIC_*`.
3. Właściciel wkleja klucze do `.env.production` i ustawia `VAPID_SUBJECT=mailto:ADRES_KONTAKTOWY` (rzeczywisty adres operatora). Zachować klucze między wdrożeniami; zmiana pary wymaga ponownej subskrypcji urządzeń.
4. Ustawić `PUSH_ENABLED=true` w backendzie oraz `NEXT_PUBLIC_PUSH_ENABLED=true` podczas budowania frontendu. Obie flagi są domyślnie wyłączone. Brak dowolnego klucza lub subject wyłącza API zapisu i wysyłkę. Wycofanie subskrypcji pozostaje dostępne w API także przy wyłączonej fladze backendu. Po wyłączeniu UI można zawsze odebrać zgodę w przeglądarce.
5. Udostępnić całą witrynę przez HTTPS. Zachować proxy `/api/` na tej samej domenie, cookies sesji i CSRF. Endpoint `/sw.js` ma być JavaScriptem, bez przekierowania i bez długiego cache CDN. Ścieżek `/.well-known/*` nie przekierowywać do Django ani na stronę główną — obsługuje je Next.js.
6. Włączyć powiadomienia ręcznie na urządzeniu testowym. Zweryfikować instalację, ponowne otwarcie bez sieci, odmowę zgody, zmianę tematów, usunięcie subskrypcji, dostarczenie i otwarcie powiadomienia. Na iOS 16.4+ push działa wyłącznie w aplikacji dodanej do ekranu początkowego, uruchomionej stamtąd. [Dokumentacja Apple Web Push](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers).

Ikony można odtworzyć przez `python scripts/generate_pwa_icons.py` z Pillow. Skrypt odczytuje geometrię `frontend-spin/app/icon.svg`, zapisuje PNG 192/512 i maskable z bezpiecznym marginesem. Przy zmianie SVG na bardziej złożone należy rozszerzyć renderer — nie używa zewnętrznej usługi.

### Kontrakt push dla integracji

`GET /api/push/subscriptions/` zwraca `{enabled, public_key, csrfToken, consent_version, results:[{endpoint, topics}]}`. Wyniki dotyczą bieżącej sesji urządzenia, nie wszystkich urządzeń konta. Cookie sesji jest wymagane także dla anonimowego użytkownika; adres endpointu nie jest tokenem do zarządzania cudzą subskrypcją.

`POST` przyjmuje `{endpoint, keys:{p256dh,auth}, topics:[...], consent_version}` z `PushSubscription.toJSON()` oraz wybranymi tematami. Nagłówek `X-CSRFToken` pochodzi z GET; oba żądania zachowują cookies. Dozwolone tematy: `spin-dnia`, `nitki-dr-spina`, `obserwowani`. POST jest idempotentny w obrębie urządzenia; zwraca 201, walidacja 400, obca sesja 409, usługa wyłączona 503. Obsługiwane usługi push: FCM, Mozilla i Apple; inne hosty są blokowane przed SSRF.

`DELETE` z CSRF usuwa subskrypcje tej sesji urządzenia (204). Frontend następnie wywołuje `unsubscribe()` w przeglądarce. Po wyczyszczeniu cookies starą subskrypcję należy wyłączyć i ponownie włączyć; wygasły endpoint zostanie usunięty po odpowiedzi 404/410 dostawcy.

`news.push.send_to_topic(topic, payload)` i `send_to_user(user, payload)` przyjmują payload `{title, body, url, tag}` i zwracają liczbę udanych wysyłek. Wysyłka do użytkownika wymaga zapisanego tematu `obserwowani`. Dla anonimowej subskrypcji powiązanie z kontem następuje dopiero przy ponownym zapisie po zalogowaniu. Zlecenia 053/055 mogą wywoływać `send_to_user` z własnych zdarzeń obserwowania; w 054 nie zmieniono ich logiki ani ustawień konta.

Spin dnia wysyła zadanie Celery o 21:15 czasu Europe/Warsaw, po wyliczeniu istniejącą funkcją wyboru dla obu obozów. Nowa opublikowana nitka generatora Dr. Spina (`dr-spin-kontekst-*`, bez autora kontowego) uruchamia wysyłkę dopiero po zatwierdzeniu transakcji. Zwykłe nitki nie uruchamiają zdarzenia. Rejestr `PushEvent` zapobiega ponownej wysyłce zdarzenia. Dostarczanie jest best effort: brak brokera, awaria workera lub dostawcy może spowodować pominięcie; nie ma gwarancji dostarczenia ani automatycznych powtórek po częściowym sukcesie.

Zapisywane są wyłącznie endpoint, klucze urządzenia, tematy, identyfikator sesji urządzenia, opcjonalny użytkownik oraz wersja i data zgody. Nie zapisujemy IP ani user-agenta. Usunięcie użytkownika kaskadowo usuwa jego subskrypcje. Integrator eksportu konta 053 powinien dołączyć tematy, datę i wersję zgody z relacji `user.push_subscriptions`, bez sekretów transportowych. Wycofanie usuwa rekord. Przed publikacją właściciel uzupełnia politykę prywatności o usługę push i dostawców transportu.

## Android — Bubblewrap / Trusted Web Activity

1. Właściciel zakłada konto organizacji iapply sp. z o.o. w Google Play Console, przechodzi weryfikację i opłaca **25 USD jednorazowo**. Wymagania nowych kont osobistych obejmują dodatkowe testy; dla spółki należy wybrać właściwy typ konta. [Rejestracja Google Play](https://support.google.com/googleplay/android-developer/answer/6112435?hl=en).
2. Na komputerze do budowania zainstalować Node.js, Bubblewrap CLI (`npm install -g @bubblewrap/cli`) oraz wymagane JDK/Android SDK zgodnie z kreatorem. Tych instalacji nie wykonano w tym zleceniu.
3. W osobnym katalogu uruchomić `bubblewrap init --manifest=https://spin.clinic/manifest.webmanifest`. Sprawdzić nazwę, domenę, start URL, ikony oraz wybrać trwały package ID, np. `pl.spin.clinic`. Zapisać bezpiecznie keystore i jego hasło; nie dodawać do repozytorium.
4. Uruchomić `bubblewrap build`. Przetestować APK na telefonie (`bubblewrap install`), przygotować podpisany AAB do Play Console. [Instrukcja TWA i Bubblewrap](https://developer.chrome.com/docs/android/trusted-web-activity/quick-start).
5. W Play Console włączyć Play App Signing i pobrać SHA-256 certyfikatu **podpisywania aplikacji**, nie samego klucza upload. Ustawić na serwerze frontendu `ANDROID_PACKAGE_NAME` i `ANDROID_SHA256_FINGERPRINT` (odcisk z dwukropkami). Endpoint `https://spin.clinic/.well-known/assetlinks.json` musi zwracać JSON 200 bez przekierowań. Bez jednej ze zmiennych zwraca 404. Dla lokalnego APK użyć odcisku jego certyfikatu w środowisku testowym.
6. Przetestować wersję z kanału wewnętrznego Play: aplikacja otwiera się bez paska przeglądarki, linki prowadzą do właściwych treści, offline i push działają po świadomej zgodzie.
7. Wypełnić opis, zrzuty ekranów, klasyfikację wieku, kontakt, politykę prywatności, Data Safety i wymagane deklaracje treści. Udostępnić recenzentom konto testowe, jeśli włączone funkcje go wymagają. Wybrać kraje i wysłać do oceny. Google podaje od kilku godzin do 7 dni, wyjątkowo dłużej; testy i weryfikacja konta są dodatkowym czasem. [Czas i publikacja](https://support.google.com/googleplay/android-developer/answer/9859654?hl=en).

## iOS — Capacitor

1. Właściciel rejestruje iapply sp. z o.o. w Apple Developer Program (weryfikacja organizacji, uprawnienia do reprezentowania, dane spółki) i opłaca **99 USD rocznie**, zależnie od lokalnej waluty i podatków. [Apple Developer Program](https://developer.apple.com/programs/enroll/).
2. Przygotować Mac z obsługiwaną wersją Xcode lub usługę CI/build z runnerem macOS i podpisywaniem. Chmura zastępuje komputer do budowania, nie konto Apple, certyfikaty ani akceptację umów; może kosztować dodatkowo.
3. W osobnym projekcie klienta zainstalować `@capacitor/core`, `@capacitor/cli`, `@capacitor/ios`; uruchomić `npx cap init` z nazwą i trwałym bundle ID. Zbudować lokalny frontend do katalogu `webDir`, następnie `npx cap add ios`, `npx cap sync ios`, `npx cap open ios`. [Dokumentacja Capacitor](https://capacitorjs.com/docs).
4. Obecny Next.js używa serwera, proxy i Route Handlers. Nie można po prostu wskazać `webDir` na `.next` ani wyeksportować całego serwisu statycznie. Przygotować klienta mobilnego z API przez HTTPS, obsługą sesji/CSRF, lokalną powłoką i odpowiednimi funkcjami natywnymi. Zdalny `server.url` może służyć prototypowi, ale sama opakowana strona nie jest gotowym produktem do App Store.
5. W Xcode ustawić Team, Bundle Identifier, signing, ikony oraz Associated Domains `applinks:spin.clinic`. Ustawić na serwerze Next `APPLE_TEAM_ID` i `APPLE_BUNDLE_ID`. Sprawdzić 200 i JSON pod `/.well-known/apple-app-site-association` (bez rozszerzenia i przekierowań; bez konfiguracji 404). Obsłużyć wejście przez Universal Link w aplikacji.
6. Dodać funkcje ponad stronę: zapis wybranych treści offline, natywne udostępnianie, poprawną nawigację i deep linki. Dla natywnego push skonfigurować uprawnienie Push Notifications, APNs oraz integrację Capacitor i backendu tokenów APNs. **Obecne Web Push/VAPID nie jest integracją APNs dla aplikacji Capacitor.** [Rejestracja w APNs](https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns).
7. Gdy logowanie Google służy do podstawowego konta, co do zasady zapewnić również Sign in with Apple (lub rozwiązanie spełniające warunki równoważnej prywatności i wyjątków z 4.8). Apple 4.2 wymaga minimalnej funkcjonalności wykraczającej ponad przepakowaną stronę. Przy kontach uwzględnić usuwanie konta z aplikacji; treści czytelników wymagają mechanizmów moderacji i zgłoszeń. Zweryfikować gotowość 053/055 przed zgłoszeniem. [App Review Guidelines 4.2, 4.8 i 5.1.1](https://developer.apple.com/app-store/review/guidelines/).
8. Utworzyć aplikację w App Store Connect, uzupełnić opis, prywatność, wiek, zrzuty, kontakt i dane do oceny. W Xcode wykonać Product → Archive → Distribute App → App Store Connect. Przetestować przez TestFlight na fizycznym iPhonie, potem wybrać build i zgłosić do oceny. [Publikacja Capacitor](https://next.capacitorjs.com/docs/next/ios/deploying-to-app-store).
9. Apple deklaruje, że 90% zgłoszeń sprawdza średnio w czasie poniżej 24 godzin; nie jest to gwarancja. Zaplanować czas na odrzucenie, wyjaśnienia i ponowną ocenę. [App Review](https://developer.apple.com/app-store/review/).

## Co pozostaje po stronie właściciela

Klucze VAPID i adres kontaktowy, flagi wdrożeniowe, migracja i działający worker/beat; konta organizacji i opłaty; identyfikatory aplikacji, certyfikaty i bezpieczne przechowanie kluczy; polityka prywatności, formularze sklepowe, materiały promocyjne, testy telefonów oraz końcowe wysłanie paczek. Nie ma gwarancji przyjęcia przez sklep. PWA można udostępnić wcześniej bez publikowania w sklepach.

## Weryfikacja kodu

Backend: `SKIP_DOTENV=1` wyłącza odczyt plików `.env` podczas testów; uruchomić wskazanym Pythonem `-m pytest -q news/test_push.py -p no:cacheprovider --basetemp=.pytest-tmp/push-054` w `backend`. Frontend: `npx --no-install tsc --noEmit -p .` oraz `node scripts/test-pwa.cjs` w `frontend-spin`. Testy nie wysyłają prawdziwych powiadomień. Test na HTTPS i fizycznych urządzeniach pozostaje etapem przedprodukcyjnym; serwer nie był uruchamiany w tym zleceniu.

Wynik lokalny: 19 testów backendu przeszło; Django `check` i kontrola zgodności migracji bez uwag. Testy Node dla obu tras powiązań, push, bezpiecznego otwierania URL, pomijania prywatnego API, czasu ważności cache i `no-store` przeszły. Nowy komponent, manifest i Route Handlers przeszły ukierunkowaną kontrolę TypeScript z istniejącymi zależnościami głównego repozytorium. Pełne polecenie `npx --no-install tsc --noEmit -p .` nie mogło się zakończyć poprawnie: kopia nie ma własnych zależności, a próba wykorzystania zewnętrznych nie zapewniła standardowego rozwiązywania modułów. Niczego nie instalowano. Pełny typecheck należy ponowić w przygotowanym środowisku budowania.
