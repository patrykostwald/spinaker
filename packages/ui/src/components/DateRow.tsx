"use client";

import type { Article } from "../types";
import { formatDatePl } from "../lib/utils";
import { NewsCard } from "../kit/NewsCard";
import { Strip } from "../kit/home/Strip";

/** Jeden dzień wyników = jeden poziomy pasek miniatur (jak „Twoje wiadomości”), przewijany w bok, bez pełnych opisów. */
export function DateRow({ date, articles }: { date: string; articles: Article[] }) {
  const label = formatDatePl(date);
  return (
    <section className="sc-search-day" aria-labelledby={`search-day-${date}`}>
      <header className="sc-search-day__head"><h2 id={`search-day-${date}`} className="sc-t-title-s">{label} <span className="sc-text-3">· {articles.length}</span></h2></header>
      <Strip label={`Materiały z dnia ${label}`}>
        {articles.map((article) => (
          <div key={article.id} className="sc-strip__slot">
            <NewsCard article={article} size="compact" headingLevel={3} expandable={false} />
          </div>
        ))}
      </Strip>
    </section>
  );
}
