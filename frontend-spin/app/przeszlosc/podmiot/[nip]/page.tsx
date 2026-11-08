import { notFound } from 'next/navigation';
import { PodmiotNipPage } from '../PodmiotNipPage';

export const metadata = {
  title: 'Podmiot po NIP - przeszłość.today',
  description: 'Zamówienia publiczne (BZP, TED) i dotacje UE (FTS) podmiotu bez wpisu w KRS, np. gminy, powiązane wyłącznie po numerze NIP.',
  robots: { index: false, follow: false },
};

export default function PodmiotRoute({ params }: { params: { nip: string } }) {
  if (!/^\d{10}$/.test(params.nip)) notFound();
  return <PodmiotNipPage nip={params.nip} />;
}
