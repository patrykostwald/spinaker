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
    const linia = surowa.trim();
    if (!linia || jestZnacznikiem(linia) || kodWojewodztwaZNazwy(linia)) continue;
    const jednostka = rozbierzLinie(linia);
    if (jednostka) wynik.push(jednostka);
  }
  return wynik;
}

/** Jedna linia jednostki („lubelskie: świdnicki”, „gmina Żarów”) albo null, gdy po zdjęciu przedrostków nic nie zostaje. */
function rozbierzLinie(surowa: string): JednostkaZMiejsca | null {
  let linia = surowa.trim();
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
  return linia ? { woj, typ, nazwa: linia } : null;
}

/**
 * Znaczniki parsera RCB w `miejsce` (R38d, P1-1): „wyłączone: lubelskie: miasto Lublin” to jednostka, którą komunikat wyłącza
 * (nie jest objęta alertem), „wyłączone: nieokreślone” to wyłączenie, którego parser nie umiał wskazać, a „nieustalone: …” to lista
 * jednostek z elementem, który nie był nazwą (lista niepełna). Zasada konserwatywna: przy znaczniku front nie mówi „wymieniony”
 * (wyłączenia) ani „nie ma na liście” (wyłączenia i lista niepełna), najwyżej „możliwe”.
 */
const PREFIKS_WYLACZONE = 'wyłączone:';
const PREFIKS_NIEUSTALONE = 'nieustalone:';
const PREFIKS_ZAKRES = 'zakres:';
const jestZnacznikiem = (linia: string): boolean =>
  linia.startsWith(PREFIKS_WYLACZONE) || linia.startsWith(PREFIKS_NIEUSTALONE) || linia.startsWith(PREFIKS_ZAKRES);

/**
 * Zakres alertu w jednym województwie (parser RCB v6, R38d zlecenie Z6P6): `cale` (całe województwo), `czesc` (część bez wskazania
 * jednostek: „w części woj.”, „na południu woj.”), `lista` (źródło wymienia jednostki tego województwa). Linia: „zakres: lubelskie: lista”.
 * Kilka różnych linii dla jednego województwa daje `czesc`. Brak linii (wpis starszy niż parser v6): brak wpisu w mapie, wtedy
 * działa dawna heurystyka.
 */
export type RodzajZakresu = 'cale' | 'czesc' | 'lista' | 'lista_otwarta';
const ZAKRES_LINIA = /^zakres:\s*([^:]+?)\s*:\s*(cale|czesc|lista|lista_otwarta)$/;

export function zakresyWojewodztw(miejsce: string | undefined): Map<string, RodzajZakresu> {
  const rodzaje = new Map<string, Set<RodzajZakresu>>();
  for (const surowa of (miejsce ?? '').split(/\r?\n/)) {
    const m = ZAKRES_LINIA.exec(surowa.trim());
    const woj = m ? kodWojewodztwaZNazwy(m[1]) : null;
    if (!m || !woj) continue;
    rodzaje.set(woj, (rodzaje.get(woj) ?? new Set()).add(m[2] as RodzajZakresu));
  }
  return new Map([...rodzaje].map(([woj, r]): [string, RodzajZakresu] => [woj, r.size === 1 ? [...r][0] : 'czesc']));
}

export interface ZnacznikiMiejsca { wylaczone: JednostkaZMiejsca[]; ogolne: boolean; nieustalone: boolean; nieustaloneWoj: Set<string> }

export function znacznikiMiejsca(miejsce: string | undefined): ZnacznikiMiejsca {
  const wynik: ZnacznikiMiejsca = { wylaczone: [], ogolne: false, nieustalone: false, nieustaloneWoj: new Set() };
  for (const surowa of (miejsce ?? '').split(/\r?\n/)) {
    const linia = surowa.trim();
    if (linia.startsWith(PREFIKS_NIEUSTALONE)) {
      // „nieustalone: lubelskie”: lista niepełna w tym województwie; „nieustalone: nazwy jednostek”: nie wiadomo w którym
      const woj = kodWojewodztwaZNazwy(linia.slice(PREFIKS_NIEUSTALONE.length));
      if (woj) wynik.nieustaloneWoj.add(woj);
      else wynik.nieustalone = true;
    } else if (linia.startsWith(PREFIKS_WYLACZONE)) {
      const reszta = linia.slice(PREFIKS_WYLACZONE.length).trim();
      const jednostka = !reszta || reszta === 'nieokreślone' || kodWojewodztwaZNazwy(reszta) ? null : rozbierzLinie(reszta);
      if (jednostka) wynik.wylaczone.push(jednostka);
      else wynik.ogolne = true;
    }
  }
  return wynik;
}

/** Komunikat zastrzega coś dla województwa `woj`: wyłączenie jednostki z tego województwa (albo bez województwa) albo wyłączenie ogólne. */
export const maWylaczenia = (z: ZnacznikiMiejsca, woj: string): boolean => z.ogolne || z.wylaczone.some(j => !j.woj || j.woj === woj);

/** Wyłączenia albo lista niepełna dla województwa `woj`: wtedy nie wolno uznać go za całe ani powiedzieć „nie ma na liście”. */
export const maZastrzezenia = (miejsce: string | undefined, woj: string): boolean => {
  const z = znacznikiMiejsca(miejsce);
  return z.nieustalone || z.nieustaloneWoj.has(woj) || maWylaczenia(z, woj);
};

/**
 * Województwo `kod` obejmuje komunikat w całości, choć zasięg wpisu jest przybliżony (R38c, P1): jego nazwa stoi w `miejsce`
 * bez żadnej jednostki, a jednostki wymienione obok należą do innych województw („lubelskiego” + „dolnośląskie: świdnicki”).
 * Jednostka bez województwa albo z tym województwem, brak jednostek (starsze wpisy, „część województwa”) i brak nazwy
 * województwa to nie jest dowód całości: zasięg zostaje przybliżony.
 */
export function calyRegionZMiejsca(miejsce: string | undefined, kod: string): boolean {
  const woj = kod.slice(0, 2);
  // wpis z parsera v6: o „całym” województwie decyduje jego własny zakres, nie to, co alert mówi o innych województwach
  const rodzaj = zakresyWojewodztw(miejsce).get(woj);
  if (rodzaj) return rodzaj === 'cale' && !maZastrzezenia(miejsce, woj);
  const linie = (miejsce ?? '').split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  if (!linie.some(l => kodWojewodztwaZNazwy(l) === woj)) return false;
  if (maZastrzezenia(miejsce, woj)) return false; // wyłączenia albo niepełna lista: to nie jest dowód całości (R38d)
  const jednostki = rozbierzMiejsce(miejsce);
  return jednostki.length > 0 && jednostki.every(j => j.woj !== null && j.woj !== woj);
}

/** Jednostki wymienione przez źródło w polu `miejsce`, bez nazw województw; przy kilku województwach z dopiskiem („świdnicki (lubelskie)”). */
export const jednostkiZMiejsca = (miejsce: string | undefined): string[] => {
  const jednostki = rozbierzMiejsce(miejsce);
  // województwa z podpisów jednostek i z samych nazw w miejsce: powiat obok całego innego województwa też dostaje dopisek (R38c)
  const nazwane = (miejsce ?? '').split(/\r?\n/).map(l => kodWojewodztwaZNazwy(l.trim()));
  const wiele = new Set([...jednostki.map(j => j.woj), ...nazwane].filter(Boolean)).size > 1;
  const nazwaWoj = (kod: string | null) => WOJEWODZTWA.find(w => w.kod === kod)?.nazwa;
  return [...new Set(jednostki.map(j => {
    const tekst = j.typ === 'powiat' ? j.nazwa : `${j.typ === 'gmina' ? 'gmina' : 'miasto'} ${j.nazwa}`;
    return wiele && j.woj ? `${tekst} (${nazwaWoj(j.woj)})` : tekst;
  }))];
};

/** Dopisek do opisu miejsca: jednostki wyłączone w komunikacie, wyłączenie bez wskazanej jednostki, niepełna lista (R38d, P1-1). */
function opisZnacznikow(miejsce: string | undefined): string {
  const { wylaczone, ogolne, nieustalone, nieustaloneWoj } = znacznikiMiejsca(miejsce);
  // Z6P8 (R38g): nie wymieniamy wyłączonych jednostek z nazwy (parser mógł je źle przypisać), tylko odsyłamy do treści komunikatu
  return [
    ogolne || wylaczone.length ? '; komunikat zawiera wyłączenia: sprawdź jego treść' : '',
    nieustalone || nieustaloneWoj.size ? '; lista jednostek może być niepełna' : '',
  ].join('');
}

/**
 * Opis miejsca wpisu do karty: „dotyczy: powiat przemyski (podkarpackie), powiat lubaczowski (podkarpackie)”. Przy zasięgu
 * przybliżonym kod nie jest zasięgiem: „w obrębie: województwo lubelskie; źródło wymienia: włodawski, Chełm…” (P1-2).
 */
export function opisMiejsca(wpis: Pick<Wpis, 'teryt' | 'dokladnosc' | 'szerokosc' | 'dlugosc' | 'bbox'> & Partial<Pick<Wpis, 'zasieg' | 'miejsce'>>): string {
  const obszary = nazwyObszarow(wpis.teryt);
  if (obszary.length && wpis.zasieg === 'przyblizony') {
    const lista = jednostkiZMiejsca(wpis.miejsce);
    // województwo podane bez jednostek obok jednostek z innych województw to zasięg całego województwa (R38c, P1)
    const cale = [...new Set(wpis.teryt.map(k => k.slice(0, 2)))].filter(k => calyRegionZMiejsca(wpis.miejsce, k)).map(nazwaObszaru);
    const calosc = cale.length ? `całe: ${cale.join(', ')}; ` : '';
    // część województwa bez wskazania jednostek (parser v6): nie „całe” i nie „nie ma na liście”
    const czesci = [...zakresyWojewodztw(wpis.miejsce)].filter(([, rodzaj]) => rodzaj === 'czesc').map(([woj]) => nazwaObszaru(woj));
    const czesc = czesci.length ? `część: ${czesci.join(', ')}; ` : '';
    const bazowy = `w obrębie: ${obszary.join(', ')}; ${calosc}${czesc}${lista.length ? `źródło wymienia: ${lista.join(', ')}` : 'dokładnego zasięgu źródło nie podaje'}`;
    return bazowy + opisZnacznikow(wpis.miejsce);
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
