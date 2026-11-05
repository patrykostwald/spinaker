const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const pwa = require('../lib/pwa');
const routing = require('../lib/threadsRouting');

const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const png = file => { const b = fs.readFileSync(path.join(root, 'public', file)); assert.equal(b.toString('latin1', 1, 4), 'PNG'); return `${b.readUInt32BE(16)}x${b.readUInt32BE(20)}`; };
function manifest(flag = 'false') {
  const source = ts.transpileModule(read('app/manifest.ts'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require: () => ({ ...routing, isThreadsEnabled: () => flag === 'true' }) });
  return exports.default();
}

test('flagi: jedna flaga APP włącza aplikację, push wymaga APP, alerty o obserwowanych także konta', () => {
  assert.deepEqual(Object.values(pwa.pwaFeatures({})).filter(Boolean), []);
  const app = pwa.pwaFeatures({ app: true });
  assert.ok(app.install && app.page && app.serviceWorker && !app.push && !app.followedAlerts);
  assert.equal(pwa.pwaFeatures({ push: true, accounts: true }).push, false, 'push bez APP nie działa');
  assert.equal(pwa.pwaFeatures({ app: true, push: true }).followedAlerts, false);
  assert.equal(pwa.pwaFeatures({ app: true, push: true, accounts: true }).followedAlerts, true);
  assert.equal(pwa.featuresFromEnv({ NEXT_PUBLIC_APP_ENABLED: 'true', NEXT_PUBLIC_PUSH_ENABLED: 'TRUE' }).push, false, 'tylko dokładnie "true"');
});

test('rejestracja service workera: flaga APP, produkcja i wsparcie przeglądarki', () => {
  const ok = { appEnabled: true, nodeEnv: 'production', hasServiceWorker: true };
  assert.equal(pwa.shouldRegisterServiceWorker(ok), true);
  for (const patch of [{ appEnabled: false }, { nodeEnv: 'development' }, { hasServiceWorker: false }]) assert.equal(pwa.shouldRegisterServiceWorker({ ...ok, ...patch }), false);
});

test('stan push: iOS poza aplikacją, brak wsparcia, odmowa, dev', () => {
  const base = { hasPush: true, hasServiceWorker: true, hasNotification: true, permission: 'default' };
  assert.equal(pwa.pushState(base), 'ok');
  assert.equal(pwa.pushState({ ...base, ios: true, installed: false, hasPush: false }), 'ios-install');
  assert.equal(pwa.pushState({ ...base, ios: true, installed: true }), 'ok');
  assert.equal(pwa.pushState({ ...base, hasPush: false }), 'unsupported');
  assert.equal(pwa.pushState({ ...base, permission: 'denied' }), 'denied');
  assert.equal(pwa.pushState({ ...base, production: false }), 'dev');
  assert.match(pwa.pushMessage('ios-install'), /Do ekranu początkowego/);
  assert.match(pwa.pushMessage('denied'), /zablokowane/);
  assert.match(pwa.permissionMessage('denied'), /zablokowane/);
  assert.match(pwa.permissionMessage('default'), /Nie udzielono zgody/);
  assert.equal(pwa.permissionMessage('granted'), '');
  assert.equal(pwa.isIosDevice({ platform: 'MacIntel', maxTouchPoints: 5 }), true);
  assert.equal(pwa.isIosDevice({ platform: 'MacIntel', maxTouchPoints: 0 }), false);
});

test('hasze okna aplikacji zależą od flag', () => {
  const on = pwa.pwaFeatures({ app: true, push: true, accounts: true }), noPush = pwa.pwaFeatures({ app: true });
  assert.deepEqual(pwa.windowHash(pwa.HASH_FOLLOWED, on), { mode: 'push', preselect: ['obserwowani'] });
  assert.equal(pwa.windowHash(pwa.HASH_PUSH, noPush), null);
  assert.deepEqual(pwa.windowHash(pwa.HASH_INSTALL, noPush), { mode: 'install', preselect: [] });
  assert.equal(pwa.windowHash('#cokolwiek', on), null);
});

test('manifest: pola instalowalności, id, zrzuty ekranu, ikony maskable i skróty z ikonami', () => {
  for (const flag of ['true', 'false']) {
    const m = manifest(flag);
    assert.equal(m.id, '/'); assert.equal(m.start_url, '/'); assert.equal(m.display, 'standalone'); assert.equal(m.lang, 'pl');
    for (const size of ['192x192', '512x512']) for (const purpose of ['any', 'maskable']) assert.ok(m.icons.some(i => i.sizes === size && i.purpose === purpose), `${purpose} ${size}`);
    for (const icon of m.icons) assert.equal(png(icon.src), icon.sizes, icon.src);
    assert.equal(m.screenshots.filter(s => s.form_factor === 'wide').length, 2);
    assert.equal(m.screenshots.filter(s => s.form_factor === 'narrow').length, 2);
    for (const s of m.screenshots) { assert.equal(png(s.src), s.sizes, s.src); assert.ok(s.label); const [w, h] = s.sizes.split('x').map(Number); assert.ok(Math.max(w / h, h / w) <= 2.3); }
    assert.ok(m.shortcuts.length >= 3 && m.shortcuts.length <= 4);
    for (const item of m.shortcuts) { assert.ok(item.url.startsWith('/') && item.name); for (const icon of item.icons) assert.equal(png(icon.src), icon.sizes); }
  }
});

function loadSw() {
  const listeners = {}, shown = [], opened = [];
  const self = { location: { origin: 'https://spin.clinic' }, addEventListener: (name, fn) => { listeners[name] = fn; }, skipWaiting: async () => {},
    registration: { showNotification: async (title, options) => { shown.push({ title, options }); } },
    clients: { claim: async () => {}, matchAll: async () => self.windows, openWindow: async url => { opened.push(url); } }, windows: [] };
  vm.runInNewContext(read('public/sw.js'), { self, URL, Date, Headers, Response, caches: { open: async () => ({ addAll: async () => {}, keys: async () => [], match: async () => undefined, put: async () => {}, delete: async () => true }), keys: async () => [], match: async () => undefined }, fetch: async () => new Response('{}', { status: 200 }), setTimeout, clearTimeout, AbortController, console });
  const run = async (name, event) => { let p; await listeners[name]({ ...event, waitUntil: x => { p = x; }, respondWith: x => { p = x; } }); return p; };
  return { self, listeners, shown, opened, run };
}

test('service worker v3: wersja pamięci, obsługa fetch, tylko publiczne API', () => {
  assert.match(read('public/sw.js'), /const VERSION = 'v3'/);
  const sw = loadSw();
  for (const name of ['install', 'activate', 'fetch', 'push', 'notificationclick']) assert.equal(typeof sw.listeners[name], 'function', name);
  const probe = path => { let responded = false; sw.listeners.fetch({ request: { method: 'GET', url: 'https://spin.clinic' + path, mode: 'cors', headers: new Headers() }, respondWith: () => { responded = true; } }); return responded; };
  for (const p of ['/api/clinic/', '/api/clinic/messages/', '/api/clinic/stats/', '/_next/static/a.js']) assert.equal(probe(p), true, p);
  for (const p of ['/api/account/me/', '/api/push/subscriptions/', '/konto/alerty']) assert.equal(probe(p), false, p);
});

test('push: tytuł z nazwiskiem, treść i bezpieczny adres wpisu', async () => {
  const sw = loadSw();
  const data = payload => ({ data: { json: () => payload } });
  await sw.run('push', data({ title: 'Anna Testowa: nowy wpis', body: 'Zbadane: 72/100', url: '/klinika/15', tag: 'followed-figure-3', kind: 'followed_diagnosis' }));
  assert.equal(sw.shown[0].title, 'Anna Testowa: nowy wpis');
  assert.equal(sw.shown[0].options.body, 'Zbadane: 72/100');
  assert.equal(sw.shown[0].options.tag, 'followed-figure-3');
  assert.equal(sw.shown[0].options.data.url, 'https://spin.clinic/klinika/15');
  await sw.run('push', data({ title: 'x', url: 'https://zlosliwa.example/phish' }));
  assert.equal(sw.shown[1].options.data.url, 'https://spin.clinic/');
  await sw.run('push', { data: { json: () => { throw new Error('bad'); } } });
  assert.equal(sw.shown[2].title, 'spin.clinic');
  await sw.run('push', data({ title: 'Jan Kowalski: wpis', url: 'https://x.com/jan_k/status/123' }));
  assert.equal(sw.shown[3].options.data.url, 'https://x.com/jan_k/status/123');
});

test('kliknięcie powiadomienia: nawigacja otwartego okna albo nowe okno, obce adresy odrzucone', async () => {
  let closed = 0;
  const click = url => ({ notification: { close: () => { closed++; }, data: { url } } });
  let sw = loadSw();
  await sw.run('notificationclick', click('https://spin.clinic/klinika/15'));
  assert.deepEqual(sw.opened, ['https://spin.clinic/klinika/15']);
  sw = loadSw();
  let focused = 0, navigated = '';
  sw.self.windows = [{ url: 'https://spin.clinic/', focus: async () => { focused++; }, navigate: async url => { navigated = url; return { focus: async () => { focused++; } }; } }];
  await sw.run('notificationclick', click('https://spin.clinic/klinika/15'));
  assert.equal(navigated, 'https://spin.clinic/klinika/15'); assert.equal(focused, 1); assert.deepEqual(sw.opened, []);
  sw = loadSw();
  await sw.run('notificationclick', click('javascript:alert(1)'));
  assert.deepEqual(sw.opened, ['https://spin.clinic/']);
  assert.equal(closed, 3);
});

test('offline: strona czyta ostatnie przekazy z pamięci i nie linkuje do spinek', () => {
  const html = read('public/app/offline.html');
  assert.match(html, /read\('\/api\/clinic\/'\)/);
  assert.match(html, /\/api\/clinic\/messages\/\?page=1/);
  assert.ok(!/href="\/(nitki|spinki|tropy)/.test(html));
});

test('PwaControls, AlertSettings i /aplikacja: spójne hasze, poprawne kodowanie, brak ?? w tekstach', () => {
  for (const file of ['app/PwaControls.tsx', 'app/konto/alerty/AlertSettings.tsx', 'app/aplikacja/AppGuide.tsx', 'lib/pwa.js', 'public/app/offline.html', 'public/sw.js']) {
    const text = read(file);
    assert.ok(!/�|Ã|Å‚/.test(text), 'kodowanie ' + file);
    for (const literal of text.match(/(["'`])(?:(?!\1)[^\\\n])*\1/g) || []) assert.ok(!/\?\?/.test(literal), file + ': ' + literal);
  }
  assert.match(read('app/PwaControls.tsx'), /shouldRegisterServiceWorker\(\{ appEnabled: true/);
  assert.match(read('app/konto/alerty/AlertSettings.tsx'), /HASH_FOLLOWED/);
  assert.match(read('app/aplikacja/page.tsx'), /serverFeature\('APP_ENABLED'\)/);
});
