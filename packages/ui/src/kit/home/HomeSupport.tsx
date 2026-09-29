"use client";

/**
 * Zbiórka jako zwykła sekcja nad newsletterem (audyt UX i makiety 28.09): licznik miesięczny i obie zbiórki.
 * Przyklejony pasek wsparcia chowa się przy przewijaniu — tu jest stałe miejsce, gdzie widać cel i postęp.
 */

import { useQuery } from "@tanstack/react-query";
import { SUPPORT_LINKS } from "../../lib/support";
import { Button } from "../Button";

export function HomeSupport() {
  const query = useQuery({
    queryKey: ["support-progress"],
    queryFn: async () => (await fetch("/support-progress")).json() as Promise<{ goal: number; raised: number }>,
    staleTime: 5 * 60_000,
  });
  const goal = query.data?.goal ?? 0;
  const raised = query.data?.raised ?? 0;
  const percent = goal > 0 ? Math.min(100, Math.round((raised / goal) * 100)) : 0;
  const format = (value: number) => value.toLocaleString("pl-PL");
  return (
    <section className="sc-home-section sc-home-support" aria-labelledby="home-support-title">
      <div className="sc-home-support__text">
        <h2 id="home-support-title" className="sc-t-title-m">Pomóż nam analizować kolejne wypowiedzi</h2>
        <p>Wpłaty pomagają pokrywać pobieranie wpisów, analizy AI i utrzymanie serwisu.</p>
      </div>
      {goal > 0 ? (
        <div className="sc-home-support__progress" aria-label={`Zebrano ${format(raised)} z ${format(goal)} zł w tym miesiącu`}>
          <p><strong>{format(raised)} zł</strong> z {format(goal)} zł w tym miesiącu</p>
          <span className="sc-support-bar__track" aria-hidden="true"><i style={{ width: `${Math.max(percent, 2)}%` }} /></span>
        </div>
      ) : null}
      <div className="sc-home-support__actions">
        <Button href={SUPPORT_LINKS.monthly} variant="primary" size="sm">Wesprzyj miesięczny budżet</Button>
        <Button href="/wsparcie" variant="secondary" size="sm">Na co idą pieniądze</Button>
      </div>
    </section>
  );
}
