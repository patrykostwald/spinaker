# Nitki dziennikarskie i sponsorowane — zakres MVP

Stan implementacji: 9 września 2026. Konta i sponsorzy w testach są fikcyjnymi fixture'ami w odizolowanej bazie testowej. Nie utworzono takich kont ani nitek w działającej bazie.

## Uprawnienia

| Konto | Tworzenie i edycja nitek | Publikacja i wyróżnienie | Sponsor | Dane źródłowe i panel administratora |
|---|---|---|---|---|
| Niezalogowane / zwykłe | Brak | Brak | Brak | Brak zapisu |
| Dziennikarz | Tylko własne nitki | Zatwierdza redakcja | Ustala redakcja | Brak zapisu / brak dostępu do admina |
| Redakcja (`is_staff`) | Wszystkie nitki | Tak | Tak | Zgodnie z dotychczasowymi uprawnieniami |

Administrator z uprawnieniami zarządzania użytkownikami przypisuje istniejące konto do grupy `journalists` w panelu Django. Migracja tworzy pustą grupę; nie nadaje nikomu członkostwa ani uprawnień administratora. Rejestracja i profil nie przyjmują nadania roli. Usunięcie członkostwa odbiera dostęp redakcyjny przy następnym żądaniu.

Zapis dziennikarza zawsze daje `published=false` i `is_featured=false`. Także edycja własnej opublikowanej nitki cofa ją do szkicu do ponownego zatwierdzenia. MVP nie przechowuje obok siebie publicznej i roboczej wersji tej samej nitki — w czasie poprawiania nitka jest niedostępna publicznie.

## API dla frontendu

- `GET /api/me/`: dotychczasowe pola oraz `role`, `is_journalist`, `can_edit_threads`, `can_create_threads`, `can_publish`, `can_manage_sponsorship`. Dziennikarz ma `is_editor=true`, `can_publish=false` i `can_manage_sponsorship=false`.
- Te same pola roli znajdują się w `user` odpowiedzi `/api/account/me/` i logowania konta. Obsługiwane wartości: `editor`, `journalist`, `reader`, `guest`.
- Oba logowania `/api/account/login/` i `/api/auth/login/` obsługują nadanego dziennikarza. Starszy adres redakcyjny nadal odrzuca zwykłe konto. Ochrona CSRF pozostaje wymagana.
- `GET /api/editor/threads/`: redakcja widzi wszystkie nitki, dziennikarz wyłącznie własne. Odczyt lub edycja cudzej przez dziennikarza zwraca 404. Zwykłe konto otrzymuje 403.
- Dziennikarz wysyła do tworzenia/edycji tylko `title`, `description`, `items`. Każdy item zawiera `article_id` **albo** `external_url` (odnośnik do posta X) oraz opcjonalnie `editorial_note`.
- Dziennikarz całkowicie pomija pola `published`, `is_featured`, `editorial_slot`, `is_sponsored`, `sponsor_name`, `created_by`, `thread_type`. Również `false` lub pusty ciąg w tych polach daje 400. Nie można zmienić właściciela przez API.
- `/api/editor/articles/`, `/api/editor/preview-url/`, katalog źródeł i pozostałe dotychczasowe operacje redakcyjne nie uzyskują nowych uprawnień dla dziennikarzy. Dodanie istniejącego materiału i bezpośredniego odnośnika X do nitki jest dostępne. Import nowego artykułu pod URL nadal wykonuje redakcja.
- Dotychczasowa odpowiedź zapisu pozostaje `{slug, published}`. Publiczne endpointy zwracają wyłącznie `published=true`.

## Sponsor i autor

`Thread` otrzymuje `is_sponsored` i `sponsor_name` (maksymalnie 200 znaków). API wymaga niepustej nazwy po oznaczeniu sponsora. Tylko redakcja może zmieniać te pola; jawne wyłączenie `is_sponsored` usuwa nazwę. Oznaczenie nie zapisuje nic w `Article`, `Source` ani metadanych źródła.

Każda odpowiedź nitki i każdy jej `ThreadItem` zawierają:

- `is_sponsored`: wartość logiczna;
- `sponsor_name`: nazwa albo pusty ciąg;
- `sponsorship_label`: `Materiał sponsorowany · <nazwa>` albo pusty ciąg;
- `author_name`: konto autora komentarza/nitki;
- `author_role`: rola autora, do rozróżnienia wyglądu podpisu.

Jeżeli dawny rekord nie ma autora, dotychczasowy podpis `Redakcja` zostaje zachowany. Samo źródło w polu `article` zachowuje swój tytuł, kategorię i autora publikacji; podpis autora nitki jest oddzielny.

Stary `thread_type=sponsored` nadal oznacza materiał sponsorowany. Migracja przenosi ten fakt do `is_sponsored=true`; bez znanej nazwy sponsora wycofuje dawną publikację i wyróżnienie, zamiast wymyślać nazwę. Ograniczenie bazy nie pozwala opublikować oznaczonej nitki z pustą nazwą. Formularz admina dodatkowo usuwa same białe znaki i waliduje nazwę. Etykiety w renderowaniu i eksporcie wdraża frontend.

Aktualizacja API zapisuje wyłącznie walidowane pola. Zwykła edycja autora nie nadpisuje oznaczeń sponsora zapisanych w międzyczasie przez redakcję.

## Wdrożenie

Migracja `0025_journalist_threads_sponsorship` zależy od `0024_profiles_topics_favorites`. Jej zastosowanie w działającej bazie i restart usług koordynuje główny proces. Nie są potrzebne klucze zewnętrznych API ani płatne wywołania.

Testy obejmują właściciela i cudze nitki, grant/revoke roli, oba logowania i CSRF, brak eskalacji przez rejestrację, zatwierdzanie, wycofanie po edycji, sponsorów w każdym boxie, odrzucenie sponsorów bez nazwy, niezmienność Article i ochronę oznaczeń przed nadpisaniem nieaktualnym obiektem. Kontrola Django i zgodność migracji przechodzą.
