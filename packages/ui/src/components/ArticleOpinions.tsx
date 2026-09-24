"use client";

import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Article } from "../types";
import { apiFetch, apiWrite } from "../lib/api";
import { useAccount } from "../lib/account";
import { measurePost } from "../lib/xText";
import { formatDateTimePl } from "../lib/utils";
import { AccountDialog } from "./AccountDialog";
import { CommentReportButton } from "./CommentReportButton";
import { Button, RadioGroup, Reveal } from "../kit";

type Polarity = "positive" | "negative";
type Opinion = { id: number; author: { id: number; username: string }; polarity: Polarity; body: string; created_at: string };
type OpinionPage = { results: Opinion[]; next_page: number | null };
type Opinions = { counts: { positive: number; negative: number }; positive: OpinionPage; negative: OpinionPage; mine: Opinion | null };

function CopyPost({ text, articleId }: { text: string; articleId: number }) {
  const [prepared, setPrepared] = useState(false);
  const [notice, setNotice] = useState("");
  const [url, setUrl] = useState("");
  const post = `${text}\n${url}`;
  const stats = measurePost(post);
  return <div className="sc-article-post">
    <Button type="button" variant="quiet" size="sm" onClick={() => { setUrl(window.location.origin + "/material/" + articleId); setPrepared(value => !value); }}>{prepared ? "Zwiń post" : "Przygotuj post na X"}</Button>
    <Reveal when={prepared} className="sc-article-post__body"><textarea readOnly aria-label="Post do skopiowania na X" rows={4} value={post} /><div><span>{stats.weightedLength}/280 · znaki ważone</span><Button type="button" variant="secondary" size="sm" disabled={!stats.valid} onClick={async () => { try { await navigator.clipboard.writeText(post); setNotice("Skopiowano post."); } catch { setNotice("Zaznacz tekst i skopiuj go ręcznie."); } }}>Kopiuj post</Button></div>{!stats.valid ? <p role="alert">Ten tekst przekracza limit posta. Skróć komentarz przed publikacją.</p> : null}<p>Link prowadzi do materiału i jego kontekstu w spin.clinic. Gotowy tekst publikujesz samodzielnie na X.</p>{notice ? <p role="status">{notice}</p> : null}</Reveal>
  </div>;
}

function OpinionContent({ article, ownerId }: { article: Pick<Article, "id">; ownerId: number | undefined }) {
  const cache = useQueryClient();
  const queryKey = ["article-opinions", article.id, ownerId];
  const opinions = useQuery({ queryKey, queryFn: () => apiFetch<Opinions>(`/api/articles/${article.id}/opinions/`), staleTime: 15_000 });
  const [body, setBody] = useState("");
  const [polarity, setPolarity] = useState<Polarity | "">("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [accountOpen, setAccountOpen] = useState(false);
  const [posted, setPosted] = useState<Opinion | null>(null);
  const [extra, setExtra] = useState<Record<Polarity, Opinion[]>>({ positive: [], negative: [] });
  const [next, setNext] = useState<Partial<Record<Polarity, number | null>>>({});
  const [loadingMore, setLoadingMore] = useState<Polarity | null>(null);
  const mine = posted ?? opinions.data?.mine;
  const chosenPolarity = mine?.polarity ?? polarity;
  const stats = measurePost(body);
  const codepoints = Array.from(body.normalize("NFC")).length;
  const bodyValid = body.trim().length > 0 && stats.weightedLength <= 240 && codepoints <= 240;

  async function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosenPolarity || mine?.body || (body.trim() ? !bodyValid : Boolean(mine))) return;
    setPending(true); setError("");
    try { const result = await apiWrite<Opinion>(`/api/articles/${article.id}/opinions/`, mine ? { body: body.trim() } : { polarity: chosenPolarity, body: body.trim() }, mine ? "PATCH" : "POST"); setPosted(result); await cache.invalidateQueries({ queryKey }); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Nie udało się dodać opinii."); }
    finally { setPending(false); }
  }
  async function loadMore(side: Polarity) {
    const page = next[side] === undefined ? opinions.data?.[side].next_page : next[side];
    if (!page || loadingMore) return;
    setLoadingMore(side); setError("");
    try { const result = await apiFetch<Opinions>(`/api/articles/${article.id}/opinions/?${side}_page=${page}`); setExtra(current => ({ ...current, [side]: [...current[side], ...result[side].results] })); setNext(current => ({ ...current, [side]: result[side].next_page })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Nie udało się pobrać komentarzy."); }
    finally { setLoadingMore(null); }
  }

  return <section className="sc-article-opinions">
    <header><div><p>REAKCJE CZYTELNIKÓW</p><h2>Reakcje i komentarze</h2><span>Czy materiał był przydatny w tym kontekście? Reakcja dotyczy materiału — nie ocenia osób ani prawdziwości treści.</span></div></header>
    {opinions.isPending ? <p role="status" className="sc-article-opinions__message">Ładuję opinie…</p> : null}
    {opinions.isError ? <p role="alert" className="sc-article-opinions__message">Nie udało się pobrać opinii. <Button type="button" variant="quiet" size="sm" onClick={() => opinions.refetch()}>Ponów</Button></p> : null}
    {opinions.data ? <div className="sc-article-opinions__columns">{(["negative", "positive"] as const).map(side => {
      const rows = [...new Map([...opinions.data![side].results, ...extra[side]].map(item => [item.id, item])).values()];
      const nextPage = next[side] === undefined ? opinions.data![side].next_page : next[side];
      return <section key={side} className={`sc-article-opinion-column is-${side}`}><h3>{side === "negative" ? "Nieprzydatne" : "Przydatne"} <span>{opinions.data!.counts[side]}</span></h3>{rows.length ? rows.map(opinion => <article key={opinion.id}><div><strong>@{opinion.author.username}</strong><time dateTime={opinion.created_at}>{formatDateTimePl(opinion.created_at)}</time></div><p>{opinion.body}</p><CopyPost text={opinion.body} articleId={article.id} />{opinion.author.id !== ownerId ? <CommentReportButton kind="article" opinionId={opinion.id} author={opinion.author.username} /> : null}</article>) : <p>Nie ma jeszcze komentarzy w tej części.</p>}{nextPage ? <Button type="button" variant="quiet" size="sm" loading={loadingMore === side} onClick={() => loadMore(side)}>Kolejne opinie</Button> : null}</section>;
    })}</div> : null}
    <Reveal when={Boolean(error)} className="sc-article-opinions__message"><p role="alert">{error}</p></Reveal>
    {!ownerId ? <div className="sc-article-opinions__invitation"><p>Zaloguj się, aby zaznaczyć, czy materiał był przydatny, i dodać komentarz.</p><Button type="button" variant="quiet" onClick={() => setAccountOpen(true)}>Zaloguj się</Button></div> : mine?.body ? <div className="sc-article-opinions__invitation"><p>Twoja reakcja i komentarz są zapisane · {mine.polarity === "positive" ? "przydatne" : "nieprzydatne"}.</p><CopyPost text={mine.body} articleId={article.id} /></div> : opinions.isSuccess ? <form className="sc-article-opinion-composer" onSubmit={publish}>
      {mine ? <p>Reakcja zapisana · {mine.polarity === "positive" ? "przydatne" : "nieprzydatne"}. Możesz jeszcze dopisać jeden komentarz.</p> : <RadioGroup name={`opinion-${article.id}`} legend="Czy ten materiał był dla Ciebie przydatny?" value={polarity} onChange={value => setPolarity(value as Polarity)} options={[{ value: "negative", label: "Nieprzydatne" }, { value: "positive", label: "Przydatne" }]} />}
      <label>Twój komentarz {mine ? "" : "(opcjonalnie)"}<textarea value={body} onChange={event => setBody(event.target.value)} rows={3} maxLength={1000} placeholder="Odnieś się do materiału i jego kontekstu, nie do osób." /></label>
      <div className="sc-article-opinion-composer__meta"><span data-invalid={stats.weightedLength > 240 || codepoints > 240 || undefined}>{stats.weightedLength}/240 znaków ważonych · {codepoints}/240 znaków</span><span>Jedna reakcja i opcjonalny komentarz. Reakcji i opublikowanego komentarza nie można później zmienić.</span></div>
      <div className="sc-article-opinion-composer__actions"><Button type="submit" variant="primary" loading={pending} disabled={!chosenPolarity || (body.trim() ? !bodyValid : Boolean(mine))}>{mine ? "Dodaj komentarz" : body.trim() ? "Zapisz reakcję i komentarz" : "Zapisz reakcję"}</Button>{bodyValid ? <CopyPost text={body.trim()} articleId={article.id} /> : null}</div>
    </form> : null}
    <AccountDialog open={accountOpen} onClose={() => setAccountOpen(false)} />
  </section>;
}

export function ArticleOpinions({ article }: { article: Pick<Article, "id"> }) {
  const account = useAccount();
  return <OpinionContent key={`${article.id}:${account.data?.user?.id ?? "guest"}`} article={article} ownerId={account.data?.user?.id} />;
}
