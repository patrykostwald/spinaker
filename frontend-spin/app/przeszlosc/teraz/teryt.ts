import type { Bbox, Dokladnosc, Wpis } from './typy';

/**
 * Nazwy i przybliżone prostokąty województw (kody TERYT, 2 cyfry). Prostokąty służą tylko do przybliżenia widoku mapy
 * i do filtra wpisów bez kodu TERYT, które mają punkt (np. wstrząs); to nie są granice administracyjne.
 * Granice powiatów (PRG) i pełną listę nazw powiatów dostarcza później Z3/Z6b; do tego czasu nieznany powiat
 * pokazujemy jako „powiat o kodzie 1814”, bez zgadywania nazwy.
 */
export interface Wojewodztwo { kod: string; nazwa: string; bbox: Bbox }

export const WOJEWODZTWA: Wojewodztwo[] = [
  { kod: '02', nazwa: 'dolnośląskie', bbox: [14.82, 49.97, 17.78, 51.8] },
  { kod: '04', nazwa: 'kujawsko-pomorskie', bbox: [17.18, 52.35, 19.65, 53.82] },
  { kod: '06', nazwa: 'lubelskie', bbox: [21.6, 50.25, 24.15, 52.35] },
  { kod: '08', nazwa: 'lubuskie', bbox: [14.55, 51.35, 16.35, 53.18] },
  { kod: '10', nazwa: 'łódzkie', bbox: [17.95, 50.82, 20.6, 52.4] },
  { kod: '12', nazwa: 'małopolskie', bbox: [18.95, 49.07, 21.45, 50.55] },
  { kod: '14', nazwa: 'mazowieckie', bbox: [19.25, 51.0, 23.15, 53.52] },
  { kod: '16', nazwa: 'opolskie', bbox: [16.9, 49.95, 18.7, 51.15] },
  { kod: '18', nazwa: 'podkarpackie', bbox: [21.1, 48.98, 23.55, 50.85] },
  { kod: '20', nazwa: 'podlaskie', bbox: [21.6, 52.25, 24.15, 54.42] },
  { kod: '22', nazwa: 'pomorskie', bbox: [16.65, 53.45, 19.55, 54.85] },
  { kod: '24', nazwa: 'śląskie', bbox: [18.05, 49.4, 19.95, 51.1] },
  { kod: '26', nazwa: 'świętokrzyskie', bbox: [19.75, 50.15, 21.85, 51.2] },
  { kod: '28', nazwa: 'warmińsko-mazurskie', bbox: [19.2, 53.3, 22.9, 54.45] },
  { kod: '30', nazwa: 'wielkopolskie', bbox: [15.75, 51.25, 19.15, 53.55] },
  { kod: '32', nazwa: 'zachodniopomorskie', bbox: [14.12, 52.55, 16.95, 54.55] },
];

/** Prostokąt Polski do widoku startowego. */
export const POLSKA_BBOX: Bbox = [14.0, 48.9, 24.2, 54.9];

/** Powiaty używane w danych próbnych; reszta po kodzie (patrz wyżej). */
const POWIATY: Record<string, string> = {
  '0602': 'biłgorajski', '0604': 'hrubieszowski', '0620': 'zamojski', '0663': 'm. Lublin',
  '1261': 'm. Kraków', '1263': 'm. Tarnów', '1465': 'm.st. Warszawa',
  '1804': 'jarosławski', '1810': 'lubaczowski', '1814': 'przemyski', '1863': 'm. Rzeszów',
};

export const wojewodztwoOKodzie = (kod: string): Wojewodztwo | undefined => WOJEWODZTWA.find(w => w.kod === kod.slice(0, 2));

/** „powiat przemyski (podkarpackie)”, „województwo lubelskie”, „gmina o kodzie 1814011 (podkarpackie)”. */
export function nazwaObszaru(kod: string): string {
  const woj = wojewodztwoOKodzie(kod)?.nazwa;
  if (kod.length === 2) return woj ? `województwo ${woj}` : `obszar o kodzie ${kod}`;
  const w = woj ? ` (${woj})` : '';
  if (kod.length === 4) {
    const nazwa = POWIATY[kod];
    return nazwa ? `powiat ${nazwa}${w}` : `powiat o kodzie ${kod}${w}`;
  }
  return `gmina o kodzie ${kod}${w}`;
}

export const nazwyObszarow = (kody: string[]): string[] => [...new Set(kody)].sort().map(nazwaObszaru);

const DOKLADNOSC: Record<Dokladnosc, string> = {
  punkt: 'punkt na mapie',
  gmina: 'gmina',
  powiat: 'powiat',
  wojewodztwo: 'województwo',
  kraj: 'cały kraj',
  brak: 'brak danych o miejscu',
};
export const etykietaDokladnosci = (d: Dokladnosc): string => DOKLADNOSC[d] ?? DOKLADNOSC.brak;

/** Opis miejsca wpisu do karty: „dotyczy: powiat przemyski (podkarpackie), powiat lubaczowski (podkarpackie)”. */
export function opisMiejsca(wpis: Pick<Wpis, 'teryt' | 'dokladnosc' | 'szerokosc' | 'dlugosc' | 'bbox'>): string {
  const obszary = nazwyObszarow(wpis.teryt);
  if (obszary.length) return `dotyczy: ${obszary.join(', ')}`;
  if (wpis.szerokosc !== null && wpis.dlugosc !== null) return 'dotyczy: punkt na mapie (położenie przybliżone)';
  if (wpis.bbox) return 'dotyczy: prostokątny obszar na mapie';
  if (wpis.dokladnosc === 'kraj') return 'dotyczy: całego kraju';
  return 'miejsce nieznane';
}

export function wBbox(lon: number, lat: number, b: Bbox): boolean {
  return lon >= b[0] && lon <= b[2] && lat >= b[1] && lat <= b[3];
}
