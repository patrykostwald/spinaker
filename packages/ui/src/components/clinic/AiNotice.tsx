"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { formatDatePl } from "../../lib/utils";

/**
 * Stały, widoczny pasek oznaczenia AI (art. 50 ust. 4 AI Act): kto analizuje, jaka wersja instrukcji i że to nie jest
 * rozstrzygnięcie redakcji. Używany na diagnozie, przekazie dnia i analizie wywiadu.
 */
export const PUBLICATION_MODEL = "Wpisy z wynikiem Strażnika powyżej 75 trafiają do analizy automatycznie, a gotowa diagnoza ukazuje się bez przeglądu człowieka; człowiek może ją tylko wycofać. Wpisy z pasma 40–75 czekają na decyzję operatora, czy je zbadać, a analiza przejrzana przez operatora ma odznakę „zatwierdzona ręcznie”.";
export const INTERVIEW_PUBLICATION_MODEL = "Człowiek wybiera tylko nagranie wywiadu. Analiza ukazuje się automatycznie, nikt nie poprawia jej treści, a ukryć ją można wyłącznie po zgłoszeniu prawnym.";

/** Odznaka sposobu publikacji: „opublikowana automatycznie” albo „zatwierdzona ręcznie” (z pola `auto_published` z API). */
export function PublicationBadge({ mode, at }: { mode: "auto" | "manual"; at?: string | null }) {
  return <span className="sc-pub-badge" data-mode={mode}>{mode === "auto" ? "Opublikowana automatycznie" : "Zatwierdzona ręcznie"}{at ? <> · <time dateTime={at}>{formatDatePl(at)}</time></> : null}</span>;
}

export function AiNotice({ models, version, note, detailsHref, publication, explain }: {
  models?: string; version?: string; note?: ReactNode; detailsHref?: string;
  publication?: { mode: "auto" | "manual"; at?: string | null } | null; explain?: string;
}) {
  return <aside className="sc-ai-notice" aria-label="Oznaczenie analizy AI">
    <span className="sc-ai-notice__head"><strong>Analiza AI</strong>{publication ? <PublicationBadge mode={publication.mode} at={publication.at} /> : null}</span>
    {models ? <span>Modele: {models}{detailsHref ? <> (<a href={detailsHref}>pełne nazwy i wersje</a>)</> : null}</span> : null}
    {version ? <span>wersja instrukcji {version}</span> : null}
    <span>{note ?? "To nie jest rozstrzygnięcie redakcji; modele mogą się mylić."} <Link href="/metodologia">Jak analizujemy</Link></span>
    {explain ? <span className="sc-ai-notice__explain">{explain}</span> : null}
  </aside>;
}

/** Stopka redakcyjna: wydawca, miejsce odpowiedzialności redakcyjnej, kontakt do sprostowań i niezależność od wsparcia. */
export function EditorialNote() {
  return <p className="sc-editorial-note">
    Wydawca: iapply sp. z o.o., Poznań · odpowiada: Redakcja spin.clinic · sprostowania i zgłoszenia: formularz na tej stronie lub{" "}
    <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a> · wsparcie czytelników nie wpływa na wybór wpisów ani na wyniki analiz.{" "}
    <Link href="/o-nas#redakcja">Więcej o redakcji</Link>
  </p>;
}
