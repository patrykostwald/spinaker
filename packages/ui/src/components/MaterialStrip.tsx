"use client";

import { useRef, type ReactNode } from "react";

export function MaterialStrip({ label, height, children }: { label: string; height: 'sm' | 'md' | 'lg'; children: ReactNode }) {
  const scroller = useRef<HTMLDivElement>(null);
  function move(direction: number) {
    const node = scroller.current;
    if (node) node.scrollBy({ left: direction * 240, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }
  return (
    <div
      ref={scroller}
      className={`material-strip material-strip-${height}`}
      tabIndex={0}
      aria-label={`${label} — przewijaj poziomo`}
      onKeyDown={event => {
        if (event.target === event.currentTarget && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
          event.preventDefault();
          move(event.key === 'ArrowLeft' ? -1 : 1);
        }
      }}
    >
      {children}
    </div>
  );
}
