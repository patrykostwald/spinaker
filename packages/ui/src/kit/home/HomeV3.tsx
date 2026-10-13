"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, getClinicPage } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { GlitchWord } from "../GlitchWord";
import { SpinRow } from "../SpinRow";
import { useWave } from "../useWave";
import { NewsletterSignup } from "../../components/NewsletterSignup";
import { PrzekazDniaCard } from "./PrzekazDniaCard";

const pl = (n: number) => n.toLocaleString("pl-PL");
const PulseIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 12h4l2-5 4 10 2-5h6" /></svg>;

/**
 * Strona główna spin.clinic v3 (prototyp spin-v3, właściciel 13.10.2026): nagłówek „Jak działa przekaz?”,
 * karta Przekaz dnia z prawdziwych danych Kliniki i lista diagnoz w jednym schemacie wiersza.
 * Dane wyłącznie z publicznego `/api/clinic/` - bez fikcji i bez danych demonstracyjnych.
 */
export function HomeV3() {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, refetchInterval: 5 * 60_000 });
  const data = query.data;
  const diagnoses = data ? CAMPS.flatMap(camp => data.columns[camp] ?? []).sort((a, b) => b.post.published_at.localeCompare(a.post.published_at)).slice(0, 7) : [];
  const [rowsRef, wave] = useWave<HTMLOListElement>("in", diagnoses.length);

  return <div className="sc-v3 sc-v3-home">
    <header className="sc-v3-hh">
      <div className="sc-v3-hh__main">
        <p className="sc-v3-hh__k">spin.clinic · Klinika spinu · Dr. Spin (AI)</p>
        <div className="sc-v3-hh__block">
          <h1>Jak działa <GlitchWord word="przekaz" />?</h1>
          <p className="sc-v3-hh__sub">Dr. Spin pokazuje, jak z wpisów polityków powstaje przekaz dnia: co krąży, w jakich wątkach i z jaką siłą perswazji.</p>
          <div className="sc-v3-hh__act">
            <Link className="sc-v3-lnk" href="/klinika">Przejdź do Kliniki <span className="sc-v3-ar" aria-hidden="true">→</span></Link>
            <a className="sc-v3-lnk" href="#alerty">Aplikacja i alerty <span aria-hidden="true">↓</span></a>
          </div>
        </div>
      </div>
      <aside className="sc-v3-hh__stats" aria-label="Skala pracy Kliniki">
        <p>Ta sama miara dla wszystkich</p>
        <dl>
          <div><dt>wpisów przeczytanych</dt><dd>{data?.stats ? pl(data.stats.read.total) : "–"}</dd></div>
          <div><dt>diagnoz</dt><dd>{data?.stats ? pl(data.stats.diagnosed.total) : "–"}</dd></div>
          <div><dt>kont polityków</dt><dd>{data ? pl(data.accounts_count) : "–"}</dd></div>
        </dl>
        <Link className="sc-v3-lnk" href="/metodologia">Metodologia <span className="sc-v3-ar" aria-hidden="true">→</span></Link>
      </aside>
    </header>

    {query.isPending && <div className="sc-v3-state" role="status">Wczytujemy przekaz dnia i najnowsze diagnozy…</div>}
    {query.isError && <div className="sc-v3-state" role="alert"><p>Nie udało się pobrać analiz.</p><button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></div>}

    {data && <>
      <PrzekazDniaCard data={data} />

      <section aria-labelledby="sc-v3-latest">
        <div className="sc-v3-feed-h">
          <h2 id="sc-v3-latest">Najnowsze diagnozy</h2>
          <Link className="sc-v3-lnk" href="/klinika/diagnozy">Wszystkie diagnozy <span className="sc-v3-ar" aria-hidden="true">→</span></Link>
        </div>
        <p className="sc-v3-sub">Liczba po prawej to siła spinu 0⁠-⁠100: zielona do 33, niebieska do 66, czerwona od 67. Opisuje perswazję, nie prawdziwość wypowiedzi ani osobę.</p>
        {diagnoses.length ? <ol className="sc-v3-rows" ref={rowsRef} data-sc-wave={wave}>
          {diagnoses.map((spin, index) => <SpinRow key={spin.id} index={index} href={`/klinika/${spin.id}`} name={spin.author.name}
            icon={<PulseIcon />} kind={<>Diagnoza AI · {spin.verdict_label}</>} title={spin.headline}
            meta={[spin.author.name, <time key="t" dateTime={spin.post.published_at}>{formatDateTimePl(spin.post.published_at)}</time>, `#SPIN-${spin.id}`]}
            value={spin.intensity} />)}
        </ol> : <p className="sc-v3-empty">Pierwsze diagnozy pojawią się po publikacji analiz.</p>}
      </section>

      {data.interview && <section aria-labelledby="sc-v3-interview">
        <div className="sc-v3-feed-h">
          <h2 id="sc-v3-interview">Wywiad dnia</h2>
          <Link className="sc-v3-lnk" href="/klinika/wywiady">Archiwum wywiadów <span className="sc-v3-ar" aria-hidden="true">→</span></Link>
        </div>
        <Link href={`/klinika/wywiady/${data.interview.id}`} className="sc-v3-card" style={{ marginTop: 12 }}>
          <h3>{data.interview.headline || data.interview.title}</h3>
          <p>{data.interview.summary}</p>
          <p className="sc-v3-card__f"><time dateTime={data.interview.day}>{formatDatePl(data.interview.day)}</time><span className="sc-v3-lnk">Czytaj analizę <span className="sc-v3-ar" aria-hidden="true">→</span></span></p>
        </Link>
      </section>}
    </>}

    <section id="alerty" className="sc-v3-alerts" style={{ scrollMarginTop: 24 }}><NewsletterSignup source="home" appLaunch /></section>
  </div>;
}
