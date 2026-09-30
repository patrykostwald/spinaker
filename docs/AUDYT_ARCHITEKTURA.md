**Rekomendacja: zachować obecny język wizualny, ale przebudować podział treści.** Montserrat, neutralne powierzchnie, niebieskie interakcje, skaner diagnozy i wykresy stanowią dobry fundament. „Misz-masz” wynika dziś przede wszystkim z powtarzania funkcji, nadmiaru treści na stronach wejściowych oraz kilku sprzecznych sposobów prezentowania tych samych danych.

Docelowo serwis powinien mieć cztery czytelne wejścia: **strona główna, Klinika, Wiadomości i Konsylium AI**. Metodologia, Karta i materiały dla redakcji dostają własne, łatwe do podlinkowania miejsca.

Nie zmieniałem plików. Ocena obejmuje 40 zrzutów oraz kod. Ważne: checkout `codex-zlecenia-2` zawiera starsze wersje części komponentów. Nowsze implementacje fal A–C znalazłem w [spinaker-mvp-frontend](C:/Users/User/spin-clinic/.local/spinaker-mvp-frontend), m.in. `ClinicNav`, `SpinSummary` i animację. Wygląd oceniam ze zrzutów, a wskazania implementacyjne odnoszę do tej nowszej wersji. Nadal występują rozbieżności: odnośnik `/o-nas#film` jest w hero, ale w odczytanej stronie „O nas” nie znalazłem odpowiadającego osadzenia i kotwicy. Ustalenie kompletnej wersji referencyjnej jest pierwszą paczką D.

**1. Ocena z siedmiu perspektyw i wspólna decyzja**

- **Architekt informacji:** główna i Klinika zawierają niemal całe podserwisy, natomiast „O nas” przechowuje większość wiedzy o produkcie. Potrzebne są krótsze strony wejściowe i osobne dokumenty referencyjne.
- **Ekspert UI:** większość ekranów ma już wspólną paletę i geometrię. Pozostały różnice typografii, formularzy, odstępów i zagnieżdżania kart. Wystarczy doprowadzić istniejący system do konsekwencji.
- **Ekspert UX:** telefon nadal pokazuje zbyt dużo wprowadzenia przed wynikiem. Stały pasek wsparcia ogranicza przestrzeń, a źródło pojedynczej diagnozy pojawia się dopiero po całym uzasadnieniu.
- **Wizualizacja danych:** wykresy są jednym z najmocniejszych elementów. Najpilniejsze są zgodność liczników, jawna jednostka pomiaru, prawdziwy czas aktualizacji i spójne kategorie technik.
- **Redaktor:** „Klinika”, „Dr. Spin”, „Konsylium”, „diagnoza”, „baza”, „nitka” konkurują o uwagę. Metafora powinna wspierać jasne nazwy funkcji. Dokumenty mieszają stan obecny z planowanym.
- **Nowy użytkownik:** powinien szybko zrozumieć: „Analizują konkretne wypowiedzi, pokazują techniki i źródła, mogę sprawdzić wynik”. Obietnica układania własnych wiadomości jest drugim zadaniem i powinna prowadzić do Wiadomości.
- **Dziennikarz:** potrzebuje trwałego adresu analizy, materiału wejściowego, cytatów, źródeł, wersji metodologii i informacji o korektach. Długi opis projektu nie zastępuje tych narzędzi.

**Wspólna decyzja:** skrócić główną i przegląd Kliniki, wydzielić Wiadomości oraz centrum wiedzy o AI, rozszerzyć istniejące profile osób. Zachować ocenę konkretnych materiałów. **Nie tworzyć ocen prawdomówności osób, lig polityków ani rankingów „kto kłamie”.**

**2. Wszystkie obecne trasy — decyzja**

W `frontend-spin/app` są **38 szablonów stron `page.tsx`**. Strony dynamiczne liczę jako jeden szablon, niezależnie od liczby rekordów.

**Strony publiczne i treści:**

- `/` — **potrzebna**. Krótkie wejście do produktu; ograniczyć obecną rozbudowaną zawartość.
- `/klinika` — **potrzebna**. Przegląd aktualnych analiz, bez pełnego archiwum i rozbudowanych rejestrów.
- `/klinika/diagnozy` — **potrzebna**. Główna lista analiz z filtrami.
- `/klinika/[id]` — **potrzebna**. Zachować istniejące adresy diagnoz; nie przenosić ich dla samej symetrii URL.
- `/klinika/wskazniki` — **potrzebna**. Nazwa w interfejsie: „Dane i wykresy”. Nie tworzyć konkurencyjnej strony `/dane`.
- `/klinika/wywiady` — **potrzebna**. Osobne archiwum uzasadnia inny typ materiału i dwie oceny.
- `/klinika/wywiady/[id]` — **potrzebna**. Pełna analiza z odnośnikami do momentów nagrania.
- `/klinika/przekazy` — **potrzebna**. Archiwum dziennych syntez obu stron.
- `/raport` — **scalić z Kliniką**. Docelowo przekierowanie do `/klinika/raporty`.
- `/raport/[week]` — **scalić z Kliniką**. Docelowo `/klinika/raporty/[week]`; stare adresy zachować jako przekierowania.
- `/search` — **potrzebna**. To wyszukiwanie kontekstu na osi czasu, a nie jedynie druga lista materiałów. Zachować funkcję i powiązać ją z Wiadomościami.
- `/material/[id]` — **potrzebna**. Trwały adres materiału i jego kontekstu, także przy otwieraniu przez portal.
- `/thread/[slug]` — **potrzebna**. Opublikowana nitka redakcyjna lub kontekstowa; odróżnić ją od przyszłych nitek czytelników.
- `/osoby-publiczne` — **potrzebna**. Neutralny katalog osób i udokumentowanych funkcji.
- `/osoby-publiczne/[id]` — **potrzebna, rozszerzyć**. Profil już istnieje. Dodać diagnozy wypowiedzi tej osoby, bez zbiorczego „wyniku polityka”.
- `/zrodla` — **potrzebna**. Katalog źródeł wiadomości; jasno odróżnić go od źródeł dowodowych pojedynczej diagnozy.

**Informacje, dokumenty i wsparcie:**

- `/o-nas` — **potrzebna, odchudzić**. Misja, autor/operator, finansowanie, kontakt i krótki rozwój projektu.
- `/o-nas/karta-konsylium` — **scalić organizacyjnie z Konsylium**. Dokument zachować pod `/konsylium/karta`; stary adres przekierować.
- `/o-projekcie` — **scalić — już wykonane**. Zachować istniejące przekierowanie do `/o-nas`.
- `/wsparcie` — **potrzebna**. Jedna główna akcja, koszty, niezależność finansowania, pozostałe cele niżej.
- `/newsletter` — **potrzebna**. Samodzielny adres zapisu i jasna obietnica rodzaju wiadomości.
- `/newsletter/potwierdz` — **potrzebna technicznie**. Poza menu i indeksem wyszukiwarki.
- `/newsletter/wypisz` — **potrzebna technicznie**. Poza menu i indeksem wyszukiwarki.
- `/zasady-korzystania` — **potrzebna**. Osobny dokument; nie łączyć z metodologią analiz.
- `/polityka-prywatnosci` — **potrzebna**. Osobny dokument.
- `/dostep` — **usunąć jako samodzielną stronę promocyjną**. Przy niedostępnej funkcji pokazywać konkretny komunikat; stary adres może prowadzić do `/o-nas#rozwoj`.

**Funkcje kont i społeczności — zachować za flagami, bez promowania w obecnym menu:**

- `/konto` — **potrzebna w fazie kont**. Jedno centrum prywatnych ustawień i zapisanych treści.
- `/konto/nitki/nowa` — **potrzebna w fazie nitek**. Edytor tworzenia.
- `/konto/nitki/[id]` — **potrzebna w fazie nitek**. Edytor konkretnej nitki.
- `/nitki` — **potrzebna w fazie nitek**. Publiczny katalog, gdy funkcja zostanie uruchomiona.
- `/nitki/[id]` — **potrzebna w fazie nitek**. Opublikowana nitka czytelnika.
- `/profile` — **scalić z `/konto`**. Obecne zapisane treści, aktywność, prywatność i ustawienia nie potrzebują drugiego centrum użytkownika.
- `/profile/[username]` — **potrzebna po uruchomieniu kont**. Publiczny profil autora; nie mylić z profilem osoby publicznej.

**Zaplecze:**

- `/editor` — **potrzebna wewnętrznie**.
- `/editor/klinika` — **potrzebna wewnętrznie**.
- `/editor/political` — **potrzebna wewnętrznie**.
- `/editor/sources` — **potrzebna wewnętrznie**.
- `/ui-kit` — **potrzebna wewnętrznie** jako miejsce odbioru wspólnych komponentów.

Zaplecze powinno mieć własną nawigację i nie dziedziczyć publicznych zachęt do wpłat. Wyłączenie z indeksowania nie zastępuje kontroli dostępu.

Poza stronami pozostają:

- `/support-progress` — **zachować**, endpoint danych wsparcia.
- `/sitemap.xml` — **zachować i uzupełnić**.
- `/robots.txt` — **zachować i dostosować do docelowej mapy**.
- `/manifest.webmanifest` — **zachować**.
- `/icon.svg` — **zachować**.
- `/jak-dziala/index.html` — zasób z `public`, **nie osobna pozycja menu**. Docelowo zastąpić jego funkcję wspólnym komponentem animacji.

**3. Docelowa mapa i brakujące miejsca**

**Główna `/`:** obietnica → liczby → najnowsza diagnoza → krótki podgląd wiadomości → wejście do zasad działania → wsparcie/newsletter. Pełna baza i personalizacja przechodzą do Wiadomości.

**Klinika `/klinika`:** najnowsze diagnozy, ostatni wywiad, przekazy dnia, ostatni raport i krótki podgląd danych. Każda sekcja pokazuje próbkę i prowadzi do właściwego archiwum.

**Wiadomości `/wiadomosci` — NOWA STRONA.** Przenieść tutaj obecne „Wiadomości”, „Twoje wiadomości”, bazę materiałów i wejścia do nitek kontekstowych. Lokalnie: „Najnowsze”, „Twoje wiadomości”, „Materiały”. Zachować ustawienia zapisane w przeglądarce.

**Konsylium AI `/konsylium` — NOWA STRONA.** Jedno centrum odpowiedzi na pytanie „co zrobiliście z AI?”:

- droga wpisu od selekcji do publikacji;
- aktualny skład, role, twórca modelu i dostawca usługi;
- narzędzia rzeczywiście używane oraz osobno planowane;
- przykład rozbieżności ocen;
- odnośniki do metodologii, Karty i zasad zgłaszania błędów.

Wykorzystać istniejący `CouncilRoster`, który pobiera `/api/clinic/council/`. Nie budować drugiej ręcznie utrzymywanej listy modeli.

**Metodologia `/metodologia` — NOWA STRONA.** Dokument referencyjny: selekcja materiałów, zakres analizy, werdykty, skala 0–100, agregacja ocen, zgodność modeli, statusy twierdzeń, kategorie technik, mianowniki wykresów, ograniczenia i obsługa korekt. Wersja i data obowiązywania widoczne na początku.

**Karta `/konsylium/karta` — PRZENIESIONY DOKUMENT.** Zasady i ich wersje. Aktualny skład należy przede wszystkim do centrum Konsylium; Karta może wskazywać stan deklaracji dotyczących konkretnej wersji dokumentu.

**Dla redakcji `/dla-redakcji` — NOWA STRONA.** Dwa jasno oddzielone zastosowania: korzystanie z analiz spin.clinic oraz pilotaż autoryzowanych nitek. Na początku: przykład cytowania diagnozy, trwały link, źródła, metodologia i kontakt. Warunki współpracy niżej.

**Raporty `/klinika/raporty` — NOWE ARCHIWUM.** Najnowszy raport wyróżniony, poniżej lista tygodni. Pełne raporty pod `/klinika/raporty/[week]`.

**Przekaz dnia `/klinika/przekazy/[day]` — NOWA STRONA SZCZEGÓŁOWA.** Obie strony tego samego dnia, zakres materiału, syntezy i źródła. Kotwice do poszczególnych obozów. Obecny dialog nie daje wystarczająco wygodnego adresu do cytowania i udostępniania.

**Profil polityka: rozszerzyć istniejącą stronę.** Sekcja „Diagnozy wypowiedzi” powinna pokazywać chronologię i filtry. Powiązanie przez zweryfikowaną tożsamość/konto, nie dopasowanie nazwiska. Bez średniego „spinu osoby”, odznak winy i pozycji w rankingu.

Nie tworzyć kolejnych osobnych stron „Jak to działa”, „Narzędzia AI”, „Dokumenty”, „Politycy” czy „Dane”. Ich zadania mieszczą się w powyższej strukturze.

**4. Nawigacja główna, lokalna i stopka**

**Komputer:**

`logo → główna · Klinika · Wiadomości · Jak działa AI · Więcej`

„Jak działa AI” prowadzi do `/konsylium`. Obok pozostaje jednoznacznie nazwane wyszukiwanie materiałów, przełącznik motywu i dyskretne „Wesprzyj”. Usunąć bieżący zegar: zajmuje miejsce i może być mylony z aktualnością danych.

**Telefon:**

`logo · Szukaj · Menu`

Pola interakcji minimum `44 × 44 px`. W rozwiniętym menu te same wejścia co na komputerze, wsparcie i przełącznik motywu. Nie ściskać kilku pozycji tekstowych pomiędzy logo a ikonami.

**„Więcej”:** O nas, Dla redakcji, Metodologia, Karta Konsylium, Osoby publiczne, Źródła, Newsletter, Kontakt. Dostępne z nagłówka, nie dopiero z dołu ekranu.

**Lokalna nawigacja Kliniki:**

`Przegląd · Diagnozy · Dane i wykresy · Wywiady · Przekazy · Raporty`

Na telefonie przycisk powinien pokazywać **aktualne miejsce**, np. „Klinika: Diagnozy”, zamiast samego „W Klinice”. W szczególe diagnozy dodać „Wróć do wyników”, zachowując filtry i pozycję listy.

**Stopka:** zwykła, w przepływie dokumentu. Trzy grupy: „Czytaj”, „Jak pracujemy”, „Projekt i kontakt”. Dokumenty prawne na końcu. Wsparcie jako jedna akcja w stopce oraz sekcja na głównej.

Usunąć stały dolny pasek. Obecnie chowa się przy części przewijania, ale po wejściu nadal konkuruje z treścią. Na telefonie zabiera około 52 px właśnie wtedy, gdy użytkownik próbuje zobaczyć wynik.

**5. Pierwsze 10 sekund i miejsce animacji**

To docelowa kolejność uwagi, nie wynik przeprowadzonego badania użytkowników.

**Pierwsze 3 sekundy:** widoczny nagłówek:

> Zobacz, jak politycy budują przekaz.

Pod nim:

> Kilka modeli AI analizuje tę samą wypowiedź. Pokazujemy techniki perswazji, cytaty i źródła do sprawdzanych twierdzeń.

**Sekundy 3–6:** trzy krótkie liczniki oraz „Przeglądaj diagnozy”. Liczby muszą mieć zakres dat; nie sugerować, że każdy przeczytany wpis otrzymał pełną analizę.

**Sekundy 6–10:** początek konkretnej diagnozy: autor, tytuł, werdykt i siła spinu. Obecnie na telefonie po hero widać głównie nagłówek „Dr. Spin” i kolejne linki.

Na `390 × 844` cel odbioru: **pierwszy wynik liczbowy diagnozy widoczny bez przewijania**. Osiągnąć to skróceniem treści i odstępów, bez zmniejszania podstawowego tekstu ani ucinania pełnego H1. Hero powinno zajmować orientacyjnie 320–360 px, ale mieć naturalną wysokość, również przy powiększonym tekście.

Hasło „Ty układasz własne wiadomości” przenieść do wejścia do Wiadomości. W hero wystarczy jedna obietnica.

**Animacja: na `/konsylium#film`, z wejściem z głównej.** Nie jako automatycznie odtwarzane tło.

Obecny film:

- trwa około 69 sekund;
- dochodzi do Kliniki dopiero w piątej scenie, po około 39 sekundach;
- zawiera także planowane nitki i asystenta;
- skaluje scenę `1280 × 720` do szerokości telefonu.

Oznaczenia faz planowanych istnieją — problemem jest proporcja i kolejność opowieści. Film reklamowany jako wyjaśnienie diagnozy za długo mówi o innych funkcjach.

**Decyzja:** przebudować animację na około 40–45 sekund: wpis → niezależne oceny → sprawdzenie twierdzeń → różnice między modelami → diagnoza i możliwość zgłoszenia błędu. Plany rozwoju pozostają w „O nas”.

Wymagania:

- start na żądanie, pauza i wybór kroku;
- zatrzymanie poza ekranem;
- czytelny wariant mobilny, bez pomniejszania całego desktopowego interfejsu;
- tekstowa wersja pięciu kroków;
- obsługa ograniczonego ruchu;
- etykieta „przykład”, jeśli używane są dane demonstracyjne.

**Zaufanie budować stopniowo:** jedno zdanie na głównej, konkretne modele i zakres przy diagnozie, pełne zasady w Konsylium i Metodologii.

**6. Spójność — konkretne poprawki**

Skróty ścieżek poniżej: `F = frontend-spin/app`, `U = packages/ui/src`. Wartości są docelową specyfikacją; nie oznaczają, że wszystkie obecne wartości są błędne.

**Wspólny fundament**

- Zachować kontener `1152 px`, mobilny gutter `16 px`, tabletowy `24 px`. Nagłówek globalny może mieć `1280 px`.
- Zachować promienie: sekcja `28 px`, wyróżniona karta `22 px`, panel `18 px`, media `14 px`, kontrolka `10 px`.
- Odstępy: sekcje `24 px`; nagłówek–treść `20 px`; karty listy `12 px`; padding karty `20/16 px`.
- H1 krótkiej strony `48/54 px`, mobilnie `32/38 px`; długi H1 `32/40` i `26/34`.
- Tytuł karty `18/25 px`; tekst artykułowy `16/26`; opis karty `14/21`; metadane `12/18`.
- Kolory semantyczne zachować. Siła spinu jako pomiar ma jeden kolor niebieski; werdykt własny kolor i tekst. Obóz polityczny nie dziedziczy koloru oceny.
- Ujednolicić `InfoPage` i `SectionHeader`. Nie tworzyć kolejnego komponentu nagłówka.
- Zebrać reguły każdego komponentu w jednym miejscu w `kit.css`, usuwając zastąpione nadpisania. Nie dopisywać następnej warstwy końcowych wyjątków.

**Nagłówek, lokalne menu i stopka — komputer i telefon**

Problem: duża przestrzeń przed treścią, „W Klinice” bez informacji o bieżącej sekcji, wsparcie stale silniejsze od lokalnych działań.

Poprawka: jeden komponent układu strony, jeden odstęp pod nagłówkiem `24/16 px`, lokalne menu z bieżącą nazwą, zwykła stopka. Nie dodawać równocześnie odstępów z `gap`, `margin-bottom` nagłówka i marginesu następnej sekcji.

Pliki: `F/layout.tsx`, `U/components/SiteHeader.tsx`, `U/kit/NavMenu.tsx`, `U/kit/SiteFooter.tsx`, `U/components/clinic/ClinicNav.tsx`, `U/kit/kit.css`.

**Główna**

Komputer: pełny skaner, przekazy, wiadomości, personalizacja i baza tworzą kilka konkurujących centrów strony.

Telefon: hero ma około 540 px, a właściwa diagnoza zaczyna się późno. Pełna strona jest bardzo długa.

Poprawka: jedna najnowsza diagnoza w wariancie skróconym; pełne głosowanie modeli i tabela technik dopiero po rozwinięciu lub w szczególe. Trzy podglądy wiadomości i wyraźne przejście do `/wiadomosci`. Personalizacja i baza poza główną. Tytuł sekcji „Najnowsza diagnoza”; „Dr. Spin” może pozostać oznaczeniem produktu.

Pliki: `U/kit/home/HomePage.tsx`, `HomeHero.tsx`, `HomeSpinTeaser.tsx`, `HomeBaza.tsx`, `HomeThreads.tsx`; klasy `.sc-hero*`, `.sc-home-spin*`.

**Przegląd Kliniki**

Komputer: liczniki, pełna diagnoza, przekazy z historią, wywiady, kolejne diagnozy, niedostępne wpisy i politycy wyglądają jak kilka stron połączonych w jedną.

Telefon: pierwsza karta danych zaczyna się dopiero około 476 px; użytkownik długo nie ogląda analizy.

Poprawka: H1 „Klinika spinu”, lead maksymalnie dwa krótkie zdania. Pod nim zwarta informacja o pracy i najnowsze diagnozy. Jeden podgląd wywiadu, para przekazów i wejście do raportu. Pełną historię przekazów usunąć z przeglądu; katalog osób przenieść do istniejącego katalogu. Niedostępne wpisy jako zwarty moduł szczegółów.

Domyślny wybór: „Najnowsza”. „Najwyższa siła spinu w dniu…” może pozostać opcją, z konkretną datą. Na zrzutach zegar pokazuje 29 września, a wyróżnienia dotyczą 28 września — etykieta „dziś” wymaga spójności z datą zbioru.

Pliki: `U/components/clinic/ClinicPage.tsx`, `ClinicExtras.tsx`, `ClinicIndicators.tsx`.

**Baza diagnoz**

Komputer: „Sortuj” spada do osobnego wiersza, licznik po prawej jest nieproporcjonalnie mocny. Telefon: ucięty placeholder i osobny wysoki wiersz „Znaleziono” odsuwają listę.

Poprawka:

- placeholder „Szukaj diagnoz…”;
- wyszukiwanie + „Filtry”, poniżej jeden wiersz „36 wyników” i sortowanie;
- liczba wyników `14/20 px`, bez oddzielnego dużego KPI;
- tytuły kart `18/25 px`, maksymalnie trzy linie;
- opis maksymalnie dwie linie na liście;
- techniki w zwartej liście jako „3 techniki”, szczegóły w diagnozie;
- aktywne filtry zachować — są już wdrożone.

Pliki: `ClinicDatabase.tsx`, `SpinParts.tsx`; `.sc-clinic-db__toolbar`, `__bottom`, `__count`, `.sc-spin-row__title`, `__summary`.

**Pojedyncza diagnoza**

Komputer: duży wynik jest czytelny, ale autor i karta mają zbyt duże odstępy; synteza powtarza się w kilku miejscach.

Telefon: liczba 55/100 pojawia się bardzo nisko, a „Materiał źródłowy” dopiero na samym końcu całej analizy.

Poprawka: kolejność dokumentu **autor → pełny tytuł i wynik → krótka synteza → rozwijany materiał źródłowy → uzasadnienie**. Źródło na komputerze pozostaje otwartą kolumną, mobilnie zwiniętym elementem bezpośrednio przed uzasadnieniem.

Panel mobilny: cztery zwarte pola `2 × 2`; szczegółowe głosy modeli po rozwinięciu. „Zgłoś błąd” przy identyfikatorze oraz na końcu. Dodać kotwice „Techniki”, „Twierdzenia i źródła”, „Modele”, „Ograniczenia”.

Pliki: [SpinDetail.tsx](C:/Users/User/spin-clinic/.local/spinaker-mvp-frontend/packages/ui/src/components/clinic/SpinDetail.tsx:59), `SpinSummary.tsx`, `SourceDisclosure.tsx`.

**Wynik diagnozy — spójność danych**

To poprawka o najwyższym priorytecie.

Na raporcie widać **7 technik**, a podział pokazuje jedną w „Danych” i zera w pozostałych rodzinach. W [SpinSummary.tsx](C:/Users/User/spin-clinic/.local/spinaker-mvp-frontend/packages/ui/src/components/clinic/SpinSummary.tsx:33) liczba technik i liczby rodzin mogą pochodzić z różnych agregatów; rodzina `inne` nie jest wyświetlana.

Poprawka: jeden model prezentacji danych dla licznika, pasków i tabeli. Musi zachodzić:

`liczba typów technik = suma typów w rodzinach, razem z „Inne/nieprzypisane”`.

Nie dopasowywać historycznych kategorii na siłę i nie usuwać ich z wyniku.

Dodatkowo:

- „2/3 zgodne” zastąpić „2 z 3 modeli: ten sam werdykt”; to nie jest miara pewności.
- Brak odpowiedzi modelu pokazywać osobno od rozbieżnej oceny.
- Rozróżniać opinię, niesprawdzone twierdzenie oraz twierdzenie sprzeczne ze źródłami.
- Sprawdzić potencjalne powtórzenie twierdzenia o kurtkach w pokazanej diagnozie. Licznik musi jasno mówić, czy liczy unikalne twierdzenia, czy zapisane pozycje analizy.
- Przy rozbieżności etykiety „Spin” i niskiej liczby, np. 6/100 w wywiadzie, wyjaśnić regułę albo zgłosić niespójność danych. Nie zmieniać werdyktu automatycznie według koloru paska.

Pliki: `SpinSummary.tsx`, `InterviewScanner.tsx`, `U/lib/techniqueFamilies.ts`, nowy wspólny moduł prezentacji danych.

**Dane i wykresy**

Komputer: zachować układ i porównania. Wspólne skale histogramów, wzory serii i tabele danych są już dobrym kierunkiem.

Telefon: sekcja wszystkich technik jest nadmiernie długa, tabela partii wymaga przewijania, a metadane konkurują z wykresami.

Poprawka: początkowo sześć najczęstszych technik, „Pokaż wszystkie” poniżej. Etykiety wykresów minimum `12 px` w rzeczywistym renderze. Tabele jako jawnie oznaczony poziomy obszar przewijania; kluczowe kolumny pierwsze.

„Najczęściej badane konta” opisywać jako **zakres wybranej próby**, nie miarę aktywności polityka. Domyślny katalog alfabetyczny; liczba diagnoz może być dodatkowym sortowaniem, bez ocen osoby.

W [PeriodNote](C:/Users/User/spin-clinic/.local/spinaker-mvp-frontend/packages/ui/src/components/clinic/ClinicIndicators.tsx:50) „stan na” korzysta z czasu pobrania przez przeglądarkę, a początek pracy jest wpisany na sztywno. Potrzebne osobne pola: zakres danych, czas wygenerowania zestawienia i ewentualnie czas pobrania. Do czasu dostępności pola serwerowego pisać „Pobrano”, nie „Stan danych”.

Pliki: `ClinicIndicators.tsx`, `HomeHero.tsx`, kontrakt API statystyk.

**Wywiady**

Komputer: pole wyszukiwania ma inną szerokość niż sąsiedni select; opisy zakresu oceny krzyczą wersalikami. Telefon: tytuł nagrania i powtarzane instrukcje bardzo wydłużają kartę.

Poprawka: formularz desktop `minmax(0, 2fr) minmax(220px, 1fr)`, oba pola `width:100%`, `44 px`. Mobilnie jedna kolumna.

Najpierw dwa zwarte wyniki: „Wypowiedzi gościa” oraz „Pytania prowadzącego”, potem wspólna synteza. Objaśnienie zakresu raz nad listą, zwykłym tekstem `14/21 px`. Tytułu źródłowego nie przepisywać, ale oznaczyć go jako tytuł nagrania; tytuł analizy może pełnić główną rolę.

Pliki: `ClinicArchives.tsx`, `InterviewScanner.tsx`; `.sc-clinic-archives__filters`, `__columns`, `.sc-archive-interview-summary`.

**Przekazy**

Komputer: dzień i licznik wyglądają jak przypadkowe akapity; akcje w kartach mają różne wysokości położenia. Telefon: pełna karta pierwszej strony odsuwa drugą.

Poprawka: nagłówek „Przekazy dnia”, licznik jako metadane; nagłówek dnia `20/28 px`, odstęp `16 px`. Na telefonie para skrótów obu stron, po maksymalnie trzy linie syntezy. Pełna treść i źródła na nowej stronie dnia.

W kartach zastosować `grid-template-rows: auto 1fr auto auto`, żeby akcja i stopka miały wspólną pozycję. Ten sam limit treści dla obu obozów.

Pliki: `ClinicArchives.tsx`, `ClinicExtras.tsx`, nowy `MessageDetail.tsx`.

**Raport tygodnia**

Komputer: sekcja „Trzy obserwacje” czyta się jak jeden akapit; techniki zawierają podobne nazwy, a panel diagnozy ma wskazaną wyżej niespójność liczb.

Telefon: pełne karty liczników zajmują dużo miejsca przed obserwacjami. Duża karta „Spinu tygodnia” ponownie odtwarza znaczną część diagnozy.

Poprawka: trzy rzeczywiste punkty z `12 px` odstępu; dwa zwarte liczniki obok siebie przy szerokości co najmniej `360 px`; pełne zastrzeżenie dotyczące próby poniżej. Wyróżniona diagnoza w wariancie skróconym. Techniki grupować według wspólnego słownika kategorii, zachowując możliwość obejrzenia nazw oryginalnych.

Daty: „21–27 września 2026 · opublikowano 27 września, 20:00”, bez sekund i technicznego ISO w głównej treści.

Pliki: `WeeklyReport.tsx`, nowe archiwum. Przy migracji usunąć dodatkowy `<main>` z tras raportu — globalny layout już go zawiera.

**O nas**

Komputer: dziesięć dużych rozdziałów, boczny spis i kolejne karty wewnątrz kart. Telefon: pierwszy pogrubiony akapit sam zajmuje znaczną część ekranu.

Poprawka: wstęp 60–90 słów, lead `18/28` na komputerze i `16/25` na telefonie, bez pogrubiania całego bloku. Cztery części: projekt, autor/operator, finansowanie i niezależność, kontakt/rozwój. Metodologia, AI i redakcje opuszczają tę stronę.

Długie dokumenty korzystają ze wspólnego układu: tekst `68ch`, boczny spis `200 px` na komputerze, rozwijany spis na telefonie. Akapity na otwartym tle; karty dla danych, przykładów i ważnych komunikatów.

Pliki: `F/o-nas/page.tsx`, `U/kit/InfoPage.tsx`, `.sc-onas*`; nowy wspólny układ dokumentu.

**Konsylium i Karta — ustalenia z kodu**

Aktualny `CouncilRoster` istnieje i powinien być rozwijany. Statyczna lista modeli w starszych plikach nie powinna stać się nowym źródłem prawdy.

Poprawki treści:

- „Każdy członek przyjął Kartę” zastąpić opisem faktycznego stanu deklaracji.
- Licznik deklaracji sprawdza również zgodność `charter.version` z aktualną wersją.
- Oświadczenie wygenerowane przez model nie jest certyfikatem jakości ani poparciem jego dostawcy.
- Wymóg „co najmniej cztery modele, w tym polski” z dokumentu rozbudowy oznaczyć jako plan, dopóki nie jest spełniany przez rzeczywiste diagnozy.
- Aktualny skład systemu i historyczny skład konkretnej diagnozy pokazywać oddzielnie.
- Rozstrzygnąć relację „Nikt nie poprawia diagnoz” z „Korekty są jawne”. Dokument ma opisywać rzeczywiście obsługiwany proces wycofania, ponownej analizy i historii wersji; nie obiecywać nieistniejącego mechanizmu.

Pliki: `CouncilRoster.tsx`, `F/o-nas/karta-konsylium/page.tsx`, `docs/KARTA_KONSYLIUM.md`, `docs/KONSYLIUM.md`.

**Wsparcie**

Komputer i telefon: śródtytuły „Kto za tym stoi”, „Na co idą pieniądze” wyglądają jak zwykłe zdania. Duże odstępy oddzielają obietnicę od właściwej akcji.

Poprawka: `.sc-info-page__body h2` — `20/28 px`, `700`, margines dolny `12 px`; sekcje co `24 px`. CTA bezpośrednio po leadzie. Uporządkowane kategorie kosztów, bez obietnic przeliczających wpłatę na liczbę diagnoz. Zachować jasne stwierdzenie, że zbiórka nie jest subskrypcją.

Nie trzeba wypełniać wolnej prawej kolumny dekoracją. Wąski tekst jest właściwy dla tej strony.

Pliki: `F/wsparcie/page.tsx`, `InfoPage.tsx`, `.sc-support*`.

**Pozostałe strony — ustalenia z kodu, bez zrzutów**

- Źródła, katalog osób i wyszukiwanie powinny używać `SectionHeader`; mają dziś własne warianty nagłówków.
- `/search`: wyszukiwane hasło i formularz przed technicznym postępem archiwum.
- Profile osób: wspólna typografia, chronologia, źródła i nowa sekcja diagnoz.
- Nitka: „Wszystkie historie” powinno prowadzić do miejsca, gdzie rzeczywiście znajduje się lista, docelowo Wiadomości.
- Newsletter i dokumenty prawne: wspólne `InfoPage`, śródtytuły, daty dokumentów i stany powodzenia/błędu.
- Globalne metadata nadal używają „pokazujemy chwyty, nie werdykty”, choć interfejs pokazuje werdykty. Zmienić na „pokazujemy, jak zbudowany jest przekaz”.
- `template.tsx` bezwarunkowo przewija na początek. Sprawdzić i poprawić obsługę kotwic oraz powrotu do wyników.
- Mapa XML nie obejmuje wszystkich ważnych archiwów i dokumentów. Uzupełnić po migracji.

Nie uznaję tych stron za wizualnie odebrane. Wymagają zrzutów po wdrożeniu.

**7. Fala D — paczki po 1–2 godziny**

Kolejność uwzględnia zależności. „NOWY” oznacza nową stronę lub komponent; nie należy ponownie tworzyć istniejących `SectionHeader`, `ClinicNav`, `SpinSummary`, `SourceDisclosure` i `CouncilRoster`.

1. **D01 — wersja referencyjna i mapa adresów.** Porównać checkouty, ustalić komplet A–C, potwierdzić osadzenie filmu. Pliki: `F/*`, komponenty Kliniki, dokumenty audytu. Odbiór: jedna wskazana wersja wejściowa i lista migracji.

2. **D02 — wspólne liczenie wyniku.** NOWY `U/lib/diagnosisPresentation.ts`; podłączyć `SpinSummary` i `InterviewScanner`. Odbiór: suma rodzin zgadza się z liczbą technik, braki odpowiedzi i statusy twierdzeń są rozróżnione. Testy rzeczywistych przypadków historycznych.

3. **D03 — zakres i aktualność danych.** `backend/news/clinic_api.py`, typy odpowiedzi, `ClinicIndicators.tsx`, `HomeHero.tsx`. Odbiór: czas zestawienia pochodzi z serwera; brak twardego „od 23 września” w komponentach.

4. **D04 — typografia i rytm.** `kit.css`, `tokens.ts`, `SectionHeader.tsx`, `InfoPage.tsx`. Odbiór: wspólne H1/H2, metadane, pola i odstępy; usunięte zastąpione nadpisania.

5. **D05 — układ dokumentów.** NOWY `U/kit/DocLayout.tsx`, oparty na istniejącym systemie. Odbiór: `68ch`, spis treści desktop/mobile, nagłówek dokumentu z wersją i datą.

6. **D06 — globalna nawigacja.** `SiteHeader.tsx`, `NavMenu.tsx`, NOWY `U/lib/siteNavigation.ts`. Odbiór: identyczny zestaw wejść na obu szerokościach, aktywna sekcja, poprawna obsługa menu.

7. **D07 — lokalne menu i stopka.** `ClinicNav.tsx`, `SiteFooter.tsx`, `F/layout.tsx`, `kit.css`. Odbiór: aktualna nazwa sekcji mobilnie, stopka nie zasłania treści, „Więcej” dostępne u góry.

8. **D08 — Wiadomości.** NOWE `F/wiadomosci/page.tsx`, `U/kit/home/NewsPage.tsx`; przeniesienie modułów z `HomePage`. Odbiór: zachowane filtry, parametry i lokalne ustawienia personalizacji.

9. **D09 — główna i hero.** `HomePage.tsx`, `HomeHero.tsx`, `HomeSpinTeaser.tsx`. Odbiór: jedna obietnica, krótkie liczniki, wynik diagnozy widoczny na pierwszym ekranie telefonu.

10. **D10 — przegląd Kliniki.** `ClinicPage.tsx`, `ClinicExtras.tsx`, `ClinicShowcase`. Odbiór: krótkie podglądy i wejścia do archiwów; brak pełnej historii przekazów i rozbudowanego katalogu osób.

11. **D11 — baza diagnoz.** `ClinicDatabase.tsx`, `SpinParts.tsx`, style listy. Odbiór: zwarty pasek wyników/sortowania, krótkie karty, zachowanie filtrów przy powrocie.

12. **D12 — szczegół diagnozy.** `SpinDetail.tsx`, `SpinSummary.tsx`, `SourceDisclosure.tsx`. Odbiór: wynik przed rozwiniętym tekstem, źródło przed uzasadnieniem, kotwice i widoczne zgłoszenie błędu.

13. **D13 — wywiady.** `ClinicArchives.tsx`, `InterviewScanner.tsx`. Odbiór: dwa zwarte wyniki przed syntezą, jednakowe formularze, pełny tytuł i źródło w szczególe.

14. **D14 — dane pojedynczego przekazu dnia.** `backend/news/clinic_api.py`, `backend/news/urls.py`, `U/lib/clinic.ts`. Odbiór: stabilny odczyt konkretnego dnia, zakres i źródła, jednoznaczne zachowanie dla braku publikacji.

15. **D15 — strony przekazów.** NOWE `F/klinika/przekazy/[day]/page.tsx`, `U/components/clinic/MessageDetail.tsx`; aktualizacja `MessageBox`. Odbiór: kopiowalny adres, obie strony i źródła dostępne bez dialogu.

16. **D16 — archiwum raportów i adresy.** NOWE `F/klinika/raporty/page.tsx`, `F/klinika/raporty/[week]/page.tsx`, `ReportArchive.tsx`; przekierowania starych tras. Odbiór: lista tygodni i działające stare linki.

17. **D17 — prezentacja raportu.** `WeeklyReport.tsx`, wspólny model danych. Odbiór: trzy osobne obserwacje, zwarte liczniki, spójne techniki i skrót wyróżnionej diagnozy.

18. **D18 — wykresy mobilne.** `ClinicIndicators.tsx`, `.sc-ind-*`. Odbiór: czytelne etykiety, sześć technik na wejściu, pełne dane po rozwinięciu, właściwe opisy próby.

19. **D19 — centrum Konsylium.** NOWE `F/konsylium/page.tsx`; rozwinięcie `CouncilRoster.tsx`. Odbiór: proces, aktualny skład, role, narzędzia i statusy „działa/planowane”.

20. **D20 — metodologia.** NOWE `F/metodologia/page.tsx`; treść zweryfikowana z `clinic_council.py` i kontraktami danych. Odbiór: jawne zasady skali, agregacji, zgodności, statusów i mianowników.

21. **D21 — Karta.** NOWE `F/konsylium/karta/page.tsx`, przekierowanie starego adresu; aktualizacja dokumentu źródłowego. Odbiór: zgodna wersja, prawdziwy stan deklaracji, jednoznaczny opis korekt.

22. **D22 — animacja procesu.** NOWY `U/components/clinic/ClinicExplainer.tsx`; wykorzystanie materiału z `public/jak-dziala/index.html`. Odbiór: pięć kroków, start na żądanie, czytelny telefon, wersja tekstowa i ograniczony ruch.

23. **D23 — O nas i Dla redakcji.** Skrócenie `F/o-nas/page.tsx`; NOWE `F/dla-redakcji/page.tsx`; przeniesienie przykładu nitki. Odbiór: każda strona ma własny cel, aktualny kontakt i jedno główne działanie.

24. **D24 — wsparcie i strony informacyjne.** `F/wsparcie`, `newsletter`, `zrodla`, dokumenty prawne, `InfoPage`. Odbiór: wspólne nagłówki, formularze, metadane i stany komunikatów.

25. **D25 — precyzyjny filtr autora.** Backend listy diagnoz oraz `U/lib/clinic.ts`, `ClinicDatabase.tsx`. Odbiór: filtrowanie po zweryfikowanym identyfikatorze konta, bez wyszukiwania nazwiska jako substytutu tożsamości.

26. **D26 — diagnozy na profilu osoby.** `PublicFigureProfile.tsx`, `PublicFigureDirectory.tsx`, NOWY `AuthorDiagnoses.tsx`. Odbiór: chronologia analiz i źródła; brak zbiorczego wyniku osoby.

27. **D27 — migracja linków i odbiór desktop.** `F/sitemap.ts`, metadata, `template.tsx`, odnośniki i stare kotwice. Odbiór: brak martwych przejść, zgodne canonicale, komputer/tablet oraz oba motywy. Starych kotwic nie obsłuży samo przekierowanie serwerowe — fragment adresu wymaga zachowania kotwicy lub obsługi w przeglądarce.

28. **D28 — odbiór mobilny i interakcje.** Wszystkie publiczne szablony; `320`, `390`, `768 px`, klawiatura, powiększony tekst, ograniczony ruch, długie tytuły oraz brak/błąd danych. Odbiór: brak zasłaniania treści, poprawny powrót do list i komplet zrzutów porównawczych.

To **28 paczek, orientacyjnie 28–56 godzin**. Fala D obejmuje architekturę, nowe miejsca treści i ujednolicenie danych, więc nie jest wyłącznie porządkowaniem CSS.

Za zakończoną uznałbym ją dopiero wtedy, gdy nowy użytkownik zobaczy konkretny wynik na pierwszym ekranie telefonu, dziennikarz dotrze z diagnozy do źródła i metodologii, a wszystkie liczniki tej samej analizy będą zgodne. Obecny audyt jest statyczny; nie stanowi jeszcze odbioru jasnego motywu ani działania interakcji w przeglądarce.