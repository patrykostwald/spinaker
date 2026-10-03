import { serverFeature } from '../../../../lib/features';
import { redirect } from 'next/navigation';
import type { Metadata } from 'next';
import { MojaNitkaEditor } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Nowa spinka - spin.clinic',
  robots: { index: false, follow: false },
};

export default async function NewPersonalThreadPage() {
  // Tropy czytelników wracają w fazie II (NEXT_PUBLIC_THREADS_ENABLED=true).
  if (!(await serverFeature('THREADS_ENABLED'))) redirect('/konto');
  if (!(await serverFeature('ACCOUNTS_ENABLED'))) redirect('/');
  return <MojaNitkaEditor />;
}
