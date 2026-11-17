"use client";

import { PositionPairsNote } from "../../kit/PositionPair";
import { normalizeBlock, pairDetailHref } from "../../lib/positionPairs";
import { useFeature } from "../../lib/features";

/**
 * Karta diagnozy: jedna linia "Ta osoba wypowiadała się wcześniej na ten temat: zobacz obok siebie" - tylko gdy API zwróciło
 * zatwierdzoną parę dotyczącą tego wpisu (klucz `position_pairs`, API-v3.md sekcja 5) i flaga NEXT_PUBLIC_POSITION_PAIRS jest włączona.
 * Ta sama reguła dla każdej diagnozy: nie zależy od osoby ani od wyniku diagnozy.
 */
export function DiagnosisPairs({ block, figureId }: { block: unknown; figureId?: number | null }) {
  const enabled = useFeature("POSITION_PAIRS_ENABLED");
  const parsed = enabled ? normalizeBlock(block) : null;
  if (!parsed || parsed.paused || !parsed.items.length) return null;
  return <PositionPairsNote pairs={parsed.items} person={figureId ?? null} detailHref={pairDetailHref} />;
}
