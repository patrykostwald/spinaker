"use client";

import { OpinionsPanel } from "./OpinionsPanel";

export function ThreadOpinions({ slug }: { slug: string }) {
  return <OpinionsPanel endpoint={`/api/threads/${slug}/opinions/`} reportKind="thread" labels={{
    kicker: "REAKCJE CZYTELNIKÓW",
    question: "Czy ten trop był przydatny?",
    positive: "Przydatna",
    negative: "Nieprzydatna",
    signedOut: "Zaloguj się, aby zaznaczyć, czy trop był przydatny, i dodać komentarz.",
  }} />;
}
