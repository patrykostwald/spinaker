/*
 * Service worker spin.clinic (v3) i przeszłość.today (ta sama aplikacja, druga domena: osobna pamięć, offline /przeszlosc/offline.html, bez pamięci API).
 * - Pamięć podręczna: tylko pliki statyczne aplikacji oraz publiczne odpowiedzi API (GET bez poświadczeń).
 * - Offline: strona /app/offline.html pokazuje ostatnie przekazy dnia z pamięci podręcznej.
 * - Push: powiadomienie z nazwiskiem w tytule; kliknięcie otwiera wpis lub diagnozę.
 * - Aktualizacja: nowa wersja przejmuje stronę od razu (skipWaiting + claim); aplikacja pokazuje przycisk „Odśwież”.
 * - przeszłość.today (seria PWA 13.10): pamięć 1 = powłoka (strona „Brak połączenia”, ikony) + pliki statyczne (/_next/static, ikony, kroje);
 *   pamięć 2 = ostatnio otwarte STATYCZNE strony informacyjne z listy OFFLINE_PAGES (najwyżej 6, bez zapytań w adresie, tylko odpowiedzi
 *   bez no-store/private). Nigdy: odpowiedzi API, strony osób i spółek, adresy z ?zapytaniem, żądania z autoryzacją.
 */
const VERSION = 'v3';
// przeszłość.today (port v3, 13.10): ta sama aplikacja pod drugą domeną - osobna pamięć, własna strona offline i ikony.
// Pamięć podręczna i tak jest osobna dla każdej domeny; inna nazwa nie miesza wpisów np. na localhost.
const HOST = new URL(self.location.origin).hostname.replace(/^www\./, '');
const PT = HOST === 'przeszlosc.today';
const CACHE = PT ? `przeszlosc-pwa-${VERSION}` : `spin-pwa-${VERSION}`;
const CACHE_PREFIX = PT ? 'przeszlosc-pwa-' : 'spin-pwa-';
const OFFLINE = PT ? '/przeszlosc/offline.html' : '/app/offline.html';
const ICON = PT ? '/przeszlosc/icon-192.png' : '/app/icon-192.png';
const APP_NAME = PT ? 'przeszłość.today' : 'spin.clinic';
const SHELL = PT ? [OFFLINE, ICON, '/przeszlosc/icon-512.png'] : ['/app/offline.html', '/app/icon-192.png', '/app/icon-512.png'];
const STATIC_PREFIX = PT ? '/przeszlosc/' : '/app/';
// Strony przeszłości, które działają bez sieci po wcześniejszym otwarciu: statyczne, bez danych z API i bez danych osobowych.
// Strony z danymi (temat, osoba, głosowania) wolą "Brak połączenia" niż pustą powłokę z błędami.
const PAGES_CACHE = `przeszlosc-pages-${VERSION}`;
const OFFLINE_PAGES = PT ? ['/przeszlosc/jak-to-dziala', '/jak-to-dziala'] : [];
const PAGES_MAX = 6;
const MAX_ENTRIES = 100;
const API_MAX_AGE = 5 * 60 * 1000;
const PUBLIC_API = /^\/api\/clinic\/(?:stats|spins|messages)?\/?$/;

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => (key.startsWith(CACHE_PREFIX) && key !== CACHE) || (PT && key.startsWith('przeszlosc-pages-') && key !== PAGES_CACHE)).map(key => caches.delete(key))))
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
/** Strona informacyjna przeszłości: najpierw sieć, kopia tylko publicznej odpowiedzi 200 tej samej domeny; offline = kopia albo "Brak połączenia". */
async function offlinePage(request, url) {
  const cache = await caches.open(PAGES_CACHE);
  const key = url.pathname.replace(/\/+$/, '');
  try {
    const response = await fetch(request);
    if (response.ok && response.type === 'basic' && !response.redirected && !/no-store|private/.test(response.headers.get('Cache-Control') || '')) {
      await cache.put(key, response.clone());
      const keys = await cache.keys();
      await Promise.all(keys.slice(0, Math.max(0, keys.length - PAGES_MAX)).map(old => cache.delete(old)));
    }
    return response;
  } catch {
    return (await cache.match(key, { ignoreVary: true })) || (await caches.match(OFFLINE));
  }
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
    const page = OFFLINE_PAGES.includes(url.pathname.replace(/\/+$/, '')) && !url.search;
    event.respondWith(page ? offlinePage(request, url) : fetch(request).catch(() => caches.match(OFFLINE)));
  } else if (url.pathname.startsWith('/_next/static/') || (url.pathname.startsWith(STATIC_PREFIX) && (!PT || /\.(png|svg|ico|woff2|html)$/.test(url.pathname)))) {
    event.respondWith(staticAsset(request));
  } else if (!PT && PUBLIC_API.test(url.pathname)) {
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
  const title = typeof data.title === 'string' && data.title.trim() ? data.title.trim().slice(0, 120) : APP_NAME;
  const body = typeof data.body === 'string' && data.body.trim() ? data.body.trim().slice(0, 240) : 'Zobacz, co nowego.';
  event.waitUntil(self.registration.showNotification(title, {
    body, lang: 'pl', icon: ICON, badge: ICON,
    tag: typeof data.tag === 'string' && data.tag ? data.tag.slice(0, 80) : (PT ? 'przeszlosc-today' : 'spin-clinic'),
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
