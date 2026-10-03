"use client";
import { useLayoutEffect, useRef, useState, type ReactNode, type CSSProperties } from 'react';

export const RATINGS = ['positive', 'doubt', 'negative'] as const;
export type Rating = typeof RATINGS[number];
export type Counts = Record<Rating, number>;
export const ratingLabels = (ai = false): Record<Rating, string> => ({ positive: ai ? 'Trafna' : 'Zgadzam się', doubt: 'Mam wątpliwości', negative: ai ? 'Błędna' : 'Nie zgadzam się' });
export function SocialIcon({ kind }: { kind: Rating | 'comment' }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind === 'positive' ? <path d="m5 12 4 4L19 6" /> : kind === 'negative' ? <path d="m6 6 12 12M18 6 6 18" /> : kind === 'doubt' ? <><path d="M8 8a4 4 0 1 1 6 3.5c-2 1-2 1.5-2 3" /><path d="M12 19h.01" /></> : <path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-8l-6 3v-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />}
  </svg>;
}
export function RatingFrame({ counts, ai }: { counts: Counts; ai?: boolean }) {
  const total = RATINGS.reduce((n, key) => n + counts[key], 0);
  const labels = ratingLabels(ai);
  const description = RATINGS.map(key => `${labels[key]}: ${counts[key]}`).join(', ');
  return <div className="sc-social-frame" aria-label={description} data-highlight={total >= 3}>
    {RATINGS.map(key => <span className="sc-social-frame__slot" key={key}>
      <button type="button" className="sc-social-frame__icon" data-rating={key} aria-label={description} title={`${labels[key]}: ${counts[key]}`}
        style={{ color: total >= 3 ? `var(--sc-${key === 'doubt' ? 'warning' : key})` : 'var(--sc-line)', '--rating-opacity': total >= 3 ? .35 + .65 * counts[key] / total : 1 } as CSSProperties}>
        <SocialIcon kind={key} /><span role="tooltip">{labels[key]}: {counts[key]}</span>
      </button>
    </span>)}
  </div>;
}
export function ClampedText({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element || open) return;
    const measure = () => setOverflows(element.scrollHeight > element.clientHeight + 1);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [children, open]);
  return <div className="sc-social-text"><div ref={ref} className={open ? '' : 'sc-social-clamp'}>{children}</div>
    {(overflows || open) && <button type="button" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? 'Zwiń' : 'Rozwiń'}</button>}
  </div>;
}
export function CharacterCount({ text, limit }: { text: string; limit: number }) {
  const length = Array.from(text).length;
  return <small className="sc-social-count" data-near={length >= limit * .9} aria-live="polite">{length}/{limit}</small>;
}
