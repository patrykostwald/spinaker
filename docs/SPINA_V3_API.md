# Spina v3: dane dla nowego wyglądu (ciąg przyczyn, siła spinu dnia, głosowania, powiązania)

Stan: 13.10.2026, gałąź `claude/redesign-v3`. Kod: `backend/news/causal_chain.py`, `backend/news/przeszlosc_v3.py`,
modele `CausalChain` i `CausalChainEvent` (`news/clinic_models.py`, migracja `0161_causal_chain_v3`), testy
`backend/news/test_spina_v3.py`. Pełne przykłady JSON: kontrakt `zbudujmi/gust/spin/port/API-v3.md`.

## Flagi (domyślnie wyłączone)

| Zmienna | Skutek |
|---|---|
| `CAUSAL_CHAIN_ENABLED` | przekaz dnia dostaje klucz `causal_chain` (zatwierdzony łańcuch albo `null`) |
| `PRZEKAZ_SPIN_STRENGTH_ENABLED` | przekaz dnia dostaje klucz `spin_strength` (`{value, n, method}` albo `null`) |
| `ELECTION_SILENCE` | cisza wyborcza: `causal_chain` zawsze `null`, bez generowania i zatwierdzania (API 423) |
| `PRZESZLOSC_VOTES_LIST_ENABLED` | `GET /api/przeszlosc/glosowania/` (oraz `PRZESZLOSC_ENABLED=true`) |
| `PRZESZLOSC_NETWORK_ENABLED` | `GET /api/przeszlosc/osoba/<ident>/powiazania/` (oraz `PRZESZLOSC_ENABLED=true`) |
| `POSITION_PAIRS_ENABLED` | „Wcześniej i teraz”: klucz `position_pairs` w profilu osoby i diagnozie, `/stanowiska/`, zgłoszenia, powiadomienia |

`ELECTION_SILENCE` ukrywa także pary „Wcześniej i teraz” (`items: []`, `paused: true`) i wstrzymuje ich zatwierdzanie.

Wyłączona flaga = odpowiedź bez nowego klucza (identyczna jak przed v3) albo 404 dla nowych ścieżek.

## Siła spinu dnia - stała definicja

`spin_strength.value` = mediana pola `SpinDiagnosis.intensity` (wynik Konsylium: mediana ocen członków, `clinic_council.combine`)
z diagnoz, które spełniają wszystkie warunki:
1. dotyczą wpisów cytowanych w przekazie (`ClinicDailyMessage.posts`);
2. są opublikowane (`clinic.published_diagnoses()`: zatwierdzone, niewycofane, nieukryte, wpis dostępny);
3. mają werdykt `spin`, `partial` albo `no_spin` (bez „nie da się ocenić”).

Minimum 3 takie diagnozy, inaczej `null`. Przy parzystej liczbie: średnia dwóch środkowych zaokrąglona w górę od 0,5.
`n` = liczba diagnoz w medianie; `method` = opis słowny tej reguły. Ta sama reguła dla każdej strony; to miara nasilenia
technik perswazji we wpisach przekazu, nie procent fałszu i nie ocena strony.

## Ciąg przyczyn „Dr Spin wyjaśnia”

Kroki: `{kind: fakt|interpretacja|spin|wniosek, text, source?{name,url,date}, technique?, degraded?}`, 3-5 kroków.

Walidator w kodzie (`causal_chain.validate_steps`, czysta funkcja):
- materiały = wpisy przekazu i linki w nich (`causal_chain.materials`); tylko one mogą być źródłem faktu;
- `fakt`: źródło wskazane identyfikatorem materiału albo adresem; nazwa, adres i data zawsze z materiału, nie z modelu;
  bez źródła - krok zostaje jako `interpretacja` z `degraded: true`;
- usuwany jest krok: z liczbą spoza materiałów, z cytatem spoza materiałów, z zarzutem (słownik `clinic_plain.ACCUSATIONS`),
  który nie padł w materiałach, z przypisaniem intencji (poza faktem), z wykrzyknikiem lub pytajnikiem, emotikoną, adresem,
  dłuższy niż 160 znaków; długi myślnik zamieniany na krótki;
- mniej niż 3 kroki albo brak faktu ze źródłem = łańcuch `failed` (nigdy publiczny);
- `technique` tylko z kanonicznej listy (`techniques.canonical_technique`, bez „Inne”).

Bramki (`CausalChain.gates`): `walidator`, `fact_checker`, `prawnik`, `jezykoznawca` (deterministyczne, status `pass|fixed|fail`
z listą zmian) oraz `przeglad` - modele w rolach Fact-checker, Prawnik, Językoznawca z `report_roles.ROLES`
(darmowa ścieżka `agents_common.ask_any`); decyzja inna niż `publish` albo uwaga krytyczna = `blocked`.

Statusy: `pending_review` (do zatwierdzenia), `approved`, `rejected`, `failed`. Publicznie tylko `approved` z `approved_at`.

### Procedura zatwierdzania
1. Generowanie (darmowe modele; nie startuje samo z harmonogramu):
   `python manage.py lancuch_przekazu generuj --dzien 2026-10-12 [--oboz government] [--bez-przegladu]`.
2. Przegląd: `python manage.py lancuch_przekazu lista` i `... pokaz <id>` albo admin Django „Ciągi przyczyn przekazów”.
3. Decyzja człowieka (konto `is_staff`), bez edycji kroków:
   - `python manage.py lancuch_przekazu zatwierdz <id> --kto <login> [--uwaga "..."]`;
   - przy `przeglad: blocked` tylko z uzasadnieniem: `--mimo-uwag --uwaga "..."`;
   - `python manage.py lancuch_przekazu odrzuc <id> --kto <login> --uwaga "..."`;
   - albo `POST /api/staff/clinic/messages/<message_id>/causal-chain/review/` `{"decision","note","override"}`,
     albo akcje w adminie.
4. Zatwierdzenie i odrzucenie czyszczą cache `/api/clinic/`. Odrzucenie zatwierdzonego łańcucha zdejmuje go z API.

### Dziennik (AI Act art. 50, przejrzystość)
`CausalChainEvent`: `generated`, `failed`, `reviewed`, `approved`, `rejected` z czasem, osobą, modelem, wersją promptu
(`causal_chain.PROMPT_VERSION = 'chain-1'`) i szczegółami (bramki, uzasadnienie, override). Surowa odpowiedź modelu
i lista materiałów w `CausalChain.usage`. Publicznie: `ai_generated: true`, `model`, `prompt_version`, `notice`.

## przeszłość.today

### `GET /api/przeszlosc/glosowania/`
Parametry: `kadencja`, `klub`, `od`, `do`, `wynik` (`przyjete|odrzucone|nieustalone`), `q` (min. 3 znaki), `strona`,
`na_strone` (1-50, domyślnie 20). Wynik: `results`, `total`, `page`, `pages`, `per_page`, `filter`, `clubs`, `coverage`.
`outcome` z `counts.yes >= counts.majorityVotes` (dane API Sejmu); bez wymaganej większości - `nieustalone`.
`coverage.complete = false`: lista obejmuje tylko głosowania zaimportowane do bazy. Nagłówek `Cache-Control: public, max-age=300`,
gzip; `clubs` i `coverage` w cache serwera 1 h (PostgreSQL).

### `GET /api/przeszlosc/osoba/<ident>/powiazania/`
Graf `{person, nodes, edges, coverage, note, access}` z istniejących mianowników profilu (`co_occurrence`, `shared_krs`,
`vote_alignment`, cache `cached_person`). Krawędzie `wspolwystepowanie`, `krs`, `glosowania` z dowodami (link do źródła).
Bramka Pro `denominators` (403 przy zamkniętej), `Cache-Control: private, max-age=300`.

## „Wcześniej i teraz” (zmiana stanowiska, bez ocen)

Kod: `backend/news/position_pairs.py`, modele `PositionPair`, `PositionPairEvent`, `PositionPairReport` (migracja `0162_position_pairs_v3`),
komenda `pary_stanowisk`, testy `backend/news/test_position_pairs.py`. Kontrakt JSON: `API-v3.md`, sekcja 5.

Zasada naczelna: dwie wypowiedzi albo głosy tej samej osoby o tym samym temacie obok siebie, z datami i źródłami; wnioski wyciąga
czytelnik. Bez etykiet oceniających, bez liczników zmian i bez rankingów. Publicznie tylko pary zatwierdzone przez człowieka.

### Algorytm (identyczny dla każdej strony)
1. Materiały osoby wyłącznie po identyfikatorze: wpisy z kont X potwierdzonych przy osobie (`x_accounts`), wystąpienia i głosy
   imienne po oficjalnym identyfikatorze posła (`mp_identities`); nigdy po nazwisku.
2. Kandydaci (status „zgłoszona”, niepubliczni):
   - `pary_stanowisk generuj --z-petli`: pary z istniejącej pętli „Zmiana zdania” (`PositionCheck`, relacja zmiana stanowiska,
     pewność od 75, cytaty sprawdzone w obu tekstach) - bez nowych wywołań modeli;
   - `pary_stanowisk generuj --osoba <id> --temat "..."`: materiały z tematem (wszystkie 5-literowe początki słów tematu),
     dla 5 najnowszych (B) najbliższe tematycznie wcześniejsze (A, co najmniej 14 dni wcześniej); ocenę daje darmowy model z tym
     samym poleceniem co pętla Zmiana zdania (`zmiana_zdania.SYSTEM`), najwyżej 6 pytań; głosy porównywane z deklaracjami w obie strony;
   - `pary_stanowisk dodaj ...`: kandydat od człowieka z kluczy materiałów (`post:<id>`, `record:<id>`, `ballot:<id>`).
3. Walidator (`position_pairs.validate`, ten sam dla AI i człowieka):
   - obie strony to materiały tej osoby ze źródłem (nazwa, adres) i datą; A starsza od B o co najmniej 14 dni;
   - cytat dosłowny z materiału (12-280 znaków), głos = wynik z imiennego głosowania (`za`, `przeciw`, `wstrzymał się`);
   - odrzucenie: podanie dalej albo cytat cudzego wpisu (metadane X `retweeted`/`quoted`, tekst `RT @`/`rt @` także ze spacjami,
     „@konto: ...”, `via @konto`), wypowiedź warunkowa (jeśli, jeżeli, gdyby, o ile, chyba że, pod warunkiem) sprawdzana w całym
     zdaniu materiału, z którego pochodzi cytat (skrócony cytat nie omija warunku), znaczniki ironii ((sic), emotikony, `/s`) w całym
     materiale, dwa takie same głosy; odpowiedź na cudzy wpis (`replied_to`) to własna wypowiedź;
   - temat i kontekst opisowe: kontekst najwyżej jedno zdanie i 200 znaków, bez wykrzykników i pytań, bez słów z listy
     `EVALUATIVE` (m.in. hipokryzja, obłuda, kłamstwo, zdrada, wolta, zmiana frontu, niekonsekwencja, sprzeczność, nagle, znowu).
4. Kod nie zna partii ani obozu (sprawdzane testem `test_same_measure_for_both_sides`); `pary_stanowisk bilans` pokazuje
   personelowi liczby kandydatów i decyzji wg obozu kont - tylko do kontroli tej samej miary, nigdy publicznie.

### Decyzje, sprostowanie, dziennik
- Zatwierdzenie i odrzucenie: `pary_stanowisk zatwierdz|odrzuc <id> --kto <login> [--uwaga]` albo akcje w adminie
  („Pary stanowisk”); treść pary tylko do odczytu. Wycofanie zatwierdzonej pary z publicznym powodem: `pary_stanowisk wycofaj`.
- Uprawnienia: decyzje (zatwierdzenie, odrzucenie, wycofanie, rozpatrzenie zgłoszeń, weryfikacja zgłaszającego) wymagają
  `news.can_decide_positionpair`; decyzje o ciągu przyczyn `news.can_decide_causalchain` (komendy, akcje admina, API personelu).
  Sam `is_staff` nie wystarcza; uprawnienie nadaje superużytkownik w adminie (Użytkownicy albo Grupy).
- Para z wpisem niedostępnym na X nie może zostać zatwierdzona (błąd `unavailable`); para, której wpis zniknie później, nie jest
  pokazywana (jak diagnozy).

### Zgłoszenia błędów (procedura sprostowania)
- `POST /api/stanowiska/<id>/zgloszenie/`: powód min. 20 znaków, opcjonalny kontakt i `is_subject`; limit 5 na godzinę z adresu IP
  (także dla zalogowanych). Zapisujemy skrót IP z solą serwisu, nie sam adres.
- Każde zgłoszenie trafia do kolejki moderacji: `pary_stanowisk zgloszenia` (najpierw priorytet wysoki: zgłoszenie osoby
  zweryfikowanej albo z zaznaczeniem „dotyczy mnie”, potem najstarsze).
- Automatyczne zdjęcie z API (para wraca do statusu „zgłoszona”) tylko, gdy:
  1. zgłasza konto zweryfikowane przez personel jako osoba z pary albo jej przedstawiciel (`VerifiedReporter`,
     `pary_stanowisk zweryfikuj --login --osoba --rola --dowod --kto` albo admin „Zweryfikowani zgłaszający”), albo
  2. jest co najmniej `POSITION_PAIR_REPORT_THRESHOLD` (domyślnie 3) niezależnych zgłoszeń z kont w oknie
     `POSITION_PAIR_REPORT_WINDOW_HOURS` (domyślnie 24 h): każde z innego konta i innego skrótu IP. Zgłoszenia anonimowe idą do kolejki,
     ale nie liczą się do progu.
- W pozostałych przypadkach para zostaje widoczna z `review_pending: true` i neutralną notą „Do tej pary wpłynęło zgłoszenie.
  Czeka na przegląd.”.
- SLA (`POSITION_PAIR_REVIEW_SLA_HOURS`, domyślnie 48 h): człowiek z uprawnieniem rozpatruje każde zgłoszenie; priorytet wysoki
  najpóźniej następnego dnia roboczego. Decyzje: zostawić parę (`pary_stanowisk rozpatrz <id> --kto --uwaga`), wycofać ją z publicznym
  powodem (`wycofaj`) albo po zdjęciu zatwierdzić ponownie lub odrzucić. Odpowiedź do zgłaszającego i wpis w rejestrze korekt na razie
  ręcznie (do automatyzacji).
- Dziennik `PositionPairEvent`: `suggested`, `approved`, `rejected`, `withdrawn`, `reported` (z informacją: zweryfikowany,
  niezależne zgłoszenia, czy zdjęto), `reports_resolved`; kandydat AI ma `ai_suggested`, `model_name`, `prompt_version` (`pary-1`).
- Nagłówki: endpoint par i profil osoby przy włączonej fladze `Cache-Control: no-store`.

### Powiadomienia
Po zatwierdzeniu (flaga włączona, poza ciszą wyborczą) obserwujący osobę dostają `Notification` `kind="position_pair"`,
tytuł „Nowa wypowiedź różni się od wcześniejszej: zobacz obie”, adres profilu z kotwicą pary. Jedno powiadomienie na parę i osobę.

### Relacja do istniejącej „Zmiany zdania”
Blok `position_changes` w diagnozie (`zmiana_zdania.public_data`) działa jak dotąd: publikuje automatycznie po ocenie modelu.
Nowa funkcja wymaga decyzji człowieka. Czy wyłączyć stary blok po włączeniu `POSITION_PAIRS_ENABLED`, decyduje właściciel.

## Recenzja Fable 13.10 (prawo i produkt): zmiany

### Jedyna zmiana zachowania produkcji po wdrożeniu
`POSITION_CHANGES_LEGACY_ENABLED` (domyślnie `False`): stary automatyczny blok „Zmiana zdania” (`position_changes` w diagnozie,
`zmiana_zdania.public_data`) i linia w tekście na Facebooka (`social_line`) są wyłączone; w ciszy wyborczej wyłączone zawsze.
Pętla wyszukiwania kandydatów działa dalej niepublicznie. Przegląd dotychczas widocznych pozycji:
`pary_stanowisk stare` (lista) i `pary_stanowisk stare --przenies` (do kolejki „Wcześniej i teraz”, decyzja człowieka).
Pozostałe zmiany są za flagami domyślnie wyłączonymi albo dodają pola bez zmiany istniejących.

### „Wcześniej i teraz”
- Głos: `vote_target` (`całość`, `wniosek o odrzucenie`, `poprawka`, `inne`) z opisu głosowania, `vote_label` zgodny z przedmiotem
  (np. „za wnioskiem o odrzucenie projektu”), `vote_subject` z prefiksem typu. Para z głosem innym niż całość projektu wymaga
  `--potwierdzam-przedmiot` przy zatwierdzaniu.
- Nota: „Dwie wypowiedzi tej samej osoby o tym samym temacie z różnych dat. Zestawiamy je, bo według naszej metody stanowiska się
  różnią. Nie oceniamy powodów. Sprawdź oba źródła w całości.” Powiadomienie: „Nowe zestawienie wypowiedzi: {temat}”.
- Temat i kontekst obowiązkowe przy zatwierdzeniu (`--temat`, `--kontekst`); `context_source` (`ai`/`human`) i `context_note`
  publiczne. Temat tylko od człowieka albo z tytułu źródła (głosowanie, wystąpienie).
- Cztery oczy: zatwierdza inna osoba niż ta, która dodała kandydata.
- Zgłoszenia: „dotyczy mnie” z adresem e-mail dostaje link potwierdzający (48 h, `GET /api/stanowiska/zgloszenie/potwierdz/<token>/`).
  Potwierdzony adres z domen `POSITION_PAIR_OFFICIAL_DOMAINS` (sejm.gov.pl, senat.gov.pl, europarl.europa.eu, kprm.gov.pl,
  prezydent.pl; lista do przeglądu prawnika, domeny partii do dopisania) zdejmuje parę jak `VerifiedReporter`; inny potwierdzony
  adres daje priorytet wysoki i `review_pending`. `review_pending` tylko po zgłoszeniu zweryfikowanym (konto albo potwierdzony e-mail).
  Do progu liczą się konta starsze niż 7 dni. Odpowiedź e-mail z decyzją i powodem przy każdej decyzji. Retencja adresu: 90 dni
  po rozstrzygnięciu (`pary_stanowisk czysc-kontakty`, do harmonogramu).
- SLA: klasa A (osoba potwierdzona, przedstawiciel) i C (żądanie prawne) do 2 dni roboczych; klasa B (czytelnik) do 7 dni.
- Rejestr korekt przeszłości (`/api/przeszlosc/poprawki/`): wycofane pary jako `pair_withdrawal` z publicznym powodem.

### Ciąg przyczyn
- Override przeglądu tylko dla uwag Językoznawcy; uwagi krytyczne Fact-checkera i Prawnika = nowe wygenerowanie (`blocked_hard`).
- Kroki `interpretacja`, `spin`, `wniosek` bez imion, nazwisk (także odmienionych) i @kont osób z materiałów.
- Łańcuch znika z API, gdy którykolwiek wpis z jego materiałów zniknął z X.
- Zgłoszenie błędu: `POST /api/clinic/messages/<id>/causal-chain/zgloszenie/` (kolejka, bez automatycznego zdjęcia);
  `report_url` w łańcuchu. Odrzucenie opublikowanego łańcucha wymaga publicznego powodu (komenda, API, admin) i trafia do
  `/api/clinic/corrections/` jako `chain_withdrawal`.

### Graf powiązań i dane trzecie
- Węzeł tylko z identyfikatora: `figure:<id>` albo `mp:<kadencja>:<numer posła>`; poseł bez numeru nie jest pokazywany.
- Każda krawędź ma `evidence` albo `evidence_note` i `evidence_url` (sekcja profilu); krawędź głosowań ma `shared` i `window`.
- Wydatki posła (`open_data.mp_expenses`): `third_party`, `notice` („Dane z serwisu trzeciego, nie sprawdzono automatycznie...”),
  `source_label`, `source_url`, `primary_urls` (PDF Kancelarii Sejmu). Bez wskaźników pochodnych.

### Przełączniki i cisza wyborcza
`SiteFlag` (klucz, wartość, od, do, kto, kiedy) nadpisuje env bez restartu; dziennik `SiteFlagChange`; admin „Przełączniki v3”
i komenda `przelacznik`. Cisza wyborcza: `SiteFlag ELECTION_SILENCE` z oknem albo `ELECTION_SILENCE_FROM/UNTIL` w env.
Procedura: `docs/RUNBOOK_KILL_SWITCH.md`.

## Decyzje właściciela 13.10 (domeny, art. 14, odpowiedź osoby, oświadczenia, pilotaż)

### Domeny urzędowe i partyjne
Plik `backend/news/config/official_domains.json`: każda pozycja z rodzajem, źródłem, datą sprawdzenia i statusem
(`potwierdzona` albo `do potwierdzenia`; obie działają od razu). Env `POSITION_PAIR_OFFICIAL_DOMAINS` (gdy ustawiony) zastępuje
plik. Zmiany: `domeny_urzedowe dodaj|usun` (dziennik `OfficialDomainChange`, ostatni wpis wygrywa), `domeny_urzedowe lista`,
`domeny_urzedowe sprawdz [domena]` (DNS, MX gdy jest dnspython; bez wysyłania wiadomości). Dopasowanie po sufiksie domeny,
bez wielkości liter (`sejm.gov.pl` obejmuje poddomeny). Używane w ścieżce osoby (potwierdzony e-mail z domeny = zdjęcie pary).

### Klauzula art. 14 RODO i sprzeciw (SZKIC DO PRAWNIKA)
Flaga `PRZESZLOSC_PRIVACY_NOTICE_ENABLED` (domyślnie wyłączona). Profil osoby dostaje `privacy_notice`
(`version` `art14-szkic-1`, `date`, `status: szkic do prawnika`, `sections[{heading, text}]`, `objection_url`, `contact`).
Sprzeciw: `POST /api/przeszlosc/osoba/<ident>/sprzeciw/` `{reason (min. 20), contact (e-mail), relation: osoba|przedstawiciel|inna}`
-> 202, link potwierdzający (48 h, `GET /api/przeszlosc/sprzeciw/potwierdz/<token>/`); kolejka `sprzeciwy lista`, decyzja
`sprzeciwy rozpatrz <id> --decyzja uwzgledniony|odrzucony --uwaga --kto` z odpowiedzią e-mail. Bez automatycznego usuwania danych.
Do prawnika: podstawa (art. 6 ust. 1 lit. e/f, art. 85), okres przechowywania, treść sekcji.

### Odpowiedź osoby i powiadomienie o wycofaniu
`POST /api/stanowiska/<id>/odpowiedz/` `{text (10-600), token?}`: tylko konto `VerifiedReporter` tej osoby albo token
potwierdzonego zgłoszenia z domeny urzędowej; status `zgloszona` -> decyzja personelu z `can_decide_positionpair`
(`pary_stanowisk odpowiedzi`, `odpowiedz-opublikuj|odpowiedz-odrzuc <id>`). Publicznie w parze: `subject_response`
`{label: "Odpowiedź osoby", text, date}` albo `null`. Wycofanie pary: obserwujący, którzy dostali powiadomienie o parze,
dostają `kind: position_pair_withdrawn`, tytuł „Zestawienie wycofane: {temat}. Powód: {powód}”.

### Oświadczenia majątkowe posłów
Zbieracz indeksu już istniał (`scraper/public_records.py`, źródło `assets`, env `PUBLIC_RECORDS_ASSETS_ENABLED`): z profilu
posła na www.sejm.gov.pl zapisuje linki do PDF (rok, opis). Nowe (`news/asset_declarations.py`, flaga `ASSETS_DECLARATIONS_ENABLED`):
- `oswiadczenia synchronizuj`: indeks -> `AssetDeclaration` (rok, typ oświadczenie/korekta, data złożenia z opisu, poseł po
  numerze z Sejmu i kadencji);
- `oswiadczenia metadane --limit 20`: grzeczne pobranie tylko z www.sejm.gov.pl (opóźnienie `ASSETS_DECLARATIONS_DELAY_SECONDS`,
  domyślnie 5 s; ETag i If-Modified-Since; odświeżenie co 30 dni; limit 10 MB; najwyżej 200 na przebieg), suma kontrolna,
  rozmiar, liczba stron i obecność warstwy tekstu (bez OCR, bez odczytu kwot); PDF nie jest przechowywany;
- profil: `assets_declarations {items[{year, kind, kind_label, published_on, title, url, sha256, checked_at, auto_read}], notice,
  source, rights}`. Bez wskaźników pochodnych, porównań i ocen; ta sama procedura dla każdego posła.
Do prawnika: ponowne wykorzystanie informacji publicznej (jawność oświadczeń z ustawy o wykonywaniu mandatu), okres
przechowywania po wygaśnięciu mandatu, dane osób trzecich w oświadczeniach (małżonek) - pokazujemy tylko link i metadane.

### Pilotaż
`docs/PILOTAZ_V3.md`, komenda `pilotaz par|lancuch|raport`, moduł `news/pilotaz.py`.

## Miniatury kont X (13.10)
Diagnoza: zbieranie wpisów (x_watch, political_polling, nastroje, odbior_spinu) prosi tylko o `attachments.media_keys`, bez
`author_id`/`user.fields`, więc `PoliticalPost.author_data` nie ma `profile_image_url` i `avatar_url` w API był pusty.
Rozwiązanie bez zmian w zapytaniach zbierających: `news/x_avatars.py` i komenda `x_avatary odswiez [--limit 200] [--dry-run]
[--starsze-niz 30]`.
- Jedno wywołanie `GET https://api.x.com/2/users/by?usernames=...&user.fields=profile_image_url` na 100 kont, przez istniejące
  `political_polling.request_x` (stały host, bez przekierowań, limity rozmiaru i czasu).
- Budżet: ta sama rezerwacja co odczyty wpisów (`ImportState political-x-budget`): dzierżawa, dzienny limit zapytań,
  miesięczny limit USD; koszt `USER_PRICE` (0,010 USD) za każde zwrócone konto, rozliczany po odpowiedzi. Brak budżetu
  albo trwający odczyt = przerwanie z komunikatem, bez wywołania. ~170 kont = 2 wywołania, do 1,70 USD (przy domyślnym
  limicie 5 USD/mies. to istotna część - sprawdź `--dry-run`).
- Tożsamość: zapis tylko, gdy `id` z X = `PoliticalAccount.user_id`. Adres tylko `https://pbs.twimg.com/profile_images/...`,
  wariant `_bigger`. Konto odświeżane najwyżej co 30 dni (`avatar_checked_at`).
- API: `author.avatar_url` i `posts[].avatar_url` biorą najpierw `profile_image_url` z danych wpisu, potem `avatar_url` konta.
  Front ma już zastępcze inicjały.
- Harmonogram NIE jest włączony. Po zgodzie właściciela: w `backend/config/celery.py` (`app.conf.beat_schedule`) wpis
  `'x-avatars-weekly': {'task': 'news.tasks.x_avatars_task', 'schedule': crontab(day_of_week='sun', hour=4, minute=20)}`
  i zadanie w `news/tasks.py` wołające `x_avatars.refresh(limit=200)` (jedno wywołanie tygodniowo wystarcza: tylko konta
  starsze niż 30 dni).
- Do prawnika: regulamin X (Developer Agreement) a wyświetlanie miniatur z pbs.twimg.com (hotlinking) i ich odświeżanie;
  adresy miniatur wygasają po zmianie zdjęcia (odświeżenie co 30 dni, front pokazuje inicjały przy błędzie obrazka).
