"use client";

import { useState } from "react";

import type { Article, TimelineResponse } from "../types";
import { ArticleModal } from "./ArticleModal";
import { DateRow } from "./DateRow";

type Props = {
  timeline: TimelineResponse["timeline"];
  emptyLabel?: string;
};

export function TimelineGrid({ timeline, emptyLabel = "Brak wyników." }: Props) {
  const [selected, setSelected] = useState<Article | null>(null);
  const days = Object.keys(timeline);

  if (!days.length) {
    return <p className="py-16 text-center text-slate-500">{emptyLabel}</p>;
  }

  return (
    <>
      <div className="space-y-10">
        {days.map((date) => (
          <DateRow key={date} date={date} articles={timeline[date]} onSelect={setSelected} />
        ))}
      </div>
      <ArticleModal article={selected} onClose={() => setSelected(null)} />
    </>
  );
}
