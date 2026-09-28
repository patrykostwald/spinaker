"use client";

import { useEffect } from "react";

/**
 * Telefon: listy z własnym przewijaniem nie „łapią” palca — strona przewija się dalej.
 * Przytrzymanie palca na liście (ok. 0,4 s) włącza jej przewijanie (niebieska ramka, krótka wibracja);
 * dotknięcie poza listą wyłącza. Na komputerze (mysz) nic się nie zmienia.
 */
export const INNER_SCROLLERS = [
  ".sc-clinic-column__list",
  ".sc-home-baza__results",
  ".sc-home-baza__aside",
  ".sc-home-lead__list",
  ".sc-deleted__list",
  ".sc-clinic-sotd__reading",
  ".sc-source-coverage__list",
].join(",");

const HOLD_MS = 400;
const MOVE_TOLERANCE = 10;

export function TouchScrollGuard() {
  useEffect(() => {
    if (!window.matchMedia("(pointer: coarse)").matches) return;
    const root = document.documentElement;
    root.dataset.touchScroll = "guard";
    let timer: number | undefined;
    let start: { x: number; y: number } | null = null;
    let active: HTMLElement | null = null;

    const release = () => {
      if (active) delete active.dataset.scrollActive;
      active = null;
    };
    const onStart = (event: TouchEvent) => {
      const target = (event.target as HTMLElement | null)?.closest<HTMLElement>(INNER_SCROLLERS) ?? null;
      if (active && target !== active) release();
      if (!target || target === active) return;
      const touch = event.touches[0];
      start = { x: touch.clientX, y: touch.clientY };
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        active = target;
        target.dataset.scrollActive = "1";
        navigator.vibrate?.(15);
      }, HOLD_MS);
    };
    const onMove = (event: TouchEvent) => {
      if (!start) return;
      const touch = event.touches[0];
      if (Math.abs(touch.clientX - start.x) > MOVE_TOLERANCE || Math.abs(touch.clientY - start.y) > MOVE_TOLERANCE) {
        window.clearTimeout(timer);
        start = null;
      }
    };
    const onEnd = () => {
      window.clearTimeout(timer);
      start = null;
    };
    document.addEventListener("touchstart", onStart, { passive: true });
    document.addEventListener("touchmove", onMove, { passive: true });
    document.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      document.removeEventListener("touchstart", onStart);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onEnd);
      delete root.dataset.touchScroll;
    };
  }, []);
  return null;
}
