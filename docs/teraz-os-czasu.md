# Teraz: oś czasu i przełącznik TODAY / PRZESZŁOŚĆ (W4)

Stan na 20.11.2026. Gałąź robocza `warsztat/W4` (zlecenie: claude/teraz-11 na W1 = claude/teraz-09).
Dokument opisuje tylko W4; wspólne plany (`docs/notes/PLAN_AKTUALNY.md`, `HANDOFF_AI.md`) uzupełnia koordynator przy scalaniu W1-W5,
żeby równoległe gałęzie nie kłóciły się o te same linie.

## Co jest

| Plik | Rola |
|---|---|
| `frontend-spin/app/przeszlosc/teraz/czasOsi.ts` | czysta logika: doby w strefie Warszawy (także 23 i 25 godz.), przedziały jak `historia.kubelki`, adres URL, kroki suwaka, odtwarzanie, walidacja `os/` i `wpisy/?na=`, luki, teksty |
| `frontend-spin/app/przeszlosc/teraz/useHistoria.ts` | stan osi (adres i pamięć), zapytania `os/` i `wpisy/?na=`, wybór danych dla mapy, listy i tabeli |
| `frontend-spin/app/przeszlosc/teraz/Os.tsx`, `os.css` | pas osi: przełącznik, baner stanu, histogram z suwakiem, ◀ ▶, odtwarzanie, prędkość, krok |
| `frontend-spin/tests/160-*.test.cjs`, `161-*.test.cjs` | 22 testy `node --test` (logika czasu i montaż) |

Integracja (minimalna, bo W2 zmienia panel i kartę równolegle): `TerazPage.tsx` dostał 7 linii (import, `useHistoria`,
`useWpisyWTrybie` na wyniku dotychczasowego `useWpisy`, warunek „brak komunikatów” tylko przy pełnym stanie archiwum, jedna linia
montowania `<Os …/>`), a `page.tsx` import `./os.css` (testy renderujące `TerazPage` nie znają arkuszy CSS).
`czas.ts` już istniał (formatowanie dat), więc nowa logika jest w `czasOsi.ts`.

## Zachowanie

- **Adres:** `?tryb=przeszlosc&na=2026-11-18T22:59:59Z&krok=godzina`. Archiwum wymaga obu parametrów; błędny moment = TODAY,
  przyszłość jest dociągana do teraz, moment starszy niż 30 dób do początku osi. Wartości domyślne (TODAY, krok dzień) znikają z adresu.
- **Pamięć widoku:** krok i prędkość (`localStorage`, klucz `przeszlosc.teraz.os.v1`). Trybu i momentu celowo nie pamiętamy:
  po powrocie na stronę zawsze widać dane bieżące, archiwum otwiera tylko link.
- **Moment przedziału** to jego ostatnia sekunda (dzień: 23:59:59, godzina: hh:59:59), nigdy później niż teraz. Okno komunikatów
  (1 godz., 24 godz., 7 dni z panelu) liczy się wstecz od momentu: `wpisy/?od=na-okres&na=na`.
- **Oś dni:** 30 dób do dziś. **Oś godzin:** doba wybranego momentu; strzałka za krawędzią doby przechodzi do sąsiedniej.
- **Klawiatura:** natywny suwak (strzałki, Home, End, PageUp, PageDown), przyciski ◀ ▶, przełączniki z `aria-pressed`.
- **Odtwarzanie:** z TODAY albo z końca osi startuje od początku osi (oś godzin: od północy, „animacja dnia”), następna klatka
  dopiero po wczytaniu bieżącej i jest pobierana z wyprzedzeniem; stop na ostatnim przedziale. Przy `prefers-reduced-motion`
  przycisk zostaje na swoim miejscu, ale jest wyłączony (w miejscu tempa napis „Bez animacji”), zostaje krok ręczny.
- **Podpis luk:** jedna krótka linia („Kreskowane = brak w naszych danych, nie zero (8 dni)”) jako przycisk „Szczegóły”;
  panel podaje legendę, nazwy źródeł bez odpowiedzi i retencję (Esc zamyka i oddaje fokus). Oś w trakcie wczytywania ma
  przerywaną linię, a przy błędzie `os/` wszystkie przedziały są kreskowane („nie wiemy”), nigdy pusta oś udająca zera.
- **Luki:** `liczba: null`, `luka_retencji`, `luka_zrodel` są kreskowane z podpisem; zero przy luce zamieniamy na „nie wiemy”.
  Luka częściowa (liczba znana, część źródeł bez danych) to słupek z kreskowaniem i opis „co najmniej N”.
  Rekordy `brak_danych` z `wpisy/?na=` są liczone osobno („N komunikatów bez wersji z tej chwili”), nie jako zły format.
- **Archiwum:** baner „Archiwum, nie bieżące dane”, „Stan na <dzień>, godz. <hh:mm>”, bursztynowa ramka sceny;
  „Brak komunikatów” nie pojawia się, gdy stan z tamtej chwili jest niepełny (`niepelne`).
- Dane na żywo odświeżają się dalej także w archiwum (powrót do TODAY bez czekania).

## Sprawdzenie (zrobione i sprawdzone)

- `node --test tests/139-*.cjs tests/14[0-8]-*.cjs tests/16[01]-*.cjs`: 136/136 (stare testy Teraz bez zmian).
- `npm run typecheck`: bez błędów (przy `csstype` 3.2.3 jak w `pnpm-lock.yaml`; npm bez lockfile dociąga 3.2.4, co psuje typy `packages/ui`).
- `npm run build`: kompilacja bez błędów (fonty Google niedostępne z serwera roboczego, build użył zapasowych).
- Playwright headless, dane próbne, 1440×900 i 390×844: 0 błędów konsoli, 0 przepełnień poziomych; pas 135 px (1440)
  i 298 px (390), ten sam w TODAY, w archiwum i przy ograniczonym ruchu; kolejność fokusu = kolejność wzrokowa; na 1440 dolna krawędź podpisu luk = dolna krawędź baneru (264 px),
  lewa kolumna pasa = szerokość panelu warstw, histogram zaczyna się nad mapą. Strzałki, Home, End, odtwarzanie (2 klatki w 5 s)
  i brak przycisku przy ograniczonym ruchu sprawdzone w przeglądarce.

## Panel designu (20.11.2026, jeden recenzent z trzema perspektywami: UX, laik, dostępność)

Wprowadzone: wczytywanie i błąd osi nie wyglądają jak zera; krótkie, policzalne luki w banerze i przycisk „Szczegóły”
zamiast tekstu tylko w `title`; słupki bez przezroczystości (kontrast 1.4.11); widoczna etykieta „Tempo 1×”;
kolejność DOM = kolejność wzrokowa; przygaszone kreskowanie (luka to tło, nie „najwięcej”); uchwyt na środku słupka
i suwak zwężony o pół słupka (klik trafia w widoczny słupek); bez `aria-pressed` przy zmiennej nazwie przycisku;
obrys fokusu tylko z klawiatury. Nie wprowadzone: odtwarzanie przy ograniczonym ruchu (zlecenie każe je wyłączyć).
Kontrast w jasnym motywie nie był mierzony (zrzuty tylko w ciemnym).

## Niesprawdzone i zaplanowane

- Niesprawdzone na prawdziwym backendzie (tylko dane próbne): kształt odpowiedzi `os/` i `wpisy/?na=` wzięty z serializerów W1.
- Skrypt `gust/odstepy.js` właściciela (ścieżka Windows) niedostępny na serwerze roboczym: zasadę 10 sprawdzono pomiarem położeń.
- Do decyzji: link „Kopiuj” w karcie wpisu (`adresWpisu`, obszar W2) nie przenosi `tryb` i `na`, więc udostępniony wpis otworzy się
  w TODAY; karta nie pokazuje jeszcze pola `stan` (wersja poprzednia, `obowiazywala_do`). Widok „Mój powiat” zostaje na żywo
  (oś jest tylko przy mapie, liście i tabeli).
- Telefon: pas zajmuje 298 px z 844 (po panelu designu: osobny wiersz podpisu luk i widoczne „Tempo”); jeśli panel designu uzna to za za dużo, kandydat: zwijanie histogramu w TODAY (kosztem zasady 5).
