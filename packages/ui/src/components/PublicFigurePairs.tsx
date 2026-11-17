"use client";

import { useQuery } from "@tanstack/react-query";
import { PositionPairs } from "../kit/PositionPair";
import { fetchPersonPairs } from "../lib/positionPairs";
import { useFeature } from "../lib/features";

/**
 * Profil osoby publicznej na spin.clinic (/osoby-publiczne/<id>): sekcja "Wcześniej i teraz" z listy osoby
 * (GET /api/przeszlosc/osoba/<id>/stanowiska/). Za flagą NEXT_PUBLIC_POSITION_PAIRS; bez par (albo gdy API odpowie 404) nic nie
 * pokazujemy. Ta sama miara dla każdej osoby: zapytanie i wygląd nie zależą od osoby.
 */
export function PublicFigurePairs({ figureId }: { figureId: number }) {
  const enabled = useFeature("POSITION_PAIRS_ENABLED");
  const query = useQuery({ queryKey: ["position-pairs", figureId], queryFn: () => fetchPersonPairs(figureId), enabled, staleTime: 5 * 60_000, retry: false });
  if (!enabled || !query.data) return null;
  return <div className="sc-v3" style={{ marginTop: "var(--sc-sec, 64px)" }}><PositionPairs block={query.data} /></div>;
}
