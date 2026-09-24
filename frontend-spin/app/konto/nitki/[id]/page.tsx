import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { MojaNitkaEditor } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Moja nitka kontekstowa — spin.clinic',
  robots: { index: false, follow: false },
};

export default function PersonalThreadPage({ params }: { params: { id: string } }) {
  if (!/^[1-9]\d{0,11}$/.test(params.id)) notFound();
  return <MojaNitkaEditor threadId={Number(params.id)} />;
}
