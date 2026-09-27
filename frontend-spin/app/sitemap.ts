import type { MetadataRoute } from 'next';

const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic';
const API = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const BASE = `https://${DOMAIN}`;

export const revalidate = 3600;

/** Mapa strony dla wyszukiwarek: strony stałe i najnowsze diagnozy Kliniki (gdy API nie odpowie — same strony stałe). */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const pages: MetadataRoute.Sitemap = [
    { url: `${BASE}/`, lastModified: now, changeFrequency: 'hourly', priority: 1 },
    { url: `${BASE}/klinika`, lastModified: now, changeFrequency: 'hourly', priority: 0.9 },
    { url: `${BASE}/raport`, changeFrequency: 'weekly', priority: 0.8 },
    { url: `${BASE}/o-nas`, changeFrequency: 'monthly', priority: 0.6 },
    { url: `${BASE}/zrodla`, changeFrequency: 'weekly', priority: 0.5 },
    { url: `${BASE}/wsparcie`, changeFrequency: 'monthly', priority: 0.4 },
    { url: `${BASE}/zasady-korzystania`, changeFrequency: 'yearly', priority: 0.2 },
    { url: `${BASE}/polityka-prywatnosci`, changeFrequency: 'yearly', priority: 0.2 },
  ];
  try {
    const response = await fetch(`${API}/api/clinic/`, { next: { revalidate: 3600 } });
    if (!response.ok) return pages;
    const data = await response.json() as { columns?: Record<string, Array<{ id: number; post?: { published_at?: string } }>> };
    const spins = Object.values(data.columns ?? {}).flat().map(spin => ({
      url: `${BASE}/klinika/${spin.id}`,
      lastModified: spin.post?.published_at ? new Date(spin.post.published_at) : undefined,
      changeFrequency: 'monthly' as const,
      priority: 0.7,
    }));
    return [...pages, ...spins];
  } catch {
    return pages;
  }
}
