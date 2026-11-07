/**
 * Nastrój tła (właściciel 3.10): kropkowy gradient w tle płynnie przyjmuje kolory tego, co czytelnik ogląda.
 * Spinki: proporcje reakcji (✕ czerwony z lewej, ? żółty w środku, ✓ zielony z prawej). Diagnoza: siła spinu
 * (słaby zielony, średni niebieski, silny czerwony). Bez nastroju wracają kolory działu (html[data-view], kit.css).
 */
type Counts = { positive: number; doubt: number; negative: number };

const VARS = ['--sc-g1', '--sc-g2', '--sc-g3'] as const;
const mix = (color: string, share: number) => `color-mix(in srgb, ${color} ${Math.round(18 + 62 * share)}%, transparent)`;

function apply(values: [string, string, string] | null) {
  if (typeof document === 'undefined') return;
  const style = document.documentElement.style;
  VARS.forEach((name, index) => { if (values) style.setProperty(name, values[index]); else style.removeProperty(name); });
}

export function sumCounts(rows: (Counts | undefined)[] | undefined): Counts | null {
  const total = { positive: 0, doubt: 0, negative: 0 };
  (rows ?? []).forEach(row => { if (row) { total.positive += row.positive; total.doubt += row.doubt; total.negative += row.negative; } });
  return total.positive + total.doubt + total.negative ? total : null;
}

/** Nastrój z reakcji; null przywraca kolory działu. */
export function setReactionMood(counts: Counts | null) {
  if (!counts) { apply(null); return; }
  const all = counts.positive + counts.doubt + counts.negative;
  if (!all) { apply(null); return; }
  apply([mix('var(--sc-negative)', counts.negative / all), mix('var(--sc-warning)', counts.doubt / all), mix('var(--sc-positive)', counts.positive / all)]);
}

/** Nastrój z siły spinu 0-100. */
export function setSpinMood(intensity: number | null | undefined) {
  if (intensity == null) { apply(null); return; }
  const value = Math.max(0, Math.min(100, intensity)) / 100;
  apply([mix('var(--sc-spin-lo)', 1 - value), mix('var(--sc-spin-mid)', 1 - Math.abs(value - .5) * 2), mix('var(--sc-spin-hi)', value)]);
}
