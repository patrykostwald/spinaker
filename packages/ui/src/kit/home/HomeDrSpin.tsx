"use client";

/**
 * Dr Spin (wzór: „Popular Videos”). Opublikowana nitka renderuje się przez `ThreadView` — te same
 * dwa układy co na stronie nitki (dwie kolumny / jeden rząd), ograniczone do pięciu materiałów.
 * Bez opublikowanej nitki — układ-zapowiedź z dotychczasowymi napisami (żadnych zmyślonych treści).
 */

import { Button } from "../Button";
import { ThreadView } from "../ThreadView";
import type { ThreadDetail } from "../../types";
import { EmptySlot } from "./Strip";

const PREVIEW_TYPES = ["Wywiad", "Dokument urzędowy", "Reportaż"];

export function HomeDrSpin({ thread }: { thread: ThreadDetail | null }) {
  const published = thread?.published ? thread : null;

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
              Otwórz nitkę
            </Button>
          ) : null}
        </div>
      </header>

      {published ? (
        <ThreadView items={published.items} anchorFirst={Boolean(published.editorial_slot)} maxItems={5} storageKey="spinclinic-home-thread-layout" />
      ) : (
        <div className="sc-home-drspin__grid">
          <div className="sc-home-drspin__anchor">
            <div className="sc-home-anchor-placeholder" role="img" aria-label="Główny materiał Dr Spina — miejsce na post lub materiał otwierający">
              <div className="sc-skeleton sc-home-anchor-placeholder__media" />
              <span className="sc-t-caption sc-text-3">Główny materiał</span>
              <strong className="sc-t-title-m">Post lub materiał otwierający</strong>
              <span className="sc-t-body-s sc-text-2">Tu Dr Spin krótko wyjaśni, co sprawdzamy i dlaczego.</span>
            </div>
          </div>
          <div className="sc-home-drspin__column">
            {PREVIEW_TYPES.map((type, index) => (
              <EmptySlot key={type} index={index + 2} label={type} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
