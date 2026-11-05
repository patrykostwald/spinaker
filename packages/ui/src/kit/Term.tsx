import type { ReactNode } from "react";
import Link from "next/link";
import { glossaryEntry } from "../lib/glossary";

/** Pojęcie z definicją: podpowiedź po najechaniu i link do słowniczka. Używaj przy pierwszym wystąpieniu w danym bloku (nie w linku ani przycisku). */
export function Term({ id, children }: { id: string; children: ReactNode }) {
  const entry = glossaryEntry(id);
  if (!entry) return <>{children}</>;
  return <Link className="sc-term" href={`/metodologia#pojecie-${entry.id}`} title={`${entry.term}: ${entry.definition}`}>{children}</Link>;
}
