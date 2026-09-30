"use client";

import { useRef, type PointerEvent } from "react";

/**
 * Przytrzymanie palcem (ok. 0,45 s) wywołuje akcję — np. rozwija przycięty wpis albo wywiad na telefonie.
 * Tylko dotyk: mysz i pióro nie reagują. Ruch palca (przewijanie) anuluje przytrzymanie.
 */
export function useLongPress(action: () => void, delay = 450) {
  const timer = useRef<number | undefined>(undefined);
  const start = useRef<{ x: number; y: number } | null>(null);
  const clear = () => {
    window.clearTimeout(timer.current);
    start.current = null;
  };
  return {
    onPointerDown(event: PointerEvent) {
      if (event.pointerType !== "touch") return;
      start.current = { x: event.clientX, y: event.clientY };
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        start.current = null;
        navigator.vibrate?.(15);
        action();
      }, delay);
    },
    onPointerMove(event: PointerEvent) {
      if (start.current && (Math.abs(event.clientX - start.current.x) > 10 || Math.abs(event.clientY - start.current.y) > 10)) clear();
    },
    onPointerUp: clear,
    onPointerCancel: clear,
  };
}
