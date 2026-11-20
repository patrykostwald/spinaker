import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import type { Okres, Stan, Warstwa, Wpis, WynikListy, Zdarzenie } from './typy';
import { OKRESY } from './warstwy';
import { WOJEWODZTWA } from './teryt';
import { BladFormatu, walidujStan, walidujStrone, walidujWarstwy, walidujWpis, walidujZdarzenie } from './walidacja';
import { filtrujProbneWpisy, probneStan, probneWarstwy, probneWpisy, probneZdarzenia } from './dane-probne';

/**
 * Klient API „Teraz”: GET /api/teraz/{warstwy,wpisy,zdarzenia,stan}/ (kontrakt: backend/teraz/api.py, urls.py).
 * Adres bazowy: ten sam origin (rewrites w next.config.js kierują /api/* do backendu); NEXT_PUBLIC_TERAZ_API_URL
 * pozwala wskazać inny. Odświeżanie ze wstrzymaniem w karcie w tle: stan i wpisy co 30 s, zdarzenia co 60 s, warstwy co 120 s
 * (zmieniają się rzadko), a po powrocie do karty odświeżenie od razu, jeśli dane są nieaktualne.
 * Odpowiedzi są walidowane (walidacja.ts): zła struktura to błąd (stan „dane niedostępne”), nie pusta lista.
 * W trybie próbnym te same hooki zwracają dane przykładowe (dane-probne/), bez żadnego zapytania do sieci.
 */
export const ODSWIEZANIE_MS = 30_000;
export const ODSWIEZANIE_ZDARZEN_MS = 60_000;
export const ODSWIEZANIE_WARSTW_MS = 120_000;
/** Strona DRF ma 50 wpisów; mapa pobiera najwyżej tyle stron (najnowsze wpisy). */
export const MAKS_STRON_WPISOW = 6;
/** Zapytanie o prostokąt województwa dopełnia tylko wpisy bez kodu TERYT (punkty), więc wystarczy mniej stron. */
const MAKS_STRON_PROSTOKATA = 3;
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

/** `waliduj` sprawdza strukturę odpowiedzi; jej wyjątek BladFormatu staje się BladApi (jeden rodzaj błędu dla interfejsu). */
export async function pobierz<T>(sciezka: string, parametry: Parametry = {}, signal?: AbortSignal, waliduj?: (surowe: unknown) => T): Promise<T> {
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
  let surowe: unknown;
  try {
    surowe = await odpowiedz.json();
  } catch {
    throw new BladApi(odpowiedz.status, 'Serwer odpowiedział w nieznanym formacie.');
  }
  if (!waliduj) return surowe as T;
  try {
    return waliduj(surowe);
  } catch (e) {
    if (e instanceof BladFormatu) throw new BladApi(odpowiedz.status, e.message);
    throw e;
  }
}

/**
 * Pobiera kolejne strony paginacji DRF (?page=) do limitu. `uciete` = są jeszcze starsze rekordy poza limitem stron,
 * `pominiete` = rekordy o złym formacie (pomijane). Zła struktura strony kończy się wyjątkiem BladApi.
 * Bez `waliduj` rekordy idą bez zmian.
 */
export async function pobierzStrony<T>(
  sciezka: string, parametry: Parametry, maksStron: number, signal?: AbortSignal, waliduj: (rekord: unknown) => T | null = rekord => rekord as T,
): Promise<WynikListy<T>> {
  const wyniki: T[] = [];
  let pominiete = 0;
  for (let strona = 1; strona <= maksStron; strona++) {
    const dane = await pobierz(sciezka, { ...parametry, page: strona > 1 ? strona : undefined }, signal, surowe => walidujStrone(surowe, waliduj));
    wyniki.push(...dane.wyniki);
    pominiete += dane.pominiete;
    if (!dane.nastepna) return { wyniki, uciete: false, pominiete };
  }
  return { wyniki, uciete: true, pominiete };
}

/** Początek okresu (ISO), zaokrąglony w dół do pełnej minuty: te same adresy dla wszystkich klientów w tej minucie (cache backendu). */
export const odKiedy = (okres: Okres, teraz: number = Date.now()): string =>
  new Date(Math.floor(teraz / 60_000) * 60_000 - (OKRESY.find(o => o.id === okres)?.ms ?? 86_400_000)).toISOString();

export interface WynikWpisow { wpisy: Wpis[]; uciete: boolean; pominiete: number }
export type WynikZdarzen = WynikListy<Zdarzenie>;

const poNajnowszych = (x: Wpis, y: Wpis) => Date.parse(y.opublikowano_at) - Date.parse(x.opublikowano_at);

/** Wpisy z okresu (i regionu): dla województwa łączy wynik filtra TERYT z wynikiem filtra prostokąta (wpisy z punktem bez kodu). */
export async function pobierzWpisy(okres: Okres, woj: string | null, signal?: AbortSignal): Promise<WynikWpisow> {
  const od = odKiedy(okres);
  if (!woj) {
    const { wyniki, uciete, pominiete } = await pobierzStrony<Wpis>('wpisy', { od }, MAKS_STRON_WPISOW, signal, walidujWpis);
    return { wpisy: wyniki, uciete, pominiete };
  }
  const region = WOJEWODZTWA.find(w => w.kod === woj);
  const [a, b] = await Promise.all([
    pobierzStrony<Wpis>('wpisy', { od, teryt: woj }, MAKS_STRON_WPISOW, signal, walidujWpis),
    region
      ? pobierzStrony<Wpis>('wpisy', { od, bbox: region.bbox.join(',') }, MAKS_STRON_PROSTOKATA, signal, walidujWpis)
      : Promise.resolve({ wyniki: [] as Wpis[], uciete: false, pominiete: 0 }),
  ]);
  const poId = new Map<number, Wpis>();
  for (const w of [...a.wyniki, ...b.wyniki]) poId.set(w.id, w);
  return { wpisy: [...poId.values()].sort(poNajnowszych), uciete: a.uciete || b.uciete, pominiete: a.pominiete + b.pominiete };
}

/**
 * Wpisy do „Mój powiat”: dla każdego z podanych województw (kod 2 cyfry) zapytanie z filtrem TERYT, bez filtra prostokąta
 * (powiat dopasowujemy po kodzie wpisu, wpis bez kodu go nie dotyczy). Filtr `teryt=06` zwraca też wpisy z kodami
 * powiatów i gmin tego województwa, więc jedno zapytanie na województwo wystarcza także dla wpisów „całe województwo”.
 * `uciete` = któreś województwo ma więcej wpisów, niż pobieramy; wtedy „brak wpisów” nie jest pewny.
 */
export async function pobierzWpisyTeryt(okres: Okres, kodyWojewodztw: string[], signal?: AbortSignal): Promise<WynikWpisow> {
  const od = odKiedy(okres);
  const wyniki = await Promise.all(kodyWojewodztw.map(w => pobierzStrony<Wpis>('wpisy', { od, teryt: w }, MAKS_STRON_WPISOW, signal, walidujWpis)));
  const poId = new Map<number, Wpis>();
  for (const r of wyniki) for (const w of r.wyniki) poId.set(w.id, w);
  return { wpisy: [...poId.values()].sort(poNajnowszych), uciete: wyniki.some(r => r.uciete), pominiete: wyniki.reduce((suma, r) => suma + r.pominiete, 0) };
}

/**
 * Wspólne ustawienia zapytań. Domyślny klient aplikacji (providers.tsx) wyłącza odświeżanie po powrocie do okna, więc tu jest
 * włączone jawnie: po powrocie do karty dane starsze niż `staleTime` są pobierane od razu, bez czekania na następny cykl.
 */
export const wspolne = { refetchIntervalInBackground: false, refetchOnWindowFocus: true, refetchOnReconnect: true, retry: 1, retryDelay: 2000 } as const;
export const co = (ms: number) => ({ refetchInterval: ms, staleTime: ms / 2 });

export function useStan(probne: boolean) {
  return useQuery<Stan>({
    queryKey: ['teraz', 'stan', probne],
    queryFn: ({ signal }) => probne ? Promise.resolve(probneStan()) : pobierz<Stan>('stan', {}, signal, walidujStan),
    ...wspolne, ...co(ODSWIEZANIE_MS),
  });
}

export function useWarstwy(probne: boolean) {
  return useQuery<Warstwa[]>({
    queryKey: ['teraz', 'warstwy', probne],
    queryFn: ({ signal }) => probne ? Promise.resolve(probneWarstwy()) : pobierz<Warstwa[]>('warstwy', {}, signal, walidujWarstwy),
    ...wspolne, ...co(ODSWIEZANIE_WARSTW_MS),
  });
}

/**
 * `aktywne` = false wstrzymuje zapytania (widok „Mój powiat” nie potrzebuje danych mapy; przed odczytem preferencji też czekamy).
 * Celowo bez keepPreviousData (recenzja PR #38, P1-4): po zmianie okresu albo regionu wiersze z poprzedniego filtra nie mogą
 * udawać wyniku nowego (tabela, podpis i eksport CSV czekają na odpowiedź dla bieżącego filtra).
 */
export function useWpisy(probne: boolean, okres: Okres, woj: string | null, aktywne: boolean = true) {
  return useQuery<WynikWpisow>({
    enabled: aktywne,
    queryKey: ['teraz', 'wpisy', probne, okres, woj],
    queryFn: ({ signal }) => {
      if (!probne) return pobierzWpisy(okres, woj, signal);
      const wpisy = filtrujProbneWpisy(probneWpisy(), { od: odKiedy(okres) });
      return Promise.resolve({ wpisy, uciete: false, pominiete: 0 });
    },
    ...wspolne, ...co(ODSWIEZANIE_MS),
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
      return Promise.resolve({ wpisy: [...poId.values()].sort(poNajnowszych), uciete: false, pominiete: 0 });
    },
    // celowo bez keepPreviousData: po zmianie zestawu powiatów stare dane nie mogą udawać kompletnych (fałszywe „brak komunikatów”)
    ...wspolne, ...co(ODSWIEZANIE_MS),
  });
}

/**
 * Zdarzenia z limitem stron. `pominiete` liczy także powiązane wpisy odrzucone przez walidację wewnątrz zdarzeń: bez tego wpis
 * z odrzuconym powiązaniem dostałby fałszywe „Komunikat bez zdarzenia” (P2-8).
 */
export async function pobierzZdarzenia(signal?: AbortSignal): Promise<WynikZdarzen> {
  const wynik = await pobierzStrony<Zdarzenie>('zdarzenia', {}, MAKS_STRON_ZDARZEN, signal, walidujZdarzenie);
  return { ...wynik, pominiete: wynik.pominiete + wynik.wyniki.reduce((suma, z) => suma + z.odrzucone_wpisy, 0) };
}

/** Zdarzenia dają status wpisów. Awaria albo ucięcie (`uciete`) oznacza, że status części wpisów jest nieznany (patrz zbudujWidoki). */
export function useZdarzenia(probne: boolean) {
  return useQuery<WynikZdarzen>({
    queryKey: ['teraz', 'zdarzenia', probne],
    queryFn: async ({ signal }) => probne
      ? { wyniki: probneZdarzenia(), uciete: false, pominiete: 0 }
      : pobierzZdarzenia(signal),
    ...wspolne, ...co(ODSWIEZANIE_ZDARZEN_MS),
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
