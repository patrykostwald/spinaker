"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { getClinicInterviews, type Interview, type InterviewQuote } from "../../lib/clinic";
import { formatDatePl, plural } from "../../lib/utils";
import { useDebouncedValue } from "../../lib/useDebouncedValue";
import { rememberClinicVisit } from "../../lib/clinicHistory";
import { initials } from "../../lib/spinScale";
import { PageHeaderV3 } from "../../kit/PageHeaderV3";
import { SpinMeter } from "../../kit/SpinMeter";
import { SpinRow } from "../../kit/SpinRow";
import { Loading } from "../../kit/Loading";
import { ClinicNav } from "./ClinicNav";
import { ClinicDiscussion, DiscussionCounts } from "./ClinicDiscussion";
import { InterviewScope, interviewParticipants } from "./InterviewScanner";
import { Toc } from "./SpinDetailV3";

/**
 * Wywiady v3 (seria 2, 13.10.2026): lista w jednym schemacie wiersza (jak diagnozy) i szczegół z kolumną treści
 * + spisem treści. Bez pasków: siła gościa jako sama liczba w tonie na liście, na szczegółzie liczba + cienka linia.
 * Dane wyłącznie z /api/clinic/interviews/ (bez fikcji).
 */

/** Najstarsze analizy mogły podać siłę w skali 0-10: werdykt „spin” przy sile <= 10 jest sprzeczny - nie pokazujemy liczby (audyt 046). */
export const suspectScale = (part: { verdict?: string | null; intensity?: number | null }) =>
  ["spin", "partial"].includes(part.verdict ?? "") && typeof part.intensity === "number" && part.intensity > 0 && part.intensity <= 10;

/** Liczba do pokazania na liście albo null (brak wyniku albo niepewna skala). */
export function interviewScore(part: { verdict?: string | null; intensity?: number | null }): number | null {
  return typeof part.intensity === "number" && !suspectScale(part) ? part.intensity : null;
}

const MicIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>;
const ExtIcon = () => <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>;
const domain = (url: string) => { try { const u = new URL(url); return /^https?:$/.test(u.protocol) ? u.hostname.replace(/^www\./, "") : ""; } catch { return ""; } };

function timeLink(url: string, item: { time: string; seconds: number | null }): { href: string | null; label: string } | null {
  if (item.seconds == null || !Number.isFinite(item.seconds) || item.seconds < 0) return item.time ? { href: null, label: item.time } : null;
  const s = Math.floor(item.seconds);
  const label = item.time || `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  try { const u = new URL(url); if (!/^https?:$/.test(u.protocol)) return { href: null, label }; u.searchParams.set("t", `${s}s`); return { href: u.toString(), label }; }
  catch { return { href: null, label }; }
}

export function InterviewArchiveV3() {
  const [search, setSearch] = useState("");
  const [channel, setChannel] = useState("");
  const q = useDebouncedValue(search.trim());
  const query = useInfiniteQuery({
    queryKey: ["clinic-interviews", q, channel],
    queryFn: ({ pageParam }) => getClinicInterviews({ page: pageParam, q, channel }),
    initialPageParam: 1,
    getNextPageParam: last => last.next_page ?? undefined,
  });
  const first = query.data?.pages[0];
  const rows = query.data?.pages.flatMap(page => page.results) ?? [];
  const channels = Array.from(new Set([...(first?.channels ?? []), ...(channel ? [channel] : [])]));
  return <section className="sc-v3 sc-v3-page sc-v3-iv">
    <PageHeaderV3 nav={<ClinicNav />} kicker={<><span className="sc-v3-tag" data-tone="accent" title="Wygenerowane z udziałem AI">AI</span> Klinika · Dr. Spin (AI)</>}
      title="Archiwum wywiadów" sub="Analizy gości i prowadzących, z cytatami i odwołaniem do nagrania."
      aside={first ? <dl><div><dt>{q || channel ? plural(first.count, "znaleziony wywiad", "znalezione wywiady", "znalezionych wywiadów") : plural(first.count, "wywiad w archiwum", "wywiady w archiwum", "wywiadów w archiwum")}</dt><dd>{first.count.toLocaleString("pl-PL")}</dd></div></dl> : undefined} />
    <div>
      <form className="sc-v3-filter" role="search" onSubmit={event => event.preventDefault()}>
        <label className="sc-v3-field"><span className="sc-v3-sr">Szukaj gościa, prowadzącego lub tytułu</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          <input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Gość, prowadzący, tytuł" />
        </label>
        <label className="sc-v3-field sc-v3-field--sel"><span className="sc-v3-sr">Kanał</span>
          <select value={channel} onChange={event => setChannel(event.target.value)}>
            <option value="">Każdy kanał</option>
            {channels.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
      </form>
      <p className="sc-v3-sub">Liczba po prawej to siła spinu gościa 0⁠-⁠100: zielona do 33, niebieska do 66, czerwona od 67. Wynik prowadzącego jest w szczegółach.</p>
      {query.isPending ? <p className="sc-v3-state" role="status"><Loading label="Wczytywanie wywiadów" /></p> : null}
      {query.isError ? <div className="sc-v3-state" role="alert"><p>Nie udało się wczytać wywiadów.</p><button type="button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</button></div> : null}
      {first && !rows.length ? <p className="sc-v3-empty">Brak wywiadów spełniających wybrane kryteria.</p> : null}
      {rows.length ? <ol className="sc-v3-rows">{rows.map((iv, index) => {
        const score = interviewScore(iv.guest);
        // 14.10 (właściciel): nad tytułem tylko nazwa źródła - dział "Wywiady" już mówi, że to wywiad; rodzaj zostaje dla czytnika ekranu
        return <SpinRow key={iv.id} index={index} href={`/klinika/wywiady/${iv.id}`} name={iv.guest_name} icon={<MicIcon />}
          kind={iv.channel || " "} kindSr={iv.channel ? `Wywiad, ${iv.channel}` : "Wywiad"} title={iv.headline || "Analiza wywiadu"}
          meta={[`Gość: ${iv.guest_name}${iv.guest_role ? `, ${iv.guest_role}` : ""}`, iv.host_name ? `Prowadzący: ${iv.host_name}` : null, <time key="t" dateTime={iv.day}>{formatDatePl(iv.day)}</time>]}
          value={score} valueLabel={score === null ? <span className="sc-v3-meta sc-v3-iv__none">bez liczby</span> : undefined} />;
      })}</ol> : null}
      {query.hasNextPage ? <p className="sc-v3-more-row"><button className="sc-archive-more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? <Loading inline label="Wczytywanie" /> : "Pokaż więcej"}</button></p> : null}
    </div>
    {/* InterviewScope renderuje <p>: wrapper musi być <div>, inaczej <p> w <p> = błąd hydracji (plakietka "1 error" w dev) */}
    <div className="sc-v3-meta"><InterviewScope /></div>
  </section>;
}

export function InterviewDetailV3({ interview }: { interview: Interview }) {
  const recorded = useRef<number | null>(null);
  useEffect(() => {
    if (recorded.current === interview.id) return;
    recorded.current = interview.id;
    rememberClinicVisit({ type: "interview", id: interview.id, title: interview.headline || interview.title,
      camp: null, verdict: interview.guest.verdict, intensity: interview.guest.intensity, guest: interview.guest_name });
  }, [interview]);
  const people = interviewParticipants(interview);
  const prefix = `iv-${interview.id}`;
  const toc: Array<[string, string]> = [[`${prefix}-nagranie`, "Nagranie"], [`${prefix}-summary`, "Podsumowanie"],
    ...people.map(person => [`${prefix}-${person.id}`, `${person.label}: ${person.name || person.label}`] as [string, string]), [`${prefix}-limits`, "Ograniczenia analizy"]];
  const quote = (item: InterviewQuote, index: number) => {
    const t = timeLink(interview.url, item);
    return <li key={index} className="sc-v3-tech">
      <h4>{item.name}</h4>
      {item.quote ? <q>{item.quote}</q> : null}
      {item.explanation ? <p>{item.explanation}</p> : null}
      {t ? <p className="sc-v3-meta">{t.href ? <a className="sc-v3-inl" href={t.href} target="_blank" rel="noopener noreferrer">Odtwórz od {t.label} <span aria-hidden="true">↗</span></a> : t.label}</p> : null}
    </li>;
  };
  return <article className="sc-v3 sc-v3-page sc-v3-dg sc-v3-ivd">
    <ClinicNav />
    <p className="sc-v3-ctx">
      <Link className="sc-v3-crumb" href="/klinika/wywiady">← Wszystkie wywiady</Link>
      <span className="sc-v3-tag" data-tone="accent" title="Analiza przygotowana przez system AI">AI</span>
      
      <span>Ocena AI, może zawierać błędy</span>
      <Link className="sc-v3-lnk" href="/metodologia">Metoda <span className="sc-v3-ar" aria-hidden="true">→</span></Link>
    </p>
    <div className="sc-v3-dg__grid">
      <div className="sc-v3-dg__main">
        <section id={`${prefix}-nagranie`} className="sc-v3-dg-sec" aria-labelledby={`${prefix}-title`}>
          <p className="sc-v3-dg-k"><span>#WYWIAD-{interview.id}</span><time dateTime={interview.day}>{formatDatePl(interview.day)}</time><span>{interview.channel}</span></p>
          <h1 id={`${prefix}-title`} className="sc-v3-dg-title">{interview.headline || "Analiza wywiadu"}</h1>
          {interview.selection_label ? <p className="sc-v3-meta" style={{ marginTop: 8 }}>{interview.selection_label}</p> : null}
          <a className="sc-v3-ivd__rec" href={interview.url} target="_blank" rel="noopener noreferrer">
            {/* eslint-disable-next-line @next/next/no-img-element -- miniatura nagrania z danych wywiadu */}
            {interview.thumbnail_url ? <img src={interview.thumbnail_url} alt="" loading="lazy" referrerPolicy="no-referrer" /> : <span className="sc-v3-ivd__noimg" aria-hidden="true" />}
            <span className="sc-v3-ivd__rect"><b>{interview.title}</b><span>{interview.channel} · {domain(interview.url) || "nagranie"} <ExtIcon /></span></span>
          </a>
          <p className="sc-v3-ivd__people">
            <span><span className="sc-v3-av" aria-hidden="true">{initials(interview.guest_name)}</span><span>Gość: <b>{interview.guest_name}</b>{interview.guest_role ? `, ${interview.guest_role}` : ""}</span></span>
            {interview.host_name ? <span><span className="sc-v3-av" aria-hidden="true">{initials(interview.host_name)}</span><span>Prowadzący: <b>{interview.host_name}</b></span></span> : null}
          </p>
        </section>

        <section id={`${prefix}-summary`} className="sc-v3-dg-sec sc-v3-prose" aria-labelledby={`${prefix}-sum-h`}>
          <h2 id={`${prefix}-sum-h`}>Podsumowanie wywiadu<small><InterviewScope /></small></h2>
          {interview.summary ? <p>{interview.summary}</p> : null}
          {interview.overall ? <p>{interview.overall}</p> : null}
          <p className="sc-v3-meta"><DiscussionCounts {...interview} /></p>
        </section>

        {people.map(person => {
          const score = interviewScore({ verdict: person.verdict, intensity: person.intensity });
          const host = person.role === "host";
          return <section key={person.id} id={`${prefix}-${person.id}`} className="sc-v3-dg-sec" aria-labelledby={`${prefix}-${person.id}-h`}>
            <h2 id={`${prefix}-${person.id}-h`}>{person.label}: {person.name || person.label}{person.function ? <small>{person.function}</small> : null}</h2>
            <div className="sc-v3-power">
              {score !== null ? <SpinMeter value={score} size="md" label={host ? "Siła spinu w pytaniach prowadzącego" : "Siła spinu gościa"} />
                : <p className="sc-v3-meta">{typeof person.intensity === "number" ? "Siła: skala tej analizy wymaga wyjaśnienia." : "Brak wyniku liczbowego."}</p>}
              {person.verdict_label ? <p className="sc-v3-power__txt"><b>Werdykt AI: {person.verdict_label}.</b> {person.summary}</p> : person.summary ? <p className="sc-v3-power__txt">{person.summary}</p> : null}
            </div>
            <h3 className="sc-v3-ivd__h3">{host ? "Warsztat prowadzącego" : "Techniki"}</h3>
            {person.techniques.length ? <ol className="sc-v3-techs">{person.techniques.map(quote)}</ol> : <p className="sc-v3-empty">Nie wskazano technik w tej analizie.</p>}
            {!host || person.claims.length ? <>
              <h3 className="sc-v3-ivd__h3">Twierdzenia i źródła</h3>
              {person.claims.length ? <ul className="sc-v3-claims">{person.claims.map((claim, index) => {
                const t = timeLink(interview.url, claim);
                const sources = claim.sources.filter(source => domain(source.url));
                return <li key={index}><details>
                  <summary><span className="sc-v3-st" data-assessment={claim.assessment}>{claim.assessment_label}</span><span className="sc-v3-claim__t">{claim.claim}</span>{sources.length ? <span className="sc-v3-claim__n">{sources.length} {sources.length === 1 ? "źródło" : sources.length < 5 ? "źródła" : "źródeł"}</span> : null}</summary>
                  <div className="sc-v3-claim__body">
                    {claim.explanation ? <p>{claim.explanation}</p> : null}
                    {sources.length ? <ul>{sources.map((source, i) => <li key={i}><a className="sc-v3-lnk" href={source.url} target="_blank" rel="noopener noreferrer">{source.title || "Źródło"} · {domain(source.url)} <ExtIcon /></a></li>)}</ul> : null}
                    {t?.href ? <p><a className="sc-v3-inl" href={t.href} target="_blank" rel="noopener noreferrer">Odtwórz od {t.label} <span aria-hidden="true">↗</span></a></p> : null}
                  </div>
                </details></li>;
              })}</ul> : <p className="sc-v3-empty">Brak osobno sprawdzonych twierdzeń.</p>}
            </> : null}
            {person.limitations ? <p className="sc-v3-meta" style={{ marginTop: 12 }}>Ograniczenia: {person.limitations}</p> : null}
          </section>;
        })}

        <section id={`${prefix}-limits`} className="sc-v3-dg-sec" aria-labelledby={`${prefix}-lim-h`}>
          <h2 id={`${prefix}-lim-h`}>Ograniczenia analizy</h2>
          <p className="sc-v3-prose"><span className="sc-v3-ivd__lim">{interview.limitations || "Nie zapisano dodatkowych ograniczeń tej analizy."}</span></p>
          <p className="sc-v3-meta" style={{ marginTop: 12 }}>Ocena konsylium AI · {interview.model} · diagnoza {interview.diagnosed_at ? formatDatePl(interview.diagnosed_at) : "-"}</p>
          <p className="sc-v3-acts"><a className="sc-v3-qbtn" href={`mailto:kontakt@spin.clinic?subject=${encodeURIComponent(`Zgłoszenie błędu w diagnozie WYWIAD-${interview.id}`)}`}>Zgłoś błąd lub sprostowanie</a></p>
        </section>
        <ClinicDiscussion kind="interviews" id={interview.id} />
      </div>
      <Toc items={toc} />
    </div>
  </article>;
}
