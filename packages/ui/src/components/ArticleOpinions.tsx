"use client";
import { useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { Article } from '../types';
import { apiFetch, apiWrite } from '../lib/api';
import { useAccount } from '../lib/account';
import { measurePost } from '../lib/xText';
import { formatDateTimePl } from '../lib/utils';
import { AccountDialog } from './AccountDialog';
import { CommentReportButton } from './CommentReportButton';

type Polarity = 'positive' | 'negative';
type Opinion = { id: number; author: { id: number; username: string }; polarity: Polarity; body: string; created_at: string };
type OpinionPage = { results: Opinion[]; next_page: number | null };
type Opinions = { counts: { positive: number; negative: number }; positive: OpinionPage; negative: OpinionPage; mine: Opinion | null };

function CopyPost({ text, articleId }: { text: string; articleId: number }) {
  const [prepared, setPrepared] = useState(false);
  const [notice, setNotice] = useState('');
  const [url, setUrl] = useState('');
  const post = `${text}\n${url}`;
  const stats = measurePost(post);
  return <div className="opinion-export"><button type="button" className="text-xs text-primary" onClick={() => { setUrl(window.location.origin + '/material/' + articleId); setPrepared(v => !v); }}>{prepared ? 'Zwiń post' : 'Przygotuj post na X ↗'}</button>{prepared && <div className="mt-3 space-y-2"><textarea readOnly aria-label="Post do skopiowania na X" className="w-full rounded border bg-transparent p-3 text-sm" rows={4} value={post} /><div className="flex items-center justify-between gap-3"><span className="text-xs text-slate-500">{stats.weightedLength}/280 · znaki ważone</span><button type="button" disabled={!stats.valid} className="quiet-button" onClick={async () => { try { await navigator.clipboard.writeText(post); setNotice('Skopiowano post.'); } catch { setNotice('Zaznacz tekst i skopiuj go ręcznie.'); } }}>Kopiuj post</button></div>{!stats.valid && <p className="text-xs text-red-700">Ten tekst przekracza limit posta. Skróć komentarz przed publikacją.</p>}<p className="text-xs text-slate-500">Link prowadzi do materiału i jego kontekstu w spin.clinic. Gotowy tekst publikujesz samodzielnie na X.</p>{notice && <p role="status" className="text-xs text-primary">{notice}</p>}</div>}</div>;
}

function OpinionContent({ article, ownerId }: { article: Pick<Article, 'id'>; ownerId: number | undefined }) {
  const cache = useQueryClient();
  const queryKey = ['article-opinions', article.id, ownerId];
  const opinions = useQuery({ queryKey, queryFn: () => apiFetch<Opinions>(`/api/articles/${article.id}/opinions/`), staleTime: 15_000 });
  const [body, setBody] = useState('');
  const [polarity, setPolarity] = useState<Polarity | ''>('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [accountOpen, setAccountOpen] = useState(false);
  const [posted, setPosted] = useState<Opinion | null>(null);
  const [extra, setExtra] = useState<Record<Polarity, Opinion[]>>({ positive: [], negative: [] });
  const [next, setNext] = useState<Partial<Record<Polarity, number | null>>>({});
  const [loadingMore, setLoadingMore] = useState<Polarity | null>(null);
  const mine = posted ?? opinions.data?.mine;
  const chosenPolarity = mine?.polarity ?? polarity;
  const stats = measurePost(body);
  const codepoints = Array.from(body.normalize('NFC')).length;
  const bodyValid = body.trim().length > 0 && stats.weightedLength <= 240 && codepoints <= 240;
  async function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!chosenPolarity || mine?.body || (body.trim() ? !bodyValid : Boolean(mine))) return;
    setPending(true); setError('');
    try {
      const result = await apiWrite<Opinion>(`/api/articles/${article.id}/opinions/`, mine ? { body: body.trim() } : { polarity: chosenPolarity, body: body.trim() }, mine ? 'PATCH' : 'POST');
      setPosted(result);
      await cache.invalidateQueries({ queryKey });
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się dodać opinii.'); }
    finally { setPending(false); }
  }
  async function loadMore(side: Polarity) {
    const page = next[side] === undefined ? opinions.data?.[side].next_page : next[side];
    if (!page || loadingMore) return;
    setLoadingMore(side); setError('');
    try {
      const result = await apiFetch<Opinions>(`/api/articles/${article.id}/opinions/?${side}_page=${page}`);
      setExtra(current => ({ ...current, [side]: [...current[side], ...result[side].results] }));
      setNext(current => ({ ...current, [side]: result[side].next_page }));
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się pobrać komentarzy.'); }
    finally { setLoadingMore(null); }
  }
  return <section className="article-opinions">
    <header className="strip-heading"><div><h2>Reakcje i komentarze</h2><p>Czy materiał był przydatny w tym kontekście? Reakcja dotyczy materiału — nie ocenia osób ani prawdziwości treści.</p></div></header>
    {opinions.isPending && <p role="status" className="strip-empty">Ładuję opinie…</p>}
    {opinions.isError && <p role="alert" className="strip-empty">Nie udało się pobrać opinii. <button onClick={() => opinions.refetch()} className="text-primary">Ponów</button></p>}
    {opinions.data && <div className="opinion-columns">{(['negative', 'positive'] as const).map(side => {
      const rows = [...new Map([...opinions.data![side].results, ...extra[side]].map(item => [item.id, item])).values()];
      const nextPage = next[side] === undefined ? opinions.data![side].next_page : next[side];
      return <section key={side} className={`opinion-column opinion-${side}`} aria-label={`Komentarze: ${side === 'negative' ? 'nieprzydatne' : 'przydatne'}`}><h3>{side === 'negative' ? 'Nieprzydatne' : 'Przydatne'} <span>{opinions.data!.counts[side]}</span></h3>{rows.length ? rows.map(opinion => <article key={opinion.id} className="reader-opinion"><div className="flex flex-wrap items-baseline justify-between gap-2"><strong>@{opinion.author.username}</strong><time dateTime={opinion.created_at}>{formatDateTimePl(opinion.created_at)}</time></div><p>{opinion.body}</p><CopyPost text={opinion.body} articleId={article.id} />{opinion.author.id !== ownerId && <CommentReportButton kind="article" opinionId={opinion.id} author={opinion.author.username} />}</article>) : <p className="opinion-empty">Nie ma jeszcze komentarzy w tej części.</p>}{nextPage && <button disabled={Boolean(loadingMore)} onClick={() => loadMore(side)} className="quiet-button">{loadingMore === side ? 'Ładuję…' : 'Kolejne opinie'}</button>}</section>;
    })}</div>}
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    {!ownerId ? <div className="opinion-invitation"><p>Zaloguj się, aby zaznaczyć, czy materiał był przydatny, i dodać komentarz.</p><button className="quiet-button" onClick={() => setAccountOpen(true)}>Zaloguj się</button></div> : mine?.body ? <div className="opinion-confirmation"><p className="text-sm">Twoja reakcja i komentarz są zapisane · {mine.polarity === 'positive' ? 'przydatne' : 'nieprzydatne'}.</p><CopyPost text={mine.body} articleId={article.id} /></div> : opinions.isSuccess ? <form onSubmit={publish} className="opinion-composer">
      {mine && <p role="status" className="mb-4 text-sm text-primary">Reakcja zapisana · {mine.polarity === 'positive' ? 'przydatne' : 'nieprzydatne'}. Możesz jeszcze dopisać jeden komentarz.</p>}
      <fieldset disabled={Boolean(mine)}><legend className="mb-3 text-sm">Czy ten materiał był dla Ciebie przydatny?</legend><div className="flex gap-3">{(['negative', 'positive'] as const).map(side => <label key={side} className={`opinion-choice opinion-${side}`}><input type="radio" name={`opinion-${article.id}`} value={side} checked={chosenPolarity === side} onChange={() => setPolarity(side)} required />{side === 'negative' ? 'Nieprzydatne' : 'Przydatne'}</label>)}</div></fieldset>
      <label className="mt-4 block text-sm">Twój komentarz {mine ? '' : '(opcjonalnie)'}<textarea value={body} onChange={e => setBody(e.target.value)} rows={3} maxLength={1000} className="mt-2 w-full rounded border bg-transparent p-3" placeholder="Odnieś się do materiału i jego kontekstu, nie do osób." /></label>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500"><span className={stats.weightedLength > 240 || codepoints > 240 ? 'text-red-700' : ''}>{stats.weightedLength}/240 znaków ważonych · {codepoints}/240 znaków</span><span>Jedna reakcja i opcjonalny komentarz. Reakcji i opublikowanego komentarza nie można później zmienić.</span></div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><button disabled={pending || !chosenPolarity || (body.trim() ? !bodyValid : Boolean(mine))} className="rounded bg-primary px-5 py-2.5 text-sm text-white disabled:opacity-40">{pending ? 'Zapisuję…' : mine ? 'Dodaj komentarz' : body.trim() ? 'Zapisz reakcję i komentarz' : 'Zapisz reakcję'}</button>{bodyValid && <CopyPost text={body.trim()} articleId={article.id} />}</div>
    </form> : null}
    <AccountDialog open={accountOpen} onClose={() => setAccountOpen(false)} />
  </section>;
}

export function ArticleOpinions({ article }: { article: Pick<Article, 'id'> }) {
  const account = useAccount();
  return <OpinionContent key={`${article.id}:${account.data?.user?.id ?? 'guest'}`} article={article} ownerId={account.data?.user?.id} />;
}
