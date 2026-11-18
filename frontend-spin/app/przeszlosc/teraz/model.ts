import type { Bbox, KodWarstwy, LiniaStanu, Stan, StatusKlucz, Warstwa, WidokWpisu, Wpis, Zdarzenie, Zrodlo } from './typy';
import { metaStatusu, metaWarstwy, KOLEJNOSC_WARSTW } from './warstwy';
import { WOJEWODZTWA, wBbox } from './teryt';

/** Czysta logika widoku (bez Reacta i mapy), żeby dało się ją sprawdzić testami. */

/** Wpis → zdarzenie (przy kilku zdarzeniach wygrywa to z najświeższym wpisem); status tylko ze zdarzenia. */
export function zbudujWidoki(wpisy: Wpis[], zdarzenia: Zdarzenie[]): WidokWpisu[] {
  const poWpisie = new Map<number, Zdarzenie>();
  for (const z of zdarzenia) {
    for (const w of z.wpisy) {
      const stare = poWpisie.get(w.id);
      if (!stare || Date.parse(z.ostatni_wpis_at) > Date.parse(stare.ostatni_wpis_at)) poWpisie.set(w.id, z);
    }
  }
  return wpisy.map(wpis => {
    const zdarzenie = poWpisie.get(wpis.id) ?? null;
    const status: StatusKlucz = zdarzenie ? zdarzenie.status : 'brak';
    return { wpis, status, zdarzenie };
  });
}

const poprawnyPunkt = (w: Wpis): boolean =>
  w.szerokosc !== null && w.dlugosc !== null && Number.isFinite(w.szerokosc) && Number.isFinite(w.dlugosc)
  && Math.abs(w.szerokosc) <= 90 && Math.abs(w.dlugosc) <= 180;

export const maPunkt = (w: Wpis): boolean => poprawnyPunkt(w);
export const maObszar = (w: Wpis): boolean => !poprawnyPunkt(w) && Array.isArray(w.bbox) && w.bbox.length === 4 && w.bbox.every(Number.isFinite);
/** Wpis bez punktu i bez prostokąta: pokazujemy tylko na liście („dotyczy: powiat X”). */
export const bezPolozenia = (w: Wpis): boolean => !poprawnyPunkt(w) && !maObszar(w);

/** Filtr województwa: kod TERYT zaczyna się od kodu województwa; wpis bez TERYT ale z punktem lub prostokątem liczy się, gdy leży w przybliżonym prostokącie. */
export function zgodnyZRegionem(w: Wpis, woj: string | null): boolean {
  if (!woj) return true;
  if (w.teryt.length) return w.teryt.some(k => k.startsWith(woj));
  const region = WOJEWODZTWA.find(r => r.kod === woj);
  if (!region) return true;
  if (poprawnyPunkt(w)) return wBbox(w.dlugosc as number, w.szerokosc as number, region.bbox);
  if (maObszar(w)) {
    // prostokąt bez TERYT przypisujemy do województwa, w którym leży jego środek (przecięcia dałyby wpisy z sąsiednich województw)
    const b = w.bbox as Bbox;
    return wBbox((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, region.bbox);
  }
  return false;
}

export const aktywna = (w: Warstwa): boolean => w.zrodla.length > 0;

/** Warstwy w kolejności produktu; nieznane kody na końcu. */
export function posortujWarstwy(warstwy: Warstwa[]): Warstwa[] {
  const miejsce = (k: KodWarstwy) => { const i = KOLEJNOSC_WARSTW.indexOf(k); return i < 0 ? 999 : i; };
  return [...warstwy].sort((a, b) => miejsce(a.warstwa) - miejsce(b.warstwa));
}

export function nazwaZrodla(warstwy: Warstwa[] | undefined, slug: string): { nazwa: string; instytucja: string } {
  for (const w of warstwy ?? []) {
    const z: Zrodlo | undefined = w.zrodla.find(s => s.slug === slug);
    if (z) return { nazwa: z.nazwa, instytucja: z.instytucja };
  }
  return { nazwa: slug, instytucja: '' };
}

/** Które warstwy są włączone: null z URL i pamięci = wszystkie aktywne. */
export function wlaczoneWarstwy(wybor: string[] | null, warstwy: Warstwa[]): Set<string> {
  if (wybor === null) return new Set(warstwy.filter(aktywna).map(w => w.warstwa));
  return new Set(wybor);
}

export interface WierszStanu {
  warstwa: KodWarstwy;
  nazwa: string;
  aktywna: boolean;
  ostatniePobranie: string;
  komunikaty: string;
  komunikat: string;
}

export interface PodsumowanieStanu {
  informacja: string;
  wiersze: WierszStanu[];
  /** Warstwy ze źródłami, które mają luki albo błędy: tu pokazujemy zdanie z API. */
  ostrzezenia: WierszStanu[];
}

export function podsumujStan(stan: Stan | undefined, warstwy: Warstwa[] | undefined): PodsumowanieStanu | null {
  if (!stan) return null;
  const nazwy = new Map((warstwy ?? []).map(w => [w.warstwa, w]));
  const wiersze = stan.warstwy.map((l: LiniaStanu): WierszStanu => {
    const w = nazwy.get(l.warstwa);
    return {
      warstwa: l.warstwa,
      nazwa: w?.nazwa ?? metaWarstwy(l.warstwa).opis,
      aktywna: w ? aktywna(w) : true,
      ostatniePobranie: l.ostatnie_pobranie,
      komunikaty: l.komunikaty,
      komunikat: l.komunikat,
    };
  });
  const posortowane = [...wiersze].sort((a, b) => KOLEJNOSC_WARSTW.indexOf(a.warstwa) - KOLEJNOSC_WARSTW.indexOf(b.warstwa));
  return { informacja: stan.informacja, wiersze: posortowane, ostrzezenia: posortowane.filter(x => x.aktywna && x.komunikat) };
}

/** `ikona` to nazwa obrazu znacznika: ik-<kształt>-<kolor bez #> (rysowany na żądanie w Mapa.tsx). */
export interface CechaPunktu { id: number; kolor: string; ikona: string; warstwa: string; status: string; tytul: string }
export interface CechaObszaru { id: number; kolor: string; styl: string; warstwa: string; status: string }

type Punkt = { type: 'Feature'; properties: CechaPunktu; geometry: { type: 'Point'; coordinates: [number, number] } };
type Obszar = { type: 'Feature'; properties: CechaObszaru; geometry: { type: 'Polygon'; coordinates: [number, number][][] } };

export function prostokat(b: Bbox): [number, number][][] {
  const [z, p, w, n] = b;
  return [[[z, p], [w, p], [w, n], [z, n], [z, p]]];
}

/** Dane dla mapy: punkty (z kształtem statusu) i prostokąty obszarów (z obramowaniem statusu). */
export function naGeoJson(widoki: WidokWpisu[]): {
  punkty: { type: 'FeatureCollection'; features: Punkt[] };
  obszary: { type: 'FeatureCollection'; features: Obszar[] };
} {
  const punkty: Punkt[] = [];
  const obszary: Obszar[] = [];
  for (const { wpis, status } of widoki) {
    const kolor = metaWarstwy(wpis.warstwa).kolor;
    const st = metaStatusu(status);
    if (poprawnyPunkt(wpis)) {
      punkty.push({
        type: 'Feature',
        properties: { id: wpis.id, kolor, ikona: `ik-${st.ksztalt}-${kolor.replace('#', '')}`, warstwa: wpis.warstwa, status, tytul: wpis.tytul },
        geometry: { type: 'Point', coordinates: [wpis.dlugosc as number, wpis.szerokosc as number] },
      });
    } else if (maObszar(wpis)) {
      obszary.push({
        type: 'Feature',
        properties: { id: wpis.id, kolor, styl: st.obramowanie, warstwa: wpis.warstwa, status },
        geometry: { type: 'Polygon', coordinates: prostokat(wpis.bbox as Bbox) },
      });
    }
  }
  return { punkty: { type: 'FeatureCollection', features: punkty }, obszary: { type: 'FeatureCollection', features: obszary } };
}

/** Adres do skopiowania: bieżący adres strony z parametrem wpisu (reszta widoku zostaje). */
export function adresWpisu(origin: string, sciezka: string, zapytanie: string, id: number): string {
  const q = new URLSearchParams(zapytanie);
  q.set('wpis', String(id));
  return `${origin}${sciezka}?${q.toString()}`;
}
