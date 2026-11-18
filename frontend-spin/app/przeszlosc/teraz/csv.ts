/**
 * Eksport do CSV po stronie przeglądarki. Separator: średnik (polski Excel), kodowanie UTF-8 z BOM (dodawany przy
 * tworzeniu pliku), końce wierszy CRLF. Komórki zaczynające się od znaku formuły dostają apostrof na początku,
 * żeby arkusz nie wykonał ich jako formuły (CSV injection).
 */
export const SEPARATOR_CSV = ';';

const ZNAKI_FORMULY = /^[=+\-@\t\r]/;

export function komorkaCsv(wartosc: string, separator: string = SEPARATOR_CSV): string {
  const tekst = ZNAKI_FORMULY.test(wartosc) ? `'${wartosc}` : wartosc;
  const trzebaCytowac = tekst.includes(separator) || tekst.includes('"') || tekst.includes('\n') || tekst.includes('\r');
  return trzebaCytowac ? `"${tekst.replace(/"/g, '""')}"` : tekst;
}

export function budujCsv(naglowki: readonly string[], wiersze: readonly (readonly string[])[], separator: string = SEPARATOR_CSV): string {
  const linia = (komorki: readonly string[]) => komorki.map(k => komorkaCsv(k, separator)).join(separator);
  return [linia(naglowki), ...wiersze.map(linia)].join('\r\n') + '\r\n';
}

const dwie = (n: number) => String(n).padStart(2, '0');

/** „teraz-komunikaty-2026-11-18-1432.csv” (czas z zegara przeglądarki, strefa lokalna). */
export function nazwaPlikuCsv(teraz: Date): string {
  return `teraz-komunikaty-${teraz.getFullYear()}-${dwie(teraz.getMonth() + 1)}-${dwie(teraz.getDate())}-${dwie(teraz.getHours())}${dwie(teraz.getMinutes())}.csv`;
}
