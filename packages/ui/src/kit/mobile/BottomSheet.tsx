"use client";

/**
 * BottomSheet — telefoniczny odpowiednik dropdownu/modala (docs/UI_KIT_PLAN.md → «Mobilne
 * rozkłady»: «Dropdowny i filtry na telefonie to dolne arkusze»). Fizyka jest DOKŁADNIE tą samą
 * fizyką, co zamykanie portalu: 1:1 za palcem, projekcja bezwładności, decyzja po znaku prędkości,
 * gumowa granica u góry (patrz `portal/useDragDismiss.ts`, R4).
 *
 * `AnimatePresence` jest zamontowany NA STAŁE wewnątrz tego komponentu — wywołujący warunkuje
 * tylko `open`, nigdy nie odmontowuje samego `<BottomSheet>` (plan → «Portal»: warunkowy ma być
 * tylko dziecko `AnimatePresence`, nie ona sama).
 */

import { AnimatePresence, motion } from "framer-motion";
import { createPortal } from "react-dom";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { cn } from "../../lib/utils";
import { RADIUS } from "../tokens";
import { useMotionTokens } from "../motion/useMotionTokens";
import { useDragDismiss } from "../portal/useDragDismiss";
import { useScrollLock } from "../portal/useScrollLock";
import { useModalA11y } from "../portal/useModalA11y";

export type BottomSheetProps = {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Nadpisuje wygenerowane `id` powierzchni — potrzebne np. `Dropdown`u dla `aria-controls`. */
  id?: string;
};

/** Zanim arkusz zdąży się zmierzyć, potrzebny jest jakiś mianownik dla progu zamknięcia. */
const HEIGHT_ESTIMATE = 480;

export function BottomSheet({ open, onClose, title, children, className, id }: BottomSheetProps) {
  const m = useMotionTokens();
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const [mounted, setMounted] = useState(false);
  const [height, setHeight] = useState(HEIGHT_ESTIMATE);
  const instanceId = useId();
  const titleId = `sc-sheet-title-${instanceId}`;

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    const rect = surfaceRef.current?.getBoundingClientRect();
    if (rect?.height) setHeight(rect.height);
  }, [open]);

  const drag = useDragDismiss({ height, onDismiss: onClose });
  useScrollLock(open);
  const a11y = useModalA11y(surfaceRef as React.RefObject<HTMLElement>, open, onClose);

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => a11y.focusFirst());
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!mounted) return null;

  return createPortal(
    <AnimatePresence onExitComplete={() => a11y.restoreFocus(previouslyFocusedRef.current)}>
      {open && (
        <div className="sc-sheet">
          <motion.div
            className="sc-sheet__scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: m.t("scrim") }}
            exit={{ opacity: 0, transition: m.t("scrim") }}
            style={{ opacity: drag.scrimOpacity }}
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            ref={surfaceRef}
            id={id}
            role="dialog"
            aria-modal="true"
            aria-labelledby={title ? titleId : undefined}
            className={cn("sc-sheet__surface sc-chrome", className)}
            style={{
              borderTopLeftRadius: RADIUS["2xl"],
              borderTopRightRadius: RADIUS["2xl"],
              y: drag.y,
            }}
            initial={{ y: m.reduced ? 0 : height, opacity: m.reduced ? 0 : 1 }}
            animate={{ y: 0, opacity: 1, transition: m.t("sheet") }}
            exit={{ y: m.reduced ? 0 : height, opacity: m.reduced ? 0 : 1, transition: m.t("sheet") }}
            {...drag.dragProps}
            onPointerDown={(event) => drag.startIfAtTop(event, scrollerRef.current)}
          >
            <div
              className="sc-sheet__handle"
              aria-hidden="true"
              style={{ touchAction: "none", WebkitTouchCallout: "none" }}
            />
            {title ? (
              <h2 id={titleId} className="sc-sheet__title sc-t-title-s">
                {title}
              </h2>
            ) : null}
            <div ref={scrollerRef} className="sc-sheet__scroller">
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
