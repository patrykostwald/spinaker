"use client";

import { useMemo, type ReactNode } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import type { Article } from "../types";
import { apiFetch } from "../lib/api";
import type { ArticleContext as ContextResponse } from "../lib/portal";
import { formatDatePl } from "../lib/utils";
import { NewsStrip } from "./NewsStrip";
import { Button, MorphValue } from "../kit";

export function ArticleContext({ article, onSelect, children }: { article: Article; onSelect: (article: Article) => void; children?: ReactNode }) {
  const context = useInfiniteQuery({ queryKey: ["article-context", article.id], initialPageParam: 1,
    queryFn: ({ pageParam }) => apiFetch<ContextResponse>(`/api/articles/${article.id}/context/?page=${pageParam}`),
    getNextPageParam: last => last.next_page ?? undefined, staleTime: 60_000 });
  const first = context.data?.pages[0];
  const groups = useMemo(() => {
    const result: Record<string, Article[]> = {};
    const seen = new Set<number>();
    for (const page of context.data?.pages ?? []) for (const [date, articles] of Object.entries(page.timeline)) {
      for (const item of articles) if (!seen.has(item.id)) { seen.add(item.id); (result[date] ??= []).push(item); }
    }
    const noDate = (date: string) => date === "undated" || date === "unknown";
    return Object.entries(result).sort(([a], [b]) => noDate(a) ? (noDate(b) ? 0 : 1) : noDate(b) ? -1 : b.localeCompare(a));
  }, [context.data]);

  return <section className="sc-article-context">
    <header className="sc-article-context__head"><div><h2>Kontekst w źródłach</h2><p>Powiązania tematyczne · wcześniejsze i późniejsze publikacje</p></div>{first ? <span aria-label={`${first.total.toLocaleString("pl-PL")} materiałów`}><MorphValue value={first.total} className="sc-article-context__total" /></span> : null}</header>
    {context.isPending ? <p role="status" className="sc-article-context__empty">Szukam powiązanych materiałów w archiwum…</p> : null}
    {context.isError ? <p role="status" className="sc-article-context__empty">Nie udało się pobrać kontekstu. <Button type="button" size="sm" variant="quiet" onClick={() => context.refetch()}>Ponów</Button></p> : null}
    {first ? <><div className="sc-article-context__counts" aria-label="Liczba powiązanych materiałów według kategorii">{first.counts.map(item => <span key={item.category} data-category={item.category}>{item.label}<strong>{item.count.toLocaleString("pl-PL")}</strong></span>)}</div><p className="sc-article-context__method">{first.match_basis || "Dobór na podstawie słów tematu w dostępnych metadanych; nie dowodzi związku przyczynowego."} Zakres obejmuje materiały obecne w naszej bazie.</p>{!first.total ? <p className="sc-article-context__empty">Nie znaleźliśmy jeszcze powiązanych materiałów. Baza jest nadal uzupełniana.</p> : null}</> : null}
    {children}
    <div className="sc-article-context__days">{groups.map(([date, rows]) => <NewsStrip key={date} title={formatDatePl(date)} articles={rows} onSelect={onSelect} />)}</div>
    {context.hasNextPage ? <Button type="button" variant="secondary" loading={context.isFetchingNextPage} onClick={() => context.fetchNextPage()}>Pokaż wcześniejsze powiązania</Button> : null}
  </section>;
}
