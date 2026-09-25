"use client";

/**
 * Część powiększonego boxa pod miniaturą, tytułem i opisem (overlay portalu i strona /material/<id>):
 * 1) oś czasu 15 najważniejszych powiązanych boxów, 2) pasek reakcji i komentarze,
 * 3) baza powiązanych doniesień — kolumny-kategorie × wiersze-daty („wodospad”).
 */

import type { ReactNode } from "react";
import type { Article } from "../types";
import { MaterialReactions } from "./MaterialReactions";
import { MaterialTimeline } from "./MaterialTimeline";
import { MaterialWaterfall } from "./MaterialWaterfall";

export function MaterialDetails({ article, onSelect, children }: { article: Article; onSelect?: (next: Article) => void; children?: ReactNode }) {
  return (
    <div className="sc-material-details">
      <MaterialTimeline article={article} onSelect={onSelect} />
      {children}
      <MaterialReactions article={article} />
      <MaterialWaterfall article={article} onSelect={onSelect} />
    </div>
  );
}
