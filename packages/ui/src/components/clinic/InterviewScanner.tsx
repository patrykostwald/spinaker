"use client";

import { techniqueLabel } from "../../lib/clinic";

import Link from "next/link";
import { useRef, useState } from "react";
import type { Interview, InterviewQuote } from "../../lib/clinic";
import { diagnosisPresentation } from "../../lib/diagnosisPresentation";
import { formatDatePl } from "../../lib/utils";
import { VerdictTag } from "./SpinParts";

const firstSentence = (text: string) => text.match(/^.*?[.!?](?=\s|$)/s)?.[0] ?? text;
function domain(url: string) {
  try { const parsed = new URL(url); return /^https?:$/.test(parsed.protocol) ? parsed.hostname.replace(/^www\./, "") : ""; }
  catch { return ""; }
}

function RecordingTime({ url, item, expanded }: { url: string; item: { time: string; seconds: number | null }; expanded: boolean }) {
  if (item.seconds == null || !Number.isFinite(item.seconds) || item.seconds < 0) return item.time ? <span>{item.time}</span> : null;
  const seconds = Math.floor(item.seconds);
  const timestamp = item.time || `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  let target: URL;
  try { target = new URL(url); }
  catch { return <span>{timestamp}</span>; }
  if (!/^https?:$/.test(target.protocol)) return <span>{timestamp}</span>;
  target.searchParams.set("t", `${seconds}s`);
  return <a tabIndex={expanded ? 0 : -1} href={target.toString()} target="_blank" rel="noopener noreferrer" aria-label={`Odtwórz od ${timestamp}`}>{timestamp} ↗</a>;
}

export function InterviewScope() {
  return <p className="sc-interview-scope">Analiza transkrypcji: u gościa badamy techniki perswazji, u prowadzącego — sposób zadawania pytań i reakcje na odpowiedzi.</p>;
}

function ResultBar({ value }: { value: number }) {
  return <div className="sc-scan-g"><span className="sc-scan-g-track"><i style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></span><span className="sc-scan-g-scale"><b>0</b><b>50</b><b>100</b></span></div>;
}

const suspectScale = (part: { verdict: string; intensity: number }) => ["spin", "partial"].includes(part.verdict) && part.intensity > 0 && part.intensity <= 10;

/** Wynik gościa i prowadzącego w układzie panelu skanera: etykieta, werdykt, duża liczba, pasek 0–100. */
export function InterviewResults({ interview }: { interview: Interview }) {
  const { guest, host } = interview;
  return <div className="sc-interview-results">
    <section>
      <p className="sc-scan-m-lbl">Gość · siła spinu</p>
      <p className="sc-interview-results__who">{interview.guest_name}{interview.guest_role ? <span>, {interview.guest_role}</span> : null}</p>
      {/* Najstarsze analizy mogły podać siłę w skali 0–10: werdykt „spin” przy sile ≤ 10 jest sprzeczny — nie pokazujemy mylącej liczby (audyt 046) */}
      {suspectScale(guest) ? <div className="sc-interview-results__score"><p className="sc-interview-results__none">Siła: skala tej analizy wymaga wyjaśnienia</p><VerdictTag verdict={guest.verdict} label={guest.verdict_label} /></div> : <>
      <div className="sc-interview-results__score"><p className="sc-scan-m-num sc-scan-strength">{guest.intensity}<small>/100</small></p><VerdictTag verdict={guest.verdict} label={guest.verdict_label} /></div>
      <ResultBar value={guest.intensity} /></>}
    </section>
    <section>
      <p className="sc-scan-m-lbl">Prowadzący · siła spinu w pytaniach</p>
      <p className="sc-interview-results__who">{interview.host_name || "Prowadzący"}</p>
      <div className="sc-interview-results__score">{host.intensity == null ? <p className="sc-interview-results__none">Brak wyniku liczbowego</p> : <p className="sc-scan-m-num">{host.intensity}<small>/100</small></p>}
        {host.verdict ? <VerdictTag verdict={host.verdict} label={host.verdict_label ?? ""} /> : null}</div>
      {host.intensity == null ? null : <ResultBar value={host.intensity} />}
    </section>
  </div>;
}

/** `full` — własna strona wywiadu: jeden tytuł (H1 strony), uzasadnienie od razu otwarte, bez odsyłacza do samej siebie (audyt 046). */
export function InterviewScanner({ interview, full = false }: { interview: Interview; full?: boolean }) {
  const [expanded, setExpanded] = useState(full);
  const [sharing, setSharing] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");
  const expandRef = useRef<HTMLButtonElement>(null);
  const cardRef = useRef<HTMLElement>(null);
  const { guest, host } = interview;
  const { techniques, families, familyMax, typeCount, checked, claims, claimSquares } = diagnosisPresentation(guest);
  const path = `/klinika/wywiady/${interview.id}`;
  const shareText = `Dr. Spin (AI) · Wywiad z ${interview.guest_name} · ${guest.verdict_label} ${guest.intensity}/100\n${interview.headline}\nhttps://spin.clinic${path}`;
  const prefix = `interview-scan-${interview.id}`;
  function collapse() {
    setExpanded(false);
    expandRef.current?.focus({ preventScroll: true });
    if (cardRef.current && cardRef.current.getBoundingClientRect().top < 0) cardRef.current.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }
  async function copy() {
    try { await navigator.clipboard.writeText(shareText); setCopyStatus("Skopiowano"); }
    catch { setCopyStatus("Nie udało się skopiować. Zaznacz tekst i skopiuj ręcznie."); }
  }
  function quote(item: InterviewQuote, index: number) {
    return <div className="sc-scan-t-item" key={index}><strong>{item.name}</strong>{item.quote ? <q>{item.quote}</q> : null}<span>{item.explanation}</span><RecordingTime url={interview.url} item={item} expanded={expanded} /></div>;
  }
  return <article ref={cardRef} className="sc-scan-card sc-interview-scan" data-expanded={expanded || undefined} aria-labelledby={`${prefix}-lead`} onClick={event => {
    if (!(event.target as HTMLElement).closest("a,button,textarea,input,select,label,details") && !window.getSelection()?.toString()) setExpanded(true);
  }}>
    <div className="sc-scan-p">
      <div className="sc-scan-p-inner">
        <p className="sc-clinic-kicker">Nagranie wywiadu</p>
        <a className="sc-interview-scan-media" href={interview.url} target="_blank" rel="noopener noreferrer" aria-label={`Odtwórz film: ${interview.title}`}>
          {/* Miniatura nagrania pochodzi z danych wywiadu. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {interview.thumbnail_url ? <img src={interview.thumbnail_url} alt="" referrerPolicy="no-referrer" /> : null}<span aria-hidden="true">▶</span>
        </a>
        <p className="sc-interview-recording-label">Tytuł nagrania</p><h3 className="sc-scan-p-name">{interview.title}</h3>
        <p>Gość: {interview.guest_name}{interview.guest_role ? `, ${interview.guest_role}` : ""}</p>
        <p>Prowadzący: {interview.host_name}</p>
        <div className="sc-interview-scan-meta"><time dateTime={interview.day}>{formatDatePl(interview.day)}</time><a href={interview.url} target="_blank" rel="noopener noreferrer">{interview.channel} ↗</a></div>
      </div>
    </div>
    <div className="sc-scan-dg">
      <header className="sc-scan-dg-head"><span className="sc-scan-dg-ai">OCENA KONSYLIUM AI</span><span className="sc-scan-dg-id">#WYWIAD-{interview.id} · diagnoza {interview.diagnosed_at ? formatDatePl(interview.diagnosed_at) : "—"}</span></header>
      {expanded ? <p className="sc-scan-dg-who">Wywiad: <strong>{interview.guest_name}</strong> · {formatDatePl(interview.day)} · <a href={interview.url} target="_blank" rel="noopener noreferrer">{interview.channel} ↗</a></p> : null}
      {full ? <span id={`${prefix}-lead`} hidden>{interview.headline}</span> : <h3 className="sc-scan-dg-lead" id={`${prefix}-lead`}>{interview.headline}</h3>}
      <InterviewScope />
      <InterviewResults interview={interview} />
      <p className="sc-archive-interview-summary">{interview.summary}</p>
      <footer className="sc-scan-dg-foot"><a className="sc-scan-dg-report" href={`mailto:kontakt@spin.clinic?subject=${encodeURIComponent(`Zgłoszenie błędu w diagnozie WYWIAD-${interview.id}`)}`}>Zgłoś błąd</a><div className="sc-scan-dg-actions">
        <button ref={expandRef} type="button" aria-expanded={expanded} aria-controls={`${prefix}-details`} onClick={() => expanded ? collapse() : setExpanded(true)}>{expanded ? "Zwiń uzasadnienie" : "Pokaż uzasadnienie"}</button>
        <button type="button" aria-expanded={sharing} aria-controls={`${prefix}-share`} onClick={() => setSharing(!sharing)}>Udostępnij</button>{full ? null : <Link className="sc-scan-button sc-scan-primary" href={path}>Pełna analiza →</Link>}
      </div></footer>
      <div className="sc-scan-expand" data-open={expanded}><div><section id={`${prefix}-details`} className="sc-scan-details" aria-label="Uzasadnienie" aria-hidden={!expanded}>
      <div className="sc-scan-m">
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl" title="Liczymy zapisane pozycje analizy, bez scalania podobnych twierdzeń">Twierdzenia</p><p className="sc-scan-m-num">{checked}<small> sprawdzone</small></p>
          <div className="sc-scan-g"><span className="sc-scan-g-squares" aria-hidden="true">{claimSquares.map((kind, index) => <i key={index} data-k={kind} />)}</span><span className="sc-scan-g-legend">{claims.map(claim => claim.count ? <span key={claim.key} data-k={claim.kind}>{claim.count} {claim.label}</span> : null)}</span></div>
        </div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Techniki</p><p className="sc-scan-m-num">{typeCount}<small> {techniqueLabel(typeCount)}</small></p><div className="sc-scan-g">{families.map(({ key, label, count }) => <span key={key} className="sc-scan-g-row sc-scan-g-fam" data-family={key}><em>{label.split(" ")[0]}</em><span className="sc-scan-g-track sc-scan-g-thin"><i style={{ width: `${count / familyMax * 100}%` }} /></span><b>{count}</b></span>)}</div></div>
      </div>
      <table className="sc-scan-t"><thead><tr><th>Rodzina technik</th><th>Techniki w analizowanym materiale</th><th className="sc-scan-t-n">Typy</th></tr></thead><tbody>{families.map(({ key, label, count, types }) => <tr key={key} data-family={key}><th scope="row"><i />{label}</th><td>{types.map(item => item.label).join(" · ") || <span className="sc-scan-t-none">Nie wskazano</span>}</td><td className="sc-scan-t-n">{count}</td></tr>)}</tbody></table>
        <div className="sc-scan-details-grid">
          <div className="sc-scan-details-col"><h4>Techniki gościa według rodzin</h4>{families.map(({ key, label, count }) => <div className="sc-scan-fam" data-family={key} key={key}><p className="sc-scan-fam-head"><i />{label}<b>{count}</b></p>{techniques.some(item => item.family === key) ? guest.techniques.filter((_, index) => techniques[index].family === key).map(quote) : <p className="sc-scan-t-none">Nie wskazano</p>}</div>)}</div>
          <div className="sc-scan-details-col"><h4>Twierdzenia i dowody</h4>{guest.claims.length ? <ul className="sc-scan-cl">{guest.claims.map((claim, index) => <li key={index}><span className="sc-scan-assessment" data-assessment={claim.assessment}>{claim.assessment_label}</span><q>{claim.claim}</q><p>{firstSentence(claim.explanation)}</p><div className="sc-scan-cl-src">{claim.sources.filter(source => domain(source.url)).map((source, index) => <a key={index} tabIndex={expanded ? 0 : -1} href={source.url} target="_blank" rel="noopener noreferrer">{domain(source.url)}</a>)}<RecordingTime url={interview.url} item={claim} expanded={expanded} /></div></li>)}</ul> : <p>Brak osobno sprawdzonych twierdzeń.</p>}</div>
        </div>
        <section className="sc-scan-details-col"><h4>Warsztat prowadzącego</h4><p>{host.summary}</p>{host.notes.map(quote)}</section>
        {interview.limitations ? <p>Ograniczenia: {interview.limitations}</p> : null}
        <button type="button" tabIndex={expanded ? 0 : -1} onClick={collapse}>Zwiń uzasadnienie</button>
      </section></div></div>
    </div>
    {sharing ? <div id={`${prefix}-share`} className="sc-scan-share"><section className="sc-scan-sh sc-scan-sh-text" aria-label="Udostępnij wywiad"><label htmlFor={`${prefix}-text`}>Tekst z linkiem</label><textarea id={`${prefix}-text`} value={shareText} readOnly rows={5} /><button type="button" onClick={() => void copy()}>Kopiuj</button><span role="status">{copyStatus}</span></section></div> : null}
  </article>;
}
