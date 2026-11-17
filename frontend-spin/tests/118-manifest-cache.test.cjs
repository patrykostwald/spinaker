// Seria 2 (13.10.2026): nagłówki pamięci manifestu PWA zależnego od hosta (spin.clinic / przeszlosc.today).
// Sprawdza: wspólna stała, next.config.js headers() dla obu adresów, route handlery z Cache-Control i Vary: Host
// oraz treść manifestu spin.clinic bez zmian względem app/manifest.ts.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { MANIFEST_CACHE, MANIFEST_VARY } = require('../lib/manifestCache');

function load(file, mocks = {}) {
  const source = ts.transpileModule(read(file), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require: name => mocks[name], URL, JSON, process: { env: {} } });
  return exports;
}

class FakeResponse {
  constructor(body, init) { this.body = body; this.headers = new Map(Object.entries(init.headers)); }
}

test('stała pamięci: krótko w przeglądarce, dłużej w CDN, klucz z hostem', () => {
  assert.match(MANIFEST_CACHE, /^public, /);
  assert.match(MANIFEST_CACHE, /max-age=\d+/);
  assert.match(MANIFEST_CACHE, /s-maxage=\d+/);
  assert.ok(Number(/max-age=(\d+)/.exec(MANIFEST_CACHE)[1]) <= 3600, 'przeglądarka najwyżej godzinę');
  assert.equal(MANIFEST_VARY, 'Host');
});

test('next.config.js: Cache-Control i Vary: Host dla /manifest.webmanifest i /przeszlosc/manifest.webmanifest', async () => {
  const config = require('../next.config.js');
  const rules = await config.headers();
  for (const source of ['/manifest.webmanifest', '/przeszlosc/manifest.webmanifest']) {
    const rule = rules.find(r => r.source === source);
    assert.ok(rule, source);
    const h = Object.fromEntries(rule.headers.map(x => [x.key, x.value]));
    assert.equal(h['Cache-Control'], MANIFEST_CACHE, source);
    assert.equal(h.Vary, 'Host', source);
  }
  // service worker bez zmian
  const sw = rules.find(r => r.source === '/sw.js');
  assert.equal(sw.headers.find(x => x.key === 'Cache-Control').value, 'no-cache, no-store, must-revalidate');
});

test('route handler przeszłości: nagłówki z lib/manifestCache, zakres zależny od hosta', () => {
  const pwa = load('app/przeszlosc/pwa.ts');
  const mod = load('app/przeszlosc/manifest.webmanifest/route.ts', {
    'next/server': { NextResponse: FakeResponse }, '../pwa': pwa, '../../../lib/manifestCache': { MANIFEST_CACHE, MANIFEST_VARY },
  });
  assert.equal(mod.dynamic, 'force-dynamic');
  const req = host => ({ headers: { get: () => host } });
  const own = mod.GET(req('przeszlosc.today'));
  assert.equal(own.headers.get('Cache-Control'), MANIFEST_CACHE);
  assert.equal(own.headers.get('Vary'), 'Host');
  assert.equal(JSON.parse(own.body).start_url, '/');
  assert.equal(JSON.parse(mod.GET(req('spin.clinic')).body).start_url, '/przeszlosc');
});

test('route handler spin.clinic: ta sama treść co app/manifest.ts, nagłówki pamięci', () => {
  const routing = require('../lib/threadsRouting');
  const manifest = load('app/manifest.ts', { '../lib/threadsRouting': routing });
  const mod = load('app/spin-manifest.webmanifest/route.ts', {
    'next/server': { NextResponse: FakeResponse }, '../manifest': manifest, '../../lib/manifestCache': { MANIFEST_CACHE, MANIFEST_VARY },
  });
  const res = mod.GET();
  assert.equal(res.headers.get('Cache-Control'), MANIFEST_CACHE);
  assert.equal(res.headers.get('Vary'), 'Host');
  assert.match(res.headers.get('Content-Type'), /application\/manifest\+json/);
  assert.deepEqual(JSON.parse(res.body), JSON.parse(JSON.stringify(manifest.default())));
  assert.equal(JSON.parse(res.body).name, 'spin.clinic - wiadomości i Klinika spinu');
});
