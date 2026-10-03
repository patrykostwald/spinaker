"use client";
import { useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiWrite } from '../../lib/api';
import { emailVerified, useAccount } from '../../lib/account';
import { useFeature } from '../../lib/features';
import { REPORT_REASONS } from '../../lib/community';
import { Dialog } from '../Dialog';
import { FollowButton } from '../FollowButton';
import { CharacterCount, ClampedText, RATINGS, ratingLabels, SocialIcon, type Counts, type Rating } from './SocialPrimitives';

type Comment = { id: number; body: string; author: string; username?: string; x_profile?: string | null; reactions_count: number; reacted: boolean; created_at: string; edited_at: string | null; is_owner: boolean; can_edit: boolean; hidden?: boolean };
type CommentPage = { results: Comment[]; next_cursor: string | null; count: number };
export type RatingsData = { counts: Counts; mine: { polarity: Rating } | null };
const message = (error: unknown) => error instanceof Error ? error.message : 'Nie udało się zapisać.';

export function SocialReport({ threadId, commentId }: { threadId: number; commentId?: number }) {
  const account = useAccount();
  const enabled = useFeature('ACCOUNTS_ENABLED');
  const [open, setOpen] = useState(false), [reason, setReason] = useState('spam'), [details, setDetails] = useState('');
  const [status, setStatus] = useState(''), [pending, setPending] = useState(false);
  if (!enabled || !account.data?.authenticated) return null;
  async function submit(event: FormEvent) {
    event.preventDefault(); if (pending) return;
    setPending(true);
    try {
      await apiWrite(`/api/community/threads/${threadId}/${commentId ? `comments/${commentId}/` : ''}report/`, { reason, details });
      setStatus('Zgłoszenie przyjęte. O decyzji poinformujemy e-mailem.'); setOpen(false);
    } catch (error) { setStatus(message(error)); } finally { setPending(false); }
  }
  return <span className="sc-social-report"><button type="button" onClick={() => setOpen(true)}>Zgłoś</button><span role="status">{status}</span>
    <Dialog className="sc-social-report-dialog" open={open} onClose={() => setOpen(false)} title={commentId ? 'Zgłoś komentarz' : 'Zgłoś nitkę'}><form onSubmit={submit}>
      <label>Powód<select value={reason} onChange={e => setReason(e.target.value)}>{REPORT_REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}</select></label>
      <label>Opis<textarea maxLength={1000} value={details} onChange={e => setDetails(e.target.value)} /></label><CharacterCount text={details} limit={1000} />
      <button disabled={pending}>Wyślij zgłoszenie</button><p role="status">{status}</p>
    </form></Dialog>
  </span>;
}

export function ThreadSocial({ id, title, ai, expanded, preview = false, showComments, setShowComments, draft, setDraft, focusBox, boxCount, onCounts, onCommentCount }: {
  expanded?: boolean;
  /** Rozwinięty wiersz listy: 3 najtrafniejsze komentarze, „Pokaż wszystkie” i jedno pole „Odpowiedz”. */
  preview?: boolean;
  id: number; title: string; ai?: boolean; showComments: boolean; setShowComments: (value: boolean) => void;
  draft: string; setDraft: (text: string) => void; focusBox: (n: number) => void; boxCount: number;
  onCounts: (counts: Counts) => void; onCommentCount: (count: number) => void;
}) {
  const account = useAccount(), enabled = useFeature('ACCOUNTS_ENABLED'), threads = useFeature('THREADS_ENABLED');
  const canWrite = enabled && account.data?.authenticated && emailVerified(account.data);
  const [showRatings, setShowRatings] = useState(false), [pending, setPending] = useState(false), [status, setStatus] = useState('');
  const [editing, setEditing] = useState<number | null>(null), [editBody, setEditBody] = useState('');
  const [sort, setSort] = useState('best');
  const cache = useQueryClient(), base = `/api/community/threads/${id}/`;
  const ratings = useQuery({ queryKey: ['thread-ratings', id, account.data?.user?.id], queryFn: () => apiFetch<RatingsData>(base + 'opinions/'), enabled: threads && showRatings });
  const comments = useInfiniteQuery({ queryKey: ['thread-comments', id, account.data?.user?.id, sort],
    queryFn: ({ pageParam }) => apiFetch<CommentPage>(base + `comments/?sort=${sort}&after=${encodeURIComponent(pageParam)}`), initialPageParam: '',
    getNextPageParam: page => page.next_cursor ?? undefined, enabled: threads && (showComments || preview) });
  useEffect(() => {
    if (/^#comment-\d+$/.test(window.location.hash)) document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: 'center' });
  }, [comments.data]);
  const labels = ratingLabels(ai);
  async function write(path: string, body: unknown, method = 'POST') {
    if (pending) return false;
    setPending(true); setStatus('');
    try {
      await apiWrite(base + path, body, method);
      await Promise.all(['account-activity', 'account-profile', 'public-profile', 'account-threads'].map(key => cache.invalidateQueries({ queryKey: [key] })));
      await Promise.all([cache.invalidateQueries({ queryKey: ['thread-comments', id] }), cache.invalidateQueries({ queryKey: ['community-threads'] }), cache.invalidateQueries({ queryKey: ['community-thread', String(id)] })]);
      const first = await apiFetch<CommentPage>(base + 'comments/'); onCommentCount(first.count);
      return true;
    } catch (error) { setStatus(message(error)); return false; } finally { setPending(false); }
  }
  async function rate(polarity: Rating) {
    if (pending) return; setPending(true); setStatus('');
    try {
      const result = await apiWrite<RatingsData>(base + 'opinions/', { polarity });
      cache.setQueryData(['thread-ratings', id, account.data?.user?.id], result); onCounts(result.counts);
      await Promise.all(['account-activity', 'account-profile', 'public-profile', 'account-threads'].map(key => cache.invalidateQueries({ queryKey: [key] })));
      await cache.invalidateQueries({ queryKey: ['community-threads'] });
    } catch (error) { setStatus(message(error)); } finally { setPending(false); }
  }
  function content(body: string) {
    return body.split(/(@boks\s+\d{1,3}\b)/gi).map((part, index) => {
      const match = /^@boks\s+(\d+)$/i.exec(part), n = Number(match?.[1]);
      return match && n > 0 && n <= boxCount ? <button className="sc-social-chip" key={index} onClick={() => focusBox(n)}>{part}</button> : part;
    });
  }
  if (!threads) return null;
  if (preview) {
    const rows = comments.data?.pages[0]?.results.slice(0, 3) ?? [];
    const count = comments.data?.pages[0]?.count ?? 0;
    return <div className="sc-thread-social sc-thread-social--preview">
      <section aria-label="Najtrafniejsze komentarze" className="sc-social-comments sc-social-comments--preview">
        {comments.isLoading && <div className="sc-social-skeleton" aria-label="Ładowanie komentarzy" />}
        {comments.isSuccess && !rows.length && <p className="sc-social-empty">Nikt jeszcze nie skomentował. Bądź pierwszy.</p>}
        {rows.length > 0 && <ol>{rows.map(row => <li key={row.id}>
          <header><span className="sc-social-avatar" aria-hidden="true">{row.author.replace('@', '').charAt(0).toUpperCase()}</span><strong>{row.author}</strong><time dateTime={row.created_at}>{new Date(row.created_at).toLocaleDateString('pl-PL')}</time>{row.reactions_count > 0 && <small className="sc-social-trafne"><SocialIcon kind="positive" />{row.reactions_count}</small>}</header>
          <ClampedText>{content(row.body)}</ClampedText>
        </li>)}</ol>}
        {count > 3 && <Link className="sc-social-all" href={`/nitki/${id}#komentarze`}>Pokaż wszystkie komentarze ({count})</Link>}
        {canWrite ? <form className="sc-social-reply" onSubmit={async e => { e.preventDefault(); if (await write('comments/', { body: draft })) { setDraft(''); setStatus('Komentarz dodany.'); } }}>
          <label className="sc-sr-only" htmlFor={`reply-${id}`}>Odpowiedz w nitce</label>
          <input id={`reply-${id}`} value={draft} maxLength={600} onChange={e => setDraft(e.target.value)} placeholder="Odpowiedz…" />
          <button disabled={pending || !draft.trim()}>Odpowiedz</button>
        </form> : enabled ? <p className="sc-social-login"><a href="/konto">Zaloguj się</a>, aby odpowiedzieć.</p> : null}
      </section>
      <p role="status">{status}</p>
    </div>;
  }
  return <div className="sc-thread-social">
    <nav className="sc-thread-social-actions" aria-label="Akcje nitki">
      <button type="button" aria-expanded={showRatings} onClick={() => setShowRatings(!showRatings)}>Oceń</button>
      <button type="button" aria-expanded={showComments} onClick={() => setShowComments(!showComments)}>Komentarz</button>
      <button type="button" onClick={async () => {
        try { const url = `${location.origin}/nitki/${id}`; if (navigator.share) await navigator.share({ title, url }); else { await navigator.clipboard.writeText(url); setStatus('Skopiowano link.'); } }
        catch (error) { if (!(error instanceof Error && error.name === 'AbortError')) setStatus('Nie udało się udostępnić linku.'); }
      }}>Udostępnij</button>
      <FollowButton kind="thread" targetId={id} label={title} compactLabel />
    </nav>
    {showRatings && <section aria-label="Ocena całej nitki" className="sc-social-ratings">
      {ratings.isLoading && <div className="sc-social-skeleton" aria-label="Ładowanie ocen" />}
      {ratings.isError && <button onClick={() => ratings.refetch()}>Ponów odczyt ocen</button>}
      {RATINGS.map(key => enabled ? <button key={key} data-rating={key} disabled={!canWrite || pending} aria-pressed={ratings.data?.mine?.polarity === key} onClick={() => rate(key)}>
        <SocialIcon kind={key} />{labels[key]}<span className="sc-social-rating-count">{ratings.data?.counts[key] ?? 0}</span>
      </button> : <span key={key} data-rating={key}><SocialIcon kind={key} />{labels[key]}: {ratings.data?.counts[key] ?? 0}</span>)}
      {enabled && !canWrite && <p><a href="/konto">Zaloguj się i potwierdź e-mail</a>, aby oceniać i komentować.</p>}
    </section>}
    {showComments && <section id="komentarze" aria-label="Komentarze pod nitką" className="sc-social-comments">
      <label>Kolejność komentarzy<select value={sort} onChange={e => setSort(e.target.value)}><option value="best">Najtrafniejsze</option><option value="new">Najnowsze</option></select></label>
      {comments.isLoading && <div className="sc-social-skeleton" aria-label="Ładowanie komentarzy" />}
      {comments.isError && <button onClick={() => comments.refetch()}>Ponów odczyt komentarzy</button>}
      {comments.isSuccess && !comments.data.pages[0].results.length && <p><SocialIcon kind="comment" /> Bądź pierwszy.</p>}
      <ol>{comments.data?.pages.flatMap(page => page.results).map(row => <li key={row.id} id={`comment-${row.id}`}>
        <header><span className="sc-social-avatar" aria-hidden="true">{row.author.replace('@', '').charAt(0).toUpperCase()}</span><strong>{row.username ? <Link href={`/profile/${encodeURIComponent(row.username)}`}>{row.author}</Link> : row.author}</strong>{row.x_profile && <a href={row.x_profile} target="_blank" rel="noopener noreferrer" aria-label="Połączone konto X">𝕏</a>}<time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString('pl-PL')}</time>{row.edited_at && <small>edytowany</small>}</header>
        {row.hidden && <p>Ten komentarz jest ukryty. Treść widzisz jako autor.</p>}
        {editing === row.id ? <form onSubmit={async e => { e.preventDefault(); if (await write(`comments/${row.id}/`, { body: editBody }, 'PATCH')) setEditing(null); }}>
          <label>Edytuj komentarz<textarea value={editBody} maxLength={600} onChange={e => setEditBody(e.target.value)} /></label><CharacterCount text={editBody} limit={600} />
          <button disabled={pending || !editBody.trim()}>Zapisz</button><button type="button" onClick={() => setEditing(null)}>Anuluj</button>
        </form> : <ClampedText>{content(row.body)}</ClampedText>}
        <footer>{!row.hidden && <button type="button" className="sc-comment-reaction" disabled={!canWrite || pending} aria-pressed={row.reacted} onClick={() => write(`comments/${row.id}/reaction/`, {}, row.reacted ? 'DELETE' : 'POST')}><SocialIcon kind="positive" />Trafne <small>{row.reactions_count ?? 0}</small></button>}{enabled && row.is_owner && <>{row.can_edit && <button onClick={() => { setEditing(row.id); setEditBody(row.body); }}>Edytuj</button>}<button disabled={pending} onClick={() => write(`comments/${row.id}/`, {}, 'DELETE')}>Usuń</button></>}
          {!row.hidden && <SocialReport threadId={id} commentId={row.id} />}</footer>
      </li>)}</ol>
      {comments.hasNextPage && <button disabled={comments.isFetchingNextPage} onClick={() => comments.fetchNextPage()}>Pokaż kolejne komentarze</button>}
      {canWrite ? <form onSubmit={async e => { e.preventDefault(); if (await write('comments/', { body: draft })) { setDraft(''); setStatus('Komentarz dodany.'); } }}>
        <label>Komentarz pod nitką<textarea value={draft} maxLength={600} onChange={e => setDraft(e.target.value)} placeholder="Możesz wskazać @boks 3" /></label>
        <CharacterCount text={draft} limit={600} /><button disabled={pending || !draft.trim()}>Dodaj komentarz</button>
      </form> : enabled ? <p><a href="/konto">Zaloguj się i potwierdź e-mail</a>, aby dodać komentarz.</p> : null}
      <a href="/zasady-korzystania#nitki">Zasady nitek, ocen i komentarzy</a>
    </section>}
    {expanded && canWrite && <button type="button" onClick={e => { setShowComments(true); const parent = e.currentTarget.parentElement; requestAnimationFrame(() => parent?.querySelector<HTMLTextAreaElement>('form textarea')?.focus()); }}>Dodaj swój komentarz</button>}
    <p role="status">{status}</p>
  </div>;
}
