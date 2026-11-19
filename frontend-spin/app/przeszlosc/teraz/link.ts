/**
 * Odnośnik do oryginału u źródła pochodzi z zewnętrznego API, więc do `href` trafia tylko bezwzględny adres `http:` albo `https:`
 * z nazwą hosta. Adresy względne, `javascript:`, `data:` i inne schematy dają null (interfejs pokazuje wtedy brak odnośnika,
 * a nie martwy albo niebezpieczny link).
 */
export function adresZrodla(url: unknown): string | null {
  if (typeof url !== 'string') return null;
  const tekst = url.trim();
  if (!/^https?:\/\//i.test(tekst)) return null;
  try {
    const adres = new URL(tekst);
    return (adres.protocol === 'http:' || adres.protocol === 'https:') && adres.hostname ? adres.href : null;
  } catch {
    return null;
  }
}
