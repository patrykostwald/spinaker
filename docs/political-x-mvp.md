# Zaplecze „Przekazu dnia” — konfiguracja X

Stan: 9 września 2026. To uruchamialny fundament zaplecza redakcyjnego, przetestowany na syntetycznych danych. **Nie wykonano płatnych wywołań X, nie dodano prawdziwych kont ani postów, nie podłączono generowania propozycji AI i nie opublikowano nitek.**

## Co jest przygotowane

- `PoliticalAccount`: stabilny identyfikator X, nazwa konta, nazwa wyświetlana, obóz government/opposition, publiczne źródło i notatka potwierdzenia. Aktywny redaktor jawnie potwierdza dane; zapisujemy osobę i datę. Zmiana danych lub obozu unieważnia skuteczność poprzedniego potwierdzenia. Klasyfikacja nie jest oceną dokonaną przez AI.
- `PoliticalPost`: źródłowy tekst i metadane API, data podana przez X, identyfikator, permalink, rzeczywisty autor, pasujące media, hash odpowiedzi i obóz w chwili pobrania. Dane pozostają poza Article i publiczną wyszukiwarką mediów.
- `PoliticalDraft`: wybrane przez redaktora 1–15 postów oraz przestrzeń na przyszły szkic AI. API udostępnia pakiet źródeł i zasady, jawnie z `ai_status=not_requested`. Zatwierdzenie szkicu nie publikuje Thread. Dwie publiczne sekcje korzystają dopiero ze zwykłych nitek zatwierdzonych i opublikowanych przez redakcję.
- `PoliticalRead`: operacyjny rejestr rezerwacji odczytów. Nie zawiera tokenów. Zaplecze ma listę kont, postów, szkiców i status budżetu; wszystkie endpointy wymagają staff.

## Integracja techniczna

Migracja `0023_political_intake` zależy od `0022_public_accounts`. Uruchomienie migracji i restart koordynuje główny proces projektu; moduł nie wykonuje ich sam.

Do istniejących tras można dołączyć `path('staff/political/', include('news.political_urls'))`. Dostępne są `accounts/`, `accounts/{id}/confirm/`, `posts/`, `drafts/`, `drafts/{id}/packet/`, `drafts/{id}/review/` i `status/`. API nie publikuje nitek i nie uruchamia płatnego pobrania przy żądaniu przeglądarki.

Rejestracja administratora: `news.political_admin.register_political_admin(site)`. Zadanie harmonogramu: `news.political_polling.political_poll_cycle()`. Jedno wywołanie przetwarza najwyżej jedną stronę jednego konta. Istniejący harmonogram ma je wywoływać poza procesem web.

Przykładowe ustawienia startowe — sekret wpisuje właściciel w konfiguracji serwera, nie w repozytorium:

```dotenv
X_POLITICAL_POLLING_ENABLED=false
X_POLITICAL_BEARER_TOKEN=
X_POLITICAL_PAGE_SIZE=10
X_POLITICAL_DAILY_POST_LIMIT=100
X_POLITICAL_DAILY_REQUEST_LIMIT=100
X_POLITICAL_MONTHLY_USD_LIMIT=5
X_POLITICAL_INITIAL_LOOKBACK_HOURS=24
```

Bez osobnego włączenia i tokenu cykl zwraca `disabled` bez żądania sieciowego i bez rezerwowania pieniędzy. Sam dawny `TWITTER_ENABLED` lub jego token nie włącza tego nowego modułu. Brak aktywnych, potwierdzonych kont daje `idle`. Limit budżetu daje jawny `budget_limit`; nie zmieniamy po cichu częstotliwości kont.

## Odczyt i kompletność

Używamy wyłącznie oficjalnego `GET https://api.x.com/2/users/{id}/tweets`. Referencja sprawdzona 9 września 2026 opisuje `post.fields` i `note_post`; starszy przewodnik zawiera nazwy `tweet.fields`. Moduł stosuje bieżącą referencję i nie wykonuje automatycznych dodatkowo płatnych prób innego schematu. Pierwszy odczyt z prawdziwym tokenem musi potwierdzić dostęp i odpowiedź dla konkretnej aplikacji. Obsługa błędu nie fabrykuje tekstu ani daty. [Referencja endpointu](https://docs.x.com/x-api/users/get-posts).

Pierwsze okno to domyślnie ostatnie 24 godziny, bez pełnego importu historii konta. Odpowiedzi użytkownika są uwzględniane, reposty wyłączone. Początek i koniec okna są stałe w trakcie jego paginacji. `since_id` przesuwa się dopiero po ostatniej stronie; błąd zachowuje okno i token do ponowienia. Brak postów również zachowuje granicę sprawdzonego okresu. API przyjmuje 5–100 postów na stronę. Timeline nie gwarantuje pełnego archiwum: dokumentacja podaje granicę 3200 najnowszych postów oraz 800 przy wykluczeniu odpowiedzi. [Paginacja i zakres](https://docs.x.com/x-api/posts/timelines/integrate).

Zapis strony i jej postępu jest atomowy. Globalna dzierżawa w bazie ogranicza równoległe rezerwacje także przy wielu procesach. Przed zapisem ponownie sprawdzamy konto, potwierdzenie i jego niezmienność. Weryfikujemy zgodność identyfikatora autora oraz nazwy konta z odpowiedzią X. HTTP 429 respektuje czas ponowienia, a błędy dostępu blokują dalsze próby przez okres oczekiwania. Wygasły token paginacji lub zmiana schematu wymagają diagnozy; nie zerujemy bez dowodu historii postępu. [Limity X](https://docs.x.com/x-api/fundamentals/rate-limits).

## Budżet

Dokumentacja podaje **0,005 USD za zwrócony post i 0,010 USD za użytkownika**. Pobieramy rozwinięcie jednego autora, aby sprawdzić tożsamość i mieć atrybucję. Przed żądaniem rezerwujemy maksimum: liczba wyników × 0,005 + 0,010 USD. Poprawna, zweryfikowana odpowiedź zwalnia niewykorzystaną część. Błąd lub niepewny wynik pozostawia pełną rezerwację. Nie zakładamy rabatu za deduplikację. Dodatkowy limit liczby żądań zabezpiecza także puste odpytywania. [Cennik X](https://docs.x.com/x-api/getting-started/pricing).

Przykład szacunkowy: 500 postów i 25 odczytów użytkownika to 2,75 USD według powyższych stawek. Kwota nie obejmuje AI, podatków ani przewalutowania. Lokalny licznik jest ostrożnym oszacowaniem tego modułu, nie fakturą X ani limitem wszystkich aplikacji na koncie. Ceny trzeba potwierdzić w konsoli przed aktywacją i ustawić tam własny limit wydatków. Domyślne 5 USD to mały pilotaż; duża lista kont może wymagać zwiększenia budżetu.

## Miniatury, osadzenie i eksport

Miniatura jest zapisywana tylko wtedy, gdy odpowiedź API wiąże `attachments.media_keys` z dokładnie jednym obiektem `includes.media`. Zdjęcie pochodzi z pola `url`, a kadr filmu z `preview_image_url`; dopuszczamy oficjalny host obrazów `pbs.twimg.com`. Brak zgodności lub obrazu oznacza pusty podgląd. Nie tworzymy zrzutów ani obrazów zastępczych sugerujących rzeczywisty post. Poufne dane autora nie są żądane.

Do publicznego pokazywania wpisów preferowany jest oficjalny embed. Obsługuje autora, post, media, edycje i akcje. Sam adres posta nie gwarantuje miniatury ani działającego embedu, np. po usunięciu lub ograniczeniu dostępności. Własne wyświetlanie wymaga pełnego, niezmienionego tekstu, autora, @nazwy, zdjęcia profilu, daty i odnośników, oznaczenia X oraz zgodnych akcji lub „Zobacz w X”. Miniatura nie zastępuje całego wymaganego przedstawienia posta. Nie należy nakładać komentarza autora naszej nitki na źródłowy tekst X ani sugerować poparcia sponsora. [Osadzanie postów](https://docs.x.com/x-for-websites/embedded-posts/overview), [wymagania prezentacji](https://docs.x.com/developer-terms/display-requirements).

Eksport nitki pozostaje wariantem do ręcznej publikacji, nie połączeniem konta X ani automatycznym wysyłaniem. Każdy fragment trzeba sprawdzić funkcją `twitter-text`, z numeracją 1/N i linkami. Standardowy budżet to 280 ważonych znaków; URL liczy 23, a emoji mają własne wagi. Zwykłe `len()` nie wystarcza. Nie można przyciąć cytatu i przedstawiać go jako pełnej, niezmienionej wypowiedzi. Dla materiałów przekraczających budżet bezpieczny układ eksportu to komentarz autora naszej nitki i link do oryginalnego posta. [Liczenie znaków](https://docs.x.com/fundamentals/counting-characters).

## Aktualność i dalsze AI

API timeline nie zastępuje obsługi usunięć i późniejszych zmian. X wymaga aktualizacji przechowywanego materiału oraz usunięcia lub zmiany go możliwie szybko, w tym w ciągu 24 godzin od otrzymania odpowiedniego żądania. Przygotowano akcję staff usuwającą tekst i media niedostępnego posta oraz cofającą przegląd powiązanych szkiców. Powtórne pobranie nie odtwarza tak wycofanej treści. **Automatyczna synchronizacja usunięć/zmian i publiczny renderer nie są jeszcze podłączone**; trzeba je zamknąć przed publicznym prezentowaniem kopii tekstu. [Zasady przechowywania i aktualizacji](https://docs.x.com/developer-terms/policy).

Przekazanie źródeł do późniejszego wnioskowania AI nie jest trenowaniem modelu. Obecny moduł nie robi żadnego z nich. Umowa X III.A(k) zabrania wykorzystywania API lub treści X do fine-tuningu/trenowania modeli foundation/frontier. Planowane wnioskowanie i wyświetlanie trzeba prawidłowo opisać w zastosowaniu deweloperskim; nie należy traktować zakupu kredytów jako zgody na dowolne dalsze użycie. [Developer Agreement](https://docs.x.com/developer-terms/agreement).

## Pozostałe warunki uruchomienia

1. Właściciel zakłada aplikację X z opisanym zastosowaniem, dostarcza token tylko do konfiguracji serwera i ustawia budżet.
2. Redakcja dodaje konta na podstawie sprawdzonych publicznych źródeł, podaje stabilne ID, jawnie potwierdza obóz i włącza wybrane konta. Rejestr startuje pusty.
3. Główny proces stosuje migracje i dołącza cykl. Pierwszy mały odczyt potwierdza rzeczywisty schemat, opłaty oraz dostęp danej aplikacji; dopiero potem poszerzamy listę.
4. Adapter AI ma korzystać z pakietu źródeł, oznaczać propozycję jako niezatwierdzoną, nie przypisywać intencji ani pozornie naukowych procentów i nie publikować Thread. Obecne packet/rules to przygotowane wejście, a nie działający agent generujący.
5. Po redakcyjnym przeglądzie powstaje zwykła nitka w odpowiednim miejscu strony. Zatwierdzenie PoliticalDraft samo nie wykonuje tej czynności.

Weryfikacja: **21 testów izolowanych**, `manage.py check` bez problemów i brak brakujących migracji w `makemigrations --check --dry-run`. Testy nie korzystały z prawdziwego tokenu, kont polityków ani płatnej sieci.
