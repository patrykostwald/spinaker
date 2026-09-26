"use client";

/**
 * Pasek reakcji powiększonego boxa: przydatne / nieprzydatne / komentarze (z `/api/articles/<id>/opinions/`),
 * a pod nim pełne `ArticleOpinions` (reakcja + opcjonalny komentarz, po jednym na konto) w ograniczonym,
 * przewijanym obszarze. Reakcje i komentarze dotyczą boxów i nitek kontekstowych, nie pasków newsowych.
 */

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { Article } from "../types";
import { ArticleOpinions } from "./ArticleOpinions";
import { ACCOUNTS_ENABLED } from "../lib/features";

type OpinionSide = { results: unknown[]; next_page: number | null };
type OpinionSummary = { counts: { positive: number; negative: number }; positive: OpinionSide; negative: OpinionSide };

function commentsLabel(data: OpinionSummary): string {
  const shown = data.positive.results.length + data.negative.results.length;
  const more = Boolean(data.positive.next_page || data.negative.next_page);
  return `${shown}${more ? "+" : ""}`;
}

function MaterialReactionsInner({ article }: { article: Pick<Article, "id"> }) {
  const summary = useQuery({
    queryKey: ["article-opinions-summary", article.id],
    queryFn: () => apiFetch<OpinionSummary>(`/api/articles/${article.id}/opinions/`),
    staleTime: 15_000,
  });
  const data = summary.data;
  return (
    <section className="sc-material-reactions" aria-label="Reakcje i komentarze">
      <div className="sc-material-reactions__bar" role="group" aria-label="Podsumowanie reakcji">
        <span className="sc-material-reactions__stat is-positive">
          <span aria-hidden="true">▲</span> Przydatne <strong>{data ? data.counts.positive : "–"}</strong>
        </span>
        <span className="sc-material-reactions__stat is-negative">
          <span aria-hidden="true">▼</span> Nieprzydatne <strong>{data ? data.counts.negative : "–"}</strong>
        </span>
        <span className="sc-material-reactions__stat">
          Komentarze <strong>{data ? commentsLabel(data) : "–"}</strong>
        </span>
        {/* Przycisk, nie kotwica: adres `#…` wszedłby w historię portalu (tryb `path`). */}
        <button
          type="button"
          className="sc-home-linkbtn sc-material-reactions__jump"
          onClick={() => document.getElementById(`opinie-${article.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" })}
        >
          Dodaj reakcję lub komentarz
        </button>
      </div>
      <div id={`opinie-${article.id}`} className="sc-material-reactions__body" tabIndex={0} aria-label="Komentarze — przewijaj w obrębie sekcji">
        <ArticleOpinions article={article} />
      </div>
    </section>
  );
}

/** Wyłączone razem z kontami czytelników (NEXT_PUBLIC_ACCOUNTS_ENABLED). */
export function MaterialReactions(props: Parameters<typeof MaterialReactionsInner>[0]) {
  return ACCOUNTS_ENABLED ? <MaterialReactionsInner {...props} /> : null;
}
