"use client";
import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import Link from 'next/link';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiWrite } from '../../lib/api';
import { emailVerified, useAccount } from '../../lib/account';
import { useFeature } from '../../lib/features';
import { REPORT_REASONS } from '../../lib/community';
import { Dialog } from '../Dialog';
import { FollowButton } from '../FollowButton';
import { ago, Avatar, CharacterCount, ClampedText, RATINGS, ratingLabels, SocialIcon, type Counts, type Rating } from './SocialPrimitives';

type Comment = { id: number; body: string; author: string; author_color?: string; username?: string; x_profile?: string | null; reactions_count: number; reacted: boolean; created_at: string; edited_at: string | null; is_owner: boolean; can_edit: boolean; hidden?: boolean; stance?: '' | 'positive' | 'doubt' | 'negative'; reactions?: Counts; my_reaction?: '' | Rating };
type CommentPage = { results: Comment[]; next_cursor: string | null; count: number };
export type RatingsData = { counts: Counts; mine: { polarity: Rating } | null };
/**
 * Pole „Skomentuj” (właściciel 3.10): krótki komentarz do 280 znaków albo dłuższy do 2000,
 * w którym jednym kliknięciem wstawia się odniesienie do boksu (@boks N) albo spinki (@spinka N).
 */
const COMMENT_SORTS = [{ value: 'best', label: 'Najtrafniejsze' }, { value: 'new', label: 'Najnowsze' }];
/** Kolejność komentarzy: sam tekst, rozwija się na tle motywu bez obramowania i zakrywa to, co pod spodem (właściciel 3.10). */
function CommentSort({ sort, setSort }: { sort: string; setSort: (value: string) => void }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const close = (event: Event) => { if (!(event.target as HTMLElement).closest?.('.sc-social-sort')) setOpen(false); };
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('click', close); window.addEventListener('keydown', key);
    return () => { document.removeEventListener('click', close); window.removeEventListener('keydown', key); };
  }, [open]);
  const label = COMMENT_SORTS.find(item => item.value === sort)?.label ?? COMMENT_SORTS[0].label;
  return <div className="sc-social-sort">
    <button type="button" aria-haspopup="listbox" aria-expanded={open} aria-label={`Kolejność komentarzy: ${label}`} onClick={() => setOpen(!open)}>{label} <span aria-hidden="true">⌄</span></button>
    {open && <ul role="listbox" aria-label="Kolejność komentarzy">{COMMENT_SORTS.map(item => <li key={item.value}>
      <button type="button" role="option" aria-selected={item.value === sort} onClick={() => { setSort(item.value); setOpen(false); }}>{item.label}</button></li>)}</ul>}
  </div>;
}

function Composer({ id, me, draft, setDraft, boxCount, pending, onSubmit, extra, end }: {
  id: number; me: string; draft: string; setDraft: (text: string) => void; boxCount: number; pending: boolean; onSubmit: () => void; extra?: ReactNode; end?: ReactNode;
}) {
  const [long, setLong] = useState(draft.length > 280);
  const refs = Array.from({ length: boxCount }, (_, i) => i === 0 ? [{ ref: '@b1', label: 'Boks 1' }] : [{ ref: `@s${i}`, label: `Spinka ${i}` }, { ref: `@b${i + 1}`, label: `Boks ${i + 1}` }]).flat();
  const insert = (ref: string) => setDraft(`${draft.trimEnd()} ${ref} `.trimStart());
  const limit = long ? 2000 : 280;
  return <form className={`sc-social-composer${long ? ' is-long' : ''}`} onSubmit={event => { event.preventDefault(); onSubmit(); }}>
    <Avatar name={me} />
    <div>
      {boxCount > 0 && <div className="sc-social-refs" aria-label="Odnieś się do boksu albo spinki">{refs.map(row => <button key={row.ref} type="button" title={row.label} onClick={() => insert(row.ref)}>{row.ref}</button>)}</div>}
      <label className="sc-sr-only" htmlFor={`compose-${id}`}>Skomentuj spinkę</label>
      {long ? <textarea id={`compose-${id}`} value={draft} maxLength={limit} rows={4} onChange={e => setDraft(e.target.value)} placeholder="Skomentuj. Przyciski nad polem dodają odnośnik do boksu (@b1) albo spinki (@s1)." />
        : <input id={`compose-${id}`} value={draft} maxLength={limit} onChange={e => setDraft(e.target.value)} placeholder="Skomentuj" />}
      <div className="sc-social-composer__row">
        <button type="button" className="sc-social-longtoggle" onClick={() => setLong(!long)}>{long ? 'Krótki komentarz' : 'Dłuższy komentarz'}</button>
        {extra}
        <CharacterCount text={draft} limit={limit} />
        <button type="submit" disabled={pending || !draft.trim()}>Skomentuj</button>
        {end && <span className="sc-social-composer__end">{end}</span>}
      </div>
    </div>
  </form>;
}

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
    <Dialog className="sc-social-report-dialog" open={open} onClose={() => setOpen(false)} title={commentId ? 'Zgłoś komentarz' : 'Zgłoś spinkę'}><form onSubmit={submit}>
      <label>Powód<select value={reason} onChange={e => setReason(e.target.value)}>{REPORT_REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}</select></label>
      <label>Opis<textarea maxLength={1000} value={details} onChange={e => setDetails(e.target.value)} /></label><CharacterCount text={details} limit={1000} />
      <button disabled={pending}>Wyślij zgłoszenie</button><p role="status">{status}</p>
    </form></Dialog>
  </span>;
}

export function ThreadSocial({ id, title, ai, expanded, preview = false, showComments, setShowComments, draft, setDraft, focusBox, boxCount, onCounts, onCommentCount, tools, filter, onClearFilter }: {
  /** Wybrany boks albo spinka: komentarze zawężone do jego odnośnika (@b1, @s1); sekcja zostaje w tym samym miejscu. */
  filter?: { ref: string; label: string; pattern: RegExp }; onClearFilter?: () => void;
  /** Dodatkowe akcje w pasku (otwarta spinka): kontraspinka, kopiowanie, eksport. */
  tools?: ReactNode;
  expanded?: boolean;
  /** Rozwinięty wiersz listy: 3 najtrafniejsze komentarze, „Pokaż wszystkie” i jedno pole „Odpowiedz”. */
  preview?: boolean;
  id: number; title: string; ai?: boolean; showComments: boolean; setShowComments: (value: boolean) => void;
  draft: string; setDraft: (text: string) => void; focusBox: (n: number) => void; boxCount: number;
  onCounts: (counts: Counts) => void; onCommentCount: (count: number) => void;
}) {
  const account = useAccount(), enabled = useFeature('ACCOUNTS_ENABLED'), threads = useFeature('THREADS_ENABLED');
  const canWrite = enabled && account.data?.authenticated && emailVerified(account.data);
  const me = account.data?.user?.username ?? 'Ty';
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
    return body.split(/(@(?:boks\s*|b)\d{1,3}\b|@(?:spinka\s*|s)\d{1,3}\b)/gi).map((part, index) => {
      const box = /^@(?:boks\s*|b)(\d+)$/i.exec(part), clip = /^@(?:spinka\s*|s)(\d+)$/i.exec(part), n = Number(box?.[1]);
      if (clip) return <span className="sc-social-chip sc-social-chip--clip" key={index} title={`Spinka ${clip[1]}`}>{part}</span>;
      return box && n > 0 && n <= boxCount ? <button className="sc-social-chip" key={index} title={`Boks ${n}`} onClick={() => focusBox(n)}>{part}</button> : part;
    });
  }
  /** Pierwsze zdanie komentarza w kolorze oceny, którą autor dał tropowi (✓ zielony, ? żółty, ✕ czerwony); reszta neutralna. */
  const commentLabels: Record<Rating, string> = { positive: 'Trafny', doubt: 'Wątpliwy', negative: 'Nietrafny' };
  /** Oceny komentarza od innych czytelników: trzy małe przyciski ✓ ? ✕ z liczbami; ponowne kliknięcie cofa ocenę. */
  function commentRating(row: Comment) {
    const counts = row.reactions ?? { positive: row.reactions_count ?? 0, doubt: 0, negative: 0 };
    return <div className="sc-comment-rate" role="group" aria-label="Oceń komentarz">
      {RATINGS.map(key => <button key={key} type="button" data-rating={key} aria-pressed={row.my_reaction === key}
        disabled={!canWrite || pending || row.is_owner || row.hidden} title={`${commentLabels[key]}: ${counts[key]}`} aria-label={`${commentLabels[key]}: ${counts[key]}`}
        onClick={() => write(`comments/${row.id}/reaction/`, row.my_reaction === key ? {} : { polarity: key }, row.my_reaction === key ? 'DELETE' : 'POST')}>
        <SocialIcon kind={key} /><span>{counts[key]}</span></button>)}
    </div>;
  }
  function stanced(row: Comment) { return content(row.body); }
  /** Stanowisko autora wobec tropu: mała kropka w kolorze jego oceny przy nazwie (✓ zielona, ? żółta, ✕ czerwona). */
  function stanceDot(row: Comment) {
    if (!row.stance) return null;
    const label = { positive: 'zgadza się', doubt: 'ma wątpliwości', negative: 'nie zgadza się' }[row.stance];
    return <span className="sc-stance-dot" data-stance={row.stance} title={`Autor ${label} ze spinką`} role="img" aria-label={`Autor ${label} ze spinką`} />;
  }
  useEffect(() => {
    const bare = /^\s*(@[bs]\d+\s*)?$/.test(draft);
    if (filter && bare) setDraft(`${filter.ref} `);
    if (!filter && bare && draft) setDraft('');
  }, [filter?.ref]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!threads) return null;
  if (preview) {
    const rows = comments.data?.pages[0]?.results.slice(0, 3) ?? [];
    const count = comments.data?.pages[0]?.count ?? 0;
    return <div className="sc-thread-social sc-thread-social--preview">
      <section aria-label="Najtrafniejsze komentarze" className="sc-social-comments sc-social-comments--preview">
        {canWrite ? <Composer id={id} me={me} draft={draft} setDraft={setDraft} boxCount={boxCount} pending={pending}
          onSubmit={async () => { if (await write('comments/', { body: draft })) { setDraft(''); setStatus('Komentarz dodany.'); } }} />
 : enabled ? <p className="sc-social-login"><a href="/konto">Zaloguj się</a>, aby skomentować.</p> : null}
        {comments.isLoading && <div className="sc-social-skeleton" aria-label="Ładowanie komentarzy" />}
        {comments.isSuccess && !rows.length && <p className="sc-social-empty">Nikt jeszcze nie skomentował. Bądź pierwszy.</p>}
        {rows.length > 0 && <ol>{rows.map(row => <li key={row.id} className="sc-cmt">
          <Avatar name={row.author} />
          <div className="sc-cmt__body">
            <header><strong style={row.author_color ? { color: row.author_color } : undefined}>{row.author}</strong>{stanceDot(row)}<span aria-hidden="true">·</span><time dateTime={row.created_at} title={new Date(row.created_at).toLocaleString('pl-PL')}>{ago(row.created_at)}</time></header>
            <ClampedText>{stanced(row)}</ClampedText>
            <footer>{commentRating(row)}</footer>
          </div>
        </li>)}</ol>}
        {count > 3 && <Link className="sc-social-all" href={`/spinki/${id}#komentarze`}>Pokaż wszystkie komentarze ({count})</Link>}
      </section>
      <p role="status">{status}</p>
    </div>;
  }
  async function share() {
    try { const url = `${location.origin}/spinki/${id}`; if (navigator.share) await navigator.share({ title, url }); else { await navigator.clipboard.writeText(url); setStatus('Skopiowano link.'); } }
    catch (error) { if (!(error instanceof Error && error.name === 'AbortError')) setStatus('Nie udało się udostępnić linku.'); }
  }
  // pasek akcji zniknął (właściciel 3.10): na razie tylko „Udostępnij” i „Zgłoś”, na skrajnej prawej w wierszu z „Skomentuj”;
  // „Zapisz”, „Przepnij spinkę” i „Kopiuj” czekają na nowe miejsce (tools zostaje w kodzie)
  void tools; void FollowButton;
  const end = <><button type="button" className="sc-social-share" onClick={() => void share()}>Udostępnij</button><SocialReport threadId={id} /></>;
  return <div className="sc-thread-social">
    {showRatings && <section aria-label="Ocena całej spinki" className="sc-social-ratings">
      {ratings.isLoading && <div className="sc-social-skeleton" aria-label="Ładowanie ocen" />}
      {ratings.isError && <button onClick={() => ratings.refetch()}>Ponów odczyt ocen</button>}
      {RATINGS.map(key => enabled ? <button key={key} data-rating={key} disabled={!canWrite || pending} aria-pressed={ratings.data?.mine?.polarity === key} onClick={() => rate(key)}>
        <SocialIcon kind={key} />{labels[key]}<span className="sc-social-rating-count">{ratings.data?.counts[key] ?? 0}</span>
      </button> : <span key={key} data-rating={key}><SocialIcon kind={key} />{labels[key]}: {ratings.data?.counts[key] ?? 0}</span>)}
      {enabled && !canWrite && <p><a href="/konto">Zaloguj się i potwierdź e-mail</a>, aby oceniać i komentować.</p>}
    </section>}
    {showComments && <section id="komentarze" aria-label="Komentarze pod spinką" className="sc-social-comments">
      {filter && <p className="sc-social-filter">Komentarze: {filter.label}<button type="button" onClick={onClearFilter}>pokaż wszystkie</button></p>}
      {canWrite ? <Composer id={id} me={me} draft={draft} setDraft={setDraft} boxCount={boxCount} pending={pending} extra={<CommentSort sort={sort} setSort={setSort} />} end={end}
        onSubmit={async () => { if (await write('comments/', { body: draft })) { setDraft(''); setStatus('Komentarz dodany.'); } }} />
        : <div className="sc-social-sortrow">{enabled && <p><a href="/konto">Zaloguj się i potwierdź e-mail</a>, aby dodać komentarz.</p>}<CommentSort sort={sort} setSort={setSort} /><span className="sc-social-composer__end">{end}</span></div>}
      {comments.isLoading && <div className="sc-social-skeleton" aria-label="Ładowanie komentarzy" />}
      {comments.isError && <button onClick={() => comments.refetch()}>Ponów odczyt komentarzy</button>}
      {comments.isSuccess && !comments.data.pages[0].results.length && <p><SocialIcon kind="comment" /> Bądź pierwszy.</p>}
      {filter && comments.isSuccess && !comments.data.pages.flatMap(page => page.results).some(row => filter.pattern.test(row.body)) && <p className="sc-social-empty">Nikt jeszcze nie skomentował: {filter.label}.</p>}
      <ol>{comments.data?.pages.flatMap(page => page.results).filter(row => !filter || filter.pattern.test(row.body)).map(row => <li key={row.id} id={`comment-${row.id}`} className="sc-cmt">
        <Avatar name={row.author} />
        <div className="sc-cmt__body">
        <header><strong style={row.author_color ? { color: row.author_color } : undefined}>{row.username ? <Link href={`/profile/${encodeURIComponent(row.username)}`} style={row.author_color ? { color: row.author_color } : undefined}>{row.author}</Link> : row.author}</strong>{row.x_profile && <a href={row.x_profile} target="_blank" rel="noopener noreferrer" aria-label="Połączone konto X">𝕏</a>}{stanceDot(row)}<span aria-hidden="true">·</span><time dateTime={row.created_at} title={new Date(row.created_at).toLocaleString('pl-PL')}>{ago(row.created_at)}</time>{row.edited_at && <small>edytowany</small>}</header>
        {row.hidden && <p>Ten komentarz jest ukryty. Treść widzisz jako autor.</p>}
        {editing === row.id ? <form onSubmit={async e => { e.preventDefault(); if (await write(`comments/${row.id}/`, { body: editBody }, 'PATCH')) setEditing(null); }}>
          <label>Edytuj komentarz<textarea value={editBody} maxLength={2000} onChange={e => setEditBody(e.target.value)} /></label><CharacterCount text={editBody} limit={2000} />
          <button disabled={pending || !editBody.trim()}>Zapisz</button><button type="button" onClick={() => setEditing(null)}>Anuluj</button>
        </form> : <ClampedText>{stanced(row)}</ClampedText>}
        <footer>{!row.hidden && commentRating(row)}{enabled && row.is_owner && <>{row.can_edit && <button onClick={() => { setEditing(row.id); setEditBody(row.body); }}>Edytuj</button>}<button disabled={pending} onClick={() => write(`comments/${row.id}/`, {}, 'DELETE')}>Usuń</button></>}
          {!row.hidden && <SocialReport threadId={id} commentId={row.id} />}</footer>
        </div>
      </li>)}</ol>
      {comments.hasNextPage && <button disabled={comments.isFetchingNextPage} onClick={() => comments.fetchNextPage()}>Pokaż kolejne komentarze</button>}
    </section>}
    <p role="status">{status}</p>
  </div>;
}
