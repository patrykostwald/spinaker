import type { ZrodloPubliczne } from '../zrodla';
import { probneWarstwy } from './index';

/**
 * DANE PRZYKŁADOWE źródeł trybu próbnego (?probne=1): ten sam format co GET /api/teraz/zrodla/. Slugi, nazwy i warstwy
 * pochodzą z probneWarstwy (jedno źródło prawdy), rodzaje łącza i kody błędów są zmyślone na potrzeby podglądu.
 * Pokrywają wszystkie stany: działa, luka, błąd HTTP, dostęp wstrzymany i źródło bez żadnego sukcesu.
 */
const MIN = 60_000;
const iso = (teraz: number, minutTemu: number) => new Date(teraz - minutTemu * MIN).toISOString();

// rodzaje jak w backend/teraz/zrodla/rejestr.py (RODZAJ_LACZA)
const RODZAJE: Record<string, string> = {
  'rcb-gov-pl': 'scraping', 'imgw-meteo': 'api', 'imgw-hydro': 'api', 'gios-powietrze': 'api',
  'nasa-firms': 'api', emsc: 'websocket', 'cert-polska': 'rss',
};
/** Przykłady wyjątków: kod błędu (źródło z błędem ma też lukę, gdy ostatni sukces jest stary). */
const BLEDY: Record<string, string> = { 'imgw-hydro': 'blad_http', 'cert-polska': 'dostep_wstrzymany' };

export function probneZrodla(teraz: number = Date.now()): ZrodloPubliczne[] {
  const zrodla: ZrodloPubliczne[] = [];
  for (const w of probneWarstwy(teraz)) {
    for (const z of w.zrodla) {
      const wstrzymane = BLEDY[z.slug] === 'dostep_wstrzymany';
      zrodla.push({
        slug: z.slug, nazwa: z.nazwa, instytucja: z.instytucja, warstwa: w.warstwa, atrybucja: '',
        rodzaj_lacza: RODZAJE[z.slug] ?? '', czestotliwosc_s: z.czestotliwosc_s,
        // źródło wstrzymane: ostatni sukces sprzed 3 dni (pokazuje „od 17 listopada”, nie „od dziś”)
        ostatni_sukces_at: wstrzymane ? iso(teraz, 3 * 24 * 60) : z.ostatni_sukces_at,
        ostatni_blad: BLEDY[z.slug] ?? null,
        luka: z.luka || wstrzymane,
      });
    }
  }
  return zrodla;
}
