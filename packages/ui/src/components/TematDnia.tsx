"use client";

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { apiFetch } from '../lib/api';
import { getNewsFeed } from '../lib/portal';
import { categoryLabel } from '../lib/utils';
import type { Article } from '../types';

type DailyTopic = {
  query: string | null; label: string | null; mode: 'automatic' | 'unavailable';
  source_count: number; article_count: number;
};

type Moment = { key: string; time: string; articles: Article[] };
type RelatedLayout = 'auto' | 'compact' | 'expanded';

function TopicDayPlaceholder({ layout }: { layout: RelatedLayout }) {
  const compact = layout === 'compact';
  const rows = compact ? 2 : 3;
  const columns = compact ? 2 : 4;
  return (
    <div className={`mvp-evidence-table mvp-evidence-placeholder mvp-evidence-layout-${layout}`} aria-label="Przykładowy układ Tematu dnia">
      <div className="mvp-evidence-featured-media mvp-evidence-placeholder-media" />
      <div className="mvp-evidence-featured-copy mvp-evidence-placeholder-main">
        <span>NAJWAŻNIEJSZY MATERIAŁ</span>
        <strong>Temat dnia pojawi się, gdy źródła opiszą wspólne wydarzenie.</strong>
      </div>
      <div className="mvp-evidence-timeline" aria-label="Przykładowa oś czasu">
        {['XX:XX', 'XX:XX', 'XX:XX', 'XX:XX'].map((time, index) => <div key={`${time}-${index}`} className="mvp-evidence-moment"><span className="mvp-evidence-dot" aria-hidden="true" /><span>{time}</span></div>)}
      </div>
      <div className="mvp-evidence-updates" aria-label="Przykładowe aktualizacje">
        {['Krótka aktualizacja wydarzenia', 'Nowe doniesienie ze źródła', 'Kolejny istotny fakt', 'Materiał do sprawdzenia'].map((text, index) => <p key={index}>{text}</p>)}
      </div>
      <div className="mvp-evidence-event-lanes mvp-evidence-placeholder-related">
        {Array.from({ length: rows }, (_, row) => <div key={row}>{Array.from({ length: columns }, (_, column) => <span key={column} />)}</div>)}
      </div>
    </div>
  );
}

function buildMoments(articles: Article[]): Moment[] {
  const buckets = new Map<string, Article[]>();
  for (const article of articles) {
    if (!article.published_date) continue;
    const date = new Date(article.published_date);
    const hour = new Intl.DateTimeFormat('pl-PL', { timeZone: 'Europe/Warsaw', hour: '2-digit', hour12: false }).format(date).padStart(2, '0');
    const key = `${hour}:00`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key)!.push(article);
  }
  return [...buckets.entries()].map(([key, items]) => ({ key, time: key, articles: items }));
}

export function TematDnia() {
  const topic = useQuery({ queryKey: ['mvp-topic-of-day'], queryFn: () => apiFetch<DailyTopic>('/api/portal/topic-of-day/'),
    refetchInterval: 600_000, refetchIntervalInBackground: false, staleTime: 600_000 });
  const query = topic.data?.mode === 'automatic' ? topic.data.query : null;
  const materials = useQuery({ queryKey: ['mvp-topic-of-day-materials', query], queryFn: () => getNewsFeed({ query: query!, match: 'words', pageSize: 40 }), enabled: Boolean(query) });
  const articles = materials.data?.results ?? [];
  const moments = useMemo(() => buildMoments(articles), [articles]);
  const [selected, setSelected] = useState(0);
  const [relatedLayout, setRelatedLayout] = useState<RelatedLayout>('auto');
  const activeIndex = Math.min(selected, Math.max(0, moments.length - 1));

  const displayMoments = moments.slice(0, 4);

  const ready = Boolean(query) && moments.length >= 2 && articles.length >= 3;
  const main = articles[0];

  return (
    <section className="mvp-section mvp-temat-dnia" aria-label="Temat dnia">
      <header className="mvp-strip-heading">
        <h2>Temat dnia</h2>
        <div className="mvp-topic-heading-actions">
          {topic.data?.label && ready && <p>{topic.data.label}</p>}
          <div className="mvp-topic-layout-controls" aria-label="Układ materiałów Tematu dnia">
            <button type="button" className={relatedLayout === 'compact' ? 'is-active' : ''} aria-pressed={relatedLayout === 'compact'} aria-label="Widok zwarty: dwa rzędy po dwa materiały" title="Widok zwarty" onClick={() => setRelatedLayout(current => current === 'compact' ? 'auto' : 'compact')}><span className="mvp-topic-layout-icon mvp-topic-layout-icon-compact" aria-hidden="true">{Array.from({ length: 4 }, (_, index) => <i key={index} />)}</span></button>
            <button type="button" className={relatedLayout === 'expanded' ? 'is-active' : ''} aria-pressed={relatedLayout === 'expanded'} aria-label="Widok rozszerzony: trzy rzędy po cztery materiały" title="Widok rozszerzony" onClick={() => setRelatedLayout(current => current === 'expanded' ? 'auto' : 'expanded')}><span className="mvp-topic-layout-icon mvp-topic-layout-icon-expanded" aria-hidden="true">{Array.from({ length: 12 }, (_, index) => <i key={index} />)}</span></button>
          </div>
        </div>
      </header>
      {!ready ? (
        <>
          <TopicDayPlaceholder layout={relatedLayout} />
          <p role="status" className="mvp-strip-caption">
            {materials.isPending && query ? 'Sprawdzam materiały wspólnego tematu…' : 'Szukamy wspólnego tematu w różnych źródłach.'}
          </p>
        </>
      ) : (
        <div className={`mvp-evidence-table mvp-evidence-layout-${relatedLayout}`}>
          <Link href={`/material/${main.id}`} className="mvp-evidence-featured-media">
            {main.image_url ? <img src={main.image_url} alt="" /> : <span className="material-box-type">{categoryLabel(main.category)}</span>}
          </Link>
          <Link href={`/material/${main.id}`} className="mvp-evidence-featured-copy">
            <span className="mvp-evidence-source">{main.source.name} · {categoryLabel(main.category)}</span>
            <strong>{main.title}</strong>
            {main.description && <span>{main.description}</span>}
          </Link>
          <div className="mvp-evidence-timeline" role="listbox" aria-label="Oś czasu tematu dnia" tabIndex={0}
            onKeyDown={event => {
              if (event.key === 'ArrowUp') { event.preventDefault(); setSelected(current => Math.max(0, Math.min(current, moments.length - 1) - 1)); }
              if (event.key === 'ArrowDown') { event.preventDefault(); setSelected(current => Math.min(moments.length - 1, Math.min(current, moments.length - 1) + 1)); }
            }}>
            {displayMoments.map((moment, index) => (
              <button key={moment.key} type="button" role="option" aria-selected={index === activeIndex}
                className={`mvp-evidence-moment${index === activeIndex ? ' is-active' : ''}`} onClick={() => setSelected(index)}>
                <span className="mvp-evidence-dot" aria-hidden="true" />
                <span>{moment.time}</span>
              </button>
            ))}
          </div>
          <div className="mvp-evidence-updates" aria-label="Aktualizacje na osi czasu">
            {displayMoments.map((moment, index) => <p className={index === activeIndex ? 'is-active' : ''} key={moment.key}>{moment.articles[0]?.title ?? 'Aktualizacja wydarzenia'}</p>)}
          </div>
          <div className="mvp-evidence-event-lanes" aria-label="Materiały przypisane do wydarzeń na osi czasu">
            {displayMoments.map((moment, index) => (
              <div className={`mvp-evidence-event-row${index === activeIndex ? ' is-active' : ''}`} key={moment.key}>
                {moment.articles.slice(0, 2).map(article => <Link key={article.id} href={`/material/${article.id}`} className="mvp-evidence-event-material">
                  <span>{article.source.name} · {categoryLabel(article.category)}</span>
                  <strong>{article.title}</strong>
                </Link>)}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
