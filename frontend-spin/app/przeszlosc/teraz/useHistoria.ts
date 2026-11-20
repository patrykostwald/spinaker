'use client';
import { keepPreviousData, useQuery, type UseQueryResult } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { MAKS_STRON_WPISOW, pobierz, type WynikWpisow } from './api';
import {
  KLUCZ_PAMIECI_OSI, PREDKOSC_DOMYSLNA, klatkaOdtwarzania, STAN_OSI_DOMYSLNY, isoSekundy, ogranicz, parsujPamiecOsi, parsujStanOsi, probnaOs, probneBrakiNa,
  walidujOs, walidujStroneNa, zakresOsi, zapytanieOsi,
  type BrakDanych, type DaneOsi, type Krok, type PamiecOsi, type Predkosc, type StanOsi,
} from './czasOsi';
import { filtrujProbneWpisy, probneWpisy } from './dane-probne';
import { WOJEWODZTWA } from './teryt';
import type { Okres, Wpis } from './typy';
import { OKRESY } from './warstwy';

/**
 * Stan osi czasu i dane trybu PRZESZŁOŚĆ (W4). TerazPage woła useHistoria() i przepuszcza wynik useWpisy() przez useWpisyWTrybie():
 * w trybie TODAY wynik jest dokładnie ten sam co wcześniej (useWpisy, odświeżanie co 30 s), w trybie PRZESZŁOŚĆ to stan na moment
 * z wpisy/?na= (bez odświeżania: archiwum się nie zmienia). Stan osi jest w adresie (tryb, na, krok); krok i prędkość także
 * w pamięci przeglądarki (czasOsi.ts: KLUCZ_PAMIECI_OSI). Tryb i moment celowo nie są pamiętane.
 */

const MINUTA = 60_000;
const teraz = () => Math.floor(Date.now() / MINUTA) * MINUTA;

/** „Teraz” zaokrąglone do minuty, odświeżane co minutę (te same adresy zapytań dla wszystkich w tej minucie). */
export function useTeraz(): number {
  const [t, setT] = useState(teraz);
  useEffect(() => {
    const id = window.setInterval(() => setT(teraz()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  return t;
}

/** prefers-reduced-motion: wtedy bez odtwarzania (krok ręczny). */
export function useOgraniczonyRuch(): boolean {
  const [ograniczony, setOgraniczony] = useState(false);
  useEffect(() => {
    const m = window.matchMedia('(prefers-reduced-motion: reduce)');
    const ustaw = () => setOgraniczony(m.matches);
    ustaw();
    m.addEventListener('change', ustaw);
    return () => m.removeEventListener('change', ustaw);
  }, []);
  return ograniczony;
}

const czytajPamiecOsi = (): PamiecOsi => {
  try { return parsujPamiecOsi(window.localStorage.getItem(KLUCZ_PAMIECI_OSI)); } catch { return {}; }
};
const zapiszPamiecOsi = (p: PamiecOsi) => {
  try { window.localStorage.setItem(KLUCZ_PAMIECI_OSI, JSON.stringify({ ...czytajPamiecOsi(), ...p })); } catch { /* tryb prywatny */ }
};

export interface Historia {
  stan: StanOsi;
  /** Adres i pamięć odczytane (dopiero wtedy startują zapytania i rysuje się oś: bez rozjazdu z renderem serwera). */
  gotowa: boolean;
  teraz: number;
  predkosc: Predkosc;
  odtwarzanie: boolean;
  pokazDzis: () => void;
  pokazMoment: (na: number) => void;
  ustawKrok: (krok: Krok) => void;
  ustawPredkosc: (p: Predkosc) => void;
  ustawOdtwarzanie: (wlaczone: boolean) => void;
}

export function useHistoria(): Historia {
  const [stan, setStan] = useState<StanOsi>(STAN_OSI_DOMYSLNY);
  const [gotowa, setGotowa] = useState(false);
  const [predkosc, setPredkosc] = useState<Predkosc>(PREDKOSC_DOMYSLNA);
  const [odtwarzanie, setOdtwarzanie] = useState(false);
  const t = useTeraz();

  // adres wygrywa z pamięcią (jak w TerazPage); tryb i moment tylko z adresu
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const p = czytajPamiecOsi();
    const zAdresu = parsujStanOsi(q, Date.now());
    setStan({ ...zAdresu, krok: q.has('krok') ? zAdresu.krok : p.krok ?? zAdresu.krok });
    if (p.predkosc) setPredkosc(p.predkosc);
    setGotowa(true);
  }, []);
  // replaceState: bez nowych wpisów w historii przeglądarki; parametry TerazPage zostają (zapytanieOsi zmienia tylko swoje)
  useEffect(() => {
    if (!gotowa) return;
    window.history.replaceState(window.history.state, '', `${window.location.pathname}${zapytanieOsi(stan, window.location.search)}`);
  }, [gotowa, stan]);

  const pokazDzis = useCallback(() => { setOdtwarzanie(false); setStan(s => ({ ...s, tryb: 'dzis', na: null })); }, []);
  const pokazMoment = useCallback((na: number) => setStan(s => ({ ...s, tryb: 'przeszlosc', na: ogranicz(na, Date.now()) })), []);
  const ustawKrok = useCallback((krok: Krok) => { setStan(s => ({ ...s, krok })); zapiszPamiecOsi({ krok }); }, []);
  const ustawPredkosc = useCallback((p: Predkosc) => { setPredkosc(p); zapiszPamiecOsi({ predkosc: p }); }, []);
  return useMemo(() => ({ stan, gotowa, teraz: t, predkosc, odtwarzanie, pokazDzis, pokazMoment, ustawKrok, ustawPredkosc, ustawOdtwarzanie: setOdtwarzanie }),
    [stan, gotowa, t, predkosc, odtwarzanie, pokazDzis, pokazMoment, ustawKrok, ustawPredkosc]);
}

// ---------------------------------------------------------------- os/

/** Histogram osi z os/ (albo dane próbne). Poprzednia odpowiedź zostaje na czas wczytywania (Os.tsx odrzuca ją przy innym kroku). */
export function useOs(probne: boolean, stan: StanOsi, t: number, aktywne: boolean): UseQueryResult<DaneOsi> {
  const z = zakresOsi(stan.krok, stan.na, t);
  return useQuery<DaneOsi>({
    enabled: aktywne,
    queryKey: ['teraz', 'os', probne, stan.krok, z.od, z.do],
    queryFn: ({ signal }) => probne
      ? Promise.resolve(walidujOs(probnaOs(z.od, z.do, stan.krok, Date.now(), probneWpisy())))
      : pobierz<DaneOsi>('os', { od: isoSekundy(z.od), do: isoSekundy(z.do), krok: stan.krok }, signal, walidujOs),
    placeholderData: keepPreviousData,
    staleTime: 60_000, refetchInterval: 5 * MINUTA, refetchIntervalInBackground: false, retry: 1, retryDelay: 2000,
  });
}

// ---------------------------------------------------------------- wpisy/?na=

export interface DodatkiNa {
  /** Moment faktycznie użyty przez serwer (przyszłość jest ścinana do teraz). */
  na: string | null;
  /** Wpisy bez znanej wersji z tamtej chwili (rekordy `brak_danych`): nie pokazujemy ich, ale mówimy, ile ich jest. */
  bezHistorii: number;
  lukaRetencji: boolean;
  brakDanych: BrakDanych[];
  /** Coś z tamtej chwili nie jest w danych: wtedy nie wolno twierdzić „brak komunikatów”. */
  niepelne: boolean;
}
export type WynikWpisowHistorii = WynikWpisow & Partial<DodatkiNa>;

const msOkresu = (okres: Okres) => OKRESY.find(o => o.id === okres)?.ms ?? 86_400_000;
const poNajnowszych = (x: Wpis, y: Wpis) => Date.parse(y.opublikowano_at) - Date.parse(x.opublikowano_at);

async function stronyNa(parametry: Record<string, string>, maksStron: number, signal?: AbortSignal) {
  const wpisy: Wpis[] = [];
  let pominiete = 0, bezHistorii = 0, uciete = true;
  let meta: Pick<DodatkiNa, 'na' | 'lukaRetencji' | 'brakDanych'> = { na: null, lukaRetencji: false, brakDanych: [] };
  for (let strona = 1; strona <= maksStron; strona++) {
    const s = await pobierz('wpisy', { ...parametry, page: strona > 1 ? strona : undefined }, signal, walidujStroneNa);
    if (strona === 1) meta = { na: s.na, lukaRetencji: s.lukaRetencji, brakDanych: s.brakDanych };
    wpisy.push(...s.wyniki);
    pominiete += s.pominiete;
    bezHistorii += s.bezHistorii;
    if (!s.nastepna) { uciete = false; break; }
  }
  return { wpisy, pominiete, bezHistorii, uciete, ...meta };
}

/** Stan na moment `na`: okres liczony wstecz od `na`; województwo jak w pobierzWpisy (filtr TERYT plus prostokąt dla punktów). */
export async function pobierzWpisyNa(okres: Okres, woj: string | null, na: number, signal?: AbortSignal): Promise<WynikWpisow & DodatkiNa> {
  const baza = { od: isoSekundy(na - msOkresu(okres)), na: isoSekundy(na) };
  const region = woj ? WOJEWODZTWA.find(w => w.kod === woj) : null;
  const wyniki = await Promise.all(woj
    ? [stronyNa({ ...baza, teryt: woj }, MAKS_STRON_WPISOW, signal), ...(region ? [stronyNa({ ...baza, bbox: region.bbox.join(',') }, 3, signal)] : [])]
    : [stronyNa(baza, MAKS_STRON_WPISOW, signal)]);
  const poId = new Map<number, Wpis>();
  for (const r of wyniki) for (const w of r.wpisy) poId.set(w.id, w);
  const brakDanych = wyniki[0].brakDanych;
  const bezHistorii = Math.max(...wyniki.map(r => r.bezHistorii));
  return {
    wpisy: [...poId.values()].sort(poNajnowszych), uciete: wyniki.some(r => r.uciete), pominiete: wyniki.reduce((s, r) => s + r.pominiete, 0),
    na: wyniki[0].na, bezHistorii, lukaRetencji: wyniki[0].lukaRetencji, brakDanych, niepelne: bezHistorii > 0 || brakDanych.length > 0,
  };
}

export const kluczNa = (probne: boolean, okres: Okres, woj: string | null, na: number) => ['teraz', 'wpisy-na', probne, okres, woj, isoSekundy(na)] as const;

/** Zapytanie stanu na moment (to samo dla useWpisyWTrybie i dla wstępnego pobrania następnej klatki odtwarzania w Os.tsx). */
export function zapytanieNa(probne: boolean, okres: Okres, woj: string | null, na: number) {
  return {
    queryKey: kluczNa(probne, okres, woj, na),
    queryFn: ({ signal }: { signal?: AbortSignal }): Promise<WynikWpisow & DodatkiNa> => {
      if (!probne) return pobierzWpisyNa(okres, woj, na, signal);
      const wpisy = filtrujProbneWpisy(probneWpisy(), { od: isoSekundy(na - msOkresu(okres)), do: isoSekundy(na) });
      const brakDanych = probneBrakiNa(na, Date.now());
      return Promise.resolve({ wpisy, uciete: false, pominiete: 0, na: isoSekundy(na), bezHistorii: 0, lukaRetencji: false, brakDanych, niepelne: brakDanych.length > 0 });
    },
    // archiwum się nie zmienia (poza decyzjami redakcji), więc bez odświeżania co 30 s
    staleTime: 5 * MINUTA, retry: 1, retryDelay: 2000,
  };
}

/**
 * Wpisy dla mapy, listy i tabeli: TODAY = `zywe` (useWpisy z TerazPage, bez zmian), PRZESZŁOŚĆ = wpisy/?na=. Dane na żywo
 * odświeżają się dalej także w archiwum (powrót do TODAY bez czekania). Archiwum czeka na odczyt adresu (historia.gotowa;
 * ten sam cykl efektów co pamiecGotowa w TerazPage). Bez keepPreviousData: wiersze z innego momentu nie mogą udawać wyniku
 * bieżącego (jak P1-4). Podczas odtwarzania następna klatka jest pobierana z wyprzedzeniem (Doherty: bez czekania na mapę).
 */
export function useWpisyWTrybie(historia: Historia, zywe: UseQueryResult<WynikWpisow>, probne: boolean, okres: Okres, woj: string | null, aktywne: boolean): UseQueryResult<WynikWpisowHistorii> {
  const { stan, gotowa, odtwarzanie, teraz: t } = historia;
  const archiwum = stan.tryb === 'przeszlosc' && stan.na !== null;
  const na = stan.na ?? 0;
  const stare = useQuery<WynikWpisowHistorii>({ ...zapytanieNa(probne, okres, woj, na), enabled: aktywne && gotowa && archiwum });
  const nastepna = archiwum && odtwarzanie ? klatkaOdtwarzania(stan, t).na : na;
  useQuery<WynikWpisowHistorii>({ ...zapytanieNa(probne, okres, woj, nastepna), enabled: aktywne && gotowa && archiwum && odtwarzanie && nastepna !== na });
  return archiwum ? stare : zywe;
}
