"use client";

import React from "react";
import { HorizontalTimeline } from "./HorizontalTimeline";
import { useLiveResearch, type ResearchSection } from "../lib/useLiveResearch";
import { Button } from "../kit";

function CitedText({ section }: { section: ResearchSection }) {
  const chars = Array.from(section.text);
  let cursor = 0;
  const pieces: React.ReactNode[] = [];
  section.citations.forEach((citation, index) => {
    pieces.push(chars.slice(cursor, citation.start).join(""));
    pieces.push(<a key={index} href={citation.url} target="_blank" rel="noopener noreferrer">{chars.slice(citation.start, citation.end).join("") || `[${index + 1}]`}</a>);
    cursor = citation.end;
  });
  pieces.push(chars.slice(cursor).join(""));
  return <p>{pieces}</p>;
}

export function ResearchProgress({ search }: { search: ReturnType<typeof useLiveResearch> }) {
  if (!search.query.trim()) return null;
  const citedUrls = new Set(search.result?.sources.map(source => source.url) ?? []);
  const timelineArticles = search.articles.filter(article => citedUrls.has(article.url) && article.published_date)
    .sort((a, b) => Date.parse(a.published_date!) - Date.parse(b.published_date!) || a.id - b.id).slice(0, 15);

  return <section aria-label="Wyszukiwanie AI" className="sc-research-progress">
    <header>
      <p>SPIN.CLINIC · WYSZUKIWANIE ŹRÓDEŁ</p>
      <div>
        {(search.busy || search.enriching) ? <Button type="button" variant="quiet" size="sm" onClick={search.stop}>Zatrzymaj</Button> : null}
        {["error", "stopped"].includes(search.phase) ? <Button type="button" variant="quiet" size="sm" onClick={search.retry}>Ponów wyszukiwanie AI</Button> : null}
      </div>
    </header>
    <div className="sc-research-progress__status" role="status">
      <span aria-hidden="true" data-active={search.busy || undefined} />
      <p>{search.message || "Sprawdzam dostępność wyszukiwania internetowego…"}{search.sources.length > 0 ? <> <strong>Znalezione odnośniki: {search.sources.length}.</strong></> : null}</p>
    </div>
    {search.enriching ? <p className="sc-research-progress__note">Odczytuję dostępne metadane u wydawców. Pełne boxy będą pojawiały się poniżej.</p> : null}
    {search.result ? <div className="sc-research-progress__result">
      <div><h2>Kontekst tematu</h2><p>do 15 materiałów · od najstarszego · wybór AI do sprawdzenia</p></div>
      {timelineArticles.length ? <HorizontalTimeline items={timelineArticles.map((article, position) => ({ id: article.id, position, editorial_note: "", article }))} /> : <p className="sc-research-progress__note">Oś czasu powstanie z materiałów, których datę uda się odczytać. Znalezione linki są dostępne poniżej.</p>}
      <details><summary>Notatka AI i odniesienia do źródeł</summary>{search.result.sections.map((section, index) => <CitedText key={index} section={section} />)}<p className="sc-research-progress__note">{search.result.limitation}</p></details>
    </div> : null}
  </section>;
}

export function AIResearch({ initialQuery = "" }: { initialQuery?: string; autoStart?: boolean; navigateSearch?: boolean }) {
  const search = useLiveResearch(initialQuery);
  return <ResearchProgress search={search} />;
}
