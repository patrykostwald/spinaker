/** @type {import('next').NextConfig} */
module.exports = {
  skipTrailingSlashRedirect: true,
  experimental: { proxyTimeout: 130000 },
  transpilePackages: ['@spin-clinic/ui'],
  env: { NEXT_PUBLIC_DOMAIN: process.env.NEXT_PUBLIC_DOMAIN || 'przeszlosc.today' },
  images: { unoptimized: true },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*/` }];
  },
};
