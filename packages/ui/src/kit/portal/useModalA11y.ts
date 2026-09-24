"use client";

import { useCallback, useEffect, useRef, type RefObject } from "react";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export type ModalA11y = {
  /** Ставит фокус на первый фокусируемый элемент поверхности. Вызывать ПОСЛЕ завершения анимации открытия. */
  focusFirst: () => void;
  /** Возвращает фокус на элемент, с которого был открыт оверлей. Вызывать в `onExitComplete`. */
  restoreFocus: (originEl: HTMLElement | null) => void;
};

/**
 * A11y-обвязка полноэкранного оверлея: `inert` на `#main-content` и `header` вместо
 * рукописной ловушки фокуса — это заодно блокирует поиск по странице (Ctrl+F) и указатель
 * под оверлеем. Ловушка Tab добавлена лишь как ЗАПАСНОЙ вариант на случай, если `inert`
 * почему-то не подхватился. Escape перехватывается на фазе capture, чтобы срабатывать
 * раньше вложенных обработчиков (например, открытого Dropdown внутри оверлея).
 */
export function useModalA11y(
  surfaceRef: RefObject<HTMLElement>,
  active: boolean,
  onEscape: () => void,
): ModalA11y {
  const inertedRef = useRef<HTMLElement[]>([]);

  useEffect(() => {
    if (!active) return;
    const inerted: HTMLElement[] = [];
    const main = document.getElementById("main-content");
    const header = document.querySelector("header");
    for (const el of [main, header]) {
      if (el instanceof HTMLElement && !el.hasAttribute("inert")) {
        el.setAttribute("inert", "");
        inerted.push(el);
      }
    }
    inertedRef.current = inerted;
    return () => {
      for (const el of inertedRef.current) el.removeAttribute("inert");
      inertedRef.current = [];
    };
  }, [active]);

  useEffect(() => {
    if (!active) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onEscape();
        return;
      }
      if (event.key !== "Tab") return;
      const surface = surfaceRef.current;
      if (!surface) return;
      const focusable = Array.from(surface.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
        (el) => el.offsetParent !== null,
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus({ preventScroll: true });
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus({ preventScroll: true });
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [active, onEscape, surfaceRef]);

  const focusFirst = useCallback(() => {
    const surface = surfaceRef.current;
    if (!surface) return;
    const focusable = surface.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    (focusable ?? surface).focus({ preventScroll: true });
  }, [surfaceRef]);

  const restoreFocus = useCallback((originEl: HTMLElement | null) => {
    originEl?.focus({ preventScroll: true });
  }, []);

  return { focusFirst, restoreFocus };
}
