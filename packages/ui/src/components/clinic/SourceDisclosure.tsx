"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Native disclosure follows DOM reading order; desktop keeps its source column open. */
export function SourceDisclosure({ children, className, full }: { children: ReactNode; className?: string; full?: boolean }) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 761px)");
    const sync = () => { if (ref.current) ref.current.open = desktop.matches; };
    sync();
    desktop.addEventListener("change", sync);
    return () => desktop.removeEventListener("change", sync);
  }, []);
  return <details ref={ref} className={`sc-source-disclosure ${className ?? ""}`} data-full={full || undefined}>
    <summary>Materiał źródłowy</summary>
    {children}
  </details>;
}
