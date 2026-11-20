# Teraz: koncepcje wizualne mapy (G1)

Stan: **zrobione i sprawdzone** (zrzuty 1440 i 390 px, pomiar położeń, panel designu), 20.11.2026.
To prototypy wyglądu, nie kod produkcyjny. Dane są próbne (losowane z ziarnem, powtarzalne).

| Plik | Co to jest |
|---|---|
| `A-rzezba-nocna.html` | Koncepcja A: ciemna mapa z cieniowaną rzeźbą, cienkie warstwice, pulsujące pierścienie |
| `B-makieta-polski.html` | Koncepcja B: pochylona kamera, powiaty jako płytkie bryły, słupki, świetlna siatka, 3 zdania RCB |
| `REKOMENDACJA.md` | Jedna strona: którą koncepcję brać i co z drugiej przenieść |
| `zrzuty/` | Zrzuty 1440 i 390 px: widok zwykły i tryb prosty (A), widok zwykły i wybrany alert RCB (B) |
| `narzedzia/zbuduj.py` | Skrypt, który skleja szablony z danymi w dwa samodzielne pliki HTML |
| `narzedzia/zrzuty.mjs`, `narzedzia/sprawdz.mjs` | Zrzuty z pomiarem położeń i test działania (Playwright, headless) |
| `narzedzia/szablony/` | Źródła: `a.html`, `b.html`, `wspolne.css`, `wspolne.js` (edytuj tu, nie w wynikowych plikach) |

## Jak otworzyć

Pliki HTML są samodzielne (dane wbudowane, bez internetu): wystarczy otworzyć je w przeglądarce
(dwuklik albo przeciągnięcie do okna). Między koncepcjami przełącza przycisk w prawym górnym rogu.

## Jak przebudować (po zmianie szablonów)

Z katalogu głównego repozytorium (katalog podręczny musi być poza gitem albo ignorowany):

```
python3 -I docs/teraz-koncepcje/narzedzia/zbuduj.py .warsztat-zrzuty/dane
```

Skrypt sam pobiera do katalogu podręcznego uproszczone granice powiatów i kafle wysokości (źródła niżej).

Zrzuty i test działania (Playwright w katalogu roboczym, poza gitem; skrypty szukają pakietu obok siebie, więc kopiujemy je tam):

```
npm --prefix .warsztat-zrzuty/narzedzia install playwright@1
cp docs/teraz-koncepcje/narzedzia/zrzuty.mjs docs/teraz-koncepcje/narzedzia/sprawdz.mjs .warsztat-zrzuty/narzedzia/
node .warsztat-zrzuty/narzedzia/zrzuty.mjs docs/teraz-koncepcje .warsztat-zrzuty/robocze
node .warsztat-zrzuty/narzedzia/sprawdz.mjs "$PWD/docs/teraz-koncepcje"
```

`zrzuty.mjs` robi 14 zrzutów (1440 i 390; zwykły, prosty, bez ruchu, RCB) i zapisuje `pomiar.json` z położeniami boksów; do `zrzuty/` trafia wybrane 8.

## Co pokazują oba prototypy (wspólne)

- **Miara:** „liczba komunikatów w okresie” na powiat, jedna barwa (bursztyn), 4 progi (1, 2–3, 4–6, 7+). Barwa, wysokość i ruch nie kodują wagi; pod tytułem stoi „nie poziom zagrożenia”.
- **Brak danych:** wzór kreskowany i podpis „brak w naszych danych” (źródło, okres, data w opisie powiatu), w legendzie „to nie znaczy, że jest spokojnie”. Nigdy zero ani zieleń. Na osi czasu kreskowane są dni bez części danych.
  Przykład: 14 powiatów lubuskiego, bo źródło WCZK lubuskie (scraping) nie odpowiada od 17.11, 21:40.
- **Zero:** osobny stan „mamy dane, w okresie bez komunikatów”.
- **Zasięg przybliżony:** linia przerywana z podpisem; nie liczymy go do powiatów (nie poszerzamy zasięgu ponad źródło).
- **Wyłączenia:** wzór kropkowany i kropkowany obrys, „wyłączone w treści komunikatu (sprawdź oryginał)”.
- **Oś czasu PRZESZŁOŚĆ / TODAY:** histogram 30 dni, suwak końca okresu z widocznym uchwytem (klawiatura: strzałki), długość okresu (1 dzień, 7 dni, 30 dni), „Wróć do dziś”.
- **Lista zdarzeń pod mapą:** czas, łącze, tytuł, miejsce i źródło; status tylko przy wyjątkach (zgłoszone, odwołane). Na komputerze lista wypełnia kolumnę do wysokości panelu obok.
- **Panel źródeł:** etykiety łączy (X, API, MCI, RSS, scraping, WebSocket, plik, ręcznie) i zdrowie źródła (znak + słowo, nie sama barwa).
- **Tekstowy odpowiednik mapy:** „Najwięcej komunikatów” i rozwijana tabela wszystkich 380 powiatów; etykieta mapy zmienia się z okresem.
- **Tryb prosty:** bez rzeźby, ruchu i 3D; większy tekst.
- **Animacje:** domyślnie według `prefers-reduced-motion`, przełącznik w pasku zapamiętany w przeglądarce; w trybie prostym nieaktywny. Esc zamyka dymek.

B dodatkowo: 3 karty zdań RCB (wiele województw; wyłączenia; lista powiatów z jednostką nierozpoznaną, czyli zasięgiem przybliżonym).
Kliknięcie karty pokazuje zasięg na makiecie (wymienione: obrys bursztynowy; wyłączone: wzór kropkowany).

## Źródła danych w prototypach

- Granice powiatów: Państwowy Rejestr Granic (GUGiK), uproszczenie z github.com/ppatrzyk/polska-geojson (pliki `*-min`).
  Plik jest starszy niż rejestr TERYT: „jeleniogórski” zamieniono na „karkonoski”. Kody TERYT z `frontend-spin/public/teraz/teryt-powiaty.json`.
- Rzeźba: AWS Terrain Tiles (Terrarium, z=6; m.in. SRTM i EU-DEM), siatka ok. 3 km, wygładzona. Szczyty są zaniżone (Tatry ok. 2100 m zamiast 2499 m).
  W produkcji: NMT GUGiK albo Copernicus GLO-30/90 i atrybucja na mapie.
- Komunikaty, zdania RCB, stany źródeł: **próbne**. Zdania RCB są napisane na potrzeby prototypu, nie są cytatami.

## Panel designu (20.11.2026)

Trzech niezależnych recenzentów (UX i wygląd, czytelnik-laik, ruch i dostępność) oceniło zrzuty i kod. Werdykt jednogłośny: A z kartami RCB z B.
Wprowadzone po panelu: skala 4 klas o mocniejszym kontraście; przygaszona rzeźba pod danymi; tabela wszystkich powiatów; dymek bez `role=status`, zamykany Esc;
ogłoszenie zasięgu po wybraniu karty RCB; jeden obrys strefy RCB 2 px; kreskowane dni bez danych na osi; widoczny uchwyt suwaka; przyciski okresu 44 px ze znakiem ✓;
„Animacje” zapamiętane i nieaktywne w trybie prostym; „TODAY” z `lang="en"`; fokus po „Pokaż więcej”; podpisy na mapie z podkładem i bez nachodzenia;
teksty dla laika (brak danych, pierścień, słupek, zasięg przybliżony z tematem); kolejność na telefonie: mapa, oś czasu, legenda.
Nie wprowadzone (do etapu budowy): pole „Wpisz miejscowość”, ukrycie typów łączy pod „szczegóły”, legenda zwijana na telefonie, wybór powiatu klawiaturą na samej mapie.

## Pomiar i sprawdzenie

- Playwright (headless), 1440×900 i 390×844: 14 zrzutów, 0 błędów konsoli, 0 przepełnień poziomych, żaden tytuł boksu nie łamie się.
- `sprawdz.mjs`: suwak przesuwa okres strzałkami (14–20.11 na 12–18.11), „30 dni” daje 22.10–20.11, tabela ma 380 powiatów (14 z brakiem danych),
  „Animacje” zapisują wybór, karta RCB ogłasza „19 powiatów wymienionych, 3 wyłączone w treści”, a tabela pokazuje te 3 jednostki jako wyłączone.
- Równe wysokości: wiersze źródeł 58 px, wiersze zdarzeń 56 px (78 px na telefonie), karty RCB 214 px.
- Dolne krawędzie obu kolumn na 1440 px wyrównane: A 1940/1940 px, B 1926/1926 px (także w trybie prostym i z wybranym alertem).
- Pierwszy element pod paskiem: 24 px na 1440, 16 px na 390.
- Narzędzie `gust/odstepy.js` właściciela (ścieżka Windows) nie było dostępne na serwerze roboczym: zasadę 10 sprawdzono pomiarem położeń, nie tym skryptem.

## Otwarte pytania do właściciela

- „MCI” w liście łączy przepisano dosłownie ze zlecenia. Jeśli chodziło o MCP (Model Context Protocol), to jedna zmiana w `wspolne.js` (`LACZA`, `ZRODLA`).
- Wzorce z `C:\Users\User\rysy-ai` (src\niebo, widok3d.js) nie były dostępne na serwerze roboczym; język wizualny oparto na palecie ze zlecenia.
