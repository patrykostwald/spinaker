# Zlecenie 023 — końcowy audyt spin.clinic

**Data:** 29 września 2026  
**Zakres:** wygląd, spójność, UX, wizualizacja danych i treści.  
**Materiały:** 24 dostarczone zrzuty oraz kod stron i komponentów.

## 0. Werdykt konsylium audytowego

**Kierunek wizualny jest gotowy do utrwalenia. Obecna realizacja wymaga jeszcze ujednolicenia przed zamknięciem wyglądu.**

Zachować:

- Montserrat, neutralne tła, niebieski akcent interakcji.
- Konstrukcję skanera: materiał źródłowy, synteza, cztery grupy danych, uzasadnienie.
- Architekturę strony wskaźników: praca Kliniki → przebieg dzienny → porównanie obozów → techniki → partie i konta.
- Tekstowe werdykty i oddzielenie siły spinu od prawdziwości twierdzeń.
- Zasadę karty materiału: kategoria ↖, polubienia ↗, data ↙, źródło ↘.

Największy efekt przyniesie **ujednolicenie istniejących elementów**, nie nowy projekt graficzny.

### Pięć ocen osobno

| Perspektywa | Ocena | Najważniejsza decyzja |
|---|---|---|
| UI | Skaner i wskaźniki tworzą dobry język wizualny. Archiwa, pełna diagnoza, raport i strony informacyjne stosują jego różne odmiany. | Jedna skala typografii, semantyczne promienie i wspólne komponenty nagłówka, przycisku oraz metadanych. |
| UX | Na telefonie materiał wejściowy i objaśnienia wypychają wynik poza pierwszy ekran. Stopka dodatkowo ogranicza przestrzeń. | Wynik przed rozbudowanym źródłem; zwykła stopka; krótsze wprowadzenia. |
| Wizualizacja danych | Układ jest czytelny, ale kilka reguł rysowania może zniekształcać interpretację. | Wspólna skala histogramów, prawdziwe zero, jawne okresy i mianowniki, rozdzielenie opinii od niesprawdzonych twierdzeń. |
| Redakcja | Metafora Kliniki jest charakterystyczna, lecz miejscami zastępuje jasne wyjaśnienie. Pojawiają się sprzeczne obietnice. | Prosty opis funkcji przed metaforą; jeden słownik etykiet; opis AI bez deklaracji nieomylności i bez stałej liczby modeli. |
| Nowy użytkownik | Dowiaduje się, że AI analizuje polityków, lecz nie widzi od razu skali pracy ani wyniku. „Konsylium” pozostaje niejasne. | Pierwszy ekran: obietnica → jednozdaniowe wyjaśnienie AI → liczby → wejście do diagnoz → początek wyniku. |

### Warunki zamknięcia wyglądu

Przed zamknięciem muszą zniknąć:

1. Ucinanie treści na „Wsparciu”.
2. Dominacja przyklejonej stopki.
3. Brak wyniku diagnozy na pierwszym ekranie telefonu.
4. Archiwa wyglądające jak niewystylowany formularz.
5. Pusty panel raportu i niewyjaśnione puste powierzchnie głównej.
6. Różne skale histogramów obozów i graficzne wartości większe od rzeczywistego zera.
7. Niespójne nazwy ocen, przycisków i okresów.
8. Sprzeczne opisy działania Konsylium i finansowania.
9. Brak weryfikacji jasnego motywu oraz obsługi klawiaturą.

### Granice pewności

- **Zrzut:** problem widoczny w dostarczonym obrazie.
- **Kod:** zachowanie lub reguła potwierdzone w plikach.
- **Do sprawdzenia:** wymaga uruchomionej strony, rzeczywistych danych albo testu interakcji.

Zrzuty pokazują motyw ciemny. Jasny oceniono na podstawie tokenów, bez wizualnego odbioru. Nie wykonano testów przeglądarkowych, czytnika ekranu ani symulacji zaburzeń widzenia barw.

Pełne zrzuty są dostępne dla głównej, Kliniki, „O nas” i wskaźników. Dla pozostałych stron dolne sekcje oceniono z kodu. Nie należy traktować braku uwagi o niewidocznym fragmencie jako jego akceptacji.

---

## 1. Jeden system wizualny

### 1.1. Fundament: uporządkować źródła stylów

W `frontend-spin/app/globals.css` nadal istnieje starsza paleta granatowo-beżowa oraz globalne nadpisania klas i kontrolek. `packages/ui/src/kit/kit.css` dostarcza nową paletę, a następnie wielokrotnie nadpisuje własne komponenty.

Przykłady:

- `.sc-footer[data-sticky]` ma kilka kolejnych zestawów reguł.
- `.sc-clinic-message` zmienia tło zależnie od rodzica: powierzchnia, przezroczystość, czerń strony.
- `.sc-scan-m-num` dostaje późniejsze nadpisania `!important`.
- `.sc-onas-section` początkowo działa jako otwarta sekcja, później jako karta.
- `.sc-info-page` i inne selektory odwołują się do `--sc-s-12` lub `--sc-s-16`; nie znaleziono ich definicji w przeszukanym `packages/ui/src` i `frontend-spin/app`.

**Decyzja:** publiczne strony mają korzystać z `--sc-*`. Starsze komponenty wymagają jawnych aliasów albo lokalnej migracji. Nie usuwać hurtowo `globals.css`, bo obsługuje też inne widoki.

Brakujący token w skróconym `margin` może unieważnić całą deklarację. Zastąpić takie odwołania istniejącą skalą, zamiast dopisywać kolejne przypadkowe stopnie.

### 1.2. Kolory i poziomy powierzchni

Poniższe wartości są docelową specyfikacją. Nazwy oznaczone „nowy” należy dopiero wprowadzić.

| Token / rola | Ciemny | Jasny | Zastosowanie |
|---|---|---|---|
| `--sc-bg` | `#000000` | `#FFFFFF` | Tło strony. |
| `--sc-surface` | `#0F0F0F` | `#F4F4F4` | Sekcja lub samodzielny panel. |
| `--sc-surface-2` | `#171717` | `#FFFFFF` | Karta wewnątrz sekcji. |
| `--sc-surface-3` | `#212121` | `#E8E8E8` | Tor miernika, hover, pole pomocnicze. |
| `--sc-line` | `#262626` | `#DADADA` | Subtelny podział strukturalny. |
| `--sc-line-strong` | `#454545` | `#B8B8B8` | Mocniejszy podział, nie automatycznie obrys każdej kontrolki. |
| `--sc-control-line` — nowy | `#767676` | `#767676` | Obrys pola, gdy jest potrzebny do rozpoznania kontrolki. |
| `--sc-text` | `#FFFFFF` | `#111111` | Tytuł i treść podstawowa. |
| `--sc-text-2` | `#B3B3B3` | `#4F4F4F` | Opis, lead, tekst pomocniczy. |
| `--sc-text-3` | `#999999` | `#666666` | Data i podpis; bez dodatkowej redukcji opacity. |
| `--sc-accent` | `#4A9EFF` | `#0A62D0` | Linki i aktywna nawigacja. |
| `--sc-focus` | `#6FB2FF` | `#0A62D0` | Obrys fokusu 2 px, odsunięcie 3 px. |
| `--sc-primary-bg` | `#FFFFFF` | `#111111` | Główny przycisk. |
| `--sc-primary-fg` | `#000000` | `#FFFFFF` | Tekst głównego przycisku. |
| `--sc-ind-gov` | **`#55B4FF`** | **`#006DB3`** | Rządzący. |
| `--sc-ind-opp` | **`#F5A54A`** | **`#A65300`** | Opozycja. |
| `--sc-negative` | `#FF6B6B` | `#C42B2B` | Ocena negatywna / sprzeczność, nigdy obóz. |
| `--sc-warning` | `#F2B441` | `#8A5A00` | Częściowy spin / ocena pośrednia. |
| `--sc-positive` | `#4ED18A` | `#147A4B` | Potwierdzenie / bez spinu, nigdy obóz. |

**Reguła powierzchni:** strona → sekcja → karta. Maksymalnie dwa pełne obramowania na tej ścieżce. Wewnętrzny panel pomiarów skanera może zachować ciemniejsze tło jako nazwany wariant `metrics`, zgodny z zatwierdzonym wzorcem.

Nie odwracać dowolnie powierzchni przy przenoszeniu komponentu na inną stronę. Przykładowo `MessageBox` powinien przyjmować jawny wariant osadzenia, zamiast zmieniać wygląd dzięki selektorowi rodzica.

### 1.3. Geometria

| Element / token | Wartość docelowa | Reguła |
|---|---:|---|
| Nagłówek globalny | maks. 1280 px | Może być szerszy od treści. |
| `--sc-layout-wide` | 1152 px | Jeden kontener główny dla audytowanych stron. |
| Margines telefonu | 16 px | Jedna warstwa paddingu; przy 390 px zostaje 358 px. |
| Margines tabletowy | 24 px | Bez dokładania kolejnych gutterów w podstronach. |
| Tekst artykułowy | maks. 68ch, nie więcej niż 100% | Diagnoza, „O nas”, „Wsparcie”. |
| Sekcja główna | promień 28 px | Skaner, duże grupy treści. |
| Karta wyróżniona | promień 22 px | Główna karta diagnozy. |
| Panel standardowy | promień 18 px | Wskaźnik, karta listy, przekaz, wywiad. |
| Media / podpanel | promień 14 px | Załącznik, mały panel wewnętrzny. |
| Kontrolka | promień 10 px | Przycisk, pole, select. |
| Pigułka | promień 999 px | Chip, werdykt, filtr. |
| Padding sekcji | 24 / 16 px | Komputer / telefon. |
| Padding karty | 20 / 16 px | Komputer / telefon. |
| Przerwa między sekcjami | 24 px | Stały rytm strony. |
| Nagłówek → zawartość | 20 px | Nie zależy od podstrony. |
| Przerwa między kartami listy | 12 px | Baza i archiwa. |
| Skala odstępów | 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80 px | Korzystać z istniejących `--sc-s-*`. |
| Cień zwykłej karty | brak | Powierzchnia i obrys wystarczą. |
| Cień menu/dialogu | ciemny: `0 12px 32px #00000066`; jasny: `0 12px 32px #0000001F` | Wyłącznie element nad treścią. |

Obecne promienie nie są same w sobie błędne. Problemem jest ich stosowanie bez znaczenia: archiwum wywiadów ma kartę 10 px, wskaźnik 18 px, karta „O nas” 22 px, a różne przyciski raz są pigułką, raz prostokątem.

Wprowadzić aliasy semantyczne, np. `--sc-radius-panel: var(--sc-r-lg)`. Nie trzeba likwidować całej obecnej skali.

### 1.4. Typografia

Zachować Montserrat. Ujednolicić role, zamiast robić wszystkie nagłówki równie duże.

| Rola | Komputer | Telefon | Grubość |
|---|---|---|---:|
| Tytuł krótkiej strony | 48/54 px | 32/38 px | 600 |
| Długi tytuł diagnozy / raportu | 32/40 px | 26/34 px | 600 |
| Nagłówek dużej sekcji | 28/36 px | 24/32 px | 600 |
| Nagłówek panelu danych | 20/28 px | 20/28 px | 700 |
| Tytuł karty | 18/25 px | 18/25 px | 600 |
| Lead strony | 18/28 px | 16/25 px | 400 |
| Tekst artykułowy | 16/26 px | 16/26 px | 400 |
| Opis w zwartej karcie | 14/21 px | 14/21 px | 400 |
| Metadane | 12/18 px | 12/18 px | 500 |
| Kicker wersalikami | 12/16 px | 12/16 px | 600 |
| Główna liczba | 36/40 px | 30/36 px | 700 |

Dodatkowe zasady:

- Kicker: `letter-spacing: .08em`; zwykła treść bez rozstrzelenia.
- Liczby: `font-variant-numeric: tabular-nums`.
- Nie stosować pełnego justowania akapitów.
- Główne informacje nie mogą mieć 10–11 px.
- H1 identyfikuje stronę; H2 sekcję; H3 kartę. Rozmiar wynika z roli, nie z domyślnego stylu znacznika.
- Dla „Dr. Spin” wewnątrz głównej użyć rozmiaru nagłówka sekcji, nie osobnego 30 px.

### 1.5. Kontrolki i etykiety

| Element | Specyfikacja |
|---|---|
| Główny przycisk | min. 44 px wysokości, padding 12–16 px, promień 10 px, 14/20 px, 600; jasny w ciemnym motywie i odwrotnie. |
| Drugi przycisk | Ta sama geometria; tło transparentne, tekst podstawowy, obrys 1 px. |
| Cichy przycisk | Ta sama wysokość obszaru interakcji; brak ramki; czytelny hover/focus. |
| Filtr-pigułka | 44 px; promień 999 px; aktywny stan rozpoznawalny także po nazwie i możliwości usunięcia. |
| Zakładka | min. 44 px; promień 10 px; aktywna: tło poziomu 2 i dolna linia 2 px; poprawne `aria-selected`. |
| Pole / select | min. 44 px, promień 10 px, tekst 16 px na telefonie, stała etykieta. |
| Chip informacyjny | min. 24 px, tekst 12/18 px, padding 3–8 px; nie udaje przycisku. |
| Werdykt | min. 24 px, tekst 12/18 px, 700, obrys 1 px, pełna etykieta. |
| Znacznik AI | min. 20 px; `flex-shrink: 0`; nie może się łamać ani ściskać. |
| Przycisk ikonowy | pole 44 × 44 px; ikona 20 px, linia 1,75–2 px. |
| Strzałki | `→` dla przejścia wewnątrz serwisu, `↗` dla zewnętrznego źródła. |

44 px to przyjęty standard wygody serwisu, nie stwierdzenie, że każda mniejsza kontrolka automatycznie narusza WCAG.

### 1.6. Wspólny nagłówek sekcji

Docelowy kontrakt:

1. Kicker, jeśli wnosi kontekst.
2. Tytuł.
3. Jedno–dwa zdania podtytułu.
4. Jedna główna akcja i najwyżej jeden link pomocniczy.

Na komputerze akcje mogą stać po prawej. Na telefonie przechodzą pod tekst i zawijają się naturalnie.

Proponowany nowy komponent: `packages/ui/src/kit/SectionHeader.tsx`, z wariantami `page`, `section`, `panel`. Nie tworzyć osobnych rozwiązań dla archiwów, wsparcia i raportu.

### 1.7. Zasada boxa

Dla karty materiału:

- ↖ typ materiału;
- ↗ polubienia, jeśli funkcja jest dostępna;
- środek: tytuł, media, opis;
- ↙ data publikacji;
- ↘ źródło.

Dla diagnozy stosować analogiczny porządek metadanych, ale **nie dokładać fikcyjnego licznika polubień**. Rozdzielić datę wpisu od daty diagnozy. Ocena AI ma własny nagłówek i nie zastępuje kategorii materiału źródłowego.

`NewsCard.tsx` już zawiera osobne elementy kategorii, daty i źródła. Ten komponent powinien pozostać jedynym wzorcem kart materiałów.

---

## 2. Niespójności strona po stronie

**MUSI** — przed zamknięciem wyglądu.  
**PÓŹNIEJ** — usprawnienie, które nie blokuje spójnego wydania.

### 2.1. Elementy wspólne

**G01 — MUSI — stopka konkuruje z treścią.**  
Na komputerze zajmuje około 90 px, na telefonie około 82 px. Telefon pokazuje urwane linki i ucięty komunikat wsparcia, a stały biały przycisk jest często silniejszy niż właściwa akcja strony.

Kod `SiteFooter.tsx` zawiera chowanie przy przewijaniu w dół. Nie jest więc prawdą, że stopka nigdy się nie chowa; problem pozostaje na wejściu, przy przewijaniu w górę i przy fokusie.

**Docelowo:** zwykła stopka w przepływie dokumentu. Wsparcie w nagłówku/menu i w końcowej sekcji. Linki stopki zawijane, bez poziomego paska z ukrytym scrollbarem.  
**Pliki:** `frontend-spin/app/layout.tsx`, `kit/SiteFooter.tsx`, `components/SupportBar.tsx`, `.sc-footer-dock`.

**G02 — MUSI — różne osie treści.**  
Na telefonie główna i „O nas” zaczynają się około 10 px od krawędzi, Klinika i baza około 26 px, archiwa około 22 px. To skutek nakładania kontenera i paddingów podstron.

**Docelowo:** jeden gutter 16 px. Wewnętrzne karty mają własne 16 px, ale strona nie dostaje drugiego zewnętrznego marginesu.  
**Klasy:** `.sc-app-main`, `.sc-clinic`, `.sc-clinic-archives`, `.sc-info-page`, `.sc-onas`.

**G03 — MUSI — niespójne nagłówki.**  
„Baza diagnoz” i „Wskaźniki Kliniki” mają duże tytuły; „Archiwum wywiadów” i „Archiwum przekazów” wyglądają jak zwykłe akapity.

**Docelowo:** kontrakt nagłówka z punktu 1.6.

**G04 — MUSI — wiele rodzin przycisków.**  
Baza używa pigułek, skaner prostokątów 10 px, wskaźniki dużego białego CTA-pigułki, archiwa własnej kontrolki „Pokaż więcej”.

**Docelowo:** zwykłe akcje korzystają z `Button`; pigułki pozostają filtrami i chipami.

**G05 — MUSI — „baza” znaczy dwie różne rzeczy.**  
Globalne „Szukaj w bazie…” prowadzi do materiałów, lokalne wyszukiwanie do diagnoz.

**Docelowo:** „Szukaj materiałów…” w nagłówku, „Szukaj diagnoz…” w Klinice; w menu osobno „Materiały” i „Diagnozy”.

**G06 — MUSI — niewystarczające rozróżnienie stanów.**  
`SpinDetail.tsx` traktuje brak `query.data` jako „Nie znaleziono diagnozy”, także po błędzie pobierania. `WeeklyReport.tsx` może po błędzie pokazać zapowiedź pierwszego raportu. `HomeSpinTeaser.tsx` przy braku danych zwraca `null`.

**Docelowo:** osobno ładowanie, brak publikacji, brak wyników, błąd połączenia i brak konkretnego zasobu. Błąd ma przycisk „Spróbuj ponownie”.

**G07 — MUSI — wielkość metadanych i ukryte informacje.**  
Ważne daty, identyfikatory i znaczenia kolorów bywają bardzo małe albo dostępne tylko jako `title`.

**Docelowo:** minimum 12/18 px; podstawowa informacja widoczna bez hovera.

**G08 — MUSI — semantyka strony.**  
`layout.tsx` ma główny `<main>`, a komponenty archiwów dodają kolejny `<main>`.

**Docelowo:** jeden główny landmark; archiwa jako `<section>` lub `<div>`.

### 2.2. Główna

**H01 — MUSI — pierwszy ekran nie pokazuje skali pracy.**  
Liczby są dopiero pod skanerem i przekazami dnia.

**Docelowo:** trzy liczniki bezpośrednio pod krótkim opisem serwisu: przeczytane wpisy, wstępnie ocenione wpisy, opublikowane diagnozy.

**H02 — MUSI — telefon pokazuje źródło przed wynikiem.**  
Widać autora i duży załącznik, lecz nie tytuł diagnozy ani ocenę.

**Docelowo:** w mobilnej wersji skanera: autor → wynik i synteza → mierniki → akcja → zwijany materiał źródłowy. Zachować dwukolumnowy układ komputerowy.

**H03 — MUSI — ilustracja konkuruje z opisem.**  
Na telefonie długi szary tekst leży na szczegółowym obrazie.

**Docelowo:** tekst na jednolitej powierzchni; ilustracja jako osobny, dyskretny fragment albo dekoracja z zapewnionym kontrastem. Nie uzależniać czytelności od konkretnej pory dnia ilustracji.

**H04 — MUSI — obietnice w hero są zbyt szerokie.**  
„Każdy wpis i wywiad” przeczy selekcji materiałów. „Także płatne” nie wyjaśnia wartości. „Bez sympatii i antypatii” brzmi jak gwarancja braku uprzedzeń.

**Docelowo:** gotowy tekst z punktu 3.

**H05 — MUSI — „Zobacz dzisiejsze diagnozy” nie odpowiada działaniu.**  
Link prowadzi do `#dr-spin`, a komponent może pokazać ostatnie 24/72 godziny lub starszy materiał.

**Docelowo:** hero: „Przeglądaj diagnozy” → `/klinika/diagnozy`; sekcja: „Wybrana diagnoza” i rzeczywisty okres.

**H06 — MUSI — puste powierzchnie głównej.**  
Pełny zrzut pokazuje duże puste sekcje wiadomości oraz pustą przestrzeń przed wsparciem.

W kodzie są dwa różne tropy:

- `HomeReveal.tsx` startuje od `opacity: 0`, co może wpływać na pełnostronicowy zrzut przed przewinięciem.
- `HomePage.tsx` nie pokazuje komunikatu pustego wyniku dla każdego wariantu: brak materiałów bez filtrów i błąd wymagają osobnej obsługi.

**Docelowo:** treść nie może pozostać niewidoczna przez animację; puste sekcje mają krótki komunikat i naturalną wysokość. Nie diagnozować całej pustki jako awarii API bez sprawdzenia.

**H07 — MUSI — CTA wsparcia powtarza się w hero, stopce i dolnej sekcji.**  
**Docelowo:** główna akcja hero prowadzi do diagnoz. Wsparcie pozostaje dostępne, ale nie dominuje nad pierwszym zadaniem czytelnika.

**H08 — PÓŹNIEJ — „Twoje wiadomości” potrzebują jasnego objaśnienia.**  
Dodać: „Obserwuj temat lub źródło. Ustawienia zapisują się na tym urządzeniu”, jeśli odpowiada to działaniu. Pusty pasek nie powinien wyglądać jak niedoładowana treść.

**Pliki:** `HomeHero.tsx`, `HomePage.tsx`, `HomeSpinTeaser.tsx`, `HomeSpinScanner.tsx`, `HomeReveal.tsx`, `HomeThreads.tsx`.

### 2.3. Klinika

**K01 — MUSI — wprowadzenie jest zbyt techniczne.**  
Na telefonie opis Strażnika, progów zgodności i konsultacji zajmuje dużą część ekranu przed pierwszą korzyścią.

**Docelowo:** dwa zdania o tym, co czytelnik dostaje; szczegóły procesu pod „Jak działa analiza”.

**K02 — MUSI — nagłówki nie mają wspólnej hierarchii.**  
„Dr. Spin”, wersalikowe „Spin dnia | Najnowszy spin”, „Wywiad dnia” i nagłówki list nie tworzą jednej skali.

**Docelowo:** widoczny H2 „Wybrana diagnoza”; pod nim zakładki „Wyróżniona” i „Najnowsza”. Kryterium wyróżnienia napisane pod zakładkami.

**K03 — MUSI — aktualny przekaz jest zagnieżdżony inaczej niż archiwalny.**  
`.sc-clinic-group .sc-clinic-message` ma tło strony, archiwum inne tło. Powstaje efekt czarnych „otworów” wewnątrz karty.

**Docelowo:** jawny wariant karty wewnętrznej z `--sc-surface-2`.

**K04 — MUSI — „Najnowsze diagnozy” tworzą dużą pustą kolumnę.**  
Na pełnym zrzucie po lewej jest mało materiałów, po prawej znacznie więcej.

**Docelowo:** dla prezentacji obok siebie pokazać najwyżej trzy materiały każdej strony, z osobnym „Wszystkie diagnozy rządzących/opozycji”. Nie wyrównywać wysokości przez puste miejsce. Pozostawić informację, że liczby publikacji mogą być różne.

**K05 — MUSI — poprzednie wywiady i tabele są zbyt drobne względem skanera.**  
**Docelowo:** metadane 12 px, tytuły minimum 14 px, wiersze klikalne minimum 44 px. Lista jest uproszczoną wersją tej samej karty, a nie osobnym stylem.

**K06 — MUSI — „Usunięte posty” nadmiernie przesądza przyczynę.**  
Kod dopuszcza również wpisy, które stały się niedostępne.

**Docelowo:** „Niedostępne wpisy” i opis rozróżniający usunięcie od innych przyczyn niedostępności. Nie budować „najczęściej usuwających” bez pewności przyczyny.

**K07 — PÓŹNIEJ — skrócić drogę do głównych części Kliniki.**  
Dodać wspólną nawigację lokalną do diagnoz, wskaźników, wywiadów, przekazów i raportów.

**Pliki:** `ClinicPage.tsx`, `ClinicExtras.tsx`, `ClinicIndicators.tsx`, `InterviewScanner.tsx`.

### 2.4. Baza diagnoz

**B01 — MUSI — tytuł jest krótszy niż opis.**  
Na telefonie tytuł zostaje ucięty po dwóch liniach, a opis zajmuje około siedmiu.

**Docelowo:** tytuł do trzech linii w podglądzie; opis do trzech linii; całość dostępna po otwarciu. Pierwszeństwo ma sens diagnozy.

**B02 — MUSI — autor i data znikają w jednym wierszu.**  
**Docelowo:** autor w oddzielnym wierszu, data publikacji poniżej lub w stopce karty. Nie ucinać równocześnie nazwiska, konta i daty.

**B03 — MUSI — lista zaczyna się zbyt nisko.**  
Rozbudowane statystyki, toolbar i osobny wiersz „Znaleziono” zajmują dużą część telefonu.

**Docelowo:** pod tytułem krótko „36 diagnoz · 22 konta z diagnozą”. Pozostałe liczby przenieść do wskaźników. Wynik wyszukiwania w jednym zwartym wierszu pod filtrami.

**B04 — MUSI — niespójny słownik.**  
„Siła”, „nasilenie”, „najsilniejsze”, „niej ednoznaczne”/„nie da się ocenić” nie tworzą jednego systemu.

**Docelowo:** „Siła spinu”, „Najwyższa siła spinu”, „Nie da się ocenić”, „Cały okres”, „Najnowsze diagnozy”.

**B05 — MUSI — miniatury zachowują się inaczej na telefonie.**  
Samo ukrycie miniatur w bazie jest uzasadnione: lista ma służyć wyszukiwaniu. Należy jednak zachować autora, zakres analizy i pełną drogę do materiału.

**Docelowo:** bez miniatur w zwartej liście mobilnej; pełny materiał w diagnozie.

**B06 — PÓŹNIEJ — widoczne aktywne filtry poza dialogiem.**  
Po zamknięciu filtra pokazać krótkie chipy, np. „Opozycja ×”, „7 dni ×”. Samo „Filtry (2)” nie mówi, co ogranicza wyniki.

Dobre elementy do zachowania: parametry filtrów w adresie, dialog mobilny, komunikaty błędów, `aria-live` licznika.

**Pliki:** `ClinicDatabase.tsx`, `SpinParts.tsx`, `.sc-clinic-db*`, `.sc-spin-row*`.

### 2.5. Pełna diagnoza

**D01 — MUSI — wynik jest za całym wpisem na telefonie.**  
To najpoważniejsza przeszkoda dla osoby przychodzącej z X.

**Docelowo:** H1, autor analizowanego wpisu, ocena, siła i krótka synteza przed źródłem. Nie wystarczy wizualne CSS `order`, jeśli czytnik ekranu nadal czyta długi wpis jako pierwszy; uporządkować strukturę dokumentu.

**D02 — MUSI — strona gubi język skanera.**  
Lista i główna pokazują panel danych, pełna diagnoza przechodzi w długi artykuł z drobnym miernikiem.

**Docelowo:** wspólne podsumowanie skanera na górze, potem pełne uzasadnienie. Wydzielić część wspólną, nie kopiować całego interaktywnego skanera.

**D03 — MUSI — załącznik tekstowy jest przycięty.**  
Obraz z artykułem może być dowodem. Kadrowanie go bez wyraźnej możliwości obejrzenia całości utrudnia ocenę.

**Docelowo:** podgląd z przyciskiem „Pokaż cały załącznik”; w pełnym podglądzie `object-fit: contain`.

**D04 — MUSI — źródła są wizualnie zbyt ciche.**  
`.sc-spin-detail__sources a` korzysta z koloru pomocniczego.

**Docelowo:** czytelny link z podkreśleniem, tytułem i domeną. Źródła są podstawową funkcją diagnozy, nie przypisem drugiej kategorii.

**D05 — MUSI — brak widocznego zgłoszenia błędu w głównej części diagnozy.**  
Skaner ma „Zgłoś błąd”, a `SpinDiagnosisBody` kończy się informacją o modelu i udostępnianiem.

**Docelowo:** stała akcja „Zgłoś błąd” przy identyfikatorze diagnozy oraz na końcu uzasadnienia.

**D06 — MUSI — tytuły podsekcji są za małe.**  
„Diagnoza — techniki perswazji” ma styl bliższy tekstowi niż sekcji.

**Docelowo:** H2 20/28 px; nazwy „Techniki perswazji”, „Twierdzenia i źródła”, „Oceny modeli”, „Ograniczenia analizy”.

**D07 — MUSI — informacja o AI jest zbyt późno.**  
**Docelowo:** krótka etykieta „Analiza AI” od początku, skład i wersje modeli niżej. Numer diagnozy widoczny także mobilnie.

**Pliki:** `SpinDetail.tsx`, `HomeSpinScanner.tsx`, `SpinParts.tsx`.

### 2.6. Wskaźniki

**W01 — MUSI — kolory obozów są za mało wyraziste.**  
Wprowadzić paletę z punktu 1.2 we wszystkich wykresach, legendach i porównaniach.

**W02 — MUSI — histogramy mają różne skale.**  
`CampColumn` liczy `histMax` osobno dla każdej strony. Najwyższy słupek 8 i najwyższy słupek 13 mogą mieć tę samą wysokość.

**Docelowo:** wspólne maksimum przekazane do obu kolumn. Podpis osi: „Liczba diagnoz”. Alternatywa procentowa wymaga jawnej zmiany etykiet; nie mieszać obu znaczeń.

**W03 — MUSI — zero może mieć wysokość.**  
`ClinicShowcase` używa `Math.max(3, …)`, `Funnel` używa `Math.max(0.6, …)`, a histogram ma `min-height: 2px`.

**Docelowo:** zero = brak słupka. Wartość bardzo mała, ale dodatnia, może mieć osobny znacznik z dokładną liczbą; nie przedstawiać go jako proporcjonalnej długości.

**W04 — MUSI — okresy nie są dostatecznie widoczne.**  
Obok siebie występują „od początku”, dzienne zestawienie i „ostatnie 30 dni”. Liczby 1834 i 1220 mogą wyglądać na sprzeczne.

**Docelowo:** każdy panel ma własny zakres dat. Szczególnie sprawdzić, czy „12 diagnoz z 558 przeczytanych wpisów” łączy dane z tego samego okresu — komponent korzysta z różnych pól odpowiedzi.

**W05 — MUSI — osie SVG maleją wraz z wykresem.**  
`DailyChart` ma `viewBox` o szerokości 640 i etykiety 11 jednostek. Po zwężeniu na telefonie podpisy mogą być bardzo drobne.

**Docelowo:** mobilny układ wykresu z etykietami około 12 px w rzeczywistym renderze, rzadsze daty, tabela danych dostępna pod wykresem.

**W06 — MUSI — legenda nie wystarcza do identyfikacji każdej serii.**  
W wykresach technik wiersze polegają głównie na kolorze.

**Docelowo:** nazwy/skrót obozu w dostępnym tekście oraz wzór serii. Tooltip nie jest jedynym nośnikiem wartości.

**W07 — MUSI — zbyt duża kategoria „bez przypisanej partii”.**  
Na zrzucie 19 z 36 diagnoz trafia do tej grupy.

**Docelowo:** nie udawać, że to partia. Podpis „Nieustalona afiliacja” i wyjaśnienie zakresu braków. To również zadanie jakości danych.

**W08 — PÓŹNIEJ — przełącznik słupków dziennych.**  
Domyślnie zachować wykres skumulowany do pokazania całej pracy. Dodać wariant „Porównaj strony” z parami słupków od wspólnej podstawy.

**W09 — PÓŹNIEJ — „Najczęściej badane konta”.**  
Zachować liczbę analiz i wyraźny opis „To nie jest ocena osoby”. Nie dodawać medali, podium ani rankingu średniej „winności”.

**Plik:** `ClinicIndicators.tsx`, `.sc-ind-*`.

### 2.7. Wywiady

**Y01 — MUSI — H1 i tytuły kart wyglądają jak zwykły tekst.**  
**Docelowo:** H1 według systemu, tytuł wywiadu 18/25 px i wyraźne oddzielenie od daty.

**Y02 — MUSI — karta 10 px odbiega od pozostałych paneli.**  
**Docelowo:** 18 px, padding 20/16 px, spójna powierzchnia.

**Y03 — MUSI — formularz różni się od bazy diagnoz.**  
Pola mają inną geometrię i dominują w pierwszym ekranie.

**Docelowo:** wspólne pole wyszukiwania i filtr kanału. Etykieta „Gość, prowadzący lub tytuł”, wysokość 44 px.

**Y04 — MUSI — dwie oceny mogą być mylone.**  
Ta sama etykieta „Spin” pojawia się przy gościu i prowadzącym.

**Docelowo:** wyraźne nagłówki „Wypowiedzi gościa” i „Pytania i reakcje prowadzącego”, z jednozdaniowym wyjaśnieniem zakresu oceny.

**Y05 — MUSI — na telefonie długa ocena gościa odsuwa drugą ocenę.**  
**Docelowo:** najpierw dwa krótkie wyniki, potem streszczenie i „Czytaj analizę”. Pełne opisy po wejściu.

**Y06 — PÓŹNIEJ — miniatura nagrania.**  
Może ułatwić rozpoznanie rozmowy, ale nie jest konieczna do zamknięcia stylu. Najpierw uporządkować hierarchię.

**Pliki:** `ClinicArchives.tsx`, `InterviewScanner.tsx`.

### 2.8. Przekazy

**P01 — MUSI — ten sam problem nagłówka co w wywiadach.**  
**Docelowo:** H1 „Przekazy dnia”, podtytuł i licznik jako metadane, nie cztery równorzędne linie tekstu.

**P02 — MUSI — mobilny nagłówek karty rozpada się na wąską kolumnę.**  
„PRZEKAZ DNIA · RZĄDZĄCY” łamie się na kilka wierszy, znacznik AI się ściska. Kod wymusza `white-space: nowrap` dla metadanych w jednym flexie.

**Docelowo:** wiersz 1: nazwa strony + AI; wiersz 2 lub stopka: „35 wpisów · 28 września 2026”. Metadane nie mogą wypychać tytułu.

**P03 — MUSI — cały akapit jest przyciskiem bez jasnego wezwania.**  
`MessageBox` otwiera dialog kliknięciem tekstu.

**Docelowo:** widoczne „Czytaj przekaz i zobacz źródła”. Akapit pozostaje tekstem do czytania i zaznaczania.

**P04 — MUSI — długa karta opóźnia zobaczenie drugiej strony.**  
**Docelowo:** w archiwum mobilnym krótka synteza obu stron, po maksymalnie około pięciu linijek; pełna treść w szczegółach. Obie strony mają ten sam limit.

**P05 — MUSI — pozycja daty nie odpowiada regule boxa.**  
**Docelowo:** data ↙; informacja o materiale źródłowym ↘. Nazwa obozu pozostaje na górze.

**Pliki:** `ClinicArchives.tsx`, `ClinicExtras.tsx`, `.sc-clinic-message*`.

### 2.9. O nas

**O01 — MUSI — strona zaczyna od definicji cudzej roli.**  
Pierwszy ekran mówi, kim jest spin doctor, zamiast wyjaśniać spin.clinic.

**Docelowo:** H1 „O spin.clinic”, krótki opis projektu, dwa wejścia: „Zobacz diagnozy” i „Jak działa Konsylium AI”. Słownik przenieść niżej.

**O02 — MUSI — „Pokazujemy chwyty, nie werdykty” przeczy interfejsowi.**  
Serwis ma „Werdykt” i etykiety „Spin”, „Częściowy spin”, „Bez spinu”.

**Docelowo:** „Pokazujemy, jak zbudowany jest przekaz”. Dopowiedzenie: „Oceniamy wypowiedź, nie człowieka”.

**O03 — MUSI — justowanie tworzy duże przerwy między słowami.**  
Potwierdzone regułą `.sc-onas-prose p`.

**Docelowo:** wyrównanie do lewej; długość linii do 68ch.

**O04 — MUSI — zbyt wiele kart wewnątrz kart.**  
Słownik, fazy, statusy i podsekcje konkurują obrysami.

**Docelowo:** jedna powierzchnia na rozdział; wewnątrz zwykłe nagłówki i separatory. Definicja słownikowa może mieć pojedynczą linię akcentu bez kolejnej pełnej karty.

**O05 — MUSI — mobilny spis treści nie pokazuje swojej pełnej zawartości.**  
Widać początek poziomego rzędu.

**Docelowo:** rozwijane „Na tej stronie” z listą kotwic. Na komputerze zachować boczny spis.

**O06 — MUSI — skład i role AI są zbyt związane z nazwami produktów.**  
**Docelowo:** główna treść opisuje role; aktualne modele w osobnym, wersjonowanym składzie. Nie zakładać trzech członków na stałe.

**O07 — MUSI — roadmapa przytłacza wyjaśnienie produktu.**  
**Docelowo:** trzy krótkie fazy i rozwijane „Szczegóły techniczne”. Zachować wyraźne statusy: działa, beta, planowane.

**O08 — PÓŹNIEJ — oddzielna strona dla redakcji.**  
Obecna kotwica wystarczy na zamknięcie stylu, jeśli łatwo do niej trafić.

**Plik:** `frontend-spin/app/o-nas/page.tsx`, `.sc-onas-*`.

### 2.10. Wsparcie

**S01 — MUSI — tekst wychodzi poza ekran.**  
Na telefonie akapit „Kto za tym stoi” jest ucięty po prawej.

**Docelowo:** `min-width: 0` dla elementów siatki, `max-width: 100%`, zawijanie długich linków i przycisków, pojedynczy gutter. Sprawdzić długie CTA wewnątrz `.sc-info-page__body`, ponieważ mogą podnosić minimalną szerokość kolumny. Nie maskować problemu `overflow-x: hidden`.

**S02 — MUSI — tytuł jest bardziej krzykliwy niż reszta serwisu.**  
**Docelowo:** zachować hasło jako charakterystyczny tekst, ale użyć tej samej skali H1. Skrócona propozycja w punkcie 6.

**S03 — MUSI — śródtytuły znikają w tekście.**  
„Kto za tym stoi” i „Na co idą pieniądze” wyglądają jak zwykłe akapity.

**Docelowo:** 20/28 px, 600–700; 24 px odstępu przed sekcją.

**S04 — MUSI — sprzeczność finansowania.**  
„Utrzymują go wyłącznie czytelnicy” i „Dziś pokrywamy te koszty sami” nie mogą opisywać tego samego stanu bez dopowiedzenia.

**Docelowo:** prawdziwy opis stanu obecnego, np. finansowanie przez twórcę i wpłaty czytelników. Nie przedstawiać celu jako osiągniętego modelu.

**S05 — MUSI — nieudokumentowane przeliczniki i obietnice.**  
„10 zł to kilka diagnoz albo kilka dni pracy” oraz „koszt spadnie prawie do zera” wymagają danych.

**Docelowo:** zastąpić opisem kategorii kosztów. Konkretne przeliczniki dopiero po pomiarze.

**S06 — MUSI — „docisk Claude” i „wykorzystujemy limity do końca dnia”.**  
To język wewnętrzny, nie informacja potrzebna wspierającemu.

**Docelowo:** „Dodatkowa weryfikacja trudniejszych analiz” i „Część zadań korzysta z bezpłatnych limitów usług”.

**S07 — MUSI — zbyt wiele równorzędnych akcji wpłaty.**  
**Docelowo:** jeden główny cel „Wesprzyj bieżące działanie”; inne metody jako akcje drugorzędne. Zbiórka na sprzęt w osobnej sekcji.

**S08 — MUSI — nazwa zbiórki a płatność cykliczna.**  
„Wspieraj co miesiąc” może sugerować automatyczne odnawianie.

**Docelowo:** dopóki mechanizm nie jest potwierdzony, „Wesprzyj miesięczny budżet”. Etykietę płatności cyklicznej stosować tylko przy faktycznej subskrypcji.

**Pliki:** `frontend-spin/app/wsparcie/page.tsx`, `kit/InfoPage.tsx`, `.sc-support-*`.

### 2.11. Raport tygodnia

**R01 — MUSI — pusty panel jest realnie renderowany.**  
`WeeklyReport.tsx` zawiera pustą sekcję `.sc-report__panel` z `aria-label="Waga spinu"`.

**Docelowo:** usunąć pusty panel albo wypełnić go właściwymi danymi. Nie pozostawiać dekoracyjnej kapsuły.

**R02 — MUSI — długi lead pochłania pierwszy ekran telefonu.**  
**Docelowo:** dwuzdaniowa synteza, dwa liczniki stron, trzy najważniejsze obserwacje. Rozwinięcie niżej.

**R03 — MUSI — raport używa starszego `SpinOfDay`.**  
Główna i Klinika korzystają z `HomeSpinScanner`, raport z innej konstrukcji, w tym wewnętrznego przewijania diagnozy.

**Docelowo:** wspólne podsumowanie skanera również w raporcie. Bez zagnieżdżonego czytania artykułu w małym scrollowanym oknie.

**R04 — MUSI — procent bez jawnego licznika jest nieweryfikowalny.**  
„9 postów, z czego 50%” nie daje całkowitej liczby wpisów przy takim mianowniku.

**Docelowo:** generować procent z danych i prezentować „x z n (y%)”. Sprawdzić, czy chodzi o spin, spin wraz z częściowym spinem, czy podzbiór ocen.

**R05 — MUSI — raport nie ma czytelnego miejsca w nawigacji.**  
**Docelowo:** traktować raport jako część Kliniki, z aktywną sekcją i linkiem do archiwum raportów.

**R06 — PÓŹNIEJ — wywiady w raporcie jako rzeczywiste wejścia.**  
Wiersz wywiadu powinien prowadzić bezpośrednio do analizy, nie być samym streszczeniem.

**Pliki:** `WeeklyReport.tsx`, `ClinicPage.tsx`, `SiteHeader.tsx`.

---

## 3. Pierwsze 10 sekund na głównej

### Docelowy tekst i kolejność

**1. Widoczny H1**

> Zobacz, jak politycy budują przekaz.

**2. Jednozdaniowe wyjaśnienie produktu**

> spin.clinic wskazuje techniki perswazji i zestawia twierdzenia polityków ze źródłami.

**3. Krótkie wyjaśnienie Konsylium**

> Konsylium AI to kilka modeli analizujących ten sam materiał według wspólnych zasad. Ich oceny i źródła możesz sprawdzić.

**4. Liczniki**

Dla stanu ze zrzutów:

- **1834** przeczytane wpisy;
- **1151** wstępnie ocenionych;
- **36** opublikowanych diagnoz.

Pod nimi: „Od początku działania · aktualizacja: [czas danych]”. Liczb nie wpisywać na stałe.

**5. Akcje**

- Główna: **„Przeglądaj diagnozy”** → `/klinika/diagnozy`.
- Pomocnicza: **„Jak działa Konsylium AI”** → `/o-nas#konsylium`.

**6. Początek skanera**

Nagłówek: **„Wybrana diagnoza”**.  
Zakładki: **„Rządzący”**, **„Opozycja”**.  
Podpis: „Najwyższa siła spinu wśród [n] analiz z [okres]”.

W mobilnej karcie od razu widoczne: autor, werdykt, siła i tytuł diagnozy.

### Układ telefonu 390 × 844

Orientacyjny budżet:

- nagłówek: 56–64 px;
- wprowadzenie i objaśnienie: około 180–220 px;
- liczniki: około 76–96 px;
- akcje: około 88–100 px;
- poniżej początek wyniku.

To cel projektowy, nie gwarancja dla powiększonej czcionki. Przy większym tekście układ rośnie, niczego nie ucina.

Nie umieszczać przed wynikiem dużego załącznika ani wieloakapitowego opisu metodologii.

### Nawigacja

**Komputer:** zachować „Główna”, „Klinika”, „O nas”; obok jednoznaczne wyszukiwanie materiałów. Zegar przenieść poza główną hierarchię — bieżący czas nie jest czasem aktualizacji danych.

**Telefon:** logo, przycisk szukania i przycisk menu z obszarem 44 px. Menu zawiera wszystkie główne wejścia, w tym wsparcie i źródła. Nie ukrywać funkcji wyszukiwania bez zamiennika.

**Nawigacja lokalna Kliniki:** „Przegląd”, „Diagnozy”, „Wskaźniki”, „Wywiady”, „Przekazy”, „Raporty”. Na telefonie zwijane „W Klinice”, zamiast wielowierszowego zbioru niebieskich linków.

---

## 4. Ścieżki użytkownika

### 4.1. Czytelnik

1. **Wchodzi na główną.**  
   Przeszkoda: nie widzi liczników ani wyniku.  
   Poprawka: pierwszy ekran z punktu 3.

2. **Otwiera diagnozy.**  
   Przeszkoda: „baza” może znaczyć materiały lub analizy.  
   Poprawka: konsekwentnie „Baza diagnoz”.

3. **Wybiera temat lub autora.**  
   Przeszkoda: na telefonie nie widać, jakie filtry działają.  
   Poprawka: aktywne chipy i liczba wyników.

4. **Czyta diagnozę.**  
   Przeszkoda: najpierw cały wpis i obraz.  
   Poprawka: synteza oraz wynik przed rozwinięciem źródła.

5. **Sprawdza twierdzenie.**  
   Przeszkoda: źródła są małe i szare.  
   Poprawka: wyraźny tytuł źródła, domena, powiązanie z konkretnym twierdzeniem.

6. **Wraca do listy.**  
   Do sprawdzenia: zachowanie filtrów i miejsca przewinięcia po nawigacji wstecz.  
   Warunek odbioru: użytkownik wraca do tej samej listy, nie zaczyna od początku.

### 4.2. Dziennikarz

1. **Szuka zasad i kontaktu.**  
   Przeszkoda: „Dla redakcji” jest w częściowo uciętej stopce.  
   Poprawka: dostęp w menu i spisie „O nas”.

2. **Oceni wiarygodność procesu.**  
   Przeszkoda: marketing miesza się z listą technologii.  
   Poprawka: zakres analiz, ograniczenia, sposób doboru materiałów i polityka korekt przed szczegółami technicznymi.

3. **Wybiera materiał.**  
   Przeszkoda: daty publikacji i diagnozy mogą się zlewać.  
   Poprawka: osobne daty, numer i wersja analizy.

4. **Weryfikuje źródła oraz rozbieżności modeli.**  
   Przeszkoda: samo „2/3 zgodne” nie określa przedmiotu zgodności.  
   Poprawka: „Zgodność oceny końcowej: 2 z 3 modeli”; pełne wyniki dostępne niżej.

5. **Cytuje lub udostępnia.**  
   Poprawka: link kanoniczny, kopiowanie linku, informacja o autorstwie AI i data. Warunki wykorzystania muszą być łatwo dostępne; audyt nie rozstrzyga ich treści prawnej.

6. **Zgłasza błąd.**  
   Poprawka: jeden kontakt i formularz/mail z numerem diagnozy, bez wymogu szukania go w stopce.

### 4.3. Osoba przychodząca z X

1. **Kliknęła kartę diagnozy.**  
   Oczekuje tej samej oceny, autora i numeru.  
   Poprawka: te informacje na początku strony.

2. **Chce poznać uzasadnienie.**  
   Przeszkoda: pełny wpis poprzedza diagnozę.  
   Poprawka: „Dlaczego taka ocena?” bezpośrednio po syntezie.

3. **Sprawdza, czy to ocena człowieka czy AI.**  
   Poprawka: widoczna etykieta „Analiza AI” i link do zasad.

4. **Otwiera oryginał.**  
   Poprawka: „Otwórz wpis na X ↗”, bez mylenia z przyciskiem udostępniania.

5. **Widzi ograniczenia lub nie zgadza się.**  
   Poprawka: jawne ograniczenia i „Zgłoś błąd” obok akcji.

6. **Przechodzi dalej.**  
   Poprawka: „Zobacz inne diagnozy” prowadzące do bazy, nie kilka konkurencyjnych CTA.

---

## 5. Dane, wykresy i kolory obozów

### 5.1. Rekomendowana para

| Motyw | Rządzący | Opozycja |
|---|---|---|
| Ciemny | `#55B4FF` — błękit | `#F5A54A` — pomarańcz |
| Jasny | `#006DB3` — ciemny błękit | `#A65300` — ciemny pomarańcz |

To mocniejsza wersja obecnej opozycji chłodny/ciepły, bez czerwieni i zieleni przypisanej obozom.

Obliczony kontrast pełnych kolorów:

| Para | Rządzący | Opozycja |
|---|---:|---:|
| Ciemny kolor / `#171717` | 7,99:1 | 8,85:1 |
| Ciemny kolor / `#212121` | 7,18:1 | 7,95:1 |
| Jasny kolor / `#FFFFFF` | 5,47:1 | 5,44:1 |
| Jasny kolor / `#F4F4F4` | 4,97:1 | 4,95:1 |

Wartości obliczono z luminancji sRGB. Nie obejmują przezroczystości, mieszania z obrazem ani wszystkich stanów UI.

**Nie przenosić jasnych kolorów z motywu ciemnego na białe tło:** tam ich kontrast jest zbyt niski dla drobnego tekstu.

### 5.2. Równorzędność i daltonizm

Sam HEX nie zapewnia rozróżnialności dla każdej osoby. Docelowy system ma działać również bez rozpoznawania barwy:

- rządzący: pełne wypełnienie + znacznik koła;
- opozycja: delikatny ukośny wzór + znacznik kwadratu;
- obie serie: identyczna szerokość słupków, grubość linii i typografia;
- stała kolejność w legendach i na wykresach;
- tekstowe nazwy przy porównaniach;
- w wykresie skumulowanym separator 2 px w kolorze powierzchni.

Kolorów obozów **nie wolno stosować jako koloru werdyktu**. Pomarańcz opozycji i bursztyn częściowego spinu muszą być rozdzielone etykietą i kontekstem; nie stawiać samych kropek obu systemów obok siebie.

Przed odbiorem sprawdzić protanopię, deuteranopię, tritanopię i skalę szarości. Nie wykonano takiej symulacji w tym audycie.

Wymagania dotyczące kontrastu, użycia koloru i dostępności kontrolek należy odnosić do odpowiednich kryteriów, nie do samego wyglądu. Przyjęto cel 4,5:1 dla zwykłego tekstu i 3:1 dla istotnej grafiki względem sąsiadującego tła. [WCAG 2.2 — wymagania](https://www.w3.org/TR/wcag/)

### 5.3. Panel danych diagnozy

**Siła spinu**

- Jedna nazwa: „Siła spinu”.
- Wartość zawsze z `/100`.
- Wyjaśnienie przy pierwszym użyciu: „Ocena użycia technik perswazji. Nie jest oceną prawdziwości ani osoby”.
- Jeden kolor miernika skali we wszystkich widokach; kolorowy werdykt obok wystarcza.

**Konsylium**

- „2/3 zgodne” → „Zgodność oceny: 2 z 3 modeli”.
- Liczba członków dynamiczna.
- Brak odpowiedzi modelu nie może wyglądać jak wynik 0.
- Stałe `height: 80px` dla `.sc-scan-g` nie jest odpowiednie dla rozszerzanego składu. Lista głosów musi rosnąć albo mieć własne rozwinięcie.
- Pełna nazwa i wersja modelu dostępne w szczegółach; skrót w panelu jest dopuszczalny.

**Twierdzenia**

W `HomeSpinScanner.tsx` fallback liczy jako opinie niesprawdzone twierdzenia bez źródeł. Brak źródeł nie dowodzi, że wypowiedź jest opinią.

Docelowe odrębne kategorie:

- potwierdzone;
- sprzeczne ze źródłami;
- wprowadzające w błąd;
- niesprawdzone;
- opinie — tylko gdy rozpoznane jako opinie.

Nie sumować tych kategorii do „sprawdzonych” bez jasnej reguły.

**Techniki**

- „3 typy” → „3 techniki”.
- W obrębie rodzin: liczba unikalnych technik, nie liczba wystąpień, jeśli tak działa API.
- Nie porównywać długości lokalnie normalizowanych pasków między różnymi diagnozami. Albo wspólna skala, albo same liczby.

### 5.4. Co jeszcze warto pokazać

**MUSI**

1. Zakres dat i moment aktualizacji każdego zestawu.
2. Wspólną skalę obu histogramów.
3. Mianownik obok procentu: „7 z 12, 58%”.
4. Prawdziwe zero.
5. Rozróżnienie „0”, „brak danych”, „nie dotyczy”.
6. Krótkie zastrzeżenie o selekcji próby przy porównaniu obozów, nie dopiero na końcu strony.
7. Dane wykresu dostępne jako prosta tabela po rozwinięciu.

**PÓŹNIEJ**

- Rozkład zgodności modeli, z podaniem liczby diagnoz.
- Odsetek twierdzeń sprawdzonych i niesprawdzonych.
- Zakres analizy: tekst, obraz, nagranie.
- Liczba korekt i ich przyczyny.
- Przebieg pracy: od pobrania do diagnozy, jeśli etapy dotyczą tej samej kohorty wpisów.
- Zmiany liczby analiz w czasie z objaśnieniem zmian procesu.

Nie dodawać rankingów polityków według średniej siły spinu ani wykresów sugerujących reprezentatywne badanie całej sceny politycznej.

---

## 6. Gotowe teksty

### 6.1. Podtytuły stron i sekcji

| Miejsce | Tekst docelowy |
|---|---|
| Klinika | „Analizujemy wybrane wpisy i wywiady polityków. Pokazujemy techniki perswazji, oceny modeli AI i źródła dotyczące sprawdzanych twierdzeń.” |
| Baza diagnoz | „Znajdź analizę wpisu, autora lub techniki perswazji.” |
| Wskaźniki | „Zobacz, ile wpisów przetworzyliśmy i co pokazują opublikowane diagnozy. Porównania dotyczą analizowanych materiałów, nie całej polityki.” |
| Wywiady | „Analizy wypowiedzi gości oraz pytań i reakcji prowadzących — z cytatami i odwołaniami do nagrania.” |
| Przekazy | „Podsumowania tematów i sposobów argumentacji w przeanalizowanych wpisach rządzących i opozycji.” |
| Wiadomości | „Materiały ze źródeł. Każda karta prowadzi do oryginalnej publikacji.” |
| Twoje wiadomości | „Obserwuj wybrane tematy i źródła.” |
| Raport | „Najważniejsze obserwacje z diagnoz opublikowanych w tym tygodniu.” |
| Techniki diagnozy | „Jak zbudowano przekaz: techniki, cytaty i wyjaśnienia.” |
| Twierdzenia i źródła | „Co można sprawdzić i jakie źródła wykorzystano w analizie.” |

### 6.2. Pierwszy akapit „O nas”

> spin.clinic pomaga zrozumieć, jak politycy budują przekaz. Wskazujemy techniki perswazji, pokazujemy cytaty i zestawiamy sprawdzane twierdzenia ze źródłami. Analizy przygotowuje Konsylium AI — kilka modeli pracujących według wspólnych zasad. Możesz przejrzeć ich oceny, sprawdzić uzasadnienie i zgłosić błąd.

Nagłówek kolejnego fragmentu:

> Oceniamy wypowiedzi, nie ludzi.

Tekst:

> Siła spinu opisuje użycie technik perswazji w konkretnym materiale. Nie jest oceną autora ani miarą prawdziwości całej wypowiedzi. Twierdzenia o faktach sprawdzamy osobno.

### 6.3. Konsylium AI — krótko

> Konsylium AI to kilka modeli, które osobno analizują ten sam materiał według wspólnych zasad. Przy diagnozie pokazujemy uczestników, ich oceny i wykorzystane źródła. Skład może się zmieniać; analiza zachowuje informację o modelach, które ją przygotowały.

### 6.4. Konsylium AI — wersja rozwinięta

> Modele wskazują techniki perswazji, oceniają ich siłę i wyodrębniają twierdzenia do sprawdzenia. Kolejne etapy porównują wyniki, szukają źródeł i przygotowują uzasadnienie. Rozbieżność ocen jest informacją dla czytelnika, a nie dowodem, że większość musi mieć rację. Analizy mogą zawierać błędy.

**Zapowiedź Karty Konsylium:**

> Przygotowujemy Kartę Konsylium — dokument zasad analizy, publikacji i korekt. Opiszemy w nim role członków, sposób postępowania przy rozbieżnościach oraz zmiany składu.

Po jej publikacji:

> Zasady pracy, skład i sposób zgłaszania błędów opisuje Karta Konsylium.

„Podpisy” modeli przedstawić jawnie jako deklaracje wygenerowane przez konkretne wersje modeli, z datą i wersją dokumentu. Nie sugerować podpisu ani poparcia firm dostarczających modele, jeśli ich nie uzyskano.

### 6.5. Wsparcie

**H1:**

> Pomóż nam analizować kolejne wypowiedzi.

Obecne hasło „Politycy mają spin doktorów. My mamy spin.clinic” można zachować jako dodatkowy akapit, nie największy element strony.

**Lead — po potwierdzeniu stanu finansowania:**

> spin.clinic powstaje dzięki pracy twórcy i wsparciu czytelników. Wpłaty pomagają pokrywać pobieranie wpisów, analizy AI i utrzymanie serwisu.

**Kto za tym stoi:**

> Serwis rozwija jedna osoba, korzystając z narzędzi AI do programowania i analizy przekazów. Informacje o twórcy, operatorze i kontakcie znajdziesz poniżej.

Deklaracje dotyczące afiliacji zachować tylko w zakresie, który właściciel może potwierdzić.

**Na co idą pieniądze:**

> Finansujemy dostęp do wpisów na X, płatne etapy analizy, transkrypcje nagrań oraz serwer, bazę danych i kopie zapasowe. Część zadań korzysta z bezpłatnych limitów usług.

**Wpływ wspierających:**

> Wpłata nie daje wpływu na wybór analizowanych materiałów ani wynik diagnozy. Zgłoszenia błędów rozpatrujemy według tych samych zasad, niezależnie od tego, kto je przesyła.

**Cel:**

> Cel miesięczny: [kwota]. Zebrano: [kwota]. Aktualizacja: [data].

Nie publikować wartości domyślnego zera, gdy kwota jest nieznana.

### 6.6. Jeden słownik interfejsu

| Obecnie | Docelowo |
|---|---|
| Siła / nasilenie | Siła spinu |
| Ocenione na izbie przyjęć | Wstępnie ocenione wpisy |
| Zbadane konta | Konta z opublikowaną diagnozą |
| Przeczytane / ocenione bez rozróżnienia | Przeczytane / wstępnie ocenione / z diagnozą |
| Niejednoznaczne | Nie da się ocenić |
| Cały czas | Cały okres |
| Najsilniejsze | Najwyższa siła spinu |
| Otwórz stronę wywiadu | Czytaj analizę |
| Rozwiń uzasadnienie | Pokaż uzasadnienie |
| Terapia — co mówią źródła | Twierdzenia i źródła |
| 2/3 zgodne | Zgodność oceny: 2 z 3 modeli |
| 3 typy | 3 techniki |
| Post / wpis | Wpis |
| Wspomóż projekt | Wesprzyj projekt |
| Bez redakcji / nikt nie poprawia | Publikowane automatycznie; zasady korekt opisujemy w… |

Ostatniej etykiety użyć dopiero po ustaleniu rzeczywistej polityki korekt. „Nikt nie poprawia” jest niewłaściwe również dlatego, że opis Konsylium przewiduje redaktora i poprawki po kontroli.

### 6.7. Stany

- Ładowanie: **„Wczytujemy diagnozy…”**
- Brak publikacji: **„Nie ma jeszcze opublikowanych diagnoz dla tego wyboru.”**
- Brak wyników: **„Nie znaleźliśmy pasujących diagnoz.”** + „Wyczyść filtry”.
- Błąd: **„Nie udało się pobrać danych.”** + „Spróbuj ponownie”.
- Starsze dane: **„Pokazujemy dane z [czas]. Aktualizacja jest chwilowo niedostępna.”**
- Brak odpowiedzi modelu: **„Brak odpowiedzi”**, nigdy `0/100`.
- Brak raportu: **„Raport za ten okres nie został jeszcze opublikowany.”**

---

## 7. Plan wdrożenia — paczki po około 1–2 godziny

Szacunki dotyczą uporządkowania istniejącego interfejsu. Nowe pola API i polityka korekt mogą wymagać osobnej pracy. Nie łączyć całej migracji CSS w jeden duży commit.

Skróty ścieżek:

- **KIT:** `packages/ui/src/kit/`
- **CLINIC:** `packages/ui/src/components/clinic/`
- **APP:** `frontend-spin/app/`

### MUSI — przed zamknięciem wyglądu

| Kolejność | Paczka | Pliki | Wynik odbioru |
|---:|---|---|---|
| 1 | Naprawa szerokości i gutterów, 1–2 h | `KIT/kit.css`, `KIT/InfoPage.tsx`, `APP/wsparcie/page.tsx` | Brak poziomego overflow przy 320 i 390 px; jeden gutter. |
| 2 | Stopka, 1–2 h | `KIT/SiteFooter.tsx`, `APP/layout.tsx`, `KIT/kit.css` | Zwykła stopka; wszystkie linki dostępne; brak zasłaniania treści. |
| 3 | Tokeny powierzchni i kolorów, 1–2 h | `KIT/kit.css`, `APP/globals.css` | Jedna paleta publicznych stron, nowe kolory obozów, usunięte użycia brakujących tokenów w audytowanym zakresie. |
| 4 | Typografia i nagłówki, 1–2 h | `KIT/kit.css`, nowy `KIT/SectionHeader.tsx`, `KIT/index.ts` | Zatwierdzony kontrakt trzech rozmiarów nagłówka. |
| 5 | Wspólne kontrolki, 1–2 h | `KIT/Button.tsx`, `KIT/SearchField.tsx`, `KIT/kit.css` | Wspólne wysokości, promienie, focus i mobilne zawijanie długich CTA. |
| 6 | Archiwa — migracja stylu, 1–2 h | `CLINIC/ClinicArchives.tsx`, `KIT/kit.css` | H1, karty, filtry i przyciski zgodne z systemem; jeden `<main>`. |
| 7 | Przekazy — mobilna karta, 1–2 h | `CLINIC/ClinicExtras.tsx`, `KIT/kit.css` | Nagłówek bez ściskania AI; widoczna akcja i właściwe metadane. |
| 8 | Wspólne podsumowanie diagnozy, 1–2 h | `KIT/home/HomeSpinScanner.tsx`, nowy komponent w `CLINIC/` | Wydzielone dane wyniku do użycia na głównej, w diagnozie i raporcie. |
| 9 | Kolejność mobilnego skanera, 1–2 h | `KIT/home/HomeSpinScanner.tsx`, `KIT/kit.css` | Wynik przed pełnym źródłem; poprawna kolejność odczytu. |
| 10 | Pełna diagnoza, 1–2 h | `CLINIC/SpinDetail.tsx`, `KIT/kit.css` | Podsumowanie na początku, czytelne źródła, cały załącznik, „Zgłoś błąd”. |
| 11 | Pierwszy ekran głównej, 1–2 h | `KIT/home/HomeHero.tsx`, `HomeSpinTeaser.tsx`, `HomePage.tsx` | Obietnica, wyjaśnienie Konsylium, liczniki i jedna główna akcja. |
| 12 | Puste i błędne stany, 1–2 h | `HomePage.tsx`, `HomeReveal.tsx`, `SpinDetail.tsx`, `WeeklyReport.tsx` | Brak pustych wielkich powierzchni i mylenia błędu z brakiem treści. |
| 13 | Baza diagnoz, 1–2 h | `CLINIC/ClinicDatabase.tsx`, `SpinParts.tsx`, `KIT/kit.css` | Czytelne tytuły, krótkie opisy, autor i data, spójne nazwy filtrów. |
| 14 | Skale wykresów i zero, 1–2 h | `CLINIC/ClinicIndicators.tsx`, `KIT/kit.css` | Wspólna skala histogramów, zero bez słupka, oznaczone okresy. |
| 15 | Dostępność wykresów, 1–2 h | `CLINIC/ClinicIndicators.tsx`, `KIT/kit.css` | Czytelne osie mobilne, nazwy serii, alternatywna tabela danych i wzory. |
| 16 | Semantyka danych skanera, 1–2 h | `HomeSpinScanner.tsx`, `CLINIC/InterviewScanner.tsx`, typy w `lib/clinic.ts` | Opinie oddzielone od niesprawdzonych; brak odpowiedzi ≠ zero; dynamiczny skład. |
| 17 | Raport tygodnia, 1–2 h | `CLINIC/WeeklyReport.tsx` | Brak pustego panelu, krótki lead, spójny skaner, procenty z liczników. |
| 18 | Klinika — dolne sekcje, 1–2 h | `CLINIC/ClinicPage.tsx`, `ClinicExtras.tsx` | Zwarta lista diagnoz obu stron, spójne tabele i status niedostępnych wpisów. |
| 19 | Nawigacja, 1–2 h | `components/SiteHeader.tsx`, `KIT/NavMenu.tsx`, `ClinicArchives.tsx` | Dostępne wyszukiwanie mobilne, wspólna nawigacja Kliniki, aktywne raporty. |
| 20 | „O nas”, 1–2 h | `APP/o-nas/page.tsx`, `KIT/kit.css` | Projekt przed słownikiem, brak justowania, krótsza roadmapa, opis ról AI. |
| 21 | „Wsparcie” i słownik, 1–2 h | `APP/wsparcie/page.tsx`, `APP/o-nas/page.tsx`, `HomeHero.tsx` | Brak sprzecznych obietnic; jeden zestaw nazw i CTA. |
| 22 | Odbiór komputerowy i jasny motyw, 1–2 h | Wszystkie audytowane trasy | Kontrola 1440 i 768 px, oba motywy, długie treści. |
| 23 | Odbiór telefonu i dostępności, 1–2 h | Wszystkie audytowane trasy | Kontrola 390 i 320 px, klawiatura, zoom, stany, powrót fokusu. |

**Łącznie orientacyjnie: 23–46 godzin.** To zakres przekrojowy obejmujący dziesięć stron, wspólne komponenty, dane i odbiór, a nie jedna poprawka CSS.

Jeśli paczka 16 wymaga nowych pól backendu, najpierw usunąć nieuprawnione wnioskowanie w interfejsie i pokazywać „niesprawdzone”. Nowego rozpoznawania opinii nie upychać w dwugodzinnym zadaniu.

### PÓŹNIEJ

| Paczka | Zakres |
|---|---|
| Karta Konsylium | Wersjonowany dokument, role, zasady rozbieżności, korekt i zmian składu. Treść wymaga decyzji właściciela. |
| Dodatkowe wskaźniki | Zgodność modeli, kompletność sprawdzenia twierdzeń, zakres mediów, historia korekt. |
| Strona dla redakcji | Osobna ścieżka, materiały do cytowania i kontakt. |
| Eksport danych | CSV i stabilne odnośniki do przefiltrowanych zestawień, po ustaleniu zakresu danych. |
| Archiwum przekazów | Trwałe adresy szczegółów, jeśli obecny dialog utrudnia udostępnianie. |
| Porządkowanie martwego CSS | Usunięcie starszych komponentów i reguł dopiero po sprawdzeniu wszystkich ich użyć. |

### Checklista końcowego odbioru

Wygląd można uznać za zamknięty, gdy:

- [ ] Każda z 10 stron ma spójny nagłówek, kontener, przyciski i metadane.
- [ ] Przy 320 i 390 px nie ma poziomego przewijania całej strony.
- [ ] Pierwszy ekran głównej wyjaśnia produkt, Konsylium i skalę pracy.
- [ ] Pełna diagnoza na telefonie zaczyna się od wyniku.
- [ ] Żadna stopka ani warstwa nie zasłania aktywnej kontrolki.
- [ ] Zerowe wartości nie rysują dodatnich słupków.
- [ ] Porównywane histogramy mają wspólną skalę.
- [ ] Każdy procent ma określony mianownik i okres.
- [ ] Serie wykresów da się rozpoznać bez koloru.
- [ ] Skład Konsylium może rosnąć bez rozsadzenia panelu.
- [ ] Brak danych, błąd i zero mają różne komunikaty.
- [ ] Długie nazwisko, tytuł, źródło i przycisk nie rozszerzają kontenera.
- [ ] Klawiatura obsługuje menu, filtry, zakładki, rozwinięcia i dialogi.
- [ ] Po zamknięciu dialogu fokus wraca do kontrolki wywołującej.
- [ ] Oba motywy sprawdzono wizualnie, także w stanach hover, focus i disabled.
- [ ] Pełnostronicowy zrzut po przewinięciu nie zawiera niewyjaśnionych pustych bloków.
- [ ] Teksty o finansowaniu, automatyzacji i korektach opisują stan faktyczny.

**Rekomendacja końcowa:** zatwierdzić skaner i wskaźniki jako wzorce, wdrożyć paczki „MUSI”, a następnie zamrozić role komponentów i tokeny. Dalsze funkcje powinny korzystać z tego systemu zamiast dopisywać kolejne lokalne odmiany.