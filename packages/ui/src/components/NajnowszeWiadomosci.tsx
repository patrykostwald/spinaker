"use client";

import { useQuery } from '@tanstack/react-query';
import { getNewsFeed } from '../lib/portal';
import { MaterialBox } from './MaterialBox';
import { MaterialStrip } from './MaterialStrip';

export function NajnowszeWiadomosci() {
  const feed = useQuery({ queryKey: ['mvp-latest'], queryFn: () => getNewsFeed({ mode: 'latest', pageSize: 30 }), refetchInterval: 20_000, refetchIntervalInBackground: false });
  const articles = feed.data?.results ?? [];
  return (
    <section className="mvp-section" aria-label="Najnowsze wiadomości">
      <header className="mvp-strip-heading"><h2>Najnowsze wiadomości</h2><p>Wszystkie aktywne źródła w bazie · od najnowszej publikacji</p></header>
      {feed.isPending && <p role="status" className="mvp-strip-empty">Ładuję materiały…</p>}
      {feed.isError && <p role="alert" className="mvp-strip-empty">Nie udało się odświeżyć materiałów. <button className="text-primary" onClick={() => feed.refetch()}>Ponów</button></p>}
      {!feed.isPending && !articles.length && !feed.isError && <p className="mvp-strip-empty">Nie ma jeszcze zaimportowanych materiałów.</p>}
      {!feed.isPending && <MaterialStrip label="Najnowsze wiadomości" height="sm">
        {articles.map(article => <MaterialBox key={article.id} article={article} />)}
      </MaterialStrip>}
    </section>
  );
}
