"use client";

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useInfiniteQuery } from '@tanstack/react-query';
import { getCommunityThreads } from '../../lib/community';
import { useFeature } from '../../lib/features';
import { ThreadStrip } from './ThreadStrip';
import { ThreadOverlay, viewTransition } from './ThreadOverlay';
import { Button } from '../../kit/Button';
import { Loading } from "../../kit/Loading";

export type FeedSort = 'hot' | 'new' | 'best' | 'comments';
export type FeedSource = 'all' | 'drspin' | 'readers' | 'izba';
const SOURCES: FeedSource[] = ['all', 'drspin', 'readers', 'izba'];
const SORTS: FeedSort[] = ['hot', 'new', 'best', 'comments'];

/**
 * Jedna lista tropów. Źródło i kolejność wybiera się w pasku kategorii nad treścią (SectionBar, ?zrodlo= i ?sort=). Bez filtra obozów:
 * ta sama miara dla wszystkich. Izba przyjęć: nowe tropy czytelników przed awansem na główną (news/admission.py).
 */
export function ThreadFeed({ initialSort = 'hot', limit, term = '', context = {}, exclude, label = 'Spinki' }: {
  initialSort?: FeedSort; limit?: number; term?: string; context?: { article_id?: number; figure_id?: number; url?: string }; exclude?: number; label?: string;
}) {
  const accounts = useFeature('ACCOUNTS_ENABLED');
  const params = useSearchParams();
  const sort = SORTS.find(value => value === params?.get('sort')) ?? initialSort;
  const source = SOURCES.find(value => value === params?.get('zrodlo')) ?? 'all';
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
    {source === 'izba' && <p className="sc-thread-sortbar__hint">Nowe spinki czytelników. Na główną przechodzi spinka, którą ktoś skomentuje albo oceni.</p>}
    {query.isPending && <Loading label="Ładowanie spinek" />}
    {query.isError && <p role="alert" className="sc-thread-feed__empty">Nie udało się pobrać spinek. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p>}
    {query.isSuccess && !threads.length && (source === 'izba'
      ? <div className="sc-thread-feed__izba">
          <p className="sc-thread-feed__izba-title">Izba przyjęć czeka na pierwsze spinki</p>
          <p>Tu trafia każda nowa spinka czytelnika. Twoje oceny ✕ ? ✓ decydują, co przejdzie na główną.</p>
          {accounts && <Button href="/konto/spinki/nowa" variant="secondary" size="sm">Ułóż swoją spinkę</Button>}
        </div>
      : <p className="sc-thread-feed__empty">{source === 'readers' ? 'Pierwsze spinki czytelników pojawią się tu po przejściu przez izbę przyjęć.' : 'Nie ma jeszcze spinek w tym widoku.'}</p>)}
    {threads.length > 0 && <ol className="sc-thread-feed__list">
      {threads.map((thread, index) => <li key={thread.id}>
        <ThreadStrip thread={thread} variant="row" open={openId === thread.id} offset={(index % 6) * 600}
          onOpenChange={value => setOpenId(value ? thread.id : null)} onFullscreen={() => viewTransition(() => setFullId(thread.id))} />
      </li>)}
    </ol>}
    {fullId !== null && <ThreadOverlay id={fullId} order={threads.map(thread => thread.id)} onClose={() => viewTransition(() => setFullId(null))} />}
    {!limit && query.hasNextPage && <button type="button" className="sc-thread-feed__more" disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>Pokaż więcej spinek</button>}
  </section>;
}
