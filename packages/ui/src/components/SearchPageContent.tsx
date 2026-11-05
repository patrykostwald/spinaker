"use client";
import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { searchTimeline } from "../lib/api";
import { ExternalSearchResults } from "./ExternalSearchResults";
import { SourceCoverage } from "./SourceCoverage";
import { ResearchProgress } from "./AIResearch";
import { ArchiveProgress } from "./ArchiveProgress";
import { useLiveResearch } from "../lib/useLiveResearch";
import { mergeSearchTimeline } from "../lib/search-timeline";
import { formatDateTimePl } from "../lib/utils";
import { SearchBar } from "./SearchBar";
import { TimelineGrid } from "./TimelineGrid";
import { FigureMatch } from "./FigureMatch";
import { Button } from "../kit/Button";
import { Checkbox } from "../kit/Checkbox";
import { Dropdown } from "../kit/Dropdown";
const categories = [["factcheck", "Fact-checki"], ["context", "Kontekst"], ["voting", "Głosowania Sejmu"], ["legislation", "Akty prawne / obwieszczenia"], ["parliamentary_print", "Druki sejmowe"], ["document", "Dokumenty urzędowe"], ["article", "Artykuły"], ["interview", "Wywiady"], ["reportage", "Reportaże"], ["statement", "Komunikaty / oświadczenia"], ["mention", "Wzmianki"], ["sponsored", "Sponsorowane"], ["advertisement", "Reklamy"], ["video", "Filmy"], ["podcast", "Podcasty"], ["opinion", "Opinie"], ["other", "Inne"]] as const;

const categoryValues = new Set<string>(categories.map(([value]) => value));
const validDate = (value: string | null) => value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : "";

export function SearchPageContent() {
  const params = useSearchParams(); const router = useRouter(); const pathname = usePathname(); const q = params.get("q") ?? ""; const queryValid = q.length <= (/^https?:\/\//.test(q) ? 1024 : 200);
  const research = useLiveResearch(queryValid ? q : ""); const [live, setLive] = useState(true);
  // Filtry żyją w adresie (?categories=…&from=…&to=…): link do wyników można przesłać dalej.
  const fromDate = validDate(params.get("from")); const toDate = validDate(params.get("to"));
  const selected = (params.get("categories") ?? "").split(",").filter(value => categoryValues.has(value)); const invalid = Boolean(fromDate && toDate && fromDate > toDate);
  function setFilters(values: { categories?: string[]; from?: string; to?: string }) {
    const next = new URLSearchParams(params.toString());
    const apply = (key: string, value: string | undefined) => { if (value === undefined) return; if (value) next.set(key, value); else next.delete(key); };
    apply("categories", values.categories?.join(",")); apply("from", values.from); apply("to", values.to);
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }
  const results = useInfiniteQuery({ queryKey: ["timeline", q, selected, fromDate, toDate], initialPageParam: 1, refetchOnWindowFocus: false, staleTime: 5000, retry: false, queryFn: ({ pageParam }) => searchTimeline(q, selected.join(","), fromDate, toDate, pageParam), getNextPageParam: last => last.next_page ?? undefined, refetchInterval: query => live && !query.state.error && (query.state.data?.pages.length ?? 0) <= 1 ? 5000 : false, enabled: Boolean(q.trim()) && !invalid && queryValid });
  const timeline = mergeSearchTimeline(results.data?.pages ?? [], research.articles, selected, fromDate, toDate); const storedUrls = new Set(research.articles.map(article => article.url)); const pending = research.sources.filter(source => !storedUrls.has(source.url)); const visibleCount = Object.values(timeline).reduce((count, articles) => count + articles.length, 0);
  return <div className="sc-search-page"><ArchiveProgress /><header className="sc-search-page__head"><div><h1 className="sc-t-title-l">{q ? <>Wyniki dla: <span>{q}</span></> : "Znajdź kontekst"}</h1><p className="sc-t-body sc-text-2">Przeszukujemy materiały z naszej bazy (artykuły, głosowania, dokumenty) i układamy je na osi czasu.{q ? <> Diagnozy spinu znajdziesz w <Link href={`/klinika/diagnozy?q=${encodeURIComponent(q)}`}>Bazie diagnoz</Link>.</> : null}</p></div><div className="sc-search-page__live"><Checkbox label="Odświeżaj wyniki na żywo" checked={live} onChange={setLive} /><p className="sc-t-caption sc-text-2">Co kilka sekund dopisuje nowe materiały z bazy, dopóki trwa wyszukiwanie.</p></div></header>{!q ? <SearchBar /> : null}{!queryValid ? <p role="alert" className="sc-search-page__notice">Wpisz hasło do 200 znaków lub URL do 1024 znaków.</p> : null}
    {Boolean(results.data?.pages[0]?.direct_results?.length) ? <section className="sc-search-votes" aria-label="Głosowania odpowiadające na pytanie"><h2 className="sc-t-title-s">Głosowania · dane Sejmu</h2><p className="sc-t-caption sc-text-2">Najnowsze pasujące głosowania. Pełną listę znajdziesz na osi.</p>{results.data?.pages[0]?.direct_results?.map(article => <article key={article.id}><a href={article.url} target="_blank" rel="noopener noreferrer" className="sc-search-votes__link">{article.title} ↗</a><p className="sc-t-caption sc-text-2">{formatDateTimePl(article.published_date, article.date_precision)} · posiedzenie {article.voting?.sitting}, głosowanie {article.voting?.number}</p>{article.voting?.matching_ballots.map(ballot => <p key={ballot.mp_id} className="sc-t-body">{ballot.name}: <strong>{({ YES: "Za", NO: "Przeciw", ABSTAIN: "Wstrzymał(a) się", ABSENT: "Nieobecność" } as Record<string, string>)[ballot.vote] ?? ballot.vote}</strong></p>)}</article>)}</section> : null}
    <ResearchProgress search={research} /><div className="sc-search-filters"><label>Od dnia<input aria-label="Od dnia" type="date" value={fromDate} onChange={event => setFilters({ from: event.target.value })} /></label><label>Do dnia<input aria-label="Do dnia" type="date" value={toDate} onChange={event => setFilters({ to: event.target.value })} /></label><Dropdown label={`Typ materiału · ${selected.length || "wszystkie"}`} ariaLabel="Typ materiału" mode="multi" items={categories.map(([value, label]) => ({ value, label }))} value={selected} onChange={value => setFilters({ categories: Array.isArray(value) ? value : [] })} presentation="auto" /><Button variant="quiet" size="md" type="button" onClick={() => setFilters({ categories: [], from: "", to: "" })}>Wyczyść filtry</Button></div><SourceCoverage />
    {invalid ? <p role="alert" className="sc-search-page__notice">Data końcowa musi być późniejsza od początkowej.</p> : !q.trim() || !queryValid ? <p className="sc-search-empty sc-t-body sc-text-2">Wpisz temat lub nazwisko, aby zobaczyć historię doniesień.</p> : results.isPending ? <p role="status" className="sc-search-empty sc-t-body">Ładuję oś czasu…</p> : <>{results.isError ? <div role="alert" className="sc-search-page__notice"><p>Nie udało się odświeżyć bazy. Zachowujemy odebrane wyniki.</p><Button variant="quiet" size="sm" onClick={() => results.refetch()}>Spróbuj ponownie</Button></div> : null}<FigureMatch query={q} /><p role="status" className="sc-t-meta sc-text-2">Pasujące do hasła w bazie: {results.data?.pages[0]?.total ?? 0} · na osi: {visibleCount}{research.articles.length ? " · uwzględnia odniesienia z wyszukiwania AI" : ""}</p><TimelineGrid timeline={timeline} emptyLabel="Brak materiałów. Spróbuj innej frazy lub szerszego zakresu dat." />{results.hasNextPage ? <Button variant="secondary" size="md" loading={results.isFetchingNextPage} onClick={() => results.fetchNextPage()}>Pokaż starsze materiały</Button> : null}</>}
    {pending.length ? <section className="sc-search-links" aria-label="Odnalezione odnośniki"><h2 className="sc-t-title-s">Znalezione w internecie · metadane do odczytania</h2><p className="sc-t-caption sc-text-2">Linki pozostają dostępne, gdy wydawca nie udostępnia daty lub miniatury.</p><div>{pending.map(source => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer"><span className="sc-t-caption">{source.source_name}</span><strong className="sc-t-body">{source.title || source.url}</strong><span className="sc-t-caption sc-text-2">Data nieustalona · otwórz źródło ↗</span></a>)}</div></section> : null}
    {q.trim() && queryValid && !invalid ? <ExternalSearchResults key={`${q}|${selected.join(",")}|${fromDate}|${toDate}`} query={q} categories={selected.join(",")} fromDate={fromDate} toDate={toDate} onRefreshArchive={() => { void results.refetch(); }} refreshingArchive={results.isFetching} /> : null}
  </div>;
}
