import { cache } from 'react';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import type { Article } from '@spin-clinic/ui';
import MaterialView from './view';

const getMaterial = cache(async (id: string): Promise<Article> => {
  if (!/^[1-9]\d{0,11}$/.test(id)) notFound();
  const api = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
  const response = await fetch(`${api}/api/articles/${id}/`, { cache: 'no-store', headers: { Accept: 'application/json' } });
  if (response.status === 404) notFound();
  if (!response.ok) throw new Error('Nie udało się odczytać materiału.');
  return response.json();
});

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const article = await getMaterial(params.id);
  const description = `${article.source.name} · Otwórz źródło, powiązane publikacje i opinie czytelników w spin.clinic.`;
  const image = article.image_url && /^https?:\/\//i.test(article.image_url) ? article.image_url : undefined;
  return {
    metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'),
    title: `${article.title} — spin.clinic`, description,
    alternates: { canonical: `/material/${article.id}` },
    openGraph: { type: 'article', title: article.title, description, url: `/material/${article.id}`, siteName: 'spin.clinic', ...(image ? { images: [{ url: image, alt: '' }] } : {}) },
    twitter: { card: image ? 'summary_large_image' : 'summary', title: article.title, description, ...(image ? { images: [image] } : {}) },
  };
}

export default async function MaterialPage({ params }: { params: { id: string } }) {
  return <MaterialView article={await getMaterial(params.id)} />;
}
