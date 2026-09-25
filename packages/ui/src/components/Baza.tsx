"use client";

import { forwardRef, useEffect, useMemo, useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { getNewsFeed } from '../lib/portal';
import type { CategoryOption } from '../lib/portal';
import type { Source } from '../types';
import { MaterialBox } from './MaterialBox';
import { TwojePaski } from './TwojePaski';
import { BottomSheet, Button, Checkbox, RadioGroup, SearchField } from '../kit';

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

function SourceTree({ groups, selectedSources, onToggle, expanded = false }: {
  groups: ReturnType<typeof groupSources>; selectedSources: number[]; onToggle: (id: number) => void; expanded?: boolean;
}) {
  const labels = { important: 'Największe media', media: 'Media', public: 'Publiczne' } as const;
  return <div className={`sc-base-source-tree${expanded ? ' is-expanded' : ''}`}>
    {(Object.keys(labels) as Array<keyof typeof labels>).map(key => groups[key].length > 0 && <details key={key} className="sc-base-source-group">
      <summary>{labels[key]} <span>{groups[key].length}</span></summary>
      <div className="sc-base-source-options">{groups[key].map(source => (
        <div key={source.id} className={source.is_active === false ? 'is-catalog-candidate' : ''}>
          <Checkbox checked={selectedSources.includes(source.id)} onChange={() => onToggle(source.id)} label={source.name} />
          {source.is_active === false && <small>Katalog</small>}
        </div>
      ))}</div>
    </details>)}
  </div>;
}

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
            </div>
            {feed.hasNextPage && <div ref={loadMoreRef} className="sc-base-load-more" role="status">{feed.isFetchingNextPage ? 'Ładuję kolejne materiały…' : 'Przewiń niżej, aby załadować kolejne materiały.'}</div>}
          </div>
          <aside className={`sc-base-filters${filtersOpen ? ' is-open' : ''}`}>
            <details open>
              <summary>Kategorie <span>{selectedCategories.length || 'wszystkie'}</span></summary>
              <div className="sc-base-checkbox-options">{categories.map(item => (
                <Checkbox key={item.value} checked={selectedCategories.includes(item.value)}
                  onChange={() => setSelectedCategories(current => current.includes(item.value) ? current.filter(v => v !== item.value) : [...current, item.value])} label={item.label} />
              ))}</div>
            </details>
            <details>
              <summary>Źródła <span>{selectedSources.length || 'wszystkie'}</span></summary>
              <SearchField className="sc-base-source-search" label="Znajdź źródło" value={sourceSearch} onChange={setSourceSearch} placeholder="Nazwa źródła" />
              <Button type="button" variant="secondary" size="sm" className="sc-base-source-picker-open" onClick={() => setSourcePickerOpen(true)}>Przeglądaj i wybierz źródła</Button>
              <SourceTree groups={sourceGroups} selectedSources={selectedSources} onToggle={toggleSource} />
              {!visibleSources.length && <p className="sc-base-empty">Nie znaleźliśmy takiego źródła.</p>}
            </details>
            <details>
              <summary>Platformy <span>{selectedPlatforms.length || 'wszystkie'}</span></summary>
              <div className="sc-base-platform-options">
                <Checkbox checked={selectedPlatforms.includes('youtube')} onChange={() => setSelectedPlatforms(current => current.includes('youtube') ? [] : ['youtube'])} label="YouTube — materiały wideo" />
                <p><strong>X</strong> · posty polityków przechodzą najpierw przez redakcyjny przegląd Dr. Spina.</p>
              </div>
            </details>
            <details open>
              <summary>Okres <span>{PERIODS.find(item => item.value === period)?.label}</span></summary>
              <RadioGroup name="mvp-baza-period" legend="Okres materiałów" value={period} onChange={setPeriod} options={PERIODS.map(item => ({ value: item.value, label: item.label }))} />
            </details>
            {activeFilterCount > 0 && <Button type="button" variant="quiet" size="sm" onClick={() => { setSelectedCategories([]); setSelectedSources([]); setSelectedPlatforms([]); setPeriod('all'); }}>Wyczyść filtry</Button>}
          </aside>
        </div>
        <BottomSheet open={sourcePickerOpen} onClose={() => setSourcePickerOpen(false)} title="Wybierz źródła do przeglądu" className="sc-base-source-sheet">
          <p className="sc-base-source-sheet-kicker">KATALOG ŹRÓDEŁ</p>
          <SearchField label="Znajdź źródło" value={sourceSearch} onChange={setSourceSearch} placeholder="Nazwa źródła" />
          <p className="sc-base-source-sheet-note">Źródła oznaczone „Katalog” są przygotowane do uruchomienia, ale nie mają jeszcze aktywnego dopływu materiałów.</p>
          <SourceTree groups={sourceGroups} selectedSources={selectedSources} onToggle={toggleSource} expanded />
          <Button type="button" variant="primary" fullWidth onClick={() => setSourcePickerOpen(false)}>Zastosuj wybór · {selectedSources.length || 'wszystkie'}</Button>
        </BottomSheet>
      </section>
    );
  },
);
