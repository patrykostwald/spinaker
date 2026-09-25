"use client";

/**
 * Oś czasu powiększonego boxa: do 15 najważniejszych powiązanych materiałów w jednej poziomej taśmie,
 * od NAJNOWSZEGO (lewa) do coraz starszych (prawa). Otwarty box stoi na swoim miejscu według daty —
 * jeśli jest najnowszy, jest pierwszy. Kolejność ważności przy wyborze 14 sąsiadów: najpierw
 * `/api/articles/<id>/related/` (dopasowanie po słowach tytułu, ±7 dni, posortowane wg trafności),
 * potem pierwsza strona `/api/articles/<id>/context/` (dopasowanie po słowach kluczowych).
 */

import { useQuery } from "@tanstack/react-query";
import { NewsCard, Strip } from "../kit";
import { apiFetch } from "../lib/api";
import type { ArticleContext as ArticleContextData } from "../lib/portal";
import { formatDatePl, formatTimePl } from "../lib/utils";
import type { Article } from "../types";

export const TIMELINE_SIZE = 15;

export function articleContextPage(id: number, page: number) {
  return { queryKey: ["article-context-page", id, page] as const, queryFn: () => apiFetch<ArticleContextData>(`/api/articles/${id}/context/?page=${page}`), staleTime: 60_000 };
}

function timeOf(article: Article): number {
  const iso = article.published_date;
  const value = iso && iso !== "undated" && iso !== "unknown" ? new Date(iso).getTime() : NaN;
  return Number.isFinite(value) ? value : -Infinity;
}

/** 14 najważniejszych sąsiadów + otwarty box, posortowane od najnowszego. */
export function buildTimeline(article: Article, related: Article[], context: Article[]): Article[] {
  const picked = new Map<number, Article>();
  for (const item of [...related, ...context]) {
    if (item.id === article.id || picked.has(item.id)) continue;
    picked.set(item.id, item);
    if (picked.size >= TIMELINE_SIZE - 1) break;
  }
  return [article, ...picked.values()].sort((a, b) => timeOf(b) - timeOf(a) || b.id - a.id);
}

function dateLabel(article: Article): string {
  const iso = article.published_date;
  if (!iso || iso === "undated" || iso === "unknown") return "Data nieustalona";
  return `${formatDatePl(iso)} · ${formatTimePl(iso)}`;
}

export function MaterialTimeline({ article, onSelect }: { article: Article; onSelect?: (next: Article) => void }) {
  const related = useQuery({
    queryKey: ["article-related", article.id],
    queryFn: () => apiFetch<{ related: Article[] }>(`/api/articles/${article.id}/related/`).then((result) => result.related),
    staleTime: 60_000,
  });
  const context = useQuery(articleContextPage(article.id, 1));
  const contextArticles = context.data ? Object.values(context.data.timeline).flat() : [];
  const loading = related.isPending || context.isPending;
  const items = buildTimeline(article, related.data ?? [], contextArticles);
  const position = items.findIndex((item) => item.id === article.id);

  return (
    <section className="sc-material-timeline" aria-label="Oś czasu powiązanych materiałów">
      <header className="sc-material-timeline__head">
        <div>
          <p className="sc-t-caption sc-text-3">Oś czasu</p>
          <h3 className="sc-t-title-s">Najważniejsze powiązane doniesienia</h3>
        </div>
        <p className="sc-t-meta sc-text-2">
          {loading ? "Szukam powiązanych materiałów…" : items.length > 1 ? `${items.length} materiałów · od najnowszego do najstarszego · ten box: ${position + 1}.` : "Nie znaleźliśmy jeszcze powiązanych materiałów."}
        </p>
      </header>
      {items.length > 1 || loading ? (
        <Strip label="Oś czasu powiązanych materiałów" slot="260px">
          {items.map((item) => {
            const current = item.id === article.id;
            return (
              <div key={item.id} className="sc-strip__slot sc-material-timeline__slot" data-current={current || undefined}>
                <div className="sc-material-timeline__inner">
                  <p className="sc-t-meta sc-material-timeline__date">
                    <span className="sc-material-timeline__dot" aria-hidden="true" />
                    {dateLabel(item)}
                    {current ? <strong className="sc-material-timeline__here"> · ten box</strong> : null}
                  </p>
                  <NewsCard article={item} size="mini" headingLevel={4} expandable={false} onOpen={current ? () => undefined : onSelect} />
                </div>
              </div>
            );
          })}
        </Strip>
      ) : null}
    </section>
  );
}
