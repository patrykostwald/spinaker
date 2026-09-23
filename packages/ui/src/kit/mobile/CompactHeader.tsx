"use client";

/**
 * CompactHeader — nagłówek, który zwęża się/rozszerza po KIERUNKU przewijania (nie po pozycji):
 * w dół → zwężenie (64 → 48px), w górę → powrót (docs/UI_KIT_PLAN.md → «Mobilne rozkłady»,
 * «Nagłówek»). Jedyny nasłuch przewijania w tym pliku — na kontenerze/oknie, NIE na elementach
 * listy — więc nie łamie zakazu nasłuchów "na element".
 *
 * Wysokość jest jedynym dozwolonym wyjątkiem od reguły „tylko transform/opacity" (jak w
 * `RevealHeight`), animowana sprężyną `ui`. Slot wyszukiwania dostaje stan `compact` przez render
 * prop, żeby sam mógł zwinąć się w ikonę.
 */

import { motion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { cn } from "../../lib/utils";
import { useMotionTokens } from "../motion/useMotionTokens";

export type CompactHeaderRenderProps = { compact: boolean };

export type CompactHeaderProps = {
  children: ReactNode | ((state: CompactHeaderRenderProps) => ReactNode);
  /** Kontener przewijania — na stoisku witryny to ramka telefonu; domyślnie okno przeglądarki. */
  scrollRootRef?: RefObject<HTMLElement | null>;
  className?: string;
};

const EXPANDED_HEIGHT = 64;
const COMPACT_HEIGHT = 48;
/** Ignoruje mikro-drgania przewijania (np. odbicie na iOS) poniżej tego progu w px. */
const DIRECTION_DEADZONE = 4;

export function CompactHeader({ children, scrollRootRef, className }: CompactHeaderProps) {
  const m = useMotionTokens();
  const [compact, setCompact] = useState(false);
  const lastScrollRef = useRef(0);

  useEffect(() => {
    const root = scrollRootRef?.current ?? null;
    const target: EventTarget = root ?? window;
    const getScrollTop = () => (root ? root.scrollTop : window.scrollY);
    lastScrollRef.current = getScrollTop();

    function onScroll() {
      const top = getScrollTop();
      const delta = top - lastScrollRef.current;
      if (Math.abs(delta) < DIRECTION_DEADZONE) return;
      setCompact(delta > 0 && top > COMPACT_HEIGHT);
      lastScrollRef.current = top;
    }

    target.addEventListener("scroll", onScroll, { passive: true } as AddEventListenerOptions);
    return () => target.removeEventListener("scroll", onScroll);
  }, [scrollRootRef]);

  return (
    <motion.header
      className={cn("sc-compact-header sc-chrome", className)}
      data-compact={compact || undefined}
      animate={{ height: compact ? COMPACT_HEIGHT : EXPANDED_HEIGHT, transition: m.t("ui") }}
    >
      <div className="sc-compact-header__inner">
        {typeof children === "function" ? children({ compact }) : children}
      </div>
    </motion.header>
  );
}
