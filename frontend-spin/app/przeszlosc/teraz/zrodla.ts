import { BladFormatu } from './walidacja';
import { odGodziny } from './czas';

/**
 * Łącze i zdrowie źródeł „Teraz” (GET /api/teraz/zrodla/, backend/teraz/api.py: ZrodloPubliczneSerializer).
 * Moduł jest czysty (bez Reacta i sieci). Zasady twarde (REKOMENDACJA.md w docs/teraz-koncepcje):
 *  - rodzaj łącza i stan źródła mają ikonę/znak i słowo, kolor nigdy nie jest jedynym nośnikiem,
 *  - luka albo błąd źródła to „brak w naszych danych: źródło X, od <data>”, nigdy „bez komunikatów” ani „spokojnie”,
 *  - nieznana wartość (rodzaj łącza, kod błędu) jest pokazywana jako nieznana, nie ukrywana i nie zgadywana,
 *  - awaria pobrania /zrodla/ to osobny stan „stan źródeł niedostępny”, nie pusta lista.
 */

export type RodzajLacza = 'x' | 'api' | 'mci' | 'rss' | 'scraping' | 'websocket' | 'plik' | 'reczne';
export type KodLacza = RodzajLacza | 'nieznane';

export interface MetaLacza {
  kod: KodLacza;
  /** Tekst na etykiecie (jak w prototypie A: X, API, MCI, RSS, scraping, WebSocket, plik, ręcznie). */
  etykieta: string;
  /** Opis dla laika, po polsku (podpowiedź, legenda „Skąd i jak”). */
  opis: string;
}

/** Kolejność rodzajów jak w zleceniu i w prototypie: wartości kontraktu RodzajLacza z backend/teraz/models.py. */
export const KOLEJNOSC_LACZ: readonly RodzajLacza[] = ['x', 'api', 'mci', 'rss', 'scraping', 'websocket', 'plik', 'reczne'];

export const LACZA: Record<KodLacza, MetaLacza> = {
  x: { kod: 'x', etykieta: 'X', opis: 'Wpisy z oficjalnego konta instytucji na portalu X.' },
  api: { kod: 'api', etykieta: 'API', opis: 'Interfejs programistyczny instytucji: dane w ustalonym formacie, pobierane bezpośrednio od źródła.' },
  mci: { kod: 'mci', etykieta: 'MCI', opis: 'Łącze MCI: nazwa rodzaju łącza z rejestru źródeł (dokładniejszy opis w przygotowaniu).' },
  rss: { kod: 'rss', etykieta: 'RSS', opis: 'Kanał RSS: lista najnowszych publikacji ze strony instytucji.' },
  scraping: { kod: 'scraping', etykieta: 'scraping', opis: 'Odczyt strony WWW: program czyta komunikaty z publicznej strony, bo źródło nie ma interfejsu. Zmiana układu strony może przerwać pobieranie.' },
  websocket: { kod: 'websocket', etykieta: 'WebSocket', opis: 'Stałe połączenie z serwerem źródła: dane przychodzą na bieżąco.' },
  plik: { kod: 'plik', etykieta: 'plik', opis: 'Plik z danymi, który źródło publikuje cyklicznie; pobieramy go co jakiś czas.' },
  reczne: { kod: 'reczne', etykieta: 'ręcznie', opis: 'Wpis albo korekta wprowadzona ręcznie przez redakcję.' },
  nieznane: { kod: 'nieznane', etykieta: 'nieznane', opis: 'Nie wiemy, jak pobieramy to źródło: serwer nie podał rodzaju łącza albo podał nieznany.' },
};

const ZNANE: ReadonlySet<string> = new Set(KOLEJNOSC_LACZ);

/** Rodzaj łącza z odpowiedzi API; pusta albo nieznana wartość to „nieznane” (nie zgadujemy). */
export const metaLacza = (kod: string | null | undefined): MetaLacza => (kod && ZNANE.has(kod) ? LACZA[kod as RodzajLacza] : LACZA.nieznane);

export interface ZrodloPubliczne {
  slug: string;
  nazwa: string;
  instytucja: string;
  warstwa: string;
  atrybucja: string;
  /** Surowa wartość z API: może być pusta albo spoza listy (patrz metaLacza). */
  rodzaj_lacza: string;
  czestotliwosc_s: number;
  ostatni_sukces_at: string | null;
  /** Ogólny kod błędu (backend/teraz/historia.py: kod_bledu) albo null, gdy ostatnie pobranie się udało. */
  ostatni_blad: string | null;
  /** Brak sukcesu dłużej niż 3 x częstotliwość albo brak jakiegokolwiek sukcesu. */
  luka: boolean;
}

export type StanZdrowia = 'dziala' | 'luka' | 'blad' | 'wstrzymane';

export interface MetaZdrowia { znak: string; slowo: string; opis: string }

/** Znak i słowo (nie sama barwa). Znaki jak w prototypie A: ●, ◐, ✕, ‖. */
export const ZDROWIE: Record<StanZdrowia, MetaZdrowia> = {
  dziala: { znak: '●', slowo: 'działa', opis: 'Ostatnie pobranie się udało i jest świeże.' },
  luka: { znak: '◐', slowo: 'luka w danych', opis: 'Dawno nie było udanego pobrania. Komunikaty z tego okresu mogły do nas nie dotrzeć.' },
  blad: { znak: '✕', slowo: 'błąd pobierania', opis: 'Ostatnie pobranie się nie udało. Komunikaty z tego źródła mogą być niepełne.' },
  wstrzymane: { znak: '‖', slowo: 'wstrzymane', opis: 'Źródło odmówiło dostępu, więc wstrzymaliśmy pobieranie.' },
};
export const KOLEJNOSC_ZDROWIA: readonly StanZdrowia[] = ['dziala', 'luka', 'blad', 'wstrzymane'];

/** Kody błędów z backend/teraz/historia.py (KOD_WSTRZYMANIA, KOD_HTTP, KOD_OGOLNY), po polsku. */
export const KODY_BLEDOW: Record<string, string> = {
  dostep_wstrzymany: 'Dostęp wstrzymany: źródło odmówiło dostępu albo zażądało potwierdzenia, że nie jesteśmy robotem, więc pobieranie wstrzymano.',
  blad_http: 'Serwer źródła odpowiedział błędem.',
  blad_zrodla: 'Nie udało się pobrać albo odczytać danych ze źródła.',
};

/** Opis kodu błędu po polsku; nieznany kod jest pokazany z kodem (nie ukrywamy go i nie zgadujemy znaczenia). */
export const opisBledu = (kod: string): string => KODY_BLEDOW[kod] ?? `Nieznany kod błędu: ${kod}.`;

export function stanZdrowia(z: Pick<ZrodloPubliczne, 'ostatni_blad' | 'luka'>): StanZdrowia {
  if (z.ostatni_blad === 'dostep_wstrzymany') return 'wstrzymane';
  if (z.ostatni_blad) return 'blad';
  return z.luka ? 'luka' : 'dziala';
}

/**
 * Zdanie o luce albo błędzie: „brak w naszych danych: źródło X, od <data>”. Data to ostatnie udane pobranie (od niego brakuje
 * danych); gdy źródło nigdy nie zostało pobrane, mówimy to wprost. Dla źródła, które działa, zwraca null.
 */
export function opisBraku(z: Pick<ZrodloPubliczne, 'nazwa' | 'ostatni_sukces_at' | 'ostatni_blad' | 'luka'>, teraz: number = Date.now()): string | null {
  if (stanZdrowia(z) === 'dziala') return null;
  const od = odGodziny(z.ostatni_sukces_at, teraz);
  return od ? `brak w naszych danych: źródło ${z.nazwa}, ${od}` : `brak w naszych danych: źródło ${z.nazwa}, nie mamy żadnego udanego pobrania`;
}

export interface PodsumowanieZrodel { razem: number; dziala: number; luka: number; blad: number; wstrzymane: number; problemy: number }

export function podsumujZrodla(lista: readonly ZrodloPubliczne[]): PodsumowanieZrodel {
  const p: PodsumowanieZrodel = { razem: lista.length, dziala: 0, luka: 0, blad: 0, wstrzymane: 0, problemy: 0 };
  for (const z of lista) p[stanZdrowia(z)]++;
  p.problemy = p.razem - p.dziala;
  return p;
}

/** Wynik pobrania: `pominiete` = rekordy o złym formacie (ich stanu nie znamy, więc interfejs ma o tym powiedzieć). */
export interface WynikZrodel { zrodla: ZrodloPubliczne[]; pominiete: number }

type Obiekt = Record<string, unknown>;
const jestObiektem = (x: unknown): x is Obiekt => typeof x === 'object' && x !== null && !Array.isArray(x);
const jestTekstem = (x: unknown): x is string => typeof x === 'string';
const jestCzasem = (x: unknown): x is string => jestTekstem(x) && Number.isFinite(Date.parse(x));

function walidujZrodloPubliczne(x: unknown): ZrodloPubliczne | null {
  if (!jestObiektem(x) || !jestTekstem(x.slug) || !x.slug || !jestTekstem(x.nazwa) || !x.nazwa) return null;
  // brak pola o błędzie to nie „wszystko w porządku” (luka go i tak pokaże), ale pole złego typu liczymy jako błąd ogólny
  const blad = jestTekstem(x.ostatni_blad) ? x.ostatni_blad || null : x.ostatni_blad === null || x.ostatni_blad === undefined ? null : 'blad_zrodla';
  return {
    slug: x.slug,
    nazwa: x.nazwa,
    instytucja: jestTekstem(x.instytucja) ? x.instytucja : '',
    warstwa: jestTekstem(x.warstwa) ? x.warstwa : '',
    atrybucja: jestTekstem(x.atrybucja) ? x.atrybucja.trim() : '',
    rodzaj_lacza: jestTekstem(x.rodzaj_lacza) ? x.rodzaj_lacza : '',
    czestotliwosc_s: typeof x.czestotliwosc_s === 'number' && Number.isFinite(x.czestotliwosc_s) ? x.czestotliwosc_s : 0,
    ostatni_sukces_at: jestCzasem(x.ostatni_sukces_at) ? x.ostatni_sukces_at : null,
    ostatni_blad: blad,
    // brak pola „luka” liczymy na niekorzyść danych (jak w walidacji warstw)
    luka: x.luka !== false,
  };
}

/** Odpowiedź zrodla/: tablica. Rekord o złym formacie jest pomijany i liczony; gdy żaden nie przeszedł, to awaria, nie „brak źródeł”. */
export function walidujZrodla(x: unknown): WynikZrodel {
  if (!Array.isArray(x)) throw new BladFormatu('zrodla');
  const zrodla = x.map(walidujZrodloPubliczne).filter((z): z is ZrodloPubliczne => z !== null);
  if (x.length > 0 && zrodla.length === 0) throw new BladFormatu('zrodla');
  return { zrodla, pominiete: x.length - zrodla.length };
}

/**
 * Stan danych o źródłach dla interfejsu (jedno miejsce, trzy rozłączne stany):
 *  - `ladowanie`: pierwsze pobranie trwa (nic nie twierdzimy),
 *  - `niedostepne`: błąd i brak wcześniejszych danych („stan źródeł niedostępny”, nigdy „brak danych” ani „wszystko działa”),
 *  - `nieaktualne`: błąd odświeżenia, ale mamy wcześniejszy stan (pokazujemy go z godziną pobrania).
 */
export interface DaneZrodel {
  lista: ZrodloPubliczne[] | undefined;
  ladowanie: boolean;
  niedostepne: boolean;
  nieaktualne: boolean;
  pominiete: number;
  /** Czas (ms) ostatniego udanego pobrania listy; 0, gdy jeszcze nie było. */
  pobranoMs: number;
}

export interface WynikZapytania { data?: WynikZrodel; isPending: boolean; isError: boolean; dataUpdatedAt: number }

export function daneZrodel(q: WynikZapytania): DaneZrodel {
  return {
    lista: q.data?.zrodla,
    ladowanie: q.isPending,
    niedostepne: q.isError && !q.data,
    nieaktualne: q.isError && !!q.data,
    pominiete: q.data?.pominiete ?? 0,
    pobranoMs: q.data ? q.dataUpdatedAt : 0,
  };
}

export const znajdzZrodlo = (dane: DaneZrodel | undefined, slug: string): ZrodloPubliczne | undefined => dane?.lista?.find(z => z.slug === slug);

/** Źródła jednej warstwy (po slugach z warstwy/ albo po polu `warstwa` z zrodla/). */
export const zrodlaWarstwy = (dane: DaneZrodel | undefined, warstwa: string): ZrodloPubliczne[] => (dane?.lista ?? []).filter(z => z.warstwa === warstwa);

/** Zdanie o niedostępnym albo nieaktualnym stanie źródeł (do komunikatów); null, gdy stan jest znany i świeży. */
export function komunikatZrodel(dane: DaneZrodel): string | null {
  if (dane.niedostepne) return 'Nie udało się pobrać stanu źródeł, więc nie wiemy, które działają, a które mają lukę. Brak komunikatów nie znaczy, że nic się nie dzieje.';
  if (dane.nieaktualne) return 'Nie udało się odświeżyć stanu źródeł. Pokazujemy ostatnio pobrany, mógł się zmienić.';
  if (dane.pominiete) return `Pominięto źródła o nieznanym formacie: ${dane.pominiete}. Ich stanu nie znamy.`;
  return null;
}
