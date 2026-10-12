# Przegląd Projektanta nr 1 (przeszłość.today)

**Ograniczenia:** `przeszlosc.today` zablokowane przez proxy środowiska (403 CONNECT), więc brak zrzutów 1440/390 i pomiarów w przeglądarce
(Playwright/chromium są dostępne). `frontend-spin` nie ma zainstalowanych zależności, więc `npx tsc --noEmit` nie dał wiarygodnego wyniku
(błędy braku `process`/`@tanstack/react-query` wynikają z braku `node_modules`); zmiany dotyczą wyłącznie CSS. Poniżej analiza statyczna kodu CSS; dowody to reguły i wymiary z kodu. Trzeba je potwierdzić pomiarem po wdrożeniu.

| id | miejsce | dowód | prawo UX / zasada | poprawka | status |
|----|---------|-------|-------------------|----------|--------|
| P1 | `.px-dn__seg button` (Wspólne mianowniki) | min-height 40 px na komputerze i telefonie | Fitts, cele 44 px | 44 px; wiersz `.px-dn__card` 44→48 px (2 px ramka x2), wszystkie 3 boksy równo | zrobione |
| P2 | `.px-modes button` | min-height 40 px na komputerze | Fitts | 44 px | zrobione |
| P3 | `.px-beta` (link z etykietą Beta) | min-height 24 px | Fitts | pseudo-element `::after` powiększa cel do ok. 44 px, wygląd bez zmian | zrobione |
| P4 | `.px-mt__foot`, `.px-mt__foot .px-quiet` (boksy tematu) | 36 px | Fitts; równe stopki | 44 px we wszystkich trzech boksach | zrobione |
| P5 | `.px-flow__categories`, `.px-dev__tabs` | `overflow-x:auto`, pasek `thin` | styl: bez pasków przewijania | ukryty pasek, przewijanie dotykiem zostaje | zrobione |
| P6 | `.px-chips button`, `--px-tap: 36px` na komputerze (kit.css) | 36 px | Fitts | podnieść do 44 wymaga decyzji (gęstość układu chipów) | do decyzji |
| P7 | `.px-pp__sum`, `.px-pp__proof` | ujemne marginesy (-24/-16 px) do ściągania sekcji | Proximity, stałe odstępy | zastąpić rytmem gap; wymaga pomiaru | do decyzji |
| P8 | etykiety 11–12.5 px (`.px-wm__status`, `.px-dn__seg`, `.px-dev__tabs small`) | font 11–12.5 px | czytelność | pomiar kontrastu i skali na zrzucie | do decyzji |

Nie zmierzono: wysokości i krawędzie boksów w rzędach, odstępy sekcji, wystawanie poza 390 px, łamanie tytułów (CSS wymusza `nowrap` + wielokropek w tytułach, więc łamanie jest mało prawdopodobne).
