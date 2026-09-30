# Audyt UX fazy 2 — zlecenie 055

Data: 30.09.2026. Audyt kodu wykonany **przed zmianami implementacji**. Zakres: pełna ścieżka czytelnika w `frontend-spin/app` i `packages/ui/src`. To przegląd ekspercki z ośmiu perspektyw, nie badanie z rzeczywistymi uczestnikami ani deklaracja zgodności WCAG. Bez uruchamiania serwera; zrzuty i weryfikację wizualną 1440/390 wykonuje Claude.

## Konsylium i wspólna decyzja

- UI: zachować Montserrat, czarne powierzchnie i niebieski akcent; ograniczyć konkurujące nagłówki i rozdzielić nawigację od działań.
- UX telefonu / jedna ręka: podstawowe działania na końcu krótkiego kroku; pełnoszerokie pola; przestawianie materiałów przyciskami obok przeciągania.
- Architektura informacji: `/konto` jako jeden punkt powrotu. „Twoje wiadomości” to SavedTopic, „Twoje nitki” to uporządkowane źródła. Nie nazywać obu rzeczy nitkami.
- Czytelnik 60+: tekst formularza co najmniej 16 px, czytelne opisy, minimum 44 × 44 px dla celów dotykowych; ikona wymaga nazwy.
- Nowy użytkownik: wyjaśnić cel nitki jednym zdaniem, doprowadzić do pierwszego zapisanego tematu bez wymagania publikacji.
- Bezstronny wydawca: brak politycznie wybranych sugestii obserwowania; wyszukiwanie inicjuje czytelnik. Opinie dotyczą argumentacji nitki, nie wartości osoby. AI i czytelnik mają osobne oznaczenia autorstwa.
- Dostępność: etykiety, logiczne nagłówki, widoczny fokus, status zapisu w `aria-live`, sterowanie klawiaturą, brak wymaganego gestu przeciągania. Do sprawdzenia wizualnego: kontrast wszystkich motywów, zoom 200/400%, fokus niezasłonięty na telefonie.
- Retencja: powrót do wybranych tematów, obserwacji i nieprzeczytanych informacji. Bez przymusu push, domyślnych zgód marketingowych, liczników presji i serii codziennych wizyt.

P0 = bezpieczeństwo publikacji/danych i utrata pracy. P1 = domknięcie głównej ścieżki fazy 2. P2 = dalsze ulepszenia istniejącej części serwisu.

## 1. Pierwsza wizyta `/`

Działa: `kit/home/HomeHero.tsx` mówi wprost „Konsylium AI bada przekaz polityków”, pokazuje wspólną miarę i prowadzi do diagnoz. `HomePage.tsx` oddziela Klinikę od wiadomości.

Tarcia: `HomePage` i `HomeHero` mają dwa h1; liczne sekcje i nazwa `HomeThreads` mogą zacierać różnicę między paskiem newsowym a nitką kontekstową. Nowicjusz nie widzi jednej drogi do własnego miejsca.

Propozycja: **P1** czytelne wejście „Mój spin.clinic” w istniejącym sterowaniu kontem; **P2** uporządkować nagłówki i skrócić dalsze sekcje po badaniu pierwszych 5 sekund.

1440: nagłówek → zdanie celu + główne CTA → diagnozy → wiadomości. 390: logo/menu → cel → CTA na całą szerokość → jedna diagnoza → wiadomości; konto dostępne z nawigacji.

## 2. Klinika i diagnoza

Działa: `components/clinic/ClinicPage.tsx`, `SpinDetail.tsx`, `SpinSummary.tsx` rozdzielają wpis, werdykt, uzasadnienie, źródła, modele i ograniczenia. Źródła w twierdzeniach są rozwijane świadomie.

Tarcia: po przeczytaniu diagnozy brak przejścia do nitek zawierających oryginalny wpis. Rozbudowane sekcje i wewnętrzne przewijanie wymagają oceny na małym ekranie.

Propozycja: **P1** „W nitkach” po diagnozie, wiązanie po konkretnym URL oryginału; **P2** ocena długości i wewnętrznych przewijań. Nigdy nie zmieniać tekstu diagnozy AI.

1440: wpis i podsumowanie → uzasadnienie/źródła → W nitkach → opinie. 390: jedna kolumna; źródła rozwijane; karty nitek pionowo.

## 3. Materiał / box i źródła

Działa: `MaterialDetails.tsx` składa oś czasu, reakcje i materiały powiązane; `MaterialBox.tsx` prowadzi do oryginału. Rozróżnienie źródła i kontekstu jest zachowane.

Tarcia: nie ma prawdziwego paska „W nitkach”; `ContextThreadStrip.tsx` zawiera wyłącznie fikcyjny przykład używany w treściach informacyjnych.

Propozycja: **P1** rozszerzyć komponent o tryb danych po `article_id`, pozostawić jawnie oznaczony przykład. Nie wyprowadzać faktycznego członkostwa z podobieństwa tytułów.

1440: materiał → oś → 3 karty W nitkach → powiązane źródła. 390: materiał → źródło → karty jedna pod drugą; długie URL łamane.

## 4. Osoba publiczna i profil użytkownika

Działa: `PublicFigureProfile.tsx` pokazuje funkcje, źródła, głosowania i diagnozy, bez oceny osoby. `AccountProfile.tsx/PublicAccountProfile` respektuje prywatną historię.

Tarcia: brak obserwowania; publiczna aktywność zwraca nazwę użytkownika, ale bez ID wymaganego do jednoznacznego obserwowania. Nie należy wysyłać nazwy w polu liczbowego ID ani zgadywać tożsamości.

Propozycja: **P1** jeden `FollowButton` dla figure/user/thread; publiczne dane autora rozszerzyć o ID; połączyć profil osoby z nitkami zawierającymi materiały o niej, jasno opisać podstawę dopasowania. Zachować prywatną historię.

1440: nagłówek profilu + Obserwuj → zakładki → treść → W nitkach. 390: nazwa → Obserwuj ≥44 px → zawijana nawigacja → treść.

## 5. Rejestracja / logowanie

Działa: `AccountDialog.tsx`, `Dialog.tsx`, `lib/api.ts` korzystają z sesji i CSRF, mają etykiety i autouzupełnianie.

Tarcia: brak odzyskania hasła, informacji o weryfikacji e-mail i akceptacji wersji zasad; po rejestracji okno tylko się zamyka. Brak jednolitego rozpoznawania 404 operacji zapisu (`apiWrite` gubi status HTTP).

Propozycja: **P0** zachować status HTTP błędów; zgoda na zasady bez zaznaczenia z góry, wersja przesyłana do API; **P1** reset hasła, ekran potwierdzenia e-mail, przejście do `/konto` po rejestracji. Datę zgody ustala serwer, nie zegar klienta.

1440: wyśrodkowany dialog do 480 px, etykiety nad polami. 390: dialog w szerokości ekranu, pola 16 px, jedna akcja główna i czytelny powrót do logowania.

## 6. Pierwsze kroki po rejestracji

Działa: istnieją `SavedTopic`, `PersonalizedNews.tsx`, `MaterialFilters.tsx` i API feed; nie potrzeba drugiego modelu tematów.

Tarcia: onboarding nie istnieje; panel odsyła do `/profile`; zapisane tematy mają limit 10, zlecenie wymaga 1–5. Paski lokalne z głównej i paski konta są opisane obok siebie bez jasnej hierarchii.

Propozycja: **P1** trzy pomijalne kroki: wybierz temat i nazwę paska → samodzielnie znajdź osobę do obserwowania → zobacz pierwszy pasek w „Twoich wiadomościach”. Zapamiętać pominięcie na tym urządzeniu per konto; synchronizacja onboardingu wymaga osobnego kontraktu 053. Bez domyślnych obserwacji.

1440: krótki onboarding nad panelem; niżej 4 skróty i menu 220 px + treść. 390: krok/3 → jedno zadanie → Dalej/Pomiń → skróty 2 × 2 → sekcje.

## 7. Budowa i publikacja nitki

Działa: `MojaNitkaEditor.tsx` ma wyszukiwarkę Bazy, `resolveLink`, limity notatek 280, strzałki kolejności z odzyskiwaniem fokusu. `ThreadEditor.tsx` to osobny istniejący warsztat zespołu/dziennikarzy — nie należy mieszać jego uprawnień z nitkami czytelników.

Tarcia: bardzo długi formularz, zapis tylko ręczny, publikacja pojedynczym checkboxem, brak podglądu czytelnika i blokady niepotwierdzonego e-mail. Zmiana opublikowanej nitki może przypadkowo stać się publiczna przy autozapisie.

Propozycja: **P0** autozapis wyłącznie prywatnego szkicu, serializacja zapisów, brak nadpisywania zmian powstałych w czasie żądania; ochrona wyjścia z niezapisanymi zmianami. Publikacja tylko jawnie po weryfikacji e-mail i potwierdzeniu zasad. Opublikowana nitka wymaga ręcznego zatwierdzenia zmian. **P1** 5 kroków: tytuł/pytanie, materiały, kolejność/notatki, podgląd, publikacja; przeciąganie uzupełnia przyciski.

1440: kroki w jednym rzędzie → formularz max 900 px → status i akcje. 390: „Krok n z 5”, zawijana lista kroków → jedna kolumna → Wstecz/Dalej na końcu; podgląd taki sam jak publiczna oś.

## 8. Powrót następnego dnia

Działa: są prywatne ulubione, zapisane tematy i historia reakcji w `MojeKonto.tsx`.

Tarcia: brak powiadomień, licznika nieprzeczytanych, obserwowanych i nowych diagnoz. `/nitki` nie ma sortowania ani filtra tematu, karta nie rozróżnia typu autora od popularności.

Propozycja: **P1** cztery skróty: Twoje wiadomości, Twoje nitki, Obserwowani, Powiadomienia; sekcje danych z kontraktu, oznaczanie pojedynczych/wszystkich jako przeczytane; najnowsze diagnozy obserwowanych osób przez istniejące API. Sortowanie globalne na serwerze, nie tylko jednej wczytanej strony. Dr. Spin wyróżniony na podstawie istniejących danych, bez zgadywania po nicku.

1440: powitanie → skróty → menu/treść; lista nitek w dwóch kolumnach, filtry ponad listą. 390: skróty 2 × 2 → nowe wiadomości → powiadomienia z czytelną datą → pionowe karty nitek.

## 9. Telefon / aplikacja

Działa: `frontend-spin/app/manifest.ts` deklaruje aplikację standalone; istnieje mobilna warstwa kitu. `CommandPanel.tsx` ma wskazówkę instalacji dla osobnego panelu.

Tarcia: brak pomocy instalacji w koncie czytelnika; sam manifest nie potwierdza pełnej instalowalności, offline ani działania push. Długie tytuły, poziome paski i sticky savebar wymagają regresji 390 px.

Propozycja: **P1** pomoc instalacji w ustawieniach, responsywny panel i kreator bez poziomego przewijania strony, obsługa safe area; preferencje push wyłącznie pod flagą. Implementacja subskrypcji i aplikacji należy do 054. **P2** test fizycznych urządzeń i instalacji poza zakresem kodowego audytu.

1440: pomoc w ustawieniach. 390: Ustawienia → aplikacja na telefonie → instrukcja przeglądarki; brak automatycznego pytania o push.

## 10. Ustawienia, prywatność, usunięcie

Działa: `AccountProfile.tsx` ma świadome udostępnienie aktywności, `ThemeSwitcher.tsx` istniejące motywy, strony zasad/prywatności wskazują operatora.

Tarcia: brak e-mail, jego statusu, eksportu, usunięcia i preferencji powiadomień w panelu. Rozproszone ustawienia utrudniają znalezienie prywatności.

Propozycja: **P0** eksport JSON pobierany wyłącznie na żądanie; usunięcie wymaga hasła i wpisania `USUŃ`, czyści cache sesji dopiero po sukcesie. **P1** profil publiczny, motyw, e-mail/weryfikacja, reset hasła, email_digest i flagowane preferencje push w `/konto`. Przy 404 spokojny stan, nigdy komunikat o udanym zapisie.

1440: ustawienia w grupach Profil / Powiadomienia / Bezpieczeństwo; strefa usunięcia na końcu. 390: kolejno te same grupy, etykiety nad polami, potwierdzenie usunięcia rozwijane na żądanie.

## Wiążące zasady projektowe fazy 2 — także 053/054

1. Hierarchia: jeden h1 strony, krótki opis, h2 sekcji. Jedno główne działanie w kroku. „Mój spin.clinic” to konto; „Twoje wiadomości” to 1–5 zapisanych pasków; „nitka kontekstowa” to źródła w kolejności autora.
2. Siatka: szerokość płynna do 1200 px; panel desktop menu 220 px i `minmax(0,1fr)`; odstępy 8/16/24/32 px. Na 390 px marginesy 16 px, jedna kolumna, skróty 2 × 2. Każde dziecko grid/flex może się zwężać (`min-width:0`), długie teksty łamane. Nie maskować błędów globalnym `overflow-x:hidden`.
3. Typografia/kolor: istniejące tokeny `--sc-*`, Montserrat; treść i pola 16 px, interlinia 1.6; metadane co najmniej 14 px. Niebieski akcent oznacza działanie, nie obóz polityczny. Status ma tekst, nie tylko kolor. Bez nowych gradientów i dekoracyjnych neonów.
4. Cele i fokus: co najmniej 44 × 44 px; widoczny fokus tokenem `--sc-focus`, etykiety formularzy niezależne od placeholderów. Podgląd i zmiana kolejności działają bez myszy. Ruch ograniczony zgodnie z preferencją systemową.
5. Stany: ładowanie ma `role=status`; pusty stan mówi co można zrobić dalej. 404 kontraktu = funkcja jeszcze niedostępna, bez czerwonego błędu i bez ponawiania w pętli. Pozostałe awarie: krótki komunikat + Ponów. Nie pokazywać zera jako potwierdzonej liczby, gdy pobranie się nie udało.
6. Zapis: potwierdzenie dopiero po sukcesie API; mutacje bez automatycznych ponowień. Autozapis z opóźnieniem, jedna operacja naraz, prywatny szkic; utrzymanie niezapisanej treści po awarii. Publikacja i usunięcie zawsze świadome.
7. Teksty: polskie, krótkie, bez żargonu wdrożeniowego w głównych przepływach. „Zespół spin.clinic”, nigdy „redakcja” jako operator; operator iapply sp. z o.o. Nie ujawniać danych prywatnych w profilu.
8. Karty: tytuł, autor/źródło, data, status i jedna czytelna droga do treści. „W nitkach” oznacza rzeczywiste powiązanie, a nie losową rekomendację. Link spoza Bazy zachowuje wyłącznie tytuł/URL/domenę; notatka autora jest odrębna od źródła.
9. Bezstronność: brak domyślnych politycznych obserwacji i rankingu osób. „Najlepiej oceniane” dotyczy nitek i jawnego licznika opinii. Diagnozy AI pozostają nieedytowane. Moderacja nitek przez zespół po zgłoszeniu.
10. Kontrakt: nie zmieniać endpointów konta z 053; pola zgody wersjonowane, czas po stronie serwera. Flagi wyłączone domyślnie. Push z 054 wymaga osobnej zgody przeglądarki; zapis preferencji nie jest subskrypcją urządzenia.

## Kryteria odbioru i granice weryfikacji

Sprawdzić: obie flagi wyłączone/osobno/włączone, gość i dwie różne sesje, 404/401/403/500, wolny zapis podczas dalszego pisania, utratę sieci, pierwszy zapis i ponowne otwarcie szkicu, brak e-mail/weryfikację, publikację z ≥2 materiałami, klawiaturę/strzałki, puste dane i długie tytuły. `tsc --noEmit` jest kontrolą typów, nie testem UX. Zrzuty 1440/390, czytnik ekranu, kontrast i integracja z nowym backendem są osobnymi bramkami przed włączeniem produkcyjnym.

## Dopisek po wykonaniu 055 — przekazanie do 053/054 i Claude

Powyższa część audytu została zapisana przed kodem. Wykonanie rozbudowuje istniejące komponenty; dodatkowe części panelu są w `components/AccountPhase2.tsx`, wspólny przycisk w `FollowButton.tsx`. Nie przebudowano warsztatu `ThreadEditor`: ma odrębne role i uprawnienia; kreator czytelnika pozostaje w `MojaNitkaEditor`.

Zrealizowano:

- `/konto`: powitanie, cztery skróty, wiadomości SavedTopic (maksymalnie pięć widocznych pasków; starsze nadmiarowe zapisy nadal można edytować/usunąć), szkice/publiczne nitki z dojściem do opinii, obserwowani z najnowszymi diagnozami, ulubione, powiadomienia i ustawienia. Stara trasa `/profile` prowadzi do `/konto`; publiczne `/profile/[username]` pozostają.
- Pomijalny onboarding w trzech krokach, dostępny ponownie z panelu. Pierwsze logowanie na urządzeniu prowadzi do panelu. Stan ukończenia jest lokalny, osobny dla ID konta; nie zapisuje wybranych treści w localStorage.
- Kontrakt konta: obserwacje, licznik/oznaczanie powiadomień, profil publiczny, istniejący motyw, e-mail i ponowna weryfikacja, reset hasła, preferencje e-mail/push, eksport JSON i usunięcie potwierdzone hasłem oraz `USUŃ`. Flaga push steruje preferencjami, nie rejestruje subskrypcji (054).
- Kreator: pięć kroków, pytanie w istniejącym polu `description`, tematy, Baza/resolve_link, kolejność strzałkami i przeciąganiem, 280 znaków notatki, wspólny renderer podglądu i publikacji. Autozapis szkicu po 1200 ms, pojedynczy zapis naraz, brak nadpisania tekstu wpisanego podczas żądania. Publikacja wymaga potwierdzonego e-mail i świadomej akceptacji zasad; publiczne zmiany zatwierdzane ręcznie. Ostrzeżenie przed wyjściem przy niezapisanych zmianach. Błąd nie kasuje szkicu w pamięci; treść, której serwer nie zapisał, nie przetrwa zamknięcia karty.
- `/nitki`: sortowanie serwerowe, tematy, wyróżnienie istniejących nitek `dr-spin-kontekst-*`, oś, opinie „Zgadzam się / Nie zgadzam się”, link do udostępnienia na X, obserwowanie autora/nitki, zgłaszanie. Opinie wcześniejsze zachowują dotychczasowe wartości positive/negative — przed włączeniem fazy 2 uzgodnić interpretację wcześniejszych ocen „Przydatna/Nieprzydatna”.
- Rzeczywiste „W nitkach” na materiale, diagnozie i osobie publicznej; przykład promocyjny jest nadal jawnie fikcyjny. Starszy backend ignorujący filtry nie powoduje pokazywania niepowiązanych nitek.
- Jeden blok CSS na końcu `kit.css`, zgodnie ze zleceniem; pionowe wiadomości na telefonie, zawijane akcje, cele 44 px, widoczny fokus, ograniczenie ruchu. Zakładki osoby publicznej mają obsługę strzałek/Home/End i zawijają się na telefonie.

### Uzgodnienia integracyjne

1. 053 musi przyjąć `accepted_terms_version: "2026-09-30"` przy rejestracji oraz PATCH `/api/account/me/`; data zgody i egzekwowanie potwierdzonego e-mail należą do serwera. Ta wersja jest też widoczna na stronie zasad. Obecny starszy backend nie zapewnia tego kontraktu — flagi produkcyjne pozostają wyłączone.
2. Adresy wiadomości z 053: `/konto/potwierdz-email?token=…` oraz `/konto/reset-hasla?uid=…&token=…`. Strony mają noindex i no-referrer; token nie jest kluczem cache ani wpisem localStorage. Potwierdzenie wykonuje przycisk, nie sam odczyt linku przez skaner poczty.
3. Drobne rozszerzenia istniejącego API w **055**, do zachowania przy scalaniu z 053: `community.py` obsługuje `sort=new|best`, `topic`, `article_id`, `figure_id`, `url`; zwraca `author_id`, `topics`, `context_filtered`. `best` sortuje po liczbie positive, następnie dacie i ID; `figure_id` używa tylko potwierdzonych `PublicFigureArticleReference`, nie podobieństwa nazwisk. `profiles.py` dodaje `id` do publicznej aktywności, pozostawiając 404 dla prywatnej historii.
4. Brak prywatnej historii oznacza brak publicznego ID w tym endpointcie: przycisk obserwowania autora pozostaje dostępny na jego publicznych nitkach. Nie ujawniamy prywatnej historii, aby odblokować przycisk.
5. Endpointy 404/405/501 dają spokojny stan. Operacje nie udają sukcesu. `apiWrite` zachowuje status HTTP, a wylogowanie i zmiana konta czyszczą cache danych prywatnych.

### Weryfikacja wykonania

- Frontend: `npx --no-install tsc --noEmit -p .` w `frontend-spin` — bez błędów.
- Testy klienta API: `node --test packages/ui/src/lib/api.phase2.test.mjs` — 3/3; status 404 także przy HTML zamiast JSON, zachowanie 403 i komunikatu walidacji, DELETE/CSRF/204.
- Backend: `test_community_phase2.py`, `test_community.py`, `test_profiles_topics.py`, `test_personal_context.py` — 26 poprawnych, 1 istniejąca rozbieżność: `test_source_selection_includes_beyond_top_ten_and_hides_inactive`. Potwierdzona osobnym uruchomieniem. Niezmieniony `portal.py` świadomie pokazuje kandydatów/nieaktywne źródła w publicznym katalogu, a test oczekuje ich ukrycia. Nie zmieniono tej niezwiązanej z nitkami polityki katalogu.
- Użyto już zainstalowanych zależności z głównego repo przez lokalne junctions. Nie instalowano pakietów. Testy uruchamiano z tymczasowym bootstrapem wyłączającym odczyt `.env`, bazą testową SQLite i katalogami w `.pytest-tmp`.
- Nie uruchamiano serwera, nie wykonywano płatnych zapytań, nie commitowano. Brak zrzutów i testu interakcji w przeglądarce — do wykonania przez Claude na 1440/390 wraz z macierzą stanów opisaną wyżej. Zgodność WCAG wymaga także manualnej weryfikacji.

### Właściciel i ryzyka wydania

055 nie wymaga nowych kluczy. Do uruchomienia całej fazy potrzebne są: działająca wysyłka e-mail i domena nadawcy (053), konfiguracja Web Push/VAPID i zgód urządzenia (054), a dla aplikacji sklepowych konta/decyzje wydawnicze właściciela (054). Najpierw scalić kontrakt i sprawdzić publikację, zgody, eksport oraz usunięcie na środowisku testowym. Następnie test wizualny i dostępności. Dopiero wtedy włączyć odpowiednie flagi. Nie ma deklaracji pełnej gotowości produkcyjnej przy brakującym backendzie 053.
