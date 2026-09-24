"use client";

import type { TimelineResponse } from "../types";
import { DateRow } from "./DateRow";

type Props = { timeline: TimelineResponse["timeline"]; emptyLabel?: string };

/** Wyniki są od razu kartami portalu — nie otwierają już równoległego, starego modalu. */
export function TimelineGrid({ timeline, emptyLabel = "Brak wyników." }: Props) {
  const days = Object.keys(timeline);
  if (!days.length) return <p className="sc-search-empty sc-t-body sc-text-2">{emptyLabel}</p>;
  return <div className="sc-search-timeline">{days.map((date) => <DateRow key={date} date={date} articles={timeline[date]} />)}</div>;
}
