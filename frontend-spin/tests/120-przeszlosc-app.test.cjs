// Aplikacja przeszłość.today (PWA seria 2, 13.10.2026): manifest, ikony (w tym bezpieczna strefa maskable), zrzuty ekranu, skróty na istniejące trasy,
// middleware dla krótkich adresów, service worker (pamięć stron tylko publicznych i statycznych) oraz teksty instalacji.
// node --test, bez nowych pakietów (TS przez typescript.transpileModule, PNG dekodowany zlib-em).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const zlib = require('node:zlib');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const exists = file => fs.existsSync(path.join(root, file));
function load(file, mocks = {}) {
  const source = ts.transpileModule(read(file), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require: name => mocks[name], URL }, { filename: file });
  return exports;
}

/** Minimalny dekoder PNG (8 bit, bez przeplotu, typy 0/2/4/6): wymiary i piksele RGB do kontroli bezpiecznej strefy. */
function decodePng(buffer) {
  assert.equal(buffer.toString('latin1', 1, 4), 'PNG');
  let offset = 8, width = 0, height = 0, depth = 0, type = 0, interlace = 0;
  const idat = [];
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset), name = buffer.toString('latin1', offset + 4, offset + 8), data = buffer.subarray(offset + 8, offset + 8 + length);
    if (name === 'IHDR') { width = data.readUInt32BE(0); height = data.readUInt32BE(4); depth = data[8]; type = data[9]; interlace = data[12]; }
    if (name === 'IDAT') idat.push(data);
    offset += 12 + length;
  }
  return { width, height, depth, type, interlace, idat: Buffer.concat(idat) };
}
function pixels(png) {
  assert.equal(png.depth, 8); assert.equal(png.interlace, 0);
  const channels = { 0: 1, 2: 3, 4: 2, 6: 4 }[png.type];
  assert.ok(channels, `typ koloru ${png.type}`);
  const raw = zlib.inflateSync(png.idat), stride = png.width * channels, out = Buffer.alloc(stride * png.height);
  for (let y = 0; y < png.height; y++) {
    const filter = raw[y * (stride + 1)];
    for (let x = 0; x < stride; x++) {
      const cur = raw[y * (stride + 1) + 1 + x];
      const a = x >= channels ? out[y * stride + x - channels] : 0, b = y ? out[(y - 1) * stride + x] : 0, c = x >= channels && y ? out[(y - 1) * stride + x - channels] : 0;
      const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
      const pred = [0, a, b, (a + b) >> 1, pa <= pb && pa <= pc ? a : pb <= pc ? b : c][filter];
      out[y * stride + x] = (cur + pred) & 255;
    }
  }
  return { channels, data: out, stride };
}
const png = file => { const d = decodePng(fs.readFileSync(path.join(root, 'public', file))); return `${d.width}x${d.height}`; };

const base = '/';
const manifest = () => JSON.parse(JSON.stringify(load('app/przeszlosc/pwa.ts').przeszloscManifest(base)));

test('manifest: id, scope, start_url, kolory, język, tryb, kategorie; odrębny od spin.clinic', () => {
  const m = manifest();
  assert.equal(m.name, 'przeszłość.today'); assert.equal(m.short_name, 'przeszłość');
  assert.equal(m.id, '/'); assert.equal(m.scope, '/'); assert.equal(m.start_url, '/');
  assert.equal(m.display, 'standalone'); assert.equal(m.lang, 'pl'); assert.equal(m.dir, 'ltr');
  assert.equal(m.theme_color, '#0b0c0e'); assert.equal(m.background_color, '#0b0c0e');
  assert.ok(Array.isArray(m.categories) && m.categories.includes('news'));
  // tożsamość = origin + id: przeszlosc.today i spin.clinic to różne aplikacje, obie instalują się naraz
  const spin = read('app/manifest.ts');
  assert.match(spin, /id: '\/'/); assert.match(spin, /name: 'spin\.clinic/);
  assert.notEqual(new URL(m.id, 'https://przeszlosc.today').href, new URL('/', 'https://spin.clinic').href);
  // pod spin.clinic/przeszlosc: id, scope i start odrębne od aplikacji spin.clinic ("/")
  const nested = load('app/przeszlosc/pwa.ts').przeszloscManifest('/przeszlosc');
  assert.equal(nested.id, '/przeszlosc'); assert.equal(nested.scope, '/przeszlosc'); assert.equal(nested.start_url, '/przeszlosc');
});

test('ikony: any i maskable 192 i 512 istnieją z deklarowanymi wymiarami; apple-touch 180', () => {
  const m = manifest();
  for (const size of ['192x192', '512x512']) for (const purpose of ['any', 'maskable']) assert.ok(m.icons.some(i => i.sizes === size && i.purpose === purpose), `${purpose} ${size}`);
  for (const icon of m.icons) { assert.ok(icon.src.startsWith('/przeszlosc/')); assert.equal(png(icon.src.slice(1)), icon.sizes, icon.src); assert.equal(icon.type, 'image/png'); }
  assert.equal(png('przeszlosc/apple-touch-icon.png'), '180x180');
  assert.equal(png('przeszlosc/favicon-32.png'), '32x32');
});

test('ikony: znak wyśrodkowany, a w maskable cała treść mieści się w bezpiecznej strefie (koło o promieniu 40% szerokości)', () => {
  for (const file of ['icon-192', 'icon-512', 'maskable-192', 'maskable-512', 'apple-touch-icon']) {
    const d = decodePng(fs.readFileSync(path.join(root, 'public/przeszlosc', file + '.png')));
    const { channels, data, stride } = pixels(d);
    const bg = [data[0], data[1], data[2]];
    let minX = d.width, minY = d.height, maxX = -1, maxY = -1, outside = 0;
    const centerX = d.width / 2, centerY = d.height / 2, radius = d.width * 0.4;
    for (let y = 0; y < d.height; y++) for (let x = 0; x < d.width; x++) {
      const o = y * stride + x * channels;
      const diff = Math.max(Math.abs(data[o] - bg[0]), Math.abs(data[o + 1] - bg[1]), Math.abs(data[o + 2] - bg[2]));
      if (diff <= 24) continue;
      minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
      if (Math.hypot(x + 0.5 - centerX, y + 0.5 - centerY) > radius) outside++;
    }
    const cx = (minX + maxX + 1) / 2 / d.width, cy = (minY + maxY + 1) / 2 / d.height;
    assert.ok(Math.abs(cx - 0.5) < 0.02 && Math.abs(cy - 0.5) < 0.02, `${file}: środek znaku ${cx.toFixed(3)} x ${cy.toFixed(3)}`);
    if (file.startsWith('maskable')) assert.equal(outside, 0, `${file}: ${outside} pikseli poza bezpieczną strefą`);
    else assert.ok((maxX - minX) / d.width < 0.7, `${file}: znak za duży`);
  }
});

test('zrzuty ekranu: wide 1280x720 i narrow 780x1688, form_factor, label, pliki istnieją', () => {
  const shots = manifest().screenshots;
  const wide = shots.filter(s => s.form_factor === 'wide'), narrow = shots.filter(s => s.form_factor === 'narrow');
  assert.ok(wide.length >= 2 && narrow.length >= 2, 'min. 2 zrzuty każdego rodzaju');
  for (const s of shots) {
    assert.ok(s.label && s.label.length > 8, `label ${s.src}`);
    assert.ok(!/[–—]/.test(s.label), 'bez długiego myślnika');
    assert.equal(s.type, 'image/png');
    assert.equal(png(s.src.slice(1)), s.sizes, s.src);
    assert.equal(s.sizes, s.form_factor === 'wide' ? '1280x720' : '780x1688', s.src);
  }
  assert.equal(new Set(shots.map(s => s.src)).size, shots.length);
});

test('skróty: 2-4, adresy wskazują istniejące trasy aplikacji, ikony istnieją', () => {
  const m = manifest();
  assert.ok(m.shortcuts.length >= 2 && m.shortcuts.length <= 4);
  for (const s of m.shortcuts) {
    assert.ok(s.name && s.short_name && s.short_name.length <= 12, s.name);
    const u = new URL(s.url, 'https://przeszlosc.today');
    assert.ok(u.pathname === m.scope || u.pathname.startsWith('/przeszlosc'), 'w zakresie aplikacji');
    const dir = u.pathname.replace(/^\//, '');
    assert.ok(exists(`app/${dir}/page.tsx`), `trasa ${u.pathname} -> app/${dir}/page.tsx`);
    for (const i of s.icons) assert.equal(png(i.src.slice(1)), i.sizes);
  }
  for (const wanted of ['/przeszlosc', '/przeszlosc/odstepstwa', '/przeszlosc/funkcje']) assert.ok(m.shortcuts.some(s => new URL(s.url, 'https://x').pathname === wanted), wanted);
  // Głosowania: trasa jest, ale za flagą API; brak skrótu to świadoma decyzja (komentarz w pwa.ts)
  assert.ok(exists('app/przeszlosc/glosowania/page.tsx'));
  assert.match(read('app/przeszlosc/pwa.ts'), /PRZESZLOSC_VOTES_LIST_ENABLED/);
});

test('trasy: /przeszlosc/aplikacja i /przeszlosc/jak-to-dziala istnieją; aplikacja za flagą APP', () => {
  assert.ok(exists('app/przeszlosc/aplikacja/page.tsx'));
  assert.ok(exists('app/przeszlosc/jak-to-dziala/page.tsx'));
  assert.match(read('app/przeszlosc/aplikacja/page.tsx'), /serverFeature\('APP_ENABLED'\)/);
  assert.match(read('app/przeszlosc/aplikacja/page.tsx'), /canonical: 'https:\/\/przeszlosc\.today\/aplikacja'/);
});

test('middleware: krótkie adresy przeszłości, stare /zrodla i /metodologia, reszta bez zmian', () => {
  const NextResponse = { next: () => ({ kind: 'next' }), rewrite: url => ({ kind: 'rewrite', to: url.pathname + url.search }), redirect: (url, code) => ({ kind: 'redirect', to: String(url.pathname || url), code }) };
  const mw = load('middleware.ts', { 'next/server': { NextResponse } });
  const req = (host, pathname, search = '') => ({ headers: { get: () => host }, nextUrl: { pathname, search }, url: `https://${host}${pathname}${search}` });
  assert.deepEqual(mw.middleware(req('przeszlosc.today', '/aplikacja')), { kind: 'rewrite', to: '/przeszlosc/aplikacja' });
  assert.deepEqual(mw.middleware(req('przeszlosc.today', '/jak-to-dziala/')), { kind: 'rewrite', to: '/przeszlosc/jak-to-dziala' });
  assert.deepEqual(mw.middleware(req('www.przeszlosc.today', '/jak-to-dziala', '?x=1')), { kind: 'rewrite', to: '/przeszlosc/jak-to-dziala?x=1' });
  for (const old of ['/zrodla', '/metodologia']) assert.deepEqual(mw.middleware(req('przeszlosc.today', old)), { kind: 'redirect', to: '/jak-to-dziala', code: 308 });
  assert.deepEqual(mw.middleware(req('przeszlosc.today', '/')), { kind: 'rewrite', to: '/przeszlosc' });
  assert.deepEqual(mw.middleware(req('przeszlosc.today', '/manifest.webmanifest')), { kind: 'rewrite', to: '/przeszlosc/manifest.webmanifest' });
  assert.equal(mw.middleware(req('przeszlosc.today', '/sw.js')).kind, 'next');
  assert.equal(mw.middleware(req('przeszlosc.today', '/przeszlosc-app/screenshots/wide-1.png')).kind, 'next');
  assert.equal(mw.middleware(req('przeszlosc.today', '/klinika')).kind, 'redirect');
  // spin.clinic: /aplikacja, /zrodla, /metodologia zostają swoje; manifest przez route handler
  for (const own of ['/aplikacja', '/zrodla', '/metodologia', '/jak-to-dziala']) assert.equal(mw.middleware(req('spin.clinic', own)).kind, 'next', own);
  assert.deepEqual(mw.middleware(req('spin.clinic', '/manifest.webmanifest')), { kind: 'rewrite', to: '/spin-manifest.webmanifest' });
});

function sw(origin) {
  const listeners = {}, stores = new Map();
  const store = name => { if (!stores.has(name)) stores.set(name, new Map()); return stores.get(name); };
  const keyOf = request => (typeof request === 'string' ? new URL(request, origin) : new URL(request.url)).pathname;
  const cacheApi = name => ({
    addAll: async list => { for (const item of list) store(name).set(keyOf(item), { body: 'shell' }); },
    keys: async () => [...store(name).keys()].map(key => ({ url: origin + key })),
    match: async request => store(name).get(keyOf(request)),
    put: async (request, response) => { const s = store(name); const key = keyOf(request); s.delete(key); s.set(key, response); },
    delete: async request => store(name).delete(keyOf(request)),
  });
  const caches = {
    open: async name => cacheApi(name),
    keys: async () => [...stores.keys()],
    match: async request => { for (const s of stores.values()) if (s.has(keyOf(request))) return s.get(keyOf(request)); return undefined; },
    delete: async name => stores.delete(name),
  };
  let online = true, nextResponse;
  const self = { location: { origin }, addEventListener: (name, fn) => { listeners[name] = fn; }, skipWaiting: async () => {},
    registration: { showNotification: async () => {} }, clients: { claim: async () => {}, matchAll: async () => [], openWindow: async () => {} } };
  const fetchMock = async () => { if (!online) throw new Error('offline'); return nextResponse; };
  vm.runInNewContext(read('public/sw.js'), { self, URL, Date, Headers, Response, caches, fetch: (...a) => fetchMock(...a), setTimeout, clearTimeout, AbortController, console });
  const reply = (body, { cache = 'public, s-maxage=3600', type = 'basic', ok = true, redirected = false } = {}) =>
    ({ body, ok, type, redirected, status: ok ? 200 : 500, headers: new Headers({ 'Cache-Control': cache }), clone() { return this; } });
  const nav = async (pathname, { headers = {}, method = 'GET' } = {}) => {
    let result = 'pass';
    const req = { method, url: origin + pathname, mode: 'navigate', headers: new Headers(headers) };
    await new Promise(resolve => {
      const done = Promise.resolve(listeners.fetch({ request: req, respondWith: p => { result = Promise.resolve(p); } }));
      done.then(resolve);
    });
    return result === 'pass' ? 'pass' : await result;
  };
  return { install: () => listeners.install({ waitUntil: p => p }), stores, store, reply, nav, setOnline: v => { online = v; }, setResponse: r => { nextResponse = r; } };
}

test('service worker przeszłości: strona informacyjna trafia do pamięci stron, dane i zapytania nie', async () => {
  const o = sw('https://przeszlosc.today');
  await o.install();
  assert.ok(o.store('przeszlosc-pwa-v3').has('/przeszlosc/offline.html'));
  // publiczna strona statyczna: zapisana
  o.setResponse(o.reply('<html>jak</html>'));
  await o.nav('/przeszlosc/jak-to-dziala');
  assert.ok(o.store('przeszlosc-pages-v3').has('/przeszlosc/jak-to-dziala'));
  // bez sieci: kopia
  o.setOnline(false);
  const hit = await o.nav('/przeszlosc/jak-to-dziala');
  assert.equal(hit.body, '<html>jak</html>');
  // bez sieci i bez kopii: "Brak połączenia" (offline.html)
  const miss = await o.nav('/przeszlosc/osoba/241-monika-rosa');
  assert.equal(miss.body, 'shell');
  const missQuery = await o.nav('/przeszlosc/jak-to-dziala?q=Kowalski');
  assert.equal(missQuery.body, 'shell');
  o.setOnline(true);
  // nie zapisujemy: odpowiedzi z no-store/private, strony z danymi i osób, adresów z zapytaniem, przekierowań, obcych odpowiedzi
  for (const [path, response] of [
    ['/przeszlosc/jak-to-dziala?utm=x', o.reply('q')], ['/przeszlosc/osoba/241-monika-rosa', o.reply('osoba')], ['/przeszlosc/spolka/0000026438', o.reply('krs')],
    ['/przeszlosc?q=CPK', o.reply('temat')], ['/przeszlosc/alerty?potwierdz=token', o.reply('token')], ['/przeszlosc/aplikacja', o.reply('app')],
  ]) { o.setResponse(response); await o.nav(path); }
  assert.deepEqual([...o.store('przeszlosc-pages-v3').keys()], ['/przeszlosc/jak-to-dziala']);
  o.setResponse(o.reply('prywatna', { cache: 'private, no-store' })); await o.nav('/jak-to-dziala');
  o.setResponse(o.reply('przekierowanie', { redirected: true })); await o.nav('/jak-to-dziala');
  o.setResponse(o.reply('blad', { ok: false })); await o.nav('/jak-to-dziala');
  assert.deepEqual([...o.store('przeszlosc-pages-v3').keys()], ['/przeszlosc/jak-to-dziala']);
  // żądanie z autoryzacją i nie-GET pomija service worker
  assert.equal(await o.nav('/przeszlosc/jak-to-dziala', { headers: { authorization: 'Bearer x' } }), 'pass');
  assert.equal(await o.nav('/przeszlosc/jak-to-dziala', { method: 'POST' }), 'pass');
  // odpowiedzi API nigdy nie wchodzą do żadnej pamięci
  for (const name of ['przeszlosc-pwa-v3', 'przeszlosc-pages-v3']) for (const key of o.store(name).keys()) assert.ok(!key.startsWith('/api/'), key);
});

test('service worker: pamięć stron ograniczona do 6 wpisów; spin.clinic bez pamięci stron przeszłości', async () => {
  const src = read('public/sw.js');
  assert.match(src, /const PAGES_MAX = 6;/);
  assert.match(src, /OFFLINE_PAGES = PT \?/);
  const spin = sw('https://spin.clinic');
  await spin.install();
  spin.setResponse(spin.reply('<html>jak</html>'));
  await spin.nav('/przeszlosc/jak-to-dziala');
  assert.equal(spin.stores.has('przeszlosc-pages-v3'), false);
  assert.ok(spin.store('spin-pwa-v3').has('/app/offline.html'));
});

test('PwaControls: nazwa przeszłość.today, konwencja terminala, tryb standalone i obszary bezpieczne', () => {
  const c = read('app/PwaControls.tsx'), css = read('app/pwa.css');
  assert.match(c, /Zainstaluj przeszłość\.today/);
  assert.match(c, /location\.hostname\.replace\(\/\^www\\\.\/, ''\) === 'przeszlosc\.today'/);
  assert.match(c, /setBanner\(!dismissed\(\) && !standalone\(\)\)/);          // baner ukryty w trybie standalone
  assert.match(c, /isIos && !standalone\(\) && !dismissed\(\)/);               // iOS też
  assert.match(c, /pt-install-dismissed/);
  assert.match(css, /\.sc-pwa--pt/);
  assert.match(css, /content:">"/); assert.match(css, /content:"_"/);
  assert.match(css, /env\(safe-area-inset-bottom\)/); assert.match(css, /env\(safe-area-inset-right\)/); assert.match(css, /env\(safe-area-inset-left\)/);
  // spin.clinic zachowuje swoje komunikaty
  assert.match(c, /Zainstaluj aplikację/);
});

test('teksty przeszłości: bez długiego myślnika i bez "??" w nowych plikach', () => {
  for (const file of ['app/przeszlosc/pwa.ts', 'app/przeszlosc/aplikacja/AplikacjaPage.tsx', 'app/przeszlosc/aplikacja/page.tsx', 'public/przeszlosc/offline.html']) {
    const text = read(file);
    assert.ok(!/[–—]/.test(text), `${file}: długi myślnik`);
    assert.ok(!/\?\?/.test(text), `${file}: ??`);
  }
});

// ---- strona "Jak to działa" (zadanie B) ----
// JSON przenosi dane między kontekstami vm (inne prototypy tablic); nb zostaje funkcją
const tresc = () => { const m = load('app/przeszlosc/jak-to-dziala/tresc.ts'); return { ...JSON.parse(JSON.stringify(m)), nb: m.nb }; };

test('Jak to działa: 9 sekcji, kotwice zgodne z nagłówkami, spis i obietnica', () => {
  const t = tresc();
  assert.equal(t.SEKCJE.length, 9);
  assert.deepEqual(t.SEKCJE.map(s => s.tytul).slice(0, 3), ['Jak to działa', 'W trzech krokach', 'Skąd mamy dane']);
  const view = read('app/przeszlosc/jak-to-dziala/JakToDziala.tsx');
  for (const s of t.SEKCJE.slice(1)) assert.match(view, new RegExp(`<Naglowek id="${s.id}" />`), s.id);
  assert.match(view, /<h1 id="jak">/);
  assert.match(view, /href="\/przeszlosc#wynik"/);               // "Zobacz przykład" = temat dnia
  assert.equal(t.KROKI.length, 3);
  assert.ok(t.OBIETNICA.split('. ').length === 1, 'obietnica to jedno zdanie');
});

test('Jak to działa: tabela źródeł ma 5 pól w każdym wierszu, braki oznaczone "Do potwierdzenia", bez wymyślonych dat', () => {
  const { ZRODLA, ZRODLA_UWAGA } = tresc();
  assert.ok(ZRODLA.length >= 10);
  for (const z of ZRODLA) for (const k of ['nazwa', 'domena', 'zawiera', 'zakres', 'odswiezanie', 'ograniczenia']) assert.ok(z[k] && z[k].length >= 3, `${z.nazwa}.${k}`);
  assert.ok(ZRODLA.some(z => /^Do potwierdzenia/.test(z.zakres)), 'są pola do potwierdzenia');
  assert.match(ZRODLA_UWAGA, /brak w naszych danych \(stan na 13 października 2026\)/);
  for (const name of ['Sejm', 'KRS', 'Zamówienia publiczne: TED', 'Wpisy na X', 'Media', 'spin.clinic']) assert.ok(ZRODLA.some(z => z.nazwa === name), name);
});

test('Jak to działa: progi odstępstw zgodne z backend/news/voting_anomalies.py', () => {
  const py = fs.readFileSync(path.join(root, '..', 'backend/news/voting_anomalies.py'), 'utf8');
  const get = name => Number(new RegExp(`^${name} = ([0-9.]+)`, 'm').exec(py)[1]);
  const text = JSON.stringify(tresc().PROGI);
  assert.equal(get('EXCESS_PP'), 5); assert.match(text, /5 punktów procentowych/);
  assert.equal(get('UNITY'), 0.8); assert.match(text, /80%/);
  assert.equal(get('MIN_VOTES'), 20); assert.match(text, /20 głosami/);
  assert.equal(get('MIN_CLUB_CAST'), 3); assert.match(text, /3 oddane głosy/);
  assert.equal(get('WINDOW_DAYS'), 90); assert.match(text, /90 dni/);
});

test('Jak to działa: odstępy w tekście (twarde spacje), bez długiego myślnika, bez prostych cudzysłowów w treści', () => {
  const t = tresc();
  assert.equal(t.nb('Sejm i z kim w Sejmie 90 dni'), 'Sejm i z kim w Sejmie 90 dni');
  const all = JSON.stringify(t);
  assert.ok(!/[–—]/.test(all), 'długi myślnik');
  assert.ok(!/\?\?/.test(all));
  const strings = [];
  (function walk(v) { if (typeof v === 'string') strings.push(v); else if (v && typeof v === 'object') Object.values(v).forEach(walk); })(t);
  for (const s of strings) assert.ok(!/"/.test(s), `prosty cudzysłów: ${s.slice(0, 60)}`);
});

test('Jak to działa: strona statyczna (bez API i ciasteczek), metadane, przekierowania starych adresów, odnośniki', () => {
  const view = read('app/przeszlosc/jak-to-dziala/JakToDziala.tsx'), page = read('app/przeszlosc/jak-to-dziala/page.tsx');
  assert.ok(!/fetch\(|useEffect|cookies\(|headers\(/.test(view + page), 'komponent serwerowy bez API');
  assert.match(view, /<Bar quiet \/>/);
  assert.match(page, /canonical: 'https:\/\/przeszlosc\.today\/jak-to-dziala'/);
  assert.match(page, /description: DESCRIPTION/);
  for (const old of ['zrodla', 'metodologia']) assert.match(read(`app/przeszlosc/${old}/page.tsx`), /permanentRedirect\('\/przeszlosc\/jak-to-dziala'\)/);
  const ui = read('app/przeszlosc/ui.tsx');
  assert.match(ui, /\['\/przeszlosc\/jak-to-dziala', 'Jak to działa'\]/);
  assert.ok(!/przeszlosc#jak/.test(ui));
  assert.match(ui, /<a href="\/przeszlosc\/jak-to-dziala">Jak to działa<\/a>/);             // stopka
  assert.match(read('app/przeszlosc/TopicTree.tsx'), /href="\/przeszlosc\/jak-to-dziala">Jak to działa i skąd mamy dane/);  // pod wyszukiwarką
});
