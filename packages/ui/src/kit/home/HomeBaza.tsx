"use client";

/**
 * Baza: jeden główny pasek (tytuł · pole szukania na środku · „Najnowsze materiały” z liczbą
 * i zakresem źródeł), pod nim obszar o stałej wysokości: siatka `mini` (3 kolumny × ~5 rzędów)
 * przewijana WEWNĄTRZ obszaru, z nieskończonym doładowaniem obserwowanym w tym samym kontenerze,
 * i obok niej kolumna filtrów (≤900px — arkusz dolny z przycisku w pasku). Strona nie rośnie
 * razem z liczbą materiałów, więc globalna stopka jest zaraz pod Bazą.
 * Grupa źródeł (`?zrodla=`, selektor w pasku kategorii / stopka) zawęża Bazę, dopóki nie wybrano
 * konkretnych źródeł w filtrach. Zmiana filtra: ocalałe karty jadą, nowe wchodzą (`MorphList`).
 */

import { forwardRef, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../Button";
import { Checkbox } from "../Checkbox";
import { NewsCard } from "../NewsCard";
import { RadioGroup } from "../Radio";
import { SearchField } from "../SearchField";
import { Switch } from "../Switch";
import { BottomSheet } from "../mobile/BottomSheet";
import { MorphList } from "../motion/MorphList";
import { MorphValue } from "../motion/MorphValue";
import { Reveal, RevealHeight } from "../motion/Reveal";
import { FilterIcon } from "../icons/FilterIcon";
import { ChevronDownIcon } from "../icons/ChevronDownIcon";
import type { CategoryOption } from "../../lib/portal";
import type { Source } from "../../types";
import { useHomeInfiniteFeed } from "./data";
import { groupSources, sourceGroupLabel, type SourceGroup } from "./sourceGroups";

// ---------------------------------------------------------------------------
// Filtry
// ---------------------------------------------------------------------------

const PERIODS: { value: string; label: string; hours: number | null }[] = [
  { value: "all", label: "Zawsze", hours: null },
  { value: "24h", label: "Ostatnie 24 godziny", hours: 24 },
  { value: "7d", label: "Ostatnie 7 dni", hours: 24 * 7 },
  { value: "30d", label: "Ostatnie 30 dni", hours: 24 * 30 },
];

const GROUP_LABELS = { top: "Top media", media: "Media", publiczne: "Publiczne" } as const;

type FiltersState = {
  categories: string[];
  sources: number[];
  youtube: boolean;
  period: string;
};

function FilterGroup({ title, summary, defaultOpen = false, children }: { title: string; summary: string; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="sc-home-filter" data-open={open || undefined}>
      <button type="button" className="sc-home-filter__summary" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <span className="sc-t-title-s">{title}</span>
        <span className="sc-t-meta sc-text-2">{summary}</span>
        <ChevronDownIcon size={16} open={open} />
      </button>
      <RevealHeight when={open}>
        <div className="sc-home-filter__body">{children}</div>
      </RevealHeight>
    </div>
  );
}

function FiltersPanel({
  categories,
  sources,
  state,
  onChange,
  onReset,
  activeCount,
}: {
  categories: CategoryOption[];
  sources: Source[];
  state: FiltersState;
  onChange: (next: FiltersState) => void;
  onReset: () => void;
  activeCount: number;
}) {
  const [sourceSearch, setSourceSearch] = useState("");
  const visibleSources = sources.filter((source) => source.name.toLocaleLowerCase("pl").includes(sourceSearch.toLocaleLowerCase("pl")));
  const groups = groupSources(visibleSources);
  const toggle = <T,>(list: T[], value: T) => (list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);

  return (
    <div className="sc-home-filters">
      <FilterGroup title="Kategorie" summary={state.categories.length ? String(state.categories.length) : "wszystkie"} defaultOpen>
        {categories.map((item) => (
          <Checkbox key={item.value} label={item.label} checked={state.categories.includes(item.value)} onChange={() => onChange({ ...state, categories: toggle(state.categories, item.value) })} />
        ))}
      </FilterGroup>

      <FilterGroup title="Źródła" summary={state.sources.length ? String(state.sources.length) : "wszystkie"}>
        <SearchField value={sourceSearch} onChange={setSourceSearch} placeholder="Nazwa źródła" label="Znajdź źródło" />
        {(Object.keys(GROUP_LABELS) as Array<keyof typeof GROUP_LABELS>).map((key) =>
          groups[key].length > 0 ? (
            <div key={key} className="sc-home-filter__group">
              <p className="sc-t-caption sc-text-3">
                {GROUP_LABELS[key]} · {groups[key].length}
              </p>
              {groups[key].map((source) => (
                <Checkbox
                  key={source.id}
                  label={source.is_active === false ? `${source.name} · katalog` : source.name}
                  checked={state.sources.includes(source.id)}
                  onChange={() => onChange({ ...state, sources: toggle(state.sources, source.id) })}
                />
              ))}
            </div>
          ) : null,
        )}
        {!visibleSources.length ? <p className="sc-t-body-s sc-text-2">Nie znaleźliśmy takiego źródła.</p> : null}
      </FilterGroup>

      <FilterGroup title="Platformy" summary={state.youtube ? "YouTube" : "wszystkie"}>
        <Switch label="YouTube · materiały wideo" checked={state.youtube} onChange={(checked) => onChange({ ...state, youtube: checked })} />
        <p className="sc-t-body-s sc-text-2">
          <strong>X</strong> · posty polityków przechodzą najpierw przez redakcyjny przegląd Dr Spina.
        </p>
      </FilterGroup>

      <FilterGroup title="Okres" summary={PERIODS.find((item) => item.value === state.period)?.label ?? "Zawsze"} defaultOpen>
        <RadioGroup name="baza-period" legend="Okres" value={state.period} onChange={(value) => onChange({ ...state, period: value })} options={PERIODS.map(({ value, label }) => ({ value, label }))} />
      </FilterGroup>

      <Reveal when={activeCount > 0}>
        <Button variant="quiet" size="sm" onClick={onReset}>
          Wyczyść filtry
        </Button>
      </Reveal>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sekcja
// ---------------------------------------------------------------------------

const PAGE_SIZE = 30;
const EMPTY_FILTERS: FiltersState = { categories: [], sources: [], youtube: false, period: "all" };

export const HomeBaza = forwardRef<HTMLElement, { categories: CategoryOption[]; sources: Source[]; initialQuery: string; sourceGroup?: SourceGroup | null }>(
  function HomeBaza({ categories, sources, initialQuery, sourceGroup = null }, ref) {
  const [query, setQuery] = useState(initialQuery);
  const [filters, setFilters] = useState<FiltersState>(EMPTY_FILTERS);
  const [sheetOpen, setSheetOpen] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Grupa źródeł zawęża listę w filtrach i zakres zapytania; wybrane ręcznie źródła spoza grupy odpadają.
  const scopedSources = useMemo(() => (sourceGroup ? groupSources(sources)[sourceGroup] : sources), [sources, sourceGroup]);
  const groupEmpty = Boolean(sourceGroup) && sources.length > 0 && scopedSources.length === 0;
  useEffect(() => {
    if (!sourceGroup) return;
    const allowed = new Set(scopedSources.map((source) => source.id));
    setFilters((current) => (current.sources.every((id) => allowed.has(id)) ? current : { ...current, sources: current.sources.filter((id) => allowed.has(id)) }));
  }, [sourceGroup, scopedSources]);

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  const feed = useHomeInfiniteFeed("baza", {
    query,
    categories: filters.categories,
    sources: filters.sources.length ? filters.sources : sourceGroup ? scopedSources.map((source) => source.id) : [],
    platforms: filters.youtube ? ["youtube"] : [],
    pageSize: PAGE_SIZE,
  }, { enabled: !groupEmpty });

  const allArticles = useMemo(
    () => [...new Map((feed.data?.pages.flatMap((page) => page.results) ?? []).map((article) => [article.id, article])).values()],
    [feed.data],
  );
  const periodHours = PERIODS.find((item) => item.value === filters.period)?.hours ?? null;
  const articles = useMemo(() => {
    if (!periodHours) return allArticles;
    const cutoff = Date.now() - periodHours * 3_600_000;
    return allArticles.filter((article) => article.published_date && new Date(article.published_date).getTime() >= cutoff);
  }, [allArticles, periodHours]);

  const activeCount = filters.categories.length + filters.sources.length + (filters.youtube ? 1 : 0) + (filters.period !== "all" ? 1 : 0);
  const total = feed.data?.pages[0]?.total ?? articles.length;
  const sourcesNote = filters.sources.length
    ? `Wybrane źródła: ${filters.sources.length}`
    : sourceGroup
      ? `Źródła: ${sourceGroupLabel(sourceGroup)}`
      : "Wszystkie aktywne źródła";

  useEffect(() => {
    const target = sentinelRef.current;
    if (!target || !feed.hasNextPage || feed.isFetchingNextPage) return;
    // Korzeń = przewijany obszar Bazy (nie okno): doładowanie zależy od przewinięcia siatki.
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) feed.fetchNextPage();
      },
      { root: scrollRef.current, rootMargin: "400px 0px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [feed.fetchNextPage, feed.hasNextPage, feed.isFetchingNextPage, feed]);

  const panel = (
    <FiltersPanel categories={categories} sources={scopedSources} state={filters} onChange={setFilters} onReset={() => setFilters(EMPTY_FILTERS)} activeCount={activeCount} />
  );

  return (
    <section ref={ref} id="baza" className="sc-home-section sc-home-baza" aria-label="Baza materiałów">
      <header className="sc-home-baza__bar">
        <div className="sc-home-baza__title">
          <h2 className="sc-t-title-l sc-home-section__title">Baza</h2>
          <p className="sc-t-body-s sc-text-2">Przeszukaj wszystkie materiały w bazie</p>
        </div>
        <form className="sc-home-baza__search" role="search" onSubmit={(event) => event.preventDefault()}>
          <SearchField value={query} onChange={setQuery} placeholder="Szukaj w bazie…" label="Szukaj w bazie" resultsCount={query ? total : undefined} />
        </form>
        <div className="sc-home-baza__latest">
          <h3 className="sc-t-title-s">
            Najnowsze materiały{" "}
            <span className="sc-t-meta sc-text-2 sc-home-baza__count">
              <MorphValue value={total} /> {total === 1 ? "materiał" : "materiałów"}
            </span>
          </h3>
          <p className="sc-t-body-s sc-text-2">{sourcesNote} · od najnowszej publikacji</p>
        </div>
        <Button className="sc-home-baza__filters-toggle" variant="secondary" size="sm" iconStart={<FilterIcon size={16} />} onClick={() => setSheetOpen(true)}>
          Filtry{activeCount ? ` · ${activeCount}` : ""}
        </Button>
      </header>

      <div className="sc-home-baza__layout">
        <div ref={scrollRef} className="sc-home-baza__results" tabIndex={0} aria-label="Materiały w Bazie — przewijaj w obrębie sekcji">
          {groupEmpty && sourceGroup ? <p className="sc-t-body-s sc-text-2">Brak aktywnych źródeł w grupie „{sourceGroupLabel(sourceGroup)}”.</p> : null}
          {feed.isPending && !groupEmpty ? <p role="status" className="sc-t-body-s sc-text-2">Ładuję materiały…</p> : null}
          {feed.isError ? (
            <p role="alert" className="sc-t-body-s sc-text-2">
              Nie udało się odświeżyć bazy.{" "}
              <button type="button" className="sc-home-linkbtn" onClick={() => feed.refetch()}>
                Ponów
              </button>
            </p>
          ) : null}
          {feed.isSuccess && !articles.length ? <p className="sc-t-body-s sc-text-2">Brak materiałów pasujących do wybranych filtrów.</p> : null}
          <MorphList
            id="sc-home-baza"
            as="ul"
            itemAs="li"
            className="sc-home-baza__grid"
            items={articles}
            getKey={(article) => article.id}
            renderItem={(article) => <NewsCard article={article} size="mini" headingLevel={4} />}
          />
          {feed.hasNextPage ? (
            <div ref={sentinelRef} className="sc-home-baza__more" role="status">
              {feed.isFetchingNextPage ? "Ładuję kolejne materiały…" : "Przewiń siatkę niżej, aby załadować kolejne materiały."}
            </div>
          ) : null}
        </div>
        <aside className="sc-home-baza__aside" aria-label="Filtry">
          {panel}
        </aside>
      </div>

      <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Filtry">
        {panel}
        <div className="sc-home-baza__sheet-actions">
          <Button variant="primary" size="md" fullWidth onClick={() => setSheetOpen(false)}>
            Pokaż materiały{total ? ` · ${total}` : ""}
          </Button>
        </div>
      </BottomSheet>
    </section>
  );
  },
);
