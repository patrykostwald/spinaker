"use client";

import type { Article } from "../types";
import { formatDatePl } from "../lib/utils";
import { NewsCard } from "../kit/NewsCard";

export function DateRow({ date, articles }: { date: string; articles: Article[] }) {
  return (
    <section className="sc-search-day" aria-labelledby={`search-day-${date}`}>
      <header className="sc-search-day__head"><h2 id={`search-day-${date}`} className="sc-t-title-s">{formatDatePl(date)}</h2></header>
      <div className="sc-search-day__cards sc-strip-bleed">
        {articles.map((article) => <NewsCard key={article.id} article={article} size="compact" showDescription />)}
      </div>
    </section>
  );
}
