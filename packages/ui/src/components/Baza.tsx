"use client";

import { forwardRef, useEffect, useMemo, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { getNewsFeed } from '../lib/portal';
import type { CategoryOption } from '../lib/portal';
import type { Source } from '../types';
import { EmptyMaterialSlot, MaterialBox } from './MaterialBox';
import { TwojePaski } from './TwojePaski';
import { Button, SearchField } from '../kit';

const PERIODS: { value: string; label: string; hours: number | null }[] = [
  { value: 'all', label: 'Zawsze', hours: null },
  { value: '24h', label: 'Ostatnie 24 godziny', hours: 24 },
  { value: '7d', label: 'Ostatnie 7 dni', hours: 24 * 7 },
  { value: '30d', label: 'Ostatnie 30 dni', hours: 24 * 30 },
];

const IMPORTANT_SOURCE_NAMES = /pap|reuters|tvn|polsat|wyborcza|oko\.press|rp\.pl|gazeta|onet|interia/i;
const PUBLIC_SOURCE_TYPES = /public|official|government|parliament|sejm|institution|minister|urzad/i;

function groupSources(sources: Source[]) {
  const groups = { important: [] as Source[], media: [] as Source[], public: [] as Source[] };
  for (const source of sources) {
    if (IMPORTANT_SOURCE_NAMES.test(source.name) || /top|major|featured/i.test(source.source_type)) groups.important.push(source);
    else if (PUBLIC_SOURCE_TYPES.test(source.source_type) || /sejm|minister|urz[ąa]d|gov\.pl|główny urząd/i.test(source.name)) groups.public.push(source);
    else groups.media.push(source);
  }
  return groups;
}

function SourceTree({ groups, selectedSources, onToggle }: {
  groups: ReturnType<typeof groupSources>; selectedSources: number[]; onToggle: (id: number) => void;
}) {
  const labels = { important: 'Największe media', media: 'Media', public: 'Publiczne' } as const;
  return <div className="mvp-source-tree">
    {(Object.keys(labels) as Array<keyof typeof labels>).map(key => groups[key].length > 0 && <details key={key} className="mvp-source-group">
      <summary>{labels[key]} <span>{groups[key].length}</span></summary>
      <div className="source-filter-options category-options">{groups[key].map(source => (
        <label key={source.id} className={source.is_active === false ? 'is-catalog-candidate' : ''}>
          <input type="checkbox" checked={selectedSources.includes(source.id)} onChange={() => onToggle(source.id)} />
          <span>{source.name}</span>{source.is_active === false && <small>Katalog</small>}
        </label>
      ))}</div>
    </details>)}
  </div>;
}

const EMPTY_TYPES = ['ARTYKUŁ', 'WYWIAD', 'REPORTAŻ', 'ŚLEDZTWO', 'DOKUMENT URZĘDOWY', 'REKLAMA', 'FILM', 'ARTYKUŁ'];
const BASE_INITIAL_SLOTS = 30;

export const Baza = forwardRef<HTMLDivElement, { categories: CategoryOption[]; sources: Source[]; initialQuery: string }>(
  function Baza({ categories, sources, initialQuery }, ref) {
    const [query, setQuery] = useState(initialQuery);
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
    const [selectedSources, setSelectedSources] = useState<number[]>([]);
    const [selectedPlatforms, setSelectedPlatforms] = useState<('youtube')[]>([]);
    const [period, setPeriod] = useState('all');
    const [sourceSearch, setSourceSearch] = useState('');
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [sourcePickerOpen, setSourcePickerOpen] = useState(false);
    const loadMoreRef = useRef<HTMLDivElement>(null);

    useEffect(() => { setQuery(initialQuery); }, [initialQuery]);

    const feed = useInfiniteQuery({
      queryKey: ['mvp-baza', query, selectedCategories.join(','), selectedSources.join(','), selectedPlatforms.join(',')],
      initialPageParam: 1,
      queryFn: ({ pageParam }) => getNewsFeed({ query, categories: selectedCategories, sources: selectedSources, platforms: selectedPlatforms, page: pageParam, pageSize: BASE_INITIAL_SLOTS }),
      getNextPageParam: last => last.next_page ?? undefined,
    });

    const allArticles = useMemo(() => [...new Map((feed.data?.pages.flatMap(page => page.results) ?? []).map(article => [article.id, article])).values()], [feed.data]);
    const periodHours = PERIODS.find(item => item.value === period)?.hours ?? null;
    const articles = useMemo(() => {
      if (!periodHours) return allArticles;
      const cutoff = Date.now() - periodHours * 3_600_000;
      return allArticles.filter(article => article.published_date && new Date(article.published_date).getTime() >= cutoff);
    }, [allArticles, periodHours]);

    const visibleSources = sources.filter(source => source.name.toLocaleLowerCase('pl').includes(sourceSearch.toLocaleLowerCase('pl')));
    const sourceGroups = groupSources(visibleSources);
    const activeFilterCount = selectedCategories.length + selectedSources.length + selectedPlatforms.length + (period !== 'all' ? 1 : 0);
    const emptySlotCount = Math.max(0, BASE_INITIAL_SLOTS - articles.length);
    const toggleSource = (id: number) => setSelectedSources(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]);

    useEffect(() => {
      const target = loadMoreRef.current;
      if (!target || !feed.hasNextPage || feed.isFetchingNextPage) return;
      const observer = new IntersectionObserver(([entry]) => {
        if (entry.isIntersecting) feed.fetchNextPage();
      }, { rootMargin: '800px 0px' });
      observer.observe(target);
      return () => observer.disconnect();
    }, [feed.fetchNextPage, feed.hasNextPage, feed.isFetchingNextPage]);

    return (
      <section ref={ref} className="sc-base" aria-label="Baza materiałów">
        <header className="sc-base-head"><h2>Baza</h2><p>Przeszukaj wszystkie materiały w bazie</p></header>
        <TwojePaski categories={categories} sources={sources} openSignal={0} />
        <div className="sc-base-latest-heading">
          <h3>Najnowsze materiały</h3>
          <p>Wszystkie aktywne źródła · od najnowszej publikacji</p>
        </div>
        <form className="sc-base-search" onSubmit={event => { event.preventDefault(); }}>
          <SearchField value={query} onChange={setQuery} placeholder="Szukaj w bazie…" label="Szukaj w bazie" maxLength={200} />
        </form>
        <Button type="button" variant="secondary" className="sc-base-filters-toggle" onClick={() => setFiltersOpen(value => !value)} aria-expanded={filtersOpen}>
          Filtry {activeFilterCount > 0 ? `· ${activeFilterCount}` : ''} ▾
        </Button>
        <div className="sc-base-layout">
          <div className="sc-base-results">
            {feed.isPending && <p role="status" className="sc-base-empty">Ładuję materiały…</p>}
            {feed.isError && <p role="alert" className="sc-base-empty">Nie udało się odświeżyć bazy. <Button size="sm" variant="quiet" onClick={() => feed.refetch()}>Ponów</Button></p>}
            {feed.isSuccess && !articles.length && <p className="sc-base-empty">Brak materiałów pasujących do wybranych filtrów.</p>}
            <div className="sc-base-grid" aria-label="Najnowsze materiały w Bazie">
              {articles.map(article => <MaterialBox key={article.id} article={article} />)}
              {Array.from({ length: emptySlotCount }, (_, index) => <EmptyMaterialSlot key={`empty-${index}`} index={articles.length + index + 1} label={EMPTY_TYPES[(articles.length + index) % EMPTY_TYPES.length]} />)}
            </div>
            {feed.hasNextPage && <div ref={loadMoreRef} className="sc-base-load-more" role="status">{feed.isFetchingNextPage ? 'Ładuję kolejne materiały…' : 'Przewiń niżej, aby załadować kolejne materiały.'}</div>}
          </div>
          <aside className={`sc-base-filters${filtersOpen ? ' is-open' : ''}`}>
            <details open>
              <summary>Kategorie <span>{selectedCategories.length || 'wszystkie'}</span></summary>
              <div className="category-options">{categories.map(item => (
                <label key={item.value}><input type="checkbox" checked={selectedCategories.includes(item.value)}
                  onChange={() => setSelectedCategories(current => current.includes(item.value) ? current.filter(v => v !== item.value) : [...current, item.value])} />{item.label}</label>
              ))}</div>
            </details>
            <details>
              <summary>Źródła <span>{selectedSources.length || 'wszystkie'}</span></summary>
              <label className="source-filter-search">Znajdź źródło<input type="search" value={sourceSearch} onChange={event => setSourceSearch(event.target.value)} placeholder="Nazwa źródła" /></label>
              <button type="button" className="mvp-source-picker-open" onClick={() => setSourcePickerOpen(true)}>Przeglądaj i wybierz źródła</button>
              <SourceTree groups={sourceGroups} selectedSources={selectedSources} onToggle={toggleSource} />
              {!visibleSources.length && <p className="mvp-strip-empty">Nie znaleźliśmy takiego źródła.</p>}
            </details>
            <details>
              <summary>Platformy <span>{selectedPlatforms.length || 'wszystkie'}</span></summary>
              <div className="platform-filter-options">
                <label><input type="checkbox" checked={selectedPlatforms.includes('youtube')} onChange={() => setSelectedPlatforms(current => current.includes('youtube') ? [] : ['youtube'])} />YouTube <small>materiały wideo</small></label>
                <p><strong>X</strong> · posty polityków przechodzą najpierw przez redakcyjny przegląd Dr Spina.</p>
              </div>
            </details>
            <details open>
              <summary>Okres <span>{PERIODS.find(item => item.value === period)?.label}</span></summary>
              <div className="period-options">{PERIODS.map(item => (
                <label key={item.value}><input type="radio" name="mvp-baza-period" checked={period === item.value} onChange={() => setPeriod(item.value)} />{item.label}</label>
              ))}</div>
            </details>
            {activeFilterCount > 0 && <button type="button" className="filter-reset" onClick={() => { setSelectedCategories([]); setSelectedSources([]); setSelectedPlatforms([]); setPeriod('all'); }}>Wyczyść filtry</button>}
          </aside>
        </div>
        {sourcePickerOpen && <div className="mvp-source-picker-backdrop" role="presentation" onMouseDown={() => setSourcePickerOpen(false)}>
          <section className="mvp-source-picker" role="dialog" aria-modal="true" aria-labelledby="source-picker-title" onMouseDown={event => event.stopPropagation()}>
            <header><div><p>KATALOG ŹRÓDEŁ</p><h2 id="source-picker-title">Wybierz źródła do przeglądu</h2></div><button type="button" aria-label="Zamknij katalog źródeł" onClick={() => setSourcePickerOpen(false)}>×</button></header>
            <label className="source-filter-search">Znajdź źródło<input autoFocus type="search" value={sourceSearch} onChange={event => setSourceSearch(event.target.value)} placeholder="Nazwa źródła" /></label>
            <p className="mvp-source-picker-note">Źródła oznaczone „Katalog” są przygotowane do uruchomienia, ale nie mają jeszcze aktywnego dopływu materiałów.</p>
            <SourceTree groups={sourceGroups} selectedSources={selectedSources} onToggle={toggleSource} />
            <footer><button type="button" className="mvp-source-picker-done" onClick={() => setSourcePickerOpen(false)}>Zastosuj wybór · {selectedSources.length || 'wszystkie'}</button></footer>
          </section>
        </div>}
      </section>
    );
  },
);
