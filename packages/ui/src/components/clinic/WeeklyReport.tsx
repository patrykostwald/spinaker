"use client";

import { SectionHeader } from "../../kit/SectionHeader";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, DOMAIN } from "../../lib/api";
import { CAMPS, CAMP_LABELS, type Camp, type SpinDetailData, type SpinScale as SpinScaleData, type Verdict } from "../../lib/clinic";
import { measurePost } from "../../lib/xText";
import { xIntentUrl } from "../../lib/xThread";
import { Dialog } from "../Dialog";
import { SpinSummary } from "./SpinSummary";
import { ClinicNav } from "./ClinicNav";
import { SpinAuthorRow } from "./SpinParts";
import { Button } from "../../kit/Button";
import { AiTag, VerdictTag } from "./SpinParts";

type Report = {
  week_start: string; week_end: string; summary: string; created_at: string;
  diagnoses: Record<Camp, number>; scale: SpinScaleData; spin_of_week: SpinDetailData | null;
  techniques: Record<Camp, Array<{ name: string; count: number }>>; deleted: Record<Camp, number>;
  interviews: Array<{ id: number; day: string; headline: string; guest: string; channel: string; verdict: Verdict | "" }>;
};
type ReportResponse = { report: Report | null; archive: Array<{ week_start: string; week_end: string }> };

const MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"];

function weekLabel(start: string, end: string): string {
  const [ys, ms, ds] = start.split("-").map(Number);
  const [ye, me, de] = end.split("-").map(Number);
  if (ms === me && ys === ye) return `${ds}–${de} ${MONTHS[me - 1]} ${ye}`;
  return `${ds} ${MONTHS[ms - 1]} – ${de} ${MONTHS[me - 1]} ${ye}`;
}

function shorten(text: string, budget: number): string {
  if (measurePost(text).weightedLength <= budget) return text;
  let result = "";
  for (const word of text.split(/\s+/)) {
    const next = result ? `${result} ${word}` : word;
    if (measurePost(`${next}…`).weightedLength > budget) break;
    result = next;
  }
  return `${result}…`;
}

/** Raport jako wątek na X: podsumowanie z linkiem, techniki obu stron, spin tygodnia, niedostępne wpisy. */
function reportThread(report: Report, url: string): string[] {
  const label = weekLabel(report.week_start, report.week_end);
  const head = `Raport tygodnia Dr. Spina (AI), ${label}:`;
  const posts = [`${head} ${shorten(report.summary || "najważniejsze spiny, techniki i niedostępne wpisy polityków.", 280 - 30 - measurePost(head).weightedLength)} ${url}`];
  const tech = CAMPS.map(camp => `${CAMP_LABELS[camp]}: ${report.techniques[camp].slice(0, 3).map(t => t.name).join(", ") || "brak ocen"}`).join(". ");
  posts.push(shorten(`Najczęstsze techniki w ocenionych wpisach. ${tech}.`, 270));
  if (report.spin_of_week) {
    const spin = report.spin_of_week;
    posts.push(shorten(`Spin tygodnia: ${spin.author.name} (@${spin.author.handle}) — ${spin.headline} Siła spinu ${spin.intensity}/100. https://${DOMAIN}/klinika/${spin.id}`, 280));
  }
  posts.push(`Niedostępne wpisy polityków w tym tygodniu — rządzący: ${report.deleted.government}, opozycja: ${report.deleted.opposition}. Pełny raport: ${url}`);
  return posts.map((post, index) => `${index + 1}/${posts.length} ${post}`);
}

function ShareReport({ report }: { report: Report }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);
  const posts = reportThread(report, `https://${DOMAIN}/raport/${report.week_end}`);
  async function copy(text: string, index: number) {
    try { await navigator.clipboard.writeText(text); setCopied(index); } catch { setCopied(null); }
  }
  return <>
    <button type="button" className="sc-report__share" onClick={() => setOpen(true)}>Udostępnij raport na X</button>
    <Dialog open={open} onClose={() => setOpen(false)} title="Raport tygodnia jako wątek na X">
      <div className="sc-xshare">
        <div className="sc-xshare__actions">
          <a className="sc-xshare__link is-primary" href={xIntentUrl(posts[0])} target="_blank" rel="noopener noreferrer">Opublikuj 1/{posts.length} na X</a>
          <button type="button" className="sc-xshare__link" onClick={() => copy(posts.join("\n\n"), -1)}>{copied === -1 ? "Skopiowano cały wątek" : "Kopiuj cały wątek"}</button>
        </div>
        <ol className="sc-xshare__posts">{posts.map((post, index) => (
          <li key={index}><p>{post}</p><button type="button" onClick={() => copy(post, index)}>{copied === index ? "Skopiowano" : "Kopiuj"}</button></li>
        ))}</ol>
      </div>
    </Dialog>
  </>;
}

/** Raport tygodnia Dr. Spina — automatyczne zestawienie z 7 dni: waga spinu, spin tygodnia, techniki, niedostępne wpisy, wywiady. */
export function WeeklyReport({ weekEnd }: { weekEnd?: string }) {
  const query = useQuery({
    queryKey: ["clinic-report", weekEnd ?? "latest"],
    queryFn: () => apiFetch<ReportResponse>(weekEnd ? `/api/clinic/report/${weekEnd}/` : "/api/clinic/report/"),
  });
  const data = query.data;
  if (query.isLoading) return <p className="sc-clinic-empty">Ładowanie raportu…</p>;
  if (query.isError && !data?.report) return <div role="alert"><p>Nie udało się pobrać danych.</p><button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></div>;
  if (!data?.report) return <p className="sc-clinic-empty">Raport za ten okres nie został jeszcze opublikowany.</p>;
  const report = data.report;
  return (
    <article className="sc-report">
      {query.isError ? <p role="status">Pokazujemy dane z {new Date(query.dataUpdatedAt).toLocaleString("pl-PL")}. Aktualizacja jest chwilowo niedostępna. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : null}
      <ClinicNav />
      <SectionHeader variant="page" longTitle kicker={<>Raport tygodnia <AiTag /></>}
        title={<>Tydzień w spinie: {weekLabel(report.week_start, report.week_end)}</>}
        subtitle="Najważniejsze obserwacje z diagnoz opublikowanych w tym tygodniu."
        action={<ShareReport report={report} />} />

      <p className="sc-ind-note">Okres: {report.week_start} – {report.week_end} · Publikacja: {new Date(report.created_at).toLocaleString("pl-PL")}</p>
      <div className="sc-report__cols sc-report__counts">{CAMPS.map(camp => <section key={camp} data-camp={camp}><h2>{CAMP_LABELS[camp]}</h2><p><strong>{report.diagnoses[camp]}</strong> opublikowanych diagnoz</p><p>{report.scale[camp].assessed ? `${report.scale[camp].spin + report.scale[camp].partial} z ${report.scale[camp].assessed} (${Math.round((report.scale[camp].spin + report.scale[camp].partial) / report.scale[camp].assessed * 100)}%) ze spinem lub częściowym spinem` : "Brak diagnoz do obliczenia udziału spinu."}</p></section>)}</div>
      <section className="sc-report__panel" aria-labelledby="report-observations"><h2 id="report-observations" className="sc-report__title">Trzy obserwacje</h2><ol>
        <li>Opublikowano {report.diagnoses.government + report.diagnoses.opposition} diagnoz: {report.diagnoses.government} wpisów rządzących i {report.diagnoses.opposition} opozycji. To wybrane materiały, nie reprezentatywna próba całej polityki.</li>
        <li>{CAMPS.map(camp => `${CAMP_LABELS[camp]} — najczęstsza technika: ${[...report.techniques[camp]].sort((a, b) => b.count - a.count)[0]?.name ?? "brak danych"}`).join(". ")}.</li>
        <li>Odnotowano {report.deleted.government + report.deleted.opposition} niedostępnych wpisów; niedostępność nie potwierdza usunięcia przez autora.</li>
      </ol>{report.summary ? <details><summary>Pełne podsumowanie tygodnia</summary><p>{report.summary}</p></details> : null}</section>

      {report.spin_of_week ? (
        <section className="sc-report__panel sc-clinic-sotd" aria-labelledby="report-sotw">
          <h2 id="report-sotw" className="sc-report__title">Spin tygodnia</h2>
          <SpinAuthorRow author={report.spin_of_week.author} publishedAt={report.spin_of_week.post.published_at} />
          <SpinSummary spin={report.spin_of_week} />
          <Button href={`/klinika/${report.spin_of_week.id}`}>Pełna diagnoza ze źródłami →</Button>
        </section>
      ) : null}

      <section className="sc-report__panel" aria-labelledby="report-techniques">
        <h2 id="report-techniques" className="sc-report__title">Najczęstsze techniki</h2>
        <div className="sc-report__cols">{CAMPS.map(camp => (
          <div key={camp}>
            <h3>{CAMP_LABELS[camp]} <span>{report.diagnoses[camp]} ocenionych wpisów</span></h3>
            {report.techniques[camp].length ? <ol>{report.techniques[camp].map(t => <li key={t.name}>{t.name} <span>{t.count} z {report.diagnoses[camp]} ({report.diagnoses[camp] ? `${Math.round(t.count / report.diagnoses[camp] * 100)}%` : "brak danych"})</span></li>)}</ol>
              : <p className="sc-clinic-empty">Brak ocenionych wpisów.</p>}
          </div>
        ))}</div>
      </section>

      <section className="sc-report__panel" aria-labelledby="report-deleted">
        <h2 id="report-deleted" className="sc-report__title">Niedostępne wpisy</h2>
        <p className="sc-report__deleted">{CAMPS.map(camp => <span key={camp}>{CAMP_LABELS[camp]}: <strong>{report.deleted[camp]}</strong></span>)}</p>
        <p className="sc-report__note">Niedostępność wpisu nie oznacza potwierdzonego usunięcia przez autora. Nie pokazujemy treści wpisów. Szczegóły w <Link href="/klinika">Klinice → Niedostępne wpisy</Link>.</p>
      </section>

      {report.interviews.length ? (
        <section className="sc-report__panel" aria-labelledby="report-interviews">
          <h2 id="report-interviews" className="sc-report__title">Wywiady dnia</h2>
          <ul className="sc-report__interviews">{report.interviews.map(row => (
            <li key={row.id}><span>{row.day}</span><strong>{row.guest}</strong> <small>{row.channel}</small> — <Link href={`/klinika/wywiady/${row.id}`}>{row.headline || "Czytaj analizę"} →</Link>
              {row.verdict ? <> <VerdictTag verdict={row.verdict} label={row.verdict === "spin" ? "Spin" : row.verdict === "partial" ? "Częściowy spin" : row.verdict === "no_spin" ? "Bez spinu" : "Nie da się ocenić"} /></> : null}</li>
          ))}</ul>
        </section>
      ) : null}

      {data.archive.length > 1 ? (
        <nav className="sc-report__archive" aria-label="Poprzednie raporty">
          <h2 className="sc-report__title">Poprzednie tygodnie</h2>
          <ul>{data.archive.map(week => (
            <li key={week.week_end}><Link href={`/raport/${week.week_end}`} aria-current={week.week_end === report.week_end ? "page" : undefined}>{weekLabel(week.week_start, week.week_end)}</Link></li>
          ))}</ul>
        </nav>
      ) : null}
    </article>
  );
}
