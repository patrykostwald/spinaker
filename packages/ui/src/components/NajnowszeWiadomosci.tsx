"use client";

import { useQuery } from '@tanstack/react-query';
import { getNewsFeed } from '../lib/portal';
import { NewsStrip } from './NewsStrip';

export function NajnowszeWiadomosci() {
  const feed = useQuery({ queryKey: ['mvp-latest'], queryFn: () => getNewsFeed({ mode: 'latest', pageSize: 30 }), refetchInterval: 20_000, refetchIntervalInBackground: false });
  const articles = feed.data?.results ?? [];
  return (
    <NewsStrip
      title="Najnowsze wiadomości"
      eyebrow="Wszystkie aktywne źródła w bazie · od najnowszej publikacji"
      articles={articles}
      loading={feed.isPending}
      error={feed.isError}
      onRetry={() => feed.refetch()}
      empty="Nie ma jeszcze zaimportowanych materiałów."
      large
      live
    />
  );
}
