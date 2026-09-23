# Identyfikacja i szaty graficzne spin.clinic

Stan decyzji na 24 września 2026 (etap 1 UI kitu, `kit/design@7051357`). Ten dokument opisuje
**docelową** identyfikację — kit w `packages/ui/src/kit/**` i witrynę `/ui-kit`. Zobacz sekcję
«Stan przejściowy» na końcu: część tego, co tu opisane, **jeszcze nie działa** na żywych stronach.

## Identyfikacja domyślna

Nowa szata to **czerń/biel z niebieskim akcentem**: głęboka, prawie czarna noc albo czysta biel,
skruglone karty ze zdjęciami, jeden akcentowy kolor zamiast trzech konkurujących. Poprzedni,
gazetowy kierunek (`.material-box` bez zaokrągleń, cienie wyłączone, bursztynowo-koralowa paleta
trzech szat) jest w całości zastępowany. Referencja doboru: układ w duchu USA Today —
zaokrąglone karty z obrazem, czysta hierarchia typograficzna, niebieski jako jedyny kolor
identyfikacji.

Wersja ciemna (**Noc**) pozostaje wyglądem domyślnym.

## Znak

Bez zmian względem poprzedniej decyzji: rezygnujemy z osobnego sygnetu z literami `S`, `P`, `I`,
`N`. Podstawowym znakiem jest sam lowercase wordmark `spin.clinic`, bez symbolu medycznego, okręgu,
kropek ani dodatkowego monogramu. Favicon i avatar wymagają odrębnego rozwiązania opartego na
wordmarku.

## Typografia

**Montserrat** (`next/font/google`, `subsets: ["latin", "latin-ext"]`) zastępuje superrodzinę
IBM Plex w całości:

- jeden krój na wszystko — nawigację, treść interfejsu, tytuły kart, przyciski; zmienna oś wagi
  (`axes: ["wght"]`) zamiast sześciu statycznych plików;
- **bez antykwy.** Stary bursztynowy kierunek rezerwował IBM Plex Serif dla tytułów ważnych nitek
  i cytatów Dr Spin — nowy widok jest w pełni gotycki, jedna rodzina, jedna intonacja;
- **cyfry tabularne zamiast kroju mono.** Tam, gdzie poprzednio źródło/czas/daty/liczniki/ślad
  dowodowy szły przez IBM Plex Mono, teraz jest `font-variant-numeric: tabular-nums` na samym
  Montserracie (klasa `.sc-t-meta` w kicie) — liczby wyrównują się w kolumnę bez drugiej rodziny
  krojów. Systemowy `ui-monospace` zostaje wyłącznie dla prawdziwych identyfikatorów i adresów,
  gdzie ważne jest rozróżnienie `0/O` i `1/l/I`.
- `latin-ext` jest **obowiązkowy** — polska diakrytyka (`ą ć ę ł ń ó ś ź ż`) żyje w tym podzbiorze;
  bez niego tekst po cichu podmienia się na zapasowy krój i jedzie po szerokości i kolorze.

Skala kegli (kit → `--sc-t-*`), z kompensacją optyczną wagi między motywami (jasny tekst na ciemnym
tle czyta się grubiej przy tym samym nacięciu):

| Rola | Kegiel | Waga: Noc / Dzień |
|---|---|---|
| `display` (nagłówki sekcji, hero) | `clamp(34–56px)` | 600 / 700 |
| `title-l` (tytuł dużej karty, tytuł oveleja) | 26px | 600 / 700 |
| `title-m`…`title-xs` (tytuły kart) | 20 / 16 / 14px | 500 / 600 |
| `body` (proza, opisy) | 15px | 400 / 400 |
| `meta` (źródło · data, tabularne) | 12px | 500 / 500 |
| `caption` (odznaki, nadtytuły, WERSALIKI) | 11px | 600 / 600 |

Minimalny kegiel w bibliotece — 11px. Obecne 7px/8px/9.5px w `globals.css` znikają wraz z migracją
żywych stron na etapie 2 — to główna utracona czytelność, którą ten kierunek naprawia.

## Dwie szaty + Auto

Trzy szaty użytkownika (Ciemna/Jasna/Pastelowa) ustępują **dwóm**: **Noc** i **Dzień**, plus
**Auto** (respektuje `prefers-color-scheme` urządzenia na żywo — nie jest trzecią szatą, tylko
sposobem wyboru). Wybór jest przypisany do konta i odtwarzany na urządzeniach użytkownika;
niezalogowany może zachować go lokalnie. Przełącznik (`ThemeToggle` w kicie) to sekwencja trzech
pozycji Noc/Dzień/Auto z przejeżdżającym wskaźnikiem — stan czytelny bez koloru (etykieta tekstowa
+ pozycja), nie trzy kolorowe paski jak poprzednio.

| Rola | Noc | Dzień |
|---|---|---|
| Tło / powierzchnia | `#08090b` / `#111317` | `#ffffff` / `#ffffff` |
| Tekst główny / drugorzędny | `#f5f6f7` / `#a0a6af` | `#0b0c0e` / `#4b5159` |
| **Akcent (jedyny kolor identyfikacji)** | `#4a9eff` | `#0a62d0` |
| Kolor na akcencie | `#04101f` (prawie czarny) | `#ffffff` |
| Kromka | `#262a31` | `#e3e5e9` |

Akcent jest **wyłącznie niebieski** w obu szatach — bez bursztynu, koralu, śliwki czy zieleni
zarezerwowanych dla identyfikacji, jak w poprzednim wariancie trzech szat. Pełna tabela tokenów —
`docs/UI_KIT.md` §2.1.

Kontrast liczony, nie na oko: noc — akcent na tle 7.23, tekst 18.4, wtórny 7.59, `--sc-on-accent`
na akcencie 6.94; dzień — akcent 5.72, biały na akcencie 5.72, tekst 19.6, wtórny 8.01. Biały tekst
na nocnym akcencie dawał 2.75:1 (porażka) — dlatego kolor na akcencie w nocy jest prawie czarny,
nie biały.

System respektuje `prefers-color-scheme`, `prefers-reduced-motion`, `prefers-reduced-transparency`
i `prefers-contrast`.

## Skala promieni (zaokrąglenia)

Zamiast dawnego «brak zaokrągleń wcale» (`.material-box` 184×120px bez `border-radius`), nowy
widok jest w pełni zaokrąglony, skalą koncentryczną — wewnętrzny promień zawsze mniejszy o
odstęp od zewnętrznego, żeby narożniki karty i jej medium nie rozjeżdżały się wizualnie:

```
xs 6px · sm 10px · md 14px · lg 18px · xl 22px · 2xl 28px · pill 999px
```

Karta `mini`/`compact` — `lg` (18px), `medium` — `xl` (22px), `large` — `2xl` (28px). Panel
dropdownu i przycisk pill — `xl`/`pill`.

## Głębia: cień + wewnętrzna kromka, NIE na kartach

Zamiast dawnego `.shadow-sm { box-shadow: none }` (cienie były systemowo wyłączone), głębia wraca
przez dwuwarstwowy przepis:

1. **Cień** (`--sc-e-1`/`-2`/`-3`/`-menu`) — na prawie czarnym tle cień sam w sobie ledwo czytelny,
   więc rośnie z rozmiarem/wagą elementu (panel dropdownu i portal dostają najgłębszy, `-menu`/`-3`).
2. **Wewnętrzna kromka** `--sc-ring: inset 0 0 0 1px var(--sc-hairline)` — cienki jasny/ciemny
   hairline WEWNĄTRZ krawędzi, dokłada się do cienia. To ona, nie kolorowa ramka, oddziela
   powierzchnię od tła na ciemnym motywie.

**Karty są wyjątkiem.** `.sc-card` jawnie zeruje `--sc-ring` (`border: 0`, tabela cienia bez
`inset`) — u kart nie ma ani ramki, ani wewnętrznej kromki wcale. Separację od tła niosą wyłącznie
cień i poświata (patrz niżej); dodanie kromki do karty rozmyłoby efekt «podświetlono z tyłu» na
ступни A/B. Przyciski, panele, stopka, nawigacja i inne powierzchnie zachowują `--sc-ring`.

## Reguła poświaty (glow)

Poświata przy najechaniu jest **wyłącznie u kart** — `.sc-card` na wszystkich stopniach (A/B),
klon podglądu w warstwie portalu i pełnoekranowa powierzchnia materiału. **Żaden inny element jej
nie dostaje**: przyciski, linki, punkty menu, ikony, kontrolki i linki stopki przy najechaniu
zmieniają wyłącznie kolor tekstu/ikony — bez ореolu, bez podniesienia, bez wzrostu cienia.

Kolor poświaty — **wyłącznie niebieski** z palety akcentu (`--sc-glow`/`--sc-glow-strong`,
zbudowane na `rgba` akcentu tej szaty). Żadnego bursztynu — to jednoznaczna decyzja właściciela
(23.09): «янтаря в системе нет вообще», wcześniejsze wzmianki o bursztynowej poświacie w
dokumentacji roboczej są historyczne i nieaktualne.

Poświata **rośnie razem z kartą**: na stopniu A — `--sc-glow-ring` (pierścień + rozmyty ореol
24px), na stopniu B (rozwinięty podgląd) — `--sc-glow-ring-strong` (szerszy, jaśniejszy pierścień
44px) — im większa/ważniejsza powierzchnia karty w danym momencie, tym mocniejsza poświata.
Zawieszony blok dodatkowy pod rozwiniętą kartą i klon w warstwie portalu niosą **ten sam**
pierścień co karta — poświata jest jedną, ciągłą właściwością powierzchni, nie osobną warstwą.
Implementacyjnie to zewnętrzny `box-shadow` samego elementu (zmienna `--sc-ring` przełącza się na
pierścień), nie pseudoelement — bo jak tylko framer-motion nadaje elementowi `transform`, staje
się on kontekstem nakładania i wewnętrzny pseudoelement rysowałby się NAD tłem, nie za nim.

Klawiatura dostaje dokładnie to samo, co najechanie myszą (`:focus-visible` i stopień A/B
osiągalny fokusem). `@media (hover: hover)` chroni przed «zaklejonym» stanem po tapnięciu na
dotyku. Przy zredukowanym ruchu poświata **zostaje** (zmiana przezroczystości nie jest
westybularna), znika tylko podniesienie/skalowanie.

## Role kont i reakcje

Role z poprzedniej wersji zostają, kolory są przemapowane na nowe tokeny kitu. Nazwa roli i
uprawnienia są zawsze podane **tekstem** — kolor nigdy nie jest jedynym nośnikiem znaczenia (ta
zasada się nie zmienia).

W MVP: **Ordynator** (administrator) i **Doktor: [specjalizacja]** (autoryzowany autor). W etapie
II dochodzi **Pacjent** (zwykły użytkownik).

- **Ordynator** — neutralna plakietka: tło `--sc-surface-3`, tekst `--sc-text`, kontur
  `--sc-line-strong`. Oznacza uprawnienie administracyjne, nie ocenę jakości wypowiedzi — celowo
  bez akcentu, żeby nie konkurować wizualnie z primary CTA.
- **Doktor** — kontur `--sc-accent` (niebieski), bez wypełnienia, plus jawna specjalizacja tekstem
  obok. Nie używamy wypełnionego akcentowego tła jako plakietki — to zarezerwowane dla `Button`
  `primary`.
- **Pacjent** (etap II) — `--sc-text-2` na `--sc-surface-2`, etykieta tekstowa, status nie obniża
  widoczności merytorycznej treści.

Reakcja na box jest opinią społeczności, nie oceną prawdziwości. Wariant dodatni —
`--sc-positive` (`#4ed18a` noc / `#147a4b` dzień), ujemny — `--sc-negative` (`#ff6b6b` noc /
`#c42b2b` dzień, ten sam token co `--sc-live`), oba na delikatnie zabarwionym tle. Zawsze
towarzyszą im znak `+`/`−`, etykieta tekstowa i liczba — interfejs czytelny bez koloru. `--sc-live`
zostaje zarezerwowany dla czasu/pilności (głosowania na żywo, alerty) — reakcja ujemna go nie
przechwytuje wizualnie inaczej niż wspólnym tokenem koloru z jasnym rozróżnieniem przez kontekst i
etykietę.

## Стан переходный / Stan przejściowy

To, co ten dokument opisuje, działa **na razie tylko** w `packages/ui/src/kit/**` i na witrynie
`/ui-kit`. Żywe strony (`/`, `/search`, `/zrodla`, `/konto`, `/editor/*` i inne) pozostają **bez
zmian** do etapu 2:

- `frontend-spin/app/globals.css` ma zero zmian — trzy stare szaty (Ciemna/Jasna/Pastelowa),
  bursztynowo-koralowa paleta, `.material-box` bez zaokrągleń i `.shadow-sm { box-shadow: none }`
  wciąż obowiązują na żywych stronach;
  ​
- `ThemeSwitcher.tsx`, `localStorage['spin-theme']` i skrypt anty-FOUC w `layout.tsx` (odczytujący
  ten sam klucz) nie są tknięte — `pastel` jako trzecia szata żyje dalej w żywym przełączniku i w
  wyliczeniu bazy danych po stronie backendu, mimo że w samym kicie jest już tylko aliasem szaty
  dziennej;
- żywe strony pozostają na superrodzinie **IBM Plex** (`@fontsource/ibm-plex-*` w `layout.tsx`);
  Montserrat jest podłączony wyłącznie jako zmienna CSS i używany tam, gdzie kod jawnie sięga po
  `--sc-font-sans` — czyli tylko wewnątrz kitu i na `/ui-kit`;
- role/reakcje w tym dokumencie opisują docelowy wygląd; sam mechanizm ról i ich nazwy w backendzie
  nie zmieniają się w tym etapie — zmienia się wyłącznie to, jakimi tokenami kolorystycznymi
  przyszłe komponenty będą je rysować;
- `docs/UI_KIT.md` ma pełną listę technicznych ograniczeń etapu 1 (dropdown nieportalizowany w
  lentach, `template.tsx` tylko na `/ui-kit` itd.) — ten dokument ich nie powtarza.

Etap 2 przenosi wygląd na żywe strony: usuwa `pastel`, przełącza `body` na Montserrat, przenosi
promienie z `globals.css` do komponentów i sprząta kod, który stanie się martwy.

## Stały układ głównej

Niezależnie od szaty i etapu zachowujemy kolejność bloków głównej:

1. Wszystkie wiadomości,
2. TOP 10,
3. Top temat dnia,
4. jedna nitka Dr Spin, wyjątkowo dwie,
5. jedna jawnie oznaczona nitka sponsorowana,
6. nitki autoryzowanych dziennikarzy.

Nitka wydarzenia może mieć duży punkt wyjścia po lewej oraz chronologiczny, przewijany pasek
powiązanych boxów po prawej. Ta kolejność jest decyzją treściową, niezależną od szaty graficznej —
obowiązuje też po migracji głównej na etapie 2 (tam, gdzie plan UI kitu opisuje wizualny układ
poszczególnych bloków — `docs/UI_KIT_PLAN.md` → «Дизайн страниц и панелей» → «/ — главная» —
kolejność bloków jest zgodna z listą powyżej).
