"use client";

import { useEffect, useRef, useState, type ReactNode } from 'react';

/**
 * Przewijanie w poziomie bez paska przewijania (właściciel 4.10): tylko strzałki ‹ › po bokach,
 * jak w łańcuchu spinek; pokazują się, gdy jest dokąd przewinąć, i po najechaniu.
 */
export function ScrollArrows({ className = '', label, children }: { className?: string; label: string; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const [edge, setEdge] = useState({ prev: false, next: false });
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const update = () => setEdge({ prev: el.scrollLeft > 2, next: el.scrollLeft + el.clientWidth < el.scrollWidth - 2 });
    update();
    el.addEventListener('scroll', update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => { el.removeEventListener('scroll', update); observer.disconnect(); };
  }, []);
  const move = (dir: number) => box.current?.scrollBy({ left: dir * box.current.clientWidth * .8, behavior: 'smooth' });
  return <div className="sc-hscroll">
    {edge.prev && <button type="button" className="sc-hscroll__arrow sc-hscroll__arrow--prev" aria-label={`${label}: wcześniej`} onClick={() => move(-1)}>‹</button>}
    <div ref={box} className={`sc-hscroll__box ${className}`} role="region" aria-label={label} tabIndex={0}>{children}</div>
    {edge.next && <button type="button" className="sc-hscroll__arrow sc-hscroll__arrow--next" aria-label={`${label}: dalej`} onClick={() => move(1)}>›</button>}
  </div>;
}
