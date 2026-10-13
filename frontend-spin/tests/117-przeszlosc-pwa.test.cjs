// PWA przeszłość.today (port v3, 13.10.2026): manifest zależny od hosta, ikony, middleware i service worker z osobną pamięcią.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const png = file => { const b = fs.readFileSync(path.join(root, 'public', file)); assert.equal(b.toString('latin1', 1, 4), 'PNG'); return `${b.readUInt32BE(16)}x${b.readUInt32BE(20)}`; };
function load(file, mocks = {}) {
  const source = ts.transpileModule(read(file), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require: name => mocks[name], URL });
  return exports;
}

test('manifest przeszłości: nazwa, zakres zależny od domeny, ikony z public/przeszlosc, skróty', () => {
  const { przeszloscManifest, PT_THEME } = load('app/przeszlosc/pwa.ts');
  const own = przeszloscManifest('/');
  assert.equal(own.name, 'przeszłość.today');
  assert.equal(own.start_url, '/'); assert.equal(own.scope, '/'); assert.equal(own.id, '/');
  assert.equal(own.display, 'standalone'); assert.equal(own.lang, 'pl');
  assert.equal(own.theme_color, PT_THEME); assert.equal(own.background_color, PT_THEME);
  for (const size of ['192x192', '512x512']) for (const purpose of ['any', 'maskable']) assert.ok(own.icons.some(i => i.sizes === size && i.purpose === purpose), `${purpose} ${size}`);
  for (const icon of own.icons) { assert.ok(icon.src.startsWith('/przeszlosc/')); assert.equal(png(icon.src), icon.sizes, icon.src); }
  assert.ok(own.shortcuts.length >= 2 && own.shortcuts.length <= 4);
  for (const s of own.shortcuts) { assert.ok(s.url.startsWith('/przeszlosc')); assert.ok(s.name); for (const i of s.icons) assert.equal(png(i.src), i.sizes); }
  assert.ok(own.shortcuts.some(s => s.url === '/przeszlosc/odstepstwa'));
  const other = przeszloscManifest('/przeszlosc');
  assert.equal(other.start_url, '/przeszlosc'); assert.equal(other.scope, '/przeszlosc');
  assert.equal(png('przeszlosc/apple-touch-icon.png'), '180x180');
  assert.ok(fs.existsSync(path.join(root, 'public/przeszlosc/offline.html')));
});

test('middleware: przeszlosc.today dostaje własny manifest i service worker, spin.clinic bez zmian', () => {
  const calls = [];
  const NextResponse = { next: () => ({ kind: 'next' }), rewrite: url => ({ kind: 'rewrite', to: url.pathname }), redirect: (url, code) => ({ kind: 'redirect', to: url, code }) };
  const mw = load('middleware.ts', { 'next/server': { NextResponse } });
  const req = (host, pathname) => ({ headers: { get: () => host }, nextUrl: { pathname, search: '' }, url: `https://${host}${pathname}` });
  assert.deepEqual(mw.middleware(req('przeszlosc.today', '/manifest.webmanifest')), { kind: 'rewrite', to: '/przeszlosc/manifest.webmanifest' });
  assert.equal(mw.middleware(req('przeszlosc.today', '/sw.js')).kind, 'next');
  assert.equal(mw.middleware(req('przeszlosc.today', '/przeszlosc/icon-192.png')).kind, 'next');
  assert.equal(mw.middleware(req('www.przeszlosc.today', '/')).to, '/przeszlosc');
  assert.equal(mw.middleware(req('przeszlosc.today', '/klinika')).kind, 'redirect');
  // seria 2: spin.clinic dostaje ten sam manifest (app/manifest.ts) przez route handler z nagłówkami pamięci
  assert.deepEqual(mw.middleware(req('spin.clinic', '/manifest.webmanifest')), { kind: 'rewrite', to: '/spin-manifest.webmanifest' });
  assert.equal(mw.middleware(req('spin.clinic', '/klinika')).kind, 'next');
  assert.equal(calls.length, 0);
});

function loadSw(origin) {
  const listeners = {}, shown = [], opened = [];
  const self = { location: { origin }, addEventListener: (name, fn) => { listeners[name] = fn; }, skipWaiting: async () => {},
    registration: { showNotification: async (title, options) => { shown.push({ title, options }); } },
    clients: { claim: async () => {}, matchAll: async () => [], openWindow: async url => { opened.push(url); } } };
  const opens = [];
  vm.runInNewContext(read('public/sw.js'), { self, URL, Date, Headers, Response, caches: { open: async name => { opens.push(name); return { addAll: async list => { opens.push(list); }, keys: async () => [], match: async () => undefined, put: async () => {}, delete: async () => true }; }, keys: async () => [], match: async () => undefined }, fetch: async () => new Response('{}', { status: 200 }), setTimeout, clearTimeout, AbortController, console });
  const run = async (name, event) => { let p; await listeners[name]({ ...event, waitUntil: x => { p = x; }, respondWith: x => { p = x; } }); return p; };
  const probe = p => { let responded = false; listeners.fetch({ request: { method: 'GET', url: origin + p, mode: 'cors', headers: new Headers() }, respondWith: () => { responded = true; } }); return responded; };
  return { listeners, shown, opens, run, probe };
}

test('service worker na przeszlosc.today: osobna pamięć, własne ikony i offline, bez pamięci API', async () => {
  const sw = loadSw('https://przeszlosc.today');
  await sw.run('install', {});
  assert.equal(sw.opens[0], 'przeszlosc-pwa-v3');
  assert.equal(JSON.stringify(sw.opens[1]), JSON.stringify(['/przeszlosc/offline.html', '/przeszlosc/icon-192.png', '/przeszlosc/icon-512.png']));
  for (const p of ['/_next/static/a.js', '/przeszlosc/icon-192.png']) assert.equal(sw.probe(p), true, p);
  for (const p of ['/api/clinic/', '/api/przeszlosc/temat/?q=MON', '/przeszlosc/osoba/1?_rsc=x']) assert.equal(sw.probe(p), false, p);
  await sw.run('push', { data: { json: () => ({}) } });
  assert.equal(sw.shown[0].title, 'przeszłość.today');
  assert.equal(sw.shown[0].options.icon, '/przeszlosc/icon-192.png');
  const spin = loadSw('https://spin.clinic');
  await spin.run('install', {});
  assert.equal(spin.opens[0], 'spin-pwa-v3');
  assert.equal(spin.probe('/api/clinic/'), true);
});
