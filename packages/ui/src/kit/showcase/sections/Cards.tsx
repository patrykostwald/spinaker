"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { NewsCard } from "../../NewsCard";
import { useMotionTokens } from "../../motion/useMotionTokens";
import { CARD_SIZES } from "../../tokens";
import { FIXTURE_STATES, makeArticle, makeArticles } from "../fixtures";

export const meta = {
  id: "karty",
  title: "Karty",
  lead: "NewsCard — jeden komponent, cztery rozmiary, sześć stanów danych. Najechanie: stopień A, po 400 ms jeden wspólny przedpodgląd w warstwie nad stroną; klik — pełny ekran morfingiem.",
};

const BADGE_CATEGORIES = ["article", "document", "video", "voting"] as const;
const EDGE_ARTICLES = makeArticles(12, 21);

export function Section() {
  return (
    <div>
      <h3 className="sc-t-title-m sc-section__sub">Rozmiary × stany danych</h3>
      <div style={{ display: "grid", gap: "var(--sc-s-6)" }}>
        {CARD_SIZES.map((size) => (
          <div key={size}>
            <p className="sc-t-caption sc-text-3" style={{ margin: "0 0 var(--sc-s-3)" }}>{size}</p>
            <div
              style={{
                display: "grid",
                gap: "var(--sc-s-4)",
                gridTemplateColumns: size === "mini" ? "repeat(auto-fill, minmax(280px, 1fr))" : "repeat(auto-fill, minmax(240px, 1fr))",
              }}
            >
              {FIXTURE_STATES.map(({ key, article }) => (
                <NewsCard key={key} article={article} size={size} />
              ))}
            </div>
          </div>
        ))}
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Odznaka kategorii (na medium, nad zdjęciem)</h3>
      <div style={{ display: "grid", gap: "var(--sc-s-4)", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))" }}>
        {BADGE_CATEGORIES.map((category, index) => (
          // R0: явный id — иначе id брался из счётчика модуля и расходился между сервером и клиентом (гидратация).
          <NewsCard key={category} article={makeArticle({ id: -(300 + index), category })} size="medium" />
        ))}
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Karta large — stack i split (split od 900px wzwyż)</h3>
      <div style={{ display: "grid", gap: "var(--sc-s-5)" }}>
        <NewsCard article={FIXTURE_STATES[0].article} size="large" layout="stack" />
        <NewsCard article={FIXTURE_STATES[5].article} size="large" layout="split" />
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Eyebrow i akcja poza linkiem</h3>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-3)" }}>
        Klik w kartę otwiera portal (wspólny dla całej witryny); przycisk akcji leży poza linkiem i nie otwiera nic.
      </p>
      <div style={{ display: "grid", gap: "var(--sc-s-4)", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))" }}>
        <NewsCard
          article={FIXTURE_STATES[0].article}
          size="medium"
          eyebrow="DEMO"
          expandable
          action={
            <button
              type="button"
              aria-label="Dodaj do ulubionych"
              onClick={(e) => e.preventDefault()}
              style={{
                width: 32,
                height: 32,
                borderRadius: "var(--sc-r-pill)",
                border: "1px solid var(--sc-line)",
                background: "var(--sc-surface)",
                color: "var(--sc-text)",
                cursor: "pointer",
              }}
            >
              ♥
            </button>
          }
        />
      </div>

      <BounceRig />

      <h3 className="sc-t-title-m sc-section__sub">Siatka 12 kart — zachowanie krawędziowe (transform-origin)</h3>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-4)" }}>
        Najedź na kartę przy krawędzi siatki: powinna rosnąć do wewnątrz (stopień B po 400ms), nie poza ekran.
      </p>
      <div style={{ display: "grid", gap: "var(--sc-s-4)", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
        {EDGE_ARTICLES.map((article) => (
          <NewsCard key={article.id} article={article} size="medium" expandable />
        ))}
      </div>
    </div>
  );
}

/**
 * Suwak steruje parametrem `bounce` sprężyny `ui` na izolowanym stanowisku obok — te same wartości,
 * których NewsCard używa wewnętrznie na stopniach A/B (docs/UI_KIT_PLAN.md → «Trzy stopnie»:
 * 0.18/0.26s na A, 0.22/0.38s na B). NewsCard nie przyjmuje własnego propa `transition` (kontrakt
 * propów jest zamrożony), więc strojenie na żywo pokazujemy na osobnym, wizualnie identycznym pudełku.
 */
function BounceRig() {
  const motionTokens = useMotionTokens();
  const [bounce, setBounce] = useState(0.18);
  const [stage, setStage] = useState<"rest" | "a" | "b">("rest");

  return (
    <div>
      <h3 className="sc-t-title-m sc-section__sub">Stopnie A/B — regulator odbicia (bounce)</h3>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-3)" }}>
        Izolowane stanowisko: ten sam parametr <code>bounce</code> sprężyny <code>ui</code>, tutaj pokazany osobno, żeby dało się go
        przesuwać na żywo.
      </p>
      <label className="sc-showcase__check" style={{ marginBottom: "var(--sc-s-4)", display: "flex", alignItems: "center", gap: "var(--sc-s-2)" }}>
        bounce: {bounce.toFixed(2)}
        <input
          type="range"
          min={0}
          max={0.5}
          step={0.01}
          value={bounce}
          onChange={(e) => setBounce(Number(e.target.value))}
          style={{ width: 160 }}
        />
      </label>
      <div className="sc-showcase__seg" role="group" aria-label="Podgląd stopnia" style={{ marginBottom: "var(--sc-s-4)" }}>
        {(["rest", "a", "b"] as const).map((s) => (
          <button key={s} type="button" aria-pressed={stage === s} onClick={() => setStage(s)}>
            {s === "rest" ? "spoczynek" : s === "a" ? "A — podświetlenie" : "B — przedpodgląd"}
          </button>
        ))}
      </div>
      <motion.div
        className="sc-morph-card sc-hoverable"
        style={{ width: 220, height: 140 }}
        animate={{
          scale: stage === "b" ? 1.12 : stage === "a" ? 1.03 : 1,
          y: stage === "rest" ? 0 : -3,
        }}
        transition={motionTokens.t("ui", { bounce })}
        data-lit={stage !== "rest" || undefined}
      >
        <strong>Karta próbna</strong>
        <span className="sc-probe__note">bounce {bounce.toFixed(2)}</span>
      </motion.div>
    </div>
  );
}
