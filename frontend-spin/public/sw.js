/*
 * Service worker spin.clinic (v3).
 * - Pamięć podręczna: tylko pliki statyczne aplikacji oraz publiczne odpowiedzi API (GET bez poświadczeń).
 * - Offline: strona /app/offline.html pokazuje ostatnie przekazy dnia z pamięci podręcznej.
 * - Push: powiadomienie z nazwiskiem w tytule; kliknięcie otwiera wpis lub diagnozę.
 * - Aktualizacja: nowa wersja przejmuje stronę od razu (skipWaiting + claim); aplikacja pokazuje przycisk „Odśwież”.
 */
const VERSION = 'v3';
const CACHE = `spin-pwa-${VERSION}`;
const SHELL = ['/app/offline.html', '/app/icon-192.png', '/app/icon-512.png'];
const MAX_ENTRIES = 100;
const API_MAX_AGE = 5 * 60 * 1000;
const PUBLIC_API = /^\/api\/clinic\/(?:stats|spins|messages)?\/?$/;

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key.startsWith('spin-pwa-') && key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});
self.addEventListener('message', event => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

async function trim(cache) {
  const keys = await cache.keys();
  await Promise.all(keys.filter(key => !SHELL.includes(new URL(key.url).pathname)).slice(0, Math.max(0, keys.length - MAX_ENTRIES)).map(key => cache.delete(key)));
}
async function staticAsset(request) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (response.ok && response.type === 'basic') {
    await cache.put(request, response.clone());
    await trim(cache);
  }
  return response;
}
async function publicApi(request) {
  const cache = await caches.open(CACHE);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(request, { signal: controller.signal, credentials: 'omit' });
    if (response.status >= 500) throw new Error('unavailable');
    if (response.ok && !/no-store|private|no-cache/.test(response.headers.get('Cache-Control') || '')) {
      const headers = new Headers(response.headers);
      headers.set('X-Spin-Cached-At', String(Date.now()));
      await cache.put(request, new Response(await response.clone().arrayBuffer(), { status: response.status, headers }));
      await trim(cache);
    }
    return response;
  } catch {
    const hit = await cache.match(request);
    if (hit && Date.now() - Number(hit.headers.get('X-Spin-Cached-At') || 0) < API_MAX_AGE) return hit;
    return new Response(JSON.stringify({ detail: 'Brak połączenia.' }), { status: 503, headers: { 'Content-Type': 'application/json' } });
  } finally { clearTimeout(timer); }
}

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || request.headers.has('authorization')) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match('/app/offline.html')));
  } else if (url.pathname.startsWith('/_next/static/') || url.pathname.startsWith('/app/')) {
    event.respondWith(staticAsset(request));
  } else if (PUBLIC_API.test(url.pathname)) {
    event.respondWith(publicApi(request));
  }
});

/** Adres z powiadomienia: tylko ta sama domena albo wpis na X; wszystko inne prowadzi na stronę główną. */
function safeUrl(value) {
  const home = new URL('/', self.location.origin);
  try {
    const candidate = new URL(value || '/', self.location.origin);
    if (candidate.origin === home.origin || /^https:\/\/x\.com\/[A-Za-z0-9_]{1,15}\/status\/[1-9][0-9]*$/.test(candidate.href)) return candidate;
  } catch { /* Zostaje bezpieczna strona główna. */ }
  return home;
}

self.addEventListener('push', event => {
  let data = {};
  try {
    const payload = event.data?.json();
    if (payload && typeof payload === 'object' && !Array.isArray(payload)) data = payload;
  } catch { /* Bezpieczny tekst domyślny. */ }
  const title = typeof data.title === 'string' && data.title.trim() ? data.title.trim().slice(0, 120) : 'spin.clinic';
  const body = typeof data.body === 'string' && data.body.trim() ? data.body.trim().slice(0, 240) : 'Zobacz, co nowego.';
  event.waitUntil(self.registration.showNotification(title, {
    body, lang: 'pl', icon: '/app/icon-192.png', badge: '/app/icon-192.png',
    tag: typeof data.tag === 'string' && data.tag ? data.tag.slice(0, 80) : 'spin-clinic',
    renotify: true, timestamp: Date.now(),
    data: { url: safeUrl(data.url).href, kind: typeof data.kind === 'string' ? data.kind : '' },
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = safeUrl(event.notification.data?.url);
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async clients => {
    const same = clients.filter(client => client.url.startsWith(self.location.origin));
    const exact = same.find(client => client.url === target.href);
    if (exact) return exact.focus();
    if (target.origin === self.location.origin) {
      // Otwarta aplikacja przechodzi na wpis zamiast otwierać drugie okno.
      for (const client of same) {
        try {
          const moved = await client.navigate(target.href);
          if (moved) return moved.focus();
        } catch { /* Klient nie pozwala na nawigację: otwieramy nowe okno. */ }
      }
    }
    return self.clients.openWindow(target.href);
  }));
});
