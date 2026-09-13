"use client";
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import type { Article } from '../types';
import { TopicArchiveStrip } from './TopicArchiveStrip';

type DailyTopic = {
  query: string | null; label: string | null; mode: 'automatic' | 'unavailable';
  source_count: number; article_count: number; window_hours: number;
  checked_at: string; method: string; note: string;
  covered_source_count: number; expected_source_count: number;
  sources: { id: number; name: string; has_recent_materials: boolean }[];
};

export function DailyTopicStrip({ onSelect }: { onSelect: (article: Article) => void }) {
  const topic = useQuery({ queryKey: ['portal-topic-of-day'], queryFn: () => apiFetch<DailyTopic>('/api/portal/topic-of-day/'),
    refetchInterval: 600_000, refetchIntervalInBackground: false, staleTime: 600_000 });
  const chosen = topic.data?.mode === 'automatic' && topic.data.query ? topic.data : null;
  return <section className="daily-topic-section" aria-label="Automatycznie wybrany temat dnia">
    {chosen ? <TopicArchiveStrip key={chosen.query} title={`Temat dnia · ${chosen.label}`} query={chosen.query!} onSelect={onSelect} />
      : <><header className="strip-heading"><h2>Temat dnia</h2></header><p role="status" className="strip-empty">{topic.isError ? 'Nie udało się sprawdzić wspólnego tematu źródeł.' : 'Szukamy wspólnego tematu — potrzebujemy wystarczających danych z różnych źródeł.'}</p></>}
    {chosen && <details className="daily-topic-method"><summary>Jak wybrano temat? · {chosen.source_count} źródeł TOP10</summary><p>{chosen.method}</p><p>{chosen.note}</p><p>Dostępne publikacje z ostatnich {chosen.window_hours} h: {chosen.covered_source_count} z {chosen.expected_source_count} redakcji. Materiały o wybranym temacie: {chosen.article_count}.</p>{chosen.sources.some(source => !source.has_recent_materials) && <p>Brak nowych materiałów w bazie: {chosen.sources.filter(source => !source.has_recent_materials).map(source => source.name).join(', ')}.</p>}</details>}
  </section>;
}
