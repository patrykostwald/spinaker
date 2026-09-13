'use client';
import React from 'react';
import { HorizontalTimeline } from './HorizontalTimeline';
import { useLiveResearch, type ResearchSection } from '../lib/useLiveResearch';

function CitedText({ section }: { section: ResearchSection }) {
  const chars = Array.from(section.text);
  let cursor = 0;
  const pieces: React.ReactNode[] = [];
  section.citations.forEach((citation, index) => {
    pieces.push(chars.slice(cursor, citation.start).join(''));
    pieces.push(<a key={index} href={citation.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">{chars.slice(citation.start, citation.end).join('') || `[${index + 1}]`}</a>);
    cursor = citation.end;
  });
  pieces.push(chars.slice(cursor).join(''));
  return <p className="whitespace-pre-wrap text-sm leading-relaxed">{pieces}</p>;
}

export function ResearchProgress({ search }: { search: ReturnType<typeof useLiveResearch> }) {
  if (!search.query.trim()) return null;
  const citedUrls = new Set(search.result?.sources.map(source => source.url) ?? []);
  const timelineArticles = search.articles.filter(article => citedUrls.has(article.url) && article.published_date)
    .sort((a, b) => Date.parse(a.published_date!) - Date.parse(b.published_date!) || a.id - b.id).slice(0, 15);
  return <section aria-label="Wyszukiwanie AI" className="research-panel space-y-3 border-y py-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-xs font-medium uppercase tracking-widest text-slate-400">spin.clinic · wyszukiwanie źródeł</p>
      <div className="flex items-center gap-3 text-xs">
        {(search.busy || search.enriching) && <button onClick={search.stop} className="text-slate-400 underline underline-offset-4">Zatrzymaj</button>}
        {['error', 'stopped'].includes(search.phase) && <button onClick={search.retry} className="text-primary underline underline-offset-4">Ponów wyszukiwanie AI</button>}
      </div>
    </div>
    <div className="flex items-start gap-3 text-sm text-slate-400" role="status">
      <span aria-hidden="true" className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${search.busy ? 'research-pulse bg-primary' : 'bg-slate-500'}`} />
      <p>{search.message || 'Sprawdzam dostępność wyszukiwania internetowego…'}{search.sources.length > 0 && <span className="ml-2 text-slate-200">Znalezione odnośniki: {search.sources.length}.</span>}</p>
    </div>
    {search.enriching && <p className="pl-4 text-xs text-slate-500">Odczytuję dostępne metadane u wydawców. Pełne boxy będą pojawiały się poniżej.</p>}
    {search.result && <div className="space-y-3 pt-2">
      <div className="flex flex-wrap items-baseline gap-3"><h2 className="text-base font-medium">Kontekst tematu</h2><span className="text-xs text-slate-500">do 15 materiałów · od najstarszego · wybór AI do sprawdzenia</span></div>
      {timelineArticles.length > 0 ? <HorizontalTimeline items={timelineArticles.map((article, position) => ({ id: article.id, position, editorial_note: '', article }))} /> : <p className="text-xs text-slate-400">Oś czasu powstanie z materiałów, których datę uda się odczytać. Znalezione linki są dostępne poniżej.</p>}
      <details className="space-y-3"><summary className="cursor-pointer text-xs text-slate-400">Notatka AI i odniesienia do źródeł</summary>{search.result.sections.map((section, index) => <CitedText key={index} section={section} />)}<p className="text-xs text-slate-500">{search.result.limitation}</p></details>
    </div>}
  </section>;
}

export function AIResearch({ initialQuery = '' }: { initialQuery?: string; autoStart?: boolean; navigateSearch?: boolean }) {
  const search = useLiveResearch(initialQuery);
  return <ResearchProgress search={search} />;
}
