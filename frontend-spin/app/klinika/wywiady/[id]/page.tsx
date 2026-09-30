import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { cache } from 'react';
import { ClinicInterviewPage, type Interview } from '@spin-clinic/ui';

const API = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Wspólny odczyt dla metadanych i strony; ukrycie wywiadu od razu daje 404.
const loadInterview = cache(async (id: string): Promise<Interview> => {
  if (!/^\d+$/.test(id)) notFound();
  const response = await fetch(`${API}/api/clinic/interviews/${encodeURIComponent(id)}/`, { cache: 'no-store' });
  if (response.status === 404) notFound();
  if (!response.ok) throw new Error('Unable to load interview');
  return response.json();
});

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const interview = await loadInterview(params.id);
  const title = `${interview.guest_name}: ${interview.headline || interview.title}`;
  const description = `Wywiad w ${interview.channel}. Prowadzący: ${interview.host_name}. ${interview.summary}`.slice(0, 300);
  return {
    title: `${title} — Klinika spinu`,
    description,
    openGraph: { title, description, type: 'article', siteName: 'spin.clinic', images: [{ url: '/og.png', width: 1200, height: 630 }] },
    twitter: { card: 'summary_large_image', site: '@spinclinic', title, description, images: ['/og.png'] },
  };
}

export default async function InterviewRoute({ params }: { params: { id: string } }) {
  return <ClinicInterviewPage interview={await loadInterview(params.id)} />;
}
