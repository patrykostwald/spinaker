"use client";

import { useEffect } from "react";

/** Elementy spin.clinic z efektem "spotlight" przy najechaniu (przeszłość.today ma własną konwencję terminalową - wyłączona). */
export const SPOTLIGHT_SELECTOR = ".sc-rail__group a, .sc-shell-desktop a, .sc-v3-seg button, .sc-archive-more, .sc-v3-qbtn, .sc-v3-btn-pri";

/**
 * Hover "spotlight" (seria 2): miękka plama światła w kolorze akcentu podąża za kursorem wewnątrz elementu.
 * Jeden słuchacz na dokumencie, aktualizacja zmiennych --mx/--my tylko na elemencie pod kursorem, raz na klatkę (rAF).
 * Bez efektu na urządzeniach bez precyzyjnego wskaźnika i przy prefers-reduced-motion (CSS daje wtedy statyczny odcień).
 */
export function SpotlightHover() {
  useEffect(() => {
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0, target: HTMLElement | null = null, x = 0, y = 0;
    const flush = () => {
      frame = 0;
      if (!target) return;
      const r = target.getBoundingClientRect();
      target.style.setProperty("--mx", `${Math.round(x - r.left)}px`);
      target.style.setProperty("--my", `${Math.round(y - r.top)}px`);
    };
    const move = (event: PointerEvent) => {
      const el = (event.target as Element | null)?.closest?.(SPOTLIGHT_SELECTOR) as HTMLElement | null;
      if (!el || el.closest(".pt-v3")) { target = null; return; }
      target = el; x = event.clientX; y = event.clientY;
      if (!frame) frame = requestAnimationFrame(flush);
    };
    document.addEventListener("pointermove", move, { passive: true });
    return () => { document.removeEventListener("pointermove", move); if (frame) cancelAnimationFrame(frame); };
  }, []);
  return null;
}
