"use client";

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getNewsFeed } from '../lib/portal';
import type { Source } from '../types';
import { NewsCard } from '../kit/NewsCard';

const TOPIC_PILLS: { label: string; value: string }[] = [
  { label: 'Polityka', value: 'polityka' },
  { label: 'Polska', value: 'polska' },
  { label: 'Świat', value: 'swiat' },
  { label: 'Gospodarka', value: 'biznes' },
  { label: 'Społeczeństwo', value: 'spoleczenstwo' },
  { label: 'Zdrowie', value: 'zdrowie' },
  { label: 'Technologie', value: 'technologie' },
  { label: 'Prawo', value: 'prawo' },
];

export function TopTenRedakcji({ topSources: sources }: { topSources: Source[] }) {
  const [topic, setTopic] = useState<string | null>(null);
  const [sourceIds, setSourceIds] = useState<number[]>([]);
  const [query, setQuery] = useState('');
  const [sourcesOpen, setSourcesOpen] = useState(false);

  const topics = topic ? [topic] : [];
  const feed = useQuery({
    queryKey: ['mvp-all-sources', topic, sourceIds.join(','), query],
    queryFn: () => getNewsFeed({ mode: 'latest', topics, sources: sourceIds, query, pageSize: 10 }),
    refetchInterval: 30_000, refetchIntervalInBackground: false,
  });
  const articles = useMemo(() => feed.data?.results ?? [], [feed.data]);
  const selectedSources = sources.filter(source => sourceIds.includes(source.id));
  const sourceSummary = selectedSources.length
    ? selectedSources.length <= 2
      ? selectedSources.map(source => source.name).join(' · ')
      : `${selectedSources.slice(0, 2).map(source => source.name).join(' · ')} +${selectedSources.length - 2}`
    : 'wszystkich aktywnych źródeł';
  const topicLabel = TOPIC_PILLS.find(pill => pill.value === topic)?.label;

  return (
    <section className="mvp-section mvp-top10" aria-label="Wszystkie źródła">
      <div className="mvp-top10-bar">
        <div className="mvp-sources-dropdown">
          <button type="button" className="mvp-top10-title" aria-expanded={sourcesOpen} onClick={() => setSourcesOpen(value => !value)}>
            WSZYSTKIE ŹRÓDŁA <span aria-hidden="true">▾</span>
          </button>
          {sourcesOpen && <div className="mvp-sources-menu" role="menu">
            <p className="mvp-sources-menu-title">Filtruj źródła</p>
            {sources.map(source => (
              <label key={source.id}>
                <input type="checkbox" checked={sourceIds.includes(source.id)}
                  onChange={() => setSourceIds(current => current.includes(source.id) ? current.filter(id => id !== source.id) : [...current, source.id])} />
                {source.name}
              </label>
            ))}
            {!sources.length && <p className="filter-note">Lista źródeł nie jest jeszcze dostępna.</p>}
          </div>}
        </div>
        <div className="mvp-top10-categories">
          {TOPIC_PILLS.map(pill => (
            <button key={pill.value} type="button" className={`mvp-pill${topic === pill.value ? ' is-active' : ''}`}
              aria-pressed={topic === pill.value} onClick={() => setTopic(topic === pill.value ? null : pill.value)}>{pill.label}</button>
          ))}
        </div>
          <input type="search" className="mvp-search-input" placeholder="Szukaj hasła…" value={query} onChange={event => setQuery(event.target.value)} maxLength={200} />
      </div>
      {feed.isPending ? <p role="status" className="strip-empty">Ładuję materiały ze źródeł…</p> : null}
      {feed.isError ? <p role="alert" className="strip-empty">Nie udało się odświeżyć materiałów. <button type="button" className="text-primary" onClick={() => feed.refetch()}>Spróbuj ponownie</button></p> : null}
      {!feed.isPending && !feed.isError && !articles.length ? <p className="strip-empty">Nie ma jeszcze materiałów dla wybranych filtrów.</p> : null}
      {articles.length ? <div className="news-strip-track sc-strip-bleed" tabIndex={0} aria-label="Wszystkie źródła — przewijaj poziomo">
        {articles.map(article => <div key={article.id} className="news-strip-item"><NewsCard article={article} size="medium" /></div>)}
      </div> : null}
      <p className="mvp-strip-caption">{`Najnowsze materiały z ${sourceSummary}${topicLabel ? ` · ${topicLabel}` : ''}${query ? ` · „${query}”` : ''}`}</p>
    </section>
  );
}
