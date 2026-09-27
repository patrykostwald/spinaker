"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { PublicFigureSummary } from "../lib/publicFigures";

const normalize = (value: string) => value.toLocaleLowerCase("pl").replace(/\s+/g, " ").trim();

/**
 * Hasło to imię i nazwisko z rejestru osób publicznych? Na górze wyników — karta profilu (doniesienia, kariera, podmioty).
 * Pokazujemy tylko pełne dopasowanie imienia i nazwiska, żeby nie podsuwać cudzego profilu.
 */
export function FigureMatch({ query }: { query: string }) {
  const q = query.trim();
  const result = useQuery({
    queryKey: ["figure-match", q],
    queryFn: () => apiFetch<{ results: PublicFigureSummary[] }>(`/api/public-figures/?q=${encodeURIComponent(q)}&page_size=5`),
    enabled: q.split(/\s+/).length >= 2 && q.length <= 80,
    staleTime: 60_000,
  });
  const figure = result.data?.results.find(item => normalize(item.name) === normalize(q));
  if (!figure) return null;
  return (
    <Link href={`/osoby-publiczne/${figure.id}`} className="sc-figure-match">
      <span className="sc-figure-match__kicker">Profil osoby publicznej</span>
      <strong>{figure.name}</strong>
      <span>{figure.role_title}{figure.organisation ? ` · ${figure.organisation}` : ""}</span>
      <span className="sc-figure-match__cta">Zobacz profil: doniesienia, kariera, podmioty, głosowania →</span>
    </Link>
  );
}
