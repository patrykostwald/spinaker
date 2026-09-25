"use client";

import type { ThreadDetail } from "../types";
import { NewsCard } from "../kit";
import { ThreadFavoriteButton } from "./ThreadFavoriteButton";

/** Tylko opublikowana nitka redakcyjna pojawia się w sekcji Dr. Spin. */
export function DrSpin({ thread }: { thread: ThreadDetail | null }) {
  const published = thread?.published ? thread : null;
  const anchorArticle = published?.items[0]?.article;
  if (!published || !anchorArticle) return null;

  return (
    <section className="sc-dr-spin" aria-label="Dr. Spin">
      <header className="sc-dr-spin__head">
        <div>
          <p>SPIN.CLINIC · REDAKCJA</p>
          <h2>Dr. Spin</h2>
        </div>
        <div><p>Dzisiejsza nitka redakcyjna</p><ThreadFavoriteButton thread={published} /></div>
      </header>
      <div className="sc-dr-spin__layout">
        <NewsCard article={anchorArticle} href={`/thread/${published.slug}`} size="large" headingLevel={3} showDescription action={<span className="sc-dr-spin__thread-label">Nitka redakcyjna</span>} />
        {published.items.length > 1 ? <div className="sc-dr-spin__related sc-strip-bleed" aria-label="Dr. Spin — materiały wyjaśniające">
          {published.items.slice(1, 6).map(item => <NewsCard key={item.id} article={item.article} size="compact" headingLevel={3} />)}
        </div> : null}
      </div>
    </section>
  );
}
