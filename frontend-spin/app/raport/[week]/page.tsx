import { redirect } from 'next/navigation';

export default function ReportWeekRoute({ params }: { params: { week: string } }) {
  redirect(`/klinika/raporty/${encodeURIComponent(params.week)}`);
}
