import type { Metadata } from 'next';
import { WeeklyReport, reportWeekLabel } from '@spin-clinic/ui';
import { loadReport } from '../data';

export async function generateMetadata({ params }: { params: { week: string } }): Promise<Metadata> {
  const { report } = await loadReport(params.week);
  return { title: `Raport tygodnia Dr. Spina: ${report ? reportWeekLabel(report.week_start, report.week_end) : params.week} - spin.clinic`,
    description: report?.summary, alternates: { canonical: `/klinika/raporty/${params.week}` } };
}

export default async function ReportWeekRoute({ params }: { params: { week: string } }) {
  return <div className="sc-report-page"><WeeklyReport weekEnd={params.week} initialData={await loadReport(params.week)} /></div>;
}
