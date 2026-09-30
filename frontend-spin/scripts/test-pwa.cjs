const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function route(file, env) {
  // These route handlers use plain JS syntax; no compiler dependency is needed.
  const compiled = fs.readFileSync(file, 'utf8').replace('export const dynamic', 'const dynamic').replace('export function GET', 'function GET') + '\nexports.GET = GET;';
  const context = { exports: {}, process: { env }, Response };
  vm.runInNewContext(compiled, context);
  return context.exports.GET();
}
(async () => {
  const android = 'app/.well-known/assetlinks.json/route.ts';
  const apple = 'app/.well-known/apple-app-site-association/route.ts';
  for (const file of [android, apple]) assert.equal(route(file, {}).status, 404);
  assert.equal(route(android, { ANDROID_PACKAGE_NAME: 'clinic.spin' }).status, 404);
  assert.equal(route(apple, { APPLE_TEAM_ID: 'TEAM' }).status, 404);
  const a = route(android, { ANDROID_PACKAGE_NAME: 'clinic.spin', ANDROID_SHA256_FINGERPRINT: 'AA:BB' });
  assert.match(a.headers.get('content-type'), /application\/json/);
  assert.equal((await a.json())[0].target.package_name, 'clinic.spin');
  const i = await route(apple, { APPLE_TEAM_ID: 'TEAM', APPLE_BUNDLE_ID: 'clinic.spin' }).json();
  assert.equal(i.applinks.details[0].appID, 'TEAM.clinic.spin');

  const handlers = {};
  const shown = [];
  const opened = [];
  const entries = new Map();
  const key = request => typeof request === 'string' ? request : request.url;
  const cache = {
    match: async request => entries.get(key(request))?.clone(),
    put: async (request, response) => entries.set(key(request), response),
    keys: async () => [...entries.keys()].map(url => ({ url })),
    delete: async request => entries.delete(key(request)),
  };
  let network = async () => new Response('{"count":1}', { headers: { 'Content-Type': 'application/json' } });
  const context = { URL, Response, Headers, AbortController, setTimeout, clearTimeout,
    caches: { open: async () => cache }, fetch: (...args) => network(...args),
    self: { location: { origin: 'https://spin.clinic' }, addEventListener: (name, fn) => handlers[name] = fn,
      registration: { showNotification: async (...args) => shown.push(args) },
      clients: { matchAll: async () => [], openWindow: async url => opened.push(url) } } };
  vm.runInNewContext(fs.readFileSync('public/sw.js', 'utf8'), context);
  let pending;
  handlers.push({ data: { json: () => { throw Error(); } }, waitUntil: p => pending = p });
  await pending;
  assert.equal(shown[0][0], 'spin.clinic');
  handlers.notificationclick({ notification: { close() {}, data: { url: 'https://evil.example/' } }, waitUntil: p => pending = p });
  await pending;
  assert.equal(opened[0], 'https://spin.clinic/');
  for (const url of ['/api/account/me/', '/api/push/subscriptions/', '/api/account/export/']) {
    handlers.fetch({ request: { method: 'GET', url: 'https://spin.clinic' + url, headers: new Headers(), mode: 'cors' }, respondWith: () => assert.fail('Private API intercepted') });
  }
  const request = { method: 'GET', url: 'https://spin.clinic/api/clinic/stats/', headers: new Headers(), mode: 'cors' };
  const fetchEvent = () => {
    handlers.fetch({ request, respondWith: promise => pending = promise });
    return pending;
  };
  assert.equal((await fetchEvent()).status, 200);
  assert.equal(entries.size, 1);
  network = async () => { throw Error('offline'); };
  assert.equal((await fetchEvent()).status, 200);
  entries.set(request.url, new Response('{}', { headers: { 'X-Spin-Cached-At': String(Date.now() - 301000) } }));
  assert.equal((await fetchEvent()).status, 503);
  entries.clear();
  network = async (_, options) => {
    assert.equal(options.credentials, 'omit');
    return new Response('{}', { headers: { 'Cache-Control': 'private, no-store' } });
  };
  assert.equal((await fetchEvent()).status, 200);
  assert.equal(entries.size, 0);
  console.log('PWA: associations, push, safe URLs, private API bypass, cache TTL and no-store OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
