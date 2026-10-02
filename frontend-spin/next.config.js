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
    return ['/glosowanie', '/glosowanie/', '/ankieta', '/ankieta/'].map(source => ({ source, destination: '/glosowanie/index.html', permanent: false }));
  },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*/` }];
  },
};
