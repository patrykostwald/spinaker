import type { MetadataRoute } from 'next';

const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic';

/** Wyszukiwarki: cały serwis poza panelem zespołu, kontem i API; wskazanie mapy strony. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: '*', allow: '/', disallow: ['/editor', '/konto', '/dostep', '/api/', '/ui-kit'] }],
    sitemap: `https://${DOMAIN}/sitemap.xml`,
    host: `https://${DOMAIN}`,
  };
}
