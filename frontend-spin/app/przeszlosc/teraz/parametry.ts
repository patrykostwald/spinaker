import type { Okres } from './typy';
import { KOLEJNOSC_WARSTW, OKRES_DOMYSLNY, OKRESY } from './warstwy';
import { WOJEWODZTWA } from './teryt';

/**
 * Stan widoku w adresie URL (udostępnianie): warstwy (lista włączonych), okres, woj (kod TERYT), wpis (id), widok
 * (mapa, lista, tabela, powiat), probne. Parametr `powiaty` („Mój powiat”) obsługuje powiaty.ts i nie jest tu zmieniany.
 * Moduł jest czysty: używa go serwer (początkowy stan z searchParams) i przeglądarka (zapis przez history.replaceState).
 */
export type Widok = 'mapa' | 'lista' | 'tabela' | 'powiat';
export const WIDOKI: Widok[] = ['mapa', 'lista', 'tabela', 'powiat'];

export interface Parametry {
  /** null = wszystkie aktywne warstwy włączone (brak parametru). */
  warstwy: string[] | null;
  okres: Okres;
  woj: string | null;
  wpis: number | null;
  widok: Widok;
  probne: boolean;
}

export const PARAMETRY_DOMYSLNE: Parametry = { warstwy: null, okres: OKRES_DOMYSLNY, woj: null, wpis: null, widok: 'mapa', probne: false };

type Wejscie = Record<string, string | string[] | undefined> | URLSearchParams;

const pierwszy = (w: Wejscie, klucz: string): string | undefined => {
  if (w instanceof URLSearchParams) return w.get(klucz) ?? undefined;
  const v = w[klucz];
  return Array.isArray(v) ? v[0] : v;
};

/**
 * Wspólna walidacja wartości widoku: ta sama dla adresu URL (parsuj) i dla pamięci przeglądarki (pamiec.ts).
 * Dozwolone są tylko znane kody warstw, okresy z listy i kody województw ze słownika; reszta jest odrzucana, nigdy nie trafia do adresu.
 */
export const KODY_WARSTW: ReadonlySet<string> = new Set(KOLEJNOSC_WARSTW);
export const poprawnyOkres = (x: unknown): x is Okres => OKRESY.some(o => o.id === x);
export const poprawneWojewodztwo = (x: unknown): x is string => typeof x === 'string' && WOJEWODZTWA.some(w => w.kod === x);

/** Tablica unikalnych dozwolonych kodów warstw; cokolwiek innego niż tablica daje null (czyli „wszystkie aktywne”). */
export function oczyscWarstwy(x: unknown): string[] | null {
  if (!Array.isArray(x)) return null;
  return [...new Set(x.filter((k): k is string => typeof k === 'string' && KODY_WARSTW.has(k.trim())).map(k => k.trim()))];
}

/** Wartość `warstwy=wszystkie`: jawnie „wszystkie aktywne” (link udostępniany nie zależy wtedy od pamięci odbiorcy). */
export const WSZYSTKIE_WARSTWY = 'wszystkie';
/** Wartość `woj=pl`: jawnie „cała Polska”. */
export const CALA_POLSKA = 'pl';

/**
 * Parametr `warstwy` z adresu: brak = null (decyduje pamięć), `wszystkie` = null, pusty tekst = jawnie żadna warstwa (pusta lista),
 * lista kodów = znane kody. Same nieznane kody to `bledne`: wtedy domyślne warstwy (null), a wybór nie trafia do pamięci.
 */
export function warstwyZAdresu(tekst: string | undefined): { warstwy: string[] | null; bledne: boolean } {
  if (tekst === undefined) return { warstwy: null, bledne: false };
  const surowe = tekst.split(',').map(k => k.trim()).filter(Boolean);
  if (!surowe.length) return { warstwy: [], bledne: false };
  if (surowe.length === 1 && surowe[0] === WSZYSTKIE_WARSTWY) return { warstwy: null, bledne: false };
  const czyste = oczyscWarstwy(surowe) ?? [];
  return czyste.length ? { warstwy: czyste, bledne: false } : { warstwy: null, bledne: true };
}

export function parsuj(wejscie: Wejscie): Parametry {
  const warstwyTekst = pierwszy(wejscie, 'warstwy');
  const { warstwy } = warstwyZAdresu(warstwyTekst);
  const okresTekst = pierwszy(wejscie, 'okres');
  const okres = poprawnyOkres(okresTekst) ? okresTekst : OKRES_DOMYSLNY;
  const wojTekst = pierwszy(wejscie, 'woj');
  const woj = poprawneWojewodztwo(wojTekst) ? wojTekst : null;
  const wpisTekst = pierwszy(wejscie, 'wpis');
  const wpis = wpisTekst && /^[0-9]{1,12}$/.test(wpisTekst) ? Number(wpisTekst) : null;
  const widok = WIDOKI.find(v => v === pierwszy(wejscie, 'widok')) ?? 'mapa';
  const probneTekst = pierwszy(wejscie, 'probne');
  return { warstwy, okres, woj, wpis, widok, probne: probneTekst === '1' || probneTekst === 'true' };
}

/**
 * Nakłada parametry widoku na istniejący ciąg zapytania (inne parametry zostają). Pasek adresu: wartości domyślne znikają.
 * `pelne` (link do udostępnienia): warstwy, okres i województwo zawsze jawnie, także domyślne („wszystkie”, „24h”, „pl”),
 * żeby zapamiętane ustawienia odbiorcy nie zmieniły tego, co zobaczy.
 */
export function zbudujZapytanie(p: Parametry, obecne: string = '', pelne: boolean = false): string {
  const q = new URLSearchParams(obecne);
  for (const k of ['warstwy', 'okres', 'woj', 'wpis', 'widok', 'probne']) q.delete(k);
  if (p.warstwy !== null) q.set('warstwy', p.warstwy.join(','));
  else if (pelne) q.set('warstwy', WSZYSTKIE_WARSTWY);
  if (pelne || p.okres !== OKRES_DOMYSLNY) q.set('okres', p.okres);
  if (p.woj) q.set('woj', p.woj);
  else if (pelne) q.set('woj', CALA_POLSKA);
  if (p.wpis !== null) q.set('wpis', String(p.wpis));
  if (p.widok !== 'mapa') q.set('widok', p.widok);
  if (p.probne) q.set('probne', '1');
  const tekst = q.toString();
  return tekst ? `?${tekst}` : '';
}
