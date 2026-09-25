import type { Metadata } from 'next';
import { MojeKonto } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Moje konto — spin.clinic',
  description: 'Prywatne nitki kontekstowe, ulubione materiały i nitki Dr. Spina, paski tematów i ostatnia aktywność.',
  robots: { index: false, follow: false },
};

export default function AccountPage() {
  return <MojeKonto />;
}
