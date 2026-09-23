"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "../../Button";
import { Dropdown } from "../../Dropdown";
import { NewsCard } from "../../NewsCard";
import { SearchField } from "../../SearchField";
import { BottomSheet } from "../../mobile/BottomSheet";
import { Carousel } from "../../mobile/Carousel";
import { CompactHeader } from "../../mobile/CompactHeader";
import { FoldedSection } from "../../mobile/FoldedSection";
import { useFocalBand } from "../../mobile/useFocalBand";
import { FIXTURE_ARTICLES, FIXTURE_SOURCES, FIXTURE_STRIPS } from "../fixtures";

export const meta = {
  id: "mobile",
  title: "Telefon",
  lead: "Fokus zamiast najechania, sekcje złożone do rozwinięcia, karuzela z przyciąganiem, dolny arkusz, nagłówek uszczelniany kierunkiem przewijania.",
};

const FOLDS = [
  { id: "najnowsze", title: "Najnowsze materiały", articles: FIXTURE_ARTICLES.slice(0, 6) },
  { id: "top10", title: "TOP 10", articles: FIXTURE_ARTICLES.slice(6, 12) },
  { id: "temat-dnia", title: "Temat dnia", articles: FIXTURE_ARTICLES.slice(12, 18) },
];

const SOURCE_ITEMS = FIXTURE_SOURCES.map((source) => ({ value: String(source.id), label: source.name }));

/** Tylko do odczytu na stoisku: prędkość przewijania ramki telefonu w px/ms. */
function useScrollVelocityReadout(ref: React.RefObject<HTMLElement | null>): number {
  const [velocity, setVelocity] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let lastTop = el.scrollTop;
    let lastTime = performance.now();
    function onScroll() {
      const now = performance.now();
      const top = el!.scrollTop;
      const dt = now - lastTime;
      if (dt > 0) setVelocity(Math.abs(top - lastTop) / dt);
      lastTop = top;
      lastTime = now;
    }
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [ref]);
  return velocity;
}

export function Section() {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [showBand, setShowBand] = useState(true);
  const [query, setQuery] = useState("");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sources, setSources] = useState<string[]>([]);
  const [previewed, setPreviewed] = useState<string | null>(null);
  const [opened, setOpened] = useState<string | null>(null);

  const focalId = useFocalBand(frameRef, { force: true });
  const velocity = useScrollVelocityReadout(frameRef);

  return (
    <div>
      <p className="sc-t-body-s sc-text-2" style={{ maxWidth: "var(--sc-measure)" }}>
        Ramka 375×740 z własnym przewijaniem (<code>container-type: inline-size</code>).{" "}
        <code>useFocalBand(..., {"{ force: true }"})</code> włącza pasmo fokalne mimo myszy — na
        prawdziwym telefonie robi to samo, bo tam nie ma <code>(hover: hover) and (pointer: fine)</code>.
      </p>

      <div className="sc-mobile-readouts">
        <label className="sc-showcase__check">
          <input type="checkbox" checked={showBand} onChange={(e) => setShowBand(e.target.checked)} />
          Pokaż granice pasma (35% / 65%)
        </label>
        <p className="sc-t-meta sc-text-2">
          Fokalna karta: <span className="sc-t-mono">{focalId ?? "—"}</span>
        </p>
        <p className="sc-t-meta sc-text-2">
          Prędkość przewijania: <span className="sc-t-mono">{velocity.toFixed(2)} px/ms</span>
        </p>
        <p className="sc-t-meta sc-text-2">
          Stopień B (onPreview): <span className="sc-t-mono">{previewed ?? "—"}</span> · Stopień C (onOpen):{" "}
          <span className="sc-t-mono">{opened ?? "—"}</span>
        </p>
      </div>

      <div className="sc-mobile-stand">
        <div ref={frameRef} className="sc-mobile-frame">
          {showBand && (
            <>
              <div className="sc-mobile-frame__band-line" style={{ top: "35%" }} aria-hidden="true" />
              <div className="sc-mobile-frame__band-line" style={{ top: "65%" }} aria-hidden="true" />
            </>
          )}

          <CompactHeader scrollRootRef={frameRef}>
            {({ compact }) => (
              <div className="sc-mobile-frame__header-row">
                <strong className="sc-t-title-s">spin.clinic</strong>
                {compact ? (
                  <span className="sc-mobile-frame__search-icon" aria-hidden="true">
                    🔍
                  </span>
                ) : (
                  <SearchField value={query} onChange={setQuery} placeholder="Szukaj materiałów…" />
                )}
              </div>
            )}
          </CompactHeader>

          <div className="sc-mobile-frame__scroll">
            {FOLDS.map((fold) => (
              <FoldedSection
                key={fold.id}
                scrollRootRef={frameRef}
                title={<span className="sc-t-title-s">{fold.title}</span>}
                preview={<NewsCard article={fold.articles[0]} size="compact" />}
              >
                <div className="sc-mobile-frame__list">
                  {fold.articles.slice(1).map((article) => (
                    <NewsCard key={article.id} article={article} size="compact" />
                  ))}
                </div>
              </FoldedSection>
            ))}

            <section className="sc-folded">
              <div className="sc-folded__header sc-chrome">
                <span className="sc-t-title-s">Karuzela — karty medium</span>
              </div>
              <div className="sc-mobile-frame__carousel-wrap">
                <Carousel
                  articles={FIXTURE_STRIPS[0].articles}
                  size="medium"
                  ariaLabel="Najnowsze materiały — karuzela"
                  onPreview={(article) => setPreviewed(article.title)}
                  onOpen={(article) => setOpened(article.title)}
                />
              </div>
            </section>

            <div className="sc-mobile-frame__list" style={{ padding: "0 var(--sc-s-4) var(--sc-s-6)" }}>
              <Button onClick={() => setSheetOpen(true)} fullWidth>
                Filtry (dolny arkusz)
              </Button>
              <Dropdown
                label="Źródła"
                mode="multi"
                items={SOURCE_ITEMS}
                value={sources}
                onChange={(v) => setSources(Array.isArray(v) ? v : [v])}
                presentation="sheet"
                footer={<span className="sc-t-caption sc-text-3">Wybrano: {sources.length}</span>}
              />
            </div>
          </div>
        </div>
      </div>

      <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Filtry">
        <div className="sc-mobile-frame__list" style={{ padding: "0 0 var(--sc-s-4)" }}>
          <p className="sc-t-body-s sc-text-2">
            Ten sam <code>BottomSheet</code>, którego <code>Dropdown presentation=&quot;sheet&quot;</code> używa
            wewnętrznie. Przeciągnij uchwyt w dół, żeby zamknąć — decyduje znak prędkości, nie pozycja.
          </p>
          <NewsCard article={FIXTURE_ARTICLES[0]} size="mini" />
          <NewsCard article={FIXTURE_ARTICLES[1]} size="mini" />
        </div>
      </BottomSheet>

      <h3 className="sc-t-title-m sc-section__sub">Karuzela pełnej szerokości (poza ramką)</h3>
      <Carousel articles={FIXTURE_STRIPS[1].articles} size="medium" ariaLabel="Polska — karuzela pełnej szerokości" />
    </div>
  );
}
