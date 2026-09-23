"use client";

/**
 * useDismissable — zamykanie panelu klikiem poza nim, Escape (z powrotem fokusu na wyzwalacz)
 * i Tab (bez pułapki fokusu — Tab robi swoje, panel tylko się zamyka).
 * docs/UI_KIT_PLAN.md → «Dropdown»: "Escape закрывает и возвращает фокус на триггер, Tab закрывает без ловушки".
 */

import { useEffect, useRef, type RefObject } from "react";

export type UseDismissableOptions = {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement>;
};

export function useDismissable<T extends HTMLElement>({ open, onClose, triggerRef }: UseDismissableOptions): RefObject<T> {
  const panelRef = useRef<T>(null);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: PointerEvent) {
      const target = event.target as Node | null;
      if (!target) return;
      if (panelRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      onClose();
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        triggerRef.current?.focus();
      } else if (event.key === "Tab") {
        // Nie łapiemy fokusu: Tab dokańcza swój naturalny ruch, panel tylko się zamyka.
        onClose();
      }
    }

    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown, true);
    };
  }, [open, onClose, triggerRef]);

  return panelRef;
}
