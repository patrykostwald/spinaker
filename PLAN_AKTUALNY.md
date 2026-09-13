# spin.clinic — aktualizacja planu i współpraca z Claude

Stan: 14 września 2026. Plan, nie deklaracja wdrożenia. Uzupełnia PDF v3 użytkownika; koryguje jego założenie o automatycznej legalności agregacji. Nie zmieniono Supabase, nie uruchomiono importerów ani wysyłki.

## Zasady pracy i pojęcia — decyzja właściciela

Domyślnie zadania wykonujemy na poziomie Lekki. Przed migracjami, projektowaniem uprawnień, złożonymi zmianami współbieżności lub bezpieczeństwa agent informuje właściciela, dlaczego zaleca wyższy poziom. Nie zmienia ustawień sam i nie zakłada, że większa liczba agentów oznacza szybszy lub tańszy wynik. Zewnętrzne wiadomości, publikacje i wdrożenia wymagające decyzji właściciela nie są zatwierdzane w jego imieniu.

Box oznacza jeden materiał źródłowy, niezależnie od tego, kto go dodał: importer, redakcja lub w przyszłości użytkownik. Wydawca/podmiot to osobny rekord Source. Nitka to uporządkowane odwołania do boxów, nie kopie ich treści. Powtórne dodanie tego samego URL powinno odnaleźć istniejący box; odmienne publikacje o tym samym zdarzeniu pozostają oddzielne. Przed scaleniem kontrolować kanoniczny URL i pochodzenie, nie tylko podobny tytuł.

Jeden użytkownik może mieć jedną reakcję dodatnią lub ujemną i najwyżej jeden komentarz do danego boxa. Wymusić unikalność w bazie, a nie tylko w interfejsie. Zmiana reakcji zastępuje poprzednią; cofnięcie usuwa głos. Edycja komentarza aktualizuje ten sam komentarz z historią moderacyjną, nie tworzy kolejnego. Limity tekstu uwzględniają eksport z linkiem do boxa. Reakcje są opinią użytkowników, nie werdyktem prawdziwości. Robocze nazwy pozostają neutralne (+/-); nazwy medyczne dopiero po sprawdzeniu, czy nie sugerują diagnozy lub potwierdzonego faktu.

Dodawanie URL przez zwykłych użytkowników i tworzenie ich własnych nitek to etap II. W MVP źródła dodaje redakcja i importer; uprawnienia dziennikarzy przyznaje redakcja. Każda ścieżka przechodzi tę samą walidację i kontrolę publikacji.

## Klasyfikacja materiałów

Oddzielamy cztery wymiary: typ podmiotu, typ materiału, temat i oznaczenia dodatkowe. Zachowujemy oryginalną kategorię wydawcy, naszą klasyfikację, metodę i wersję reguł. Nie odgadujemy gatunku wyłącznie po domenie.

- ARTYKUŁ: podstawowy materiał prasowy, w tym news. Szczegółowy podtyp NEWS można zachować bez mnożenia głównych filtrów.
- WYWIAD, REPORTAŻ, OPINIA/ANALIZA: gdy forma wynika z oznaczenia lub materiału; nie z domysłu na podstawie samego zdjęcia.
- FILM, PODCAST, POST: format publikacji. Film może mieć dodatkowy gatunek WYWIAD; post polityka to POST z rolą autora, nie osobny typ.
- OŚWIADCZENIE/KOMUNIKAT: oficjalna wypowiedź lub ogłoszenie; DOKUMENT: pozostały materiał dokumentowy.
- AKT PRAWNY, PROJEKT AKTU/DRUK, GŁOSOWANIE, ORZECZENIE, OBWIESZCZENIE, RAPORT, ZBIÓR DANYCH/REJESTR: rozróżnienia instytucjonalne potrzebne do filtrów. Ustawa jest podtypem aktu prawnego, nie każda propozycja ustawy jest obowiązującym prawem.
- REKLAMA: materiał reklamowy. SPONSOROWANE to dodatkowe jawne oznaczenie finansowania, niezależne od formatu i gatunku.
- INNE / DO KLASYFIKACJI: jawny brak rozpoznania, z kolejką do poprawy.

WZMIANKA to przede wszystkim relacja: materiał wspomina osobę, firmę lub temat. Zapisujemy powiązanie z boxem i dowód, jeśli wolno go przetwarzać. Nie tworzymy fikcyjnej odrębnej publikacji z każdej wzmianki. Rzeczywista samodzielna krótka notka może mieć podtyp WZMIANKA. Tematy (polityka, zdrowie, dom, gry itd.) są odrębnymi filtrami.

## Zgłoszenia problemów do administratora

Każdy problem dostaje rekord ze źródłem i podmiotem, URL, rodzajem przeszkody, czasem, ostatnią próbą, metodą pobierania, statusem, zakresem brakujących danych i następnym krokiem. Rozróżniamy błąd parsera, awarię, limit 429, blokadę techniczną, brak archiwum, nieustalone uprawnienia i odmowę. Chwilowa awaria nie uruchamia automatycznie prośby o licencję.

Panel grupuje zgłoszenia po podmiocie i pokazuje listę żądanych URL do boxów, liczbę braków, próbki oraz proponowany zakres współpracy. Administrator może zatwierdzić szkic prośby o dostęp i zaproszenia do współtworzenia, poprawić go lub odrzucić. Wysyłka pozostaje ręczna w MVP. Dziennik decyzji przechowuje zatwierdzoną wersję i odbiorcę; powiadomienia nie mogą powtarzać się dla każdej nieudanej próby.

## Potwierdzone zasoby

- CSV użytkownika: 601 źródeł; 24 w trybie RSS, 4 API, 573 homepage_links. Wszystkie enabled=true, co nie oznacza sprawdzonej dostępności lub praw.
- 239 wpisów łączy full_text i protected_by_copyright. Wymagają indywidualnego ustalenia podstawy przetwarzania, nie automatycznego włączenia pełnego tekstu.
- PDF podaje jeszcze 71 źródeł i interwał w sekundach; CSV używa rate_limit_per_min. Obowiązuje jawna jednostka, nie domysł.
- Connector Supabase: list_projects zwrócił pustą listę, ale po podaniu ID get_project potwierdził projekt spin-clinic-mvp (yyrwcggmksjhzeaovrvl), ACTIVE_HEALTHY, eu-central-1. Odczyt listy tabel potwierdzono poniżej; polityki i szczegółowy schemat wymagają audytu.
- Lokalny projekt ma wcześniejszy backend i importery. Przed nową implementacją porównać kod Claude, stare rekordy i schemat Supabase. Nie pisać wszystkiego od zera ani nadpisywać starej bazy.

## Etap I — działający agregator

### Rozszerzenie MVP — ostatnia decyzja właściciela

- Aplikacja od startu: proponowany pierwszy wariant to instalowalna PWA, wspólny kod z portalem. Nie oznacza obecności w App Store/Google Play. Jeśli sklepy są warunkiem startu, potrzebny osobny zakres i proces publikacji.
- Konto: zapisane tematy, źródła i wybrane nitki pod sekcjami redakcyjnymi; plusy dla nitek, maksymalnie jeden głos użytkownika na nitkę, możliwość cofnięcia, kontrola po stronie serwera.
- Alerty od MVP: zapis reguł hasło/źródło/temat, centrum powiadomień, opcjonalny push i e-mail. Zgoda per kanał, wyłączenie/subskrypcja, częstotliwość, ciche godziny i deduplikacja. Push zależy od przeglądarki, systemu, instalacji i zgody; zapewnić wariant in-app. Nie obiecywać natychmiastowego dostarczenia.
- Płatny dostawca AI na MVP poprzez wymienny adapter. Istniejący prototyp wykorzystuje OpenAI do wyszukiwania internetowego; Mistral EU jest drugim dostawcą pilotażowym do klasyfikacji, porządkowania kandydatów i embeddings. Zakres funkcji regionalnych musi przejść test. Szczegóły: `docs/AI_PROVIDER_PLAN.md`.
- Równoległy kierunek lokalnego modelu: zestaw ocenionych przykładów, oddzielny zbiór testowy, wersje reguł, pomiar trafności powiązań, potem porównanie modeli z odpowiednią licencją. RAG przed treningiem; nie używać automatycznie wszystkich artykułów lub odpowiedzi dostawcy do uczenia. Trening po sprawdzeniu praw, jakości danych i sprzętu. Nie blokuje startu MVP.
- Publiczna strona „Jak działamy”: zakres źródeł, metoda zbierania i aktualizacji, działanie wyszukiwarki i Dr Spina, znaczenie ocen, znane braki, korekty oraz data ostatniej zmiany metodologii. Nie publikujemy sekretów, zabezpieczeń ani szczegółowych wag rankingu umożliwiających manipulację.
- B2B/PR od początku w modelu danych: liczba wzmianek, dynamika tematów, rozkład źródeł, historie zmian i eksport z pochodzeniem oraz zakresem pokrycia. Brak podstaw do deklarowania zasięgu, wpływu lub sentymentu jako zmierzonych faktów bez metodologii. Oferta dotyczy uprawnionych analiz, nie sprzedaży cudzych pełnych tekstów ani prywatnej aktywności użytkowników.
- Analityka reakcji od pierwszego dnia: append-only zdarzenia publikacji boxa/nitki, wyświetlenia w uzgodnionym znaczeniu, zapisania, przypięcia, plusa/minusa, komentarza i zmiany widoczności. Zapisujemy czas zdarzenia, wersję materiału, kanał wejścia i pseudonimowy identyfikator potrzebny do agregacji; zmiana głosu tworzy zdarzenie audytowe, a bieżący stan nadal pozostaje unikalny per użytkownik i obiekt. Pozwala to mierzyć przebieg reakcji w czasie oraz pierwsze pojawienie się haseł w komentarzach.
- Analiza komentarzy oddziela tekst źródłowy od tekstu użytkownika. Hasła mają wersjonowany słownik/metodę wykrycia, czas pierwszego wystąpienia i liczność; nie nazywamy automatycznej klasyfikacji opinią publiczną ani reprezentatywnym sondażem. Dane B2B pokazujemy zagregowane z minimalnym progiem liczebności, zakresem źródeł i okresem. Nie sprzedajemy identyfikowalnej historii użytkowników; prywatna aktywność i ukryte elementy profilu nie trafiają do publicznych ani klienckich raportów. Użytkownik dostaje jasną informację o analityce i mechanizmy realizacji praw do danych.
- Domena spin.clinic w home.pl pozostaje. Rozpoznany pakiet Hosting Biznes Apache nie jest potwierdzonym środowiskiem dla stałych workerów, Dockera lub Node. Pilotaż importerów może działać na PC; nie kupować GPU ani zmieniać hostingu przed pomiarem.

Aktualizacja ze zrzutu właściciela: dwa pakiety Hosting Biznes Apache; panel pokazuje odpowiednio 92,09 GB i 100,00 GB dostępnego miejsca. To miejsce usług hostingowych, nie pamięć RAM ani pojemność Supabase. Dokumentacja home.pl podaje dla Hosting Biznes m.in. limit pamięci 256 MB i czas życia procesu 300 s; parametry konkretnej umowy trzeba potwierdzić. Dlatego nie planujemy na tej podstawie stale działającego workera ani modelu AI na hostingu Apache. Domena i ewentualna poczta pozostają w home.pl; ingest na PC w pilotażu, później VPS po pomiarze. Hosting strony Next.js wymaga potwierdzenia zgodnego środowiska. Nie kupiono nowych usług.

### Potwierdzony odczyt Supabase

Odczyt publicznego schematu: 15 tabel, wszystkie raportują RLS enabled. sources ma 601 wierszy; boxes, box_versions, entities, box_entities, tags, box_tags, quotes, threads, thread_boxes, profiles, box_votes, box_comments, thread_votes i thread_comments raportują 0 wierszy. To odczyt metadanych, nie pełny audyt polityk RLS. Brakuje w tym wykazie tabel personalizacji, subskrypcji alertów, kolejki dostarczeń i rejestru uprawnień. Nie wykonano migracji. Lokalna baza materiałów i zdalna baza katalogu są nadal odrębnymi systemami.

1. Wskazać właściwy projekt Supabase i wspólne repozytorium. Odczytać schemat, migracje i uprawnienia, bez automatycznych zmian produkcyjnych.
2. Ujednolicić katalog, identyfikatory i jednostki limitów. Oddzielić rodzaj podmiotu, temat oraz typ materiału. ORGANIZACJA to grupa z podtypami partia, fundacja, stowarzyszenie, związek zawodowy, organizacja pracodawców; nie zastępuje ARTYKUŁ/WYWIAD/DOKUMENT.
3. Zbudować rejestr zasad dostępu i wykorzystania opisany poniżej.
4. Uruchomić kontrolowany pilotaż: API instytucji, RSS mediów, mapy witryn oraz paginowane archiwum HTML. Zmierzyć poprawność dat, duplikaty, skuteczność, tempo i miejsce.
5. Rozszerzać pobieranie bieżące i historyczne. Kolejka z trwałym kursorem, wspólne limity na host, ponawianie z odstępem, reakcja na 429/Retry-After, brak obchodzenia blokad. Homepage_links nie oznacza pełnego archiwum.
6. Podłączyć publiczne boxy, personalizację, wyszukiwanie, reakcje i komentarz oraz zgłoszenie błędu. Redakcyjne nitki i szkice AI publikowane po zatwierdzeniu redakcji.
7. Test odzyskania kopii, uprawnień i izolacji danych przed publicznym uruchomieniem.

Publiczne API wybiera tylko dozwolone pola. Samo ukrycie treści w interfejsie nie zabezpiecza danych. Pełne treści, jeśli mają ustaloną podstawę przetwarzania, pozostają w prywatnej warstwie, bez dostępu anonimowego i bez automatycznego udostępniania przez widoki lub Storage.

## Rejestr uprawnień i kontrola publikacji

To program wykonujący jawne reguły, wspierany przez AI przy czytaniu warunków. AI nie jest prawnikiem i nie zatwierdza samodzielnie niejednoznacznych przypadków.

### Oddzielne decyzje

Dla każdego wydawcy, ścieżki i wyjątku dotyczącego materiału przechowujemy oddzielnie:

- możliwość technicznego pobrania i limit;
- prawo do zapisania metadanych;
- wyświetlenie tytułu, cytatu i miniatury — każde pole osobno;
- sposób użycia miniatury: odnośnik, osadzenie, lokalna kopia;
- zapis pełnej treści i okres retencji;
- analizę/RAG oraz trening modelu — osobne zastosowania;
- wymagane oznaczenie, link, zakres komercyjny, termin i warunki zgody.

Stany: nieustalone, wymaga przeglądu, dozwolone w określonym zakresie, zabronione, wygasłe. Każda decyzja ma podstawę, URL lub dokument dowodowy, datę sprawdzenia, wersję i osobę zatwierdzającą. Zgodność z robots.txt jest sygnałem technicznym, nie licencją. RSS, domena urzędu i hash także nie stanowią samodzielnego dowodu praw.

Program monitoruje zmiany warunków. Wygaśnięcie lub cofnięcie zgody zatrzymuje odpowiednie użycie, usuwa je z publikacji i uruchamia przegląd kopii, indeksów oraz cache. Historia audytu nie oznacza obowiązku zachowania zakazanej treści na zawsze.

Brak ustalonej podstawy nie włącza pełnego tekstu ani miniaturek. Dopuszczony węższy wariant boxa może działać tylko w zatwierdzonym zakresie; w przeciwnym razie rekord pozostaje niepubliczny do decyzji.

### Kontakt z wydawcą

1. Grupowanie źródeł po rzeczywistym podmiocie i zakresie domen, aby nie dublować próśb.
2. Lista brakujących uprawnień i potwierdzony adres kontaktowy.
3. Szkic jednej wiadomości: opis spin.clinic, pola boxa, sposób linkowania, planowane zastosowania, prośba o RSS/API/archiwum i warunki współpracy.
4. Załącznik: przykładowy układ i niewielka reprezentatywna lista URL. Pełny spis URL można przygotować wewnętrznie; nie wysyłamy zbioru cudzych treści lub obrazów bez potrzeby.
5. Człowiek zatwierdza konkretną treść, odbiorcę i wysyłkę. MVP: wysyłka ręczna. Bez automatycznej wysyłki i ponagleń.
6. Odpowiedź do przeglądu; zapis dokładnego zakresu zgody. Brak odpowiedzi nie oznacza zgody. Zgoda na box nie oznacza zgody na trening ani wszystkich fotografii osób trzecich.

## Etap II

UGC/Izba Przyjęć, alerty, płatne funkcje, B2B i rozbudowana obsługa zgód. Zakres dostępu płatnego nigdy nie rozszerza uprawnień do cudzej treści. Sponsor nie zmienia archiwum.

## Etap III

Własne zaplecze AI, wyszukiwanie hybrydowe, bardziej zaawansowane osie i BIP. Najpierw RAG i pomiar jakości na przykładach ocenionych przez redakcję; dopiero później decyzja o dostrajaniu modelu i sprzęcie GPU. Przyrost bazy nie jest treningiem modelu. Qdrant z PDF pozostaje kandydatem; porównać z wyszukiwaniem wektorowym w istniejącym Postgres przed dodaniem osobnej usługi.

## Programy na komputerze

Codex/Claude piszą i testują kod; właściciel nie musi przepisywać go ręcznie do VS Code. Docelowy pakiet ma wygodny start/stop/status, trwałe kolejki, logi, kontrolę miejsca oraz instrukcję konfiguracji. Komputer musi mieć połączenie z internetem i nie usypiać podczas pracy. Po restarcie zadania wznawiają się od kursora; tylko jeden scheduler przydziela dane zadanie.

Same programy pobierające dane nie korzystają z abonamentu AI. Koszty AI występują tylko przy jawnie podłączonych wywołaniach modelu; dochodzą koszty bazy, transferu i sprzętu. Sekrety workerów wyłącznie lokalnie/na serwerze, nie w przeglądarce, rozmowie lub repozytorium. Uprawnienia workera ograniczone do niezbędnych operacji.

## Współpraca Codex i Claude Code

Nie jesteśmy jednym modelem i nie mamy wspólnej puli limitów. Wspólne repozytorium to wersjonowany kod oraz dokumenty, nie cała baza danych ani klucze.

1. Ustalić, gdzie Claude zapisał aktualny kod i czy istnieje prywatne repozytorium. Użyć istniejącego, jeśli jest; nie publikować starego folderu bez przeglądu sekretów i plików bazy.
2. Oddzielne kopie robocze/worktree i gałęzie dla każdego agenta. Nie pracować równocześnie na tym samym checkout ani współdzielonych plikach.
3. Wspólny kontrakt danych i tablica zadań: właściciel, status, zależności, kryteria ukończenia, zmienione pliki, testy, commit i blokady.
4. Proponowany podział: Claude — adaptery źródeł; Codex — kolejka, kontrakt, integracja portalu i testy. Przydział dopiero po odczycie obecnego kodu Claude.
5. Jeden właściciel migracji w danym czasie. Obaj testują na środowisku deweloperskim; produkcyjne migracje i wdrożenia wymagają zatwierdzenia właściciela.
6. Checkpoint przed limitem: co gotowe, czego nie uruchamiać i następny krok. Status limitów tylko z rzeczywistego odczytu, z czasem pomiaru; brak danych to niewiadoma.

Na razie brak automatycznego mostu między agentami. Najprostszy start: właściciel otwiera odpowiednią kopię projektu w Claude Code i przekazuje plan. Późniejszy koordynator może obsługiwać przekazania, ale nie omija limitów ani zatwierdzeń.

### Rozpoznanie lokalne i GitHub

Folder C:\Users\User\spin-clinic nie ma .git. Na pulpicie istnieje C:\Users\User\Desktop\spin.clinic z plikami CSV, urls.txt i skryptami; harvest_metadata.py ma 0 bajtów (odczyt 13 września), więc nie zawiera implementacji. Nie uruchamiano tych skryptów. Connector GitHub zwrócił pustą listę repozytoriów — nie dowodzi to braku repozytorium na koncie. Autoryzacja GitHub została ukończona. Odczyt repozytorium patrykostwald/spinaker potwierdził pięć dokumentów i brak kodu. Lokalna gałąź codex/plan-2026-09-13 zawiera przygotowaną aktualizację planu. Nie wykonano push. Starszą wersję na GitHub należy najpierw odnaleźć i zachować jej historię, potem aktualizować na osobnej gałęzi według tego planu.

## Kolejność wykonania i kryteria odbioru dla Codex/Claude

Poniższe zadania są otwarte, o ile nie podano inaczej. Dokumentacja nie jest potwierdzeniem działającej funkcji. Nie wykonywać całej listy bez odczytania bieżącego checkpointu i zakresu upoważnienia.

1. REPO-01 — bezpieczne dołączenie kodu lokalnego do spinaker. Właściciel: jeden agent integrujący. Przegląd sekretów, wykluczenie baz/logów, osobna gałąź, zachowana historia. Odbiór: powtarzalny build i testy z czystej kopii, brak sekretów i danych użytkowników w zmianach. Obecnie repo ma dokumentację; kod nadal lokalny.
2. DATA-01 — dokładny odczyt schematu i polityk Supabase, porównanie z lokalnym Django. Właściciel: agent integrujący. Odbiór: mapa pól i tożsamości Source/Article/Box, polityka dat nieznanych, plan deduplikacji oraz migracja na środowisku testowym z rollbackiem. Zachować stare identyfikatory w mapowaniu. Nie zakładać, że tabele mają zgodne kontrakty.
3. RIGHTS-01 — rejestr zasad wykorzystania i bramka publikacji. Zależność: DATA-01. Odbiór: niedozwolone pola nie występują w publicznym API, brak obejścia przez storage/widoki, wygasła zgoda wstrzymuje zakres użycia, dowody i decyzje audytowalne.
4. INGEST-01 — kolejka trwała i jeden scheduler. Zależność: kontrakt DATA-01 i prawa RIGHTS-01. Odbiór: restart bez utraty kursora, brak podwójnych zapisów, respektowanie ograniczeń hosta, timeoutów i 429. Start/stop/status z komputera właściciela.
5. ADAPTER-01 — pilotaż API/RSS/archiwum. Może go rozwijać Claude równolegle do INGEST-01 na uzgodnionych fixture i interfejsie. Odbiór: poprawne źródło, URL, data publikacji odróżniona od czasu pobrania, jawne braki miniatur, raport stron i błędów. Archiwum musi przechodzić paginację/mapy, a nie tylko stronę główną.
6. ADMIN-01 — panel problemów i próśb do wydawców. Zależność: RIGHTS-01 i zdarzenia ingestu. Odbiór: grupowanie per podmiot, lista URL, brak duplikatów zgłoszeń, szkic bez automatycznej wysyłki, jawna decyzja administratora.
7. PORTAL-01 — podłączenie feedu, wyszukiwania, kont i personalizacji do uzgodnionej bazy. Odbiór: wyniki historyczne i nowe, filtry gatunku niezależne od tematów, brak dostępu do cudzych ustawień, reakcja i jeden komentarz wymuszone w bazie, prywatna historia profilu domyślnie.
8. APP-01 — PWA i alerty. Zależność: konta, URL boxa i kanał zdarzeń. Odbiór: instalacja na wspieranych urządzeniach, poprawny fallback, zgoda push, e-mail z rezygnacją, jedna dostawa danego alertu na kanał, reguły częstotliwości. Cache nie przechowuje prywatnych odpowiedzi między kontami. PWA jest propozycją pierwszej aplikacji; sklepy wymagają osobnego potwierdzenia zakresu.
9. AI-01 — OpenAI i Mistral przez wspólny adapter; wyszukiwanie oraz szkice do 15 powiązanych materiałów. Odbiór: wspólny zestaw ewaluacyjny, wyłącznie istniejące i dozwolone ID boxów, daty i pochodzenie, brak fikcyjnych linków, granica kosztu/liczby prób oraz zatwierdzanie przez redakcję.
10. AI-LOCAL-01 — równoległe przygotowanie ewaluacji: kilkadziesiąt różnorodnych tematów, poprawne/brakujące powiązania ocenione przez redakcję, osobny test bez przecieku danych treningowych. Uruchomienie modelu dopiero po poznaniu CPU/RAM/GPU i licencji. Odbiór: porównanie jakości, czasu i kosztu z AI-01. Trening nie jest obowiązkowym warunkiem startu.
11. B2B-01 — podstawy analityki PR w MVP, pełna płatna oferta w II etapie. Odbiór: jawny mianownik pokrycia źródeł, deduplikacja, okres pomiaru i eksport dozwolonych danych; bez obietnicy pełnego internetu, zasięgu lub obiektywnej oceny nastroju.
11a. ANALYTICS-01 — dziennik zdarzeń i agregaty reakcji od premiery. Odbiór: chronologia reakcji i komentarzy, pierwsze wystąpienie hasła odtwarzalne według wersji reguł, wykluczenie ruchu technicznego, retencja i usuwanie danych, test braku dostępu do aktywności innego użytkownika oraz raporty B2B wyłącznie po agregacji i progu liczebności.
12. RELEASE-01 — bezpieczeństwo, jakość i uruchomienie. Odbiór: test odtworzenia kopii, rozdzielone środowiska, HTTPS i sekrety, test uprawnień, limity i moderacja, monitoring importerów oraz kosztów. Właściciel zatwierdza publiczne wdrożenie i konfigurację domeny. Dopiero wtedy materiał pilotażowy prezentuje faktycznie dostępne funkcje.

W każdym przekazaniu zapisać: zadanie, gałąź/commit, zmienione pliki, wykonane testy, znane błędy, polecenie uruchomienia i następny krok. Nie wpisywać sekretów ani kopii danych użytkowników. Nie zmieniać migracji drugiego agenta w trakcie jego pracy. Nie wznawiać starego schedulera przed uzgodnieniem bazy docelowej.

## Stan a obietnice i termin startu

Potwierdzone: dostęp do projektu Supabase, katalog 601 źródeł, 15 tabel publicznych z raportowanym RLS, dostęp do repozytorium dokumentacyjnego i lokalny kod wcześniejszego prototypu. Niepotwierdzone jako obecnie działające produkcyjnie: integracja portalu z Supabase, import do boxes, PWA, alerty, płatne AI, lokalny model, pełny audyt praw i bezpieczeństwa. Historyczne testy prototypu nie zastępują testów nowej integracji.

Termin MVP ustalić po REPO-01/DATA-01 i pilotażu ingestu, na podstawie rzeczywistych przeszkód. Nie uzależniać startu od zebrania wszystkich archiwów; pokazywać znane zakresy i braki. Pełność polskiego internetu i całkowity brak sporów nie są gwarantowalnymi kryteriami odbioru. Celem jest udokumentowane pochodzenie, legalny zakres użycia i możliwość korekty.

## Informacje potrzebne od właściciela

Parametry komputera do ingestu i ewentualnego modelu (RAM, procesor, GPU/VRAM), potwierdzenie czy PWA wystarcza na start, adres skrzynki nadawczej do alertów i kontaktu oraz budżet prób AI. Sekrety wpisywane wyłącznie przez bezpieczne logowanie lub lokalną konfigurację. Zakupy i produkcyjne wdrożenie po przedstawieniu konkretnego wariantu.

## Dokumentacja referencyjna

- home.pl, parametry: https://pomoc.home.pl/baza-wiedzy/parametry-bezpieczenstwa-serwerow-home-pl
- home.pl, CRON: https://pomoc.home.pl/baza-wiedzy/jak-korzystac-z-cron-na-hostingu

- Supabase MCP: https://supabase.com/docs/guides/ai-tools/mcp
- Claude Code: https://code.claude.com/docs/en/overview
- Dyrektywa 2019/790, art. 4 i 15: https://eur-lex.europa.eu/eli/dir/2019/790/oj/eng

Kwestie prawne planu wymagają weryfikacji właściwej dla konkretnego wykorzystania; dokument nie jest opinią prawną ani gwarancją legalności.
