"use client";

import { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { getCommunityThreads } from '../../lib/community';
import { useFeature } from '../../lib/features';
import { ThreadStrip } from './ThreadStrip';
import { ThreadOverlay } from './ThreadOverlay';
import { Button } from '../../kit/Button';

export type FeedSort = 'hot' | 'new' | 'best' | 'comments';
export type FeedSource = 'all' | 'drspin' | 'readers' | 'izba';
const SOURCES: { value: FeedSource; label: string }[] = [
  { value: 'all', label: 'Wszystkie' }, { value: 'drspin', label: 'Dr. Spin' }, { value: 'readers', label: 'Czytelnicy' }, { value: 'izba', label: 'Izba przyjęć' },
];
const SORTS: { value: FeedSort; label: string }[] = [
  { value: 'hot', label: 'Najgorętsze' }, { value: 'new', label: 'Najnowsze' }, { value: 'best', label: 'Najlepiej oceniane' }, { value: 'comments', label: 'Komentowane' },
];

/**
 * Jedna lista tropów. Pasek: zakładki źródła (co oglądam) i obok ciche sortowanie (jak). Bez filtra obozów:
 * ta sama miara dla wszystkich. Izba przyjęć: nowe tropy czytelników przed awansem na główną (news/admission.py).
 */
export function ThreadFeed({ initialSort = 'hot', limit, term = '', context = {}, exclude, label = 'Tropy' }: {
  initialSort?: FeedSort; limit?: number; term?: string; context?: { article_id?: number; figure_id?: number; url?: string }; exclude?: number; label?: string;
}) {
  const accounts = useFeature('ACCOUNTS_ENABLED');
  const [sort, setSort] = useState<FeedSort>(initialSort);
  const [source, setSource] = useState<FeedSource>('all');
  const [openId, setOpenId] = useState<number | null>(null);
  const [fullId, setFullId] = useState<number | null>(null);
  const query = useInfiniteQuery({
    queryKey: ['community-threads', 'feed', source, sort, term, context],
    queryFn: ({ pageParam }) => getCommunityThreads(pageParam, term, '', { source, sort, ...context }),
    initialPageParam: 1,
    getNextPageParam: last => last.next_page ?? undefined,
    retry: false,
    staleTime: 60_000,
  });
  const all = (query.data?.pages.flatMap(page => page.results) ?? []).filter(thread => thread.id !== exclude);
  const threads = limit ? all.slice(0, limit) : all;
  return <section className="sc-thread-feed" aria-label={label}>
    <div className="sc-thread-sortbar">
      <div role="tablist" aria-label="Źródło tropów" className="sc-thread-sortbar__tabs">
        {SOURCES.map(item => <button key={item.value} type="button" role="tab" aria-selected={source === item.value}
          onClick={() => { setSource(item.value); setOpenId(null); }}>{item.label}</button>)}
      </div>
      <label className="sc-thread-sortbar__sort"><span className="sc-sr-only">Kolejność</span>
        <select value={sort} onChange={event => { setSort(event.target.value as FeedSort); setOpenId(null); }}>
          {SORTS.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      </label>
    </div>
    {source === 'izba' && <p className="sc-thread-sortbar__hint">Nowe tropy czytelników. Na główną przechodzi trop, który w 7 dni zbierze 10 ocen ✓ i co najmniej 60% poparcia.</p>}
    {query.isPending && <div className="sc-social-skeleton" aria-label="Ładowanie tropów" />}
    {query.isError && <p role="alert" className="sc-thread-feed__empty">Nie udało się pobrać tropów. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p>}
    {query.isSuccess && !threads.length && (source === 'izba'
      ? <div className="sc-thread-feed__izba">
          <p className="sc-thread-feed__izba-title">Izba przyjęć czeka na pierwsze tropy</p>
          <p>Tu trafia każdy nowy trop czytelnika. Twoje oceny ✓ ? ✕ decydują, co przejdzie na główną.</p>
          {accounts && <Button href="/konto/tropy/nowa" variant="secondary" size="sm">Ułóż swój trop</Button>}
        </div>
      : <p className="sc-thread-feed__empty">{source === 'readers' ? 'Pierwsze tropy czytelników pojawią się tu po przejściu przez izbę przyjęć.' : 'Nie ma jeszcze tropów w tym widoku.'}</p>)}
    {threads.length > 0 && <ol className="sc-thread-feed__list">
      {threads.map((thread, index) => <li key={thread.id}>
        <ThreadStrip thread={thread} variant="row" open={openId === thread.id} offset={(index % 6) * 600}
          onOpenChange={value => setOpenId(value ? thread.id : null)} onFullscreen={() => setFullId(thread.id)} />
      </li>)}
    </ol>}
    {fullId !== null && <ThreadOverlay id={fullId} onClose={() => setFullId(null)} />}
    {!limit && query.hasNextPage && <button type="button" className="sc-thread-feed__more" disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>Pokaż więcej tropów</button>}
  </section>;
}
