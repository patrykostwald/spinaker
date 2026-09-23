"use client";

/**
 * useFocalBand — zamiennik najechania na telefonie (docs/UI_KIT_PLAN.md → «Mobilne rozkłady»,
 * «Fokus przy przewijaniu — zamiana najechania»).
 *
 * Pasmo fokalne to środkowe 30% obszaru przewijania (domyślnie 35–65% wysokości). Karta, której
 * środek jest najbliżej środka pasma, dostaje `data-lit="true"` — dokładnie ta sama uwaga CSS,
 * której `.sc-hoverable::before` używa dla najechania/fokusu (kit.css, blok R0/R4). Ten hak steruje
 * WYŁĄCZNIE poświatą przez atrybut DOM, bez React state na element — stopień A (scale/lewitacja)
 * zostaje tym, czym jest w NewsCard, sterowanym własnym hover/focus tej karty.
 *
 * Wydajność: JEDEN IntersectionObserver na instancję, `rootMargin` ściąga korzeń do samego pasma —
 * przecięcie = "w paśmie". Jedyny nasłuch przewijania w całym pliku tylko ZAPISUJE prędkość do refa
 * (bez odczytu geometrii, bez setState) — decyzję "czy zatwierdzić" podejmuje się z tego refa.
 */

import { useEffect, useRef, useState, type RefObject } from "react";

export type FocalBandAxis = "y" | "x";

export type FocalBandOptions = {
  /** Ułamki [start, koniec] pasma na osi przewijania. @default [0.35, 0.65] — tylko oś Y. */
  band?: [number, number];
  /** Selektor kandydatów wewnątrz kontenera. @default '[data-material-id]' */
  selector?: string;
  /** Oś przewijania — Carousel używa 'x' z marginesem 0px -42% 0px -42% (Karuzela w planie). */
  axis?: FocalBandAxis;
  /** Wymusza działanie na urządzeniach z (hover: hover) and (pointer: fine) — używa stoisko witryny. */
  force?: boolean;
  /** Próg prędkości (px/ms), powyżej którego zmiana fokusu jest wstrzymana do zwolnienia. */
  velocityThreshold?: number;
};

/** Pasmo fokalne z planu (35–65% wysokości) — eksportowane, żeby FoldedSection używało tego samego progu. */
export const FOCAL_BAND: [number, number] = [0.35, 0.65];
const DEFAULT_VELOCITY_THRESHOLD = 0.55; // px/ms ≈ ~33px za klatkę 60Hz — dobrany na oko, patrz «Ryzyka»

/** `rootMargin` ściągający korzeń IntersectionObserver do pasma — używane też przez FoldedSection. */
export function focalBandRootMargin(axis: FocalBandAxis, band: [number, number] = FOCAL_BAND): string {
  const [start, end] = band;
  const before = `${(start * 100).toFixed(3)}%`;
  const after = `${((1 - end) * 100).toFixed(3)}%`;
  return axis === "y" ? `-${before} 0px -${after} 0px` : `0px -${after} 0px -${before}`;
}

type Candidate = { el: HTMLElement; center: number };

/**
 * Zwraca id (`data-material-id`) elementu aktualnie uznanego za focalny, albo `null`, gdy żaden.
 */
export function useFocalBand(containerRef: RefObject<HTMLElement | null>, options: FocalBandOptions = {}): string | null {
  const {
    band = FOCAL_BAND,
    selector = "[data-material-id]",
    axis = "y",
    force = false,
    velocityThreshold = DEFAULT_VELOCITY_THRESHOLD,
  } = options;

  const [focalId, setFocalId] = useState<string | null>(null);

  const candidatesRef = useRef<Map<Element, Candidate>>(new Map());
  const bandCenterRef = useRef<number | null>(null);
  const committedElRef = useRef<HTMLElement | null>(null);
  const velocityRef = useRef(0);
  const lastScrollRef = useRef(0);
  const lastTimeRef = useRef(0);

  // Stabilne przez cały czas życia efektu — zmiana w trakcie przewijania nie jest scenariuszem tego komponentu.
  const bandKey = band.join(",");

  useEffect(() => {
    const maybeContainer = containerRef.current;
    if (!maybeContainer || typeof IntersectionObserver === "undefined") return;
    // Wiązanie do nowej stałej: domknięcia funkcji zadeklarowanych niżej (obserwatorzy,
    // nasłuch przewijania) inaczej nie zachowują zawężenia `HTMLElement | null` → `HTMLElement`.
    const container: HTMLElement = maybeContainer;

    if (!force) {
      const mql = window.matchMedia("(hover: hover) and (pointer: fine)");
      if (mql.matches) return;
    }

    function commit(el: HTMLElement | null) {
      const prev = committedElRef.current;
      if (prev === el) return;
      if (prev) prev.removeAttribute("data-lit");
      if (el) el.setAttribute("data-lit", "true");
      committedElRef.current = el;
      setFocalId(el?.getAttribute("data-material-id") ?? null);
    }

    function pickNearest(): HTMLElement | null {
      const bandCenter = bandCenterRef.current;
      if (bandCenter == null) return null;
      let best: Candidate | null = null;
      for (const candidate of candidatesRef.current.values()) {
        if (!best || Math.abs(candidate.center - bandCenter) < Math.abs(best.center - bandCenter)) {
          best = candidate;
        }
      }
      return best?.el ?? null;
    }

    function maybeCommit() {
      if (Math.abs(velocityRef.current) > velocityThreshold) return; // szybkie przewijanie: fokus dogania, nie przeskakuje
      commit(pickNearest());
    }

    function onIntersect(entries: IntersectionObserverEntry[]) {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          const rect = entry.boundingClientRect;
          const center = axis === "y" ? rect.top + rect.height / 2 : rect.left + rect.width / 2;
          candidatesRef.current.set(entry.target, { el: entry.target as HTMLElement, center });
        } else {
          candidatesRef.current.delete(entry.target);
        }
        if (entry.rootBounds) {
          bandCenterRef.current =
            axis === "y"
              ? entry.rootBounds.top + entry.rootBounds.height / 2
              : entry.rootBounds.left + entry.rootBounds.width / 2;
        }
      }
      maybeCommit();
    }

    const observer = new IntersectionObserver(onIntersect, {
      root: container,
      rootMargin: focalBandRootMargin(axis, band),
      threshold: [0, 1],
    });

    function observeAll() {
      container.querySelectorAll<HTMLElement>(selector).forEach((el) => observer.observe(el));
    }
    observeAll();

    // Sekcje/karuzele montują karty asynchronicznie (rozwijanie FoldedSection, doładowanie) —
    // dogląda nowych kandydatów bez ponownego tworzenia obserwatora.
    const mutationObserver = new MutationObserver(observeAll);
    mutationObserver.observe(container, { childList: true, subtree: true });

    // Jedyny nasłuch przewijania w tym pliku: TYLKO pisze do refa, żadnego odczytu geometrii i setState.
    function onScroll() {
      const now = performance.now();
      const value = axis === "y" ? container.scrollTop : container.scrollLeft;
      const dt = now - lastTimeRef.current;
      if (dt > 0 && lastTimeRef.current > 0) {
        velocityRef.current = Math.abs(value - lastScrollRef.current) / dt;
      }
      lastScrollRef.current = value;
      lastTimeRef.current = now;
      maybeCommit(); // sprawdza deceleration z aktualnie znanych (ostatni raz zmierzonych w IO) kandydatów
    }
    container.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      observer.disconnect();
      mutationObserver.disconnect();
      container.removeEventListener("scroll", onScroll);
      committedElRef.current?.removeAttribute("data-lit");
      committedElRef.current = null;
      candidatesRef.current.clear();
      bandCenterRef.current = null;
      setFocalId(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [containerRef, selector, axis, force, velocityThreshold, bandKey]);

  return focalId;
}
