import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import type { Okres, Stan, Strona, Warstwa, Wpis, Zdarzenie } from './typy';
import { OKRESY } from './warstwy';
import { WOJEWODZTWA } from './teryt';
import { filtrujProbneWpisy, probneStan, probneWarstwy, probneWpisy, probneZdarzenia } from './dane-probne';

/**
 * Klient API „Teraz”: GET /api/teraz/{warstwy,wpisy,zdarzenia,stan}/ (kontrakt: backend/teraz/api.py, urls.py).
 * Adres bazowy: ten sam origin (rewrites w next.config.js kierują /api/* do backendu); NEXT_PUBLIC_TERAZ_API_URL
 * pozwala wskazać inny. Odświeżanie co 30 s (stan, wpisy, warstwy, zdarzenia), z wstrzymaniem w karcie w tle.
 * W trybie próbnym te same hooki zwracają dane przykładowe (dane-probne/), bez żadnego zapytania do sieci.
 */
export const ODSWIEZANIE_MS = 30_000;
/** Strona DRF ma 50 wpisów; mapa pobiera najwyżej tyle stron (najnowsze wpisy). */
export const MAKS_STRON_WPISOW = 6;
const MAKS_STRON_ZDARZEN = 4;
const BAZA = process.env.NEXT_PUBLIC_TERAZ_API_URL ?? '';

export class BladApi extends Error {
  readonly status: number;
  constructor(status: number, wiadomosc: string) {
    super(wiadomosc);
    this.name = 'BladApi';
    this.status = status;
  }
}

type Parametry = Record<string, string | number | undefined>;

export async function pobierz<T>(sciezka: string, parametry: Parametry = {}, signal?: AbortSignal): Promise<T> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(parametry)) if (v !== undefined && v !== '') q.set(k, String(v));
  const tekst = q.toString();
  const adres = `${BAZA}/api/teraz/${sciezka}/${tekst ? `?${tekst}` : ''}`;
  let odpowiedz: Response;
  try {
    odpowiedz = await fetch(adres, { signal, headers: { Accept: 'application/json' } });
  } catch (e) {
    if ((e as { name?: string })?.name === 'AbortError') throw e;
    throw new BladApi(0, 'Brak połączenia z serwerem.');
  }
  if (!odpowiedz.ok) throw new BladApi(odpowiedz.status, `Serwer odpowiedział błędem ${odpowiedz.status}.`);
  try {
    return (await odpowiedz.json()) as T;
  } catch {
    throw new BladApi(odpowiedz.status, 'Serwer odpowiedział w nieznanym formacie.');
  }
}

/** Pobiera kolejne strony paginacji DRF (?page=) do limitu; `uciete` = są jeszcze starsze wpisy. */
export async function pobierzStrony<T>(sciezka: string, parametry: Parametry, maksStron: number, signal?: AbortSignal): Promise<{ wyniki: T[]; uciete: boolean }> {
  const wyniki: T[] = [];
  for (let strona = 1; strona <= maksStron; strona++) {
    const dane = await pobierz<Strona<T>>(sciezka, { ...parametry, page: strona > 1 ? strona : undefined }, signal);
    wyniki.push(...dane.results);
    if (!dane.next) return { wyniki, uciete: false };
  }
  return { wyniki, uciete: true };
}

export const odKiedy = (okres: Okres, teraz: number = Date.now()): string =>
  new Date(teraz - (OKRESY.find(o => o.id === okres)?.ms ?? 86_400_000)).toISOString();

export interface WynikWpisow { wpisy: Wpis[]; uciete: boolean }

/** Wpisy z okresu (i regionu): dla województwa łączy wynik filtra TERYT z wynikiem filtra prostokąta (wpisy z punktem bez kodu). */
export async function pobierzWpisy(okres: Okres, woj: string | null, signal?: AbortSignal): Promise<WynikWpisow> {
  const od = odKiedy(okres);
  if (!woj) {
    const { wyniki, uciete } = await pobierzStrony<Wpis>('wpisy', { od }, MAKS_STRON_WPISOW, signal);
    return { wpisy: wyniki, uciete };
  }
  const region = WOJEWODZTWA.find(w => w.kod === woj);
  const [a, b] = await Promise.all([
    pobierzStrony<Wpis>('wpisy', { od, teryt: woj }, MAKS_STRON_WPISOW, signal),
    region ? pobierzStrony<Wpis>('wpisy', { od, bbox: region.bbox.join(',') }, MAKS_STRON_WPISOW, signal) : Promise.resolve({ wyniki: [] as Wpis[], uciete: false }),
  ]);
  const poId = new Map<number, Wpis>();
  for (const w of [...a.wyniki, ...b.wyniki]) poId.set(w.id, w);
  const wpisy = [...poId.values()].sort((x, y) => Date.parse(y.opublikowano_at) - Date.parse(x.opublikowano_at));
  return { wpisy, uciete: a.uciete || b.uciete };
}

/**
 * Wpisy do „Mój powiat”: dla każdego z podanych województw (kod 2 cyfry) zapytanie z filtrem TERYT, bez filtra prostokąta
 * (powiat dopasowujemy po kodzie wpisu, wpis bez kodu go nie dotyczy). Filtr `teryt=06` zwraca też wpisy z kodami
 * powiatów i gmin tego województwa, więc jedno zapytanie na województwo wystarcza także dla wpisów „całe województwo”.
 * `uciete` = któreś województwo ma więcej wpisów, niż pobieramy; wtedy „brak wpisów” nie jest pewny.
 */
export async function pobierzWpisyTeryt(okres: Okres, kodyWojewodztw: string[], signal?: AbortSignal): Promise<WynikWpisow> {
  const od = odKiedy(okres);
  const wyniki = await Promise.all(kodyWojewodztw.map(w => pobierzStrony<Wpis>('wpisy', { od, teryt: w }, MAKS_STRON_WPISOW, signal)));
  const poId = new Map<number, Wpis>();
  for (const r of wyniki) for (const w of r.wyniki) poId.set(w.id, w);
  const wpisy = [...poId.values()].sort((x, y) => Date.parse(y.opublikowano_at) - Date.parse(x.opublikowano_at));
  return { wpisy, uciete: wyniki.some(r => r.uciete) };
}

const wspolne = { refetchInterval: ODSWIEZANIE_MS, refetchIntervalInBackground: false, refetchOnReconnect: true, staleTime: ODSWIEZANIE_MS / 2, retry: 1, retryDelay: 2000 } as const;

export function useStan(probne: boolean) {
  return useQuery<Stan>({ queryKey: ['teraz', 'stan', probne], queryFn: ({ signal }) => probne ? Promise.resolve(probneStan()) : pobierz<Stan>('stan', {}, signal), ...wspolne });
}

export function useWarstwy(probne: boolean) {
  return useQuery<Warstwa[]>({ queryKey: ['teraz', 'warstwy', probne], queryFn: ({ signal }) => probne ? Promise.resolve(probneWarstwy()) : pobierz<Warstwa[]>('warstwy', {}, signal), ...wspolne });
}

/** `aktywne` = false wstrzymuje zapytania (widok „Mój powiat” nie potrzebuje danych mapy). */
export function useWpisy(probne: boolean, okres: Okres, woj: string | null, aktywne: boolean = true) {
  return useQuery<WynikWpisow>({
    enabled: aktywne,
    queryKey: ['teraz', 'wpisy', probne, okres, woj],
    queryFn: ({ signal }) => {
      if (!probne) return pobierzWpisy(okres, woj, signal);
      const wpisy = filtrujProbneWpisy(probneWpisy(), { od: odKiedy(okres) });
      return Promise.resolve({ wpisy, uciete: false });
    },
    placeholderData: keepPreviousData,
    ...wspolne,
  });
}

/** Wpisy wybranych powiatów (patrz pobierzWpisyTeryt); bez wybranych województw nie wysyła żadnego zapytania. */
export function useWpisyPowiatow(probne: boolean, okres: Okres, kodyWojewodztw: string[], aktywne: boolean) {
  const klucz = kodyWojewodztw.join(',');
  return useQuery<WynikWpisow>({
    enabled: aktywne && kodyWojewodztw.length > 0,
    queryKey: ['teraz', 'wpisy-powiatow', probne, okres, klucz],
    queryFn: ({ signal }) => {
      if (!probne) return pobierzWpisyTeryt(okres, kodyWojewodztw, signal);
      const od = odKiedy(okres);
      const poId = new Map<number, Wpis>();
      for (const w of kodyWojewodztw) for (const x of filtrujProbneWpisy(probneWpisy(), { od, teryt: w })) poId.set(x.id, x);
      const wpisy = [...poId.values()].sort((x, y) => Date.parse(y.opublikowano_at) - Date.parse(x.opublikowano_at));
      return Promise.resolve({ wpisy, uciete: false });
    },
    // celowo bez keepPreviousData: po zmianie zestawu powiatów stare dane nie mogą udawać kompletnych (fałszywe „brak komunikatów”)
    ...wspolne,
  });
}

export function useZdarzenia(probne: boolean) {
  return useQuery<Zdarzenie[]>({
    queryKey: ['teraz', 'zdarzenia', probne],
    queryFn: async ({ signal }) => probne ? probneZdarzenia() : (await pobierzStrony<Zdarzenie>('zdarzenia', {}, MAKS_STRON_ZDARZEN, signal)).wyniki,
    ...wspolne,
  });
}

/** Czy przeglądarka ma sieć (zdarzenia online/offline); przed hydracją zakładamy, że tak. */
export function useOnline(): boolean {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const ustaw = () => setOnline(navigator.onLine);
    ustaw();
    window.addEventListener('online', ustaw);
    window.addEventListener('offline', ustaw);
    return () => { window.removeEventListener('online', ustaw); window.removeEventListener('offline', ustaw); };
  }, []);
  return online;
}
