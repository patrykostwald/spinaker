# spina3.pl: backend (pakiet `backend/spina3`, v2 z 12.10.2026)

Stan: kod i testy lokalne, nic nie wdrożone, żadnych migracji na produkcji. Zlecenie bazowe: `Desktop\projekty\spina3\PROMPT-BACKEND.md`
(poprawki po recenzji RECENZJA-FABLE.md, pętla produktu zbudujmi\gust\spina3\PETLA-PRODUKT.md). v2: model właściciela z 11-12.10
(raport: zbudujmi\gust\spina3\RAPORT-BACKEND-v2.md).

## Model produktu v2
- Autor wstawia box (kotwica: box z bazy bez przypięcia, adres URL albo zdjęcie) i robi do niego DOKŁADNIE JEDNO przypięcie
  (dowód: box z bazy, URL albo zdjęcie) z komentarzem (do 280 znaków) i opcjonalnym stanowiskiem autora wobec boxa. Jedna operacja: `POST boxes/`.
- Inni użytkownicy NIE przypinają. Oceniają przypięcie dwustanowo (`agree` / `disagree`, jedna ocena na użytkownika, zmiana po 1 h,
  wycofanie) i komentują pod parą box + przypięcie (jeden poziom odpowiedzi, ocena "przydatny", sortowanie najnowsze / najlepiej ocenione).
- Wzorzec Dr. Spina: BOX 1 = wpis polityka (import), BOX PRZYPIĘTY = diagnoza (przypięcie systemowe `kind=diagnosis`, zatwierdzone przez
  człowieka). Wpisy polityków z importu są zarezerwowane dla diagnozy (użytkownik nie może ich przejąć: 403 `reserved_for_diagnosis`).
- Box importera bez przypięcia (artykuł, dokument) przejmuje pierwszy użytkownik jednym przypięciem (flaga `adopt_authorless_boxes`).
  Cudzego boxa użytkownika nie da się przejąć. Usunięcie przypięcia przez autora ukrywa box dodany przez niego; box importera wraca do puli.

## Zasada
Osobna aplikacja Django `spina3` na WSPÓLNEJ bazie: żadnych zmian w tabelach i plikach `news` (w tym w plikach chronionych
`clinic_council.py`, `council_quorum.py`, `techniques.py`, `council_registry.py`). Zmiany poza pakietem: `config/settings.py`
(INSTALLED_APPS + blok `SPINA3`), `config/urls.py` (jedna linia `api/spina3/`).

## Moduły
| Plik | Rola |
|---|---|
| `config.py` | Konfiguracja w jednym miejscu: m = 3, progi domknięte, histereza 0,04, min_n 3 i min_n_extreme 8 (na n ważonym OCEN), tryb zgodność/popularność, okno otwarte 6 h, jeden stopień na dobę, wagi T0-T3, klastry, limity (boxy, oceny, komentarze), kolory nicków (11 + `spin` zarezerwowany dla Dr. Spina), flagi (oceny, komentarze, przejmowanie, cisza wyborcza z osobnymi przełącznikami dla boxów, ocen i komentarzy). `public_config()` dla frontendu. Wersja wzoru 2.0. |
| `scoring.py` | Czyste funkcje: `score`, `band`, `band_with_hysteresis`, `level`, `level_transition`, `aggregate` (oceny +1/-1, rozkład `{agree, disagree}`), `views` (Spór, Zgoda, Najgoręcej, Zmiana zdania), `cluster_groups` (Jaccard na ocenach), `rating_weight`, `sort_key`, kursor, `kendall_tau`, `effective_sort`, `aria_label`. Do przepisania 1:1 na frontend. |
| `models.py` | `Box`, `BoxLink`, `Pin` (JEDNO na box: unikalność `box` przy status != removed; dowód box/url/image/diagnosis; `target_status`), `Rating` (user, pin, stance +1/-1, active/withdrawn, waga konta; jedna na user+pin), `Comment` (box, parent jeden poziom, visible/held/hidden/removed, powód ukrycia, licznik "przydatny"), `CommentVote`, `BoxSpinka` (z ocen; `first/last_rating_at`), `PinEvent` (append-only, pseudonim), `UrlCheck`, `Report` i `Appeal` (przypięcie, box albo komentarz), `RankingSnapshot`, `BoxDailyCounter`, `HeldPublication`, `Spina3Profile` (pseudonim, zespół, T3, sankcje, zgoda, klaster, `nick_color`), `Chain`/`ChainItem` (zarezerwowane). |
| `trust.py` | Poziomy T0-T3 (waga 0 / 0,5 / 1 / 1); aktywność = przypięcia + oceny + widoczne komentarze; limity dobowe: boxy 0/3/10/10, oceny 0/30/200/200, komentarze 0/10/60/60; URL od T2. Zespół: waga 0. Dr. Spin nie ocenia i nie komentuje. |
| `pins.py` | `create_box_with_pin` (jedna transakcja: kotwica + dowód; URL spoza bazy = nowy box `pending`, T3 od razu), `update_pin` (komentarz, stanowisko autora raz na 24 h, wymiana dowodu), `remove_pin`, rzecz zniknęła (7 dni, potem ukryte; przywrócenie automatyczne), anonimizacja konta (przypięcia, oceny, komentarze), zwolnienie wstrzymanych po ciszy. |
| `ratings.py` | `set_rating` (tworzy albo zmienia; własne 403, dowód oczekujący/niedostępny 409, box zamrożony 409, cisza 423, limity 429, odstęp 1 h także po wycofaniu), `withdraw_rating`, `my_rating`. |
| `comments.py` | Tworzenie, edycja, usunięcie, "przydatny", lista z kursorem (`newest` / `top`), antyspam (pre-filtr, link z konta T1 = held, limit dobowy, seria 3/min, duplikat 24 h = 409), moderacja `hide_comment` / `restore_comment` z uzasadnieniem. |
| `spinka.py` | Przeliczenie BoxSpinka z ocen po każdej zmianie (transakcyjnie); oceny liczą się tylko przy opublikowanym przypięciu z dostępnym dowodem (inaczej Otwarta: `no_pin` / `target_unavailable`); odświeżanie wag i klastrów zadaniem. |
| `ranking.py` | Migawka co 10 min, kursor (wersja + klucz), wznowienie po wygaśnięciu, TOP_CAP, wymiary, szukanie, półka podobnych, rząd "Dziś", kafelek z `pin` (skrót przypięcia), `my_rating`, `comment_count`. |
| `public.py` | Serializacja według flag praw; `author_info` (nick, znaczek `dr_spin` / `team` / `author`, kolor nicku z listy); `pin_summary`, `pin_item`, `comment_item`. |
| `importer.py` | Wpisy, diagnoza zatwierdzona przez człowieka -> box `diagnosis` + `BoxLink` + jedyne przypięcie systemowe wpisu (oceniane przez użytkowników), wycofanie -> ukrycie, usunięte wpisy -> `removed_at_source`, dokumenty urzędowe, prasa za flagą. Zero sieci. |
| `url_queue.py` | Normalizacja, SSRF, blokady, decyzja człowieka; `accept` publikuje box-kotwicę z linku albo podpina dowód, `reject` ukrywa kotwicę z powodem albo daje 7 dni na wymianę dowodu. |
| `comment_filter.py` | PESEL z sumą kontrolną = blokada; telefon, e-mail, adres = komentarz czeka na sprawdzenie (dotyczy komentarza autora i komentarzy pod parą). |
| `moderation.py` | Zgłoszenia przypięcia, boxa i komentarza (7 kategorii, SLA 24/72 h), decyzja z uzasadnieniem (DSA art. 17), kolejka (zgłoszenia, odwołania, adresy, komentarze wstrzymane, boxy oczekujące), apelacja (jedna, 14 dni), sankcje. |
| `metrics.py` | Metryki 4.1-4.11 z agregatów ocen i komentarzy, alarmy (w tym brigading: > 50% ocen z kont < 7 dni). |
| `throttles.py` | 120/min ściana, 30/min szukaj i related, 60/min odczyt komentarzy, 10/min POST boxes, 30/min oceny i "przydatny", 10/min zapis komentarzy, 10/h zgłoszenia. |
| `sso.py`, `feeds.py`, `management/commands/` | Bez zmian względem v1. |

## API (prefiks `/api/spina3/`)
Odczyt: GET `config/`, `silence/`, `wall/`, `facets/`, `boxes/search/?q=`, `box/{id}/` (box, `pin`, `can_pin`, `can_rate`, `question`),
`box/{id}/related/`, `box/{id}/comments/?sort=newest|top&cursor=&limit=`, RSS `feed/*.xml`.
Autor: POST `boxes/` (`{box: {kind, target, title?, type?}, pin: {kind, target, comment?, stance?}}`; 201; 409 `has_pin`/`self`/`frozen`; 423; 429),
PATCH/DELETE `pin/{id}/`, POST `pin/{id}/appeal/`.
Oceny: PUT/DELETE `pin/{id}/rating/` (`{stance: agree|disagree}`).
Komentarze: POST `box/{id}/comments/` (`{text, parent?}`), PATCH/DELETE `comment/{id}/`, PUT/DELETE `comment/{id}/helpful/`, POST `comment/{id}/appeal/`.
Konto: GET `me/boxes/`, `me/ratings/`, GET/PATCH `me/profile/` (`nick_color`), POST `me/consent/`, POST `report/` (`pin` | `box` | `comment`).
Zespół: GET `moderation/queue/`, POST `moderation/reports/{id}/`, `moderation/appeals/{id}/`, `moderation/urls/{id}/`, `moderation/pins/{id}/`,
`moderation/comments/{id}/`, GET `moderation/metrics/`. Auth: POST `auth/exchange/`, `auth/refresh/`, `auth/logout-everywhere/`.
Usunięte z v1: POST `box/{id}/pin/`, GET `me/pins/`. Schemat: `docs/SPINA3_OPENAPI.yaml`.

## Model oceny (wersja wzoru 2.0)
S = suma(ocena x waga) / (n_w + 3), ocena +1 / -1, waga = waga konta / rozmiar klastra (zespół 0). Poziom z `level_raw` (histereza 0,04)
przycięty do P4/P2 przy n_w < 8; Otwarta przy n_w < 3 (`hold_new_accounts`, gdy n surowe >= 3); okno otwarte 6 h od pierwszej oceny;
najwyżej jeden stopień na 24 h. Stanowisko autora w przypięciu NIE liczy się do S. Kolejność ściany: sekcje P5..P1, w sekcji ostatnia
ZAUFANA ocena malejąco, potem n, potem id; Otwarta na końcu. Domyślnie "najnowsze" do 10% boxów z poziomem; cisza wyborcza wymusza "najnowsze"
i szarą spinkę.

## Testy
```
cd backend
USE_SQLITE=true SKIP_DOTENV=1 python -m pytest -q -W ignore -p no:cacheprovider spina3
```
143 testy (model i symulacje na ocenach dwustanowych, ograniczenia bazy, boxy z przypięciem, oceny, komentarze, ściana i kursor przy 50 ocenach
w trakcie, importer, kolejka URL, moderacja z komentarzami, SSO, OpenAPI). `python manage.py makemigrations --check`: bez zmian.
Migracje: `0001_initial`, `0002_v2_ratings_comments`.

## Zadania okresowe (cron na VPS, po wdrożeniu)
```
*/10 * * * *  docker compose ... exec -T backend python manage.py spina3_snapshot
*/15 * * * *  docker compose ... exec -T backend python manage.py spina3_sync
0 6 * * 1     docker compose ... exec -T backend python manage.py spina3_metrics --days 7 >> /srv/backups/spina3-metrics.log
```

## spin.clinic: sekcja spinek
Bez zmian: `THREADS_ENABLED=false`, `/spinki`, `/nitki`, `/tropy` -> 307 `/klinika` (frontend, `lib/threadsRouting.js`). Dane zostają.
Archiwum dotychczasowych spinek: `python manage.py export_spinki_archive --eksport /tmp/spinki-archive-<data>`. Brak automatycznego importu.


## Zmiany kontraktu 14.10

S1: etap 0 „czytnik” i przygotowanie etapu 1. Migracje: `0003_contract_20261014` (pola przypięć i zgłoszeń, rodzaj `interview`) oraz
`0004_nick_colors_front` (dane kolorów nicków). Migracja kolorów jest stratna: cofnięcie nie odtwarza poprzednich identyfikatorów.

- `Pin.title`: opcjonalne, puste albo 15-80 znaków; `subtitle`: opcjonalne, do 160. Tworzenie i PATCH walidują długości.
  Oba pola są w `PinOut` i `PinSummaryOut`. `comment` pozostaje niezależny (do 280); backend nie łączy pól przez nową linię.
  Diagnozy zachowują dotychczasowy tytuł systemowy `diagnosis_title`. Anonimizacja usuwa też tezę i podtytuł użytkownika.
- Kafelek ma `pin.target = {box_id, title, kind, subtype, status}` bez pełnego boxa. Dla celu z bazy `kind` i `subtype` opisują materiał;
  dla `url`/`image`: `box_id=null`, `kind=url|image`, `subtype=""`, `title=pin.title` (także przed weryfikacją).
  `target_title`, `target_box_id`, `target_status` pozostają na jedną wersję jako `deprecated`.
- Kolory P5/P4/P3/P2/P1/open: `#62E8A3`, `#8BBF48`, `#D49A33`, `#E07A3C`, `#E45A5A`, `#8E959E`.
  Nicki: lila, wrzos, fuksja, roz, brzoskwinia, piasek, cytryna, pistacja (hexy frontu). Domyślnie `piasek`; `spin` nadal zarezerwowany.
  Migracja: lilac->lila, plum->wrzos, rose->fuksja, coral->roz, amber->brzoskwinia, sand->piasek, olive->cytryna,
  moss->pistacja, ash->piasek, slate->lila, teal->pistacja. Puste ustawienie i `spin` pozostają bez zmian.
- `GET config/`: `csrf_token` do `X-CSRFToken`, odpowiedź `Cache-Control: no-store`.
- `config/` i `silence/`: `election_silence = {active, start, end, pause: {user_pins, ratings, comments}}`.
  Daty są ISO albo null; `pause` zawiera flagi konfiguracji (obowiązują podczas `active=true`). Stare płaskie pola znikają z odpowiedzi,
  także z `config.flags`. W kodzie istnieją w `Flags` (nie w `ScoringConfig`), pozostawione bez zmian wraz z wewnętrznym stanem blokad.
- Gość: `GET me/profile/` zwraca 200 `{nick: null, anonymous: true, consent: false}`. Pozostałe operacje konta wymagają logowania.
- `GET me/boxes/`: `{items: [BoxItemOut]}`; `GET me/ratings/`: `{items: [{box_id, pin_id, stance, created_at, box}]}`.
  Usunięto poprzednie opakowania elementów; oceny i boxy są widoczne wyłącznie dla właściciela konta.
- OpenAPI wymienia wszystkie rodzaje boxów, w tym dodany `interview` i istniejący zarezerwowany `image`.
  `subtype` pozostaje otwartym słownikiem do 32 znaków: źródła nie definiują zamkniętej listy podtypów.
- Box z linku czytelnika bez daty źródła otrzymuje datę przypięcia. Akceptacja dowodu URL używa daty najwcześniejszego przypięcia
  (bez przypięcia: data zgłoszenia URL). Serializacja istniejącej kotwicy bez daty używa jej przypięcia; data źródła ma pierwszeństwo.
- Zgłoszenie: wymagane `name` (do 200), `email` (walidowany, do 254) i `good_faith=true` (brak/false: 400 z `code=good_faith`);
  opcjonalne `location` (URL do 2048) i `explanation` (do 2000). Dane zapisane wyłącznie w `Report`, poza odpowiedziami publicznymi.
  Historyczne zgłoszenia dostają puste dane i `good_faith=false`, bez domniemywania dawnego oświadczenia.

Zakres S1 nie obejmuje wysyłki potwierdzeń i decyzji e-mailem, nowych reguł ciszy dla kandydatów, wdrożenia ani zmian frontu/SSO.

Weryfikacja S1: `python -m pytest spina3/tests -q -p no:cacheprovider`: **179 passed**, 92 ostrzeżenia (deprecjacje Django/Python
oraz brak katalogu staticfiles), 118,30 s. Uruchomienie offline z `SKIP_DOTENV=1`, `USE_SQLITE=true`, `SQLITE_DATABASE_PATH=:memory:`.
`python manage.py makemigrations --check --dry-run spina3`: brak zmian. YAML porównywany w teście z generowanym schematem.
Kontrola diff: bez błędów białych znaków i uszkodzeń kodowania. Bez commitów, push i wdrożenia.
