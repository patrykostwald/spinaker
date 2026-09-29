"use client";

/**
 * Dr. Spin — poziomy pas w jednym komponencie: nagłówek, po lewej główny box (materiał otwierający
 * nitki, `large`), po prawej taśma kolejnych mniejszych boxów (`compact`), razem do pięciu materiałów.
 * Bez opublikowanej nitki — ten sam pas jako zapowiedź z dotychczasowymi napisami (żadnych zmyślonych treści).
 * Pełna nitka (oba układy `ThreadView`) zostaje na stronie `/thread/<slug>`.
 * Na dole pasa — zapowiedź własnych nitek kontekstowych (faza 2); dziś tworzy je wyłącznie Dr. Spin.
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
  const byDrSpin = !published?.author_name || published.author_name === "Dr. Spin";

  // Bez opublikowanej nitki nie pokazujemy makiety — tylko pasek dla dziennikarzy i jedno zdanie (29.09).
  if (!published) {
    return (
      <section className="sc-home-section sc-home-drspin" aria-label="Nitki kontekstowe">
        <aside className="sc-home-drspin__invite sc-home-drspin__invite--solo" aria-label="Dla dziennikarzy i redakcji">
          <p>
            <strong>Nitki kontekstowe:</strong> gdy Dr. Spin znajdzie w Bazie trafny kontekst do spinu dnia, pokaże tu nitkę — materiał i źródła wokół niego.
            <span> Dziennikarze i redakcje mogą prowadzić własne, autoryzowane nitki.</span>
          </p>
          <Button href="/o-nas#dla-redakcji" variant="primary" size="sm">Dołącz do pilotażu →</Button>
        </aside>
      </section>
    );
  }

  return (
    <section className="sc-home-section sc-home-drspin" aria-label="Dr. Spin">
      <div className="sc-home-band-surface">
        <header className="sc-home-section__head">
          <div>
            {/* Tytuł według autora: nitka Dr. Spina (AI) albo wyróżniona nitka dziennikarza — nigdy nie mylimy autorstwa. */}
            {byDrSpin ? (
              <>
                <p className="sc-t-caption sc-text-3 sc-home-kicker">Nitka kontekstowa · przygotowana automatycznie przez AI</p>
                <h2 className="sc-t-title-l sc-home-section__title">Nitka Dr. Spina</h2>
              </>
            ) : (
              <>
                <p className="sc-t-caption sc-text-3 sc-home-kicker">Nitka kontekstowa · autor: {published?.author_name}</p>
                <h2 className="sc-t-title-l sc-home-section__title">Nitka kontekstowa</h2>
              </>
            )}
          </div>
          <div className="sc-home-section__actions">
            <p className="sc-t-body-s sc-text-2">{published ? published.title : "Codzienna nitka kontekstowa"}</p>
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
                <NewsCard article={anchor.article} size="medium" headingLevel={3} eyebrow="Materiał otwierający" />
                {anchor.editorial_note ? (
                  <p className="sc-t-body-s sc-text-2 sc-home-drspin__note">
                    <strong>Dr. Spin: </strong>
                    {anchor.editorial_note}
                  </p>
                ) : null}
              </>
            ) : (
              <div className="sc-home-anchor-placeholder" role="img" aria-label="Główny materiał Dr. Spina — miejsce na wpis lub materiał otwierający">
                <div className="sc-skeleton sc-home-anchor-placeholder__media" />
                <span className="sc-t-caption sc-text-3">Główny materiał</span>
                <strong className="sc-t-title-m">Wpis lub materiał otwierający</strong>
                <span className="sc-t-body-s sc-text-2">Tu Dr. Spin krótko wyjaśni, co sprawdzamy i dlaczego.</span>
              </div>
            )}
          </div>

          <div className="sc-home-drspin__strip">
            <p className="sc-t-caption sc-text-3 sc-home-drspin__strip-head">Kolejne materiały</p>
            <Strip label="Kolejne materiały Dr. Spina" slot="220px">
              {anchor
                ? rest.map((item) => (
                    <div key={item.id} className="sc-strip__slot">
                      <NewsCard article={item.article} size="compact" headingLevel={4} expandable={false} />
                      {item.editorial_note ? <p className="sc-home-drspin__why">{item.editorial_note}</p> : null}
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

        <p className="sc-home-drspin__disclaimer">Obecność materiału w nitce nie potwierdza niczyich twierdzeń — każdy box prowadzi do oryginału.</p>
        {/* Zamiast dużego zaproszenia: jeden pasek dla dziennikarzy i zapowiedź własnych nitek (28.09). */}
        <aside className="sc-home-drspin__invite" aria-label="Dla dziennikarzy i redakcji">
          <p>
            <strong>Dla dziennikarzy i redakcji:</strong> poprowadź autoryzowaną nitkę — Twój materiał i jego kontekst, pod Twoim nazwiskiem.
            <span> Wkrótce własne nitki ułożą też czytelnicy.</span>
          </p>
          <Button href="/o-nas#dla-redakcji" variant="primary" size="sm">Dołącz do pilotażu →</Button>
        </aside>
      </div>
    </section>
  );
}
