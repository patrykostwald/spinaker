"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CAMP_LABELS, getClinicMessage, type Camp, type DailyMessage, type MessageStats } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { Loading } from "../../kit/Loading";

import { ClinicDiscussion, DiscussionCounts } from "./ClinicDiscussion";

const TONES = [["atak", "Atak"], ["osiagniecie", "Osiągnięcia"], ["apel", "Apel"], ["inne", "Inne"]] as const;

/**
 * Liczby przekazu strony (v3, właściciel 13.10): Wpisy, Konkret i Spójność jako same liczby z podpisem;
 * rozkład tonu jako czysta lista (nazwa i procent, największa wartość pogrubiona), BEZ pasków i bez kolorów
 * (kolor w serwisie oznacza wyłącznie siłę spinu), wiersze rozdzielone jedną cienką linią.
 */
export function MessageMetrics({ stats }: { stats?: MessageStats }) {
  const known = stats?.version === 1;
  const tone = known ? stats.tone : null;
  const max = tone ? Math.max(...TONES.map(([key]) => tone[key])) : -1;
  return <div className="sc-v3-msg__measures">
    {/* bez danych: kreska zamiast liczby, układ ten sam co z liczbami (właściciel 4.10) */}
    <dl className="sc-v3-m3" data-empty={known ? undefined : ""}>
      <div><dt>Wpisy</dt><dd><b>{known ? stats.posts : "–"}</b><small>autorów: {known ? stats.authors : "–"}</small></dd></div>
      <div title="Odsetek wpisów z liczbą lub linkiem. Nie oznacza potwierdzenia ich prawdziwości."><dt>Konkret</dt><dd><b>{known ? `${stats.concrete_pct}%` : "–"}</b><small>liczba lub link</small></dd></div>
      <div title="Autorzy wpisów przypisanych do głównego wątku dnia."><dt>Spójność</dt><dd><b>{known && stats.coherence_authors !== null ? `${stats.coherence_authors} z ${stats.authors}` : "–"}</b><small>autorów</small></dd></div>
    </dl>
    <div className="sc-v3-tone">
      <p className="sc-v3-tone__h">Ton wpisów <span>(przypisanie AI)</span></p>
      <ul aria-label="Ton wpisów" data-empty={tone ? undefined : ""}>
        {TONES.map(([key, label]) => {
          const value = tone ? tone[key] : 0;
          return <li key={key} data-max={tone && value === max && value > 0 ? "" : undefined}><span>{label}</span><b>{tone ? `${value.toLocaleString("pl-PL", { maximumFractionDigits: 1 })}%` : "–"}</b></li>;
        })}
      </ul>
    </div>
  </div>;
}

export function MessageCard({ camp, message, day, compact = false, emptyText }: {
  camp: Camp; message: DailyMessage | null; day?: string; compact?: boolean; emptyText?: string;
}) {
  const [open, setOpen] = useState(false);
  const date = message?.day ?? day;
  const sources = useQuery({ queryKey: ["clinic-message", date], queryFn: () => getClinicMessage(date!),
    staleTime: 60_000, enabled: Boolean(open && message && (!message.posts || message.posts.length < message.posts_count) && date) });
  const full = sources.data?.[camp] ?? message;
  const structured = Boolean(message?.thesis?.trim() && message.points && message.points.length >= 2);
  return <article className="sc-v3 sc-v3-msg" data-compact={compact || undefined} data-camp={camp} id={date ? `message-${date}-${camp}` : undefined}>
    <header className="sc-v3-msg__k"><h3 className="sc-v3-sans">{CAMP_LABELS[camp]}</h3>{date && !compact ? <time dateTime={date}>{formatDatePl(date)}</time> : null}</header>
    {message ? <>
      {structured ? <p className="sc-v3-msg__thesis">{message.thesis}</p> : <p className="sc-v3-msg__legacy">{message.message}</p>}
      <MessageMetrics stats={message.stats} />
      {!compact && structured ? <div className="sc-v3-tps">
        <p className="sc-v3-tone__h">Główne wątki</p>
        <ol>{message.points!.map((point, index) => <li key={index}>
          <b>{point.title}</b><p>{point.summary}</p><small>{point.authors.join(", ")} · wpisów: {point.post_ids.length}</small>
        </li>)}</ol>
      </div> : null}
      <p className="sc-v3-msg__counts"><DiscussionCounts {...message} /></p>
      {compact ? <Link className="sc-v3-lnk sc-v3-msg__more" href={`/klinika/przekazy/${message.day}#message-${message.day}-${camp}`}>Czytaj przekaz i źródła <span className="sc-v3-ar" aria-hidden="true">→</span></Link> :
        <details className="sc-v3-details sc-v3-msg__details" onToggle={event => setOpen(event.currentTarget.open)}>
          <summary>Szczegóły: pełna analiza i wpisy źródłowe</summary>
          <div className="sc-v3-msg__expanded">
            {message.analysis ? <div><h4>Pełna analiza</h4>{message.analysis.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>)}</div> : null}
            {/* redakcja językowa (właściciel 5.10): tylko forma, sens bez zmian; tekst pierwotny jawny */}
            {message.readability_edit ? <details className="sc-v3-details"><summary>Redakcja językowa: tekst wygładzony, sens bez zmian · pokaż tekst pierwotny</summary>
              {Object.entries(message.readability_edit.original).map(([key, text]) => <p key={key}><b>{key === "thesis" ? "Teza" : key === "message" ? "Przekaz" : "Analiza"}:</b> {text}</p>)}
            </details> : null}
            <div><h4>Źródła - wpisy</h4>
              {sources.isFetching ? <p role="status"><Loading label="Wczytywanie źródeł" /></p> : null}
              {sources.isError ? <p role="alert">Nie udało się pobrać źródeł. <button type="button" className="sc-v3-qbtn" onClick={() => void sources.refetch()}>Spróbuj ponownie</button></p> : null}
              {full?.posts?.length ? <ol className="sc-v3-msg__sources">{full.posts.map(post => <li key={post.url}>
                <a className="sc-v3-inl" href={post.url} target="_blank" rel="noopener noreferrer"><b>{post.author}</b> @{post.handle} ↗</a>
                <time dateTime={post.published_at}>{formatDateTimePl(post.published_at)}</time><p>{post.available === false ? "Wpis jest niedostępny." : post.text}</p>
              </li>)}</ol> : !sources.isFetching && !sources.isError ? <p>Brak zapisanych źródeł.</p> : null}
              <p className="sc-v3-meta">Wpisy w brzmieniu oryginalnym. Treść mogła zostać zmieniona lub usunięta po pobraniu.</p>
            </div>
            <dl className="sc-v3-msg__meta">
              {full?.scope?.date_from && full.scope.date_to ? <div><dt>Zakres publikacji źródeł</dt><dd>{formatDateTimePl(full.scope.date_from)} - {formatDateTimePl(full.scope.date_to)}</dd></div> : null}
              {message.created_at ? <div><dt>Przygotowano</dt><dd>{formatDateTimePl(message.created_at)}</dd></div> : null}
              {message.reviewed_at ? <div><dt>Zatwierdzono</dt><dd>{formatDateTimePl(message.reviewed_at)}</dd></div> : null}
              <div><dt>Model</dt><dd>{message.model || "Nie zapisano"}</dd></div>
            </dl>
            <p className="sc-v3-meta">Szum: {message.stats?.noise ?? "brak danych"} odfiltrowanych wpisów. Krótkie reakcje i podziękowania nie wchodzą do wskaźników ani do modelu.</p>
            <p className="sc-v3-meta">Konkret oznacza liczbę lub link, bez oceny prawdziwości. Spójność i ton wynikają z przypisań AI.</p>
          </div>
        </details>}
      {!compact && message.id ? <div className="sc-v3-msg__disc"><ClinicDiscussion kind="daily-messages" id={message.id} /></div> : null}
    </> : <p className="sc-v3-empty">{emptyText ?? "Brak opublikowanego przekazu tej strony w tym dniu."}</p>}
  </article>;
}
