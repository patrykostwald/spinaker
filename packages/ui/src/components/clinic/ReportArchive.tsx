import Link from "next/link";
import { type ReportResponse, reportWeekLabel, reportPublicationLabel } from "../../lib/clinicReports";
import { PageHeaderV3 } from "../../kit/PageHeaderV3";
import { ClinicNav } from "./ClinicNav";

/**
 * Raporty tygodnia v3 (seria 2): nagłówek z dociąganiem, najnowszy raport jako karta na tle tonalnym
 * (tytuł tygodnia, data publikacji, podsumowanie, odnośnik przy dolnej krawędzi), poprzednie tygodnie jako wiersze listy.
 */
export function ReportArchive({ data }: { data: ReportResponse }) {
  const latest = data.report;
  const previous = data.archive.filter(week => week.week_end !== latest?.week_end);
  return <section className="sc-v3 sc-v3-page sc-v3-rep">
    <PageHeaderV3 nav={<ClinicNav />} kicker={<><span className="sc-v3-tag" data-tone="accent" title="Wygenerowane z udziałem AI">AI</span> Klinika · Dr. Spin (AI)</>}
      title="Raporty tygodnia" sub="Obserwacje z diagnoz Dr. Spina, techniki perswazji i wywiady z kolejnych tygodni."
      aside={data.archive.length ? <dl><div><dt>tygodni w archiwum</dt><dd>{data.archive.length.toLocaleString("pl-PL")}</dd></div></dl> : undefined} />
    {latest ? <section aria-labelledby="rep-latest">
      <div className="sc-v3-feed-h"><h2 id="rep-latest">Najnowszy raport</h2></div>
      <Link className="sc-v3-card sc-v3-rep__latest" href={`/klinika/raporty/${latest.week_end}`}>
        <h3>{reportWeekLabel(latest.week_start, latest.week_end)}</h3>
        <p>{latest.summary || `Opublikowano ${latest.diagnoses.government + latest.diagnoses.opposition} diagnoz wpisów obu stron.`}</p>
        <p className="sc-v3-card__f"><span>Opublikowano {reportPublicationLabel(latest.created_at)}</span><span className="sc-v3-lnk">Czytaj raport <span className="sc-v3-ar" aria-hidden="true">→</span></span></p>
      </Link>
    </section> : <p className="sc-v3-empty">Nie ma jeszcze opublikowanych raportów.</p>}
    {previous.length ? <section aria-labelledby="report-weeks">
      <div className="sc-v3-feed-h"><h2 id="report-weeks">Poprzednie tygodnie</h2></div>
      <ul className="sc-v3-weeks">{previous.map(week => <li key={week.week_end}>
        <Link href={`/klinika/raporty/${week.week_end}`}><span>{reportWeekLabel(week.week_start, week.week_end)}</span><span className="sc-v3-ar" aria-hidden="true">→</span></Link>
      </li>)}</ul>
    </section> : null}
  </section>;
}
