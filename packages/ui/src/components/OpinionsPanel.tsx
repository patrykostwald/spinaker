"use client";

import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiWrite } from "../lib/api";
import { useAccount } from "../lib/account";
import { formatDateTimePl } from "../lib/utils";
import { AccountDialog } from "./AccountDialog";
import { CommentReportButton } from "./CommentReportButton";
import { Button, RadioGroup, Reveal } from "../kit";
import { ACCOUNTS_ENABLED } from "../lib/features";

type Polarity = "positive" | "negative";
type Opinion = { id: number; author: { id: number; username: string }; polarity: Polarity; body: string; created_at: string };
type Opinions = { counts: Record<Polarity, number>; mine: Opinion | null; positive: Opinion[]; negative: Opinion[] };

export type OpinionLabels = {
  kicker: string;
  question: string;
  positive: string;
  negative: string;
  signedOut: string;
};

/**
 * Reakcje czytelników w dwóch kolumnach. Najpierw reakcja (za / przeciw), komentarz opcjonalnie —
 * sam komentarz bez reakcji nie jest możliwy; komentarz trafia do kolumny swojej reakcji.
 */
function OpinionsPanelInner({ endpoint, labels, reportKind }: { endpoint: string; labels: OpinionLabels; reportKind?: "thread" }) {
  const account = useAccount();
  const ownerId = account.data?.user?.id;
  const key = ["opinions", endpoint, ownerId];
  const cache = useQueryClient();
  const query = useQuery({ queryKey: key, queryFn: () => apiFetch<Opinions>(endpoint) });
  const [polarity, setPolarity] = useState<Polarity | "">("");
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [accountOpen, setAccountOpen] = useState(false);
  const mine = query.data?.mine;
  const label = (side: Polarity) => (side === "positive" ? labels.positive : labels.negative);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const chosen = mine?.polarity ?? polarity;
    if (!chosen || body.length > 240 || (mine && !body.trim())) return;
    setPending(true); setError("");
    try {
      await apiWrite(endpoint, mine ? { body: body.trim() } : { polarity: chosen, body: body.trim() }, mine ? "PATCH" : "POST");
      setBody("");
      await cache.invalidateQueries({ queryKey: key });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się zapisać opinii.");
    } finally { setPending(false); }
  }

  return <section className="sc-thread-opinions">
    <header><div><p className="sc-thread-opinions-kicker">{labels.kicker}</p><h2>{labels.question}</h2></div>{query.data && <p className="sc-thread-opinions-counts"><span>{labels.positive} {query.data.counts.positive}</span><span>{labels.negative} {query.data.counts.negative}</span></p>}</header>
    {query.isError && <p role="alert" className="sc-thread-opinions-message">Nie udało się pobrać opinii. <Button size="sm" variant="quiet" onClick={() => query.refetch()}>Ponów</Button></p>}
    {query.data && <div className="sc-thread-opinions-columns">{(["negative", "positive"] as const).map(side => <section className={`sc-thread-opinion-column is-${side}`} key={side}><h3>{label(side)} <span>{query.data.counts[side]}</span></h3>{query.data[side].map(item => <article className="sc-thread-reader-opinion" key={item.id}><div><strong>@{item.author.username}</strong><time dateTime={item.created_at}>{formatDateTimePl(item.created_at)}</time></div><p>{item.body}</p>{reportKind && item.author.id !== ownerId && <CommentReportButton kind={reportKind} opinionId={item.id} author={item.author.username} />}</article>)}{!query.data[side].length && <p className="sc-thread-opinion-empty">Brak komentarzy.</p>}</section>)}</div>}
    {!ownerId ? <p className="sc-thread-opinions-message">{labels.signedOut} <Button size="sm" variant="quiet" onClick={() => setAccountOpen(true)}>Zaloguj się</Button></p> : mine?.body ? <p className="sc-thread-opinions-message">Twoja reakcja i komentarz są zapisane.</p> : query.isSuccess && <form className="sc-thread-opinion-composer" onSubmit={submit}>
      {mine ? <p>Reakcja zapisana: {label(mine.polarity).toLowerCase()}. Możesz jeszcze dodać jeden komentarz.</p> : <RadioGroup name={`opinion-${endpoint}`} legend={labels.question} value={polarity} onChange={value => setPolarity(value as Polarity)} options={[{ value: "negative", label: labels.negative }, { value: "positive", label: labels.positive }]} />}
      <label>Komentarz {mine ? "" : "(opcjonalnie)"}<textarea rows={3} maxLength={240} value={body} onChange={event => setBody(event.target.value)} className="sc-thread-opinion-textarea" /></label>
      <div className="sc-thread-opinion-actions"><span>{body.length}/240</span><Button type="submit" variant="primary" loading={pending} disabled={pending || (!mine && !polarity) || Boolean(mine && !body.trim())}>{mine ? "Dodaj komentarz" : "Zapisz reakcję"}</Button></div>
    </form>}
    <Reveal when={Boolean(error)} className="sc-thread-opinions-message sc-thread-opinions-message-error"><p role="alert">{error}</p></Reveal>
    <AccountDialog open={accountOpen} onClose={() => setAccountOpen(false)} />
  </section>;
}

/** Wyłączone razem z kontami czytelników (NEXT_PUBLIC_ACCOUNTS_ENABLED). */
export function OpinionsPanel(props: Parameters<typeof OpinionsPanelInner>[0]) {
  return ACCOUNTS_ENABLED ? <OpinionsPanelInner {...props} /> : null;
}
