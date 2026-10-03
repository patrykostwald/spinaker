import { serverFeature } from '../../../lib/features';
import { redirect } from 'next/navigation';
import type { Metadata } from 'next';
import { CommunityThreadPage } from '@spin-clinic/ui';

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  if (!(await serverFeature('THREADS_ENABLED')) || !/^\d+$/.test(params.id)) return {};
  const image = `https://spin.clinic/api/community/threads/${params.id}/card.png`;
  return { title: 'Nitka - spin.clinic', openGraph: { images: [{ url: image, width: 1200, height: 630 }] },
    twitter: { card: 'summary_large_image', images: [image] } };
}

export default async function CommunityThreadRoute({ params }: { params: { id: string } }) {
  // Nitki czytelników wracają w fazie II (NEXT_PUBLIC_THREADS_ENABLED=true).
  if (!(await serverFeature('THREADS_ENABLED'))) redirect('/');
  return <CommunityThreadPage id={params.id} />;
}
