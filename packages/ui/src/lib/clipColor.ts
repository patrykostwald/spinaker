/**
 * Kolor połączenia (spinki) z głosów (właściciel 4.10). Autor zawsze daje swoje ✓ (jeden głos), a inni czytelnicy
 * weryfikują go ✓ ? ✕. Kolor zjeżdża płynnie po skali zielony -> żółty -> czerwony według średniej
 * (✓ = 1, ? = 0,5, ✕ = 0), a nasycenie rośnie z liczbą głosów innych osób: sam głos autora to blada zieleń
 * („autor tak twierdzi”), pełny kolor dopiero po kilku ocenach. Ta sama zasada dla czytelników i Dr. Spina.
 */
type Counts = { positive: number; doubt: number; negative: number };

const GREEN = [0x4e, 0xd1, 0x8a], YELLOW = [0xf2, 0xb4, 0x41], RED = [0xff, 0x6b, 0x6b];
const FULL_AT = 6;

const lerp = (a: number[], b: number[], t: number) => a.map((v, i) => Math.round(v + (b[i] - v) * t));

/** Średnia ocena 0-1 z głosem autora oraz siła 0-1 (ile głosów innych osób). */
export function clipScore(counts?: Counts | null) {
  const c = counts ?? { positive: 0, doubt: 0, negative: 0 };
  const others = c.positive + c.doubt + c.negative;
  const value = (1 + c.positive + 0.5 * c.doubt) / (1 + others);
  return { value, strength: Math.min(1, others / FULL_AT), others };
}

/** Kolor CSS połączenia: płynna skala i krycie od 0,35 (sam autor) do 1 (pełna weryfikacja). */
export function clipColor(counts?: Counts | null) {
  const { value, strength } = clipScore(counts);
  const rgb = value >= .5 ? lerp(YELLOW, GREEN, (value - .5) * 2) : lerp(RED, YELLOW, value * 2);
  const alpha = .35 + .65 * strength;
  return `rgb(${rgb[0]} ${rgb[1]} ${rgb[2]} / ${alpha.toFixed(2)})`;
}

/** Delikatny odcień płytki z ocen czytelników (bez głosu autora); null, gdy nikt nie ocenił (właściciel 4.10). */
export function reactionTint(counts?: Counts | null) {
  const c = counts ?? { positive: 0, doubt: 0, negative: 0 };
  const n = c.positive + c.doubt + c.negative;
  if (!n) return null;
  const value = (c.positive + .5 * c.doubt) / n;
  const rgb = value >= .5 ? lerp(YELLOW, GREEN, (value - .5) * 2) : lerp(RED, YELLOW, value * 2);
  return `rgb(${rgb[0]} ${rgb[1]} ${rgb[2]})`;
}

/** Odcień według siły spinu: słaby zielony, średni niebieski, silny czerwony (jak w całym serwisie). */
export function spinTint(intensity?: number | null) {
  if (intensity == null) return null;
  return intensity >= 70 ? 'var(--sc-spin-hi)' : intensity >= 40 ? 'var(--sc-spin-mid)' : 'var(--sc-spin-lo)';
}
