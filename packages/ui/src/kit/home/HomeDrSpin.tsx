"use client";

/**
 * Dr Spin (wzór: „Popular Videos” — jeden duży + kolumna trzech). Po lewej materiał otwierający
 * nitkę (`large`), po prawej trzy materiały wyjaśniające (`compact`, poziomo: media z lewej).
 * Bez opublikowanej nitki — układ-zapowiedź z dotychczasowymi napisami (żadnych zmyślonych treści).
 */

import { useRouter } from "next/navigation";
import { Button } from "../Button";
import { NewsCard } from "../NewsCard";
import type { ThreadDetail } from "../../types";
import { EmptySlot } from "./Strip";

const PREVIEW_TYPES = ["Wywiad", "Dokument urzędowy", "Reportaż"];

export function HomeDrSpin({ thread }: { thread: ThreadDetail | null }) {
  const router = useRouter();
  const published = thread?.published ? thread : null;
  const anchor = published?.items[0]?.article;
  const rest = published ? published.items.slice(1, 4) : [];

  return (
    <section className="sc-home-section sc-home-drspin" aria-label="Dr Spin">
      <header className="sc-home-section__head">
        <div>
          <p className="sc-t-caption sc-text-3 sc-home-kicker">spin.clinic · Redakcja</p>
          <h2 className="sc-t-title-l sc-home-section__title">Dr Spin</h2>
        </div>
        <div className="sc-home-section__actions">
          <p className="sc-t-body-s sc-text-2">{published ? "Dzisiejsza nitka redakcyjna" : "Codzienna nitka redakcyjna"}</p>
          {published ? (
            <Button href={`/thread/${published.slug}`} variant="quiet" size="sm">
              Zobacz wszystko
            </Button>
          ) : null}
        </div>
      </header>

      <div className="sc-home-drspin__grid">
        <div className="sc-home-drspin__anchor">
          {published && anchor ? (
            <NewsCard article={anchor} size="large" headingLevel={3} eyebrow="Główny materiał" onOpen={() => router.push(`/thread/${published.slug}`)} />
          ) : (
            <div className="sc-home-anchor-placeholder" role="img" aria-label="Główny materiał Dr Spina — miejsce na post lub materiał otwierający">
              <div className="sc-skeleton sc-home-anchor-placeholder__media" />
              <span className="sc-t-caption sc-text-3">Główny materiał</span>
              <strong className="sc-t-title-m">Post lub materiał otwierający</strong>
              <span className="sc-t-body-s sc-text-2">Tu Dr Spin krótko wyjaśni, co sprawdzamy i dlaczego.</span>
            </div>
          )}
        </div>
        <div className="sc-home-drspin__column">
          {rest.length
            ? rest.map((item) => <NewsCard key={item.id} article={item.article} size="mini" headingLevel={3} />)
            : PREVIEW_TYPES.map((type, index) => <EmptySlot key={type} index={index + 2} label={type} />)}
        </div>
      </div>
    </section>
  );
}
