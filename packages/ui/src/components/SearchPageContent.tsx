"use client";
import { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { searchTimeline } from '../lib/api';
import { ExternalSearchResults } from './ExternalSearchResults';
import { SourceCoverage } from './SourceCoverage';
import { ResearchProgress } from './AIResearch';
import { ArchiveProgress } from './ArchiveProgress';
import { useLiveResearch } from '../lib/useLiveResearch';
import { mergeSearchTimeline } from '../lib/search-timeline';
import { formatDateTimePl } from '../lib/utils';
import { SearchBar } from './SearchBar';
import { TimelineGrid } from './TimelineGrid';
const categories = [['factcheck', 'Fact-checki'], ['context', 'Kontekst'], ['voting', 'Głosowania Sejmu'], ['legislation', 'Akty prawne / obwieszczenia'], ['parliamentary_print', 'Druki sejmowe'], ['document', 'Dokumenty urzędowe'], ['article', 'Artykuły'], ['interview', 'Wywiady'], ['reportage', 'Reportaże'], ['statement', 'Komunikaty / oświadczenia'], ['mention', 'Wzmianki'], ['sponsored', 'Sponsorowane'], ['advertisement', 'Reklamy'], ['video', 'Filmy'], ['podcast', 'Podcasty'], ['opinion', 'Opinie'], ['other', 'Inne']];
export function SearchPageContent() {
  const params = useSearchParams();
  const q = params.get('q') ?? '';
  const queryValid = q.length <= (/^https?:\/\//.test(q) ? 1024 : 200);
  const research = useLiveResearch(queryValid ? q : '');
  const [live, setLive] = useState(true);
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const invalid = Boolean(fromDate && toDate && fromDate > toDate);
  const results = useInfiniteQuery({ queryKey: ['timeline', q, selected, fromDate, toDate],
    initialPageParam: 1,
    refetchOnWindowFocus: false, staleTime: 5000, retry: false,
    queryFn: ({ pageParam }) => searchTimeline(q, selected.join(','), fromDate, toDate, pageParam), getNextPageParam: last => last.next_page ?? undefined,
    refetchInterval: query => live && !query.state.error && (query.state.data?.pages.length ?? 0) <= 1 ? 5000 : false,
    enabled: Boolean(q.trim()) && !invalid && queryValid });
  const timeline = mergeSearchTimeline(results.data?.pages ?? [], research.articles, selected, fromDate, toDate);
  const storedUrls = new Set(research.articles.map(article => article.url));
  const pending = research.sources.filter(source => !storedUrls.has(source.url));
  const visibleCount = Object.values(timeline).reduce((count, articles) => count + articles.length, 0);
  return <div className="space-y-6">
    <ArchiveProgress />
    <div className="flex flex-wrap items-baseline justify-between gap-3"><h1 className="min-w-0 break-words text-xl font-medium">{q ? <>Wyniki dla: <span className="text-primary">{q}</span></> : 'Znajdź kontekst'}</h1><label className="flex items-center gap-2 text-xs text-slate-400"><input type="checkbox" checked={live} onChange={event => setLive(event.target.checked)} />Aktualizuj wyniki bazy</label></div>
    {!q && <SearchBar />}
    {!queryValid && <p role="alert">Wpisz hasło do 200 znaków lub URL do 1024 znaków.</p>}
    {Boolean(results.data?.pages[0]?.direct_results?.length) && <section aria-label="Głosowania odpowiadające na pytanie" className="border-b pb-5">
      <h2 className="text-lg font-semibold">Głosowania · dane Sejmu</h2>
      <p className="mt-2 text-xs text-slate-400">Najnowsze pasujące głosowania. Pełną listę znajdziesz poniżej.</p>
      <div className="mt-3 space-y-3">{results.data?.pages[0]?.direct_results?.map(article => <div key={article.id} className="border-l pl-3">
        <a className="text-sm font-semibold" href={article.url} target="_blank" rel="noopener noreferrer">{article.title} ↗</a>
        <p className="text-xs text-slate-500">{formatDateTimePl(article.published_date, article.date_precision)} · posiedzenie {article.voting?.sitting}, głosowanie {article.voting?.number}</p>
        {article.voting?.matching_ballots.map(ballot => <p key={ballot.mp_id} className="text-sm text-slate-400">{ballot.name}: <strong className="text-slate-200">{({YES: 'ZA', NO: 'PRZECIW', ABSTAIN: 'WSTRZYMAŁ/A SIĘ', ABSENT: 'NIEOBECNY/A'} as Record<string,string>)[ballot.vote] ?? ballot.vote}</strong></p>)}
      </div>)}</div>
    </section>}
    <ResearchProgress search={research} />
    <div className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4">
      <label className="text-sm font-medium">Od dnia<input aria-label="Od dnia" className="mt-1 block rounded-lg border p-2" type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} /></label>
      <label className="text-sm font-medium">Do dnia<input aria-label="Do dnia" className="mt-1 block rounded-lg border p-2" type="date" value={toDate} onChange={e => setToDate(e.target.value)} /></label>
      <details className="relative"><summary className="cursor-pointer rounded-lg border px-4 py-2 text-sm">Kategorie · {selected.length || 'wszystkie'}</summary><div className="absolute left-0 z-20 mt-2 grid w-64 gap-2 rounded-xl border bg-white p-4 shadow-lg">{categories.map(([key, label]) => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selected.includes(key)} onChange={() => setSelected(current => current.includes(key) ? current.filter(c => c !== key) : [...current, key])} />{label}</label>)}</div></details>
      <button className="rounded-lg px-3 py-2 text-sm text-primary" onClick={() => { setFromDate(''); setToDate(''); setSelected([]); }}>Wyczyść filtry</button>
    </div>
    <SourceCoverage />
    {invalid ? <p role="alert">Data końcowa musi być późniejsza od początkowej.</p> : !q.trim() || !queryValid ? <p className="py-12 text-center text-slate-500">Wpisz temat lub nazwisko, aby zobaczyć historię doniesień.</p> : results.isPending ? <p role="status">Ładuję oś czasu…</p> : <>
      {results.isError && <div role="alert" className="border-l border-red-200 p-3"><p>Nie udało się odświeżyć bazy. Zachowujemy odebrane wyniki.</p><button className="mt-2 text-primary" onClick={() => results.refetch()}>Spróbuj ponownie</button></div>}
      <p role="status" className="text-sm text-slate-500">Pasujące do hasła w bazie: {results.data?.pages[0]?.total ?? 0} · na osi: {visibleCount}{research.articles.length > 0 ? ' · uwzględnia odniesienia z wyszukiwania AI' : ''}</p>
      <TimelineGrid timeline={timeline} emptyLabel="Brak materiałów. Spróbuj innej frazy lub szerszego zakresu dat." />
      {results.hasNextPage && <button className="rounded-lg border px-5 py-3 font-semibold text-primary" disabled={results.isFetchingNextPage} onClick={() => results.fetchNextPage()}>{results.isFetchingNextPage ? 'Ładuję…' : 'Pokaż starsze materiały'}</button>}
    </>}

    {pending.length > 0 && <section aria-label="Odnalezione odnośniki" className="border-t pt-4">
      <h2 className="text-sm font-medium">Znalezione w internecie · metadane do odczytania</h2>
      <p className="mt-1 text-xs text-slate-400">Te linki pozostają dostępne także wtedy, gdy wydawca nie udostępnia daty lub miniatury. Filtry dat i kategorii dotyczą materiałów już sklasyfikowanych na osi powyżej.</p>
      <div className="mt-3 flex gap-3 overflow-x-auto pb-3">{pending.map(source => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer" className="w-60 shrink-0 border-l px-3 py-2 text-xs transition-colors hover:bg-white/5"><span className="block text-primary">{source.source_name}</span><span className="my-2 block break-words leading-relaxed">{source.title || source.url}</span><span className="text-slate-500">Data nieustalona · otwórz źródło ↗</span></a>)}</div>
    </section>}

    {q.trim() && queryValid && !invalid && <ExternalSearchResults key={`${q}|${selected.join(',')}|${fromDate}|${toDate}`} query={q} categories={selected.join(',')} fromDate={fromDate} toDate={toDate} onRefreshArchive={() => { void results.refetch(); }} refreshingArchive={results.isFetching} />}
  </div>;
}
