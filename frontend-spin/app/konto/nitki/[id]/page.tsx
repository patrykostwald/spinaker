import { serverFeature } from '../../../../lib/features';
import type { Metadata } from 'next';
import { notFound, redirect } from 'next/navigation';
import { MojaNitkaEditor } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Moja nitka kontekstowa — spin.clinic',
  robots: { index: false, follow: false },
};

export default async function PersonalThreadPage({ params }: { params: { id: string } }) {
  // Nitki czytelników wracają w fazie II (NEXT_PUBLIC_THREADS_ENABLED=true).
  if (!(await serverFeature('THREADS_ENABLED'))) redirect('/konto');
  if (!(await serverFeature('ACCOUNTS_ENABLED'))) redirect('/');
  if (!/^[1-9]\d{0,11}$/.test(params.id)) notFound();
  return <MojaNitkaEditor threadId={Number(params.id)} />;
}
