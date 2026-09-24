"use client";

/**
 * Portal — demonstracja R5 (docs/UI_KIT_PLAN.md → «Портал», brief roli R5).
 * R0 (24.09): PortalProvider i PortalLayer są WSPÓLNE dla całej witryny (UiKitShowcase.tsx) —
 * ta sekcja tylko pokazuje trzy przypadki powrotu i taśmę z przycięciem.
 */

import { useEffect, useState } from "react";
import { NewsCard } from "../../NewsCard";
import { usePortal } from "../../portal";
import { FIXTURE_STRIPS, makeArticles } from "../fixtures";

export const meta = {
  id: "portal",
  title: "Portal",
  lead:
    "Karta → stopień B (ta sama karta zmienia formę nad siatką) → pełny ekran. Trzy przypadki powrotu i taśma z overflow.",
};

const GRID_ARTICLES = makeArticles(8, 41);
const STRIP = FIXTURE_STRIPS[0];

function Readout() {
  const { active, previewing } = usePortal();
  // R0: zawsze startujemy od "" — inicjalizacja z window.location.search dawała inny tekst na
  // serwerze ("") i w przeglądarce ("?…"), czyli błąd hydratacji. Odczyt synchronizujemy w efekcie.
  const [search, setSearch] = useState("");

  // Prosty odczyt na żywo: `history.pushState`/`replaceState` nie wysyła żadnego zdarzenia,
  // więc na potrzeby wystawki sondujemy — produkcyjny kod czytałby to z `active`/`previewing`.
  useEffect(() => {
    const sync = () => setSearch(window.location.search);
    sync();
    const id = window.setInterval(sync, 250);
    window.addEventListener("popstate", sync);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("popstate", sync);
    };
  }, []);

  return (
    <p className="sc-t-meta sc-text-2" style={{ margin: "0 0 var(--sc-s-4)" }} aria-live="polite">
      active: <code>{active ? active.id : "—"}</code> · previewing: <code>{previewing ? previewing.id : "—"}</code> · location.search:{" "}
      <code>{search || "(puste)"}</code>
    </p>
  );
}

export function Section() {
  return <Sandbox />;
}

function Sandbox() {
  const [removedId, setRemovedId] = useState<number | null>(null);
  const [scrollAway, setScrollAway] = useState(false);
  const gridArticles = GRID_ARTICLES.filter((a) => a.id !== removedId);

  return (
    <div>
      <Readout />

      <div className="sc-showcase__seg" role="group" aria-label="Testy zwrotu" style={{ marginBottom: "var(--sc-s-4)" }}>
        <button type="button" onClick={() => setRemovedId(gridArticles[0]?.id ?? null)}>
          Odmontuj kartę źródłową
        </button>
        <button
          type="button"
          onClick={() => {
            setScrollAway(true);
            window.scrollTo({ top: document.body.scrollHeight, behavior: "auto" });
          }}
        >
          Przewiń kartę poza ekran
        </button>
        <button
          type="button"
          onClick={() => {
            setRemovedId(null);
            setScrollAway(false);
          }}
        >
          Reset
        </button>
      </div>
      {scrollAway ? (
        <p className="sc-t-caption sc-text-3" style={{ margin: "0 0 var(--sc-s-3)" }}>
          Strona przewinięta — otwórz kartę, potem zamknij: powrót powinien najpierw doskoczyć do karty, dopiero potem zmorfować.
        </p>
      ) : null}

      <h3 className="sc-t-title-m sc-section__sub">Siatka — 8 kart medium</h3>
      <div style={{ display: "grid", gap: "var(--sc-s-4)", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))" }}>
        {gridArticles.map((article) => (
          <NewsCard key={article.id} article={article} size="medium" expandable />
        ))}
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Taśma (overflow-x: auto) — 8 kart compact</h3>
      <div className="sc-portal-strip sc-strip-bleed" style={{ display: "flex", gap: "var(--sc-s-4)", overflowX: "auto" }}>
        {STRIP.articles.map((article) => (
          <div key={article.id} style={{ flex: "0 0 240px" }}>
            <NewsCard article={article} size="compact" expandable />
          </div>
        ))}
      </div>

      <p className="sc-t-body-s sc-text-2" style={{ marginTop: "var(--sc-s-5)", maxWidth: "var(--sc-measure)" }}>
        Trzy przypadki powrotu przy zamknięciu: (1) karta na ekranie — zwykły morfing; (2) karta zamontowana, ale poza widokiem
        („Przewiń kartę poza ekran”) — natychmiastowy <code>scrollIntoView</code> w tym samym takcie, potem morfing; (3) karta
        zdemontowana („Odmontuj kartę źródłową” — otwórz ją NAJPIERW, potem odmontuj) — zamknięcie kurczy się do środka
        zapamiętanego prostokąta.
      </p>
    </div>
  );
}
