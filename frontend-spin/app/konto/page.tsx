import { redirect } from 'next/navigation';
import type { Metadata } from 'next';
import { MojeKonto } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Moje konto — spin.clinic',
  description: 'Prywatne nitki kontekstowe, ulubione materiały i nitki Dr. Spina, paski tematów i ostatnia aktywność.',
  robots: { index: false, follow: false },
};

export default function AccountPage() {
  // Konta czytelników wracają w fazie II (NEXT_PUBLIC_ACCOUNTS_ENABLED=true).
  if (process.env.NEXT_PUBLIC_ACCOUNTS_ENABLED !== 'true') redirect('/');
  return <MojeKonto />;
}
