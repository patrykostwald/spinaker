"use client";

/**
 * Dr Spin — poziomy pas w jednym komponencie: nagłówek, po lewej główny box (materiał otwierający
 * nitki, `large`), po prawej taśma kolejnych mniejszych boxów (`compact`), razem do pięciu materiałów.
 * Bez opublikowanej nitki — ten sam pas jako zapowiedź z dotychczasowymi napisami (żadnych zmyślonych treści).
 * Pełna nitka (oba układy `ThreadView`) zostaje na stronie `/thread/<slug>`.
 * Na dole pasa — zapowiedź własnych nitek kontekstowych (faza 2); dziś tworzy je wyłącznie Dr Spin.
 */

import { Button } from "../Button";
import { NewsCard } from "../NewsCard";
import type { ThreadDetail } from "../../types";
import { EmptySlot, Strip } from "./Strip";

const PREVIEW_TYPES = ["Wywiad", "Dokument urzędowy", "Reportaż", "Komunikat"];
const MAX_ITEMS = 5;

export function HomeDrSpin({ thread }: { thread: ThreadDetail | null }) {
  const published = thread?.published ? thread : null;
  const items = published ? [...published.items].sort((a, b) => a.position - b.position).slice(0, MAX_ITEMS) : [];
  const [anchor, ...rest] = items;

  return (
    <section className="sc-home-section sc-home-drspin" aria-label="Dr Spin">
      <div className="sc-home-band-surface">
        <header className="sc-home-section__head">
          <div>
            <p className="sc-t-caption sc-text-3 sc-home-kicker">spin.clinic · Redakcja</p>
            <h2 className="sc-t-title-l sc-home-section__title">Dr Spin</h2>
          </div>
          <div className="sc-home-section__actions">
            <p className="sc-t-body-s sc-text-2">{published ? published.title : "Codzienna nitka redakcyjna"}</p>
            {published ? (
              <Button href={`/thread/${published.slug}`} variant="quiet" size="sm">
                Otwórz nitkę
              </Button>
            ) : null}
          </div>
        </header>

        <div className="sc-home-drspin__band">
          <div className="sc-home-drspin__anchor">
            {anchor ? (
              <>
                <NewsCard article={anchor.article} size="large" headingLevel={3} eyebrow="Materiał otwierający" />
                {anchor.editorial_note ? (
                  <p className="sc-t-body-s sc-text-2 sc-home-drspin__note">
                    <strong>Komentarz autora: </strong>
                    {anchor.editorial_note}
                  </p>
                ) : null}
              </>
            ) : (
              <div className="sc-home-anchor-placeholder" role="img" aria-label="Główny materiał Dr Spina — miejsce na post lub materiał otwierający">
                <div className="sc-skeleton sc-home-anchor-placeholder__media" />
                <span className="sc-t-caption sc-text-3">Główny materiał</span>
                <strong className="sc-t-title-m">Post lub materiał otwierający</strong>
                <span className="sc-t-body-s sc-text-2">Tu Dr Spin krótko wyjaśni, co sprawdzamy i dlaczego.</span>
              </div>
            )}
          </div>

          <div className="sc-home-drspin__strip">
            <p className="sc-t-caption sc-text-3 sc-home-drspin__strip-head">Kolejne materiały</p>
            <Strip label="Kolejne materiały Dr Spina" slot="220px">
              {anchor
                ? rest.map((item) => (
                    <div key={item.id} className="sc-strip__slot">
                      <NewsCard article={item.article} size="compact" headingLevel={4} />
                    </div>
                  ))
                : PREVIEW_TYPES.map((type, index) => (
                    <div key={type} className="sc-strip__slot">
                      <EmptySlot index={index + 2} label={type} />
                    </div>
                  ))}
            </Strip>
          </div>
        </div>

        {/* Zapowiedź fazy 2: własne nitki kontekstowe użytkowników. */}
        <aside className="sc-home-drspin__teaser" aria-label="Własne nitki kontekstowe — wkrótce">
          <div>
            <p className="sc-t-title-s">Wkrótce: Twoje własne nitki kontekstowe</p>
            <p className="sc-t-body-s sc-text-2">
              Dziś nitki kontekstowe układa Dr Spin. W kolejnej fazie zbierzesz boxy w jedną historię — z datami, źródłami i komentarzem — i pokażesz ją innym.
            </p>
          </div>
          <Button variant="secondary" size="sm" disabled>
            Utwórz nitkę · wkrótce
          </Button>
        </aside>
      </div>
    </section>
  );
}
