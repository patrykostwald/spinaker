// „Teraz” (Z6b): tabela (sortowanie, filtr, eksport CSV), godziny, linia stanu zwinięta do jednej linii oraz kontrola
// dostępności na poziomie kodu (ARIA, fokus, ruch ograniczony). Wyniki axe w przeglądarce są w raporcie Z6b.
// node --test, bez nowych pakietów.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const root = path.join(__dirname, '..');
const dir = 'app/przeszlosc/teraz';
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

const mocks = { '@tanstack/react-query': { useQuery: () => ({}), keepPreviousData: {} } };
const cache = new Map();
function load(file) {
  if (file.endsWith('.json')) return JSON.parse(read(file));
  const bez = file.replace(/\.tsx?$/, '');
  const wzgledna = [`${bez}.ts`, `${bez}.tsx`, `${bez}/index.ts`].find(k => fs.existsSync(path.join(root, k)));
  if (!wzgledna) throw new Error(`brak modułu ${file}`);
  const abs = path.join(root, wzgledna);
  if (cache.has(abs)) return cache.get(abs).exports;
  const source = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} };
  cache.set(abs, module);
  const req = name => {
    if (name in mocks) return mocks[name];
    if (name.startsWith('.')) return load(path.relative(root, path.resolve(path.dirname(abs), name)).split(path.sep).join('/'));
    return require(name);
  };
  new Function('module', 'exports', 'require', 'process', 'fetch', source)(module, module.exports, req, { env: {} }, () => { throw new Error('fetch'); });
  return module.exports;
}

const dane = () => {
  const d = load(`${dir}/dane-probne/index`);
  const m = load(`${dir}/model`);
  const teraz = Date.now();
  const wpisy = d.probneWpisy(teraz);
  return { d, m, teraz, wpisy, widoki: m.zbudujWidoki(wpisy, d.probneZdarzenia(teraz)), warstwy: d.probneWarstwy(teraz) };
};
const tekstZHtml = html => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ');

test('CSV: średnik, cudzysłowy, końce wierszy CRLF, ochrona przed formułami, nazwa pliku', () => {
  const c = load(`${dir}/csv`);
  assert.equal(c.komorkaCsv('zwykły tekst'), 'zwykły tekst');
  assert.equal(c.komorkaCsv('a;b'), '"a;b"');
  assert.equal(c.komorkaCsv('on powiedział "tak"'), '"on powiedział ""tak"""');
  assert.equal(c.komorkaCsv('dwie\nlinie'), '"dwie\nlinie"');
  assert.equal(c.komorkaCsv('a,b'), 'a,b', 'przecinek nie jest separatorem');
  for (const zly of ['=SUM(A1:A9)', '+48 600 000 000', '-1+2', '@polecenie', '\tTab']) assert.ok(c.komorkaCsv(zly).startsWith("'") || c.komorkaCsv(zly).startsWith('"\''), `formuła zneutralizowana: ${zly}`);
  assert.equal(c.komorkaCsv('2026-11-18 14:32'), '2026-11-18 14:32', 'data zaczyna się od cyfry: bez apostrofu');
  const csv = c.budujCsv(['A', 'B'], [['1', 'x;y'], ['=2', 'z']]);
  assert.equal(csv, "A;B\r\n1;\"x;y\"\r\n'=2;z\r\n");
  assert.equal(c.nazwaPlikuCsv(new Date(2026, 10, 18, 14, 32)), 'teraz-komunikaty-2026-11-18-1432.csv');
  assert.equal(c.nazwaPlikuCsv(new Date(2026, 0, 5, 9, 7)), 'teraz-komunikaty-2026-01-05-0907.csv');
});

test('czas: początek okresu w zdaniu i czas lokalny do tabeli', () => {
  const c = load(`${dir}/czas`);
  const teraz = Date.parse('2026-11-18T12:00:00Z');
  assert.equal(c.odGodziny('2026-11-18T09:40:00Z', teraz), 'od godz. 10:40');
  assert.equal(c.odGodziny('2026-11-17T20:10:00Z', teraz), 'od wczoraj, godz. 21:10');
  assert.equal(c.odGodziny('2026-11-11T12:00:00Z', teraz), 'od 11 listopada, godz. 13:00');
  assert.equal(c.odGodziny(null, teraz), ''); assert.equal(c.odGodziny('zła data', teraz), '');
  assert.equal(c.czasLokalny('2026-11-17T13:32:00Z'), '2026-11-17 14:32');
  assert.equal(c.czasLokalny('2026-07-17T12:32:00Z'), '2026-07-17 14:32', 'lato: UTC+2');
  assert.equal(c.czasLokalny('2026-11-16T23:30:00Z'), '2026-11-17 00:30', 'doba liczona w Warszawie');
  assert.equal(c.czasLokalny(undefined), '');
});

test('tabela: wiersze z wszystkimi kolumnami, filtr tekstowy bez polskich znaków, sortowanie stabilne', () => {
  const t = load(`${dir}/tabela`);
  const { widoki, warstwy, teraz } = dane();
  const wiersze = t.wierszeTabeli(widoki, warstwy, teraz);
  assert.equal(wiersze.length, widoki.length, 'tabela ma tyle wierszy, ile komunikatów (pełny odpowiednik mapy, także bez położenia)');
  assert.deepEqual(t.KOLUMNY.map(k => k.id), ['warstwa', 'tytul', 'status', 'miejsce', 'opublikowano', 'pobrano', 'zrodlo']);
  const rcb = wiersze.find(w => w.id === 9001);
  assert.equal(rcb.warstwa, 'Alert RCB');
  assert.equal(rcb.status, 'Komunikat oficjalny');
  assert.equal(rcb.miejsce, 'powiat jarosławski (podkarpackie), powiat lubaczowski (podkarpackie), powiat przemyski (podkarpackie)');
  assert.match(rcb.opublikowano, /^dziś o godz\. \d{2}:\d{2}$/);
  assert.match(rcb.pobranoCzas, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  assert.equal(rcb.zrodlo, 'Alert RCB na gov.pl, Rządowe Centrum Bezpieczeństwa');
  assert.equal(rcb.link, 'https://www.gov.pl/web/rcb');
  assert.equal(wiersze.find(w => w.id === 9010).status, 'Zgłoszone');
  assert.equal(wiersze.find(w => w.id === 9003).status, 'Komunikat bez zdarzenia');
  // filtr
  assert.deepEqual(t.filtrujWiersze(wiersze, 'krakow').map(w => w.id), [9004], 'bez polskich znaków i wielkości liter');
  assert.deepEqual(t.filtrujWiersze(wiersze, 'ZGŁOSZONE').map(w => w.id).sort(), [9010, 9011, 9012, 9013, 9014, 9015]);
  assert.deepEqual(t.filtrujWiersze(wiersze, 'wstrząs lubin').map(w => w.id), [9020], 'każde słowo musi pasować, kolejność dowolna');
  assert.equal(t.filtrujWiersze(wiersze, '   ').length, wiersze.length, 'puste pole nie filtruje');
  assert.equal(t.filtrujWiersze(wiersze, 'xyzxyz').length, 0);
  // sortowanie
  const poCzasie = t.sortujWiersze(wiersze, 'opublikowano', 'malejaco');
  assert.equal(poCzasie[0].id, 9001, 'najnowszy pierwszy');
  assert.equal(poCzasie.at(-1).id, 9021, 'najstarszy ostatni (ponad 2 doby)');
  const rosnaco = t.sortujWiersze(wiersze, 'opublikowano', 'rosnaco');
  for (let i = 1; i < rosnaco.length; i++) assert.ok(rosnaco[i - 1].klucze.opublikowano <= rosnaco[i].klucze.opublikowano, 'czas rośnie');
  for (let i = 1; i < poCzasie.length; i++) assert.ok(poCzasie[i - 1].klucze.opublikowano >= poCzasie[i].klucze.opublikowano, 'czas maleje');
  assert.deepEqual(t.sortujWiersze(wiersze, 'opublikowano', 'malejaco').map(w => w.id), poCzasie.map(w => w.id), 'sortowanie jest deterministyczne (remis: najnowszy, potem numer)');
  assert.equal(t.sortujWiersze(wiersze, 'warstwa', 'rosnaco')[0].warstwa, 'Alert RCB', 'warstwy w kolejności produktu, RCB pierwsze');
  const poStatusie = t.sortujWiersze(wiersze, 'status', 'rosnaco');
  assert.equal(poStatusie[0].status, 'Komunikat oficjalny');
  assert.equal(poStatusie.at(-1).status, 'Komunikat bez zdarzenia');
  const normalizuj = load(`${dir}/powiaty`).normalizuj;
  const kolator = new Intl.Collator('pl');
  const poTytule = t.sortujWiersze(wiersze, 'tytul', 'rosnaco');
  for (let i = 1; i < poTytule.length; i++) assert.ok(kolator.compare(normalizuj(poTytule[i - 1].tytul), normalizuj(poTytule[i].tytul)) <= 0, 'tytuły rosnąco');
  assert.equal(poTytule.length, wiersze.length, 'sortowanie nie gubi wierszy');
  assert.equal(new Set(t.sortujWiersze(wiersze, 'miejsce', 'malejaco').map(w => w.id)).size, wiersze.length);
  assert.equal(t.kierunekPoczatkowy('opublikowano'), 'malejaco');
  assert.equal(t.kierunekPoczatkowy('tytul'), 'rosnaco');
  // eksport: te same kolumny co tabela (+ odnośnik), tylko to, co widoczne po filtrze
  assert.deepEqual(t.NAGLOWKI_CSV, ['Warstwa', 'Tytuł', 'Status', 'Miejsce', 'Opublikowano u źródła', 'Pobrano przez nas', 'Źródło', 'Odnośnik do oryginału']);
  const eksport = t.wierszeCsv(t.filtrujWiersze(wiersze, 'krakow'));
  assert.equal(eksport.length, 1);
  assert.equal(eksport[0].length, 8);
  assert.equal(eksport[0][0], 'Ostrzeżenia meteorologiczne');
  assert.match(eksport[0][4], /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/, 'czas lokalny sortowalny, nie „dziś o godz.”');
  assert.match(eksport[0][7], /^https:\/\//);
});

test('tabela (render): nagłówki z aria-sort, nagłówek wiersza, caption, przycisk CSV, pusty stan bez „spokojnie”', () => {
  const { TabelaWpisow } = load(`${dir}/TabelaWpisow`);
  const { widoki, warstwy } = dane();
  const html = renderToStaticMarkup(React.createElement(TabelaWpisow, { widoki, warstwy, wybrany: 9001, onWybierz() {}, opisFiltrow: '24 godz., cała Polska, włączone warstwy: 7' }));
  assert.match(html, /<table/);
  assert.match(html, /<caption[^>]*>Komunikaty \(24 godz\., cała Polska, włączone warstwy: 7\), 14 komunikatów\./);
  assert.equal((html.match(/<th scope="col"/g) ?? []).length, 7, 'siedem kolumn');
  assert.equal((html.match(/<th scope="row"/g) ?? []).length, widoki.length, 'tytuł jest nagłówkiem wiersza');
  assert.match(html, /<th scope="col" aria-sort="descending"><button[^>]*>Opublikowano u źródła/, 'domyślnie od najnowszych');
  assert.equal((html.match(/aria-sort="none"/g) ?? []).length, 6);
  assert.match(html, /Pobierz widok jako CSV \(14\)/);
  assert.match(html, /<label for="tz-tabela-filtr">Filtruj tabelę<\/label>/);
  assert.match(html, /role="region" aria-label="Tabela komunikatów \(przewijana strzałkami\)"/);
  assert.match(html, /tabindex="0"/, 'przewijana ramka tabeli dostępna z klawiatury');
  assert.match(html, /aria-pressed="true">Przykład: zagrożenie z powietrza/, 'wybrany wiersz oznaczony');
  assert.match(html, /rel="noopener noreferrer"/);
  assert.match(html, /Wiersze: 14\./);
  const pusty = renderToStaticMarkup(React.createElement(TabelaWpisow, { widoki: [], warstwy, wybrany: null, onWybierz() {}, opisFiltrow: '1 godz., cała Polska, włączone warstwy: 0', pusta: 'Brak komunikatów w wybranym czasie i regionie. To nie znaczy, że nic się nie dzieje: nie mamy pewności, sprawdź Alert RCB i 112.' }));
  assert.match(tekstZHtml(pusty), /Brak komunikatów w wybranym czasie i regionie\. To nie znaczy, że nic się nie dzieje: nie mamy pewności, sprawdź Alert RCB i 112\./);
  const niedostepna = renderToStaticMarkup(React.createElement(TabelaWpisow, { widoki: [], warstwy, wybrany: null, onWybierz() {}, opisFiltrow: 'x', pusta: 'Dane niedostępne, nie pokazujemy listy: nie mamy pewności, sprawdź Alert RCB i 112.' }));
  assert.ok(!/Brak komunikatów/.test(tekstZHtml(niedostepna)), 'awaria nie udaje braku komunikatów');
  assert.match(pusty, /<button[^>]*disabled[^>]*>Pobierz widok jako CSV \(0\)/);
  assert.ok(!/<table/.test(pusty));
  assert.ok(!/spokojn|bezpieczn/i.test(tekstZHtml(html + pusty)));
});

test('linia stanu: stałe zdanie i ostrzeżenie widoczne bez dotykania, „Dane przykładowe” i stan w jednej zwiniętej linii', () => {
  const { LiniaStanu } = load(`${dir}/LiniaStanu`);
  const { m, d, teraz } = dane();
  const podsumowanie = m.podsumujStan(d.probneStan(teraz), d.probneWarstwy(teraz));
  const w = load(`${dir}/warstwy`);
  const render = props => renderToStaticMarkup(React.createElement(LiniaStanu, { probne: true, podsumowanie, online: true, blad: false, odswiezonoWpisy: teraz, odswiezonoStan: teraz, ladowanie: false, ...props }));
  const html = render({});
  const przelacznik = html.indexOf('tz-stan__przelacznik');
  const szczegoly = html.indexOf('id="tz-stan-szczegoly"');
  assert.ok(przelacznik > 0 && szczegoly > przelacznik);
  assert.match(html, /aria-expanded="false"[^>]*aria-controls="tz-stan-szczegoly"|aria-controls="tz-stan-szczegoly"[^>]*aria-expanded="false"/, 'zwinięte, przycisk wskazuje rozwijaną część');
  assert.match(html.slice(szczegoly, szczegoly + 120), /hidden=""/, 'szczegóły ukryte do rozwinięcia');
  const widoczna = html.slice(0, szczegoly);
  assert.ok(widoczna.includes(w.ZDANIE_STALE), 'zdanie o stronie nieurzędowej poza ukrytą częścią');
  assert.ok(widoczna.indexOf(w.ZDANIE_STALE) < przelacznik, 'zdanie jest przed linią zwijaną');
  const ostrzezenie = widoczna.indexOf('nie mamy pewności, sprawdź Alert RCB i 112');
  assert.ok(ostrzezenie > 0 && ostrzezenie < przelacznik, 'ostrzeżenie o luce widoczne bez dotykania, przed zwijaną linią');
  assert.match(widoczna, /Ostrzeżenia hydrologiczne:<\/strong> nie mamy pewności/);
  assert.match(widoczna.slice(przelacznik), /Dane przykładowe/, 'oznaczenie próbne w zwiniętej linii');
  assert.match(html.slice(szczegoly), /To nie są prawdziwe komunikaty/, 'pełne objaśnienie po rozwinięciu');
  assert.match(html.slice(szczegoly), /To nie jest strona urzędowa\./);
  assert.match(html, /role="alert"/); assert.match(html, /role="status"/);
  // bez trybu próbnego i bez luk: jedna linia ze stanem pierwszej warstwy, bez ostrzeżenia
  const zdrowe = { ...podsumowanie, ostrzezenia: [] };
  const spokojna = render({ probne: false, podsumowanie: zdrowe });
  assert.ok(!/Dane przykładowe\./.test(spokojna.slice(0, spokojna.indexOf('id="tz-stan-szczegoly"'))));
  assert.match(tekstZHtml(spokojna), /Alert RCB: ostatnie pobranie: \d{2}:\d{2}, komunikatów z 24 h: 3/);
  assert.ok(!/tz-stan__ostrz/.test(spokojna), 'brak luk: brak ramki ostrzeżenia');
  // brak połączenia: ostrzeżenie w regionie alert, ostatnie dane z godziną
  const offline = render({ online: false });
  const alert = offline.slice(offline.indexOf('role="alert"'), offline.indexOf('role="status"'));
  assert.match(tekstZHtml(alert), /Brak połączenia z internetem: nie mamy pewności, sprawdź Alert RCB i 112\. Ostatnie komunikaty pobraliśmy o godz\. \d{2}:\d{2}\./);
  const blad = render({ blad: true });
  assert.match(tekstZHtml(blad.slice(blad.indexOf('role="alert"'), blad.indexOf('role="status"'))), /Brak połączenia z serwerem/);
  assert.ok(!/spokojn|bezpieczn/i.test(tekstZHtml(html + offline + blad + spokojna)));
});

test('dostępność w kodzie: fokus, nazwy, ruch ograniczony, kontrast wysoki, brak martwych wzorców ARIA', () => {
  const css = read(`${dir}/teraz.css`);
  const strona = read(`${dir}/TerazPage.tsx`);
  const panel = read(`${dir}/PanelWarstw.tsx`);
  const mapa = read(`${dir}/Mapa.tsx`);
  const stan = read(`${dir}/LiniaStanu.tsx`);
  const powiatKod = read(`${dir}/MojPowiat.tsx`);
  // ruch ograniczony: przejścia i animacje wyłączone, mapa bez animacji
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*transition-duration: \.01ms !important[^}]*animation-duration: \.01ms !important/);
  assert.match(mapa, /fadeDuration: reduced\(\) \? 0 : 200/);
  assert.ok((mapa.match(/reduced\(\) \? 0/g) ?? []).length >= 4, 'przeloty mapy bez ruchu przy prefers-reduced-motion');
  assert.match(css, /@media \(prefers-contrast: more\)/);
  assert.match(css, /@media \(forced-colors: active\)/);
  // widoczny fokus dla wszystkich kontrolek i brak „outline: none” poza nagłówkami z tabindex=-1
  assert.match(css, /\.tz :is\(a, button, input, select, summary\):focus-visible \{ outline: 2px solid/);
  for (const linia of css.split('\n').filter(l => /outline:\s*none/.test(l))) assert.match(linia, /tz-karta__tytul|tz-panel__tytul|tz-tabela__tytul|tz-mp-tytul/, `outline none tylko dla nagłówków fokusowanych programowo: ${linia.trim()}`);
  assert.match(css, /\.tz-stan__szczegoly\[hidden\] \{ display: none; \}/, 'atrybut hidden nie jest nadpisany przez display: grid');
  assert.match(css, /\.tz-mp-podpowiedzi\[hidden\] \{ display: none; \}/);
  // przyciski widoków: stan w aria-pressed, cztery widoki, pełna nazwa „Mój powiat” w nazwie dostępnej
  assert.equal((strona.match(/aria-pressed=\{widok === '/g) ?? []).length, 4);
  assert.match(strona, /aria-label="Mój powiat"/, 'przycisk ma pełną nazwę dostępną niezależnie od skrótu na telefonie');
  assert.match(strona, /tz-widok__skrot" aria-hidden="true">Powiat<\/span><span className="tz-widok__pelna" aria-hidden="true">Mój powiat/);
  assert.match(strona, /className="tz-marka__tekst">przeszłość\.today/);
  const okres = read(`${dir}/WyborOkresu.tsx`);
  assert.ok(!/role="radio"/.test(okres + panel), 'okres to natywne pola radiowe, bez udawanego wzorca ARIA');
  assert.match(okres, /role="radiogroup" aria-labelledby=\{opisanePrzez\}/);
  assert.match(okres, /<input type="radio" name=\{nazwa\}/, 'natywne radia: strzałki zmieniają opcję');
  assert.match(panel, /WyborOkresu/); assert.match(powiatKod, /WyborOkresu/);
  // skok do tabeli z mapy i przeniesienie fokusu na panel po otwarciu
  assert.match(strona, /Przejdź do tabeli komunikatów \(pełny odpowiednik mapy\)/);
  assert.match(strona, /getElementById\('tz-panel-tytul'\)\?\.focus\(\)/);
  assert.match(strona, /getElementById\('tz-tabela-tytul'\)\?\.focus\(\)/);
  assert.match(css, /\.tz-pomin:focus \{ transform: none; \}/);
  // linia stanu: Esc zamyka rozwinięcie, uprzejme i natychmiastowe regiony
  assert.match(stan, /e\.key !== 'Escape'/); assert.match(stan, /role="alert"/); assert.match(stan, /role="status"/);
  // mapa: opis klawiszy i wskazanie tabeli jako odpowiednika
  assert.match(mapa, /Strzałki przesuwają mapę, plus i minus zmieniają przybliżenie/);
  assert.match(mapa, /Pełny odpowiednik mapy to widok Tabela/);
  // etykiety pól
  const tabela = read(`${dir}/TabelaWpisow.tsx`);
  const powiat = read(`${dir}/MojPowiat.tsx`);
  // axe landmark-unique: widok jest jednym regionem (section.tz-scena), w środku nie powtarzamy tej samej nazwy
  assert.ok(!/<section className="tz-tabela"/.test(tabela) && !/<section className="tz-mp"/.test(powiat), 'bez zdublowanych landmarków');
  // płótno mapy dopasowuje się do kontenera po ustaleniu układu (MapLibre pomija pierwsze zdarzenie własnego obserwatora)
  assert.match(mapa, /new ResizeObserver\(\(\) => \{ if \(mapa\.current\) mapa\.current\.resize\(\); \}\)/);
  assert.match(mapa, /obserwator\?\.disconnect\(\)/);
  // odnośniki w atrybucji mapy podkreślone (WCAG 1.4.1)
  assert.match(css, /\.maplibregl-ctrl-attrib a \{ text-decoration: underline/);
  assert.match(tabela, /<label htmlFor="tz-tabela-filtr">/);
  assert.match(tabela, /aria-sort=\{ariaSort\(k\.id\)\}/);
  assert.match(powiat, /role="combobox"/); assert.match(powiat, /aria-activedescendant/); assert.match(powiat, /aria-controls=\{idListy\}/);
  assert.match(powiat, /e\.key === 'ArrowDown'/); assert.match(powiat, /e\.key === 'Escape'/); assert.match(powiat, /e\.key === 'Enter'/);
  // zapis wyboru powiatów w przeglądarce w try/catch, bez nadpisywania pamięci zestawem z cudzego linku
  assert.match(read(`${dir}/pamiec.ts`), /try \{ window\.localStorage\.setItem/);
  assert.match(strona, /zmienPowiaty = useCallback/);
  assert.ok(!/zapiszPamiec\(\{[^}]*powiaty[^}]*\}\);\s*\}, \[pamiecGotowa/.test(strona), 'efekt automatyczny nie zapisuje powiatów');
});

test('telefon: nagłówek mieści cztery widoki w jednym wierszu, bez poziomego przewijania strony', () => {
  const css = read(`${dir}/teraz.css`);
  assert.match(css, /@media \(max-width: 559\.98px\)\s*\{[^}]*\.tz-marka__tekst/);
  assert.match(css, /\.tz-widok__pelna \{ display: none; \}\s*@media \(min-width: 560px\) \{ \.tz-widok__skrot \{ display: none; \} \.tz-widok__pelna \{ display: inline; \} \}/, 'telefon: skrót „Powiat”, od 560 px pełne „Mój powiat”');
  assert.match(css, /@media \(max-width: 380px\)\s*\{[\s\S]*?\.tz-widok button \{ min-width: 46px/);
  assert.match(css, /\.tz-tabela__przewijanie \{ overflow: auto; max-width: 100%/, 'szeroka tabela przewija się w ramce, nie strona');
  assert.match(css, /\.tz-stan__jedna \{[^}]*text-overflow: ellipsis; white-space: nowrap/, 'zwinięta linia stanu to jedna linia');
  assert.match(css, /\.tz-stan__szczegoly \{ position: absolute;/, 'rozwinięcie jako nakładka: mapa się nie przesuwa');
});
