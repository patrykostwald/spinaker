/** Polska odmiana rzeczownika po liczebniku: [mianownik lp., dopełniacz lm. "few" (2-4), dopełniacz lm. "many"]. */
export type PluralForms = readonly [one: string, few: string, many: string];

export function pluralIndex(n: number): 0 | 1 | 2 {
  const abs = Math.abs(Math.trunc(n));
  if (abs === 1) return 0;
  const last = abs % 10;
  const lastTwo = abs % 100;
  if (last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return 1;
  return 2;
}

export function plural(n: number, forms: PluralForms): string {
  return forms[pluralIndex(n)];
}

/** "24 diagnozy" - liczba i poprawna forma. Liczba formatowana po polsku (spacja tysięcy). */
export function countPl(n: number, forms: PluralForms): string {
  return `${Number.isFinite(n) ? n.toLocaleString("pl-PL") : n} ${plural(n, forms)}`;
}

export const FORMS = {
  diagnosis: ["diagnoza", "diagnozy", "diagnoz"],
  entry: ["wpis", "wpisy", "wpisów"],
  material: ["materiał", "materiały", "materiałów"],
  source: ["źródło", "źródła", "źródeł"],
  vote: ["głosowanie", "głosowania", "głosowań"],
  day: ["dzień", "dni", "dni"],
  person: ["osoba", "osoby", "osób"],
  account: ["konto", "konta", "kont"],
  record: ["rekord", "rekordy", "rekordów"],
  box: ["box", "boxy", "boxów"],
  view: ["wyświetlenie", "wyświetlenia", "wyświetleń"],
} as const satisfies Record<string, PluralForms>;
