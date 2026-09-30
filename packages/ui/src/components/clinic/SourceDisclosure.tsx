"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Native disclosure follows DOM reading order; desktop keeps its source column open. */
export function SourceDisclosure({ children, className, full }: { children: ReactNode; className?: string; full?: boolean }) {
  // Materiał źródłowy otwarty na każdej szerokości: czytelnik najpierw widzi wpis, dopiero potem ocenę (uwaga testera UX).
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => { if (ref.current) ref.current.open = true; }, []);
  return <details ref={ref} open className={`sc-source-disclosure ${className ?? ""}`} data-full={full || undefined}>
    <summary>Materiał źródłowy</summary>
    {children}
  </details>;
}
