import type { Metadata } from 'next';
import { WeeklyReport } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Raport tygodnia Dr. Spina — spin.clinic',
  description: 'Automatyczny raport tygodnia: waga spinu rządzących i opozycji, spin tygodnia, najczęstsze techniki, usunięte posty polityków i wywiady dnia.',
  alternates: { canonical: '/raport' },
};

export default function ReportRoute() {
  return <main className="sc-report-page"><WeeklyReport /></main>;
}
