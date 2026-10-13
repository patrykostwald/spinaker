"use client";

import Link from "next/link";
import { useState, type CSSProperties, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, getClinicPage } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { NewsletterSignup } from "../NewsletterSignup";
import { ClinicShowcase } from "./ClinicIndicators";
import { ClinicRanking } from "./ClinicRanking";
import { ClinicNav } from "./ClinicNav";
import { MessageCard } from "./MessageCard";
import { SideLegend } from "../../kit/SideLegend";
import { PageHeaderV3 } from "../../kit/PageHeaderV3";
import { SpinRow } from "../../kit/SpinRow";
import { plural } from "../../kit/home/PrzekazDniaCard";
import { numChars } from "../../kit/home/HomeV3";

const pl = (n: number) => n.toLocaleString("pl-PL");
const PulseIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 12h4l2-5 4 10 2-5h6" /></svg>;
const InfoIcon = () => <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.5" /></svg>;

/**
 * Klinika spinu v3 (prototyp spin-v3/klinika): liczby pracy Kliniki, najnowsze diagnozy w dwóch kolumnach stron
 * (ta sama miara, wspólne wysokości wierszy), przekazy dnia stron jako neutralne karty, wywiad dnia, więcej danych w rozwinięciu.
 */
export function ClinicV3({ extra }: { extra?: ReactNode }) {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, refetchInterval: 5 * 60_000 });
  const [detailsOpen, setDetailsOpen] = useState(false);
  const data = query.data;
  const messageDay = data ? CAMPS.map(camp => data.messages[camp]?.day).filter(Boolean).sort().pop() : undefined;
  return <div className="sc-v3 sc-v3-page sc-v3-clinic">
    <PageHeaderV3 nav={<ClinicNav />} kicker={<>Klinika · Dr. Spin (AI) <span className="sc-v3-tag" data-tone="accent" title="Oceny przygotowane przez system AI">AI</span></>}
      title="Klinika spinu"
      sub="Analizujemy wybrane wpisy i wywiady polityków. Pokazujemy techniki perswazji i źródła. Ta sama miara dla wszystkich obozów."
      actions={<><Link className="sc-v3-lnk" href="/klinika/diagnozy">Wszystkie diagnozy <span className="sc-v3-ar" aria-hidden="true">→</span></Link><a className="sc-v3-lnk" href="#alerty">Aplikacja i alerty <span aria-hidden="true">↓</span></a></>}
      aside={data?.since ? <p className="sc-v3-meta">Od {formatDatePl(data.since)}{data.generated_at ? `, stan na ${formatDateTimePl(data.generated_at)}` : ""}</p> : undefined} />

    {query.isPending && <div className="sc-v3-state" role="status">Wczytujemy najnowsze analizy…</div>}
    {query.isError && <div className="sc-v3-state" role="alert"><p>Nie udało się pobrać analiz.</p><button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></div>}

    {data && <>
      {data.stats && <section aria-label="Liczby pracy Kliniki">
        <ul className="sc-v3-kpi" style={{ "--num-chars": numChars([data.stats.read.total, data.stats.screened.total, data.stats.diagnosed.total, data.accounts_count]) } as CSSProperties}>
          <li><b>{pl(data.stats.read.total)}</b><span>Przeczytanych wpisów</span><small>dziś: {pl(data.stats.read.today)}</small></li>
          <li><b>{pl(data.stats.screened.total)}</b><span>Wstępnie ocenionych</span><small>dziś: {pl(data.stats.screened.today)}</small></li>
          <li><b>{pl(data.stats.diagnosed.total)}</b><span>Diagnoz Dr. Spina</span><small>dziś: {pl(data.stats.diagnosed.today)}</small></li>
          <li><b>{pl(data.accounts_count)}</b><span>Obserwowanych kont</span><small>rządzący i opozycja</small></li>
        </ul>
        <p className="sc-v3-meta" style={{ marginTop: 12 }}>Wstępna ocena pomaga wybrać wpisy do pełnej diagnozy.</p>
      </section>}

      <section aria-labelledby="sc-v3-cl-latest">
        <div className="sc-v3-feed-h"><h2 id="sc-v3-cl-latest">Najnowsze diagnozy</h2><Link className="sc-v3-lnk" href="/klinika/diagnozy">Wszystkie <span className="sc-v3-ar" aria-hidden="true">→</span></Link></div>
        <p className="sc-v3-sub">Obie strony według tych samych zasad. Liczby opublikowanych diagnoz mogą się różnić. Liczba po prawej to siła spinu 0⁠-⁠100: zielona do 33, niebieska do 66, czerwona od 67.</p>
        <div className="sc-v3-sides">
          {CAMPS.map(camp => {
            const rows = (data.columns[camp] ?? []).slice(0, 3);
            const count = data.stats?.by_camp?.[camp]?.diagnosed;
            return <div key={camp} className="sc-v3-side">
              <p className="sc-v3-side__h"><b data-side={camp}><i className="sc-v3-sidedot" aria-hidden="true" />{CAMP_LABELS[camp]}</b>{typeof count === "number" ? <span>{pl(count)} {plural(count, "diagnoza", "diagnozy", "diagnoz")}</span> : null}</p>
              {rows.length ? <ol className="sc-v3-rows">{rows.map((spin, index) => <SpinRow key={spin.id} index={index} href={`/klinika/${spin.id}`} name={spin.author.name}
                icon={<PulseIcon />} kind={<><span className="sc-v3-row__kp">Diagnoza </span>AI · {spin.verdict_label}</>} title={spin.headline}
                meta={[spin.author.name, <time key="t" dateTime={spin.post.published_at}>{formatDateTimePl(spin.post.published_at)}</time>, `#SPIN-${spin.id}`]} value={spin.intensity} />)}</ol>
                : <p className="sc-v3-empty">Brak opublikowanych diagnoz tej strony.</p>}
            </div>;
          })}
        </div>
      </section>

      <section aria-labelledby="sc-v3-cl-msg">
        <div className="sc-v3-feed-h"><h2 id="sc-v3-cl-msg">Przekazy dnia stron</h2><Link className="sc-v3-lnk" href="/klinika/przekazy">Archiwum przekazów <span className="sc-v3-ar" aria-hidden="true">→</span></Link></div>
        <p className="sc-v3-sub">Syntezy wpisów z oficjalnych kont rządzących i opozycji{messageDay ? `, ${formatDatePl(messageDay)}` : ""}.</p>
        <SideLegend className="sc-v3-sideleg--sub" />
        <div className="sc-v3-msgs">{CAMPS.map(camp => <MessageCard key={camp} camp={camp} message={data.messages[camp]} compact emptyText="Nie ma jeszcze opublikowanego przekazu tej strony." />)}</div>
        <p className="sc-v3-note" style={{ marginTop: 16 }}><InfoIcon /><span>Próba wybranych wpisów, nie całej debaty. Nie czytaj liczb jako rankingu.</span></p>
      </section>

      {data.interview && <section aria-labelledby="sc-v3-cl-iv">
        <div className="sc-v3-feed-h"><h2 id="sc-v3-cl-iv">Wywiad dnia</h2><Link className="sc-v3-lnk" href="/klinika/wywiady">Archiwum wywiadów <span className="sc-v3-ar" aria-hidden="true">→</span></Link></div>
        <Link href={`/klinika/wywiady/${data.interview.id}`} className="sc-v3-card" style={{ marginTop: 12 }}>
          <h3>{data.interview.headline || data.interview.title}</h3>
          <p>{data.interview.summary}</p>
          <p className="sc-v3-card__f"><time dateTime={data.interview.day}>{formatDatePl(data.interview.day)}</time><span className="sc-v3-lnk">Czytaj analizę <span className="sc-v3-ar" aria-hidden="true">→</span></span></p>
        </Link>
      </section>}

      <section aria-label="Więcej danych">
        <details className="sc-v3-details sc-v3-more" onToggle={event => setDetailsOpen(event.currentTarget.open)}>
          <summary>Więcej danych i zestawień</summary>
          {detailsOpen && <div className="sc-v3-more__body"><ClinicShowcase fallback={data.stats} fallbackPeriod={data} fetchedAt={query.dataUpdatedAt} /><ClinicRanking data={data} />{extra}</div>}
        </details>
        <nav className="sc-v3-hh__act" aria-label="Narzędzia Kliniki"><Link className="sc-v3-lnk" href="/klinika/wskazniki">Dane i wykresy <span className="sc-v3-ar" aria-hidden="true">→</span></Link><Link className="sc-v3-lnk" href="/klinika/raporty">Raporty <span className="sc-v3-ar" aria-hidden="true">→</span></Link><Link className="sc-v3-lnk" href="/osoby-publiczne">Osoby publiczne <span className="sc-v3-ar" aria-hidden="true">→</span></Link><Link className="sc-v3-lnk" href="/metodologia">Metodologia <span className="sc-v3-ar" aria-hidden="true">→</span></Link></nav>
      </section>
    </>}

    <section id="alerty" className="sc-v3-alerts" style={{ scrollMarginTop: 24 }}><NewsletterSignup source="klinika" appLaunch /></section>
  </div>;
}
