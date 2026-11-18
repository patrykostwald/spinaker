import type { Bbox, Dokladnosc, Wpis } from './typy';
import { powiatOKodzie } from './slownik';

/**
 * Nazwy i przybliżone prostokąty województw (kody TERYT, 2 cyfry). Prostokąty służą tylko do przybliżenia widoku mapy
 * i do filtra wpisów bez kodu TERYT, które mają punkt (np. wstrząs); to nie są granice administracyjne.
 * Nazwy powiatów pochodzą ze słownika (slownik.ts, plik public/teraz/teryt-powiaty.json). Kod spoza słownika
 * pokazujemy jako „powiat o kodzie 1899”, bez zgadywania nazwy. Granice powiatów (PRG) dostarcza osobne zlecenie.
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

export const wojewodztwoOKodzie = (kod: string): Wojewodztwo | undefined => WOJEWODZTWA.find(w => w.kod === kod.slice(0, 2));

/** „powiat przemyski (podkarpackie)”, „miasto Tarnów (małopolskie)”, „województwo lubelskie”, „gmina o kodzie 1814011 (podkarpackie)”. */
export function nazwaObszaru(kod: string): string {
  const woj = wojewodztwoOKodzie(kod)?.nazwa;
  if (kod.length === 2) return woj ? `województwo ${woj}` : `obszar o kodzie ${kod}`;
  const w = woj ? ` (${woj})` : '';
  if (kod.length === 4) {
    const p = powiatOKodzie(kod);
    if (!p) return `powiat o kodzie ${kod}${w}`;
    return p.miasto ? `miasto ${p.nazwa}${w}` : `powiat ${p.nazwa}${w}`;
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

/** Linia z nazwą województwa w dowolnym przypadku („lubelskiego”), nie powiatu („lubelski”). */
const KONCOWKI_WOJ = /(?:ie|iego|iem|ich)$/;
/** Kod województwa (2 cyfry), jeśli cała linia jest jego nazwą („lubelskiego”, „woj. lubelskie”); inaczej null. */
export const kodWojewodztwaZNazwy = (linia: string): string | null => {
  const l = linia.trim().toLowerCase().replace(/^woj(?:\.|ewództwo)?\s+/, '');
  if (!KONCOWKI_WOJ.test(l)) return null;
  return WOJEWODZTWA.find(w => l.replace(KONCOWKI_WOJ, '') === w.nazwa.replace(/ie$/, ''))?.kod ?? null;
};

export type TypJednostki = 'powiat' | 'gmina' | 'miasto';
/** Jednostka wymieniona przez źródło: `woj` to kod województwa, pod które źródło ją podpisuje (null: źródło tego nie wiąże). */
export interface JednostkaZMiejsca { woj: string | null; typ: TypJednostki; nazwa: string }

/**
 * Rozbiera pole `miejsce` (po jednej jednostce w linii; format parsera RCB, recenzja PR #38 R38b P1-1):
 * „lubelskie: świdnicki” (powiat w województwie), „dolnośląskie: gmina Żarów”, „miasto Warszawa”, „Chełm” (bez województwa:
 * starsze wpisy albo źródło niczego nie przypisało). Same nazwy województw („lubelskiego”) nie są jednostkami.
 */
export function rozbierzMiejsce(miejsce: string | undefined): JednostkaZMiejsca[] {
  const wynik: JednostkaZMiejsca[] = [];
  for (const surowa of (miejsce ?? '').split(/\r?\n/)) {
    let linia = surowa.trim();
    if (!linia || kodWojewodztwaZNazwy(linia)) continue;
    let woj: string | null = null;
    const dwukropek = linia.indexOf(':');
    if (dwukropek > 0) {
      woj = kodWojewodztwaZNazwy(linia.slice(0, dwukropek));
      if (woj) linia = linia.slice(dwukropek + 1).trim();
    }
    let typ: TypJednostki = 'powiat';
    const przedrostek = /^(gmin(?:a|y|ie|ę)|miast(?:o|a|em))\s+(?=\S)/i.exec(linia);
    if (przedrostek) {
      typ = przedrostek[1].toLowerCase().startsWith('gmin') ? 'gmina' : 'miasto';
      linia = linia.slice(przedrostek[0].length);
    }
    if (linia) wynik.push({ woj, typ, nazwa: linia });
  }
  return wynik;
}

/** Jednostki wymienione przez źródło w polu `miejsce`, bez nazw województw; przy kilku województwach z dopiskiem („świdnicki (lubelskie)”). */
export const jednostkiZMiejsca = (miejsce: string | undefined): string[] => {
  const jednostki = rozbierzMiejsce(miejsce);
  const wiele = new Set(jednostki.map(j => j.woj).filter(Boolean)).size > 1;
  const nazwaWoj = (kod: string | null) => WOJEWODZTWA.find(w => w.kod === kod)?.nazwa;
  return [...new Set(jednostki.map(j => {
    const tekst = j.typ === 'powiat' ? j.nazwa : `${j.typ === 'gmina' ? 'gmina' : 'miasto'} ${j.nazwa}`;
    return wiele && j.woj ? `${tekst} (${nazwaWoj(j.woj)})` : tekst;
  }))];
};

/**
 * Opis miejsca wpisu do karty: „dotyczy: powiat przemyski (podkarpackie), powiat lubaczowski (podkarpackie)”. Przy zasięgu
 * przybliżonym kod nie jest zasięgiem: „w obrębie: województwo lubelskie; źródło wymienia: włodawski, Chełm…” (P1-2).
 */
export function opisMiejsca(wpis: Pick<Wpis, 'teryt' | 'dokladnosc' | 'szerokosc' | 'dlugosc' | 'bbox'> & Partial<Pick<Wpis, 'zasieg' | 'miejsce'>>): string {
  const obszary = nazwyObszarow(wpis.teryt);
  if (obszary.length && wpis.zasieg === 'przyblizony') {
    const lista = jednostkiZMiejsca(wpis.miejsce);
    return `w obrębie: ${obszary.join(', ')}; ${lista.length ? `źródło wymienia: ${lista.join(', ')}` : 'dokładnego zasięgu źródło nie podaje'}`;
  }
  if (obszary.length) return `dotyczy: ${obszary.join(', ')}`;
  if (wpis.szerokosc !== null && wpis.dlugosc !== null) return 'dotyczy: punkt na mapie (położenie przybliżone)';
  if (wpis.bbox) return 'dotyczy: prostokątny obszar na mapie';
  if (wpis.dokladnosc === 'kraj') return 'dotyczy: całego kraju';
  return 'miejsce nieznane';
}

export function wBbox(lon: number, lat: number, b: Bbox): boolean {
  return lon >= b[0] && lon <= b[2] && lat >= b[1] && lat <= b[3];
}
