"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, getClinicPage, spinVar, type SpinCardData } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { NewsletterSignup } from "../NewsletterSignup";
import { ClinicShowcase } from "./ClinicIndicators";
import { ClinicRanking } from "./ClinicRanking";

function DiagnosisCard({ spin }: { spin: SpinCardData }) {
  return <Link className="sc-overview-card sc-overview-diagnosis" href={`/klinika/${spin.id}`}>
    <div className="sc-overview-card__top"><span>{spin.camp_label}</span><span className="sc-overview-score" style={spinVar(spin.intensity)}>Siła spinu <b>{spin.intensity}</b>/100<i className="sc-spin-fill" aria-hidden="true" /></span></div>
    <h3 title={spin.headline}>{spin.headline}</h3>
    <p className="sc-overview-author" title={spin.author.name}>{spin.author.name}</p>
    <p className="sc-overview-excerpt">{spin.summary}</p>
    <div className="sc-overview-card__foot"><time dateTime={spin.post.published_at}>{formatDateTimePl(spin.post.published_at)}</time><span>Czytaj →</span></div>
  </Link>;
}

/** Krótki przegląd oparty wyłącznie na publicznych danych Kliniki. */
export function ClinicOverview({ home = false, extra }: { home?: boolean; extra?: ReactNode }) {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, refetchInterval: 5 * 60_000 });
  const [detailsOpen, setDetailsOpen] = useState(false);
  const data = query.data;
  const diagnoses = data ? CAMPS.flatMap(camp => data.columns[camp]).sort((a, b) => b.post.published_at.localeCompare(a.post.published_at)).slice(0, home ? 4 : 6) : [];
  return <div className="sc-overview">
    <header className="sc-overview-intro">
      <p className="sc-overview-kicker">{home ? "spin.clinic · weryfikacja narracji" : "Klinika · Dr. Spin (AI)"}</p>
      <h1>{home ? "Co dziś mówią politycy?" : "Przekaz pod lupą"}</h1>
      <p>Automatyczne diagnozy wpisów, przekazy dnia i analizy wywiadów. Ta sama miara dla wszystkich obozów.</p>
      <div className="sc-overview-actions"><Link href={home ? "/klinika" : "/klinika/diagnozy"}>{home ? "Przejdź do Kliniki" : "Wszystkie diagnozy"} →</Link><a href="#alerty">Aplikacja i alerty ↓</a></div>
    </header>
    {query.isPending && <div className="sc-overview-state" role="status">Wczytujemy najnowsze analizy…</div>}
    {query.isError && <div className="sc-overview-state" role="alert"><p>Nie udało się pobrać analiz.</p><button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></div>}
    {data && <>
      {data.stats && <section className="sc-overview-metrics" aria-label="Wskaźniki dnia">
        <div className="sc-overview-section-head"><h2>Wskaźniki dnia</h2>{data.generated_at && <time dateTime={data.generated_at}>{formatDatePl(data.generated_at)}</time>}</div>
        <dl>{([["Odczytane wpisy", data.stats.read.today], ["Wstępne oceny", data.stats.screened.today], ["Diagnozy", data.stats.diagnosed.today]] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value.toLocaleString("pl-PL")}</dd></div>)}</dl>
        <p className="sc-overview-metric-note">Wstępna ocena pomaga wybrać wpisy do pełnej diagnozy.</p>
      </section>}
      <section aria-labelledby="overview-messages"><div className="sc-overview-section-head"><h2 id="overview-messages">Przekazy dnia</h2><Link href="/klinika/przekazy">Archiwum →</Link></div>
        <div className="sc-overview-grid">{CAMPS.map(camp => {
          const message = data.messages[camp];
          return <article key={camp} className="sc-overview-card sc-overview-message">
            <div className="sc-overview-card__top"><h3>{CAMP_LABELS[camp]}</h3><span>Dr. Spin (AI)</span></div>
            <p className="sc-overview-excerpt">{message ? message.thesis || message.message : "Nie ma jeszcze opublikowanego przekazu tej strony."}</p>
            <div className="sc-overview-card__foot">{message ? <time dateTime={message.day}>{formatDatePl(message.day)}</time> : <span>Oczekujemy na analizę</span>}<Link href={message ? `/klinika/przekazy/${message.day}` : "/klinika/przekazy"}>{message ? "Czytaj" : "Archiwum"} →</Link></div>
          </article>;
        })}</div>
      </section>
      <section aria-labelledby="overview-latest"><div className="sc-overview-section-head"><h2 id="overview-latest">Najnowsze diagnozy</h2><Link href="/klinika/diagnozy">Wszystkie →</Link></div>
        <p className="sc-overview-note">Siła spinu opisuje perswazję, nie prawdziwość wypowiedzi ani osobę.</p>
        {diagnoses.length ? <div className="sc-overview-grid">{diagnoses.map(spin => <DiagnosisCard key={spin.id} spin={spin} />)}</div> : <p className="sc-overview-empty">Pierwsze diagnozy pojawią się po publikacji analiz.</p>}
      </section>
      {data.interview && <section aria-labelledby="overview-interview"><div className="sc-overview-section-head"><h2 id="overview-interview">Wywiad dnia</h2><Link href="/klinika/wywiady">Archiwum →</Link></div>
        <Link href={`/klinika/wywiady/${data.interview.id}`} className="sc-overview-card sc-overview-interview">
          <h3 title={data.interview.headline || data.interview.title}>{data.interview.headline || data.interview.title}</h3>
          <p className="sc-overview-excerpt">{data.interview.summary}</p>
          <div className="sc-overview-card__foot"><time dateTime={data.interview.day}>{formatDatePl(data.interview.day)}</time><span>Czytaj analizę →</span></div>
        </Link>
      </section>}
      {!home && <details className="sc-overview-details" onToggle={event => setDetailsOpen(event.currentTarget.open)}><summary>Więcej danych i zestawień</summary>{detailsOpen && <div><ClinicShowcase fallback={data.stats} fallbackPeriod={data} fetchedAt={query.dataUpdatedAt} /><ClinicRanking data={data} />{extra}</div>}</details>}
    </>}
    {!home && <nav className="sc-overview-actions" aria-label="Narzędzia Kliniki"><Link href="/klinika/wskazniki">Dane i wykresy →</Link><Link href="/klinika/raporty">Raporty →</Link><Link href="/osoby-publiczne">Osoby publiczne →</Link><Link href="/metodologia">Metodologia →</Link></nav>}
    <section id="alerty" className="sc-overview-alerts"><NewsletterSignup source={home ? "home" : "klinika"} appLaunch /></section>
  </div>;
}
