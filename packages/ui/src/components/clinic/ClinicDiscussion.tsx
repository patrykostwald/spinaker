"use client";

import Link from "next/link";
import { FormEvent, useRef, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiWrite, ApiError } from "../../lib/api";
import { emailVerified, useAccount } from "../../lib/account";
import { useFeature } from "../../lib/features";
import { formatDateTimePl } from "../../lib/utils";
import { Button } from "../../kit/Button";
import { AccountDialog } from "../AccountDialog";

type Polarity = "positive" | "negative";
type Ratings = { counts: Record<Polarity, number>; mine: { polarity: Polarity } | null };
type Comment = { id: number; author: { id: number; username: string }; body: string | null; hidden: boolean;
  hidden_reason: string; parent: number | null; created_at: string; reply_count: number };
type Page = { results: Comment[]; count: number; next_page: number | null };
const reasons = [["spam", "Spam"], ["abuse", "Naruszenie zasad"], ["privacy", "Dane prywatne"], ["off_topic", "Poza tematem"], ["other", "Inne"]];
const unavailable = (error: unknown) => error instanceof ApiError && error.status === 404;
const message = (error: unknown) => unavailable(error) ? "Dyskusja jest jeszcze niedostępna." : error instanceof Error ? error.message : "Nie udało się zapisać. Spróbuj ponownie.";

export function DiscussionCounts({ opinions, comment_count }: { opinions?: Record<Polarity, number>; comment_count?: number }) {
  const enabled = useFeature("ACCOUNTS_ENABLED");
  if (!enabled || !opinions || comment_count === undefined) return null;
  const noun = comment_count === 1 ? "komentarz" : comment_count % 10 >= 2 && comment_count % 10 <= 4 && (comment_count % 100 < 12 || comment_count % 100 > 14) ? "komentarze" : "komentarzy";
  return <span className="sc-discussion-counts" aria-label={`Trafne: ${opinions.positive}, nietrafne: ${opinions.negative}, komentarze: ${comment_count}`}>+{opinions.positive} −{opinions.negative} · {comment_count} {noun}</span>;
}

function Report({ endpoint, comment, onReported }: { endpoint: string; comment: Comment; onReported: () => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("abuse");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError("");
    try { await apiWrite(`${endpoint}comments/${comment.id}/report/`, { reason, details }); setDone(true); setOpen(false); onReported(); }
    catch (error) { setError(message(error)); } finally { setBusy(false); }
  }
  return <div className="sc-discussion-report">{done ? <p role="status">Zgłoszenie przyjęte.</p> : <>
    <Button type="button" variant="quiet" onClick={() => setOpen(!open)} aria-expanded={open}>Zgłoś</Button>
    {open ? <form onSubmit={submit} aria-label={`Zgłoś komentarz użytkownika ${comment.author.username}`}>
      <label>Powód zgłoszenia<select value={reason} onChange={event => setReason(event.target.value)}>{reasons.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>Dodatkowe informacje (opcjonalnie)<textarea value={details} onChange={event => setDetails(event.target.value)} maxLength={500} rows={2} /></label>
      <Button type="submit" disabled={busy}>{busy ? "Wysyłanie…" : "Wyślij zgłoszenie"}</Button>
    </form> : null}</>}{error ? <p role="alert">{error}</p> : null}</div>;
}

function Comments({ endpoint, ownerId, canWrite, parent, onReply }: { endpoint: string; ownerId?: number; canWrite: boolean; parent?: number; onReply: (comment: Comment) => void }) {
  const cache = useQueryClient();
  const query = useInfiniteQuery({ queryKey: ["clinic-comments", endpoint, ownerId, parent], initialPageParam: 1,
    queryFn: ({ pageParam }) => apiFetch<Page>(`${endpoint}comments/?page=${pageParam}${parent ? `&parent=${parent}` : ""}`),
    getNextPageParam: page => page.next_page ?? undefined, retry: false });
  const refresh = () => { void cache.invalidateQueries({ queryKey: ["clinic-comments", endpoint] }); };
  const rows = [...new Map(query.data?.pages.flatMap(page => page.results).map(row => [row.id, row]) ?? []).values()];
  return <div className={parent ? "sc-discussion-replies" : "sc-discussion-list"}>
    {query.isPending ? <p role="status">Ładowanie komentarzy…</p> : null}
    {query.isError ? <p role="status">{unavailable(query.error) ? "Dyskusja jest jeszcze niedostępna." : <>Nie udało się pobrać komentarzy. <Button variant="quiet" onClick={() => void query.refetch()}>Ponów</Button></>}</p> : null}
    {query.isSuccess && !rows.length ? <p>{parent ? "Brak odpowiedzi." : "Nie ma jeszcze komentarzy. Rozpocznij dyskusję."}</p> : null}
    {rows.map(row => <CommentRow key={row.id} row={row} endpoint={endpoint} ownerId={ownerId} canWrite={canWrite} onReply={onReply} refresh={refresh} />)}
    {query.hasNextPage ? <Button variant="quiet" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Ładowanie…" : parent ? "Pokaż więcej odpowiedzi" : "Pokaż więcej"}</Button> : null}
  </div>;
}

function CommentRow({ row, endpoint, ownerId, canWrite, onReply, refresh }: { row: Comment; endpoint: string; ownerId?: number; canWrite: boolean; onReply: (comment: Comment) => void; refresh: () => void }) {
  const [expanded, setExpanded] = useState(false);
  return <article className="sc-discussion-comment" id={`komentarz-${row.id}`}>
    <header><strong>@{row.author.username}</strong><time dateTime={row.created_at}>{formatDateTimePl(row.created_at)}</time></header>
    {row.hidden ? <p className="sc-discussion-hidden">Komentarz ukryty przez moderację{row.author.id === ownerId && row.hidden_reason ? ` · ${row.hidden_reason}` : ""}</p> : null}
    {row.body !== null ? <p className="sc-discussion-body">{row.body}</p> : null}
    <div className="sc-discussion-actions">
      {canWrite && !row.parent ? <Button variant="quiet" onClick={() => onReply(row)}>Odpowiedz</Button> : null}
      {canWrite && row.author.id !== ownerId && !row.hidden ? <Report endpoint={endpoint} comment={row} onReported={refresh} /> : null}
      {!row.parent && row.reply_count > 0 ? <Button variant="quiet" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? "Zwiń odpowiedzi" : `Odpowiedzi (${row.reply_count})`}</Button> : null}
    </div>
    {expanded ? <Comments endpoint={endpoint} ownerId={ownerId} canWrite={canWrite} parent={row.id} onReply={onReply} /> : null}
  </article>;
}

function DiscussionContent({ endpoint }: { endpoint: string }) {
  const account = useAccount();
  const ownerId = account.data?.user?.id;
  const verified = Boolean(ownerId && emailVerified(account.data));
  const cache = useQueryClient();
  const ratings = useQuery({ queryKey: ["clinic-ratings", endpoint, ownerId], queryFn: () => apiFetch<Ratings>(`${endpoint}opinions/`), retry: false });
  const [body, setBody] = useState("");
  const [reply, setReply] = useState<Comment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [login, setLogin] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  async function rate(polarity: Polarity) {
    if (!ownerId) { setLogin(true); return; }
    if (!verified || busy) return;
    setBusy(true); setError(""); setStatus("");
    const removing = ratings.data?.mine?.polarity === polarity;
    try {
      const result = await apiWrite<Ratings>(`${endpoint}opinions/`, { polarity }, removing ? "DELETE" : "POST");
      cache.setQueryData(["clinic-ratings", endpoint, ownerId], result);
      setStatus(removing ? "Ocena cofnięta." : "Ocena zapisana.");
    } catch (error) { setError(message(error)); } finally { setBusy(false); }
  }
  async function publish(event: FormEvent) {
    event.preventDefault(); if (busy || !body.trim()) return;
    setBusy(true); setError(""); setStatus("");
    try {
      const row = await apiWrite<Comment>(`${endpoint}comments/`, { body: body.trim(), parent: reply?.id ?? null });
      setBody(""); setReply(null);
      setStatus(row.hidden ? `Komentarz zapisany i ukryty: ${row.hidden_reason}` : "Komentarz opublikowany.");
      await cache.invalidateQueries({ queryKey: ["clinic-comments", endpoint] });
    } catch (error) { setError(message(error)); } finally { setBusy(false); }
  }
  return <section id="dyskusja" className="sc-clinic-discussion" aria-labelledby="dyskusja-title">
    <h2 id="dyskusja-title">Dyskusja</h2>
    <p>Czy analiza jest trafna? Ocena i komentarz są niezależne. Kliknij wybraną ocenę ponownie, aby ją cofnąć.</p>
    {ratings.isPending ? <p role="status">Ładowanie ocen…</p> : null}
    {ratings.isError ? <p role="status">{unavailable(ratings.error) ? "Dyskusja jest jeszcze niedostępna." : <>Nie udało się pobrać ocen. <Button variant="quiet" onClick={() => void ratings.refetch()}>Ponów</Button></>}</p> : null}
    {ratings.data ? <div className="sc-discussion-actions sc-discussion-rate" aria-label="Ocena analizy">{(["positive", "negative"] as const).map(side => <Button key={side} variant="quiet" className={`sc-rate sc-rate--${side}`} disabled={busy || Boolean(ownerId && !verified)} aria-pressed={ratings.data.mine?.polarity === side} onClick={() => void rate(side)}>{side === "positive" ? "Trafne +" : "Nietrafne −"} <span>{ratings.data.counts[side]}</span></Button>)}</div> : null}
    {ratings.data?.mine ? <p>Twoja ocena: {ratings.data.mine.polarity === "positive" ? "Trafne +" : "Nietrafne −"}.</p> : null}
    <p className="sc-discussion-note">Rozmawiaj kulturalnie, bez gróźb, wulgaryzmów i danych prywatnych. Ta sama miara obowiązuje wszystkich. Moderacja ukrywa komentarze - nie edytuje ich. <Link href="/zasady-dyskusji">Zasady dyskusji</Link>.</p>
    {account.isPending ? <p role="status">Sprawdzanie konta…</p> : !ownerId ? <Button variant="quiet" onClick={() => setLogin(true)}>Zaloguj się, aby ocenić i komentować</Button> : !verified ? <p>Potwierdź e-mail, aby ocenić i komentować. <Link href="/konto">Przejdź do konta</Link>.</p> : ratings.isSuccess ? <form onSubmit={publish}>
      {reply ? <p>Odpowiedź na komentarz @{reply.author.username} <Button variant="quiet" disabled={busy} onClick={() => setReply(null)}>Anuluj odpowiedź</Button></p> : null}
      <label htmlFor="clinic-comment-body">{reply ? "Twoja odpowiedź" : "Twój komentarz"}</label>
      <textarea ref={input} id="clinic-comment-body" value={body} disabled={busy} onChange={event => setBody(event.target.value)} rows={4} maxLength={1000} aria-describedby="clinic-comment-limit" />
      <p id="clinic-comment-limit">{Array.from(body).length}/1000 znaków. Opublikowanego komentarza nie można edytować.</p>
      <Button type="submit" variant="primary" disabled={busy || !body.trim()}>{busy ? "Zapisywanie…" : "Dodaj komentarz"}</Button>
    </form> : null}
    {error ? <p role="alert">{error}</p> : null}<p role="status" aria-live="polite">{status}</p>
    {!unavailable(ratings.error) ? <Comments endpoint={endpoint} ownerId={ownerId} canWrite={verified} onReply={row => { setReply(row); input.current?.focus(); }} /> : null}
    <AccountDialog open={login} onClose={() => setLogin(false)} />
  </section>;
}

function AccountDiscussion({ endpoint }: { endpoint: string }) {
  const account = useAccount();
  return <DiscussionContent key={`${endpoint}:${account.data?.user?.id ?? "guest"}`} endpoint={endpoint} />;
}

export function ClinicDiscussion({ kind, id }: { kind: "spins" | "interviews"; id: number }) {
  const enabled = useFeature("ACCOUNTS_ENABLED");
  return enabled ? <AccountDiscussion endpoint={`/api/clinic/${kind}/${id}/`} /> : null;
}
