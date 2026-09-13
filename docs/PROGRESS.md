# Stan pracy — aktualizacja 9 września 2026

## PAUZA rozbudowy bazy — 2026-09-09 20:46 UTC

Aktualizacja końcowa: regionalne raporty media-discovery-regional-2026-09-09.csv/json/md zapisane:276wierszy,273hosty,183nowehosty tylko w raporcie (bez wpisówSource),103wierszeRSS z niedawną publikacją. Żaden nowyimport nieuruchomiony. Trzypropozycjebrandingu są w reports/branding-2026-09-09/grafit-mineralny.png, archiwum-bursztynowe.png, atrament-stalowy.png; rootobejrzał. Rekomendowanygrafit+teal. To koncepcjeImageGen, niezmieniony live; bursztynowamakieta ma omyłkowe godziny w pustejośi —nieprzenosić ich jako danych. Palety/kontrasty i weryfikacjafontów JSON oraz3fonty/licencje zapisanewtymfolderze. Raporttekstowydomykaagent.

**Najnowsza decyzja użytkownika: oszczędzamy pozostały limit na wygląd i branding. Nie wznawiać importerów/researchu źródeł automatycznie.** Scheduler sesja69207 zatrzymany Ctrl+C (exit1), automatyzacja `kontynuuj-mvp-spin-clinic` ustawiona PAUSED. Dwaj agenci bazy zakończyli; wyłącznie agent verify_new_sources domyka3propozycje brandingu bez zmiany live. Limit odczytany94%zużycia, reset16września2026 14:33Europe/Warsaw. Nie utożsamiać limituAI z pracą niezależnego procesu pobierającego.

Zapisane117828Article,114053z datą,91548z URLminiatury;314Source,93aktywne,57,62GBwolne. Katalog krajowy181wierszy,163nowych NIEAKTYWNYCH kandydatów; raporty media-discovery-national-2026-09-09. Regionalnyresearch zapisuje checkpoint bez nowych fetchy/importów. ZeroSource150 i Republika151 aktywne; RSSniepotwierdzony,mapy potwierdzone,piloty realne. Przywrócono37/73/74/75 dokładnie do poprzednich ustawień, raport restored-sources-2026-09-09.json.

Aktualny livebuild (~20:22UTC) ma konta/profile/opinie/permalink, migracje0024/25 zastosowane po verifiedbackup `.local/backups/portal-20260909T201834449924Z.sqlite3`.105testówbackendPASS; izolowany E2Ekont13scenariuszyPASS; realnybrowserdesktop/mobile/permalinkPASS20:26, reports/portal-mvp-browser.json. To zastępuje starsze informacje o nieukończonych migracjach i crashu twitter-text.

**Zmiany zapisane PO livebuildzie, jeszcze niewdrożone:** Dialogreset scroll; ArticleOpinions po licznikach przed chronologią; placeholder5personalizowanychboxów; largerfixedanchor redakcyjny/sponsor; ciemnytealbutton; DailyTopicStrip/TopicArchiveStrip/EmptyNarrativeStrip. Frontendagent typecheckPASS przed ostatnimi rootzmianami. Root dodał daily_topic.py+URL portal/topic-of-day, ograniczony wybór zTOP10 ostatnie24h, API jawniepokazuje7/10źródeł; literalnepublisher tagi/nazwy nagłówków, NIE AI ani ręczne tematywydawców. Ranking wymaga dalszego dopracowania (obecny wynik infleksyjny Mazowszu zbyt szeroki), braktestówdaily_topic; portal.feed otrzymał opcjęmatch=words i frontendtopicjej używa (jeszcze NIE testowane). Nie deklarować tego jako zakończonego/produkcyjnego.

**Niewdrożony patchimporterów:** scraper/news_sitemaps.py+test_news_sitemaps.py; archive.py verified sitemap fallback i priorytet10freshmaps; run_local_jobsdispatcher60s wedługźródłafrequency. Agent81/82testówPASS, jedenfail test_archive_host_gate_covers_robots_and_fetch: pierwszy guard process używa job.kind na mocku bezkind, należyzastosowaćgetattr(job,'kind',None). Poprawka i ponowne właściwetesty przywznowieniu, nie restartowaćnowegoschedulera przednimi. Brak migracji.

Branding: user chce3stonowane darkkierunki,2–3fontyPL,logo,małoram/ruchpomagającyczytać. Kolorobecnyróżowawyodrzuca. TrzyImageGenmocki wygenerowane przezverify_new_sources; raporti kontrasty domyka do reports/branding-2026-09-09. Nie wdrażaćmotywu przedwyborem usera. Strona nadal localhost3000, panelźródeł /editor/sources. Klucze internetowegoAI/X nadalniepodłączone.

## Aktualny zakres i prace — 2026-09-09 20:15 UTC

**Obowiązujący plan: docs/MVP_CURRENT.md.** Zastępuje starsze decyzje poniżej: konta publiczne od startu, personalizacja tematów/źródeł/typów, prywatne ulubione i opcjonalnie publiczna historia; reakcja pozytywna/negatywna z opcjonalnym jednokrotnym komentarzem. Zwykły użytkownik nie tworzy nitek. Dziennikarz z uprawnieniami przyznanymi przez redakcję tworzy własne szkice. Redakcja publikuje dwie nitki marki **spin.clinic** (nazwa Dr Spin usuwana z UI) i może jedną sponsorowaną, zawsze oznaczoną. Nie generować fikcyjnych politycznych wypowiedzi, kont, komentarzy lub sponsorów. Udostępniany box ma permalink /material/[id] z oryginalnym źródłem i kontekstem. Eksport tekstów do X; brak automatycznego OAuth-publikowania.

Pierwszy nowy build/home działa z prawdziwą bazą, ale test wykrył crash parsera twitter-text w modalu; poprawka xText i dat unknown/undated czeka na kolejny build z rozszerzeniem profili. Frontend agent verify_new_sources kończy spójny punkt; nie uruchamiać builda podczas przejściowych importów brakujących komponentów. Root prowadzi realny read-only test wizualizacji .local/verify-portal-layout.cjs; agent robi mutacje kont wyłącznie na osobnym backendzie i SQLite port8001. Nie przedstawiać obecnego nieukończonego testu jako PASS.

Backend: 0021 (tags/genres/editorial_slot), 0022 (public accounts), 0023 (political intake) już zastosowano po kopii `.local/backups/portal-20260909T195404975373Z.sqlite3` (integrity_check PASS). 0024_profiles_topics_favorites i 0025_journalist_threads_sponsorship jeszcze czekają na root, po testach/backup. 29 testów accounts/profile/portal przechodzi; publisher genre/metadata29PASS; visibility1PASS; political21PASS. Zestawy się częściowo nakładają — nie sumować bez wspólnego uruchomienia.

Jedyny scheduler **sesja 96111**, ARCHIVE_WORKERS=32, od około19:55UTC; wcześniejsza12793 zatrzymana. Aktywne poprawki: quality1000/min z budżetem5s i małymi transakcjami; katalogi Polityka/Niebezpiecznik/Nowiny; fallback niekompletnego rekordu Liberté; WordPress archiwa. Root później dodał publisher articleSection/OGsection do tags — wejdzie po następnym restarcie. Aktualny X political job jest jawnie disabled (brak konfiguracji), nie wykonywał płatnych prób. Nie dublować schedulera.

Pomiar20:09:20UTC: **102459 Article**,99342 z datą,78461 z adresem miniatury;149 wpisów Source,91 aktywnych. Heartbeat20:09:17 świeży. Ostatni archive cykl32aktywnych:578nowychArticle/113,22s,4błędy+10odroczeń; nie twierdzić, że wszystkie źródła działają. Quality1000/0,926s,900nowych+100rewizji,11usterekodnotowanych,niezmienianotreści. WordPress3źródła w trakcie+2ukończonesnapshoty; brak kompletności całego archiwum. Wolne61GB. Raport reports/portal-runtime-checkpoint-2026-09-09.json. Około4088Article ma źródłowe tagi, tematy nie są jeszcze uzupełnione całemu historycznemu zbiorowi.

Backendfeed/context: public latest/todayTOP10/editorialconfig oraz kontekst całej historii+gatunkowe liczniki. TOP10 to jawny wybór źródeł, nie ranking najważniejszych publikacji. TestyUnicode/ukrytesource/cache/distinctPASS. Przy97kArticle: feedlatest0,33–0,43s,top0,06–0,09s,kontekst cold0,91–2,60s,warm0,002s. Raport reports/portal-runtime-benchmark-2026-09-09.md. Ograniczenie wielokrotnychCOUNT do pojedynczejagregacji nie obcina historii.

Następne kroki root: skończyć role/testy; backup/migracje0024/25 i odświeżyć backend; zbudować gotowyfrontend i odświeżyć runtime; dokończyć browser E2E desktop/mobile/permalink oraz konta na osobnejbazie; obejrzeć screenshots; zapisać finalnycheckpoint i pokazaćdemo. Pełna produkcja nadal wymaga konfiguracji usług, ochrony/obsługi kont/moderacji/odzyskiwania i finalnego przeglądu kodu oraz bezpieczeństwa. Żywe internetowe AI i politicalX nadal niepodłączone.

## Końcowy checkpoint — 2026-09-09 18:43 UTC

Demo lokalne jest gotowe pod `http://localhost:3000/search`. Prawdziwa baza działa; dopływanie linków, późniejszą zamianę w boxy, anulowanie oraz zmianę hasła sprawdzono z odizolowaną symulacją dostawcy. Żywe wyszukiwanie AI wymaga jeszcze klucza, dostępnego modelu i salda API. Preflight o 18:41:12 potwierdził brak konfiguracji i zero płatnych prób. Nie przedstawiać symulacji jako uruchomionego AI. Po poprawnym podłączeniu konta przewidziano około 30–60 minut na pierwsze rzeczywiste próby; to szacunek zależny od dostępu dostawcy.

Import archiwów nadal działa z `ARCHIVE_WORKERS=32`. Aktualny, jedyny scheduler: sesja **12793**, uruchomiona około 18:42 UTC po zakończeniu sesji 37806. Świeży heartbeat: 18:42:35. Liczba rekordów Article o 18:42:43: **64 064**, nie liczba adresów oczekujących w kolejce. Publiczny licznik osobno wyklucza typy społecznościowe. Nie utożsamiać aktywnego procesu z poprawnością każdego źródła: ostatni ukończony cykl archiwum miał 570 nowych rekordów, 46 błędów i 10 odroczeń.

Końcowa poprawka `research_metadata_cycle` używa podzapytania priorytetowych ID i istniejącego indeksu. Bez migracji. Rzeczywisty SQL: 0,170 / 0,092 / 0,076 ms zamiast wcześniejszych 1,57–2,04 s; cały pusty cykl po restarcie około 3 ms. 13 testów helpera przeszło, w tym warunki lease, backoff i nieaktywnych źródeł. Raport: `reports/research-selector-performance-2026-09-09.json`. Pięć importerów WP działa, również naprawione Liberté; szczegóły i wcześniejsze pomiary poniżej.

Frontend i backend zostały odświeżone o 18:31, ostatnia zmiana selektora dotyczyła wyłącznie schedulera. Pozostawić sesję 12793 i istniejący heartbeat `kontynuuj-mvp-spin-clinic` aktywne. Nie uruchamiać duplikatów ani kolejnego zbędnego restartu. Kontynuować archiwa, dostępność źródeł i jakość; nie wykonywać płatnych prób bez lokalnie skonfigurowanego API. Instrukcja dla właściciela: `docs/AI_START_CHECKLIST_PL.md`; opis demo: `docs/LIVE_SEARCH_DEMO.md`.

## Najnowszy stan — 2026-09-09 18:33 UTC: demo hybrydowego wyszukiwania

Użytkownik zlecił dalszy ciągły import bazy oraz priorytetowe demo: jedno hasło/URL uruchamia bazę i internetowe AI, wyniki mają napływać. Nie czekamy na zakończenie archiwów. W komentarzu oszacowano 2–4h na demo z warunkiem konfiguracji API. Wersja lokalna została już zbudowana i sprawdzona. Pełne żywe wyszukiwanie AI nadal wymaga właściciela: klucz, saldo i wybór dostępnego modelu Responses/web_search. Preflight 18:32:54: brak konfiguracji, 81 dozwolonych domen, 0 płatnych wywołań, provider_access_tested=false. Nie przedstawiać mocków jako działania live AI. Szczegóły: docs/LIVE_SEARCH_DEMO.md i docs/AI_START_CHECKLIST_PL.md.

Backend: POST /api/ai/research/stream/ prawdziwe SSE, provider stream:true, progress→sources→result→metadata→done. Tylko tool-reported URL ze znanych źródeł, tekst po weryfikacji cytowań; brak publikowania tokenów modelu jako faktów. Dotychczasowy endpoint zachowany, verify staff-only. Trwały UUID zapobiega podwójnemu kosztowi przyjęcia tej samej próby; brak autoretry płatnych requestów. Wspólny limit20/dzieńUTC, max4toolcalls/4000tokens, max30URL, szkicmax15. Read-only POST /api/ai/research/sources/ odczytuje do30URL bez providerbudget (limit240/h anon,480/h user dopasowany do krótkich sesji pollingu). Timeout100s, rozłączenia i audyt tokenów/usage. Niewiadome metryki null. WSGI teraz; ASGI wymaga adaptacji. Nextproxy130s zamiast30.

SourceRegistry w external_search zachowuje wszystkich wydawców wspólnej domeny; APIallowed_domains nadalunikalnehosty. match_source dla gov.pl wymaga poprawnego /web/{instytucja}, nie przypisuje dowolnego dokumentu ostatniemu wpisowi słownika. Unknown/ambiguous odrzucone. archive_result kontroluje Source względem konkretnegoURL oraz source_id. Nie zmieniono istniejących rekordów źródeł. Ewentualny audyt wcześniejszej tożsamości danych to osobne zadanie.

Frontend: jeden input w nagłówku, SearchPage wspólna sesjaAI i lokalne wyniki. Linki bezmetadanych jawnieosobno, potem scalanie z kartami bazy wgID i datyEurope/Warsaw, filtrykategorii/dat. Cytowanerekordy z datami składają się na kontekstdo15 od najstarszego. Zatrzymanie/zmianaquerychroniprzedstarymiodpowiedziami. Pollsourcesco5smax150s; lokalnycache5s i pierwszastronapoll5s w aktywnejkarcie, starszerozwiniętestronybezautorefreshcałości. Brave opcjonalne, ukrytejeślinieskonfigurowane; niepotrzebnedoResponses. Publiczny /api/archive/status/ pokazujeprawdziwąliczbęmateriałówiaktywnychźródeł orazświeżyheartbeat, kompletność=false. „Największa”niejestprzedstawianajakofakt.

Szybki odczyt metadata: news/research_metadata.py, maks3workers/15URL/20sczekania. Web session domyślnie allow_fetch=False, tylkokolejka+DB. research_metadata_cycle jest zadaniem w istniejącym run_local_jobs co10s (tick10s) — wspólnehost_state zarchive iWP, bezkonkurencyjnego crawleraweb. DNS/robots/limity/lease i Source ponowniesprawdzane, zapisySQLitekrótkoserializowane, brakpóźnegoArticlezapisu podeadline. SameaktywnerequestyHTTPmogąsiędokończyć (jawneograniczenie). Parseryczne błędy/sources bezdat pozostająjawne. Rzeczywisty odczyt1PolsatNews na osobnejtestSQLite:3.25s,poprawnyArticle/jobdone/0webfetch; reports/research-metadata-live-check-2026-09-09.json.

Nowy importer WP `scraper/wordpress_backfill.py` obsługuje pięć potwierdzonych źródeł (wcześniejszy spis: 50 547 publicznych postów). Strony po 100/99 rekordów mają kotwicę ID, zamrożoną górną granicę i wykrywanie przesunięć; import zachowuje źródłową datę GMT i sprawdza identyfikator miniatury. Zapisuje tylko metadane. Zadanie `wordpress-history` działa co 60 sekund. Poprawka projekcji Liberté została potwierdzona: 18:34:13 pierwsze 100 rekordów, przesunięty kursor, wyzerowany błąd; nowy materiał znaleziony w wyszukiwarce. Łącznie o 18:34:51 te importery zapisały 3965 rekordów, wszystkie z datą, 2541 z miniaturą, bez treści artykułów. O 18:40:28 kolejny cykl wszystkich pięciu źródeł zakończył się poprawnie (+495 rekordów). Raporty: `reports/wordpress-backfill-2026-09-09.md` i `reports/wordpress-backfill-pilot-2026-09-09.json`. Dane historycznego spisu nie oznaczają kompletności archiwów wydawców.

Testy: NextproductionbuildPASS; browserdesktop/mobilePASS, bezpageerrors/overflow; prawdziwalocalsearch +izolowanymockproviderstaggeredUTF8SSE/link→box/stop/zmianaquery/jedenrequest. reports/live-search-browser.json orazhome/desktop/mobilepng. Backend52targetedPASS (local/search/AI/metadata), później49WP+SSE+metadata i15registry/SSE; to nakładające sięzestawy, niesumowaćjakołącznejliczbyunikalnej. Agenci dodatkowotestyWP/queue/probe. Narzędzieagent-browserCLI nieobecne; weryfikacjaprzezbundledPlaywrightEdgeheadless. .local/verify-live-search.cjs bez DBmutacji/paidcalls.

Uruchomienia: wcześniejszy scheduler8375→79937→obecny37806 od18:30UTC, ARCHIVE_WORKERS32. 18:29 ostatniacykl32aktywnych/41eligible:563noweArticle/573strony/122.62s,59błędówźródeł+8odroczeń jawne (nie wszystkieimportyzdrowe). 18:31:55publiccounter56866,91aktywnychźródeł, heartbeat18:31:48świeży. To gotoweArticle, nie3mlnURLqueue. Backend/frontendodświeżone18:31, dokładnePIDsprawdzaćnetstat; obecnego scheduleranie dublować. Credentials.local/admin-login.txt nigdy nie ujawniać. Heartbeat kontynuuj-mvp-spin-clinic nadalACTIVEco30min, korzystaztegozapisu. Kontynuowaćarchiwa/metadatę/jakość/źródła; liveAIpilotdopieropokonfiguracji. Nie obiecywaćpracybezuruchomionegoprocesu.

Starsze sekcje poniżej są historyczne; nie cofają powyższej decyzji ani aktualnego limitu32.

## Ustalenia użytkownika
- Kontynuować samodzielnie aż użytkownik wróci rano (około 8–10 h od 00:19 UTC). Nie pytać o rutynowe zgody. Blokady kont, płatności i wymagane zatwierdzenia zebrać na koniec. Nie obchodzić ograniczeń.
- Jeden portal spin.clinic, jedna baza. Wszystko bezpłatne. Brak sztucznych danych i nitek demonstracyjnych.
- Główny UI to poziome paski-nitki z boxami. Wyniki wyszukiwania: paski dat od najnowszej, wewnątrz poziome boxy.
- Tylko zalogowany administrator tworzy nitki; przyszłe konta publiczne i głosowanie odłożone.
- Box dodawany z bazy albo po URL (automatyczne metadane do zatwierdzenia).
- Oficjalne głosowania imienne Sejmu, ustawy, obwieszczenia, dokumenty w bazie. Zapytania temat + poseł mają odnajdywać właściwe głosowania. Powiązania firma–ustawa muszą mieć źródło, a głos YES zawsze dotyczy dokładnego wniosku, np. odrzucenia weta.
- Bannerek zachęcający do współtworzenia w przyszłości. Docelowa prezentacja-film na później.
- AI: teraz przygotować fundament, nie wdrażać publicznego automatycznego fact-checkera; w przyszłości szkice RAG dla admina z dowodami i przeglądem człowieka.
- Harmonogramów nie zmniejszać: GDELT co 2 h, media RSS co 1 h, instytucje co 4 h, X co 2 h, NewsAPI 6:30/12:30/18:00. Zewnętrzne klucze nie podane. Nie kupować bez konkretnej decyzji.

## Ukończone
- Django modele, 5 migracji, wyszukiwanie, szczegóły, redakcyjne API tworzenia i edycji, logowanie sesyjne z CSRF, źródła manualne.
- 29 testów backendu przechodziło przed dodaniem oficjalnych danych.
- PostgreSQL GIN simple dla tytułu (brak domyślnego polskiego stemmera), SQLite do lokalnych testów.
- Premium usunięte z aktualnego modelu i UI, domeny już nie filtrują nitek.
- Kategorie rozszerzone, daty nieznane pozostają null. GDELT seendate = discovered_at, nie published_date. Brak daty lub strefy nie jest zastępowany bieżącym czasem.
- RSS/NewsAPI/GDELT/X importery; X rozwiązuje ID przez nazwę konta w oficjalnym API, paginuje, zachowuje kursor przy błędzie, ma limit kosztowy.
- PortalHome, paski dat, HorizontalTimeline, ArticleModal, ThreadEditor w packages/ui. frontend-spin główny, frontend-przeszlosc zachowany jako alternatywny brand, bez konieczności drugiego deployu.
- Tworzenie źródeł ręcznie działa, ale automatyczne metadane z URL jeszcze NIE zaimplementowane.
- Usunięty seed_demo. Baza nie była zasilana fikcyjnymi artykułami.
- Docker/Railway/Vercel częściowo naprawione; docs i README jeszcze STARE, wymagają ukończenia.
- Heartbeat utworzony: kontynuuj-mvp-spin-clinic, co 30 min. Wstrzymać, gdy użytkownik wróci. Nie tworzyć duplikatu.

## Najbliższa praca
1. URL metadata endpoint + frontend w kreatorze, bez zapisu przed potwierdzeniem.
2. Modele oficjalnego głosowania i głosów posłów + oficjalny importer Sejm, ELI DU/MP i dokumentów sejmowych, testy oraz czytelny widok w boxie/modal.
3. Wyszukiwanie wielowyrazowe, nazwiska i dowodowe powiązania tematów; żadnych wymyślonych relacji zondacrypto–ustawa.
4. Baner współtworzenia (bez fałszywego formularza kontaktowego lub wymyślonego adresu).
5. Dokumentacja, .env, status integracji, końcowe buildy i lokalny podgląd. Dokończyć testy dla zakresu.
6. Usunąć własne tymczasowe skrypty .update*.py/.pivot*.py itd. po zakończeniu. Nie usuwać plików użytkownika.

## Środowisko i pułapki
- cwd C:/Users/User/spin-clinic, PowerShell. Python .venv/Scripts/python.exe.
- ZAWSZE python -X utf8 i read_text(encoding='utf-8') / write_text(...,encoding='utf-8'). Domyślne CP1250 powodowało mojibake; naprawione skryptem .fix_encoding.py i rg.
- Node dostępny. pnpm C:/Users/User/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm.cmd.
- pnpm-workspace.yaml ma linkWorkspacePackages:true. Zależności zainstalowane, lockfile.
- Budowanie: workdir frontend-spin lub frontend-przeszlosc; node node_modules/next/dist/bin/next build. Ostatnie sesje 40248 i 15786 mogą być ukończone, sprawdzić write_stdin.
- Testy: USE_SQLITE=true; .venv/Scripts/python.exe -X utf8 -m pytest backend -q.
- Docker/PostgreSQL/Redis nie wykryte lokalnie. Nie twierdzić, że ich integrację sprawdzono.
- Brak .git w tym katalogu; nie twierdzić, że commit/push wykonano.
- Sieć shell ograniczona; po błędzie sieci retry require_escalated zgodnie z zasadami. Teraz auto-review włączone i user dał zgodę na pracę.
- Nie wolno delegować subagentom bez jawnego polecenia użytkownika lub właściwego skilla.

## Oficjalne źródła
- https://api.sejm.gov.pl/sejm.html: /sejm/term10/votings/search?title=..., /votings/{sitting}/{number}, votes[].MP/firstName/lastName/club/vote, date bez strefy jako lokalny czas Sejmu.
- Kody: YES, NO, ABSTAIN, NO_VOTE, ABSENT, VOTE_VALID, VOTE_INVALID, PRESENT; ON_LIST ma listVotes i votingOptions.
- https://api.sejm.gov.pl/eli_pl.html: /eli/acts/DU/{year} -> items, totalCount, offset; /eli/acts/{publisher}/{year}/{pos}; /eli/changes/acts?since=...
- https://docs.x.com/x-api/getting-started/pricing: aktualnie pay-per-use, 0.005 USD/post; nie istnieje obiecany dawny darmowy Basic. Nie aktywowano płatnych operacji.
- NewsAPI nie obsługuje language=pl; używamy domains i wyłączonego domyślnie klucza. Darmowy plan wyłącznie development.


## Aktualizacja 00:55 UTC — dalsza praca w tym samym zadaniu
- Modele oficjalnych rekordów, głosowań, głosów, powiązań dowodowych, stanu importu i historii korekt. Migracje 0006–0009 zastosowane.
- Pobrano autentyczne dane: 50 głosowań o kryptoaktywach, 22 997 głosów imiennych, 3278 druków Sejmu, 1183 pozycje DU 2026, 895 MP 2026. To nie fikcyjne dane demo. Nie utworzono publicznych nitek.
- Zapytanie „zondacrypto Mariusz Gosek” faktycznie zwraca dwa głosowania 46/75 i 55/13. Powiązania są jawne, źródło KPRM i opis ograniczeń w scraper/data/evidence_links.json. Oficjalne NO dotyczy ponownego uchwalenia. Sam Gosek także trafia Darię Gosek-Popiołek; UI pokazuje pełne nazwiska.
- Podgląd metadanych URL + formularz redakcji gotowe; brak zapisu przed potwierdzeniem. Blokada prywatnych IP/redirectów, limity czasu/rozmiaru.
- UI głosowań, paginacja posłów, załączniki urzędowe, data dzienna bez wymyślonej godziny, baner współtworzenia. Oś ma zoom kart 220–380 i strzałki, rzeczywiste daty na pasku.
- Poprawiono RSS: updated nie udaje published, brak ucięcia 100 wpisów, seeding nie obniża ręcznie zwiększonej częstotliwości. NewsAPI paginuje, zachowuje ostatni sukces przy błędzie.
- 34 testy przechodzą. Schemat OpenAPI generuje się i waliduje bez ostrzeżeń. Build obu frontendów przechodził przed ostatnimi poprawkami.
- Lokalny admin utworzony; dane wyłącznie .local/admin-login.txt (nie wyświetlać hasła w logach). .local ignorowane przez git i Docker.
- Backend działa w sesji exec 93216, 127.0.0.1:8000, DEBUG + SQLite. Restartuj go po kolejnych zmianach backendu (uruchomiono --noreload).
- HTTP smoke wykrył pętlę przekierowań /api z powodu Next trailing slash vs Django APPEND_SLASH. Naprawiono skipTrailingSlashRedirect:true w obu next.config.js. Frontend sesja62411 zatrzymana; nowy build spin sesja40585 trwa. Po build uruchomić next start i ponowić smoke logowania przez localhost:3000. Nie twierdzić, że przepływ już przeszedł.
- Rozpoczęto rzeczywisty import RSS (sprawdzić bieżącą sesję z wyniku narzędzia). Źródła wyłączone nie są pobierane.
- README, docs/DATA.md, DEPLOYMENT.md, API.md, AI.md odświeżone. Nie wdrożono do chmury. Redis/PG/Docker lokalnie brak.

### Pozostałe ważne kroki
- Dokończyć HTTP smoke i końcowe buildy po zmianach, uruchomić gotowy lokalny podgląd. Otworzyć przez open_in_codex po udanym HTTP fetch (bez browser QA, chyba że użytkownik poprosi).
- Dodać testy nowych poprawek RSS/NewsAPI, importer cykliczny Sejm/ELI i ewentualne braki stronicowania. Sprawdzić czy GDELT nie ucina wyników bez widocznego ostrzeżenia.
- Zweryfikować stan rzeczywistych RSS i pokazać błędy redakcji; nie wymyślać zamienników adresów bez weryfikacji.
- Dokończyć kontrolę bezpieczeństwa/danych w normalnym kodzie, posprzątać wyłącznie własne tymczasowe skrypty wymienione wcześniej.
- Instrukcja uruchomienia na rano, opcjonalny lokalny launcher. Hasło podawać jako ścieżkę do lokalnego pliku, nie w logach.
- Wznawianie heartbeat co30m już aktywne, nie tworzyć duplikatu. Zatrzymać tylko po rzeczywistym powrocie użytkownika, nie po automatycznej wiadomości harmonogramu.


## Aktualizacja po wznowieniu pakietu — 8 września, około 04:35 UTC
- Użytkownik jawnie poprosił o kontynuację po zwiększeniu pakietu. To nie polecenie zatrzymania prac; heartbeat pozostaje aktywny zgodnie z tą nowszą dyspozycją.
- Naprawa przekierowań wymagała również końcowego / w destination Next rewrites, nie tylko skipTrailingSlashRedirect. HTTP przez localhost:3000: strona główna/editor/search/health, logowanie, dostęp redakcji, status importu, wyszukiwanie i wylogowanie przeszły pomyślnie.
- Backend nadal ma --noreload i należy zrestartować po ostatnich poprawkach. Bieżąca stara sesja backendu45859. Frontend94261 zatrzymany do buildów; końcowe buildy spin49593 i przeszlosc21322 trwają.
- Stan danych: 6036 materiałów, 22 997 głosów, 0 nitek. 630 RSS, 3328 Sejm (3278 druki + 50 głosowań), 2078 ELI. Nie dodano fikcyjnych nitek.
- 32/59 kanałów RSS miało błąd po pierwszym imporcie. Potwierdzone na stronach wydawców poprawki GUS i RMF24 zapisano w scraper/data/feed_corrections.json; 60 nowych rzeczywistych rekordów pobrano. Pozostałych adresów nie zgadywano.
- Dodano admin-only /api/editor/status/ i rozwijany stan importu w kreatorze. X/NewsAPI jawnie nieaktywne bez tokenów. UI pokazuje ograniczenie lokalnego trybu bez worker/Beat.
- Wzmocniono fetch_feed: łączenie z konkretnym publicznym IP po DNS, zachowanie SNI/certyfikatu HTTPS, sprawdzenie każdego redirectu. Rzeczywisty RSS GUS i metadane KPRM sprawdzone po tej zmianie.
- GDELT sygnalizuje możliwe ucięcie 250 wyników. NewsAPI ma paginację i checkpoint. ELI changes paginuje i wykrywa powtórzenia. Testy obejmują awarie i zachowanie poprzedniego sukcesu.
- 42 testy przechodzą. Django check wcześniej bez uwag, makemigrations --check bez zmian, OpenAPI bez ostrzeżeń.
- Instrukcja dla właściciela docs/START.md; launcher Start-Portal.ps1 obsługuje lokalny Python i dołączony Node, nie uruchamia automatycznego importu. .local/admin-login.txt zawiera wygenerowane hasło — nie ujawniać go w logach.
- Własne 11 tymczasowych skryptów edycji usunięto. Skan kodu nie wykazał mojibake ani pozostałych paywalli.
- Publiczne wdrożenie i klucze integracji pozostają po stronie konfiguracji kont. Nie twierdzić, że PG/Redis/Docker/przeglądarka mobilna były przetestowane. Weryfikacja UI dotąd: buildy/typy i HTTP, bez automatyzacji przeglądarki.

### Ostatnie czynności bieżącego etapu
1. Odczytać wyniki buildów49593/21322, zrestartować backend45859, uruchomić gotowy frontend na127.0.0.1:3000.
2. Jednorazowy HTTP test gotowego zestawu (w tym stan importu i zapis prawdziwego szkicu tylko jeśli potrzebny; nie zostawiać testowych nitek).
3. Otworzyć lokalny portal przez open_in_codex po udanym HTTP odczycie. Zaktualizować ten plik rzeczywistymi sesjami.
4. Po ukończeniu lokalnego MVP nie generować sztucznej pracy i nie powtarzać testów bez zmian. Dalsze istotne prace wymagające kont zapisać, nie kupować usług. Heartbeat ma pozostać cichy bez nowego stanu; zatrzymać po wyraźnym zakończeniu przez użytkownika.


## Lokalny MVP — etap zakończony, około 04:32 UTC
- Oba końcowe buildy (49593/21322) przeszły. 42 testy i schemat OpenAPI bez błędów; migracje zgodne.
- Działający backend: sesja2119,127.0.0.1:8000,DEBUG+SQLite, uruchomiony z automatycznie zatwierdzonym dostępem do sieci. To konieczne, aby URL preview rzeczywiście pobierał publiczne strony. Stare backendy45859/87267 zatrzymano.
- Działający frontend: sesja58838,127.0.0.1:3000. Udostępniony w panelu Codex pod http://localhost:3000.
- Końcowy test HTTP przez frontend przeszedł: home/editor/search/health200, dwa wyniki zapytania Gosek, logowanie, prawdziwe pobranie metadanych KPRM200, utworzenie szkicu201 z dwoma autentycznymi źródłami, poprawna chronologia, ukrycie szkicu przed publicznym odczytem404, edycja200, status200, wylogowanie200.
- Jednorazowy szkic kontrolny usunięto po teście po jego unikalnym tytule. Nie pozostały testowe nitki; publikacja pierwszych historii należy do użytkownika.
- Instrukcja na rano docs/START.md; dane konta .local/admin-login.txt; launcher Start-Portal.ps1.
- Pozostałe sprawy wymagają konfiguracji kont (publiczny hosting, PG/Redis/worker/Beat, X, NewsAPI, linki wsparcia). Nie wdrożono usług ani nie wydano środków. 32 kanały RSS mają jawne błędy — brak kompletności archiwum jest opisany.
- Przy kolejnych heartbeat bez nowych wytycznych: nie powtarzać całego testowania/buildów, nie tworzyć sztucznych zadań. Reagować na istotną awarię lub nową instrukcję, zachowując ciszę przy niezmienionym stanie. Aktualna dyspozycja użytkownika to kontynuacja po zwiększeniu pakietu; nie wymaga ponownej zgody na normalne poprawki.


## Aktualny zakres — 8 września po południu (nadrzędny wobec wpisów powyżej)
Użytkownik ponownie autoryzował samodzielną pracę; konfiguracje i zakupy na koniec. Heartbeat wznowiony. X wyłącznie link po URL w nitce, bez Article w bazie, bez indeksowania i płatnego importu. Nie realizować starego katalogu kont ani kupna API X.
Bieżące zmiany: paginacja wyszukiwarki po100 bez limitu500, wyłączenie tweetów z wyszukiwania, domyślnie artykuł dla RSS mediów, migracja0011 koryguje tylko niezweryfikowane medialne RSS kategorii other. Nullable ThreadItem.article + external_url i walidacja znanych adresów X, podgląd URL X bez sieci i bez dat. UI: burgund, wspólne motto, wyszukiwarka nagłówka,5 pustych nitek, filtr kategorii obok dat. Testy44 pass. Pierwszy build wykrył inferencję typów useInfiniteQuery — poprawiono kolejność pól, ponowny build jeszcze potrzebny. Migracje jeszcze nie zastosowane do lokalnej bazy; stare serwery wymagają restartu.
Nadal do realizacji: importy archiwalne i pokrycie źródeł, czytnik treści, YouTube, komentarze nakładane na box, eksport X, monitoring/backupy i wdrożenie. Nie twierdzić, że wszystkie te rzeczy działają.


## Aktualizacja 8 września, około 19:50 UTC
Zaimplementowane i testowane: zewnętrzny ThreadItem X po URL (nie Article), paginacja100 bez odcięcia500, kategorie RSSarticle + migracja, burgund/motto/headersearch/5emptyrows/categorydropdown, nakładki komentarza autora, eksport X z twitter-text3.1.0 i kontrolą280. SourceCoverage public /api/sources/coverage. YouTube API adapterGETstatusPOSTsearch+cache+trwałybudżet, wyłączony bezklucza. ArchiveJob trwała kolejka sitemap/page, publiczne DNS+robots, retry/lease, odczyt JSONLDarticleBody do ArticleContent z hashem; contenttext uwzględnione w wyszukiwaniu. Brakujące treści jawnie oznaczane. KopieSQLite backupAPI+integrity_check. Lokalny scheduler run_local_jobs (RSSdueco60s, głosy15m, druki/ELI1h, GDELT2h, archiwa1m, discoverydaily, backupdaily), OSfilelock.
Migracje0010–0013 zastosowane. Poprawiono SQLite współbieżność: WAL i transaction_modeIMMEDIATE. Pierwszy scheduler5088 zatrzymany po OperationalError; drugi38494 działał kilka godzin bez błędów lokalnych jobów, ale błędy poszczególnych RSS/GDELT nadal istnieją i trzeba je kontrolować. Nie utożsamiać lokal:last_success z sukcesem wszystkich feedów (guarded przechwytuje wyjątki).
O19:48:6873Article,9odczytanychtekstów,250Articlearchive,272pagejobsdone,11296pagepending,1573sitemappending. Realny artykułOKO.press https://oko.press/krrit-oszukala-widzow-tv-trwam-blad-wprowadzil-andrzej-duda odnaleziony wpost-sitemap1.xml. Początkowo dataNone; poprawka parseraJSONLD potwierdziła2016-12-06T11:33:48+00:00. Inna data2016-12-03dotyczyClaimReview, ignorujemy ją. Brakującą datę uzupełniono z evidence_note, bez zgadywania.
50testówbackendpass. Buildspin84005pass przed ostatnią zmianąImportStatus; potrzeba końcowybuildobu frontendów. Backend63171 działa ze starszym kodem, frontend30039 działa. Scheduler38494 wymaga restartu do poprawkiJSONLD i pacing3s. Requeue done archivejobs z Article.published_dateNone do ponownegoodczytu poprawionymparserem; NIE zmieniać istniejącychdat. WalidacjaUI: CUA utworzył ukrytytab4localhosthome (nowyheader/motto widoczne); usertab1 nadalstaryDOM przedodświeżeniem. Nie było pełnej wizualnejQA. Agent-browserCLI niedostępny; CUA tylko docsentrypoints dostępne.
Dalsze prace: końcoweQA/restarty, trwałeudokumentowaniestatusówbłędów, kolejkauzupełnianiadat, przeglądźródełRSS i archiwów, instrukcjeserwera/kluczy, uprawnieniazaproszonychautorów/sponsorów, AIgroundedjeszczeniezaimplementowane. Nie kupować X. Nie twierdzić, że baza kompletna lubAIaktywny. Wszystkiezakupy/klucze/hostingwłaścicielkoniec.


## Stan zweryfikowany około 19:57 UTC
- Migracja0014 dodaje Source.last_attempted. RSS jest odpytywany zgodnie ze scrape_frequency_minutes także po błędzie (nie zmieniono60/240min). Poll schedulera co60s nie wywołuje już nieudanego kanału co minutę. Częstotliwości źródeł zachowane.
- 250 historycznych rekordów bez dat ponownie skierowano do odczytu poprawionym JSON-LD parserem. Poprawka uzupełnia wyłącznie pustą datę niezweryfikowanego rekordu i zapisuje źródłowy ślad w evidence_note. Istniejących dat nie nadpisuje.
- archive_cycle/discovery_cycle przeniesione do scraper/archive.py. Zasilanie kolejki bieżącymi artykułami pomija już istniejące joby, więc błędne20najnowszych nie blokuje odczytu kolejnych. Celery ma partie co minutę i discoverydaily. Każda próba w partii ma odstęp3s; robots może narzucić dłuższe ograniczenie.
- Po zmianach50testówpass; Django check OK; makemigrationscheckbez zmian. Oba końcowe buildy spin12246 i przeszlosc7295pass. Zależność twitter-text działa; pnpm-workspace allowBuilds core-js:false świadomie pomija jego skrypt instalacyjny.
- Backend aktualny38794, frontend aktualny36384 na3000. Scheduler43371 zastąpiony najnowszym uruchomieniem (zobacz bieżące narzędzia). Nie uruchamiać duplikatu; OSfilelock chroni proces.
- HTTP przez3000: home/editor/search/health/coverage/youtube-status200. Wyszukiwanie KRRiT z to_date2017-01-01 zwróciło rzeczywisty artykuł z2016-12-06. Zondacrypto Mariusz Gosek nadal2poprawnewyniki. YouTube nieaktywnebezklucza.
- CUA odczytał nową stronę główną i wszystkie5pustych nitek po5boxów. To odczyt struktury strony, nie pełna wizualnaQA/mobile. Userowi może być potrzebne odświeżenie staregoDOM otwartej karty.
- Instrukcje właściciela docs/OWNER_NEXT_STEPS.md. Przygotowano docs/SOURCE_RESEARCH_PROMPT.md z32problematycznymi RSS do niezależnego researchu. Nie traktować błędu importu jako dowodu braku źródła.
- Nadal brak konfiguracji publicznego serwera, kluczaYouTube i backupu poza urządzeniem. AIasystent, publicznerejestracje, profile dziennikarz/komentator i sponsorowaneworkflow to dalsze etapy, nie ukończone funkcje. Rdzeń nadal redakcyjny.
- Kontynuacja heartbeat: priorytet naprawa/prowadzony dowodami audyt32RSS i skalowanie archiwów, walidacja dat/treści, stabilnośćschedulera. Lokalnyjoblastsuccess nie przesądza o sukcesie feedów, guarded może przechwycić błędy; naprawić monitoring agregacji jako kolejne zadanie. Bez fikcyjnych nitek. Nie pobieraćX. Nie powtarzać buildów bez zmianyUI.


## Heartbeat 20:30 UTC — monitoring częściowych awarii
Naprawiono lokalny run_monitored: częściowy błąd nie aktualizuje last_success; pusty przebieg idle nie kasuje wcześniejszego błędu. Raport próby trafia do ImportState.cursor (status, czas zakończenia, identyfikatory błędnych źródeł/jobów). rss_cycle ocenia last_attempted/last_scraped i błędy, więc błąd zapisu po pobraniu też jest widoczny. gdelt_cycle nie maskuje wyjątków przez guarded i odczytuje sygnał ucięcia250. discovery_cycle/archive_cycle zwracają rzeczywisty partial/ok/idle, także dla zadań Celery. Poprzednie historyczne last_success lokalnych zadań mogły oznaczać tylko koniec procesu; nie uznawać ich za dowód kompletnego sukcesu źródeł.
Dodano2testy regresji monitoringu;6testów monitoringu+archiwówpass. Bez zmianUI, nie powtarzano buildów. Lokalny scheduler52222 zastąpiony38154, backend38794/frontend36384 nadal działają. Następny priorytet: udokumentowany audyt32błędnychRSS; źródła i dalszehistoryczneodczyty kontynuująpracębezX.


## 21:04 UTC — kontroler jakości i propozycje źródeł
Na prośbę użytkownika priorytet pozostaje baza, frontend czeka na komentarze. Wdrożono QualityIssue(migracja0015), scan_quality incremental200rekordów z kursorem/wrap, wyłącznieflagi brakudat/przyszłychdat/kategoriiother/nieprawidłowegoURL/potencjalnychduplikatów. Żadnego przepisywaniaźródła. Adminreadonlylista z filtrami. Lokalny scheduler i Celery uruchamiają kontrolę co5min. Pierwsza partia200rekordów14uwag;2nowetestyprzeszły (treśćArticleidentycznaprzedipo, brakduplikowaniaspraw, nieusuwaniepotencjalnychduplikatów).
Scheduler54373,backend52621,frontend36384. Migracjezastosowane. BrakzmianUI/buildów. Nowy docs/SOURCE_EXPANSION.md: zweryfikowaneoficjalnezasobyRCL,NIK,PKW,BZP,NSA,UOKiK,dane.gov.pl + kandydacisamorząd/UE/KNF/URE/UODO. To lista wdrożeniowa, NIE twierdzićże noweintegracjejużdziałają; nie dodanozgadywanychRSS. Użytkownik podkreśla agregowanie oryginałów, bez ingerencji w treść. Kontroleroceniametadane, nie prawdziwośćtwierdzeń.


## 2026-09-09 — ciemny, zwarty układ i wznowienie lokalnych importów

- Motyw grafitowy z bordowymi przyciskami i jaśniejszym akcentem dla tekstu, wspólny dla obu frontendów. Dopasowano też kolory komunikatów błędów i sukcesu.
- Strona główna: 5 pustych pasków po 5 boxów, podpisy KATEGORIA / ŹRÓDŁO / DATA oraz puste miniatury. Bez przykładowych rekordów i nitek w bazie. Mniejsze odstępy, tylko separatory pomiędzy boxami.
- Zwężono nagłówek i odstępy rzeczywistych osi czasu; zachowano wyszukiwarkę i dostępność źródeł.
- Build obu frontendów przeszedł; po końcowej korekcie wysokości miniatur ponowiono build spin. Kontrola obrazu strony głównej w przeglądarce potwierdza ciemny układ i komplet 25 placeholderów.
- Wznowiono run_local_jobs (sesja 29065), backend (60147), frontend produkcyjny lokalny (25368). Heartbeat 00:55:02 UTC. Liczba Article podczas pomiaru: 7843, wcześniej 7825. Archiwizacja, głosowania, druki, ELI i kontrola metadanych odnotowały sukces; RSS/GDELT/odkrywanie nadal zgłaszają częściowe błędy źródeł. Nie deklarujemy pełnego pokrycia.
- Zweryfikowana kopia SQLite: .local/backups/portal-20260909T005241507635Z.sqlite3. Baza nadal backend/db.sqlite3 na komputerze użytkownika; brak wdrożenia zewnętrznego i kopii poza tym komputerem. Procesy wymagają działającego komputera.
- Rozszerzenia z SOURCE_EXPANSION.md nadal wymagają wdrożenia i weryfikacji importerów; zmiana wyglądu nie oznacza dodania tych źródeł.


## 2026-09-09 — przypisanie treści do właściwego źródła

- Ponownie otwarto podgląd http://localhost:3000/ w działającej karcie 4; wcześniejsza karta 1 zawierała stronę błędu połączenia. HTTP 200 i obraz działającego układu potwierdzone.
- Czytnik JSON-LD nie wybiera już najdłuższego articleBody. W pierwszej kolejności wymaga zgodnych identyfikatorów URL/mainEntityOfPage; zachowuje parametry zapytania, obsługuje względne adresy i fragmenty. Sprzeczne lub wieloznaczne treści pozostają puste. Pojedynczy tekst bez identyfikatora jest dopuszczony tylko bez innych, obcych artykułów. Nie ucina długich tekstów do pozornego pełnego materiału.
- Metadane i czytnik używają tego samego dekodowania znaków wydawcy. Nowe ekstrakcje oznaczone wersją metody publisher_jsonld_url_matched_v2. Istniejących treści nie nadpisano.
- 64 testy backendu przeszły. Nowe przypadki obejmują obcy dłuższy artykuł, rozbieżne identyfikatory, wieloznaczność, kodowanie Windows-1250 i brak fałszywego wyniku wyszukiwania.
- Audyt wszystkich 9 wcześniejszych rekordów extracted_text: ponowne pobranie z uwzględnieniem robots, wynik nowego czytnika identyczny z każdym zapisanym tekstem. Nie jest to ocena prawdziwości twierdzeń.
- Worker wznowiony z poprawką: sesja 30490. Nowa zweryfikowana kopia .local/backups/portal-20260909T010659705496Z.sqlite3. Ostatni pomiar przed zmianą: 7882 Article. Pozostałe planowane integracje w SOURCE_EXPANSION.md nadal nie są ukończone.


## 2026-09-09 — naprawa źródeł i kontrola formatu RSS

- Baza o 01:29 UTC: 8007 Article; bieżący heartbeat potwierdzony.
- Na oficjalnych stronach odnaleziono i zweryfikowano RSS: https://www.rp.pl/rss_main (20 pozycji) i https://www.nik.gov.pl/rss/id,1.html (15 pozycji). Trwałe poprawki w feed_corrections.json, bez zmiany częstotliwości 60/240 minut ani identyfikatora źródła. Pierwszy import zapisał 35 nowych rekordów.
- RCL /feed/ i UOKiK /public/rss są wskazane przez ich strony, ale podczas próby nie zwróciły rozpoznanego RSS/Atom. Nie aktywowano importerów i nie uznano tych integracji za ukończone. Senat, KPRM i RPO nie ujawniły kanałów w sprawdzonym HTML.
- Import RSS wymaga rozpoznanego formatu kanału. HTML pod adresem RSS nie aktualizuje last_scraped i nie kasuje błędu. Poprawny pusty kanał jest nadal obsługiwany. Pełny backend: 66 testów przeszło.
- Ustalenia produktowe odłożone do wdrożenia: istniejący widok boxa bez powiększania, pod nim sugerowany pasek do 15 wydarzeń od najstarszego. Autor może dobierać materiały również po URL. Docelowe widoczne etykiety: ARTYKUŁ, WYWIAD, REPORTAŻ, FILM, PODCAST, USTAWA, dokument urzędowy; klasyfikacja ma bazować na materiale, nie samym wydawcy. URL od użytkownika wymaga osobnego ustalenia zasad włączenia do publicznego indeksu; X nadal tylko odnośnik w nitce. Brak streszczeń nie został potraktowany jako gwarancja prawna.


## 2026-09-09 09:13 UTC — pięć naprawionych kanałów wydawców

Odnaleziono odnośniki RSS/Atom w HTML oficjalnych stron Onet Wiadomości, Wprost, Polityka, Dziennik.pl i Dziennik Gazeta Prawna. Każdy kanał zweryfikowano przez pobranie i rozpoznanie formatu przed aktywacją. Aktualne adresy i strony dowodowe zapisano w scraper/data/feed_corrections.json; seed_sources stosuje poprawki tylko do niezmienionych przez redakcję starych adresów, bez zmiany źródła i częstotliwości (60 minut). Pierwszy import dodał odpowiednio 20, 74, 50, 50 i 50 materiałów: 244 łącznie. To bieżące kanały, nie dowód pełnego pokrycia historycznych archiwów. Nie dokonano zmian kodu ani ponownego uruchomienia już zaliczonych testów. Trwający worker odczytuje poprawki przy kolejnych cyklach.


## 2026-09-09 — pełny katalog, prognoza i szybkie aktualności

Wyeksportowano 61 źródeł i 22 rozszerzenia/konektory (83 wiersze bez skrótów) do reports/pelna-lista-zrodel-2026-09-09.md oraz CSV z kolumną uwag. Zapisano pomiar kolejki, tempo ~299 zadań/h i warunkową prognozę w reports/czas-bazy-i-plan-2026-09-09.md. Nie utożsamiono obecnej kolejki z całym archiwum ani rekordów z pełnymi tekstami.
Wdrożono priority_sources.json z roboczymi 15 źródłami odpytywanymi co 5 minut. seed_sources skraca wyłącznie dłuższe interwały; istniejące krótsze pozostają bez zmian. Test zachowania częstotliwości dodany, 21 testów scraper/tests.py przeszło. Zastosowano ustawienia w lokalnej bazie — działający worker odczytuje częstotliwości z bazy, restart nie jest wymagany. Dedykowana kolejka aktualności, szkice AI do 15 boxów i YouTube po URL opisane jako dalszy zakres; generator AI nie został uruchomiony. Nazwa abonamentu 99 zł pozostaje do potwierdzenia.


## 2026-09-09 11:37 UTC — archiwa priorytetem

Nowy zakres i scenariusze w reports/mvp-metadane-i-czas-2026-09-09.md. Partia archive_cycle zwiększona z 5 do 20 z zachowaniem odstępów i robots; 16 testów archiwum/monitoringu przeszło. Wykryto przerwę heartbeat od 11:07; worker wznowiony w sesji 55671, backup portal-20260909T113742642670Z.sqlite3. Agent polish_media_catalog wznowiony na wyraźne polecenie użytkownika do katalogowania dodatkowych mediów; poprzednio miał błąd limitu. Pełny czytnik i argumentacja AI mają niższy priorytet; ranking metadanych nie wymaga treningu. Nie obiecano popularności z nieistniejących danych ani automatycznej legalności miniaturek/publikacji.


## 2026-09-09 12:33 UTC — wznowienie po zwiększeniu pakietu

Agent katalogu wznowiony po limicie; dotychczasowy plik dowodów reports/kandydaci-media-dowody-sgl.json zachowany. Worker działa (heartbeat 12:33:43), baza 12 601 rekordów. Ostatnie 30 min: 459 ukończonych zadań = 918/h; około 3,1x poprzedni pomiar. Znana kolejka 24 698, modelowo 26,9 h bez dopływu; nie termin ukończenia całości archiwów. Uaktualniono reports/mvp-metadane-i-czas-2026-09-09.md.

Agent katalogu dostarczył pierwszą partię: reports/rozszerzenie-mediow-2026-09-09.md i CSV. 74 kandydatów lokalnych według odczytanych wizytówek Stowarzyszenia Gazet Lokalnych; 71 z adresem, 3 niejednoznaczne adresy pozostawione puste. To kandydaci, nie aktywne importy; kontrola docelowych stron i kanałów pozostaje do wykonania. Liczba 74 nie jest liczbą archiwalnych publikacji i nie pozwala jeszcze przeliczyć końcowego czasu.

## Wstrzymanie eskalacji importu na pytanie użytkownika

Użytkownik rozważa MVP oparte o wyszukiwanie zewnętrzne i AI zamiast masowego archiwum. Benchmark przerwany na jego wiadomość przed uzyskaniem wyników dla 4/8 importerów. Potwierdzone krótkie próbki: 1 importer 8 zadań/25,53 s; 2 importerów 15/36,42 s. Nie są miarodajnym pomiarem trwałej przepustowości ani maksimum. Lokalny scheduler (wcześniej zatrzymany do benchmarku) pozostaje zatrzymany; nie deklarować aktywnych importów. Backend wznowiony w sesji 51354. 69 testów backendu przeszło. Dodano równoległy importer i pobieranie adresu miniatury z metadanych, brak wdrożenia nowego wariantu produktu. Decyzja architektoniczna oczekuje na rozmowę z użytkownikiem; nie zwiększać importu automatycznie wbrew nowemu kierunkowi.

## 2026-09-09 — wdrożenie pilotażu hybrydowego

Zaakceptowany zakres: publiczna wyszukiwarka i nitki dr. Spina zatwierdzane przez redakcję; konta użytkowników i film prezentujący działającą wersję później. Dodano backend wyszukiwania Brave (lista domen ze źródeł, trwały limit dobowy, uczciwy disabled bez klucza, osobne kandydatury bez zgadywania dat/kategorii). Wyniki odkrywają URL do ArchiveJob; dopiero odczyt wydawcy tworzy rekord. Filtry kategorii/dat na tym etapie dotyczą lokalnej bazy; wynik sieciowy nie udaje kompletnego przeszukania archiwów.

Dodano endpoint /api/editor/draft-thread/: tylko staff, do60 istniejących kandydatów, do15 wybranych ID, bez publikacji i ocen prawdziwości, trwały limit prób. Frontend pokazuje kandydatury osobno i pozwala przyjmować elementy szkicu. 82 testy backendu przeszły. Realne płatne wyszukiwania/AI nie przetestowane — klucze pozostają do konfiguracji.

Importy wznowione: scheduler sesja72381 ARCHIVE_WORKERS=2, kopia portal-20260909T130451244480Z.sqlite3. Backend nowa sesja60995. Nie zwiększać równoległości bez dalszych pomiarów, zachować harmonogram bieżących źródeł. Instrukcje docs/HYBRID_PILOT.md i docs/EDITORIAL_AI_DRAFT.md.

Google Custom Search JSON API według odczytanej dokumentacji zamknięte dla nowych klientów, koniec2027-01-01. Nie wdrażano Google. Brave podstawowy pilot, Exa potencjalny test pokrycia, nie gwarantować kompletności któregokolwiek indeksu.

## 2026-09-09 — nowy widok AI i kontekst nad wynikami

Nowy minimalistyczny frontend: ciemne tło, cienkie separatory i subtelny sygnał oscyloskopowy z reduced-motion. Strona główna i wyszukiwanie mają AIResearch: Szukaj kontekstu oraz pomocniczy SPIN VERIFY tylko do konkretnej publicznej wypowiedzi polityka. Verify wymaga URL, przypisanego autora i wklejonej treści; X pozostaje reference-only, autorstwo i tekst użytkownika nie są automatycznie potwierdzone.

Dodano Responses web_search z listą źródeł, cytowaniami z listy konsultowanych adresów, limitem prób i wywołań. Moduł celowo nieaktywny bez klucza/modelu/flag. AI nie tworzy źródłowych rekordów z własnego tekstu. Cited istniejące Article tworzą nitkę do15 boxów z datami bazy; nowe odnośniki czekają na metadane. Pełniejsze wyniki lokalne są poniżej po datach. Nie twierdzić, że już działa streaming ani kompleksowy dobór15 nowych wydarzeń z całego internetu: wymagany live pilot i docelowy odczyt źródeł. Backend dokumentuje ograniczenia.

Pytanie „jak głosował poseł Gosek” ma oficjalne direct_results. Sprawdzono działający lokalny endpoint:100 dopasowań,3 odpowiedzi bezpośrednie. 95 testów backendu przeszło, build Next.js przeszedł. CUA potwierdziło nowy wygląd i formularz SPIN VERIFY. Poprawiono BOM skryptu Start-Portal.ps1, uruchomiono backend/frontend jako ukryte procesy przez skrypt (logi .local). Stare sesje dev zakończone. Harmonogram importu osobno72381.

Przykładowe10 nitek przerwane i odłożone wyraźnym poleceniem użytkownika, nic nie publikowano. Nitki redakcyjne mają być codzienną pracą redakcji, automatyczne publikowanie nie zostało uruchomione. Instrukcje docs/DR_SPIN_PRINCIPLES.md oraz docs/AI_RESEARCH_PILOT.md.

## 2026-09-09 13:55 UTC — import równoległy i uproszczone MVP

Użytkownik utrzymał priorytet archiwów i poprosił o równoległe rozwijanie AI. W trakcie pracy zmienił interfejs: publiczny SPIN VERIFY usunięty. Na głównej są trzy zwarte wyróżnione układy redakcyjne Dr Spina (pierwszy box: wypowiedź polityka), niżej zwykłe nitki; puste miniatury i przykładowe podpisy są wyłącznie layoutem. Nie dodano fikcyjnych danych. Formularz AI i duża fala usunięte z home. Hasło CONTEXT BEFORE CONTENT zastępuje link panelu w nagłówku. Bezpośredni login: /editor. Publiczne wyszukiwanie kontekstu zachowane, verify backend tylko dla staff przed rezerwacją limitu.

Backend: trwały AIResearchCall z rzeczywistymi metrykami odpowiedzi, bez prywatnych promptów, sekretów i tekstów analiz; ai_preflight bez sieci. Migracje0016/0017 zastosowane. URL odkryte przez AI/Brave dostają pierwszeństwo w co czwartym slocie, z zachowaniem lease i backoff. Źródła w grupach rotują, aby małe nowe archiwa nie czekały za dużymi kolejkami. Naprawiona niejednoznaczna data JSON-LD; starych danych nie nadpisano. Zalecany audyt wcześniejszych dat i uzupełnianie pustych miniatur z ewidencją pozostają w raporcie.

Zmierzono4 importerów:48 zadań/65,92s;8 importerów:95/87,31s i95/120,47s. Brak błędów pobierania w tych próbach; wyszukiwanie pod obciążeniem p95 odpowiednio0,046/0,063/0,109s. To krótkie próbki zadań (również mapy i duplikaty), nie tempo nowych artykułów ani dowód absolutnego maksimum. Wcześniejsza próba bez dostępu do sieci została odrzucona; jej NewConnectionError z dokładnego okna czasu zachowano w osobnym raporcie i ponownie zakolejkowano. Pozostałych błędów wydawców i backoff nie zmieniono.

Scheduler sesja95063 działa z ARCHIVE_WORKERS=8, ustawienie zapisane w .env i przykładzie. Odstępy domen i częstotliwości aktualności zachowane. Ostatnia partia159 zadań/96,52s miała1 błąd wydawcy. Pomiar13:55:25UTC:14258 Article;71 źródeł,36 z materiałami;1087951 pending URL. Kolejka szybko rośnie przez nowe mapy, nie oznacza tylu poprawnych artykułów; dawne prognozy25k kolejki nieaktualne. Sam duży katalog jednej domeny ogranicza jej odstęp między żądaniami.

Aktywowano10 zweryfikowanych wydawców:2RSS i8sitemap-only (jawna lista konfiguracji). DdWloclawek zostawiony kandydatem z powodu potwierdzonego błędu klasyfikacji materiału sponsorowanego. Raport wszystkich11 kontroli: reports/weryfikacja-mediow-lokalnych-2026-09-09.md. Pełny bieżący eksport71 źródeł: reports/zrodla-stan-biezacy-2026-09-09.csv.

129 testów backendu przeszło; Next production build przeszedł. Backend/frontend odświeżone przez Start-Portal, CUA potwierdziło nową stronę główną. AI nadal bez klucza i modelu: nie wykonano płatnych analiz. Instrukcja właściciela: docs/AI_START_CHECKLIST_PL.md. Serwer i DNS nadal do późniejszej konfiguracji.

## 2026-09-09 14:31 UTC — klasyfikacja sponsorowanych i kolejny wydawca

Heartbeat potwierdził dalszy import: o14:27UTC15961 materiałów,2449047 pendingURL. Osiem importerów działało, monitoring/RSS/backup zdrowe; partie archiwum częściowe, m.in. odrzucane strony bez jednoznacznych metadanych i błędy wydawców. Nie utożsamiać rosnącej kolejki z gotowymi publikacjami.

Usunięto konkretny blocker DdWloclawek: news/classification.py mapuje zweryfikowaną ścieżkę /pl/701_artykuly-sponsorowane/ na sponsored z dowodem. Używana przez podgląd metadanych i nowe automatyczne rekordy; istniejące dane/redakcyjne decyzje pozostają bez nadpisania. 64 testy klasyfikacji+dat+archiwum+RSS przeszły; konfiguracja źródeł także. Rzeczywistą stronę ponownie odczytano14:29:51UTC i potwierdzono klasyfikację; surowy wynik w reports/ddwloclawek-classification-check-2026-09-09.json. Źródło72 aktywowane sitemap-only (11 nowych zweryfikowanych lokalnychłącznie). Raport aktywacji osobno.

Scheduler odświeżony z nowym kodem: sesja61453, ARCHIVE_WORKERS=8. Backend odświeżony, frontend bez zmian. Stop poprzedniej sesji95063; pozostawione lease odzyskuje normalny importer po terminie. Klucze i płatne AI nadal niekonfigurowane; nie trzeba ponawiać pytania właścicielowi. Dalsze priorytety: dane źródłowe i klasyfikacje z dowodem, kontrola starszych niejednoznacznych dat, uzupełnianie brakujących miniatur z ewidencją, rozszerzanie zweryfikowanego katalogu.

## 2026-09-09 15:08 UTC — uzupełnianie pustych miniatur z dowodem

Heartbeat15:03UTC:18773 Article, osiem importerów pracuje; błędy archiwum głównie unclassified_page w Niebezpiecznik/Polityka oraz jawne błędy wydawców. Nie dopuszczano niejednoznacznych stron tylko dla zwiększenia liczników. Około6389 nieoficjalnych rekordów bez miniatury; część nie musi mieć zdjęcia w źródle.

Wdrożono news/enrichment.py: wyłącznie pusta miniatura w rekordzie RSS/archive, zgodność URL, brak category_reviewed; adres z metadanych wydawcy. Obecne wartości i źródłowe teksty bez nadpisania. Każde uzupełnienie ma ewidencję czasu, pola, URL i SHA odpowiedzi. Hook wykorzystuje już pobraną stronę. Nowa komenda queue_thumbnail_backfill ma trwały jednorazowy kursor, limit50 domyślnie, priorytet10, zachowuje retry i lease. Pierwsza partia50:35 zadań utworzonych/wznowionych,15 już w toku.

42 testy uzupełnień/dat/archiwum przeszły; testy jednorazowego kolejkowania i ograniczeń także. Instrukcja docs/METADATA_ENRICHMENT.md. Worker61453 zatrzymany i zastąpiony sesją9772 z nowym kodem, nadal8 importerów. Frontend i płatne AI bez zmian. Nie mnożyć ponownych odczytów całej bazy — następne niewielkie partie korzystają z kursora i nie zmniejszają ustalonych częstotliwości aktualności. DyskC ok80GB wolnego w pomiarze; SQLite ok1GB. Kopie na tym samym komputerze, niezależna zewnętrzna kopia pozostaje do wdrożenia.

## 2026-09-09 15:48 UTC — pomiar rzeczywistych przyrostów i kontrola źródeł urzędowych

Import odróżnia teraz nowo utworzone Article od powtórnych odczytów stron, map witryn, błędów i odroczonych zadań. Liczniki są agregowane z ośmiu importerów i zapisane w raporcie cyklu. Pierwsza sprawdzona partia: 148 ukończonych zadań w 88,84 s, w tym 141 stron, 7 map i 124 nowe materiały; 12 błędów zapisanych jawnie. Nie traktować 148 zadań ani zawartości map jako liczby nowych artykułów. Testy metryk, archiwum i kolejkowania: 21 zaliczonych.

Harmonogram kopii zachowuje termin po restarcie procesu, aby odświeżenie kodu nie tworzyło za każdym razem kolejnej dużej kopii. Nadal jedna kopia na 86400 s; brak, błąd, niedokończona lub przeterminowana kopia powodują natychmiastową próbę. Żadnej kopii nie usunięto. Testy monitoringu i metryk: 4 zaliczone. Django check bez uwag, brak oczekujących zmian migracji. Worker9772 zastąpiony sesją15606, ARCHIVE_WORKERS=8. Potwierdzono nowy heartbeat i zachowanie udanej kopii z15:07:34 UTC bez zbędnego ponowienia. Częstotliwości aktualności i archiwum niezmienione.

Druga ograniczona partia uzupełniania miniatur: 50 kolejnych rekordów zakolejkowanych przez trwały kursor. Zweryfikowany przykład DdWloclawek przeszedł zwykły importer jako Article22124 z kategorią sponsored i dowodem działu wydawcy; nie zapisano go ręcznie. Snapshot15:47:56 UTC: 22380 Article, 72 źródła, 46 z materiałami; 2941374 oczekujące adresy, nie potwierdzone publikacje. Pełny CSV i reports/stan-importu-2026-09-09.json odświeżone.

Agent sprawdził KPRM, Kancelarię Prezydenta i RPO. Nie potwierdził RSS/Atom ani zadeklarowanej XML sitemap; znalazł oficjalne listy HTML, dla KPRM i RPO z jawną paginacją. Wyniki i dowody: reports/weryfikacja-rss-oficjalne-2026-09-09.md/.json. Trzy nieaktywne kandydatury w reports/kandydaci-importery-oficjalne-2026-09-09.json; nie są nowymi działającymi integracjami. Następny krok: importer jawnej listy KPRM lub RPO z kontrolą dat publikacji i odnośników, bez zgadywania endpointów. Frontend oraz płatne AI bez zmian.


## 2026-09-09 16:44 UTC — pomiar importu i wspólny katalog źródeł

Wykonano 8 prób rzeczywistej kolejki: ustawienia8/12/16/24/32 z powtórkami8/24/32. Maksimum faktycznie sprawdzone28 grup; przy ustawieniu32 gotowe zadania miało27–28 źródeł. Średnio98,8 nowych/min pracy dla8 i238,1 dla32 (~2,4×);24 osiągnęło233,3, więc niewielka różnica względem32 nie dowodzi przewagi przy każdej kolejce. Brak błędów bazy/wyszukiwania;40 dodatkowych zapytań bez cache p95 0,438s, bez błędów. To krótkie pomiary partii, nie gwarancja dziennego tempa ani absolutnego maksimum sprzętu. Raport: reports/archive-capacity-2026-09-09.md/.json. ARCHIVE_WORKERS=32 w .env i .env.example; limit bezpieczeństwa kodu64 nie jest zmierzoną wydajnością. Bramka hosta, retry i aktualności bez zmiany częstotliwości.

Nowy /editor/sources jest autorytatywnym katalogiem wszystkich Source. Staff-only lista/POST/PATCH/CSV, CSRF, bez kasowania źródeł i artykułów. Kandydat nieaktywny, można dodać bez URL; configured wymaga adresu, excluded wyłącza pobieranie i chowa z bieżącej listy. Przywrócenie daje nieaktywnego kandydata. Wyszukiwarka zachowuje wcześniej zebrane materiały. Domenę źródła z publikacjami lub kolejką chroni walidacja; RSS edytowalny. DNS poza transakcją SQLite. Pełny eksport CSV z BOM i ochroną formuł. Instrukcja docs/SOURCE_CATALOG.md, dane logowania tylko w .local/admin-login.txt.

Live migracje0018/0019/0020 zastosowane; przed zmianami kopia .local/backups/portal-20260909T162756118043Z.sqlite3. Stabilny catalog_seed_key zachowuje tożsamość po edycji nazwy/ścieżki; seed nie reaktywuje wykluczonych ani nie nadpisuje ustawień RSS/częstotliwości właściciela. Import94 pozycji z dwóch pełnych list kandydatów:77 nowych nieaktywnych,17 dopasowanych; drugi przebieg0 nowych/0 notatek. Wszystkie149 wpisów,72 import włączony i77 kandydatów (włączony nie znaczy działający). Różne instytucje na gov.pl nie są scalane po wspólnej domenie. Historyczne notatki zgłoszeń mogą opisywać stan przed aktywacją.

162 testy backendu PASS i zgodne migracje; Next production build PASS. Osobna przeglądarka potwierdziła login, pełną listę149, filtrowanie, zapis bez zmiany danych, wykluczenie i przywrócenie nieaktywnego kandydata, pobranie całego CSV i brak poziomego przepełnienia na390px. Bez błędów JS. Kontrolna zmiana kandydata Gazeta ABC odwrócona; brak fikcyjnych źródeł i materiałów. Katalog API ~2,6s pod importem, obejmuje agregację dużej kolejki; nie utożsamiać z czasem publicznego wyszukiwania. Raport reports/source-catalog-browser-check.json, pełny CSV reports/katalog-zrodel-2026-09-09.csv.

Benchmark24540 zakończony; zwykły scheduler5089 zastąpiony57954 z nową obsługą katalogu, ARCHIVE_WORKERS32. Heartbeat16:44:27UTC potwierdzony. Snapshot16:44:30UTC:30223 Article,149 Source,46 źródeł z materiałami;2952118 oczekujących adresów, nie potwierdzonych artykułów. Ostatnia ukończona partia przed restartem:24 aktywne grupy z limitem32,417 nowych rekordów/115,81s. Płatne AI bez zmian/nieuruchomione. Kontynuować źródła i archiwa, respektować decyzje właściciela zapisane w katalogu; nie traktować plików seed jako nadrzędnych.
# 2026-09-09 17:49 UTC — pełny audyt dostępu, wolumen i rzeczywiste importy

Aktualny kontekst: użytkownik poprosił o głębokie badanie wszystkich źródeł, wielkości archiwów, sposobów importu, czasu i dysku. W toku doprecyzował przyszły pulpit informacji: nitki redakcyjne Dr Spina, trzy osobiste tematy, filtrowane newsy i żywa siatka bazy. Kierunek zapisany w docs/HOME_INFORMATION_DESK.md; nie wykonywano nowej przebudowy strony głównej. Priorytet nadal archiwum/metadane.

Kontrola149/149 zakończona:145 completed,4 missing_url (73,74,93,111),bez nieoczekiwanych błędów. RSS56working/4empty/22unavailable/63not_found;87źródeł z mapami;118z RSS/mapą/oficjalnymAPI.647578URLw próbkach map, bez deduplikacji między źródłami, NIE pełny wolumen. Źródła gov zweryfikowane pod kątem tożsamości, ogólny redirect nie jest dowodem dostępności ministerstwa. Dowody ImportState source-check:{id}, reports/source-access-audit-2026-09-09.{json,csv,md}. Pełny149CSV i workbook nie są skróconymi listami.

Wdrożony source_monitor.audit_due_sources: co5min max1źródło,7dni świeżości, nowe/zmienione wcześniej,6h cooldown nieoczekiwanych błędów,30min ochrona running. Lokalny scheduler + Celerybeat. Katalog /editor/sources pokazuje dowody i rzeczywiste Min/Max dat zapisanych Article. Backend testy+Next build poprawne, authenticated desktop/mobile PASS, brak overflow telefonu. source_probe testy8PASS. Wszystkie nowe zmiany backendu sprawdzone celowanymi testami (53włącznymrunie +osobny1apply; agentofficialłącznie31). Nie raportować sumy jako liczby unikalnych testów całego repo.

apply_audited_feeds z wymaganym świeżym signature, ochroną owner/excluded oraz brakiem zmian frequency: zastosowano24zmiany =5naprawRSS (12,15,27,35,44) i19nowychkanałów (80,83,87,90,94,95,97,98,100,101,107,109,112,114,117,118,121,129,132). Gzc79pozostawiony kandydatem do rozpoznania wydań gazety. W katalogu91aktywnych/58kandydatów. Wszystkie19już miały rzeczywiste Article w odczycie17:46. Reportbefore/after reports/applied-audited-feeds-2026-09-09.json. Nie zmieniać starego pliku raportu audytu, który pokazuje stan z chwili kontroli; aktualna konfiguracja jest w DB.

KPRM scraper/html_archive.py zintegrowany z archive.process: dedykowane potwierdzenie strony/daty wydarzenia, data wydarzenia w evidence_note, published_date=None jeśli brak odrębnego dowodu. Listing co60s,296stron,około2957pozycji wg paginacji (nie udowodniona unikatowość). Po pełnym przebiegu godzinny refresh z zatrzymaniem po znanym nakładaniu. O17:46cursorstrona6,importowano już rzeczywiste materiały source61; nie są one fikcyjnie datowane datą wydarzenia.

Znaleziony i naprawiony błąd paginacji Sejmu: search domyślnie50, import_period/title wcześniej brał tylko pierwszą stronę. Teraz offset/limit100 do pustej strony, walidacja tożsamości/powtórzonych stron, bezpieczne ponowienie. official_backfill.backfill_votings_cycle co5min:1tydzień od2023-11-13, frozen cutoff2026-09-09, wspólny lock z aktualnościami, stop przy wyłączonym źródle/błędzie. Pilot13nowych w6.188s; o17:46łącznie154głosowania,next_from2023-12-04,3okresy. Starsze kadencje i pełne roczniki ELI NIE mają jeszcze automatycznego backfillu. Raport official-archive-volume:65854głosowania indeksyIII–X,21275drukówVI–X,164409ELI; indeks != kompletność szczegółów/PDF. Xkadencja4628głosowań,3278druków(wszystkieIDdrukówzgodne).

WPbadanie8wydawców:6publicznychAPI,50967posts/513partiipo100,494/600miniaturwpróbkach. Demagog/Miasto i Ludzie401. Raport wordpress-archive-volume-2026-09-09.{md,json}. APIlinki/bezpiecznefetch/proof dostępne; importer WP partiami JESZCZE NIEWDROŻONY. Największe przyspieszenie kolejnego etapu: API zamiast HTMLperstrona. Ograniczyć fields do metadata, stabilne punkty odcięcia/ID, dedup, źródłowe daty i miniatury, bez cichego automatycznego streszczania.

Pomiary: około2.95mln pendingpages, RP765559hostwww.rp.pl~675pages/h→47.3doby, samodstęp3s→26.6minimum. 7–10tygodni to warunkowy plan znanej obsługiwanej kolejkiHTML, NIEterminpełnego149archiwum; źródła z błędami/brakami mają brakETA. Cała baza17:46=44378Article. Cykl17:46:32active_workers/37eligible_sources,443newarticles,461pages+79maps,72failures,155.44s. To pierwszy potwierdzony32aktywnych po rozbudowie źródeł (wcześniejszy benchmark dochodził do28). Nie trzeba zwiększać cap>32; wyniki24vs32 wcześniej zbliżone, nowa mieszanka zmienia wydajność.

Dysk17:33:67.5GiB wolne,DB1.16GiB. dbstat17:12~92.5%zajmowała kolejka;Article976B,job381B,ArticleContentmieszanka1217B. MiniaturyURLonly.16lokalnychbackupów3.86GiB;backupcodziennyNIEma retencji, nie usunięto żadnej kopii. Model3mln*4KiB+7GiBoficjalne→18.4GiBDB,1nowakopia+10GiBzapas→45.7GiBdodatkowo (mieści się),7kopii→156.4GiBdodatkowo(nie mieści). Potrzebna niezależna kopia i polityka liczby kopii zanim skala urośnie. Nie zatrzymywać importów na hipotetycznym ryzyku; mierzyć wolne miejsce. W importerze istnieje część ArticleContentbody; nie usunięto tekstów. CEST nieznane parse_date zwraca None przez naive guard; poprawę znanych offsetów można zrobić osobno, nie zakładać UTC.

Artefakty dla użytkownika: outputs/archive-research-20260909/Raport-archiwum.md, Archiwum-zrodla-czas-dysk.xlsx (4arkusze,149pełnychwierszy,159formuł; walidacjaXMLbezerror i testzmiany liczbykopii), Pelna-lista-zrodel.csv149wierszy, JSONdowody. Autor XLSX @oai/artifact-tool, builder.local/research-artifacts/build.mjs, mark_artifact_operation_started wykonanyraz. Raport jawnie oddziela pomiary/założenia/braki i wdrożone/niewdrożone metody.

Normalny scheduler poprzednio57954 zatrzymany, teraz sesja8375 USE_SQLITE=true ARCHIVE_WORKERS=32 (networkapproved). Backend/frontend odświeżone Start-Portal.ps1 po sprawdzeniu starych PID13504/21472, teraz nowePIDsprawdzać netstat. Katalogaktualny, credentials.local/admin-login.txt nigdy nie ujawniać. OpłaconeAI klucze/model nadal nieskonfigurowane; brak nowych płatnychcalli.

Następne prace:1)WPmetadataAPIbatch dla potwierdzonych6;2)ELIroczniki w trwałych małych partiach, potem poprzedniekadencje;3)zliczenie pełnych drzewmap i klasyfikacja Polityka/Infor, nie udawać ichkompletności;4)kontrola cachewyszukiwarki (SQLite LocMem=5min i brakpollinguReact, wykryte lecz nienaprawione), później pulpit z licznikiem nowychwyników;5)retencja/iniezależnośćbackupów. Nie restartować schedulera bez potrzeby. Użytkownik oczekuje ciągłości prac, nie przykładowych fikcyjnych nitek.
