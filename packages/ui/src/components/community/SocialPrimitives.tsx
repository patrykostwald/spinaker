"use client";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type CSSProperties } from 'react';

// kolejność wyświetlania ✕ ? ✓ (właściciel 5.10)
export const RATINGS = ['negative', 'doubt', 'positive'] as const;
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
/** Znak Dr. Spina (właściciel 6.10, werdykt panelu: dymek ze spiralą): wypowiedź, którą ktoś zakręcił - oceniamy
 *  wypowiedź, nie osobę. Ogonek krótki i ścięty po prawej, spirala Archimedesa; w małych rozmiarach prostsza spirala. */
const DS_BUBBLE = 'M37.32 46.95L35.82 47.22L34.3 47.4L32.77 47.49L31.23 47.49L29.7 47.4L28.18 47.22L26.68 46.95L25.2 46.59L23.76 46.15L22.36 45.63L21 45.02L19.7 44.34L18.46 43.58L17.28 42.75L16.17 41.85L15.15 40.89L14.2 39.87L13.34 38.8L12.58 37.69L11.9 36.52L11.33 35.33L10.85 34.1L10.48 32.85L10.21 31.57L10.05 30.29L10 29L10.05 27.71L10.21 26.43L10.48 25.15L10.85 23.9L11.33 22.67L11.9 21.48L12.58 20.31L13.34 19.2L14.2 18.13L15.15 17.11L16.17 16.15L17.28 15.25L18.46 14.42L19.7 13.66L21 12.98L22.36 12.37L23.76 11.85L25.2 11.41L26.68 11.05L28.18 10.78L29.7 10.6L31.23 10.51L32.77 10.51L34.3 10.6L35.82 10.78L37.32 11.05L38.8 11.41L40.24 11.85L41.64 12.37L43 12.98L44.3 13.66L45.54 14.42L46.72 15.25L47.83 16.15L48.85 17.11L49.8 18.13L50.66 19.2L51.42 20.31L52.1 21.48L52.67 22.67L53.15 23.9L53.52 25.15L53.79 26.43L53.95 27.71L54 29L53.95 30.29L53.79 31.57L53.52 32.85L53.15 34.1L52.67 35.33L52.1 36.52L51.42 37.69L50.66 38.8L49.8 39.87L48.85 40.89L47.83 41.85L46.72 42.75L47 50Z';
const DS_SPIRAL = 'M32 19L32.69 19.13L33.36 19.32L34.01 19.54L34.63 19.81L35.22 20.12L35.79 20.47L36.32 20.85L36.82 21.27L37.28 21.71L37.7 22.18L38.09 22.67L38.43 23.19L38.73 23.72L38.99 24.26L39.21 24.81L39.38 25.37L39.52 25.94L39.61 26.5L39.65 27.07L39.66 27.62L39.63 28.17L39.56 28.71L39.45 29.23L39.3 29.74L39.12 30.23L38.91 30.69L38.67 31.14L38.41 31.55L38.11 31.94L37.8 32.31L37.46 32.64L37.11 32.95L36.74 33.22L36.35 33.46L35.96 33.67L35.56 33.84L35.16 33.98L34.75 34.09L34.34 34.17L33.94 34.22L33.54 34.23L33.15 34.22L32.77 34.18L32.4 34.11L32.04 34.01L31.7 33.89L31.37 33.75L31.06 33.58L30.78 33.4L30.51 33.2L30.27 32.99L30.04 32.76L29.85 32.52L29.67 32.27L29.52 32.01L29.39 31.75L29.29 31.49L29.21 31.23L29.15 30.96L29.12 30.7L29.1 30.45L29.11 30.2L29.14 29.96L29.19 29.73L29.25 29.52L29.33 29.31L29.43 29.12L29.54 28.94L29.66 28.78L29.79 28.64L29.93 28.51L30.07 28.4L30.22 28.31L30.37 28.23L30.53 28.18L30.68 28.14L30.83 28.11L30.98 28.11L31.12 28.12L31.26 28.14L31.39 28.18L31.51 28.23L31.61 28.3';
const DS_SPIRAL_SMALL = 'M32 20L32.62 20.15L33.21 20.35L33.78 20.59L34.33 20.86L34.84 21.16L35.33 21.5L35.78 21.87L36.19 22.26L36.57 22.68L36.92 23.11L37.22 23.57L37.49 24.03L37.72 24.51L37.91 24.99L38.06 25.48L38.17 25.97L38.24 26.45L38.28 26.93L38.28 27.41L38.24 27.87L38.17 28.32L38.07 28.76L37.94 29.18L37.78 29.58L37.6 29.96L37.39 30.31L37.16 30.64L36.91 30.95L36.64 31.23L36.36 31.48L36.06 31.7L35.76 31.9L35.45 32.06L35.14 32.2L34.82 32.31L34.5 32.39L34.19 32.44L33.88 32.47L33.58 32.47L33.29 32.45L33.01 32.4L32.74 32.34L32.49 32.25L32.25 32.14L32.03 32.02L31.83 31.88L31.64 31.73L31.48 31.57L31.34 31.4L31.22 31.22L31.12 31.04L31.04 30.85L30.98 30.67L30.95 30.49L30.93 30.31L30.93 30.13L30.95 29.97L30.99 29.81L31.05 29.66L31.12 29.52L31.2 29.4L31.3 29.29L31.41 29.2L31.52 29.13L31.65 29.07';
export function DrSpinMark({ size = 36, title }: { size?: number; title?: string }) {
  return <svg className="sc-drspin-mark" width={size} height={size} viewBox="0 0 64 64" role={title ? 'img' : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
    <circle cx="32" cy="32" r="32" fill="var(--sc-drspin, #3b82f6)" />
    <g fill="none" stroke="#fff" strokeWidth={size <= 20 ? 6 : 5} strokeLinecap="round" strokeLinejoin="round">
      <path d={DS_BUBBLE} /><path className="sc-drspin-mark__spiral" d={size <= 20 ? DS_SPIRAL_SMALL : DS_SPIRAL} /></g>
  </svg>;
}

export function Avatar({ name, ai = false, size }: { name: string; ai?: boolean; size?: number }) {
  let hue = 0; for (const c of name) hue = (hue * 31 + c.charCodeAt(0)) % 360;
  const style = { ['--hue' as string]: hue, ...(size ? { width: size, height: size } : {}) };
  return <span className="sc-social-avatar" data-ai={ai || undefined} aria-hidden="true" style={style}>{ai ? <DrSpinMark size={size ?? 36} /> : name.replace('@', '').charAt(0).toUpperCase()}</span>;
}
