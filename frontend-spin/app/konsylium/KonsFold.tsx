"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Sekcja rozwijana (Aspekt 1 / I2-8): skraca główny przepływ /konsylium. Zachowuje kotwicę `#id`
 * (otwiera się, gdy adres lub spis treści wskazuje na nią) i nagłówek h2 w podsumowaniu.
 */
export function KonsFold({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const sync = () => {
      if (window.location.hash === `#${id}`) {
        setOpen(true);
        requestAnimationFrame(() => ref.current?.scrollIntoView());
      }
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [id]);
  return (
    <details id={id} ref={ref} className="sc-kons-fold" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
      <summary aria-expanded={open}><h2>{title}</h2></summary>
      <div className="sc-kons-fold__body">{children}</div>
    </details>
  );
}
