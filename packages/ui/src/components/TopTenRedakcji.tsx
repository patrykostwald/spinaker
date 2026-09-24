"use client";

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getNewsFeed } from '../lib/portal';
import type { Source } from '../types';
import { Button, Checkbox, NewsCard, SearchField } from '../kit';

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
    <section className="sc-top-ten" aria-label="Wszystkie źródła">
      <div className="sc-top-ten-bar">
        <div className="sc-top-ten-sources">
          <Button type="button" variant="quiet" aria-expanded={sourcesOpen} onClick={() => setSourcesOpen(value => !value)}>
            WSZYSTKIE ŹRÓDŁA <span aria-hidden="true">▾</span>
          </Button>
          {sourcesOpen && <div className="sc-top-ten-sources-menu" role="menu">
            <p className="sc-top-ten-sources-title">Filtruj źródła</p>
            {sources.map(source => (
              <Checkbox key={source.id} label={source.name} checked={sourceIds.includes(source.id)} onChange={() => setSourceIds(current => current.includes(source.id) ? current.filter(id => id !== source.id) : [...current, source.id])} />
            ))}
            {!sources.length && <p className="sc-top-ten-empty">Lista źródeł nie jest jeszcze dostępna.</p>}
          </div>}
        </div>
        <div className="sc-top-ten-categories">
          {TOPIC_PILLS.map(pill => (
            <Button key={pill.value} size="sm" variant="quiet" pressed={topic === pill.value}
              onClick={() => setTopic(topic === pill.value ? null : pill.value)}>{pill.label}</Button>
          ))}
        </div>
        <SearchField className="sc-top-ten-search" placeholder="Szukaj hasła…" value={query} onChange={setQuery} maxLength={200} />
      </div>
      {feed.isPending ? <p role="status" className="sc-top-ten-empty">Ładuję materiały ze źródeł…</p> : null}
      {feed.isError ? <p role="alert" className="sc-top-ten-empty">Nie udało się odświeżyć materiałów. <Button size="sm" variant="quiet" onClick={() => feed.refetch()}>Spróbuj ponownie</Button></p> : null}
      {!feed.isPending && !feed.isError && !articles.length ? <p className="sc-top-ten-empty">Nie ma jeszcze materiałów dla wybranych filtrów.</p> : null}
      {articles.length ? <div className="news-strip-track sc-strip-bleed" tabIndex={0} aria-label="Wszystkie źródła — przewijaj poziomo">
        {articles.map(article => <div key={article.id} className="news-strip-item"><NewsCard article={article} size="medium" /></div>)}
      </div> : null}
      <p className="sc-top-ten-caption">{`Najnowsze materiały z ${sourceSummary}${topicLabel ? ` · ${topicLabel}` : ''}${query ? ` · „${query}”` : ''}`}</p>
    </section>
  );
}
