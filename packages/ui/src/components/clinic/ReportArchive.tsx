import Link from "next/link";
import { type ReportResponse, reportWeekLabel, reportPublicationLabel } from "../../lib/clinicReports";
import { SectionHeader } from "../../kit/SectionHeader";
import { Button } from "../../kit/Button";
import { ClinicNav } from "./ClinicNav";

export function ReportArchive({ data }: { data: ReportResponse }) {
  const latest = data.report;
  const previous = data.archive.filter(week => week.week_end !== latest?.week_end);
  return <section className="sc-clinic-archives sc-report-archive">
    <ClinicNav />
    <SectionHeader variant="page" title="Raporty tygodnia" subtitle="Obserwacje z diagnoz Dr. Spina, techniki perswazji i wywiady z kolejnych tygodni." />
    {latest ? <article className="sc-report-archive__latest">
      <SectionHeader kicker="Najnowszy raport" title={reportWeekLabel(latest.week_start, latest.week_end)}
        subtitle={`Opublikowano ${reportPublicationLabel(latest.created_at)}`} />
      {latest.summary ? <p>{latest.summary}</p> : <p>Opublikowano {latest.diagnoses.government + latest.diagnoses.opposition} diagnoz wpisów obu stron.</p>}
      <Button href={`/klinika/raporty/${latest.week_end}`}>Czytaj raport →</Button>
    </article> : <p>Nie ma jeszcze opublikowanych raportów.</p>}
    {previous.length ? <section aria-labelledby="report-weeks">
      <SectionHeader titleId="report-weeks" title="Poprzednie tygodnie" />
      <ul className="sc-report-archive__weeks">{previous.map(week => <li key={week.week_end}>
        <Link href={`/klinika/raporty/${week.week_end}`}>{reportWeekLabel(week.week_start, week.week_end)} <span aria-hidden="true">→</span></Link>
      </li>)}</ul>
    </section> : null}
  </section>;
}
