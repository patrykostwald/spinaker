"use client";

/**
 * Przekaz dnia (stary `PrzekazDnia`): dwie kolumny „Rządzący” / „Opozycja” — każda to karta
 * `compact` z materiałem otwierającym nitkę (klik → strona nitki). Brak obu nitek → sekcji nie ma.
 */

import { useRouter } from "next/navigation";
import { NewsCard } from "../NewsCard";
import type { ThreadDetail } from "../../types";

function Column({ title, thread }: { title: string; thread: ThreadDetail | null }) {
  const router = useRouter();
  const published = thread?.published ? thread : null;
  const anchor = published?.items[0]?.article;
  return (
    <div className="sc-home-przekaz__column">
      <p className="sc-t-caption sc-text-3">{title}</p>
      {published && anchor ? (
        <NewsCard article={anchor} size="compact" headingLevel={3} eyebrow={published.title} onOpen={() => router.push(`/thread/${published.slug}`)} />
      ) : (
        <p className="sc-t-body-s sc-text-2 sc-home-przekaz__empty">W przygotowaniu</p>
      )}
    </div>
  );
}

export function HomePrzekazDnia({ government, opposition }: { government: ThreadDetail | null; opposition: ThreadDetail | null }) {
  if (!government?.published && !opposition?.published) return null;
  return (
    <section className="sc-home-section sc-home-przekaz" aria-label="Przekaz dnia">
      <header className="sc-home-section__head">
        <h2 className="sc-t-title-l">Przekaz dnia</h2>
      </header>
      <div className="sc-home-przekaz__grid">
        <Column title="Rządzący" thread={government} />
        <Column title="Opozycja" thread={opposition} />
      </div>
    </section>
  );
}
