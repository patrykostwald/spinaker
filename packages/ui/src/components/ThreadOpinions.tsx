"use client";

import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiWrite } from "../lib/api";
import { useAccount } from "../lib/account";
import { formatDateTimePl } from "../lib/utils";
import { AccountDialog } from "./AccountDialog";

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

  return <section className="thread-opinions">
    <header><div><p className="profile-kicker">OCENA CZYTELNIKÓW</p><h2>Jak oceniasz tę nitkę?</h2></div>{query.data && <p><span>− {query.data.counts.negative}</span><span>+ {query.data.counts.positive}</span></p>}</header>
    {query.isError && <p role="alert">Nie udało się pobrać opinii. <button className="quiet-button" onClick={() => query.refetch()}>Ponów</button></p>}
    {query.data && <div className="opinion-columns">{(["negative", "positive"] as const).map(side => <section className={`opinion-column opinion-${side}`} key={side}><h3>{side === "positive" ? "Pozytywne" : "Negatywne"} <span>{query.data.counts[side]}</span></h3>{query.data[side].map(item => <article className="reader-opinion" key={item.id}><div><strong>@{item.author.username}</strong><time dateTime={item.created_at}>{formatDateTimePl(item.created_at)}</time></div><p>{item.body}</p></article>)}{!query.data[side].length && <p className="opinion-empty">Brak komentarzy.</p>}</section>)}</div>}
    {!ownerId ? <button className="quiet-button" onClick={() => setAccountOpen(true)}>Zaloguj się, aby ocenić</button> : mine?.body ? <p className="opinion-confirmation">Twoja opinia została zapisana.</p> : query.isSuccess && <form className="opinion-composer" onSubmit={submit}>
      {mine ? <p>Ocena zapisana: {mine.polarity === "positive" ? "pozytywna" : "negatywna"}. Możesz jeszcze dodać jeden komentarz.</p> : <fieldset><legend>Wybierz reakcję</legend><div className="flex gap-3">{(["negative", "positive"] as const).map(side => <label className={`opinion-choice opinion-${side}`} key={side}><input required type="radio" checked={polarity === side} onChange={() => setPolarity(side)} />{side === "positive" ? "+ Pozytywna" : "− Negatywna"}</label>)}</div></fieldset>}
      <label className="mt-4 block">Komentarz {mine ? "" : "(opcjonalnie)"}<textarea rows={3} maxLength={240} value={body} onChange={event => setBody(event.target.value)} className="mt-2 w-full rounded border bg-transparent p-3" /></label>
      <div className="mt-3 flex items-center justify-between"><span>{body.length}/240</span><button className="profile-primary" disabled={pending || (!mine && !polarity) || Boolean(mine && !body.trim())}>{pending ? "Zapisuję…" : mine ? "Dodaj komentarz" : "Zapisz opinię"}</button></div>
    </form>}
    {error && <p role="alert" className="profile-message profile-message-error">{error}</p>}
    <AccountDialog open={accountOpen} onClose={() => setAccountOpen(false)} />
  </section>;
}
