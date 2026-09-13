"use client";

import type { Article } from "../types";
import { ArticleCard } from "./ArticleCard";
import { formatDatePl } from "../lib/utils";

type Props = {
  date: string;
  articles: Article[];
  onSelect?: (article: Article) => void;
};

export function DateRow({ date, articles, onSelect }: Props) {
  return (
    <section className="date-track space-y-3 border-l border-primary pl-4">
      <header className="sticky top-0 z-10 bg-slate-50/95 py-2 backdrop-blur">
        <h2 className="text-lg font-medium text-primary">{formatDatePl(date)}</h2>
      </header>
      <div className="flex snap-x snap-mandatory gap-0 overflow-x-auto pb-4">
        {articles.map((article) => (
          <div key={article.id} className="flex w-[260px] shrink-0 snap-start border-r px-3 last:border-r-0"><ArticleCard article={article} onSelect={onSelect} /></div>
        ))}
      </div>
    </section>
  );
}
