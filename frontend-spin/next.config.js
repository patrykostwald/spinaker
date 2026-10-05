/** @type {import('next').NextConfig} */
module.exports = {
  skipTrailingSlashRedirect: true,
  poweredByHeader: false,
  experimental: { proxyTimeout: 130000 },
  transpilePackages: ['@spin-clinic/ui'],
  env: { NEXT_PUBLIC_DOMAIN: process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' },
  images: { unoptimized: true },
  async headers() {
    return [{ source: '/sw.js', headers: [
      { key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' },
      { key: 'Service-Worker-Allowed', value: '/' },
    ] }];
  },
  // Krótkie adresy ankiety do postów w social media (właściciel 2.10).
  async redirects() {
    return [
      ...['/glosowanie', '/glosowanie/', '/ankieta', '/ankieta/'].map(source => ({ source, destination: '/glosowanie/index.html', permanent: false })),
      // „Nitki” nazywają się teraz „Tropy”: stare linki (powiadomienia, udostępnienia) prowadzą pod nowy adres.
      { source: '/nitki', destination: '/spinki', permanent: true },
      { source: '/nitki/:path*', destination: '/spinki/:path*', permanent: true },
      { source: '/konto/nitki/:path*', destination: '/konto/spinki/:path*', permanent: true },
      // Tropy -> Spinki (właściciel 3.10)
      { source: '/tropy', destination: '/spinki', permanent: true },
      { source: '/tropy/:path*', destination: '/spinki/:path*', permanent: true },
      { source: '/konto/tropy/:path*', destination: '/konto/spinki/:path*', permanent: true },
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
