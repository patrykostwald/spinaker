/**
 * Polska typografia w tekstach z serwera: jednoliterowe słowo (a, i, o, u, w, z) nie zostaje na końcu wiersza,
 * tylko przechodzi do następnego razem z kolejnym słowem (twarda spacja). Decyzja właściciela 1.10.2026.
 * Działa tylko na tekstach do wyświetlenia (GET); nie zmienia adresów ani tekstów bez spacji.
 */
const ORPHAN = /(^|[\s(„"«])([AaIiOoUuWwZz])\s+(?=\S)/g;

export function glueShortWords(text: string): string {
  // Dwa przebiegi: „i w domu” → oba słowa sklejone z następnym.
  return text.replace(ORPHAN, '$1$2 ').replace(ORPHAN, '$1$2 ');
}

export function typographize<T>(value: T): T {
  if (typeof value === 'string') return (/\s/.test(value) && !/^https?:\/\//.test(value) ? glueShortWords(value) : value) as T;
  if (Array.isArray(value)) return value.map(item => typographize(item)) as T;
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) out[key] = typographize(item);
    return out as T;
  }
  return value;
}
