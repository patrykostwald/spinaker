"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, getClinicStats, searchClinicSpins, type ClinicSearchParams } from "../../lib/clinic";
import { SpinRow } from "./SpinParts";

const FILTER_KEYS = ["q", "camp", "verdict", "party", "technique", "intensity_min", "intensity_max", "date_from", "date_to", "sort"] as const;
const format = (value: number) => value.toLocaleString("pl-PL");

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
  useEffect(() => {
    currentUrl.current = url;
    setSearch(new URLSearchParams(url).get("q") ?? "");
    clearTimeout(timer.current);
  }, [url]);
  useEffect(() => () => clearTimeout(timer.current), []);

  function update(values: Record<string, string>, clear = false) {
    const next = new URLSearchParams(currentUrl.current);
    if (clear) FILTER_KEYS.forEach(key => next.delete(key));
    Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    next.delete("page");
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
  const totals = stats.data?.totals;
  const active = [params.camp, params.verdict, params.party, params.technique,
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

  return (
    <section className="sc-clinic sc-clinic-db" aria-labelledby="clinic-db-title">
      <header className="sc-clinic-head">
        <nav className="sc-clinic-db__links" aria-label="Klinika spinu">
          <Link href="/klinika">← Klinika spinu</Link>
          <Link href="/klinika/wskazniki">Wskaźniki i wykresy →</Link>
        </nav>
        <h1 id="clinic-db-title">Baza diagnoz</h1>
        {totals && <p>{format(totals.diagnosed.total)} diagnoz · {stats.data?.accounts ? <>{format(new Set(stats.data.accounts.map(row => row.account_id)).size)} zbadanych kont · </> : null}{format(CAMPS.reduce((sum, camp) => sum + totals.by_camp[camp].accounts, 0))} obserwowanych kont · {format(totals.read.total)} przeczytanych wpisów</p>}
      </header>
      <div className="sc-clinic-db__toolbar">
        <label className="sc-clinic-db__search">Szukaj diagnozy
          <input type="search" value={search} placeholder="Nagłówek, podsumowanie, nazwisko lub konto" onChange={event => {
            const value = event.target.value;
            setSearch(value);
            clearTimeout(timer.current);
            timer.current = setTimeout(() => update({ q: value.trim() }), 300);
          }} />
        </label>
        <button type="button" className="sc-clinic-db__toggle" aria-expanded={filtersOpen} aria-controls="clinic-db-filters" onClick={() => setFiltersOpen(value => !value)}>Filtry ({active})</button>
        <div id="clinic-db-filters" className="sc-clinic-db__filters" data-open={filtersOpen}>
          <fieldset className="sc-clinic-db__camp">
            <legend>Strona</legend>
            <div>{[["", "Wszystkie"], ...CAMPS.map(camp => [camp, CAMP_LABELS[camp]])].map(([value, label]) =>
              <button key={value} type="button" aria-pressed={(params.camp ?? "") === value} onClick={() => change({ camp: value })}>{label}</button>)}</div>
          </fieldset>
          <label>Werdykt<select value={params.verdict ?? ""} onChange={event => change({ verdict: event.target.value })}>
            <option value="">Wszystkie werdykty</option><option value="spin">Spin</option><option value="partial">Częściowy spin</option><option value="no_spin">Bez spinu</option><option value="unclear">Niejednoznaczne</option>
          </select></label>
          <label>Partia<select value={params.party ?? ""} onChange={event => change({ party: event.target.value })}>
            <option value="">Wszystkie partie</option>
            {params.party && !parties.some(([code]) => code === params.party) && <option value={params.party}>{params.party === "unknown" ? "Nieustalona partia" : params.party}</option>}
            {parties.map(([code, value]) => <option key={code} value={code}>{value.party?.short ?? "Nieustalona partia"}</option>)}
          </select></label>
          <label>Technika<select value={params.technique ?? ""} onChange={event => change({ technique: event.target.value })}>
            <option value="">Wszystkie techniki</option>
            {params.technique && !techniques.some(([name]) => name === params.technique) && <option>{params.technique}</option>}
            {techniques.map(([name]) => <option key={name}>{name}</option>)}
          </select></label>
          <label>Siła spinu<select value={intensity} onChange={event => {
            const [minimum = "", maximum = ""] = event.target.value.split("-");
            change({ intensity_min: minimum, intensity_max: maximum });
          }}>
            <option value="">Wszystkie poziomy</option><option value="0-29">0–29</option><option value="30-69">30–69</option><option value="70-100">70–100</option>
            {intensity && !["0-29", "30-69", "70-100"].includes(intensity) && <option value={intensity}>{params.intensity_min ?? 0}–{params.intensity_max ?? 100}</option>}
          </select></label>
          <label>Okres<select value={period} onChange={event => change({ date_from: event.target.value ? daysAgo(Number(event.target.value)) : "", date_to: "" })}>
            <option value="">Wszystko</option><option value="7">Ostatnie 7 dni</option><option value="30">Ostatnie 30 dni</option>
            {period === "custom" && <option value="custom">{params.date_from ?? "Początek"} — {params.date_to ?? "dzisiaj"}</option>}
          </select></label>
          <label>Sortowanie<select value={params.sort ?? "new"} onChange={event => change({ sort: event.target.value === "new" ? "" : "strong" })}>
            <option value="new">Najnowsze</option><option value="strong">Najsilniejsze</option>
          </select></label>
        </div>
        {hasFilters && <button type="button" onClick={reset}>Wyczyść filtry</button>}
        {stats.isError && <p role="status">Nie udało się pobrać statystyk i opcji filtrów. <button type="button" onClick={() => void stats.refetch()}>Spróbuj ponownie</button></p>}
      </div>
      <p aria-live="polite" aria-atomic="true">{query.isPending ? "Szukamy diagnoz…" : count !== undefined ? `Znaleziono: ${format(count)}` : ""}</p>
      <div className="sc-clinic-db__list" aria-busy={query.isFetching}>
        {rows.map(spin => <SpinRow key={spin.id} spin={spin} withSummary withTechniques />)}
      </div>
      {query.isError && <p role="alert">Nie udało się pobrać diagnoz. <button type="button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</button></p>}
      {query.isSuccess && rows.length === 0 && <div className="sc-clinic-empty"><p>Nie znaleźliśmy diagnoz pasujących do tych filtrów.</p><button type="button" onClick={reset}>Wyczyść filtry</button></div>}
      {query.hasNextPage && !query.isFetchNextPageError && <button className="sc-clinic-db__more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Wczytywanie…" : "Pokaż więcej"}</button>}
      <p className="sc-clinic-db__notice">Baza obejmuje wpisy, które izba przyjęć uznała za warte zbadania — to nie jest próba całej polityki. Liczba diagnoz jednej strony nie mówi, która strona spinuje więcej. <Link href="/o-nas#klinika">Jak wybieramy i liczymy?</Link></p>
    </section>
  );
}
