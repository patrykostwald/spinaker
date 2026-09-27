"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, DOMAIN } from "../../lib/api";
import { CAMPS, CAMP_LABELS, type Camp, type SpinDetailData, type SpinScale as SpinScaleData, type Verdict } from "../../lib/clinic";
import { measurePost } from "../../lib/xText";
import { xIntentUrl } from "../../lib/xThread";
import { Dialog } from "../Dialog";
import { SpinOfDay } from "./ClinicPage";
import { AiTag, SpinScale, VerdictTag } from "./SpinParts";

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

/** Raport jako wątek na X: podsumowanie z linkiem, techniki obu stron, spin tygodnia, usunięte posty. */
function reportThread(report: Report, url: string): string[] {
  const label = weekLabel(report.week_start, report.week_end);
  const head = `Raport tygodnia Dr. Spina (AI), ${label}:`;
  const posts = [`${head} ${shorten(report.summary || "najważniejsze spiny, techniki i usunięte posty polityków.", 280 - 30 - measurePost(head).weightedLength)} ${url}`];
  const tech = CAMPS.map(camp => `${CAMP_LABELS[camp]}: ${report.techniques[camp].slice(0, 3).map(t => t.name).join(", ") || "brak ocen"}`).join(". ");
  posts.push(shorten(`Najczęstsze techniki w ocenionych postach. ${tech}.`, 270));
  if (report.spin_of_week) {
    const spin = report.spin_of_week;
    posts.push(shorten(`Spin tygodnia: ${spin.author.name} (@${spin.author.handle}) — ${spin.headline} Siła ${spin.intensity}/100. https://${DOMAIN}/klinika/${spin.id}`, 280));
  }
  posts.push(`Usunięte posty polityków w tym tygodniu — rządzący: ${report.deleted.government}, opozycja: ${report.deleted.opposition}. Pełny raport: ${url}`);
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

/** Raport tygodnia Dr. Spina — automatyczne zestawienie z 7 dni: waga spinu, spin tygodnia, techniki, usunięte posty, wywiady. */
export function WeeklyReport({ weekEnd }: { weekEnd?: string }) {
  const query = useQuery({
    queryKey: ["clinic-report", weekEnd ?? "latest"],
    queryFn: () => apiFetch<ReportResponse>(weekEnd ? `/api/clinic/report/${weekEnd}/` : "/api/clinic/report/"),
  });
  const data = query.data;
  if (query.isLoading) return <p className="sc-clinic-empty">Ładowanie raportu…</p>;
  if (!data?.report) return <p className="sc-clinic-empty">Pierwszy raport tygodnia pojawi się w niedzielę wieczorem.</p>;
  const report = data.report;
  return (
    <article className="sc-report">
      <header className="sc-report__head">
        <p className="sc-clinic-kicker">Raport tygodnia <AiTag /></p>
        <h1>Tydzień w spinie: {weekLabel(report.week_start, report.week_end)}</h1>
        {report.summary ? <p className="sc-report__summary">{report.summary}</p> : null}
        <ShareReport report={report} />
      </header>

      <section className="sc-report__panel" aria-label="Waga spinu">
      </section>

      {report.spin_of_week ? (
        <section className="sc-report__panel sc-clinic-sotd" aria-labelledby="report-sotw">
          <h2 id="report-sotw" className="sc-report__title">Spin tygodnia</h2>
          <SpinOfDay spin={report.spin_of_week} />
        </section>
      ) : null}

      <section className="sc-report__panel" aria-labelledby="report-techniques">
        <h2 id="report-techniques" className="sc-report__title">Najczęstsze techniki</h2>
        <div className="sc-report__cols">{CAMPS.map(camp => (
          <div key={camp}>
            <h3>{CAMP_LABELS[camp]} <span>{report.diagnoses[camp]} ocenionych postów</span></h3>
            {report.techniques[camp].length ? <ol>{report.techniques[camp].map(t => <li key={t.name}>{t.name} <span>×{t.count}</span></li>)}</ol>
              : <p className="sc-clinic-empty">Brak ocenionych postów.</p>}
          </div>
        ))}</div>
      </section>

      <section className="sc-report__panel" aria-labelledby="report-deleted">
        <h2 id="report-deleted" className="sc-report__title">Usunięte posty</h2>
        <p className="sc-report__deleted">{CAMPS.map(camp => <span key={camp}>{CAMP_LABELS[camp]}: <strong>{report.deleted[camp]}</strong></span>)}</p>
        <p className="sc-report__note">Bez treści wpisów — zasady X. Szczegóły w <Link href="/klinika">Klinice → Usunięte posty</Link>.</p>
      </section>

      {report.interviews.length ? (
        <section className="sc-report__panel" aria-labelledby="report-interviews">
          <h2 id="report-interviews" className="sc-report__title">Wywiady dnia</h2>
          <ul className="sc-report__interviews">{report.interviews.map(row => (
            <li key={row.id}><span>{row.day}</span><strong>{row.guest}</strong> <small>{row.channel}</small> — {row.headline}
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
