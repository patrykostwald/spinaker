"use client";
import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { categoryLabel } from '../lib/utils';

type Discovery = { url: string; title: string; source_name: string; published_date: string | null; image_url: string; category: string; status: string };
type DiscoveryResponse = { status: 'disabled' | 'ok' | 'partial' | 'filtered' | 'unavailable' | 'daily_limit'; results: Discovery[]; detail?: string };
const webUrl = (value: string) => { try { return ['https:', 'http:'].includes(new URL(value).protocol); } catch { return false; } };

/** Kept separate from the dated archive: discovery is not source verification. */
export function ExternalSearchResults({ query, categories, fromDate, toDate, onRefreshArchive, refreshingArchive }: { query: string; categories: string; fromDate: string; toDate: string; onRefreshArchive: () => void; refreshingArchive: boolean }) {
  const [visible, setVisible] = useState(5);
  const params = new URLSearchParams({ q: query });
  if (categories) params.set('categories', categories);
  if (fromDate) params.set('from_date', fromDate);
  if (toDate) params.set('to_date', toDate);
  const search = useQuery({ queryKey: ['external-search', query, categories, fromDate, toDate],
    queryFn: () => apiFetch<DiscoveryResponse>(`/api/search/external/?${params}`),
    staleTime: 300000, retry: false, refetchOnWindowFocus: false, enabled: query.length <= 200 });
  const rows = (search.data?.results ?? []).filter(row => webUrl(row.url));
  const notice: Record<string, string> = {
    disabled: 'Wyszukiwanie zewnętrzne nie jest jeszcze uruchomione. Przeszukujemy dostępną bazę.',
    unavailable: 'Wyszukiwanie w sieci jest chwilowo niedostępne. Wyniki z bazy pozostają dostępne.',
    daily_limit: 'Osiągnięto dzisiejszy limit wyszukiwania w sieci. Nadal możesz przeszukiwać bazę.',
    filtered: 'Dla tych filtrów nie pokazujemy dodatkowych wyników z sieci. Sprawdź materiały w bazie.',
  };
  if (query.length > 200 || search.isPending || search.data?.status === 'disabled' || search.data?.status === 'filtered') return null;
  return <section aria-labelledby="web-results-title" className="space-y-3 border-t pt-5">
    <h2 id="web-results-title" className="text-lg font-semibold">Dodatkowe odnośniki · wyszukiwarka Brave</h2>
    <p role="status" className="text-sm text-slate-500">{search.isPending ? 'Szukamy kolejnych źródeł w sieci… Wyniki z bazy są dostępne powyżej.' : search.isError ? 'Wyszukiwanie w sieci jest chwilowo niedostępne. Nadal możesz korzystać z bazy.' : notice[search.data?.status ?? ''] ?? `${rows.length} dodatkowych odnośników${search.data?.status === 'partial' ? ' · część źródeł nie odpowiedziała' : ''}.`}</p>
    {search.isError && <button className="text-sm text-primary" onClick={() => search.refetch()}>Ponów wyszukiwanie w sieci</button>}
    {rows.length > 0 && <>
      <p className="text-sm text-slate-500">To odnośniki z wyszukiwarki, jeszcze niezweryfikowane w naszej bazie. Datę i kategorię potwierdzamy u wydawcy przed dodaniem materiału na oś czasu.</p>
      {visible > 0 && <div className="flex overflow-x-auto pb-3">{rows.slice(0, visible).map(row => <article key={row.url} className="w-64 shrink-0 space-y-3 border-r px-4 first:pl-0">
        <span className="text-xs font-semibold uppercase tracking-wider text-primary">{row.category === 'other' ? 'Kategoria do sprawdzenia' : `${categoryLabel(row.category)} · do potwierdzenia`}</span>
        <div className="flex h-28 items-center justify-center rounded-sm bg-slate-100 text-xs text-slate-500">Podgląd u wydawcy</div>
        <h3 className="font-medium"><a href={row.url} target="_blank" rel="noopener noreferrer">{row.title || row.url} ↗</a></h3>
        <p className="text-xs text-slate-500">ŹRÓDŁO · {row.source_name || new URL(row.url).hostname}</p>
        <p className="text-xs text-slate-500">DATA · wymaga potwierdzenia</p>
        <Link className="inline-block text-sm text-primary" href={`/editor?source_url=${encodeURIComponent(row.url)}`}>Dodaj przez warsztat redakcji +</Link>
      </article>)}</div>}
      {visible < rows.length && <button className="rounded-lg border px-4 py-2 text-sm font-semibold text-primary" onClick={() => setVisible(n => n + 5)}>{visible ? 'Pokaż kolejne odnośniki' : `Pokaż znalezione odnośniki (${rows.length})`}</button>}
      <div className="space-y-2"><p className="text-xs text-slate-500">Sprawdzamy dostępne źródła w tle. Odświeżenie bazy może zmienić układ osi czasu.</p><button disabled={refreshingArchive} className="rounded-lg border px-4 py-2 text-sm text-primary disabled:opacity-40" onClick={onRefreshArchive}>{refreshingArchive ? 'Sprawdzam bazę…' : 'Sprawdź nowe wyniki w bazie'}</button></div>
    </>}
  </section>;
}
