/**
 * Zwijanie serii niemal identycznych materiałów jednego źródła (np. „Wniosek złożony podczas 32. sesji
 * Rady Miasta…” × 12) w jeden box z dopiskiem „+N podobnych”. Klucz: źródło + pierwsze 6 słów tytułu
 * przycięte do 4 znaków (odmiana: „wniosek/wnioski”, „złożony/złożone” dają ten sam klucz).
 * Kolejność zachowana — zostaje pierwszy (najnowszy) materiał serii.
 */

import type { Article } from "../../types";

export type Collapsed = { article: Article; similar: number };

function seriesKey(article: Article): string {
  const words = article.title
    .toLocaleLowerCase("pl")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 6)
    .map((word) => word.slice(0, 4));
  return `${article.source.id}:${words.join(" ")}`;
}

export function collapseSimilar(articles: Article[]): Collapsed[] {
  const byKey = new Map<string, Collapsed>();
  const out: Collapsed[] = [];
  for (const article of articles) {
    const key = seriesKey(article);
    const existing = byKey.get(key);
    if (existing) {
      existing.similar += 1;
      continue;
    }
    const entry = { article, similar: 0 };
    byKey.set(key, entry);
    out.push(entry);
  }
  return out;
}
