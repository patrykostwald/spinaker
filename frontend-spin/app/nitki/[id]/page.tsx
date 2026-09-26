import { redirect } from 'next/navigation';
import type { Metadata } from 'next';
import { CommunityThreadPage } from '@spin-clinic/ui';

export const metadata: Metadata = { title: 'Nitka czytelnika — spin.clinic' };

export default function CommunityThreadRoute({ params }: { params: { id: string } }) {
  // Nitki czytelników wracają w fazie II (NEXT_PUBLIC_THREADS_ENABLED=true).
  if (process.env.NEXT_PUBLIC_THREADS_ENABLED !== 'true') redirect('/');
  return <CommunityThreadPage id={params.id} />;
}
