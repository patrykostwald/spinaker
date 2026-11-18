import type { Okres } from './typy';
import { OKRES_DOMYSLNY, OKRESY } from './warstwy';
import { WOJEWODZTWA } from './teryt';

/**
 * Stan widoku w adresie URL (udostępnianie): warstwy (lista włączonych), okres, woj (kod TERYT), wpis (id), widok, probne.
 * Moduł jest czysty: używa go serwer (początkowy stan z searchParams) i przeglądarka (zapis przez history.replaceState).
 */
export interface Parametry {
  /** null = wszystkie aktywne warstwy włączone (brak parametru). */
  warstwy: string[] | null;
  okres: Okres;
  woj: string | null;
  wpis: number | null;
  widok: 'mapa' | 'lista';
  probne: boolean;
}

export const PARAMETRY_DOMYSLNE: Parametry = { warstwy: null, okres: OKRES_DOMYSLNY, woj: null, wpis: null, widok: 'mapa', probne: false };

type Wejscie = Record<string, string | string[] | undefined> | URLSearchParams;

const pierwszy = (w: Wejscie, klucz: string): string | undefined => {
  if (w instanceof URLSearchParams) return w.get(klucz) ?? undefined;
  const v = w[klucz];
  return Array.isArray(v) ? v[0] : v;
};

const KOD_WARSTWY = /^[a-z][a-z_]{1,24}$/;

export function parsuj(wejscie: Wejscie): Parametry {
  const warstwyTekst = pierwszy(wejscie, 'warstwy');
  const warstwy = warstwyTekst === undefined ? null
    : [...new Set(warstwyTekst.split(',').map(s => s.trim()).filter(s => KOD_WARSTWY.test(s)))];
  const okresTekst = pierwszy(wejscie, 'okres');
  const okres = OKRESY.find(o => o.id === okresTekst)?.id ?? OKRES_DOMYSLNY;
  const wojTekst = pierwszy(wejscie, 'woj');
  const woj = WOJEWODZTWA.some(w => w.kod === wojTekst) ? wojTekst ?? null : null;
  const wpisTekst = pierwszy(wejscie, 'wpis');
  const wpis = wpisTekst && /^[0-9]{1,12}$/.test(wpisTekst) ? Number(wpisTekst) : null;
  const widok = pierwszy(wejscie, 'widok') === 'lista' ? 'lista' : 'mapa';
  const probneTekst = pierwszy(wejscie, 'probne');
  return { warstwy, okres, woj, wpis, widok, probne: probneTekst === '1' || probneTekst === 'true' };
}

/** Nakłada parametry widoku na istniejący ciąg zapytania (inne parametry zostają); wartości domyślne znikają z adresu. */
export function zbudujZapytanie(p: Parametry, obecne: string = ''): string {
  const q = new URLSearchParams(obecne);
  for (const k of ['warstwy', 'okres', 'woj', 'wpis', 'widok', 'probne']) q.delete(k);
  if (p.warstwy !== null) q.set('warstwy', p.warstwy.join(','));
  if (p.okres !== OKRES_DOMYSLNY) q.set('okres', p.okres);
  if (p.woj) q.set('woj', p.woj);
  if (p.wpis !== null) q.set('wpis', String(p.wpis));
  if (p.widok === 'lista') q.set('widok', 'lista');
  if (p.probne) q.set('probne', '1');
  const tekst = q.toString();
  return tekst ? `?${tekst}` : '';
}
