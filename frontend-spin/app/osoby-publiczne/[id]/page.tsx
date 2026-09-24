import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { PublicFigurePage } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Profil osoby publicznej — spin.clinic',
  description: 'Funkcja publiczna, oficjalne głosowania, potwierdzone relacje i materiały z Bazy.',
};

export default function PublicFigureRoute({ params }: { params: { id: string } }) {
  if (!/^[1-9]\d{0,11}$/.test(params.id)) notFound();
  return <PublicFigurePage id={Number(params.id)} />;
}
