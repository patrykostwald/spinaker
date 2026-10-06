import { notFound } from 'next/navigation';
import { DrzewoPieniedzy } from '../../DrzewoPieniedzy';

export const metadata = {
  title: 'Drzewo przepływu pieniędzy - przeszłość.today',
  description: 'Spółka z KRS: zamówienia publiczne (TED, BZP), dotacje UE (FTS) i osoby z funkcjami w KRS, powiązane tylko po NIP, KRS i REGON.',
  robots: { index: false, follow: false },
  icons: { icon: [{ url: '/przeszlosc-icon.svg', type: 'image/svg+xml' }], shortcut: '/przeszlosc-icon.svg', apple: '/przeszlosc-icon.svg' },
};

export default function CompanyRoute({ params }: { params: { krs: string } }) {
  // adres: /przeszlosc/spolka/0000012345 (numer KRS) albo /przeszlosc/spolka/17 (id podmiotu w naszej bazie)
  if (!/^\d{10}$|^[1-9]\d{0,9}$/.test(params.krs)) notFound();
  return <DrzewoPieniedzy ident={params.krs} />;
}
