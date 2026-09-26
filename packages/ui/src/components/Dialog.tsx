"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Button, useModalA11y, useMotionTokens, useScrollLock } from "../kit";
import { CloseIcon } from "../kit/icons/CloseIcon";

export function Dialog({ open, onClose, title, children, className = "" }: { open: boolean; onClose: () => void; title: string; children: ReactNode; className?: string }) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const originRef = useRef<HTMLElement | null>(null);
  const motionTokens = useMotionTokens();
  const a11y = useModalA11y(surfaceRef, open, onClose);
  useScrollLock(open);
  // Okno renderujemy w <body>, nie w miejscu przycisku — rodzic (panel, pasek z przewijaniem) nie może go przyciąć ani zablokować kliknięć.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    originRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = requestAnimationFrame(a11y.focusFirst);
    return () => cancelAnimationFrame(frame);
  }, [a11y.focusFirst, open]);

  if (!mounted) return null;
  return createPortal(
    <AnimatePresence onExitComplete={() => a11y.restoreFocus(originRef.current)}>
      {open ? (
        <motion.div className="sc-dialog-backdrop" role="presentation" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={motionTokens.t("fade")} onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
          <motion.section ref={surfaceRef} className={["sc-dialog", className].filter(Boolean).join(" ")} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}
            initial={{ opacity: 0, y: motionTokens.rise }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: motionTokens.rise }} transition={motionTokens.t("expand")}>
            <header className="sc-dialog__head">
              <h2 className="sc-t-title-s">{title}</h2>
              <Button type="button" shape="icon" variant="ghost" size="md" aria-label="Zamknij okno" onClick={onClose} iconStart={<CloseIcon />} />
            </header>
            <div className="sc-dialog__body">{children}</div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
