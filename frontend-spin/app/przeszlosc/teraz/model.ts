import type { Bbox, KodWarstwy, LiniaStanu, Stan, StatusKlucz, Warstwa, WidokWpisu, Wpis, WynikListy, Zdarzenie, Zrodlo } from './typy';
import { metaStatusu, metaWarstwy, KOLEJNOSC_WARSTW } from './warstwy';
import { WOJEWODZTWA, wBbox } from './teryt';
import { zbudujZapytanie, type Parametry } from './parametry';

/** Czysta logika widoku (bez Reacta i mapy), żeby dało się ją sprawdzić testami. */

/**
 * Które wpisy mogą mieć status, którego nie znamy. Wpis bez zdarzenia jest „bez zdarzenia” tylko wtedy, gdy mamy pełne zdarzenia:
 *  - `wszystkie`: nie ma danych o zdarzeniach (awaria, wczytywanie) albo część rekordów miała zły format,
 *  - `nieWiekszeNiz`: zdarzenia pobrano z limitem stron (od najnowszych); zdarzenie spoza limitu ma `ostatni_wpis_at` nie
 *    późniejszy niż najstarsze pobrane, więc wpis opublikowany później niż ta granica na pewno nie należy do pominiętego zdarzenia.
 */
export interface PolitykaStatusu { wszystkie: boolean; nieWiekszeNiz: number | null }
export const PELNE_ZDARZENIA: PolitykaStatusu = { wszystkie: false, nieWiekszeNiz: null };

export function politykaStatusu(zdarzenia: WynikListy<Zdarzenie> | undefined): PolitykaStatusu {
  if (!zdarzenia || zdarzenia.pominiete > 0) return { wszystkie: true, nieWiekszeNiz: null };
  if (!zdarzenia.uciete) return PELNE_ZDARZENIA;
  const czasy = zdarzenia.wyniki.map(z => Date.parse(z.ostatni_wpis_at)).filter(Number.isFinite);
  return czasy.length ? { wszystkie: false, nieWiekszeNiz: Math.min(...czasy) } : { wszystkie: true, nieWiekszeNiz: null };
}

/** Kody warstw wyłączonych przez redakcję (pole `wylaczona` z warstwy/). */
export const kodyWylaczonych = (warstwy: Warstwa[] | undefined): Set<string> => new Set((warstwy ?? []).filter(w => w.wylaczona).map(w => w.warstwa));

/**
 * Usuwa z danych wszystko, co należy do wyłączonych warstw: wpisy oraz wpisy powiązane w zdarzeniach (karta, „inne komunikaty”).
 * Działa na danych z cache klienta, więc wycofana warstwa znika także tam, gdzie wpisy przyszły przed wyłączeniem.
 */
export function bezWylaczonych(wpisy: Wpis[], zdarzenia: Zdarzenie[], wylaczone: ReadonlySet<string>): { wpisy: Wpis[]; zdarzenia: Zdarzenie[] } {
  if (!wylaczone.size) return { wpisy, zdarzenia };
  return {
    wpisy: wpisy.filter(w => !wylaczone.has(w.warstwa)),
    zdarzenia: zdarzenia
      .map(z => (z.wpisy.some(w => wylaczone.has(w.warstwa)) ? { ...z, wpisy: z.wpisy.filter(w => !wylaczone.has(w.warstwa)) } : z))
      .filter(z => z.wpisy.length > 0),
  };
}

/** Wpis → zdarzenie (przy kilku zdarzeniach wygrywa to z najświeższym wpisem); status tylko ze zdarzenia, a gdy zdarzeń nie znamy, „status niedostępny”. */
export function zbudujWidoki(wpisy: Wpis[], zdarzenia: Zdarzenie[], polityka: PolitykaStatusu = PELNE_ZDARZENIA): WidokWpisu[] {
  const poWpisie = new Map<number, Zdarzenie>();
  for (const z of zdarzenia) {
    for (const w of z.wpisy) {
      const stare = poWpisie.get(w.id);
      if (!stare || Date.parse(z.ostatni_wpis_at) > Date.parse(stare.ostatni_wpis_at)) poWpisie.set(w.id, z);
    }
  }
  return wpisy.map(wpis => {
    const zdarzenie = poWpisie.get(wpis.id) ?? null;
    const nieznany = !zdarzenie && (polityka.wszystkie || (polityka.nieWiekszeNiz !== null && Date.parse(wpis.opublikowano_at) <= polityka.nieWiekszeNiz));
    const status: StatusKlucz = zdarzenie ? zdarzenie.status : nieznany ? 'niedostepny' : 'brak';
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

/** Czy dwa zasięgi (zachód, południe, wschód, północ) mają wspólną część. */
export const przecinaSie = (a: Bbox, b: Bbox): boolean => a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];

/**
 * Filtr województwa: kod TERYT zaczyna się od kodu województwa. Wpis bez TERYT z punktem liczy się, gdy punkt leży w przybliżonym
 * prostokącie województwa, a z prostokątem, gdy jego zasięg ma z tym prostokątem część wspólną (tak samo filtruje API: `bbox=`).
 * To przybliżenie: prostokąty województw nie są granicami, więc przy brzegach mogą trafić się wpisy z sąsiedniego województwa
 * (interfejs mówi o tym w panelu filtrów). Zasięg obejmujący część regionu nie znika.
 */
export function zgodnyZRegionem(w: Wpis, woj: string | null): boolean {
  if (!woj) return true;
  if (w.teryt.length) return w.teryt.some(k => k.startsWith(woj));
  const region = WOJEWODZTWA.find(r => r.kod === woj);
  if (!region) return true;
  if (poprawnyPunkt(w)) return wBbox(w.dlugosc as number, w.szerokosc as number, region.bbox);
  if (maObszar(w)) return przecinaSie(w.bbox as Bbox, region.bbox);
  return false;
}

/** Warstwa działa: nie jest wyłączona przez redakcję i ma publiczne źródło. Wyłączona nie pojawia się nigdzie, także w „w przygotowaniu”. */
export const aktywna = (w: Warstwa): boolean => !w.wylaczona && w.zrodla.length > 0;
export const dostepna = (w: Warstwa): boolean => !w.wylaczona;

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

/**
 * Które warstwy są włączone: null z URL i pamięci = wszystkie aktywne. Zapisany wybór obejmuje tylko warstwy, które istnieją i nie są
 * wyłączone (wyłączenie wygrywa z preferencją). Gdy listy warstw nie mamy, wybór zostaje bez zmian (nie ma z czym porównać).
 */
export function wlaczoneWarstwy(wybor: string[] | null, warstwy: Warstwa[]): Set<string> {
  if (wybor === null) return new Set(warstwy.filter(aktywna).map(w => w.warstwa));
  if (!warstwy.length) return new Set(wybor);
  const dozwolone = new Set<string>(warstwy.filter(dostepna).map(w => w.warstwa));
  return new Set(wybor.filter(k => dozwolone.has(k)));
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
  const wylaczone = kodyWylaczonych(warstwy);
  const wiersze = stan.warstwy.filter(l => !wylaczone.has(l.warstwa)).map((l: LiniaStanu): WierszStanu => {
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

/**
 * Adres do skopiowania: ścieżka strony i wyłącznie parametry widoku z listy dozwolonych (warstwy, okres, województwo, widok, tryb próbny)
 * plus wpis. Obcych parametrów z bieżącego adresu (np. śledzących) nie kopiujemy.
 */
export function adresWpisu(origin: string, sciezka: string, widok: Parametry, id: number): string {
  return `${origin}${sciezka}${zbudujZapytanie({ ...widok, wpis: id }, '')}`;
}
