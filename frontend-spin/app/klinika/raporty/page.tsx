import type { Metadata } from 'next';
import { ReportArchive } from '@spin-clinic/ui';
import { loadReport } from './data';

export const metadata: Metadata = {
  title: 'Raporty tygodnia Dr. Spina - spin.clinic',
  description: 'Najnowszy raport i archiwum tygodniowych obserwacji z diagnoz rządzących i opozycji.',
  alternates: { canonical: '/klinika/raporty' },
};

export default async function ReportArchiveRoute() {
  return <ReportArchive data={await loadReport()} />;
}
