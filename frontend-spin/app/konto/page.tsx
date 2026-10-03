import { serverFeature } from '../../lib/features';
import { redirect } from 'next/navigation';
import type { Metadata } from 'next';
import { MojeKonto } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Mój spin.clinic',
  description: 'Twoje nitki, aktywność, obserwowani, powiadomienia i ustawienia konta.',
  robots: { index: false, follow: false },
};

export default async function AccountPage() {
  // Konta czytelników wracają w fazie II (NEXT_PUBLIC_ACCOUNTS_ENABLED=true).
  if (!(await serverFeature('ACCOUNTS_ENABLED'))) redirect('/');
  return <MojeKonto />;
}
