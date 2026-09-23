"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useMotionTokens } from "../../motion/useMotionTokens";
import { RADIUS } from "../../tokens";

export const meta = {
  id: "proba-morfingu",
  title: "Próba morfingu przez portal",
  lead: "Bramka fali 0: karta w taśmie z overflow-x: auto musi przepłynąć do warstwy zamontowanej w <body>. Na tym stoi cały efekt portalu.",
};

const CARDS = Array.from({ length: 6 }, (_, i) => ({ id: i + 1, title: `Karta próbna ${i + 1}` }));

export function Section() {
  const m = useMotionTokens();
  const [active, setActive] = useState<number | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (active === null) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setActive(null);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [active]);

  return (
    <div>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-3)" }}>
        Kliknij kartę: ma urosnąć z własnego miejsca w taśmie (nie z krawędzi obcięcia) i wrócić dokładnie tam. Escape lub tło zamyka. Przewiń taśmę i spróbuj z kartą przy krawędzi.
      </p>
      <div className="sc-morph-strip">
        {CARDS.map((card) => {
          const isActive = active === card.id;
          return (
            <motion.button
              key={card.id}
              type="button"
              className="sc-morph-card sc-hoverable"
              // layoutId TYLKO na aktywnej karcie — rejestr pomiarów rośnie z N do 1 (plan → «Бюджет производительности»).
              layoutId={m.morph && isActive ? `sc-probe-${card.id}` : undefined}
              style={{ borderRadius: RADIUS.lg, opacity: isActive ? 0 : 1 }}
              whileHover={{ scale: m.scale(1.03), y: m.reduced ? 0 : -2 }}
              whileTap={{ scale: m.scale(0.97) }}
              transition={m.t("ui")}
              onClick={() => setActive(card.id)}
            >
              <span className="sc-t-caption sc-text-2">Taśma · overflow-x: auto</span>
              <strong>{card.title}</strong>
            </motion.button>
          );
        })}
      </div>

      {mounted &&
        createPortal(
          <AnimatePresence>
            {active !== null && (
              <>
                <motion.div
                  key="scrim"
                  className="sc-morph-scrim"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={m.t("scrim")}
                  onPointerDown={(e) => e.target === e.currentTarget && setActive(null)}
                />
                <motion.div
                  key={`surface-${active}`}
                  role="dialog"
                  aria-modal="true"
                  aria-label={`Karta próbna ${active}`}
                  className="sc-morph-surface"
                  layoutId={m.morph ? `sc-probe-${active}` : undefined}
                  // Promień inline i liczbowo — na tym samym elemencie co layoutId, inaczej rogi rozjadą się w elipsę.
                  style={{ borderRadius: RADIUS["2xl"] }}
                  initial={m.morph ? undefined : { opacity: 0 }}
                  animate={m.morph ? undefined : { opacity: 1 }}
                  exit={m.morph ? undefined : { opacity: 0 }}
                  transition={m.t("portalIn")}
                >
                  <span className="sc-t-caption sc-text-2">Warstwa w &lt;body&gt; · createPortal</span>
                  <h3 className="sc-t-title-l" style={{ margin: 0 }}>Karta próbna {active}</h3>
                  <motion.p
                    className="sc-t-body sc-text-2"
                    style={{ margin: 0, maxWidth: "var(--sc-measure)" }}
                    initial={{ opacity: 0, y: m.rise * 1.5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={m.t("expand", { delay: 0.12 })}
                  >
                    Treść wchodzi kaskadą już w trakcie morfingu, nie po nim — jedno działanie zamiast dwóch etapów. Zamknięcie wraca do karty bez odbicia.
                  </motion.p>
                  <button type="button" onClick={() => setActive(null)}>Zamknij</button>
                </motion.div>
              </>
            )}
          </AnimatePresence>,
          document.body,
        )}
    </div>
  );
}
