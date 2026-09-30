import { serverFeature } from '../../../lib/features';
import { Suspense } from 'react';
import { redirect } from 'next/navigation';
import { AccountRecovery } from '@spin-clinic/ui';
export const metadata = { title: 'Potwierdź e-mail — spin.clinic', robots: { index: false, follow: false } };
export default async function Page() {
  if (!(await serverFeature('ACCOUNTS_ENABLED'))) redirect('/');
  return <Suspense fallback={<p role="status">Wczytywanie…</p>}><AccountRecovery mode="verify" /></Suspense>;
}
