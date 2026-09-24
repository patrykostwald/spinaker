"use client";

/**
 * Baza (stary `Baza` + `TwojePaski`): nagłówek, „Twój przegląd” (do 5 lokalnych pasków,
 * przeciąganych za uchwyt — `ReorderableStrips`), „Najnowsze materiały” z przewijającą się liczbą,
 * pole hasła, siatka `medium` z nieskończonym przewijaniem i lepka kolumna filtrów (desktop) /
 * arkusz dolny (≤900px). Zmiana filtra: ocalałe karty jadą, nowe wchodzą (`MorphList`).
 */

import { forwardRef, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Button } from "../Button";
import { Checkbox } from "../Checkbox";
import { Dropdown } from "../Dropdown";
import { NewsCard } from "../NewsCard";
import { RadioGroup } from "../Radio";
import { ReorderableStrips } from "../ReorderableStrips";
import { SearchField } from "../SearchField";
import { Switch } from "../Switch";
import { BottomSheet } from "../mobile/BottomSheet";
import { MorphList } from "../motion/MorphList";
import { MorphValue } from "../motion/MorphValue";
import { Reveal, RevealHeight } from "../motion/Reveal";
import { FilterIcon } from "../icons/FilterIcon";
import { ChevronDownIcon } from "../icons/ChevronDownIcon";
import type { CategoryOption } from "../../lib/portal";
import {
  MAX_PERSONAL_STRIPS,
  loadPersonalStrips,
  removePersonalStrip,
  savePersonalStrip,
  updatePersonalStrip,
  type PersonalStrip,
} from "../../lib/personalStrips";
import type { Source } from "../../types";
import { useHomeFeed, useHomeInfiniteFeed } from "./data";
import { Strip } from "./Strip";

// ---------------------------------------------------------------------------
// Twój przegląd — lokalne paski
// ---------------------------------------------------------------------------

function StripForm({
  initial,
  categories,
  sources,
  onSave,
  onCancel,
}: {
  initial?: PersonalStrip;
  categories: CategoryOption[];
  sources: Source[];
  onSave: (strip: PersonalStrip) => void;
  onCancel: () => void;
}) {
  const [query, setQuery] = useState(initial?.query ?? "");
  const [category, setCategory] = useState(initial?.category ?? "");
  const [sourceId, setSourceId] = useState<string>(initial?.sourceId ? String(initial.sourceId) : "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = sources.find((item) => String(item.id) === sourceId);
    const label = query.trim() || categories.find((item) => item.value === category)?.label || source?.name || "Mój pasek";
    onSave({ id: initial?.id || `${Date.now()}`, label, query: query.trim(), category, sourceId: sourceId ? Number(sourceId) : "" });
  }

  return (
    <form className="sc-home-stripform" onSubmit={submit}>
      <p className="sc-t-caption sc-text-3">{initial?.id ? "Edytuj pasek" : "Nowy pasek"}</p>
      <div className="sc-home-stripform__row">
        <SearchField value={query} onChange={setQuery} placeholder="Hasło lub nazwisko" label="Hasło lub nazwisko" />
        <Dropdown
          label={categories.find((item) => item.value === category)?.label ?? "Kategoria: wszystkie"}
          ariaLabel="Kategoria"
          mode="single"
          presentation="auto"
          items={[{ value: "", label: "Wszystkie" }, ...categories]}
          value={category}
          onChange={(value) => setCategory(value as string)}
        />
        <Dropdown
          label={sources.find((item) => String(item.id) === sourceId)?.name ?? "Źródło: wszystkie"}
          ariaLabel="Źródło"
          mode="single"
          presentation="auto"
          items={[{ value: "", label: "Wszystkie" }, ...sources.map((item) => ({ value: String(item.id), label: item.name }))]}
          value={sourceId}
          onChange={(value) => setSourceId(value as string)}
        />
        <div className="sc-home-stripform__actions">
          <Button type="submit" variant="primary" size="sm">
            Pokaż materiały
          </Button>
          <Button type="button" variant="quiet" size="sm" onClick={onCancel}>
            Anuluj
          </Button>
        </div>
      </div>
    </form>
  );
}

function PersonalStripBody({ strip, onEdit, onRemove }: { strip: PersonalStrip; onEdit: () => void; onRemove: () => void }) {
  const feed = useHomeFeed(`personal-${strip.id}`, {
    query: strip.query,
    categories: strip.category ? [strip.category] : [],
    sources: strip.sourceId ? [strip.sourceId] : [],
    pageSize: 20,
  });
  const articles = feed.data?.results ?? [];
  return (
    <div className="sc-home-personal__strip">
      <div className="sc-home-personal__actions">
        <Button variant="quiet" size="sm" onClick={onEdit}>
          Edytuj
        </Button>
        <Button variant="quiet" size="sm" onClick={onRemove}>
          Usuń pasek
        </Button>
      </div>
      {feed.isPending ? <p role="status" className="sc-t-body-s sc-text-2">Ładuję materiały…</p> : null}
      {feed.isSuccess && !articles.length ? <p className="sc-t-body-s sc-text-2">Nie znaleźliśmy jeszcze materiałów pasujących do tego wyboru.</p> : null}
      {articles.length > 0 ? (
        <Strip label={strip.label}>
          {articles.map((article) => (
            <div key={article.id} className="sc-strip__slot">
              <NewsCard article={article} size="compact" headingLevel={4} />
            </div>
          ))}
        </Strip>
      ) : null}
    </div>
  );
}

export type StripDraft = { query: string; nonce: number };

function PersonalStrips({ categories, sources, draft }: { categories: CategoryOption[]; sources: Source[]; draft: StripDraft | null }) {
  const [strips, setStrips] = useState<PersonalStrip[]>([]);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    setStrips(loadPersonalStrips());
  }, []);

  // Pas „Twój przegląd” na dole strony: otwiera formularz z wpisanym hasłem (nonce — każde wysłanie).
  useEffect(() => {
    if (!draft) return;
    setAdding(true);
    setEditingId(null);
  }, [draft]);

  const atLimit = strips.length >= MAX_PERSONAL_STRIPS;
  const rows = useMemo(() => strips.map((strip) => ({ id: strip.id, title: strip.label, strip })), [strips]);

  return (
    <div className="sc-home-personal" aria-label="Twój przegląd">
      <header className="sc-home-subhead">
        <div>
          <h3 className="sc-t-title-m">Twój przegląd</h3>
          <p className="sc-t-body-s sc-text-2">Twój lokalnie zapisany widok materiałów z Bazy · kolejność pasków zapisuje się na tym urządzeniu</p>
        </div>
        {!adding && !atLimit ? (
          <Button variant="secondary" size="sm" onClick={() => { setAdding(true); setEditingId(null); }}>
            + Dodaj pasek
          </Button>
        ) : null}
      </header>

      {rows.length > 0 ? (
        <ReorderableStrips
          strips={rows}
          storageKey="spinclinic-home-strips-order"
          label="Kolejność Twoich pasków"
          renderStrip={(row) =>
            editingId === row.id ? (
              <StripForm
                initial={row.strip}
                categories={categories}
                sources={sources}
                onSave={(strip) => { setStrips(updatePersonalStrip(strip)); setEditingId(null); }}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <PersonalStripBody
                strip={row.strip}
                onEdit={() => { setEditingId(row.id); setAdding(false); }}
                onRemove={() => { setStrips(removePersonalStrip(row.id)); if (editingId === row.id) setEditingId(null); }}
              />
            )
          }
        />
      ) : null}

      {adding ? (
        <StripForm
          key={draft?.nonce ?? "new"}
          initial={draft?.query ? { id: "", label: "", query: draft.query, category: "", sourceId: "" } : undefined}
          categories={categories}
          sources={sources}
          onSave={(strip) => { setStrips(savePersonalStrip({ ...strip, id: strip.id || `${Date.now()}` })); setAdding(false); }}
          onCancel={() => setAdding(false)}
        />
      ) : atLimit ? (
        <p className="sc-t-body-s sc-text-2">Masz już {MAX_PERSONAL_STRIPS} pasków — usuń jeden, aby dodać kolejny.</p>
      ) : !rows.length ? (
        <div className="sc-home-personal__example">
          <p className="sc-t-body-s sc-text-2">Dopasuj własny pasek: hasło, kategoria lub źródło.</p>
          <div className="sc-home-pills">
            {["Hasło", "Kategoria", "Źródło"].map((label) => (
              <Button key={label} variant="quiet" shape="pill" size="sm" onClick={() => setAdding(true)}>
                {label}
              </Button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filtry
// ---------------------------------------------------------------------------

const PERIODS: { value: string; label: string; hours: number | null }[] = [
  { value: "all", label: "Zawsze", hours: null },
  { value: "24h", label: "Ostatnie 24 godziny", hours: 24 },
  { value: "7d", label: "Ostatnie 7 dni", hours: 24 * 7 },
  { value: "30d", label: "Ostatnie 30 dni", hours: 24 * 30 },
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

const GROUP_LABELS = { important: "Największe media", media: "Media", public: "Publiczne" } as const;

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

export const HomeBaza = forwardRef<HTMLElement, { categories: CategoryOption[]; sources: Source[]; initialQuery: string; stripDraft?: StripDraft | null }>(
  function HomeBaza({ categories, sources, initialQuery, stripDraft = null }, ref) {
  const [query, setQuery] = useState(initialQuery);
  const [filters, setFilters] = useState<FiltersState>(EMPTY_FILTERS);
  const [sheetOpen, setSheetOpen] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  const feed = useHomeInfiniteFeed("baza", {
    query,
    categories: filters.categories,
    sources: filters.sources,
    platforms: filters.youtube ? ["youtube"] : [],
    pageSize: PAGE_SIZE,
  });

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

  useEffect(() => {
    const target = sentinelRef.current;
    if (!target || !feed.hasNextPage || feed.isFetchingNextPage) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) feed.fetchNextPage();
      },
      { rootMargin: "800px 0px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [feed.fetchNextPage, feed.hasNextPage, feed.isFetchingNextPage, feed]);

  const panel = (
    <FiltersPanel categories={categories} sources={sources} state={filters} onChange={setFilters} onReset={() => setFilters(EMPTY_FILTERS)} activeCount={activeCount} />
  );

  return (
    <section ref={ref} id="baza" className="sc-home-section sc-home-baza" aria-label="Baza materiałów">
      <header className="sc-home-section__head">
        <div>
          <h2 className="sc-t-title-l">Baza</h2>
          <p className="sc-t-body-s sc-text-2">Przeszukaj wszystkie materiały w bazie</p>
        </div>
      </header>

      <PersonalStrips categories={categories} sources={sources} draft={stripDraft} />

      <div className="sc-home-subhead sc-home-baza__latest">
        <div>
          <h3 className="sc-t-title-m">
            Najnowsze materiały{" "}
            <span className="sc-t-meta sc-text-2 sc-home-baza__count">
              <MorphValue value={total} /> {total === 1 ? "materiał" : "materiałów"}
            </span>
          </h3>
          <p className="sc-t-body-s sc-text-2">Wszystkie aktywne źródła · od najnowszej publikacji</p>
        </div>
        <Button className="sc-home-baza__filters-toggle" variant="secondary" size="sm" iconStart={<FilterIcon size={16} />} onClick={() => setSheetOpen(true)}>
          Filtry{activeCount ? ` · ${activeCount}` : ""}
        </Button>
      </div>

      <form className="sc-home-baza__search" onSubmit={(event) => event.preventDefault()}>
        <SearchField value={query} onChange={setQuery} placeholder="Szukaj w bazie…" label="Szukaj w bazie" resultsCount={query ? total : undefined} />
      </form>

      <div className="sc-home-baza__layout">
        <div className="sc-home-baza__results">
          {feed.isPending ? <p role="status" className="sc-t-body-s sc-text-2">Ładuję materiały…</p> : null}
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
            renderItem={(article) => <NewsCard article={article} size="medium" headingLevel={4} />}
          />
          {feed.hasNextPage ? (
            <div ref={sentinelRef} className="sc-home-baza__more" role="status">
              {feed.isFetchingNextPage ? "Ładuję kolejne materiały…" : "Przewiń niżej, aby załadować kolejne materiały."}
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
