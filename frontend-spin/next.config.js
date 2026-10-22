/** @type {import('next').NextConfig} */
const { isThreadsEnabled, threadRedirects } = require('./lib/threadsRouting');
const { MANIFEST_CACHE } = require('./lib/manifestCache');

module.exports = {
  // osobny katalog budowy dla równoległych podglądów (next dev na innym porcie nie nadpisuje .next); domyślnie .next
  distDir: process.env.NEXT_DIST_DIR || '.next',
  skipTrailingSlashRedirect: true,
  poweredByHeader: false,
  experimental: { proxyTimeout: 130000 },
  transpilePackages: ['@spin-clinic/ui'],
  env: { NEXT_PUBLIC_DOMAIN: process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' },
  images: { unoptimized: true },
  async headers() {
    // Manifest PWA zależy od hosta (spin.clinic vs przeszlosc.today pod tym samym adresem): pamięć podręczna krótka
    // i klucz z hostem (Vary: Host), żeby CDN ani przeglądarka nie podały manifestu jednej marki drugiej domenie.
    const manifestHeaders = [
      { key: 'Cache-Control', value: MANIFEST_CACHE },
      { key: 'Vary', value: 'Host' },
    ];
    return [
      { source: '/sw.js', headers: [
        { key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' },
        { key: 'Service-Worker-Allowed', value: '/' },
      ] },
      { source: '/manifest.webmanifest', headers: manifestHeaders },
      { source: '/przeszlosc/manifest.webmanifest', headers: manifestHeaders },
    ];
  },
  // Krótkie adresy ankiety do postów w social media (właściciel 2.10).
  async redirects() {
    return [
      ...['/glosowanie', '/glosowanie/', '/ankieta', '/ankieta/'].map(source => ({ source, destination: '/glosowanie/index.html', permanent: false })),
      // spinki/nitki/tropy zależą od flagi NEXT_PUBLIC_THREADS_ENABLED (lib/threadsRouting.js)
      ...threadRedirects(isThreadsEnabled()),
      // polskie adresy wpisywane z ręki (audyt 4.10): bez 404
      { source: '/szukaj', destination: '/search', permanent: false },
      // wpisane z ręki adresy (panel designu 6.10): prowadzą do właściwych stron zamiast 404
      { source: '/wywiady', destination: '/klinika/wywiady', permanent: false },
      { source: '/osoby', destination: '/osoby-publiczne', permanent: false },
      { source: '/powiadomienia', destination: '/konto#powiadomienia', permanent: false },
      { source: '/profil', destination: '/konto', permanent: false },
    ];
  },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*/` }];
  },
};
