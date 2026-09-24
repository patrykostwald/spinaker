"use client";

import { useMemo, useState } from "react";
import { NewsCard } from "../../NewsCard";
import { makeArticles } from "../fixtures";

export const meta = {
  id: "wydajnosc",
  title: "Wydajność",
  lead: "Powtarzalna próba 240 kart materiałów. Służy do kontroli filtrowania, przewijania i stabilności siatki przed wydaniem beta.",
};

const ARTICLES = makeArticles(240, 240);
const FILTERS = ["wszystkie", "article", "document", "video", "voting"] as const;
type Filter = (typeof FILTERS)[number];

const LABELS: Record<Filter, string> = {
  wszystkie: "Wszystkie",
  article: "Artykuły",
  document: "Dokumenty",
  video: "Filmy",
  voting: "Głosowania",
};

export function Section() {
  const [filter, setFilter] = useState<Filter>("wszystkie");
  const visible = useMemo(
    () => ARTICLES.filter((article) => filter === "wszystkie" || article.category === filter),
    [filter],
  );

  return (
    <div className="sc-performance-probe">
      <div className="sc-performance-probe__bar">
        <div className="sc-showcase__seg" role="group" aria-label="Filtr próby 240 kart">
          {FILTERS.map((item) => (
            <button key={item} type="button" aria-pressed={filter === item} onClick={() => setFilter(item)}>
              {LABELS[item]}
            </button>
          ))}
        </div>
        <p className="sc-t-body-s sc-text-2" aria-live="polite">
          Widocznych: <strong>{visible.length}</strong> z 240 kart demonstracyjnych.
        </p>
      </div>
      <div className="sc-performance-probe__grid" data-card-count={visible.length}>
        {visible.map((article) => (
          <NewsCard key={article.id} article={article} size="mini" expandable={false} />
        ))}
      </div>
    </div>
  );
}
