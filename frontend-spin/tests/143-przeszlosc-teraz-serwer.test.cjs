// „Teraz” (Z6-poprawki): część serwerowa. (1) trasa /teraz używa zweryfikowanego podglądu (podpis z Django), nie samego ciasteczka
// sc_preview; (2) middleware przepuszcza dokładnie dwa pliki statyczne /teraz/* na przeszlosc.today i nie zmienia reguł innych tras.
// node --test, TS przez typescript.transpileModule, moduły Next.js podstawione.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const root = path.join(__dirname, '..');

/** Wczytuje plik TS z podstawionymi modułami, środowiskiem i fetch (każdy test ma własną kopię). */
function wczytaj(plik, { mocks = {}, env = {}, fetch = () => { throw new Error('fetch nie jest podstawiony'); } } = {}) {
  const zrodlo = ts.transpileModule(fs.readFileSync(path.join(root, plik), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const module = { exports: {} };
  const req = nazwa => { if (nazwa in mocks) return mocks[nazwa]; throw new Error(`nieoczekiwany import ${nazwa} w ${plik}`); };
  new Function('module', 'exports', 'require', 'process', 'fetch', zrodlo)(module, module.exports, req, { env }, (...a) => fetch(...a));
  return module.exports;
}

const ciasteczka = wartosci => ({ cookies: async () => ({ get: nazwa => (nazwa in wartosci ? { value: wartosci[nazwa] } : undefined) }) });
const features = (jar, opcje = {}) => wczytaj('lib/features.ts', { mocks: { 'server-only': {}, 'next/headers': ciasteczka(jar) }, ...opcje });
const odpowiedzDjango = aktywny => async () => ({ ok: true, json: async () => ({ active: aktywny }) });

test('podgląd: samo ciasteczko sc_preview nie otwiera /teraz (stary serverFeature je akceptuje, nowy sprawdza podpis w Django)', async () => {
  const jar = { sc_preview: '1' };
  const f = features(jar, { fetch: () => { throw new Error('bez podpisu nie wolno pytać Django'); } });
  assert.equal(await f.serverFeature('TERAZ_ENABLED'), true, 'dla kontrastu: serverFeature ufa niezweryfikowanemu ciasteczku');
  assert.equal(await f.serverFeatureVerified('TERAZ_ENABLED'), false, 'bez podpisu podgląd jest nieważny');
});

test('podgląd: poprawny podpis (Django: active true) otwiera trasę, nieważny albo błąd sieci nie', async () => {
  const adresy = [];
  const z = (aktywny, jar = { sc_preview: '1', sc_preview_sig: 'abc.DEF-123:xyz' }) => features(jar, {
    env: { API_INTERNAL_URL: 'http://backend.test' },
    fetch: async (adres, opcje) => { adresy.push([adres, opcje]); return odpowiedzDjango(aktywny)(); },
  });
  assert.equal(await z(true).serverFeatureVerified('TERAZ_ENABLED'), true, 'ważny podgląd');
  assert.equal(adresy[0][0], 'http://backend.test/api/preview/status/');
  assert.equal(adresy[0][1].headers.Cookie, 'sc_preview_sig=abc.DEF-123:xyz', 'do Django idzie tylko podpis');
  assert.equal(adresy[0][1].cache, 'no-store');
  assert.equal(await z(false).serverFeatureVerified('TERAZ_ENABLED'), false, 'nieważny (wygasły) podgląd');
  assert.equal(await z(true, { sc_preview: '1', sc_preview_sig: 'zły podpis ; drop' }).serverFeatureVerified('TERAZ_ENABLED'), false, 'podpis o złym kształcie nie jest wysyłany');
  assert.equal(await z(true, { sc_preview: '0', sc_preview_sig: 'abc' }).serverFeatureVerified('TERAZ_ENABLED'), false);
  assert.equal(await z(true, { sc_preview: '1' }).serverFeatureVerified('TERAZ_ENABLED'), false, 'brak podpisu');
  const awaria = features({ sc_preview: '1', sc_preview_sig: 'abc' }, { fetch: async () => { throw new TypeError('Failed to fetch'); } });
  assert.equal(await awaria.serverFeatureVerified('TERAZ_ENABLED'), false, 'błąd sieci: bez podglądu');
  const odrzucona = features({ sc_preview: '1', sc_preview_sig: 'abc' }, { fetch: async () => ({ ok: false, json: async () => ({ active: true }) }) });
  assert.equal(await odrzucona.serverFeatureVerified('TERAZ_ENABLED'), false, 'odpowiedź inna niż 2xx: bez podglądu');
});

test('flaga TERAZ_ENABLED=true otwiera trasę bez podglądu; inne flagi nie; serverFeature dla pozostałych tras bez zmian', async () => {
  const wlaczona = features({}, { env: { NEXT_PUBLIC_TERAZ_ENABLED: 'true' } });
  assert.equal(await wlaczona.serverFeatureVerified('TERAZ_ENABLED'), true);
  const inna = features({}, { env: { NEXT_PUBLIC_APP_ENABLED: 'true' } });
  assert.equal(await inna.serverFeatureVerified('TERAZ_ENABLED'), false);
  assert.equal(await inna.serverFeature('APP_ENABLED'), true);
  assert.equal(await features({}, { env: { NEXT_PUBLIC_TERAZ_ENABLED: 'false' } }).serverFeatureVerified('TERAZ_ENABLED'), false);
  // trasa /teraz korzysta z wariantu zweryfikowanego, pozostałe trasy nie zostały dotknięte
  const strona = fs.readFileSync(path.join(root, 'app/przeszlosc/teraz/page.tsx'), 'utf8');
  assert.match(strona, /import \{ serverFeatureVerified \} from '\.\.\/\.\.\/\.\.\/lib\/features'/);
  assert.match(strona, /if \(!\(await serverFeatureVerified\('TERAZ_ENABLED'\)\)\) redirect\('\/przeszlosc'\)/);
  const inneTrasy = fs.readdirSync(path.join(root, 'app'), { recursive: true }).filter(p => /page\.tsx$/.test(p) && !p.includes(`teraz${path.sep}page`));
  for (const p of inneTrasy) assert.ok(!/serverFeatureVerified/.test(fs.readFileSync(path.join(root, 'app', p), 'utf8')), `${p} nie używa nowego wariantu`);
});

// ---------- middleware ----------

function middleware() {
  const wynik = (rodzaj, adres) => ({ rodzaj, adres: adres === undefined ? undefined : String(adres) });
  const NextResponse = {
    next: () => wynik('next'),
    rewrite: adres => wynik('rewrite', adres instanceof URL ? adres.pathname + adres.search : adres),
    redirect: (adres, status) => ({ ...wynik('redirect', adres instanceof URL ? adres.href : adres), status }),
  };
  const { middleware: mw } = wczytaj('middleware.ts', { mocks: { 'next/server': { NextResponse } } });
  return (host, sciezka) => {
    const url = new URL(`https://${host}${sciezka}`);
    return mw({ headers: { get: nazwa => (nazwa === 'host' ? host : null) }, nextUrl: { pathname: url.pathname, search: url.search }, url: url.href });
  };
}

test('middleware: przeszlosc.today przepuszcza /teraz/polska.geojson i /teraz/teryt-powiaty.json bez przekierowania na spin.clinic', () => {
  const idz = middleware();
  for (const plik of ['/teraz/polska.geojson', '/teraz/teryt-powiaty.json']) {
    assert.equal(idz('przeszlosc.today', plik).rodzaj, 'next', plik);
    assert.equal(idz('www.przeszlosc.today', plik).rodzaj, 'next', `${plik} także z www`);
    assert.equal(idz('przeszlosc.today:443', plik).rodzaj, 'next');
    assert.equal(idz('spin.clinic', plik).rodzaj, 'next', 'na spin.clinic plik jest serwowany bez zmian');
  }
  // pliki istnieją pod tymi ścieżkami w public/
  assert.ok(fs.existsSync(path.join(root, 'public/teraz/polska.geojson')) && fs.existsSync(path.join(root, 'public/teraz/teryt-powiaty.json')));
});

test('middleware: reguły pozostałych tras bez zmian (tylko dokładne ścieżki plików są przepuszczone)', () => {
  const idz = middleware();
  // inne ścieżki pod /teraz/ na przeszlosc.today dalej idą na spin.clinic
  for (const sciezka of ['/teraz/inny.json', '/teraz/polska.geojson.bak', '/teraz/polska.geojson/x', '/teraz/', '/teraz/teryt-powiaty.json.map', '/teraz/..%2Fsekret']) {
    const w = idz('przeszlosc.today', sciezka);
    if (sciezka === '/teraz/') assert.equal(w.rodzaj, 'rewrite', 'ukośnik na końcu: strona /teraz (jak dotąd)');
    else { assert.equal(w.rodzaj, 'redirect', sciezka); assert.equal(w.status, 308); assert.match(w.adres, /^https:\/\/spin\.clinic\/teraz\//); }
  }
  // strona i pozostałe trasy
  assert.deepEqual(idz('przeszlosc.today', '/teraz'), { rodzaj: 'rewrite', adres: '/przeszlosc/teraz' });
  assert.deepEqual(idz('przeszlosc.today', '/teraz?woj=14'), { rodzaj: 'rewrite', adres: '/przeszlosc/teraz?woj=14' });
  assert.deepEqual(idz('przeszlosc.today', '/'), { rodzaj: 'rewrite', adres: '/przeszlosc' });
  assert.deepEqual(idz('przeszlosc.today', '/aplikacja'), { rodzaj: 'rewrite', adres: '/przeszlosc/aplikacja' });
  assert.deepEqual(idz('przeszlosc.today', '/manifest.webmanifest'), { rodzaj: 'rewrite', adres: '/przeszlosc/manifest.webmanifest' });
  assert.equal(idz('przeszlosc.today', '/przeszlosc/teraz').rodzaj, 'next');
  assert.equal(idz('przeszlosc.today', '/api/teraz/stan/').rodzaj, 'next');
  assert.equal(idz('przeszlosc.today', '/sw.js').rodzaj, 'next');
  assert.equal(idz('przeszlosc.today', '/raporty/pizza.html').rodzaj, 'next');
  const zrodla = idz('przeszlosc.today', '/zrodla');
  assert.equal(zrodla.rodzaj, 'redirect'); assert.equal(zrodla.status, 308); assert.match(zrodla.adres, /\/jak-to-dziala$/);
  const obca = idz('przeszlosc.today', '/cennik?x=1');
  assert.deepEqual(obca, { rodzaj: 'redirect', adres: 'https://spin.clinic/cennik?x=1', status: 308 });
  assert.deepEqual(idz('spin.clinic', '/manifest.webmanifest'), { rodzaj: 'rewrite', adres: '/spin-manifest.webmanifest' });
  assert.equal(idz('spin.clinic', '/cokolwiek').rodzaj, 'next');
});
