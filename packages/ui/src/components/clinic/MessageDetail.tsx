"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getClinicMessage, CAMPS, CAMP_LABELS, type Camp, type MessageDay } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { SectionHeader } from "../../kit/SectionHeader";
import { ClinicNav } from "./ClinicNav";
import { AiTag } from "./SpinParts";

const CAMP_STORAGE = "sc-message-camp-v1";
export function useMessageCamp() {
  // Pierwsza wizyta: pierwsza zakładka w stałej kolejności serwisu (Rządzący, Opozycja) - pusty ekran nic nie mówi.
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
  return <div className="sc-reader-switch" role="group" aria-label="Strona przekazu">{CAMPS.map(item => <button key={item} type="button" aria-pressed={camp === item} onClick={() => select(item)}>{CAMP_LABELS[item]}</button>)}</div>;
}

export function MessageDetail({ data }: { data: MessageDay }) {
  const { camp, select } = useMessageCamp();
  return <article className="sc-clinic-archives sc-message-detail">
    <ClinicNav />
    <SectionHeader variant="page" title={`Przekazy dnia: ${formatDatePl(data.day)}`}
      kicker={<AiTag />} subtitle="Syntezy wpisów z oficjalnych kont rządzących i opozycji wraz ze źródłami."
      link={<Link href="/klinika/przekazy">Wszystkie przekazy →</Link>} />
    <MessageCampSwitch camp={camp} select={select} />
    <MessageDayContent data={data} camp={camp} />
  </article>;
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
          <dl className="sc-message-detail__meta">
            <div><dt>Dzień przekazu</dt><dd><time dateTime={message.day}>{formatDatePl(message.day)}</time></dd></div>
            <div><dt>Materiał</dt><dd>{message.posts_count} wpisów z kont tej strony</dd></div>
            <div><dt>Zakres publikacji źródeł</dt><dd>{message.scope?.date_from && message.scope.date_to
              ? <>{formatDateTimePl(message.scope.date_from)} – {formatDateTimePl(message.scope.date_to)}</>
              : "Brak zapisanych dat źródeł"}</dd></div>
            {message.created_at ? <div><dt>Przygotowano</dt><dd>{formatDateTimePl(message.created_at)}</dd></div> : null}
            {message.reviewed_at ? <div><dt>Zatwierdzono</dt><dd>{formatDateTimePl(message.reviewed_at)}</dd></div> : null}
            <div><dt>Model</dt><dd>{message.model || "Nie zapisano nazwy modelu"}</dd></div>
          </dl>
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

function MessageSources({ message }: { message: MessageDay["government"] }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const sync = () => setOpen(media.matches);
    sync(); media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  return <aside className="sc-message-detail__feed" aria-label="Źródła przekazu"><details open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Źródła - wpisy ({message?.posts?.length ?? message?.posts_count ?? 0})</summary>
    {message ? <>
          {message.posts?.length ? <ol className="sc-message-detail__sources">{message.posts.map(post => <li key={post.url}>
            <a href={post.url} target="_blank" rel="noopener noreferrer"><strong>{post.author}</strong> @{post.handle} ↗</a>
            <time dateTime={post.published_at}>{formatDateTimePl(post.published_at)}</time>
            {post.available === false ? <p>Wpis jest niedostępny.</p> : <p>{post.text}</p>}
          </li>)}</ol> : <p>{message.posts ? "Brak zapisanych wpisów źródłowych." : "Lista źródeł nie została jeszcze wczytana."}</p>}
    </> : <p>Brak przekazu i źródeł tej strony.</p>}
  </details></aside>;
}
