"use client";

/**
 * Pozioma taśma kart (odpowiednik starego `MaterialStrip`): przewijanie kółkiem/palcem,
 * strzałki `ghost icon` po bokach (widoczne przy najechaniu na taśmę, zawsze z klawiatury),
 * strzałki przewijają sprężyną `move` przez `scrollBy` (w reduced motion — skokiem).
 * Bez stałego paska przewijania: krawędź z dalszą treścią wygasza się (`data-more-start/end`), a strzałki
 * pokazują się tylko w stronę, w którą jest co przewijać. Karty w taśmach nie
 * rosną na najechanie (`expandable={false}` u wywołujących) — przycięłoby je `overflow-x: auto`.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "../Button";
import { ChevronLeftIcon } from "../icons/ChevronLeftIcon";
import { ChevronRightIcon } from "../icons/ChevronRightIcon";
import { useMotionTokens } from "../motion/useMotionTokens";
import { cn } from "../../lib/utils";

export type StripProps = {
  label: string;
  children: ReactNode;
  /** Szerokość jednego kroku strzałki, px. Domyślnie 0.8 szerokości widoku. */
  step?: number;
  className?: string;
  /** Szerokość slotu karty (CSS), domyślnie 240px. */
  slot?: string;
};

export function Strip({ label, children, step, className, slot = "240px" }: StripProps) {
  const scroller = useRef<HTMLDivElement | null>(null);
  const m = useMotionTokens();
  const [edges, setEdges] = useState({ start: false, end: false });

  useEffect(() => {
    const node = scroller.current;
    if (!node) return;
    const update = () => {
      const start = node.scrollLeft > 4;
      const end = node.scrollLeft + node.clientWidth < node.scrollWidth - 4;
      setEdges(previous => (previous.start === start && previous.end === end ? previous : { start, end }));
    };
    update();
    node.addEventListener("scroll", update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(node);
    Array.from(node.children).forEach(child => observer.observe(child));
    return () => { node.removeEventListener("scroll", update); observer.disconnect(); };
  }, [children]);

  function move(direction: -1 | 1) {
    const node = scroller.current;
    if (!node) return;
    node.scrollBy({ left: direction * (step ?? node.clientWidth * 0.8), behavior: m.reduced ? "auto" : "smooth" });
  }

  return (
    <div className={cn("sc-strip", className)} style={{ ["--sc-strip-slot" as string]: slot }}
      data-more-start={edges.start ? "" : undefined} data-more-end={edges.end ? "" : undefined}>
      <div
        ref={scroller}
        className="sc-strip__scroller"
        tabIndex={0}
        aria-label={`${label} — przewijaj poziomo`}
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget) return;
          if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault();
            move(event.key === "ArrowLeft" ? -1 : 1);
          }
        }}
      >
        {children}
      </div>
      <div className="sc-strip__arrows">
        <Button shape="icon" variant="ghost" size="sm" aria-label={`Przewiń w lewo: ${label}`} onClick={() => move(-1)} iconStart={<ChevronLeftIcon size={20} />} />
        <Button shape="icon" variant="ghost" size="sm" aria-label={`Przewiń w prawo: ${label}`} onClick={() => move(1)} iconStart={<ChevronRightIcon size={20} />} />
      </div>
    </div>
  );
}

/** Puste miejsce w taśmie — gdy materiałów jest mniej niż slotów (stary `EmptyMaterialSlot`). */
export function EmptySlot({ index, label }: { index: number; label: string }) {
  return (
    <div className="sc-strip__empty" aria-hidden="true">
      <span className="sc-t-caption sc-text-3">{String(index).padStart(2, "0")}</span>
      <span className="sc-t-caption sc-text-3">{label}</span>
    </div>
  );
}
