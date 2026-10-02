"use client";

/**
 * Części Kliniki spinu używane też na stronie głównej: przekaz dnia z powiększeniem (pełna analiza i wpisy
 * źródłowe), przełącznik „Spin dnia | Najnowszy spin”, wywiad dnia, lista polityków z licznikami
 * i archiwum przekazów dnia. Powiększenia to natywny <dialog> (Esc i kliknięcie tła zamykają).
 */

import { Button } from "../../kit/Button";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { CAMPS, CAMP_LABELS, type Camp, type ClinicAccount, type DailyMessage, type Interview, type InterviewQuote, type SpinDetailData } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { AiTag, IntensityMeter, VerdictTag } from "./SpinParts";

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

/** Przekaz dnia: skrót w boxie i trwały link do pełnej analizy ze źródłami. */
export function MessageBox({ camp, message, emptyText, surface = "standalone" }: { camp: Camp; message: DailyMessage | null; emptyText?: string; surface?: "standalone" | "nested" }) {
  return (
    <article className="sc-clinic-message" data-surface={surface} data-camp={camp} data-clickable={message ? "" : undefined}>
      <p className="sc-clinic-kicker"><span>Przekaz dnia · {CAMP_LABELS[camp]}</span><AiTag /></p>
      {message ? <>
        <p className="sc-clinic-message__text">{message.message}</p>
        <Themes themes={message.themes} />
        <Button variant="link" href={`/klinika/przekazy/${message.day}#${camp === "government" ? "rzadzacy" : "opozycja"}`}>Czytaj przekaz i zobacz źródła →</Button>
        <footer className="sc-clinic-message__foot"><time dateTime={message.day}>{formatDatePl(message.day)}</time><span>Źródła: {message.posts_count} wpisów</span></footer>
      </> : <p className="sc-clinic-empty">{emptyText ?? "Przekaz dnia pojawi się, gdy wpisy opublikują co najmniej trzy konta tego obozu."}</p>}
    </article>
  );
}

/** Przełącznik widoku: spin dnia (najwyższa siła z dzisiaj) albo najnowszy spin. */
export function SpinSwitch({ spinOfDay, latest, render, empty, left, right }: {
  spinOfDay: SpinDetailData | null; latest: SpinDetailData | null; render: (spin: SpinDetailData) => ReactNode; empty: ReactNode;
  /** Opcjonalnie: tytuł po lewej i link po prawej - w jednej linii z zakładkami. */
  left?: ReactNode; right?: ReactNode;
}) {
  const [mode, setMode] = useState<"day" | "latest">("latest");
  const spin = mode === "day" ? spinOfDay : latest;
  const day = spinOfDay ? formatDatePl(spinOfDay.post.published_at) : null;
  const tabs = (
    <div className="sc-scan-s-tabs sc-spin-switch__tabs2" role="group" aria-label="Którą diagnozę pokazać">
      <button type="button" aria-pressed={mode === "latest"} onClick={() => setMode("latest")}>Najnowsza</button>
      <button type="button" aria-pressed={mode === "day"} disabled={!day} onClick={() => setMode("day")}>Najwyższa siła spinu{day ? ` ${day}` : " - brak danych"}</button>
    </div>
  );
  return (
    <div className="sc-spin-switch">
      {left || right ? <div className="sc-spin-switch__bar"><div>{left}</div>{tabs}<div className="sc-spin-switch__right">{right}</div></div> : tabs}
      <p className="sc-spin-switch__rule">{mode === "day" ? `Najwyższa siła spinu wśród przeanalizowanych wpisów obu stron z ${day}.` : "Ostatnia opublikowana diagnoza, niezależnie od strony."}</p>
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
      <li key={item.name + item.quote}><strong>{item.name}</strong> ({timeLink(interview, item)}) - „{item.quote}”. {item.explanation}</li>
    ))}</ul>
  ) : null;
}

/** Wywiad dnia: pasek z miniaturą i tytułem, pod nim Dr. Spin o gościu i o prowadzącym, na dole podsumowanie. */
export function InterviewBox({ interview, open: openProp, onOpenChange, hideMore, archive = [], kicker = "Wywiady" }: {
  interview: Interview;
  /** Napis nad tytułem sekcji (domyślnie „Wywiady”). */
  kicker?: string;
  /** Wcześniejsze wywiady - paski z datą po lewej, pod aktualnym wywiadem (ten sam panel). */
  archive?: Interview[];
  /** Opcjonalnie: okno analizy sterowane z zewnątrz (np. link w nagłówku sekcji na głównej). */
  open?: boolean; onOpenChange?: (open: boolean) => void; hideMore?: boolean;
}) {
  const [openState, setOpenState] = useState(false);
  const open = openProp ?? openState;
  const setOpen = onOpenChange ?? setOpenState;
  return (
    <section className="sc-interview" aria-labelledby={`interview-${interview.id}`}>
      <div className="sc-interview__top">
        <div className="sc-interview__media">
        <a className="sc-interview__thumb" href={interview.url} target="_blank" rel="noopener noreferrer" aria-label={`Film: ${interview.title}`}>
          {/* eslint-disable-next-line @next/next/no-img-element -- miniatura z YouTube */}
          <img src={interview.thumbnail_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
          <span aria-hidden="true">▶</span>
        </a>
        {/* „Pełna analiza” tuż pod miniaturą, przy lewej krawędzi - bez osobnej linii na dole boxu. */}
        {hideMore ? null : <p className="sc-interview__more"><button type="button" onClick={() => setOpen(true)}>Pełna analiza ze źródłami →</button></p>}
        </div>
        <div className="sc-interview__head">
          <p className="sc-clinic-kicker">{kicker} <AiTag /><span className="sc-clinic-message__meta">{interview.channel} · {formatDatePl(interview.day)}</span></p>
          <h3 id={`interview-${interview.id}`}><button type="button" onClick={() => setOpen(true)} aria-haspopup="dialog">{interview.headline || interview.title}</button></h3>
          <p className="sc-interview__summary">{interview.summary}</p>
          {interview.overall ? <p className="sc-interview__lede">{interview.overall}</p> : null}
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
          {/* Werdykt prowadzącego w tym samym wierszu co gościa - teksty obu kart zaczynają się na jednej wysokości. */}
          <p className="sc-spin-card__verdict">{interview.host.verdict
            ? <><VerdictTag verdict={interview.host.verdict} label={interview.host.verdict_label ?? ""} /><IntensityMeter value={interview.host.intensity ?? 0} /></>
            : <span className="sc-interview__noverdict">ocena warsztatu od kolejnych wywiadów</span>}</p>
          <p className="sc-interview__text">{interview.host.summary}</p>
        </article>
      </div>
      <p className="sc-interview__more"><Link href={`/klinika/wywiady/${interview.id}`}>Czytaj analizę →</Link>{" · "}<Link href="/klinika/wywiady">Archiwum wywiadów →</Link></p>
      {archive.length ? <InterviewArchive items={archive} /> : null}
      <ClinicDialog open={open} onClose={() => setOpen(false)} title={`Wywiad · ${interview.title}`}>
        <InterviewAnalysis interview={interview} />
      </ClinicDialog>
    </section>
  );
}

/** Etykieta werdyktu w archiwum wywiadów dopiero od tej siły (niżej - pojedyncze, słabe techniki). */
const ARCHIVE_TAG_MIN = 40;

/** Archiwum wywiadów dnia: jeden pasek na dzień - data po lewej, gość, nagłówek, werdykt; klik otwiera analizę. */
export function InterviewArchive({ items }: { items: Interview[] }) {
  const [openId, setOpenId] = useState<number | null>(null);
  const current = items.find(item => item.id === openId) ?? null;
  return (
    <div className="sc-interview-archive">
      <h4 className="sc-interview-archive__title">Wcześniejsze wywiady</h4>
      <ul>{items.map(item => (
        <li key={item.id}>
          <button type="button" className="sc-interview-archive__row" onClick={() => setOpenId(item.id)} aria-haspopup="dialog">
            <time dateTime={item.day}>{formatDatePl(item.day)}</time>
            <span className="sc-interview-archive__who">{item.guest_name}<small>{item.channel}</small></span>
            {/* Licznik siły zawsze; etykieta werdyktu dopiero od progu - przy 6/100 „Spin” sugerowałby więcej, niż stwierdzono. */}
            <span className="sc-interview-archive__score">
              <IntensityMeter value={item.guest.intensity} />
              {item.guest.intensity >= ARCHIVE_TAG_MIN ? <VerdictTag verdict={item.guest.verdict} label={item.guest.verdict_label} /> : null}
            </span>
            <span className="sc-interview-archive__headline">{item.headline || item.title}</span>
          </button>
        </li>
      ))}</ul>
      <ClinicDialog open={current !== null} onClose={() => setOpenId(null)} title={current ? `Wywiad · ${current.title}` : ""}>
        {current ? <InterviewAnalysis interview={current} /> : null}
      </ClinicDialog>
    </div>
  );
}

/** Pełna analiza wywiadu (okno): gość z technikami i twierdzeniami, prowadzący, ograniczenia. */
export function InterviewAnalysis({ interview }: { interview: Interview }) {
  return (
    <>
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
        {interview.host.verdict ? <p className="sc-spin-card__verdict"><VerdictTag verdict={interview.host.verdict} label={interview.host.verdict_label ?? ""} /><IntensityMeter value={interview.host.intensity ?? 0} /></p> : null}
        <p>{interview.host.summary}</p>
        <QuoteList interview={interview} items={interview.host.notes} />
        {interview.limitations ? <p className="sc-clinic-sotd__limits">Ograniczenia: {interview.limitations}</p> : null}
        <p className="sc-clinic-dialog__note"><AiTag /> Transkrypcja: Gemini (Google), diagnoza: {interview.model}. Cytaty tylko z transkrypcji, źródła tylko z wyszukiwania. <a href={interview.url} target="_blank" rel="noopener noreferrer">Obejrzyj oryginał ↗</a></p>
    </>
  );
}

const VISIBLE_ROWS = 5;

/** Politycy z licznikami: sprawdzone wpisy / częściowe spiny / spiny. Pierwsze wiersze, reszta po rozwinięciu. */
export function PoliticiansTable({ accounts }: { accounts: ClinicAccount[] }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <section className="sc-politicians" id="konta" aria-labelledby="politicians-title">
      <header className="sc-politicians__head">
        <h2 id="politicians-title">Politycy w Klinice <span>{accounts.length}</span></h2>
        <p>Tylko oficjalne konta X polityków i partii, potwierdzone rejestrem albo otwartymi danymi. Liczniki: wpisy sprawdzone przez strażnika · częściowe spiny · spiny.</p>
      </header>
      <div className="sc-politicians__cols">
        {CAMPS.map(camp => {
          const rows = accounts.filter(item => item.camp === camp)
            .sort((a, b) => (b.spins + b.partial_spins) - (a.spins + a.partial_spins) || b.posts_screened - a.posts_screened);
          if (!rows.length) return null;
          return (
            <section key={camp}>
              <h3>{CAMP_LABELS[camp]} <span>{rows.length}</span></h3>
              <table className="sc-ind-table">
                <thead><tr><th scope="col">Polityk</th><th scope="col" title="Wstępnie ocenione wpisy">Wstępnie ocenione wpisy</th><th scope="col">Częściowe</th><th scope="col">Spiny</th></tr></thead>
                <tbody>{(expanded ? rows : rows.slice(0, VISIBLE_ROWS)).map(item => (
                  <tr key={item.handle}>
                    <td>{item.figure_id ? <Link href={`/osoby-publiczne/${item.figure_id}`}>{item.figure_name}</Link> : item.display_name}{item.party?.short ? `, ${item.party.short}` : ""}
                      {" "}<a href={item.url} target="_blank" rel="noopener noreferrer">@{item.handle}</a></td>
                    <td>{item.posts_screened}</td><td>{item.partial_spins}</td><td>{item.spins}</td>
                  </tr>
                ))}</tbody>
              </table>
            </section>
          );
        })}
      </div>
      {CAMPS.some(camp => accounts.filter(item => item.camp === camp).length > VISIBLE_ROWS) ? (
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
      <h2 id="message-history-title">Przekazy dnia - archiwum</h2>
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
