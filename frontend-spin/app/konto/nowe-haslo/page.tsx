import { Suspense } from 'react';
import { redirect } from 'next/navigation';
import { AccountRecovery } from '@spin-clinic/ui';
export const metadata = { title: 'Nowe hasło — spin.clinic', robots: { index: false, follow: false } };
export default function Page() {
  if (process.env.NEXT_PUBLIC_ACCOUNTS_ENABLED !== 'true') redirect('/');
  return <Suspense fallback={<p role="status">Wczytywanie…</p>}><AccountRecovery mode="password" /></Suspense>;
}
