"use client";

import { SEMEVAL_MAP } from "../../lib/semeval";
import { ClinicNav } from "./ClinicNav";
import { Button } from "../../kit/Button";
import { SectionHeader } from "../../kit/SectionHeader";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, getClinicStats, searchClinicSpins, type ClinicSearchParams } from "../../lib/clinic";
import { SpinRow } from "./SpinParts";
import { clearClinicResults, readClinicResults, rememberClinicResults } from "../../lib/clinicNavigation";
import { Loading } from "../../kit/Loading";

const FILTER_KEYS = ["q", "account", "camp", "verdict", "party", "technique", "intensity_min", "intensity_max", "date_from", "date_to", "sort"] as const;
const format = (value: number) => value.toLocaleString("pl-PL");

type FilterOption = { value: string; label: string };

function FilterChip({ label, value, options, onChange, defaultValue = "" }: {
  label: string; value: string; options: FilterOption[]; onChange: (value: string) => void; defaultValue?: string;
}) {
  const selected = options.find(option => option.value === value);
  const active = value !== defaultValue;
  return <div className="sc-clinic-db__chip" data-active={active}>
    <label className="sc-clinic-db__choice">
      <span className="sc-clinic-db__chip-copy" aria-hidden="true"><span>{label}</span><strong>{selected?.label ?? value}</strong><span>⌄</span></span>
      <select aria-label={label} value={value} onChange={event => onChange(event.target.value)}>
        {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
    {active && <button type="button" className="sc-clinic-db__chip-clear" aria-label={`Wyczyść filtr: ${label}`} onClick={() => onChange(defaultValue)}>×</button>}
  </div>;
}

function daysAgo(days: number) {
  const date = new Date();
  date.setDate(date.getDate() - days + 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function ClinicDatabase() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const url = searchParams.toString();
  const currentUrl = useRef(url);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const filterButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    currentUrl.current = url;
    setSearch(new URLSearchParams(url).get("q") ?? "");
    clearTimeout(timer.current);
  }, [url]);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    if (!filtersOpen) return;
    const sheet = dialog.current;
    sheet?.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      sheet?.close();
      document.body.style.overflow = previousOverflow;
      filterButton.current?.focus();
    };
  }, [filtersOpen]);

  function update(values: Record<string, string>, clear = false) {
    const next = new URLSearchParams(currentUrl.current);
    if (clear) FILTER_KEYS.forEach(key => next.delete(key));
    Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    next.delete("page");
    clearClinicResults(`${pathname}${next.size ? `?${next}` : ""}`);
    currentUrl.current = next.toString();
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }
  function change(values: Record<string, string>) {
    clearTimeout(timer.current);
    update({ q: search.trim(), ...values });
  }
  function reset() {
    clearTimeout(timer.current);
    setSearch("");
    update({}, true);
  }

  const params: ClinicSearchParams = {};
  FILTER_KEYS.forEach(key => {
    const value = searchParams.get(key);
    if (value) Object.assign(params, { [key]: key.startsWith("intensity_") ? Number(value) : value });
  });
  const stats = useQuery({ queryKey: ["clinic-stats"], queryFn: getClinicStats, staleTime: 5 * 60_000 });
  const query = useInfiniteQuery({
    queryKey: ["clinic-database", params],
    queryFn: ({ pageParam }) => searchClinicSpins({ ...params, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: last => last.next_page ?? undefined,
  });
  const rows = query.data?.pages.flatMap(page => page.results) ?? [];
  const count = query.data?.pages[0]?.count;
  const resultsUrl = `${pathname}${url ? `?${url}` : ""}`;
  const restored = useRef<string | null>(null);
  useEffect(() => {
    if (!query.data || restored.current === resultsUrl) return;
    const saved = readClinicResults(resultsUrl);
    if (saved && query.data.pages.length < saved.pages && query.hasNextPage) {
      if (!query.isFetching && !query.isFetchNextPageError) void query.fetchNextPage();
      return;
    }
    // Wait for the list's DOM (including previously loaded pages) and route effects.
    let frame = requestAnimationFrame(() => {
      frame = requestAnimationFrame(() => {
        if (saved) window.scrollTo({ top: saved.top, behavior: "instant" as ScrollBehavior });
        restored.current = resultsUrl;
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [resultsUrl, query.data, query.hasNextPage, query.isFetching, query.isFetchNextPageError, query.fetchNextPage]);
  const active = [params.account, params.camp, params.verdict, params.party, params.technique,
    params.intensity_min !== undefined || params.intensity_max !== undefined,
    params.date_from || params.date_to, params.sort === "strong"].filter(Boolean).length;
  const hasFilters = active > 0 || !!params.q || !!search;
  const parties = Object.entries(stats.data?.by_party ?? {});
  const techniques = Object.entries(stats.data?.techniques ?? {}).filter(([, camps]) =>
    Object.values(camps).some(value => value.count > 0));
  const period = params.date_to ? "custom" : !params.date_from ? "" :
    params.date_from === daysAgo(7) ? "7" : params.date_from === daysAgo(30) ? "30" : "custom";
  const intensity = params.intensity_min === undefined && params.intensity_max === undefined ? "" :
    `${params.intensity_min ?? 0}-${params.intensity_max ?? 100}`;

  const activeChips: Array<{ label: string; clear: Record<string, string> }> = [];
  if (params.account) {
    const author = rows.find(row => String(row.author.account_id) === params.account)?.author;
    const known = stats.data?.accounts?.find(row => String(row.account_id) === params.account);
    const label = author ? `${author.name} (@${author.handle})` : known ? `${known.name} (@${known.handle})` : `konto #${params.account}`;
    activeChips.push({ label: `Autor: ${label}`, clear: { account: "" } });
  }
  if (params.q) activeChips.push({ label: `Szukaj: ${params.q}`, clear: { q: "" } });
  if (params.camp) activeChips.push({ label: CAMP_LABELS[params.camp], clear: { camp: "" } });
  if (params.verdict) activeChips.push({ label: { spin: "Spin", partial: "Częściowy spin", no_spin: "Bez spinu", unclear: "Nie da się ocenić" }[params.verdict], clear: { verdict: "" } });
  if (params.party) activeChips.push({ label: parties.find(([code]) => code === params.party)?.[1].party?.short ?? (params.party === "unknown" ? "Nieustalona afiliacja" : params.party), clear: { party: "" } });
  if (params.technique) activeChips.push({ label: params.technique, clear: { technique: "" } });
  if (intensity) activeChips.push({ label: `Siła spinu: ${intensity.replace("-", "–")}`, clear: { intensity_min: "", intensity_max: "" } });
  if (params.date_from || params.date_to) activeChips.push({ label: `${params.date_from ?? "Początek"} – ${params.date_to ?? "dzisiaj"}`, clear: { date_from: "", date_to: "" } });
  if (params.sort === "strong") activeChips.push({ label: "Najwyższa siła spinu", clear: { sort: "" } });

  const campControl = <fieldset className="sc-clinic-db__camp">
    <legend className="sc-clinic-db__sr-only">Strona</legend>
    <div>{[["", "Wszystkie"], ...CAMPS.map(camp => [camp, CAMP_LABELS[camp]])].map(([value, label]) =>
      <button key={value} type="button" aria-pressed={(params.camp ?? "") === value} onClick={() => change({ camp: value })}>{label}</button>)}</div>
  </fieldset>;
  const filterControls = <>
    <FilterChip label="Werdykt" value={params.verdict ?? ""} onChange={value => change({ verdict: value })} options={[
      { value: "", label: "Wszystkie" }, { value: "spin", label: "Spin" }, { value: "partial", label: "Częściowy spin" },
      { value: "no_spin", label: "Bez spinu" }, { value: "unclear", label: "Nie da się ocenić" },
    ]} />
    <FilterChip label="Partia" value={params.party ?? ""} onChange={value => change({ party: value })} options={[
      { value: "", label: "Wszystkie" },
      ...(params.party && !parties.some(([code]) => code === params.party) ? [{ value: params.party, label: params.party === "unknown" ? "Nieustalona afiliacja" : params.party }] : []),
      ...parties.map(([code, value]) => ({ value: code, label: value.party?.short ?? "Nieustalona afiliacja" })),
    ]} />
    <FilterChip label="Technika" value={params.technique ?? ""} onChange={value => change({ technique: value })} options={[
      { value: "", label: "Wszystkie" },
      ...(params.technique && !techniques.some(([name]) => name === params.technique) ? [{ value: params.technique, label: params.technique }] : []),
      ...techniques.map(([name]) => ({ value: name, label: name })),
    ]} />
    <FilterChip label="Siła spinu" value={intensity} onChange={value => {
      const [minimum = "", maximum = ""] = value.split("-");
      change({ intensity_min: minimum, intensity_max: maximum });
    }} options={[
      { value: "", label: "Każda" }, ...["0-29", "30-69", "70-100"].map(value => ({ value, label: value.replace("-", "–") })),
      ...(intensity && !["0-29", "30-69", "70-100"].includes(intensity) ? [{ value: intensity, label: intensity.replace("-", "–") }] : []),
    ]} />
    <FilterChip label="Okres" value={period} onChange={value => change({ date_from: value ? daysAgo(Number(value)) : "", date_to: "" })} options={[
      { value: "", label: "Cały okres" }, { value: "7", label: "7 dni" }, { value: "30", label: "30 dni" },
      ...(period === "custom" ? [{ value: "custom", label: `${params.date_from ?? "Początek"} - ${params.date_to ?? "dzisiaj"}` }] : []),
    ]} />
  </>;

  return (
    <section className="sc-clinic sc-clinic-db" aria-labelledby="clinic-db-title">
      <div>
        <ClinicNav />
        <SectionHeader variant="page" titleId="clinic-db-title" title="Baza diagnoz" subtitle={<>
        <p>Znajdź analizę wpisu, autora lub techniki perswazji.</p>
      </>} />
      </div>
      <div className="sc-clinic-db__toolbar">
        <div className="sc-clinic-db__top">
          <label className="sc-clinic-db__search">
            <span className="sc-clinic-db__sr-only">Szukaj diagnozy</span>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></svg>
            <input className="sc-clinic-db__input" type="search" value={search} placeholder="Szukaj diagnoz…" onChange={event => {
              const value = event.target.value;
              setSearch(value);
              clearTimeout(timer.current);
              timer.current = setTimeout(() => update({ q: value.trim() }), 300);
            }} />
          </label>
          <button ref={filterButton} type="button" className="sc-clinic-db__toggle" aria-haspopup="dialog" aria-expanded={filtersOpen} aria-controls="clinic-db-filters" onClick={() => setFiltersOpen(true)}>Filtry ({active})</button>
        </div>
        <div className="sc-clinic-db__bottom">
          <p className="sc-clinic-db__count" aria-live="polite" aria-atomic="true">{query.isPending ? <Loading label="Wczytywanie" /> : count !== undefined ? `${format(count)} ${count === 1 ? "wynik" : count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 12 || count % 100 > 14) ? "wyniki" : "wyników"}` : ""}</p>
          <label className="sc-clinic-db__sort"><span>· Sortuj</span><select value={params.sort ?? "new"} onChange={event => change({ sort: event.target.value === "new" ? "" : "strong" })}><option value="new">Najnowsze</option><option value="strong">Najwyższa siła spinu</option></select></label>
        </div>
        {params.technique && SEMEVAL_MAP[params.technique] && <p className="sc-semeval-note">SemEval: {(stats.data?.technique_definitions?.[params.technique]?.semeval ?? SEMEVAL_MAP[params.technique]).join("; ") || "brak odpowiednika"}. <Link href="/metodologia#techniki">O przypisaniu</Link></p>}
        {stats.isError && <p role="status">Nie udało się pobrać statystyk i opcji filtrów. <button type="button" onClick={() => void stats.refetch()}>Spróbuj ponownie</button></p>}
        <dialog ref={dialog} id="clinic-db-filters" className="sc-clinic-db__sheet" aria-labelledby="clinic-db-filters-title" onCancel={() => setFiltersOpen(false)} onClose={() => setFiltersOpen(false)} onClick={event => {
          if (event.target === event.currentTarget) {
            const bounds = event.currentTarget.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) setFiltersOpen(false);
          }
        }}>
          <div className="sc-clinic-db__sheet-head"><h2 id="clinic-db-filters-title">Filtry diagnoz</h2><button type="button" aria-label="Zamknij filtry" onClick={() => setFiltersOpen(false)}>×</button></div>
          <div className="sc-clinic-db__sheet-body">
            <p className="sc-clinic-db__caption">Strona</p>
            {campControl}
            <div className="sc-clinic-db__sheet-filters">{filterControls}</div>
          </div>
          <div className="sc-clinic-db__sheet-footer">
            <p className="sc-clinic-db__sr-only" role="status" aria-atomic="true">{filtersOpen ? query.isPending ? "Wczytujemy diagnozy…" : count !== undefined ? `Znaleziono: ${format(count)}` : "" : ""}</p>
            {hasFilters && <button type="button" className="sc-clinic-db__reset" onClick={reset}>Wyczyść filtry</button>}
            <Button type="button" variant="primary" onClick={() => setFiltersOpen(false)}>Pokaż wyniki{count !== undefined ? ` (${format(count)})` : ""}</Button>
          </div>
        </dialog>
      </div>
      {activeChips.length ? <div className="sc-clinic-db__active" aria-label="Aktywne filtry">
        {activeChips.map(chip => <button key={Object.keys(chip.clear).join("-")} type="button" aria-label={`Usuń filtr: ${chip.label}`} onClick={() => { if ("q" in chip.clear) setSearch(""); change(chip.clear); }}>{chip.label} <span aria-hidden="true">×</span></button>)}
      </div> : null}
      <div className="sc-clinic-db__list" aria-busy={query.isFetching}>
        {rows.map(spin => <SpinRow key={spin.id} spin={spin} withSummary withTechniques returnTo={resultsUrl} onOpen={() => rememberClinicResults(resultsUrl, query.data?.pages.length ?? 1)} />)}
      </div>
      {query.isError && <p role="alert">Nie udało się pobrać diagnoz. <button type="button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</button></p>}
      {query.isSuccess && rows.length === 0 && <div className="sc-clinic-empty"><p>{hasFilters ? "Nie znaleźliśmy pasujących diagnoz." : "Nie ma jeszcze opublikowanych diagnoz dla tego wyboru."}</p>{hasFilters ? <button type="button" onClick={reset}>Wyczyść filtry</button> : null}</div>}
      {query.hasNextPage && !query.isFetchNextPageError && <Button className="sc-clinic-db__more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? <Loading inline label="Wczytywanie" /> : "Pokaż więcej"}</Button>}
      <p className="sc-clinic-db__notice">Baza obejmuje wpisy, które izba przyjęć uznała za warte zbadania - to nie jest próba całej polityki. Liczba diagnoz jednej strony nie mówi, która strona spinuje więcej. <Link href="/metodologia">Jak wybieramy i liczymy?</Link></p>
    </section>
  );
}
