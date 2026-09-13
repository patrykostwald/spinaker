"use client";
import { useMemo, useState } from 'react';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { getNewsFeed, type NewsFeed } from '../lib/portal';
import type { Article } from '../types';
import { NewsStrip } from './NewsStrip';

export function TopicArchiveStrip({ title, query, onSelect }: { title: string; query: string; onSelect: (article: Article) => void }) {
  const cache = useQueryClient();
  const [acceptedHead, setAcceptedHead] = useState<NewsFeed | null>(null);
  const headKey = ['topic-archive-head', query];
  const loadHead = () => getNewsFeed({ query, page: 1, pageSize: 20, match: 'words' });
  const feed = useInfiniteQuery({
    queryKey: ['topic-archive-strip', query], initialPageParam: 1,
    queryFn: ({ pageParam }) => pageParam === 1
      ? cache.fetchQuery({ queryKey: headKey, queryFn: loadHead, staleTime: 30_000 })
      : getNewsFeed({ query, page: pageParam, pageSize: 20, match: 'words' }),
    getNextPageParam: last => last.next_page ?? undefined,
    // Only the head is polled; already-read archive pages stay in place.
    refetchOnWindowFocus: false, refetchOnReconnect: false,
  });
  const head = useQuery({ queryKey: headKey, queryFn: loadHead, enabled: feed.isSuccess,
    staleTime: 30_000, refetchInterval: 30_000, refetchIntervalInBackground: false });
  const displayedHead = acceptedHead ?? feed.data?.pages[0];
  const pendingUpdate = Boolean(head.data && displayedHead
    && head.data.results.map(article => article.id).join(',') !== displayedHead.results.map(article => article.id).join(','));
  const articles = useMemo(() => {
    const all = [...(acceptedHead?.results ?? []), ...(feed.data?.pages.flatMap(page => page.results) ?? [])];
    const unique = [...new Map(all.slice().reverse().map(article => [article.id, article])).values()];
    return unique.sort((a, b) => {
      const aTime = a.published_date ? Date.parse(a.published_date) : -Infinity;
      const bTime = b.published_date ? Date.parse(b.published_date) : -Infinity;
      return bTime - aTime || b.id - a.id;
    });
  }, [acceptedHead, feed.data]);
  return <div className="topic-archive-strip">
    <NewsStrip title={title} eyebrow="Wybrany temat · wszystkie źródła w bazie · bez ograniczenia dat"
      articles={articles} onSelect={onSelect} loading={feed.isPending} error={feed.isError}
      onRetry={() => feed.refetch()} empty="Nie ma jeszcze materiałów dotyczących tego tematu w bazie."
      controls={pendingUpdate ? <button className="quiet-button" onClick={() => setAcceptedHead(head.data ?? null)}>Pokaż nowe materiały ↑</button> : undefined} />
    {head.isError && feed.isSuccess && <p role="status" className="topic-archive-status">Nie udało się sprawdzić nowych materiałów. Wcześniej pobrane pozostają dostępne.</p>}
    {feed.hasNextPage && <button className="load-news-button" disabled={feed.isFetchingNextPage} onClick={() => feed.fetchNextPage()}>{feed.isFetchingNextPage ? 'Ładuję wcześniejsze materiały…' : `Pokaż wcześniejsze publikacje · ${title} ←`}</button>}
  </div>;
}
