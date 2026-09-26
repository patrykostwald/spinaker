import type { Metadata } from 'next';
import { SpinDetail } from '@spin-clinic/ui';

const API = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Karta linku na X i w komunikatorach: nagłówek diagnozy i jej streszczenie. */
export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  try {
    const response = await fetch(`${API}/api/clinic/spins/${encodeURIComponent(params.id)}/`, { next: { revalidate: 300 } });
    if (!response.ok) throw new Error('missing');
    const spin = await response.json() as { headline: string; summary: string; verdict_label: string; author: { handle: string } };
    const title = `${spin.verdict_label}: ${spin.headline}`;
    const description = `Diagnoza AI wpisu @${spin.author.handle}. ${spin.summary}`.slice(0, 300);
    return {
      title: `${title} — Klinika spinu`,
      description,
      openGraph: { title, description, type: 'article', siteName: 'spin.clinic' },
      twitter: { card: 'summary', title, description },
    };
  } catch {
    return { title: 'Diagnoza spinu — spin.clinic' };
  }
}

export default function SpinRoute({ params }: { params: { id: string } }) {
  return <SpinDetail id={params.id} />;
}
