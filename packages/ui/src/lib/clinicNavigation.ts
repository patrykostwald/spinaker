const DATABASE = "/klinika/diagnozy";
const PREFIX = "clinic-results:";

/** Only a local database URL can be used as the return destination. */
export function clinicResultsUrl(value: string | null): string {
  return value && (value === DATABASE || value.startsWith(`${DATABASE}?`)) ? value : DATABASE;
}

export function rememberClinicResults(url: string, pages: number) {
  try { sessionStorage.setItem(PREFIX + url, JSON.stringify({ top: window.scrollY, pages })); } catch {}
}

export function readClinicResults(url: string): { top: number; pages: number } | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(PREFIX + url) || "null");
    return value && Number.isFinite(value.top) && value.top >= 0 && Number.isInteger(value.pages) && value.pages > 0 ? value : null;
  } catch { return null; }
}

export function clearClinicResults(url: string) {
  try { sessionStorage.removeItem(PREFIX + url); } catch {}
}
