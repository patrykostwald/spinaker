/**
 * Pasek "Ostatnio w bazie" (przeszłość.today, strona główna, 13.10.2026): funkcje czyste, bez Reacta i DOM.
 * Wejście: `latest[]` z GET /api/przeszlosc/start/ (te same pozycje co sekcja "Najnowsze w bazie"): tytuł, data (ISO, bez godziny),
 * rodzaj po polsku z backendu (Głosowanie, Druk, Interpelacja, Dokument...), adres źródła. Niczego nie dopisujemy: brak godziny = bez godziny,
 * brak adresu = bez odnośnika. Jedna miara dla wszystkich pozycji: sortowanie tylko po czasie, bez filtrów po obozie, bez ocen.
 * Testy: tests/126-przeszlosc-pasek-nowosci.test.cjs (ładowane przez transpileModule, dlatego bez importów).
 */

export type StartLatest = { title: string; date: string | null; kind: string; url: string };
export type TickItem = { key: string; kind: string; date: string | null; dateText: string; timeText: string; title: string; url: string | null; host: string };

/** Zakres paska: 3-6 najnowszych pozycji (mniej niż 3 = pasek ukryty, nie "zero"). */
export const TICK_MIN = 3;
export const TICK_MAX = 6;
/** Wartości domyślne czasu; w CSS tokeny --fx-ticker-interval / --fx-ticker-fade (komponent czyta je z getComputedStyle). */
export const TICK_INTERVAL_MS = 6000;
export const TICK_FADE_MS = 320;
export const TICK_LABEL = 'Ostatnio w bazie';
export const TICK_ANCHOR = 'najnowsze';

/** Adres z danych zewnętrznych: tylko http(s) albo ścieżka w serwisie (bez //); inaczej null. */
export function tickUrl(u: unknown): string | null {
  if (typeof u !== 'string') return null;
  const s = u.trim();
  if (/^https?:\/\/[^\s]+$/i.test(s)) return s;
  return /^\/(?!\/)[^\s]*$/.test(s) ? s : null;
}
export function tickHost(u?: string | null): string {
  try { return u && /^https?:/i.test(u) ? new URL(u).hostname.replace(/^(www|api)\./, '') : ''; } catch { return ''; }
}
/** "2026-10-13" albo "2026-10-13T06:29+00:00" -> "13.10.2026"; inne -> ''. */
export function tickDate(iso?: string | null): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '');
  return m ? `${m[3]}.${m[2]}.${m[1]}` : '';
}
/** Godzina tylko wtedy, gdy jest w danych ("...T06:29..."); sama data = ''. */
export function tickTime(iso?: string | null): string {
  const m = /^\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2})/.exec(iso ?? '');
  return m ? `${m[1]}:${m[2]}` : '';
}

/** Pozycje paska: tytuł niepusty, posortowane po czasie malejąco (stabilnie), bez duplikatów tytułu, najwyżej TICK_MAX. */
export function tickItems(latest?: StartLatest[] | null): TickItem[] {
  const seen = new Set<string>();
  const rows = (latest ?? []).map((r, i) => ({ r, i })).filter(({ r }) => r && typeof r.title === 'string' && r.title.trim());
  rows.sort((a, b) => String(b.r.date ?? '').localeCompare(String(a.r.date ?? '')) || a.i - b.i);
  const out: TickItem[] = [];
  for (const { r, i } of rows) {
    const title = r.title.replace(/\s+/g, ' ').trim();
    const k = title.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    const url = tickUrl(r.url);
    out.push({ key: `${i}-${r.date ?? ''}-${k.slice(0, 40)}`, kind: (r.kind ?? '').trim(), date: r.date ?? null, dateText: tickDate(r.date), timeText: tickTime(r.date), title, url, host: tickHost(url) });
    if (out.length === TICK_MAX) break;
  }
  return out;
}
export const tickVisible = (items: TickItem[]) => items.length >= TICK_MIN;

/** Następna / poprzednia pozycja w pętli. */
export const stepIndex = (i: number, n: number, dir = 1) => (n <= 0 ? 0 : (((i + dir) % n) + n) % n);

/** Stan paska: 'static' (reduced motion albo 1 pozycja: bez zegara), 'paused' (przycisk, najechanie, fokus, karta w tle), 'running'. */
export function tickState(o: { reduced: boolean; paused: boolean; hovered: boolean; focused: boolean; hidden: boolean; n: number }): 'static' | 'running' | 'paused' {
  if (o.reduced || o.n < 2) return 'static';
  if (o.paused || o.hovered || o.focused || o.hidden) return 'paused';
  return 'running';
}

/** Skrót tytułu do jednej linii PO CAŁYM SŁOWIE (reguła właściciela: nigdy w pół słowa), mierzony prawdziwym krojem (measure = szerokość
 *  tekstu w px, np. canvas measureText). null = cały tekst się mieści. Gdy nie mieści się nawet pierwsze słowo, tnie po znakach. */
export function fitWords(text: string, width: number, measure: (s: string) => number, ellipsis = '…'): string | null {
  if (!(width > 0) || measure(text) <= width) return null;
  const words = text.split(' ');
  let best = '';
  for (let i = 1; i <= words.length; i++) {
    const cand = words.slice(0, i).join(' ').replace(/[\s,;:.-]+$/, '') + ellipsis;
    if (measure(cand) <= width) best = cand; else break;
  }
  if (best) return best;
  let s = words[0];
  while (s.length > 1 && measure(s + ellipsis) > width) s = s.slice(0, -1);
  return s + ellipsis;
}

/** Wartość czasu z tokenu CSS ("6s", "6000ms", "6000", " 320ms ") -> ms; brak albo błąd -> wartość domyślna. */
export function readMs(value: string | null | undefined, fallback: number): number {
  const m = /^\s*([\d.]+)\s*(ms|s)?\s*$/i.exec(value ?? '');
  if (!m) return fallback;
  const v = Number(m[1]);
  if (!Number.isFinite(v) || v < 0) return fallback;
  return Math.round((m[2] ?? '').toLowerCase() === 's' ? v * 1000 : v);
}
