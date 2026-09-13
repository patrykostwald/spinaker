"use client";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch, apiWrite } from '../lib/api';
import type { Article } from '../types';
import { TimelineGrid } from './TimelineGrid';
type Result = {enabled: boolean; status: string; articles: Article[]; next_token: string | null; notice?: string};
export function YouTubeSearch({query}: {query: string}) {
 const config = useQuery({queryKey: ['youtube-config'], queryFn: () => apiFetch<Result>('/api/youtube/search/')});
 const [result, setResult] = useState<Result | null>(null);
 const [busy, setBusy] = useState(false); const [error, setError] = useState('');
 const search = async (token = '') => { setBusy(true); setError(''); try {
   const next = await apiWrite<Result>('/api/youtube/search/', {q: query, page_token: token});
   setResult(old => ({...next, articles: token ? [...(old?.articles ?? []), ...next.articles].filter((a,i,all) => all.findIndex(b => b.id === a.id) === i) : next.articles}));
 } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się pobrać wyników YouTube.'); } finally { setBusy(false); } };
 const timeline: Record<string, Article[]> = {};
 for (const a of result?.articles ?? []) { const day = a.published_date ? new Intl.DateTimeFormat('sv-SE', {timeZone: 'Europe/Warsaw', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date(a.published_date)) : 'undated'; (timeline[day] ??= []).push(a); }
 return <section className="space-y-4 border-t pt-6"><h2 className="font-bold">Materiały wideo · YouTube</h2>{config.data?.enabled ? <><button disabled={busy || !query.trim()} onClick={() => search()} className="rounded-lg border px-4 py-2 text-primary">{busy ? 'Szukam…' : 'Sprawdź tę frazę także na YouTube'}</button>{result && <><p className="text-sm text-slate-500">{result.notice}</p><TimelineGrid timeline={timeline} emptyLabel="YouTube nie zwrócił materiałów dla tej frazy." />{result.next_token && <button disabled={busy} onClick={() => search(result.next_token!)} className="text-primary">Pokaż kolejne filmy</button>}</>}</> : <p className="text-sm text-slate-500">Wyszukiwanie YouTube czeka na konfigurację integracji. Filmy dodane do bazy pozostają dostępne w wynikach powyżej.</p>}{error && <p role="alert" className="text-red-700">{error}</p>}</section>;
}
