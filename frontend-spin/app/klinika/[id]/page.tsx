import type { Metadata } from 'next';
import { SpinDetail } from '@spin-clinic/ui';

const API = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Karta linku na X i w komunikatorach: nagłówek diagnozy i jej streszczenie. */
export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  try {
    const response = await fetch(`${API}/api/clinic/spins/${encodeURIComponent(params.id)}/`, { cache: 'no-store' });
    if (!response.ok) throw new Error('missing');
    const spin = await response.json() as { status?: string; headline: string; summary: string; verdict_label: string; author: { handle: string } };
    if (spin.status === 'withdrawn') return {
      title: 'Diagnoza wycofana – Klinika spinu',
      description: 'Diagnoza została wycofana. Data i powód są dostępne w publicznym rejestrze korekt.',
      robots: { index: false, follow: true },
      openGraph: { title: 'Diagnoza wycofana', description: 'Sprawdź publiczny rejestr korekt.', images: [] },
      twitter: { card: 'summary', title: 'Diagnoza wycofana', description: 'Sprawdź publiczny rejestr korekt.', images: [] },
    };
    const title = `${spin.verdict_label}: ${spin.headline}`;
    const description = `Diagnoza AI wpisu @${spin.author.handle}. ${spin.summary}`.slice(0, 300);
    return {
      title: `${title} — Klinika spinu`,
      description,
      openGraph: { title, description, type: 'article', siteName: 'spin.clinic', images: [{ url: `/api/clinic/spins/${encodeURIComponent(params.id)}/card.png`, width: 1600, height: 900 }] },
      twitter: { card: 'summary_large_image', site: '@spinclinic', title, description, images: [`/api/clinic/spins/${encodeURIComponent(params.id)}/card.png`] },
    };
  } catch {
    return { title: 'Diagnoza niedostępna – spin.clinic', robots: { index: false, follow: true }, openGraph: { images: [] }, twitter: { images: [] } };
  }
}

export default function SpinRoute({ params, searchParams }: { params: { id: string }; searchParams: { returnTo?: string | string[] } }) {
  return <SpinDetail id={params.id} returnTo={typeof searchParams.returnTo === "string" ? searchParams.returnTo : undefined} />;
}
