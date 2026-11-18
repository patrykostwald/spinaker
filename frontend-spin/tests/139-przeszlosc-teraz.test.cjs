// „Teraz” (Z6a): mapa komunikatów na przeszłość.today. Sprawdza czystą logikę (model, parametry URL, dane próbne, czas,
// TERYT), zgodność typów i danych próbnych z kontraktem API oraz zasady produktu (flaga, bez ciężkich bibliotek poza trasą,
// bez zakazanych słów i długich myślników). node --test, bez nowych pakietów (TS przez typescript.transpileModule).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const dir = 'app/przeszlosc/teraz';
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

const mocks = {
  react: { useState: () => [true, () => {}], useEffect: () => {} },
  '@tanstack/react-query': { useQuery: () => ({}), keepPreviousData: {} },
};
const cache = new Map();
const stub = { fetch: () => { throw new Error("fetch nie jest podstawiony"); } };
/** Wczytuje moduł TS z katalogu teraz razem z jego względnymi importami (bez Reacta i mapy). */
function load(file) {
  const bez = file.endsWith('.ts') ? file.slice(0, -3) : file;
  const abs = path.join(root, fs.existsSync(path.join(root, `${bez}.ts`)) ? `${bez}.ts` : `${bez}/index.ts`);
  if (cache.has(abs)) return cache.get(abs).exports;
  const source = ts.transpileModule(fs.readFileSync(abs, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  cache.set(abs, module);
  const req = name => {
    if (name in mocks) return mocks[name];
    if (name.startsWith('.')) return load(path.relative(root, path.resolve(path.dirname(abs), name)));
    throw new Error(`nieoczekiwany import ${name} w ${file}`);
  };
  // w tym samym obszarze (realm) co test, żeby deepEqual nie widział różnych prototypów tablic
  new Function('module', 'exports', 'require', 'process', 'fetch', source)(module, module.exports, req, { env: {} }, (...args) => stub.fetch(...args));
  return module.exports;
}

const pliki = () => fs.readdirSync(path.join(root, dir), { recursive: true, withFileTypes: true })
  .filter(e => e.isFile()).map(e => path.join(e.parentPath ?? e.path, e.name));

test('teksty trasy: bez długich myślników i bez słów „spokojnie” i „bezpiecznie”', () => {
  const tekstowe = pliki().filter(f => /\.(ts|tsx|css)$/.test(f));
  assert.ok(tekstowe.length >= 15, 'trasa ma komplet plików');
  for (const f of tekstowe) {
    const tresc = fs.readFileSync(f, 'utf8');
    assert.ok(!/[–—]/.test(tresc), `długi myślnik w ${path.relative(root, f)}`);
    // słowa zakazane: pomijamy komentarze, które je cytują jako zasadę
    const bezKomentarzy = tresc.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '').replace(/\/\/ .*$/gm, '');
    assert.ok(!/spokojn|bezpieczn/i.test(bezKomentarzy), `zakazane słowo w ${path.relative(root, f)}`);
  }
});

test('flaga TERAZ_ENABLED: bez niej przekierowanie na /przeszlosc; middleware zna /teraz', () => {
  const page = read(`${dir}/page.tsx`);
  assert.match(page, /serverFeature\('TERAZ_ENABLED'\)/);
  assert.match(page, /redirect\('\/przeszlosc'\)/);
  assert.match(page, /robots: \{ index: false/);
  assert.match(read('lib/features.ts'), /TERAZ_ENABLED: process\.env\.NEXT_PUBLIC_TERAZ_ENABLED/);
  assert.match(read('middleware.ts'), /short === '\/teraz'/);
});

test('ciężkie biblioteki tylko w trasie: maplibre-gl i pmtiles ładowane dynamicznie w Mapa.tsx, bez SSR', () => {
  for (const f of pliki().filter(p => /\.(ts|tsx)$/.test(p))) {
    const tresc = fs.readFileSync(f, 'utf8');
    const nazwa = path.basename(f);
    const statycznie = /^import\s(?!type\b)[^;]*from\s+'(maplibre-gl|pmtiles)'/m.test(tresc);
    assert.ok(!statycznie, `statyczny import ciężkiej biblioteki w ${nazwa}`);
    if (nazwa !== 'Mapa.tsx' && nazwa !== 'styl.ts') assert.ok(!/from 'maplibre-gl'|from 'pmtiles'/.test(tresc.replace(/import type[^\n]*\n/g, '')), nazwa);
  }
  const mapa = read(`${dir}/Mapa.tsx`);
  assert.match(mapa, /await import\('maplibre-gl'\)/);
  assert.match(mapa, /await import\('pmtiles'\)/);
  assert.match(read(`${dir}/TerazPage.tsx`), /dynamic\(\(\) => import\('\.\/Mapa'\), \{\s*ssr: false/);
  for (const f of ['Mapa.tsx', 'styl.ts', 'TerazPage.tsx', 'page.tsx', 'api.ts']) assert.ok(!/tile\.openstreetmap\.org|mapbox\.com|maptiler|googleapis\.com\/maps/i.test(read(`${dir}/${f}`)), `zakazany dostawca kafelków w ${f}`);
  const pkg = JSON.parse(read('package.json'));
  assert.ok(pkg.dependencies['maplibre-gl'] && pkg.dependencies.pmtiles);
});

test('granica Polski: lekki GeoJSON z domeny publicznej, poprawna geometria', () => {
  const geo = JSON.parse(read('public/teraz/polska.geojson'));
  assert.equal(geo.type, 'FeatureCollection');
  assert.ok(fs.statSync(path.join(root, 'public/teraz/polska.geojson')).size < 60_000, 'plik lekki');
  const punkty = geo.features[0].geometry.coordinates.flat(2);
  const lon = punkty.map(p => p[0]), lat = punkty.map(p => p[1]);
  assert.ok(Math.min(...lon) > 13.9 && Math.max(...lon) < 24.3 && Math.min(...lat) > 48.9 && Math.max(...lat) < 55.0, 'zasięg Polski');
  for (const pierscien of geo.features[0].geometry.coordinates.flat(1)) assert.deepEqual(pierscien[0], pierscien[pierscien.length - 1], 'pierścień zamknięty');
});

test('warstwy: każdy kod z kontraktu ma wygląd; stałe zdania zgodne z zasadami i z API', () => {
  const w = load(`${dir}/warstwy`);
  const kody = ['rcb', 'imgw_meteo', 'imgw_hydro', 'powietrze', 'pozary', 'wstrzasy', 'katastrofy', 'policja', 'psp', 'sg', 'wojsko', 'drogi', 'kolej', 'przestrzen', 'energetyka', 'cyber', 'media', 'urzedy'];
  assert.deepEqual(Object.keys(w.WARSTWY_META).sort(), [...kody].sort());
  assert.deepEqual([...w.KOLEJNOSC_WARSTW].sort(), [...kody].sort());
  for (const k of kody) { assert.match(w.WARSTWY_META[k].kolor, /^#[0-9a-f]{6}$/); assert.ok(w.IKONY[w.WARSTWY_META[k].ikona], `ikona ${k}`); }
  assert.equal(new Set(Object.values(w.WARSTWY_META).map(m => m.kolor)).size, kody.length, 'kolory warstw różne');
  assert.equal(w.ZDANIE_STALE, 'To nie jest strona urzędowa. W sytuacji zagrożenia słuchaj komunikatów RCB i dzwoń pod 112.');
  assert.equal(w.NIEPEWNOSC, 'nie mamy pewności, sprawdź Alert RCB i 112');
  const statusy = ['komunikat_oficjalny', 'zgloszone', 'potwierdzone', 'ocena', 'odwolane', 'brak'];
  assert.deepEqual(Object.keys(w.STATUSY).sort(), [...statusy].sort());
  assert.equal(new Set(statusy.map(s => w.STATUSY[s].ksztalt)).size, statusy.length, 'każdy status ma własny kształt (nie tylko kolor)');
  assert.deepEqual(w.OKRESY.map(o => o.id), ['1h', '24h', '7d']);
});

test('dane próbne mają dokładnie pola kontraktu API i obejmują wymagane przypadki', () => {
  const d = load(`${dir}/dane-probne/index`);
  const teraz = Date.parse('2026-11-17T14:40:00+01:00');
  const polaWpisu = ['bbox', 'dlugosc', 'dokladnosc', 'id', 'klasa', 'link', 'opublikowano_at', 'pewnosc_lokalizacji', 'pobrano_at', 'szerokosc', 'teryt', 'tresc', 'tytul', 'warstwa', 'zrodlo'];
  const wpisy = d.probneWpisy(teraz);
  for (const x of wpisy) assert.deepEqual(Object.keys(x).sort(), polaWpisu, `pola wpisu ${x.id}`);
  const polaZdarzenia = ['id', 'ostatni_wpis_at', 'pierwszy_wpis_at', 'przygotowane_automatycznie', 'status', 'tytul_roboczy', 'wpisy', 'zweryfikowal', 'zweryfikowano_at'];
  for (const z of d.probneZdarzenia(teraz)) assert.deepEqual(Object.keys(z).sort(), polaZdarzenia);
  const polaSwiezosci = ['liczba_wpisow_24h', 'luka', 'blad', 'ostatni_sukces_at', 'ostatnie_pobranie_at'];
  const warstwy = d.probneWarstwy(teraz);
  assert.equal(warstwy.length, 18, 'API zwraca wszystkie 18 warstw');
  for (const w of warstwy) {
    assert.deepEqual(Object.keys(w).sort(), [...polaSwiezosci, 'nazwa', 'warstwa', 'zrodla'].sort());
    for (const z of w.zrodla) assert.deepEqual(Object.keys(z).sort(), [...polaSwiezosci, 'czestotliwosc_s', 'instytucja', 'nazwa', 'slug'].sort());
  }
  const stan = d.probneStan(teraz);
  assert.equal(stan.informacja, 'To nie jest strona urzędowa');
  for (const l of stan.warstwy) assert.deepEqual(Object.keys(l).sort(), ['komunikat', 'komunikaty', 'ostatnie_pobranie', 'warstwa']);
  // przypadki ze zlecenia
  const rcb = wpisy.filter(x => x.warstwa === 'rcb' && x.teryt.length >= 3);
  assert.ok(rcb.some(x => x.teryt.every(k => k.length === 4)), 'RCB dla kilku powiatów');
  assert.ok(wpisy.some(x => x.warstwa === 'imgw_meteo'), 'ostrzeżenie IMGW');
  assert.ok(wpisy.filter(x => x.warstwa === 'pozary').length >= 5, 'pożary FIRMS do grupowania');
  assert.ok(wpisy.some(x => x.warstwa === 'wstrzasy'), 'wstrząs EMSC');
  assert.ok(warstwy.some(w => w.luka), 'warstwa ze świeżą luką');
  assert.ok(d.probneZdarzenia(teraz).some(z => z.status === 'zgloszone' && z.wpisy.every(w => w.warstwa === 'pozary')), 'pożar FIRMS jako Zgłoszone');
  // zdania linii stanu jak w StanView
  assert.equal(stan.warstwy.find(l => l.warstwa === 'rcb').ostatnie_pobranie, 'ostatnie pobranie: 14:39');
  assert.equal(stan.warstwy.find(l => l.warstwa === 'rcb').komunikat, '');
  assert.equal(stan.warstwy.find(l => l.warstwa === 'imgw_hydro').komunikat, 'nie mamy pewności, sprawdź Alert RCB i 112');
  assert.equal(stan.warstwy.find(l => l.warstwa === 'policja').komunikat, 'nie mamy pewności, sprawdź Alert RCB i 112', 'brak źródeł też daje niepewność jak w API');
  // wszystkie wpisy mają link http(s) i poprawne czasy
  for (const x of wpisy) { assert.match(x.link, /^https?:\/\//); assert.ok(Date.parse(x.opublikowano_at) <= Date.parse(x.pobrano_at), 'pobranie nie wcześniej niż publikacja'); assert.ok(Number.isFinite(Date.parse(x.pobrano_at))); }
});

test('filtry próbne odtwarzają filtry API: od, teryt (prefiks), bbox', () => {
  const d = load(`${dir}/dane-probne/index`);
  const teraz = Date.now();
  const wpisy = d.probneWpisy(teraz);
  const godzina = d.filtrujProbneWpisy(wpisy, { od: new Date(teraz - 3_600_000).toISOString() });
  assert.ok(godzina.length > 0 && godzina.length < wpisy.length);
  assert.ok(godzina.every(x => Date.parse(x.opublikowano_at) >= teraz - 3_600_000));
  const lubelskie = d.filtrujProbneWpisy(wpisy, { teryt: '06' });
  assert.ok(lubelskie.every(x => x.teryt.some(k => k.startsWith('06'))) && lubelskie.length >= 2);
  const malopolska = d.filtrujProbneWpisy(wpisy, { bbox: [19.0, 49.0, 21.5, 50.6] });
  assert.ok(malopolska.some(x => x.bbox) && malopolska.every(x => !(x.szerokosc !== null && (x.szerokosc < 49 || x.szerokosc > 50.6))));
});

test('model: status tylko ze zdarzenia, GeoJSON z kształtem statusu, region, wpisy bez położenia', () => {
  const d = load(`${dir}/dane-probne/index`);
  const m = load(`${dir}/model`);
  const teraz = Date.now();
  const wpisy = d.probneWpisy(teraz);
  const widoki = m.zbudujWidoki(wpisy, d.probneZdarzenia(teraz));
  assert.equal(widoki.length, wpisy.length);
  const status = id => widoki.find(v => v.wpis.id === id).status;
  assert.equal(status(9001), 'komunikat_oficjalny');
  assert.equal(status(9010), 'zgloszone');
  assert.equal(status(9002), 'odwolane');
  assert.equal(status(9003), 'brak', 'wpis bez zdarzenia nie dostaje wyprowadzonego statusu');
  const geo = m.naGeoJson(widoki);
  assert.equal(geo.punkty.features.length, 8, '6 pożarów i 2 wstrząsy');
  assert.equal(geo.obszary.features.length, 1, 'jeden prostokąt IMGW');
  const pozar = geo.punkty.features.find(f => f.properties.id === 9010);
  assert.deepEqual(pozar.geometry.coordinates, [22.88, 50.93], 'kolejność [długość, szerokość]');
  assert.equal(pozar.properties.ikona, 'ik-romb-ff8a2a', 'Zgłoszone = romb w kolorze warstwy pożarów');
  assert.equal(geo.punkty.features.find(f => f.properties.id === 9020).properties.ikona, 'ik-pierscien-b36bff', 'bez zdarzenia = pierścień');
  const obszar = geo.obszary.features[0];
  assert.equal(obszar.properties.styl, 'ciagla');
  assert.deepEqual(obszar.geometry.coordinates[0][0], obszar.geometry.coordinates[0][4], 'pierścień zamknięty');
  const bez = widoki.filter(v => m.bezPolozenia(v.wpis)).map(v => v.wpis.id).sort();
  assert.deepEqual(bez, [9001, 9002, 9003, 9004, 9030], 'wpisy tylko z TERYT albo bez miejsca idą na listę');
  const wRegionie = woj => widoki.filter(v => m.zgodnyZRegionem(v.wpis, woj)).map(v => v.wpis.id).sort();
  assert.deepEqual(wRegionie('18'), [9001], 'podkarpackie: RCB dla powiatów 18xx');
  assert.ok(wRegionie('02').includes(9020), 'punkt bez TERYT w prostokącie dolnośląskiego (wstrząs koło Lubina)');
  assert.ok(wRegionie('12').includes(9005) && wRegionie('12').includes(9004), 'Małopolska: prostokąt i kody 12xx');
  assert.equal(wRegionie(null).length, widoki.length);
});

test('model: podsumowanie stanu ostrzega tylko dla warstw ze źródłami; luka jest widoczna', () => {
  const d = load(`${dir}/dane-probne/index`);
  const m = load(`${dir}/model`);
  const teraz = Date.now();
  const p = m.podsumujStan(d.probneStan(teraz), d.probneWarstwy(teraz));
  assert.equal(p.wiersze.length, 18);
  assert.deepEqual(p.ostrzezenia.map(o => o.warstwa), ['imgw_hydro'], 'warstwy bez źródeł nie krzyczą w głównej linii, ale są oznaczone w szczegółach');
  assert.ok(p.wiersze.filter(w => !w.aktywna).every(w => w.komunikat === 'nie mamy pewności, sprawdź Alert RCB i 112'));
  assert.equal(m.podsumujStan(undefined, []), null);
  const bezNazw = m.podsumujStan(d.probneStan(teraz), undefined);
  assert.equal(bezNazw.wiersze.length, 18, 'działa też bez listy warstw');
});

test('model: warstwy włączone, sortowanie, nazwa źródła, adres wpisu', () => {
  const d = load(`${dir}/dane-probne/index`);
  const m = load(`${dir}/model`);
  const warstwy = d.probneWarstwy(Date.now());
  assert.deepEqual([...m.wlaczoneWarstwy(null, warstwy)].sort(), ['cyber', 'imgw_hydro', 'imgw_meteo', 'powietrze', 'pozary', 'rcb', 'wstrzasy']);
  assert.deepEqual([...m.wlaczoneWarstwy(['rcb'], warstwy)], ['rcb']);
  assert.deepEqual([...m.wlaczoneWarstwy([], warstwy)], []);
  assert.equal(m.posortujWarstwy(warstwy)[0].warstwa, 'rcb');
  assert.deepEqual({ ...m.nazwaZrodla(warstwy, 'nasa-firms') }, { nazwa: 'Źródła ciepła NASA FIRMS (VIIRS)', instytucja: 'NASA' });
  assert.deepEqual({ ...m.nazwaZrodla(warstwy, 'nieznane') }, { nazwa: 'nieznane', instytucja: '' });
  assert.equal(m.adresWpisu('https://przeszlosc.today', '/teraz', '?okres=7d&warstwy=rcb', 9001), 'https://przeszlosc.today/teraz?okres=7d&warstwy=rcb&wpis=9001');
});

test('parametry URL: parsowanie z walidacją i zapis bez wartości domyślnych', () => {
  const p = load(`${dir}/parametry`);
  assert.deepEqual({ ...p.parsuj({}) }, { warstwy: null, okres: '24h', woj: null, wpis: null, widok: 'mapa', probne: false });
  const x = p.parsuj({ warstwy: 'rcb,pozary,<script>,rcb', okres: '7d', woj: '14', wpis: '9001', widok: 'lista', probne: '1' });
  assert.deepEqual([...x.warstwy], ['rcb', 'pozary']);
  assert.equal(x.okres, '7d'); assert.equal(x.woj, '14'); assert.equal(x.wpis, 9001); assert.equal(x.widok, 'lista'); assert.equal(x.probne, true);
  const zle = p.parsuj({ okres: '1000d', woj: '99', wpis: 'abc', widok: 'x', probne: '0' });
  assert.equal(zle.okres, '24h'); assert.equal(zle.woj, null); assert.equal(zle.wpis, null); assert.equal(zle.widok, 'mapa'); assert.equal(zle.probne, false);
  assert.deepEqual([...p.parsuj({ warstwy: '' }).warstwy], [], 'puste warstwy = wszystkie wyłączone');
  assert.equal(p.parsuj(new URLSearchParams('okres=1h&woj=06')).woj, '06');
  assert.equal(p.zbudujZapytanie({ warstwy: null, okres: '24h', woj: null, wpis: null, widok: 'mapa', probne: false }, ''), '');
  const z = p.zbudujZapytanie({ warstwy: ['rcb', 'pozary'], okres: '7d', woj: '14', wpis: 9001, widok: 'lista', probne: true }, '?inny=1&okres=1h');
  assert.equal(z, '?inny=1&warstwy=rcb%2Cpozary&okres=7d&woj=14&wpis=9001&widok=lista&probne=1');
  assert.deepEqual({ ...p.parsuj(new URLSearchParams(z)) }, { ...p.parsuj(new URLSearchParams(z)) });
  assert.equal(p.parsuj(new URLSearchParams(z)).warstwy.join(','), 'rcb,pozary');
});

test('czas: godziny w strefie Warszawy, „dziś” i „wczoraj”', () => {
  const c = load(`${dir}/czas`);
  assert.equal(c.godzina('2026-11-17T13:32:00Z'), '14:32', 'zima: UTC+1');
  assert.equal(c.godzina('2026-07-17T12:32:00Z'), '14:32', 'lato: UTC+2');
  assert.equal(c.godzina(null), ''); assert.equal(c.godzina('nie data'), '');
  const teraz = Date.parse('2026-11-17T20:00:00Z');
  assert.equal(c.dataIGodzina('2026-11-17T13:32:00Z', teraz), 'dziś o godz. 14:32');
  assert.equal(c.dataIGodzina('2026-11-16T20:10:00Z', teraz), 'wczoraj o godz. 21:10');
  assert.match(c.dataIGodzina('2026-11-12T08:40:00Z', teraz), /^12 listopada o godz\. 09:40$/);
  assert.equal(c.dataIGodzina('2026-11-16T23:30:00Z', Date.parse('2026-11-17T10:00:00Z')), 'dziś o godz. 00:30', 'granica doby liczona w Warszawie, nie w UTC');
  assert.equal(c.ileTemu('2026-11-17T19:57:00Z', teraz), '3 min temu');
  assert.equal(c.host('https://www.gov.pl/web/rcb'), 'gov.pl');
  assert.equal(c.host('to nie adres'), '');
});

test('TERYT: nazwy województw i powiatów, nieznany powiat po kodzie, opis miejsca', () => {
  const t = load(`${dir}/teryt`);
  assert.equal(t.WOJEWODZTWA.length, 16);
  assert.equal(t.nazwaObszaru('06'), 'województwo lubelskie');
  assert.equal(t.nazwaObszaru('1814'), 'powiat przemyski (podkarpackie)');
  assert.equal(t.nazwaObszaru('1263'), 'powiat m. Tarnów (małopolskie)');
  assert.equal(t.nazwaObszaru('1899'), 'powiat o kodzie 1899 (podkarpackie)', 'nie zgadujemy nazwy');
  assert.equal(t.nazwaObszaru('1814011'), 'gmina o kodzie 1814011 (podkarpackie)');
  assert.equal(t.opisMiejsca({ teryt: ['1814', '1810'], dokladnosc: 'powiat', szerokosc: null, dlugosc: null, bbox: null }), 'dotyczy: powiat lubaczowski (podkarpackie), powiat przemyski (podkarpackie)');
  assert.equal(t.opisMiejsca({ teryt: [], dokladnosc: 'punkt', szerokosc: 51.5, dlugosc: 16.1, bbox: null }), 'dotyczy: punkt na mapie (położenie przybliżone)');
  assert.equal(t.opisMiejsca({ teryt: [], dokladnosc: 'kraj', szerokosc: null, dlugosc: null, bbox: null }), 'dotyczy: całego kraju');
  assert.equal(t.opisMiejsca({ teryt: [], dokladnosc: 'brak', szerokosc: null, dlugosc: null, bbox: null }), 'miejsce nieznane');
  for (const w of t.WOJEWODZTWA) assert.ok(w.bbox[0] < w.bbox[2] && w.bbox[1] < w.bbox[3] && /^[0-9]{2}$/.test(w.kod));
});

test('API: adresy pod /api/teraz/, odświeżanie co 30 s, paginacja DRF, błędy i brak sieci', async () => {
  const kod = read(`${dir}/api.ts`);
  assert.match(kod, /ODSWIEZANIE_MS = 30_000/);
  for (const s of ["'stan'", "'warstwy'", "'wpisy'", "'zdarzenia'"]) assert.ok(kod.includes(s), s);
  assert.match(kod, /\/api\/teraz\//);
  const a = load(`${dir}/api`);
  assert.equal(a.odKiedy('1h', 1_000_000_000), new Date(1_000_000_000 - 3_600_000).toISOString());
  assert.equal(a.odKiedy('7d', 1_000_000_000), new Date(1_000_000_000 - 604_800_000).toISOString());
  const e = new a.BladApi(503, 'x');
  assert.equal(e.status, 503); assert.equal(e.name, 'BladApi');

  const odpowiedz = (dane, ok = true, status = 200) => ({ ok, status, json: async () => dane });
  const adresy = [];
  // paginacja: dwie strony, druga bez next
  stub.fetch = async adres => {
    adresy.push(adres);
    return adres.includes('page=2') ? odpowiedz({ count: 3, next: null, previous: 'x', results: [{ id: 3 }] }) : odpowiedz({ count: 3, next: 'http://backend/api/teraz/wpisy/?page=2', previous: null, results: [{ id: 1 }, { id: 2 }] });
  };
  const dwie = await a.pobierzStrony('wpisy', { od: '2026-11-17T00:00:00.000Z', teryt: '06', pusty: '', brak: undefined }, 6);
  assert.deepEqual(dwie.wyniki.map(x => x.id), [1, 2, 3]);
  assert.equal(dwie.uciete, false);
  assert.deepEqual(adresy, ['/api/teraz/wpisy/?od=2026-11-17T00%3A00%3A00.000Z&teryt=06', '/api/teraz/wpisy/?od=2026-11-17T00%3A00%3A00.000Z&teryt=06&page=2'], 'puste i niezdefiniowane parametry pomijane, strona 1 bez ?page');
  // limit stron: zawsze jest następna strona
  stub.fetch = async () => odpowiedz({ count: 999, next: 'x', previous: null, results: [{ id: 1 }] });
  const ucieta = await a.pobierzStrony('wpisy', {}, 3);
  assert.equal(ucieta.wyniki.length, 3); assert.equal(ucieta.uciete, true);
  // błąd serwera i brak sieci
  stub.fetch = async () => odpowiedz({}, false, 503);
  await assert.rejects(a.pobierz('stan'), err => err.name === 'BladApi' && err.status === 503);
  stub.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(a.pobierz('stan'), err => err.name === 'BladApi' && err.status === 0 && /połączenia/.test(err.message));
  stub.fetch = async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('zły json'); } });
  await assert.rejects(a.pobierz('stan'), err => err.name === 'BladApi' && /formacie/.test(err.message));
  // województwo: wynik filtra TERYT i prostokąta bez duplikatów, od najnowszych
  const wpis = (id, minut) => ({ id, opublikowano_at: new Date(Date.now() - minut * 60_000).toISOString() });
  stub.fetch = async adres => odpowiedz({ count: 2, next: null, previous: null, results: adres.includes('teryt=14') ? [wpis(1, 30), wpis(2, 10)] : [wpis(2, 10), wpis(3, 5)] });
  const woj = await a.pobierzWpisy('24h', '14');
  assert.deepEqual(woj.wpisy.map(x => x.id), [3, 2, 1]);
  let zapytan = 0;
  stub.fetch = async () => { zapytan++; return odpowiedz({ count: 1, next: null, previous: null, results: [wpis(7, 1)] }); };
  assert.equal((await a.pobierzWpisy('24h', null)).wpisy.length, 1);
  assert.equal(zapytan, 1, 'bez regionu jedno zapytanie');
});
