"use client";

/**
 * Rząd czterech najnowszych materiałów (`mini`) nad heroem — wzór: pasek „ostatnie wyniki”
 * w referencji. Na tablecie 2×2, na telefonie taśma pozioma.
 */

import { NewsCard } from "../NewsCard";
import type { Article } from "../../types";
import { EmptySlot } from "./Strip";

export function HomeTicker({ articles }: { articles: Article[] }) {
  const slots = Array.from({ length: 4 }, (_, i) => articles[i] ?? null);
  return (
    <section className="sc-home-ticker" aria-label="Najnowsze materiały">
      {slots.map((article, index) =>
        article ? (
          <NewsCard key={article.id} article={article} size="mini" headingLevel={3} />
        ) : (
          <EmptySlot key={`empty-${index}`} index={index + 1} label="Najnowszy materiał" />
        ),
      )}
    </section>
  );
}
