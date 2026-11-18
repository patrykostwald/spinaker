import type { Okres } from './typy';
import { oczyscWarstwy, poprawneWojewodztwo, poprawnyOkres } from './parametry';
import { oczyscKody } from './powiaty';

/**
 * Pamięć przeglądarki (localStorage): ostatnie ustawienia widoku. Odczyt jest walidowany tymi samymi regułami co parametry adresu
 * (parametry.ts): dozwolone kody warstw, okresy i województwa oraz poprawne kody powiatów. `null`, śmieci i obcy JSON dają pustą
 * pamięć, nigdy wyjątek. Adres URL ma pierwszeństwo przed pamięcią (decyduje TerazPage).
 */
export const KLUCZ_PAMIECI = 'przeszlosc.teraz.v1';

export interface Pamiec { warstwy?: string[] | null; okres?: Okres; woj?: string | null; powiaty?: string[] }

/** Zawartość localStorage → tylko poprawne pola. Czysta funkcja (testowana bez przeglądarki). */
export function parsujPamiec(surowy: string | null | undefined): Pamiec {
  let dane: unknown;
  try { dane = JSON.parse(surowy || '{}'); } catch { return {}; }
  if (typeof dane !== 'object' || dane === null || Array.isArray(dane)) return {};
  const x = dane as Record<string, unknown>;
  const wynik: Pamiec = {};
  if (x.warstwy === null) wynik.warstwy = null;
  else if (Array.isArray(x.warstwy)) {
    // pusta lista to świadomy wybór „żadna warstwa”; lista samych śmieci nie może po cichu wyłączyć wszystkiego
    const czyste = oczyscWarstwy(x.warstwy) ?? [];
    if (czyste.length || x.warstwy.length === 0) wynik.warstwy = czyste;
  }
  if (poprawnyOkres(x.okres)) wynik.okres = x.okres;
  if (x.woj === null) wynik.woj = null;
  else if (poprawneWojewodztwo(x.woj)) wynik.woj = x.woj;
  if (Array.isArray(x.powiaty)) wynik.powiaty = oczyscKody(x.powiaty);
  return wynik;
}

export const czytajPamiec = (): Pamiec => {
  try { return parsujPamiec(window.localStorage.getItem(KLUCZ_PAMIECI)); } catch { return {}; }
};

/** Zapis łączy się z tym, co już jest w pamięci (każda część widoku zapisuje tylko swoje pola); stare śmieci są przy okazji usuwane. */
export const zapiszPamiec = (p: Pamiec) => {
  try { window.localStorage.setItem(KLUCZ_PAMIECI, JSON.stringify({ ...czytajPamiec(), ...p })); } catch { /* tryb prywatny: bez pamięci */ }
};
