"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CAMP_LABELS, getClinicMessage, type Camp, type DailyMessage, type MessageStats } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { Loading } from "../../kit/Loading";

const TONES = [["atak", "Atak"], ["osiagniecie", "Osiągnięcia"], ["apel", "Apel"], ["inne", "Inne"]] as const;
function Bar({ value }: { value: number | null | undefined }) {
  return <span className="sc-message-metric__bar" aria-hidden="true"><span style={{ width: `${value ?? 0}%` }} /></span>;
}

export function MessageMetrics({ stats }: { stats?: MessageStats }) {
  const known = stats?.version === 1;
  const tone = known ? stats.tone : null;
  return <div className="sc-message-measures">
    {/* bez danych: kreska zamiast napisu, układ ten sam co z liczbami (właściciel 4.10) */}
    <dl className="sc-message-metrics" data-empty={known ? undefined : ""}>
      <div><dt>Wpisy</dt><dd><strong>{known ? stats.posts : "–"}</strong><small>autorów: {known ? stats.authors : "–"}</small></dd><Bar value={known && stats.posts ? 100 : null} /></div>
      <div title="Odsetek wpisów z liczbą lub linkiem. Nie oznacza potwierdzenia ich prawdziwości."><dt>Konkret</dt><dd><strong>{known ? `${stats.concrete_pct}%` : "–"}</strong><small>liczba lub link</small></dd><Bar value={known ? stats.concrete_pct : null} /></div>
      <div title="Autorzy wpisów przypisanych do głównego wątku dnia."><dt>Spójność</dt><dd><strong>{known && stats.coherence_authors !== null ? `${stats.coherence_authors} z ${stats.authors}` : "–"}</strong><small>autorów</small></dd><Bar value={known ? stats.coherence_pct : null} /></div>
    </dl>
    {/* ton: cztery wiersze zawsze (także 0%), etykieta z lewej, procent z prawej, cienki pasek pod spodem (właściciel 7.10) */}
    <ul className="sc-message-tone" aria-label="Ton wpisów" data-empty={tone ? undefined : ""}>
      {TONES.map(([key, label]) => <li key={key} data-tone={key}>
        <span className="sc-message-tone__label"><i aria-hidden="true" />{label}</span>
        <b>{tone ? `${tone[key]}%` : "–"}</b>
        <span className="sc-message-tone__bar" aria-hidden="true"><span style={{ width: `${tone ? tone[key] : 0}%` }} /></span>
      </li>)}
    </ul>
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
  return <article className="sc-message-card" data-compact={compact || undefined} data-camp={camp} id={date ? `message-${date}-${camp}` : undefined}>
    <header className="sc-message-card__label"><span>{CAMP_LABELS[camp]}</span>{date ? <time dateTime={date}>{formatDatePl(date)}</time> : null}</header>
    {message ? <>
      {structured ? <h3 className="sc-message-card__thesis">{message.thesis}</h3> : <p className="sc-message-card__legacy">{message.message}</p>}
      <MessageMetrics stats={message.stats} />
      {!compact && structured ? <ol className="sc-message-points">{message.points!.map((point, index) => <li key={index}>
        <strong>{point.title}</strong><p>{point.summary}</p><small>{point.authors.join(", ")} · wpisów: {point.post_ids.length}</small>
      </li>)}</ol> : null}
      {compact ? <Link className="sc-message-card__more" href={`/klinika/przekazy/${message.day}#message-${message.day}-${camp}`}>Czytaj przekaz i źródła →</Link> :
        <details className="sc-message-card__details" onToggle={event => setOpen(event.currentTarget.open)}>
          <summary>Szczegóły</summary>
          <div className="sc-message-card__expanded">
            {message.analysis ? <div><h4>Pełna analiza</h4>{message.analysis.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>)}</div> : null}
            {/* redakcja językowa (właściciel 5.10): tylko forma, sens bez zmian; tekst pierwotny jawny */}
            {message.readability_edit ? <details className="sc-spin-detail__edit"><summary>Redakcja językowa: tekst wygładzony, sens bez zmian · pokaż tekst pierwotny</summary>
              {Object.entries(message.readability_edit.original).map(([key, text]) => <p key={key}><b>{key === "thesis" ? "Teza" : key === "message" ? "Przekaz" : "Analiza"}:</b> {text}</p>)}
            </details> : null}
            <div><h4>Źródła - wpisy</h4>
              {sources.isFetching ? <p role="status"><Loading label="Wczytywanie źródeł" /></p> : null}
              {sources.isError ? <p role="alert">Nie udało się pobrać źródeł. <button type="button" onClick={() => void sources.refetch()}>Spróbuj ponownie</button></p> : null}
              {full?.posts?.length ? <ol className="sc-message-detail__sources">{full.posts.map(post => <li key={post.url}>
                <a href={post.url} target="_blank" rel="noopener noreferrer"><strong>{post.author}</strong> @{post.handle} ↗</a>
                <time dateTime={post.published_at}>{formatDateTimePl(post.published_at)}</time><p>{post.available === false ? "Wpis jest niedostępny." : post.text}</p>
              </li>)}</ol> : !sources.isFetching && !sources.isError ? <p>Brak zapisanych źródeł.</p> : null}
            </div>
            <dl className="sc-message-detail__meta">
              {full?.scope?.date_from && full.scope.date_to ? <div><dt>Zakres publikacji źródeł</dt><dd>{formatDateTimePl(full.scope.date_from)} - {formatDateTimePl(full.scope.date_to)}</dd></div> : null}
              {message.created_at ? <div><dt>Przygotowano</dt><dd>{formatDateTimePl(message.created_at)}</dd></div> : null}
              {message.reviewed_at ? <div><dt>Zatwierdzono</dt><dd>{formatDateTimePl(message.reviewed_at)}</dd></div> : null}
              <div><dt>Model</dt><dd>{message.model || "Nie zapisano"}</dd></div>
            </dl>
            <small>Szum: {message.stats?.noise ?? "brak danych"} odfiltrowanych wpisów. Krótkie reakcje i podziękowania nie wchodzą do wskaźników ani do modelu.</small>
            <small>Konkret oznacza liczbę lub link, bez oceny prawdziwości. Spójność i ton wynikają z przypisań AI. </small>
          </div>
        </details>}
    </> : <p className="sc-clinic-empty">{emptyText ?? "Brak opublikowanego przekazu tej strony w tym dniu."}</p>}
  </article>;
}
