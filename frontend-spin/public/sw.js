/* Only allowlisted public API requests made without credentials are cached. */
const CACHE = 'spin-pwa-v1';
const SHELL = ['/app/offline.html', '/app/icon-192.png', '/app/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('spin-pwa-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
async function trim(cache) {
  const keys = await cache.keys();
  await Promise.all(keys.filter(key => !SHELL.includes(new URL(key.url).pathname)).slice(0, Math.max(0, keys.length - 100)).map(key => cache.delete(key)));
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
    if (hit && Date.now() - Number(hit.headers.get('X-Spin-Cached-At') || 0) < 5 * 60 * 1000) return hit;
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
  } else if (/^\/api\/clinic\/(stats|spins)\/?$/.test(url.pathname)) {
    event.respondWith(publicApi(request));
  }
});
self.addEventListener('push', event => {
  let data = {};
  try {
    const payload = event.data?.json();
    if (payload && typeof payload === 'object' && !Array.isArray(payload)) data = payload;
  } catch { /* Use a safe default. */ }
  event.waitUntil(self.registration.showNotification(data.title || 'spin.clinic', {
    body: data.body || 'Zobacz, co nowego.', icon: '/app/icon-192.png', badge: '/app/icon-192.png',
    tag: data.tag || 'spin-clinic', data: { url: data.url || '/' },
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  let url = new URL('/', self.location.origin);
  try {
    const candidate = new URL(event.notification.data?.url || '/', self.location.origin);
    if (candidate.origin === url.origin) url = candidate;
  } catch { /* Keep the safe home URL. */ }
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async clients => {
    const existing = clients.find(client => client.url === url.href);
    if (existing) return existing.focus();
    return self.clients.openWindow(url.href);
  }));
});
