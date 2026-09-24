"use client";

import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiWrite } from "../lib/api";
import { useAccount } from "../lib/account";
import { formatDateTimePl } from "../lib/utils";
import { AccountDialog } from "./AccountDialog";
import { CommentReportButton } from "./CommentReportButton";
import { Button, RadioGroup, Reveal } from "../kit";

type Polarity = "positive" | "negative";
type Opinion = { id: number; author: { id: number; username: string }; polarity: Polarity; body: string; created_at: string };
type Opinions = { counts: Record<Polarity, number>; mine: Opinion | null; positive: Opinion[]; negative: Opinion[] };

export function ThreadOpinions({ slug }: { slug: string }) {
  const account = useAccount();
  const ownerId = account.data?.user?.id;
  const key = ["thread-opinions", slug, ownerId];
  const cache = useQueryClient();
  const query = useQuery({ queryKey: key, queryFn: () => apiFetch<Opinions>(`/api/threads/${slug}/opinions/`) });
  const [polarity, setPolarity] = useState<Polarity | "">("");
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [accountOpen, setAccountOpen] = useState(false);
  const mine = query.data?.mine;

  async function submit(event: FormEvent) {
    event.preventDefault();
    const chosen = mine?.polarity ?? polarity;
    if (!chosen || body.length > 240 || (mine && !body.trim())) return;
    setPending(true); setError("");
    try {
      await apiWrite(`/api/threads/${slug}/opinions/`, mine ? { body: body.trim() } : { polarity: chosen, body: body.trim() }, mine ? "PATCH" : "POST");
      setBody("");
      await cache.invalidateQueries({ queryKey: key });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się zapisać opinii.");
    } finally { setPending(false); }
  }

  return <section className="sc-thread-opinions">
    <header><div><p className="sc-thread-opinions-kicker">REAKCJE CZYTELNIKÓW</p><h2>Czy ta nitka była przydatna?</h2></div>{query.data && <p className="sc-thread-opinions-counts"><span>Przydatna {query.data.counts.positive}</span><span>Nieprzydatna {query.data.counts.negative}</span></p>}</header>
    {query.isError && <p role="alert" className="sc-thread-opinions-message">Nie udało się pobrać opinii. <Button size="sm" variant="quiet" onClick={() => query.refetch()}>Ponów</Button></p>}
    {query.data && <div className="sc-thread-opinions-columns">{(["negative", "positive"] as const).map(side => <section className={`sc-thread-opinion-column is-${side}`} key={side}><h3>{side === "positive" ? "Przydatna" : "Nieprzydatna"} <span>{query.data.counts[side]}</span></h3>{query.data[side].map(item => <article className="sc-thread-reader-opinion" key={item.id}><div><strong>@{item.author.username}</strong><time dateTime={item.created_at}>{formatDateTimePl(item.created_at)}</time></div><p>{item.body}</p>{item.author.id !== ownerId && <CommentReportButton kind="thread" opinionId={item.id} author={item.author.username} />}</article>)}{!query.data[side].length && <p className="sc-thread-opinion-empty">Brak komentarzy.</p>}</section>)}</div>}
    {!ownerId ? <p className="sc-thread-opinions-message">Zaloguj się, aby zaznaczyć, czy nitka była przydatna, i dodać komentarz. <Button size="sm" variant="quiet" onClick={() => setAccountOpen(true)}>Zaloguj się</Button></p> : mine?.body ? <p className="sc-thread-opinions-message">Twoja reakcja i komentarz są zapisane.</p> : query.isSuccess && <form className="sc-thread-opinion-composer" onSubmit={submit}>
      {mine ? <p>Reakcja zapisana: {mine.polarity === "positive" ? "przydatna" : "nieprzydatna"}. Możesz jeszcze dodać jeden komentarz.</p> : <RadioGroup name="thread-opinion" legend="Czy ta nitka była dla Ciebie przydatna?" value={polarity} onChange={value => setPolarity(value as Polarity)} options={[{ value: "negative", label: "Nieprzydatna" }, { value: "positive", label: "Przydatna" }]} />}
      <label>Komentarz {mine ? "" : "(opcjonalnie)"}<textarea rows={3} maxLength={240} value={body} onChange={event => setBody(event.target.value)} className="sc-thread-opinion-textarea" /></label>
      <div className="sc-thread-opinion-actions"><span>{body.length}/240</span><Button type="submit" variant="primary" loading={pending} disabled={pending || (!mine && !polarity) || Boolean(mine && !body.trim())}>{mine ? "Dodaj komentarz" : "Zapisz reakcję"}</Button></div>
    </form>}
    <Reveal when={Boolean(error)} className="sc-thread-opinions-message sc-thread-opinions-message-error"><p role="alert">{error}</p></Reveal>
    <AccountDialog open={accountOpen} onClose={() => setAccountOpen(false)} />
  </section>;
}


