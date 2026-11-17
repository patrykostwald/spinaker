/**
 * Opis okna czasu w Odstępstwach od klubu (runda person 1, 5.11.2026).
 * „90 dni” to okno do OSTATNIEGO głosowania w danych (backend/news/voting_anomalies.py: WINDOW_DAYS), a zakres pod nagłówkiem
 * to daty głosowań faktycznie policzonych. Gdy te dwa rozchodzą się o więcej niż GAP_DAYS, mówimy wprost, czego brakuje
 * w naszych danych (zasada portalu: „brak w naszych danych” z zakresem), zamiast zostawiać pozorną sprzeczność.
 */
export const WINDOW_DAYS = 90;
export const GAP_DAYS = 7;

export function windowNote(period: string, from: string | null | undefined, to: string | null | undefined, formatDay: (iso: string) => string): string | null {
  if (period !== '90d' || !from || !to) return null;
  const nominal = new Date(to);
  nominal.setUTCDate(nominal.getUTCDate() - WINDOW_DAYS);
  const first = new Date(from);
  if (first.getTime() - nominal.getTime() <= GAP_DAYS * 86400000) return null;
  return `Okno 90 dni sięga ${formatDay(nominal.toISOString())}, ale w zestawieniu są głosowania dopiero od ${formatDay(from)}; wcześniejszych w tym oknie brak w naszych danych.`;
}
