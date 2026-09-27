import type { Metadata } from 'next';
import { WeeklyReport } from '@spin-clinic/ui';

export function generateMetadata({ params }: { params: { week: string } }): Metadata {
  return { title: `Raport tygodnia Dr. Spina (${params.week}) — spin.clinic`, alternates: { canonical: `/raport/${params.week}` } };
}

export default function ReportWeekRoute({ params }: { params: { week: string } }) {
  return <main className="sc-report-page"><WeeklyReport weekEnd={params.week} /></main>;
}
