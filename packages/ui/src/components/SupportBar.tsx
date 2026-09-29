"use client";

import { useQuery } from "@tanstack/react-query";
import { SUPPORT_LINKS } from "../lib/support";

/**
 * Pasek wsparcia przyklejony nad stopką: jedno zdanie po lewej, po prawej — ile zebraliśmy w tym miesiącu
 * (nad przyciskiem „Wesprzyj projekt”). Kwoty z /support-progress (zmienne środowiska serwera).
 */
export function SupportBar() {
  const query = useQuery({
    queryKey: ["support-progress"],
    queryFn: async () => (await fetch("/support-progress")).json() as Promise<{ goal: number; raised: number }>,
    staleTime: 5 * 60_000,
  });
  const data = query.data;
  // Bez ustawionego celu zostaje samo zdanie — licznik pojawia się, gdy SUPPORT_MONTHLY_GOAL_PLN > 0.
  const goal = data?.goal ?? 0;
  const raised = data?.raised ?? 0;
  const percent = goal > 0 ? Math.min(100, Math.round((raised / goal) * 100)) : 0;
  const format = (value: number) => value.toLocaleString("pl-PL");
  return (
    <div className="sc-support-bar">
      <p className="sc-support-bar__text">Wpłaty pomagają pokrywać pobieranie wpisów, analizy AI i utrzymanie serwisu.</p>
      {goal > 0 ? (
        <a className="sc-support-bar__progress" href={SUPPORT_LINKS.monthly} target="_blank" rel="noopener noreferrer" aria-label={`Zebrano ${format(raised)} z ${format(goal)} zł w tym miesiącu`}>
          <span className="sc-support-bar__amount"><strong>{format(raised)} zł</strong> z {format(goal)} zł w tym miesiącu</span>
          <span className="sc-support-bar__track" aria-hidden="true"><i style={{ width: `${Math.max(percent, 2)}%` }} /></span>
        </a>
      ) : null}
    </div>
  );
}
