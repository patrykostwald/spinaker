"use client";

/**
 * Części Kliniki spinu używane też na stronie głównej: przekaz dnia z powiększeniem (pełna analiza i posty
 * źródłowe), przełącznik „Spin dnia | Najnowszy spin”, wywiad dnia, lista polityków z licznikami
 * i archiwum przekazów dnia. Powiększenia to natywny <dialog> (Esc i kliknięcie tła zamykają).
 */

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { CAMPS, CAMP_LABELS, type Camp, type ClinicAccount, type DailyMessage, type Interview, type InterviewQuote, type SpinDetailData } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { AiTag, IntensityMeter, PartyBadge, VerdictTag } from "./SpinParts";

export function ClinicDialog({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className="sc-clinic-dialog" aria-label={title} onClose={onClose}
      onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="sc-clinic-dialog__body">
        <header className="sc-clinic-dialog__head">
          <h2>{title}</h2>
          <button type="button" className="sc-clinic-dialog__close" onClick={onClose} aria-label="Zamknij">×</button>
        </header>
        {open ? children : null}
      </div>
    </dialog>
  );
}

function Themes({ themes }: { themes: string[] }) {
  return themes.length ? <ul className="sc-spin-techniques" aria-label="Główne hasła">{themes.map(theme => <li key={theme}>{theme}</li>)}</ul> : null;
}

/** Przekaz dnia: skrót w boxie; kliknięcie otwiera pełną analizę i listę postów, z których powstał. */
export function MessageBox({ camp, message, emptyText }: { camp: Camp; message: DailyMessage | null; emptyText?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <article className="sc-clinic-message" data-camp={camp} data-clickable={message ? "" : undefined}>
      <p className="sc-clinic-kicker">Przekaz dnia · {CAMP_LABELS[camp]} <AiTag />{message ? <span className="sc-clinic-message__meta">z {message.posts_count} postów · {formatDatePl(message.day)}</span> : null}</p>
      {message ? <>
        <button type="button" className="sc-clinic-message__open" onClick={() => setOpen(true)} aria-haspopup="dialog">
          <span className="sc-clinic-message__text">{message.message}</span>
        </button>
        <Themes themes={message.themes} />
        <ClinicDialog open={open} onClose={() => setOpen(false)} title={`Przekaz dnia · ${CAMP_LABELS[camp]} · ${formatDatePl(message.day)}`}>
          <p className="sc-clinic-dialog__lead">{message.message}</p>
          {message.analysis ? message.analysis.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>) : null}
          <Themes themes={message.themes} />
          {message.posts?.length ? <>
            <h3>Źródła — posty ({message.posts.length})</h3>
            <ul className="sc-clinic-dialog__posts">{message.posts.map(post => (
              <li key={post.url}>
                <a href={post.url} target="_blank" rel="noopener noreferrer"><strong>{post.author}</strong> @{post.handle} · {formatDateTimePl(post.published_at)} ↗</a>
                <p>{post.text}</p>
              </li>
            ))}</ul>
          </> : null}
          <p className="sc-clinic-dialog__note"><AiTag /> Przekaz przygotował model {message.model || "AI"} z postów z oficjalnych kont. Nikt nie poprawia jego treści.</p>
        </ClinicDialog>
      </> : <p className="sc-clinic-empty">{emptyText ?? "Przekaz dnia pojawi się, gdy posty opublikują co najmniej trzy konta tego obozu."}</p>}
    </article>
  );
}

/** Przełącznik widoku: spin dnia (najwyższa siła z dzisiaj) albo najnowszy spin. */
export function SpinSwitch({ spinOfDay, latest, render, empty }: {
  spinOfDay: SpinDetailData | null; latest: SpinDetailData | null; render: (spin: SpinDetailData) => ReactNode; empty: ReactNode;
}) {
  const [mode, setMode] = useState<"day" | "latest">("day");
  const spin = mode === "day" ? spinOfDay : latest;
  return (
    <div className="sc-spin-switch">
      <div className="sc-spin-switch__tabs" role="tablist" aria-label="Który spin pokazać">
        <button type="button" role="tab" aria-selected={mode === "day"} onClick={() => setMode("day")}>Spin dnia</button>
        <span aria-hidden="true">|</span>
        <button type="button" role="tab" aria-selected={mode === "latest"} onClick={() => setMode("latest")}>Najnowszy spin</button>
      </div>
      {spin ? render(spin) : empty}
    </div>
  );
}

function timeLink(interview: Interview, item: { time: string; seconds: number | null }) {
  return item.seconds !== null && item.seconds !== undefined
    ? <a href={`${interview.url}&t=${item.seconds}s`} target="_blank" rel="noopener noreferrer">{item.time} ↗</a>
    : <span>{item.time}</span>;
}

function QuoteList({ interview, items }: { interview: Interview; items: InterviewQuote[] }) {
  return items.length ? (
    <ul className="sc-clinic-sotd__list">{items.map(item => (
      <li key={item.name + item.quote}><strong>{item.name}</strong> ({timeLink(interview, item)}) — „{item.quote}”. {item.explanation}</li>
    ))}</ul>
  ) : null;
}

/** Wywiad dnia: pasek z miniaturą i tytułem, pod nim Dr. Spin o gościu i o prowadzącym, na dole podsumowanie. */
export function InterviewBox({ interview }: { interview: Interview }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="sc-interview" aria-labelledby={`interview-${interview.id}`}>
      <div className="sc-interview__top">
        <a className="sc-interview__thumb" href={interview.url} target="_blank" rel="noopener noreferrer" aria-label={`Film: ${interview.title}`}>
          {/* eslint-disable-next-line @next/next/no-img-element -- miniatura z YouTube */}
          <img src={interview.thumbnail_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
          <span aria-hidden="true">▶</span>
        </a>
        <div className="sc-interview__head">
          <p className="sc-clinic-kicker">Wywiad dnia <AiTag /><span className="sc-clinic-message__meta">{interview.channel} · {formatDatePl(interview.day)}</span></p>
          <h3 id={`interview-${interview.id}`}><button type="button" onClick={() => setOpen(true)} aria-haspopup="dialog">{interview.headline || interview.title}</button></h3>
          <p className="sc-interview__summary">{interview.summary}</p>
        </div>
      </div>
      <div className="sc-interview__cols">
        <article>
          <p className="sc-interview__who">Gość · {interview.guest_name}{interview.guest_role ? `, ${interview.guest_role}` : ""}</p>
          <p className="sc-spin-card__verdict"><VerdictTag verdict={interview.guest.verdict} label={interview.guest.verdict_label} /><IntensityMeter value={interview.guest.intensity} /></p>
          <p className="sc-interview__text">{interview.guest.summary}</p>
        </article>
        <article>
          <p className="sc-interview__who">Prowadzący · {interview.host_name}</p>
          <p className="sc-interview__text">{interview.host.summary}</p>
        </article>
      </div>
      <p className="sc-interview__overall">{interview.overall}</p>
      <p className="sc-interview__more"><button type="button" onClick={() => setOpen(true)}>Pełna analiza ze źródłami →</button></p>
      <ClinicDialog open={open} onClose={() => setOpen(false)} title={`Wywiad dnia · ${interview.title}`}>
        <p className="sc-clinic-dialog__lead">{interview.headline}</p>
        <p>{interview.overall}</p>
        <h3>Gość · {interview.guest_name}</h3>
        <p className="sc-spin-card__verdict"><VerdictTag verdict={interview.guest.verdict} label={interview.guest.verdict_label} /><IntensityMeter value={interview.guest.intensity} /></p>
        <p>{interview.guest.summary}</p>
        <QuoteList interview={interview} items={interview.guest.techniques} />
        {interview.guest.claims.length ? <>
          <h4>Twierdzenia</h4>
          <ul className="sc-clinic-sotd__list">{interview.guest.claims.map(claim => (
            <li key={claim.claim}><span className="sc-verdict">{claim.assessment_label}</span> <strong>{claim.claim}</strong> ({timeLink(interview, claim)}) {claim.explanation}
              {claim.sources.length ? <span className="sc-interview__sources">{claim.sources.map(source => (
                <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer">{source.title || new URL(source.url).hostname} ↗</a>
              ))}</span> : null}
            </li>
          ))}</ul>
        </> : null}
        <h3>Prowadzący · {interview.host_name}</h3>
        <p>{interview.host.summary}</p>
        <QuoteList interview={interview} items={interview.host.notes} />
        {interview.limitations ? <p className="sc-clinic-sotd__limits">Ograniczenia: {interview.limitations}</p> : null}
        <p className="sc-clinic-dialog__note"><AiTag /> Transkrypcja: Gemini (Google), diagnoza: {interview.model}. Cytaty tylko z transkrypcji, źródła tylko z wyszukiwania. <a href={interview.url} target="_blank" rel="noopener noreferrer">Obejrzyj oryginał ↗</a></p>
      </ClinicDialog>
    </section>
  );
}

const VISIBLE_ROWS = 5;

/** Politycy z licznikami: sprawdzone posty / częściowe spiny / spiny. Pierwsze wiersze, reszta po rozwinięciu. */
export function PoliticiansTable({ accounts }: { accounts: ClinicAccount[] }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <section className="sc-politicians" id="konta" aria-labelledby="politicians-title">
      <header className="sc-politicians__head">
        <h2 id="politicians-title">Politycy w Klinice <span>{accounts.length}</span></h2>
        <p>Tylko oficjalne konta X polityków i partii, potwierdzone rejestrem albo otwartymi danymi. Liczniki: posty sprawdzone przez strażnika · częściowe spiny · spiny.</p>
      </header>
      <div className="sc-politicians__cols">
        {CAMPS.map(camp => {
          const rows = accounts.filter(item => item.camp === camp)
            .sort((a, b) => (b.spins + b.partial_spins) - (a.spins + a.partial_spins) || b.posts_screened - a.posts_screened);
          return (
            <section key={camp}>
              <h3>{CAMP_LABELS[camp]} <span>{rows.length}</span></h3>
              <table>
                <thead><tr><th scope="col">Polityk</th><th scope="col" title="Posty sprawdzone przez strażnika">Posty</th><th scope="col">Częściowe</th><th scope="col">Spiny</th></tr></thead>
                <tbody>{(expanded ? rows : rows.slice(0, VISIBLE_ROWS)).map(item => (
                  <tr key={item.handle}>
                    <td><PartyBadge party={item.party} /> {item.figure_id ? <Link href={`/osoby-publiczne/${item.figure_id}`}>{item.figure_name}</Link> : item.display_name}
                      {" "}<a href={item.url} target="_blank" rel="noopener noreferrer">@{item.handle}</a></td>
                    <td>{item.posts_screened}</td><td>{item.partial_spins}</td><td>{item.spins}</td>
                  </tr>
                ))}</tbody>
              </table>
            </section>
          );
        })}
      </div>
      {accounts.length > VISIBLE_ROWS * 2 ? (
        <p className="sc-politicians__more"><button type="button" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
          {expanded ? "Zwiń listę ↑" : `Pokaż wszystkich (${accounts.length}) ↓`}</button></p>
      ) : null}
    </section>
  );
}

/** Archiwum przekazów dnia: dwie kolumny, od najnowszych w dół; kliknięcie otwiera pełny przekaz. */
export function MessageHistory({ history }: { history: Record<Camp, DailyMessage[]> }) {
  const [open, setOpen] = useState<DailyMessage | null>(null);
  if (!CAMPS.some(camp => history[camp]?.length)) return null;
  return (
    <section className="sc-message-history" aria-labelledby="message-history-title">
      <h2 id="message-history-title">Przekazy dnia — archiwum</h2>
      <div className="sc-message-history__cols">
        {CAMPS.map(camp => (
          <section key={camp}>
            <h3>{CAMP_LABELS[camp]}</h3>
            <ol>{(history[camp] || []).map(message => (
              <li key={message.id ?? message.day}>
                <button type="button" onClick={() => setOpen(message)} aria-haspopup="dialog">
                  <time dateTime={message.day}>{formatDatePl(message.day)}</time>
                  <span>{message.message}</span>
                </button>
              </li>
            ))}</ol>
          </section>
        ))}
      </div>
      <ClinicDialog open={open !== null} onClose={() => setOpen(null)}
        title={open ? `Przekaz dnia · ${CAMP_LABELS[(open.camp || "government") as Camp]} · ${formatDatePl(open.day)}` : ""}>
        {open ? <>
          <p className="sc-clinic-dialog__lead">{open.message}</p>
          {open.analysis ? open.analysis.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>) : null}
          <Themes themes={open.themes} />
        </> : null}
      </ClinicDialog>
    </section>
  );
}
