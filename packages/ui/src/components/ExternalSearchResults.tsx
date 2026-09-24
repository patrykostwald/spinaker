"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import { categoryLabel } from "../lib/utils";
import { Button } from "../kit";

type Discovery = { url: string; title: string; source_name: string; published_date: string | null; image_url: string; category: string; status: string };
type DiscoveryResponse = { status: "disabled" | "ok" | "partial" | "filtered" | "unavailable" | "daily_limit"; results: Discovery[]; detail?: string };
const webUrl = (value: string) => { try { return ["https:", "http:"].includes(new URL(value).protocol); } catch { return false; } };

/** Odkrywanie jest odrębne od zweryfikowanego archiwum i może pozostać wyłączone. */
export function ExternalSearchResults({ query, categories, fromDate, toDate, onRefreshArchive, refreshingArchive }: { query: string; categories: string; fromDate: string; toDate: string; onRefreshArchive: () => void; refreshingArchive: boolean }) {
  const [visible, setVisible] = useState(5);
  const params = new URLSearchParams({ q: query });
  if (categories) params.set("categories", categories);
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  const search = useQuery({
    queryKey: ["external-search", query, categories, fromDate, toDate],
    queryFn: () => apiFetch<DiscoveryResponse>(`/api/search/external/?${params}`),
    staleTime: 300000,
    retry: false,
    refetchOnWindowFocus: false,
    enabled: query.length <= 200,
  });
  const rows = (search.data?.results ?? []).filter(row => webUrl(row.url));
  const notice: Record<string, string> = {
    disabled: "Wyszukiwanie zewnętrzne nie jest jeszcze uruchomione. Przeszukujemy dostępną bazę.",
    unavailable: "Wyszukiwanie w sieci jest chwilowo niedostępne. Wyniki z bazy pozostają dostępne.",
    daily_limit: "Osiągnięto dzisiejszy limit wyszukiwania w sieci. Nadal możesz przeszukiwać bazę.",
    filtered: "Dla tych filtrów nie pokazujemy dodatkowych wyników z sieci. Sprawdź materiały w bazie.",
  };
  if (query.length > 200 || search.isPending || search.data?.status === "disabled" || search.data?.status === "filtered") return null;

  return <section aria-labelledby="web-results-title" className="sc-external-results">
    <h2 id="web-results-title">Dodatkowe odnośniki · wyszukiwarka zewnętrzna</h2>
    <p role="status">{search.isError ? "Wyszukiwanie w sieci jest chwilowo niedostępne. Nadal możesz korzystać z bazy." : notice[search.data?.status ?? ""] ?? `${rows.length} dodatkowych odnośników${search.data?.status === "partial" ? " · część źródeł nie odpowiedziała" : ""}.`}</p>
    {search.isError ? <Button type="button" variant="quiet" size="sm" onClick={() => search.refetch()}>Ponów wyszukiwanie w sieci</Button> : null}
    {rows.length ? <>
      <p className="sc-external-results__note">To odnośniki z wyszukiwarki, jeszcze niezweryfikowane w naszej bazie. Datę i kategorię potwierdzamy u wydawcy przed dodaniem materiału na oś czasu.</p>
      <div className="sc-external-results__cards sc-strip-bleed">
        {rows.slice(0, visible).map(row => <article key={row.url}>
          <p>{row.category === "other" ? "Kategoria do sprawdzenia" : `${categoryLabel(row.category)} · do potwierdzenia`}</p>
          <h3><a href={row.url} target="_blank" rel="noopener noreferrer">{row.title || row.url} ↗</a></h3>
          <small>ŹRÓDŁO · {row.source_name || new URL(row.url).hostname}</small>
          <small>DATA · wymaga potwierdzenia</small>
          <Link href={`/editor?source_url=${encodeURIComponent(row.url)}`}>Dodaj przez warsztat redakcji</Link>
        </article>)}
      </div>
      {visible < rows.length ? <Button type="button" variant="secondary" onClick={() => setVisible(count => count + 5)}>Pokaż kolejne odnośniki</Button> : null}
      <div className="sc-external-results__actions"><p>Sprawdzamy dostępne źródła w tle. Odświeżenie bazy może zmienić układ osi czasu.</p><Button type="button" variant="secondary" loading={refreshingArchive} onClick={onRefreshArchive}>Sprawdź nowe wyniki w bazie</Button></div>
    </> : null}
  </section>;
}
