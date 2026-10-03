"use client";

import { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { getCommunityThreads } from '../../lib/community';
import { ThreadStrip } from './ThreadStrip';

export type FeedSort = 'hot' | 'new' | 'best' | 'comments';
const SORTS: { value: FeedSort; label: string; hint: string }[] = [
  { value: 'hot', label: 'Najgorętsze', hint: 'Najwięcej ocen z ostatnich 7 dni, przy remisie najnowsze.' },
  { value: 'new', label: 'Najnowsze', hint: 'Od ostatnio opublikowanej.' },
  { value: 'best', label: 'Najlepiej oceniane', hint: 'Najwięcej ocen ✓, przy remisie najnowsze.' },
  { value: 'comments', label: 'Komentowane', hint: 'Od ostatniego komentarza.' },
];

/**
 * Jedna lista nitek: wiersz pod wierszem, cienkie separatory, nad listą jeden pasek sortowania.
 * Rozwinięta jest najwyżej jedna nitka; kolejne wiersze startują z przesunięciem, więc liczby w znaczkach
 * ✓ ? ✕ przechodzą falą przez listę, a nie migają naraz.
 */
export function ThreadFeed({ initialSort = 'hot', limit, term = '', context = {}, exclude, label = 'Tropy' }: {
  initialSort?: FeedSort; limit?: number; term?: string; context?: { article_id?: number; figure_id?: number; url?: string }; exclude?: number; label?: string;
}) {
  const [sort, setSort] = useState<FeedSort>(initialSort);
  const [openId, setOpenId] = useState<number | null>(null);
  const query = useInfiniteQuery({
    queryKey: ['community-threads', 'feed', sort, term, context],
    queryFn: ({ pageParam }) => getCommunityThreads(pageParam, term, '', { sort, ...context }),
    initialPageParam: 1,
    getNextPageParam: last => last.next_page ?? undefined,
    retry: false,
    staleTime: 60_000,
  });
  const all = (query.data?.pages.flatMap(page => page.results) ?? []).filter(thread => thread.id !== exclude);
  const threads = limit ? all.slice(0, limit) : all;
  const current = SORTS.find(item => item.value === sort)!;
  return <section className="sc-thread-feed" aria-label={label}>
    <div className="sc-thread-sortbar" role="tablist" aria-label="Kolejność tropów">
      {SORTS.map(item => <button key={item.value} type="button" role="tab" aria-selected={sort === item.value} title={item.hint}
        onClick={() => { setSort(item.value); setOpenId(null); }}>{item.label}</button>)}
    </div>
    <p className="sc-thread-sortbar__hint">{current.hint}</p>
    {query.isPending && <div className="sc-social-skeleton" aria-label="Ładowanie tropów" />}
    {query.isError && <p role="alert">Nie udało się pobrać tropów. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p>}
    {query.isSuccess && !threads.length && <p className="sc-thread-feed__empty">Nie ma jeszcze tropów w tym widoku.</p>}
    {threads.length > 0 && <ol className="sc-thread-feed__list">
      {threads.map((thread, index) => <li key={thread.id}>
        <ThreadStrip thread={thread} variant="row" open={openId === thread.id} offset={(index % 6) * 600}
          onOpenChange={value => setOpenId(value ? thread.id : null)} />
      </li>)}
    </ol>}
    {!limit && query.hasNextPage && <button type="button" className="sc-thread-feed__more" disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>Pokaż więcej tropów</button>}
  </section>;
}
