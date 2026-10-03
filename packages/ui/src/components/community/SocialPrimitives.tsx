"use client";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type CSSProperties } from 'react';

export const RATINGS = ['positive', 'doubt', 'negative'] as const;
export type Rating = typeof RATINGS[number];
export type Counts = Record<Rating, number>;
export const ratingLabels = (ai = false): Record<Rating, string> => ({ positive: ai ? 'Trafna' : 'Zgadzam się', doubt: 'Mam wątpliwości', negative: ai ? 'Błędna' : 'Nie zgadzam się' });
export function SocialIcon({ kind }: { kind: Rating | 'comment' }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind === 'positive' ? <path d="m5 12 4 4L19 6" /> : kind === 'negative' ? <path d="m6 6 12 12M18 6 6 18" /> : kind === 'doubt' ? <><path d="M8 8a4 4 0 1 1 6 3.5c-2 1-2 1.5-2 3" /><path d="M12 19h.01" /></> : <path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-8l-6 3v-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />}
  </svg>;
}
/**
 * Znaczki ✓ ? ✕ co jakiś czas pokazują liczby: pierwsza zamiana 2,5 s po wejściu na ekran (najpierw widać znaczki),
 * potem co 9,5 s liczby na 2,5 s, przenikanie 200 ms. `offset` przesuwa start kolejnych nitek, więc liczby przechodzą
 * falą przez listę. Tylko widoczne nitki; najechanie lub fokus zostawia liczby na stałe; przy „ogranicz ruch” liczby
 * stoją obok znaczków bez animacji (WCAG 2.2.2: ruch, który można zatrzymać).
 */
const SHOW_MS = 2500, CYCLE_MS = 9500, FIRST_MS = 2500;
function useNumberCycle(enabled: boolean, offset: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [numbers, setNumbers] = useState(false);
  const [held, setHeld] = useState(false);
  const [still, setStill] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setStill(media.matches);
    update(); media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    const element = ref.current;
    if (!enabled || still || !element) return;
    let timers: ReturnType<typeof setTimeout>[] = [];
    const stop = () => { timers.forEach(clearTimeout); timers = []; setNumbers(false); };
    const loop = (delay: number) => {
      timers.push(setTimeout(() => {
        setNumbers(true);
        timers.push(setTimeout(() => { setNumbers(false); loop(CYCLE_MS - SHOW_MS); }, SHOW_MS));
      }, delay));
    };
    const observer = new IntersectionObserver(([entry]) => { stop(); if (entry.isIntersecting) loop(FIRST_MS + offset); }, { threshold: .6 });
    observer.observe(element);
    return () => { observer.disconnect(); stop(); };
  }, [enabled, still, offset]);
  return { ref, still, showNumbers: enabled && (numbers || held), hold: (value: boolean) => setHeld(value) };
}

export function RatingFrame({ counts, ai, cycle = false, offset = 0, numbers = false }: { counts: Counts; ai?: boolean; cycle?: boolean; offset?: number; numbers?: boolean }) {
  const total = RATINGS.reduce((n, key) => n + counts[key], 0);
  const labels = ratingLabels(ai);
  const description = RATINGS.map(key => `${labels[key]}: ${counts[key]}`).join(', ');
  const { ref, still, showNumbers, hold } = useNumberCycle(cycle && total > 0, offset);
  return <div ref={ref} className="sc-social-frame" aria-label={description} data-highlight={total >= 3}
    data-numbers={(!numbers && showNumbers) || undefined} data-still={numbers || (cycle && still && total > 0) || undefined}
    onMouseEnter={() => hold(true)} onMouseLeave={() => hold(false)} onFocus={() => hold(true)} onBlur={() => hold(false)}>
    {RATINGS.map(key => <span className="sc-social-frame__slot" key={key}>
      <button type="button" className="sc-social-frame__icon" data-rating={key} aria-label={description} title={`${labels[key]}: ${counts[key]}`}
        style={{ color: total >= 3 ? `var(--sc-${key === 'doubt' ? 'warning' : key})` : 'var(--sc-line)', '--rating-opacity': total >= 3 ? .35 + .65 * counts[key] / total : 1 } as CSSProperties}>
        <SocialIcon kind={key} /><span className="sc-social-frame__n" aria-hidden="true">{counts[key]}</span><span role="tooltip">{labels[key]}: {counts[key]}</span>
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
    const measure = () => setOverflows(element.scrollHeight > element.clientHeight + 4);
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

/** Czas jak na X: „teraz”, „5 min”, „3 godz.”, potem data. */
export function ago(iso: string) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return 'teraz';
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)} godz.`;
  return new Date(iso).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}
/** Stały, delikatny kolor awatara z nazwy - autorów łatwiej odróżnić. Dr. Spin ma akcent serwisu. */
export function Avatar({ name, ai = false, size }: { name: string; ai?: boolean; size?: number }) {
  let hue = 0; for (const c of name) hue = (hue * 31 + c.charCodeAt(0)) % 360;
  const style = { ['--hue' as string]: hue, ...(size ? { width: size, height: size } : {}) };
  return <span className="sc-social-avatar" data-ai={ai || undefined} aria-hidden="true" style={style}>{ai ? 'DS' : name.replace('@', '').charAt(0).toUpperCase()}</span>;
}
