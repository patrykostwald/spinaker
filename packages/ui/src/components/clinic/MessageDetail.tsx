"use client";

import { Term } from "../../kit/Term";
import { FORMS, plural } from "../../lib/plural";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getClinicMessage, CAMPS, CAMP_LABELS, type Camp, type MessageDay } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { SectionHeader } from "../../kit/SectionHeader";
import { Breadcrumbs } from "../../kit/Breadcrumbs";
import { CampSwitch } from "../../kit/CampSwitch";
import { ClinicNav } from "./ClinicNav";
import { AiTag } from "./SpinParts";
import { AiNotice, EditorialNote } from "./AiNotice";
import { CorrectionForm } from "../CorrectionForm";
import { modelFullName } from "../../lib/models";

const CAMP_STORAGE = "sc-message-camp-v1";
export function useMessageCamp() {
  // Pierwsza wizyta: pierwsza zakładka w stałej kolejności serwisu (Rządzący, Opozycja) — pusty ekran nic nie mówi.
  // Wybór czytelnika zapamiętujemy lokalnie.
  const [camp, setCamp] = useState<Camp | null>("government");
  useEffect(() => {
    try { const saved = localStorage.getItem(CAMP_STORAGE); if (saved === "government" || saved === "opposition") setCamp(saved); } catch { /* Storage may be blocked. */ }
  }, []);
  function select(next: Camp) {
    setCamp(next);
    try { localStorage.setItem(CAMP_STORAGE, next); } catch { /* Selection still works without persistence. */ }
  }
  return { camp, select };
}
export function MessageCampSwitch({ camp, select }: { camp: Camp | null; select: (camp: Camp) => void }) {
  return <CampSwitch value={camp} onChange={select} label="Strona przekazu" />;
}

export function MessageDetail({ data }: { data: MessageDay }) {
  // Dzień pokazuje oba obozy jeden pod drugim (równa ekspozycja, jak na stronie głównej); wybór obozu dotyczy tylko archiwum.
  return <article className="sc-clinic-archives sc-message-detail">
    <ClinicNav />
    <Breadcrumbs items={[{ label: "Główna", href: "/" }, { label: "Klinika", href: "/klinika" }, { label: "Przekazy", href: "/klinika/przekazy" }, { label: formatDatePl(data.day) }]} />
    <SectionHeader variant="page" title={`Przekazy dnia: ${formatDatePl(data.day)}`}
      kicker={<AiTag />} subtitle="Syntezy wpisów z oficjalnych kont rządzących i opozycji wraz ze źródłami."
      link={<Link href="/klinika/przekazy">Wszystkie przekazy →</Link>} />
    <MessageDayNav previous={data.previous_day} next={data.next_day} />
    {CAMPS.map(camp => <MessageDayContent key={camp} data={data} camp={camp} />)}
    <MessageDayNav previous={data.previous_day} next={data.next_day} />
    <EditorialNote />
  </article>;
}

/** Przełącznik dni: wcześniejszy / następny dzień z przekazem i lista wszystkich dni (adres zawsze zawiera datę). */
function MessageDayNav({ previous, next }: { previous?: string | null; next?: string | null }) {
  return <nav className="sc-day-nav" aria-label="Dni przekazów">
    {previous ? <Link className="sc-day-nav__link" href={`/klinika/przekazy/${previous}`} rel="prev">← {formatDatePl(previous)}</Link> : <span className="sc-day-nav__link" aria-disabled="true">Najstarszy dzień w archiwum</span>}
    <Link className="sc-day-nav__all" href="/klinika/przekazy">Lista dni</Link>
    {next ? <Link className="sc-day-nav__link" href={`/klinika/przekazy/${next}`} rel="next">{formatDatePl(next)} →</Link> : <span className="sc-day-nav__link" aria-disabled="true">Najnowszy dzień</span>}
  </nav>;
}

export function MessageDayContent({ data, camp }: { data: MessageDay; camp: Camp | null }) {
  // Archive responses omit posts; reuse the detail endpoint and its day cache.
  const sources = useQuery({ queryKey: ["clinic-message", data.day], queryFn: () => getClinicMessage(data.day), staleTime: 60_000, enabled: Boolean(camp && data[camp] && !data[camp]?.posts) });
  if (!camp) return <p role="status">Wybierz Rządzących lub Opozycję. Obie strony pokazujemy w tym samym układzie; zapamiętamy Twój wybór.</p>;
  return <>
    {[camp].map(camp => {
      const message = sources.data?.[camp] ?? data[camp];
      const anchor = `message-${data.day}-${camp}`;
      return <section key={camp} id={anchor} className="sc-message-detail__camp" aria-labelledby={`${anchor}-title`}>
        <div className="sc-message-detail__narrative">
        <SectionHeader titleId={`${anchor}-title`} title={CAMP_LABELS[camp]} />
        {message ? <>
          <AiNotice models={modelFullName(message.model)} note="To nie jest rozstrzygnięcie redakcji; model może się mylić." publication={message.auto_published ? { mode: "auto", at: message.reviewed_at ?? message.created_at } : message.reviewed_at ? { mode: "manual", at: message.reviewed_at } : null} />
          <p className="sc-message-detail__provenance">Przekaz powstał z {message.posts_count} {message.posts_count === 1 ? "wpisu" : "wpisów"} {camp === "government" ? "obozu rządzącego" : "opozycji"} i jest dziełem jednego modelu, a nie całego Konsylium.{message.auto_published
            ? <> Opublikowano automatycznie{(message.reviewed_at ?? message.created_at) ? <> <time dateTime={(message.reviewed_at ?? message.created_at) as string}>{formatDateTimePl((message.reviewed_at ?? message.created_at) as string)}</time></> : null}; nikt nie poprawia treści.</>
            : message.reviewed_at ? <> <Term id="zatwierdzono">Zatwierdzono ręcznie</Term> <time dateTime={message.reviewed_at}>{formatDateTimePl(message.reviewed_at)}</time>.</> : null}</p>
          {message.id ? <div className="sc-dg-actionbar"><CorrectionForm kind="message" targetId={message.id} type="correction" label="Sprostowanie / odpowiedź" /><CorrectionForm kind="message" targetId={message.id} type="error" label="Zgłoś błąd" /></div> : null}
          <MessageHow message={message} />
          <p className="sc-message-detail__lead">{message.message}</p>
          {message.analysis?.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>)}
          {message.themes.length ? <ul className="sc-spin-techniques" aria-label="Główne hasła">{message.themes.map(theme => <li key={theme}>{theme}</li>)}</ul> : null}
        </> : <p>Brak opublikowanego przekazu tej strony w tym dniu.</p>}
        </div>
        <div className="sc-message-detail__source-column">
        {sources.isFetching ? <p role="status">Wczytywanie źródeł…</p> : null}
        {sources.isError ? <p role="alert">Nie udało się pobrać źródeł. <button type="button" onClick={() => void sources.refetch()}>Spróbuj ponownie</button></p> : null}
        <MessageSources key={`${data.day}-${camp}`} message={message} />
        </div>
      </section>;
    })}
  </>;
}

/** Rozwijane „Jak powstał ten przekaz”: techniczne metadane (model, daty, zakres materiału). Zatwierdzenie zostaje poza nim, widoczne. */
function MessageHow({ message }: { message: NonNullable<MessageDay["government"]> }) {
  const [open, setOpen] = useState(false);
  return <details className="sc-message-detail__how" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary aria-expanded={open}>Jak powstał ten przekaz</summary>
    <dl className="sc-message-detail__meta">
      <div><dt>Model</dt><dd>{message.model ? modelFullName(message.model) : "Nie zapisano nazwy modelu"}</dd></div>
      {message.created_at ? <div><dt>Przygotowano</dt><dd><time dateTime={message.created_at}>{formatDateTimePl(message.created_at)}</time></dd></div> : null}
      <div><dt>Dzień przekazu</dt><dd><time dateTime={message.day}>{formatDatePl(message.day)}</time></dd></div>
      <div><dt>Materiał</dt><dd>{message.posts_count} {plural(message.posts_count, FORMS.entry)} z kont {message.camp === "opposition" ? "opozycji" : message.camp === "government" ? "obozu rządzącego" : "jednego obozu"}</dd></div>
      <div><dt>Zakres publikacji źródeł</dt><dd>{message.scope?.date_from && message.scope.date_to
        ? <>{formatDateTimePl(message.scope.date_from)} – {formatDateTimePl(message.scope.date_to)}</>
        : "Brak zapisanych dat źródeł"}</dd></div>
    </dl>
  </details>;
}

function MessageSources({ message }: { message: MessageDay["government"] }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const sync = () => setOpen(media.matches);
    sync(); media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  return <aside className="sc-message-detail__feed" aria-label="Źródła przekazu"><details open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Źródła — wpisy ({message?.posts?.length ?? message?.posts_count ?? 0})</summary>
    {message ? <>
          {message.posts?.length ? <ol className="sc-message-detail__sources">{message.posts.map(post => <li key={post.url}>
            <a href={post.url} target="_blank" rel="noopener noreferrer"><strong>{post.author}</strong> @{post.handle} ↗</a>
            <time dateTime={post.published_at}>{formatDateTimePl(post.published_at)}</time>
            {post.available === false ? <p>Wpis jest niedostępny.</p> : <p>{post.text}</p>}
          </li>)}</ol> : <p>{message.posts ? "Brak zapisanych wpisów źródłowych." : "Lista źródeł nie została jeszcze wczytana."}</p>}
    </> : <p>Brak przekazu i źródeł tej strony.</p>}
  </details></aside>;
}
