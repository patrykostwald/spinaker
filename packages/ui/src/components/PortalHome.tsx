"use client";
import { useMemo, useState } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { getMe } from '../lib/api';
import { getNewsFeed, getPortalConfig, type CategoryOption } from '../lib/portal';
import { formatDateTimePl } from '../lib/utils';
import type { Article, Source, ThreadDetail } from '../types';
import { HorizontalTimeline } from './HorizontalTimeline';
import { ArchiveProgress } from './ArchiveProgress';
import { ArticleCard } from './ArticleCard';
import { ArticleModal } from './ArticleModal';
import { NewsStrip } from './NewsStrip';
import { PersonalizedNews } from './PersonalizedNews';
import { ThreadExport } from './ThreadExport';
import { MaterialFilters, emptySelection } from './MaterialFilters';
import { ThreadFavoriteButton } from './ThreadFavoriteButton';
import { EmptyNarrativeStrip } from './EmptyNarrativeStrip';
import { DailyTopicStrip } from './DailyTopicStrip';

function EditorialSection({ title, thread, loading, error }: { title: string; thread: ThreadDetail | null | undefined; loading: boolean; error: boolean }) {
  const published = thread?.published ? thread : null;
  return <section className="editorial-transmission"><header className="strip-heading"><div><p className="editorial-byline">SPIN.CLINIC · REDAKCJA</p><h2>{title}</h2></div>{published && <div className="flex gap-2"><ThreadFavoriteButton thread={published} /><Link href={`/thread/${published.slug}`} className="quiet-button">Otwórz nitkę ↗</Link></div>}</header>
    {loading ? <p role="status" className="strip-empty">Ładuję przekaz redakcyjny…</p> : error ? <p role="status" className="strip-empty">Nie udało się pobrać nitek redakcyjnych.</p> : published ? <><h3 className="editorial-thread-title"><Link href={`/thread/${published.slug}`}>{published.title}</Link></h3>{published.description && <p className="editorial-description">{published.description}</p>}<HorizontalTimeline items={published.items} anchorFirst /><details className="thread-export-disclosure"><summary>Przygotuj całą nitkę do publikacji na X</summary><ThreadExport thread={published} /></details></> : <><p className="sr-only">Redakcja nie opublikowała jeszcze nitki w tej sekcji.</p><EmptyNarrativeStrip /></>}
  </section>;
}

function LiveNewsGrid({ categories, topics, sources, onSelect }: { categories: CategoryOption[]; topics: CategoryOption[]; sources: Source[]; onSelect: (article: Article) => void }) {
  const [selected, setSelected] = useState(emptySelection);
  const feed = useInfiniteQuery({ queryKey: ['live-news-grid', selected.categories.join(','), selected.topics.join(','), selected.sources.join(',')], initialPageParam: 1,
    queryFn: ({ pageParam }) => getNewsFeed({ ...selected, page: pageParam, pageSize: 24 }),
    getNextPageParam: last => last.next_page ?? undefined, refetchInterval: 30_000, refetchIntervalInBackground: false });
  const articles = useMemo(() => [...new Map((feed.data?.pages.flatMap(page => page.results) ?? []).map(article => [article.id, article])).values()], [feed.data]);
  const first = feed.data?.pages[0];
  return <section className="live-news-section">
    <header className="strip-heading"><div><h2><span className="live-dot" aria-label="Aktualizowane na żywo" />Wszystkie wiadomości</h2><p>Najnowsze publikacje ze źródeł w naszej bazie</p></div>{first && <span className="feed-updated">Odświeżono {formatDateTimePl(first.checked_at)}</span>}</header>
    <div className="live-news-layout"><aside className="news-filters"><MaterialFilters categories={categories} topics={topics} sources={sources} value={selected} onChange={setSelected} /><Link href="/search" className="filter-archive-link">Szukaj w całym archiwum ↗</Link></aside>
      <div className="min-w-0">{feed.isPending && <p role="status" className="strip-empty">Ładuję wiadomości…</p>}{feed.isError && <p role="alert" className="strip-empty">Nie udało się odświeżyć wiadomości. <button onClick={() => feed.refetch()} className="text-primary">Ponów</button></p>}{feed.isSuccess && !articles.length && <p className="strip-empty">Brak materiałów w wybranych kategoriach.</p>}
        <div className="live-news-grid">{articles.map(article => <ArticleCard key={article.id} article={article} onSelect={onSelect} />)}</div>
        {feed.hasNextPage && <button disabled={feed.isFetchingNextPage} onClick={() => feed.fetchNextPage()} className="load-news-button">{feed.isFetchingNextPage ? 'Ładuję kolejne materiały…' : 'Pokaż wcześniejsze publikacje ↓'}</button>}
      </div>
    </div>
  </section>;
}

export function PortalHome() {
  const [selected, setSelected] = useState<Article | null>(null);
  const support = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false });
  const config = useQuery({ queryKey: ['portal-config'], queryFn: getPortalConfig, refetchInterval: 60_000, refetchIntervalInBackground: false });
  const latest = useQuery({ queryKey: ['latest-news-strip'], queryFn: () => getNewsFeed({ pageSize: 20 }), refetchInterval: 15_000, refetchIntervalInBackground: false });
  const top = useQuery({ queryKey: ['top-news-strip'], queryFn: () => getNewsFeed({ mode: 'top', pageSize: 20 }), refetchInterval: 30_000, refetchIntervalInBackground: false });
  const categories = config.data?.categories ?? [];
  return <div className="portal-home portal-live"><h1 className="sr-only">Wiadomości i ich kontekst</h1>
    <NewsStrip title="Najnowsze" eyebrow="Wszystkie źródła w bazie · od najnowszej publikacji" large live articles={latest.data?.results ?? []} loading={latest.isPending} error={latest.isError} onRetry={() => latest.refetch()} onSelect={setSelected} empty="Nie ma jeszcze zaimportowanych materiałów." />
    <NewsStrip title="Dziś · TOP10" eyebrow="Wybór redakcji źródeł · dzisiejsze publikacje" articles={top.data?.results ?? []} loading={top.isPending} error={top.isError} onRetry={() => top.refetch()} onSelect={setSelected} empty="Nie ma jeszcze dzisiejszych publikacji z wybranych źródeł w naszej bazie." controls={(top.data?.top_sources ?? config.data?.top_sources)?.length ? <details className="top-sources"><summary>Lista źródeł</summary><div>{(top.data?.top_sources ?? config.data?.top_sources)?.map(source => <a key={source.id} href={source.url} target="_blank" rel="noopener noreferrer">{source.name} ↗</a>)}</div></details> : null} />
    <DailyTopicStrip onSelect={setSelected} />
    <PersonalizedNews categories={categories} topics={config.data?.topics ?? []} sources={config.data?.sources ?? []} onSelect={setSelected} />
    <div className="editorial-pair"><EditorialSection title="PRZEKAZ DNIA OBOZU RZĄDZĄCEGO" thread={config.data?.editorial.government} loading={config.isPending} error={config.isError} /><EditorialSection title="PRZEKAZ DNIA OPOZYCJI" thread={config.data?.editorial.opposition} loading={config.isPending} error={config.isError} /></div>
    <section className="sponsored-layout" aria-label="Przykład pustego układu sponsorowanego"><header className="strip-heading"><p className="sponsorship-badge">PRZYKŁAD UKŁADU SPONSOROWANEGO</p></header><EmptyNarrativeStrip /></section>
    <LiveNewsGrid categories={categories} topics={config.data?.topics ?? []} sources={config.data?.sources ?? []} onSelect={setSelected} />
    <footer className="portal-footer"><p>Materiały prezentujemy w oryginalnym kontekście źródłowym. Zestawienie publikacji i opinie czytelników nie są potwierdzeniem zawartych w nich twierdzeń.</p><div className="footer-links"><Link href="/search">Przeszukaj archiwum ↗</Link>{support.data?.patronite_url && <a href={support.data.patronite_url} target="_blank" rel="noopener noreferrer">Patronite ↗</a>}{support.data?.buycoffee_url && <a href={support.data.buycoffee_url} target="_blank" rel="noopener noreferrer">Postaw kawę ↗</a>}</div><details className="archive-disclosure"><summary>Jak rozwija się baza źródeł?</summary><ArchiveProgress /></details></footer>
    <ArticleModal article={selected} onClose={() => setSelected(null)} />
  </div>;
}
