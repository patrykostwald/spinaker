import type { Wpis } from './typy';
import { BladFormatu, walidujWpis } from './walidacja';
import { liczbaKomunikatow } from './powiaty';

/**
 * Oś czasu „Teraz” (W4): czysta logika przełącznika TODAY / PRZESZŁOŚĆ, przedziałów osi, kroków suwaka, odtwarzania i luk.
 * Bez Reacta i sieci (testy: tests/160-*). Kontrakt API (backend/teraz/api.py, historia.py):
 *  - GET os/?od&do&krok=dzien|godzina: kubełki {od, do, liczba (null przy luce), w_przegladzie, luka_retencji, luka_zrodel},
 *    doba liczona w strefie Europe/Warsaw, godzina wyrównana do pełnej godziny;
 *  - GET wpisy/?na=<ISO>: stan na moment; rekord z `brak_danych: true` to wpis bez znanej wersji z tamtej chwili (bez treści).
 * Zasada nadrzędna: brak danych nigdy nie jest zerem. Liczba null, luka retencji i luka źródła to kreskowanie z podpisem.
 */

export type Tryb = 'dzis' | 'przeszlosc';
export type Krok = 'dzien' | 'godzina';
export interface StanOsi { tryb: Tryb; /** Moment stanu (ms) w trybie PRZESZŁOŚĆ; null w trybie TODAY. */ na: number | null; krok: Krok }
export const STAN_OSI_DOMYSLNY: StanOsi = { tryb: 'dzis', na: null, krok: 'dzien' };

export const STREFA = 'Europe/Warsaw';
const GODZINA = 3_600_000;
const DOBA = 86_400_000;
/** Ile dób wstecz pokazuje oś dni (jak w koncepcji G1: 30 dni); starszy moment z adresu jest dociągany do początku osi. */
export const DNI_OSI = 30;

// ---------------------------------------------------------------- czas w strefie Warszawy

const formatCzesci = new Intl.DateTimeFormat('en-US', {
  timeZone: STREFA, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
});
function czesci(ms: number): { r: number; m: number; d: number; g: number; min: number; s: number } {
  const c: Record<string, string> = {};
  for (const p of formatCzesci.formatToParts(ms)) c[p.type] = p.value;
  return { r: +c.year, m: +c.month, d: +c.day, g: +c.hour % 24, min: +c.minute, s: +c.second };
}

/** Przesunięcie czasu Warszawy względem UTC w chwili `ms` (3 600 000 zimą, 7 200 000 latem). */
export function przesuniecie(ms: number): number {
  const c = czesci(ms);
  return Date.UTC(c.r, c.m - 1, c.d, c.g, c.min, c.s) - Math.floor(ms / 1000) * 1000;
}

/** Północ (początek doby w Warszawie) dla chwili `ms`. Zmiana czasu w Polsce jest o 2:00/3:00, więc północ zawsze istnieje. */
export function poczatekDnia(ms: number): number {
  const c = czesci(ms);
  const polnoc = Date.UTC(c.r, c.m - 1, c.d);
  return polnoc - przesuniecie(polnoc - przesuniecie(polnoc));
}
/** Początek następnej doby (doba ma 23, 24 albo 25 godzin). */
export const nastepnyDzien = (poczatek: number): number => poczatekDnia(poczatek + 36 * GODZINA);
/** Początek poprzedniej doby. */
export const poprzedniDzien = (poczatek: number): number => poczatekDnia(poczatek - 12 * GODZINA);

/** Najwcześniejszy początek osi: północ sprzed DNI_OSI - 1 dób. */
export function poczatekOsi(teraz: number): number {
  let d = poczatekDnia(teraz);
  for (let i = 1; i < DNI_OSI; i++) d = poprzedniDzien(d);
  return d;
}

/** „2026-11-18T22:59:59Z”: ISO w UTC z dokładnością do sekundy (do adresu i zapytań). */
export const isoSekundy = (ms: number): string => new Date(Math.floor(ms / 1000) * 1000).toISOString().replace('.000Z', 'Z');

// ---------------------------------------------------------------- przedziały osi

export interface Przedzial { od: number; do: number }

/** Przedziały [od, do) jak w backendzie (historia.kubelki): doby lokalne albo pełne godziny; najwyżej 400. */
export function przedzialy(od: number, doCzasu: number, krok: Krok): Przedzial[] {
  const wynik: Przedzial[] = [];
  if (krok === 'dzien') {
    for (let d = poczatekDnia(od); d <= doCzasu && wynik.length < 400; d = nastepnyDzien(d)) wynik.push({ od: d, do: nastepnyDzien(d) });
  } else {
    for (let g = Math.floor(od / GODZINA) * GODZINA; g <= doCzasu && wynik.length < 400; g += GODZINA) wynik.push({ od: g, do: g + GODZINA });
  }
  return wynik;
}

/** Zakres zapytania os/: oś dni = ostatnie DNI_OSI dób do teraz; oś godzin = doba wybranego momentu (dziś: do teraz). */
export function zakresOsi(krok: Krok, na: number | null, teraz: number): Przedzial {
  if (krok === 'dzien') return { od: poczatekOsi(teraz), do: teraz };
  const dzien = poczatekDnia(na ?? teraz);
  return { od: dzien, do: Math.min(nastepnyDzien(dzien) - 1000, teraz) };
}

export const przedzialyOsi = (stan: StanOsi, teraz: number): Przedzial[] => {
  const z = zakresOsi(stan.krok, stan.na, teraz);
  return przedzialy(z.od, z.do, stan.krok);
};

/** Moment stanu dla przedziału: ostatnia sekunda przedziału, ale nie później niż teraz. */
export const momentPrzedzialu = (p: Przedzial, teraz: number): number => Math.min(p.do - 1000, teraz);

/** Indeks przedziału z chwilą `na` (poza osią: najbliższy koniec). */
export function indeksPrzedzialu(lista: Przedzial[], na: number): number {
  if (!lista.length) return 0;
  if (na < lista[0].od) return 0;
  const i = lista.findIndex(p => na >= p.od && na < p.do);
  return i === -1 ? lista.length - 1 : i;
}

/** Moment stanu dla trybu i pozycji: TODAY = teraz. */
export const momentStanu = (stan: StanOsi, teraz: number): number => (stan.tryb === 'przeszlosc' && stan.na !== null ? stan.na : teraz);

/** Moment w granicach osi: nie w przyszłości i nie wcześniej niż początek osi dni. */
export const ogranicz = (na: number, teraz: number): number => Math.max(poczatekOsi(teraz), Math.min(na, teraz));

/**
 * Krok suwaka (strzałka, przyciski ◀ ▶): moment sąsiedniego przedziału. Na osi godzin krok poza dobę przechodzi do sąsiedniej
 * doby (23:00 poprzedniej, 0:00 następnej). Poza zakresem osi (przed początkiem albo po teraz) zostaje bieżący moment.
 */
export function przesun(stan: StanOsi, kierunek: -1 | 1, teraz: number): number {
  const obecny = momentStanu(stan, teraz);
  const lista = przedzialyOsi({ ...stan, na: obecny }, teraz);
  const j = indeksPrzedzialu(lista, obecny) + kierunek;
  if (j >= 0 && j < lista.length) return momentPrzedzialu(lista[j], teraz);
  if (stan.krok === 'godzina') {
    const dzien = poczatekDnia(obecny);
    if (kierunek < 0 && dzien > poczatekOsi(teraz)) return dzien - 1000;
    const nastepny = nastepnyDzien(dzien);
    if (kierunek > 0 && nastepny <= teraz) return momentPrzedzialu({ od: nastepny, do: nastepny + GODZINA }, teraz);
  }
  return obecny;
}

/** Czy moment jest ostatnią pozycją osi (bieżący przedział). */
export function naKoncu(stan: StanOsi, teraz: number): boolean {
  const lista = przedzialyOsi(stan, teraz);
  return !lista.length || indeksPrzedzialu(lista, momentStanu(stan, teraz)) === lista.length - 1;
}

// ---------------------------------------------------------------- odtwarzanie

export const PREDKOSCI = [
  { id: 1, etykieta: 'Tempo 1×', ms: 2000 },
  { id: 2, etykieta: 'Tempo 2×', ms: 1000 },
  { id: 4, etykieta: 'Tempo 4×', ms: 500 },
] as const;
export type Predkosc = typeof PREDKOSCI[number]['id'];
export const PREDKOSC_DOMYSLNA: Predkosc = 1;
export const poprawnaPredkosc = (x: unknown): x is Predkosc => PREDKOSCI.some(p => p.id === x);
export const odstepOdtwarzania = (p: Predkosc): number => PREDKOSCI.find(x => x.id === p)?.ms ?? 2000;

/**
 * Pierwszy moment odtwarzania: z trybu TODAY albo z końca osi zaczynamy od początku osi (oś godzin: od północy wybranej doby,
 * czyli „animacja dnia”); w środku osi odtwarzamy od bieżącego miejsca.
 */
export function startOdtwarzania(stan: StanOsi, teraz: number): number {
  if (stan.tryb === 'przeszlosc' && stan.na !== null && !naKoncu(stan, teraz)) return stan.na;
  const lista = przedzialyOsi(stan, teraz);
  return lista.length ? momentPrzedzialu(lista[0], teraz) : teraz;
}

/** Następna klatka odtwarzania; `koniec` = doszliśmy do ostatniego przedziału osi (odtwarzanie się zatrzymuje, nie przewija). */
export function klatkaOdtwarzania(stan: StanOsi, teraz: number): { na: number; koniec: boolean } {
  const lista = przedzialyOsi(stan, teraz);
  const i = indeksPrzedzialu(lista, momentStanu(stan, teraz));
  if (i + 1 >= lista.length) return { na: momentStanu(stan, teraz), koniec: true };
  return { na: momentPrzedzialu(lista[i + 1], teraz), koniec: i + 2 >= lista.length };
}

// ---------------------------------------------------------------- adres URL i pamięć

type Wejscie = string | URLSearchParams;
const zapytanie = (w: Wejscie) => (typeof w === 'string' ? new URLSearchParams(w) : w);

/**
 * Stan osi z adresu: `tryb=przeszlosc&na=<ISO>` (oba wymagane), `krok=godzina` (domyślnie dzien). Moment z przyszłości dociągamy
 * do teraz, a starszy niż początek osi do jej początku. Błędny albo brakujący moment daje TODAY: archiwum bez momentu nie istnieje.
 */
export function parsujStanOsi(w: Wejscie, teraz: number): StanOsi {
  const q = zapytanie(w);
  const krok: Krok = q.get('krok') === 'godzina' ? 'godzina' : 'dzien';
  const naTekst = q.get('na') ?? '';
  const ms = /^\d{4}-\d{2}-\d{2}T/.test(naTekst) ? Date.parse(naTekst) : NaN;
  if (q.get('tryb') !== 'przeszlosc' || !Number.isFinite(ms)) return { tryb: 'dzis', na: null, krok };
  return { tryb: 'przeszlosc', na: ogranicz(ms, teraz), krok };
}

/** Nakłada stan osi na ciąg zapytania (inne parametry zostają); wartości domyślne (TODAY, krok dzień) znikają z adresu. */
export function zapytanieOsi(stan: StanOsi, obecne: string = ''): string {
  const q = new URLSearchParams(obecne);
  for (const k of ['tryb', 'na', 'krok']) q.delete(k);
  if (stan.tryb === 'przeszlosc' && stan.na !== null) { q.set('tryb', 'przeszlosc'); q.set('na', isoSekundy(stan.na)); }
  if (stan.krok === 'godzina') q.set('krok', 'godzina');
  const tekst = q.toString();
  return tekst ? `?${tekst}` : '';
}

/**
 * Pamięć widoku osi (localStorage, osobny klucz, żeby nie ruszać pamiec.ts): krok i prędkość. Trybu i momentu celowo nie pamiętamy:
 * po powrocie na stronę zawsze widać dane bieżące, a archiwum otwiera się tylko z adresu (nikt nie weźmie archiwum za „teraz”).
 */
export const KLUCZ_PAMIECI_OSI = 'przeszlosc.teraz.os.v1';
export interface PamiecOsi { krok?: Krok; predkosc?: Predkosc }
export function parsujPamiecOsi(surowy: string | null | undefined): PamiecOsi {
  let dane: unknown;
  try { dane = JSON.parse(surowy || '{}'); } catch { return {}; }
  if (typeof dane !== 'object' || dane === null || Array.isArray(dane)) return {};
  const x = dane as Record<string, unknown>;
  const wynik: PamiecOsi = {};
  if (x.krok === 'dzien' || x.krok === 'godzina') wynik.krok = x.krok;
  if (poprawnaPredkosc(x.predkosc)) wynik.predkosc = x.predkosc;
  return wynik;
}

// ---------------------------------------------------------------- odpowiedź os/

export interface Kubelek { od: number; do: number; liczba: number | null; wPrzegladzie: number; lukaRetencji: boolean; lukaZrodel: string[] }
export interface BrakDanych { powod: string; zrodla: string[]; od: number | null; do: number | null }
export interface DaneOsi { krok: Krok | null; kubelki: Kubelek[]; brakDanych: BrakDanych[]; lukaRetencji: boolean; pominiete: number }

type Obiekt = Record<string, unknown>;
const jestObiektem = (x: unknown): x is Obiekt => typeof x === 'object' && x !== null && !Array.isArray(x);
const czasMs = (x: unknown): number | null => (typeof x === 'string' && Number.isFinite(Date.parse(x)) ? Date.parse(x) : null);
const teksty = (x: unknown): string[] => (Array.isArray(x) ? x.filter((s): s is string => typeof s === 'string') : []);

function walidujBraki(x: unknown): BrakDanych[] {
  if (!Array.isArray(x)) return [];
  return x.filter(jestObiektem).filter(b => typeof b.powod === 'string')
    .map(b => ({ powod: b.powod as string, zrodla: teksty(b.zrodla), od: czasMs(b.od), do: czasMs(b.do) }));
}

/**
 * Odpowiedź os/ po walidacji. Zła struktura całości to wyjątek (oś niedostępna). Kubełek z poprawnym czasem, ale złą liczbą
 * dostaje liczbę null (nie wiemy), a zero przy jakiejkolwiek luce też staje się null: brak danych nigdy nie jest zerem.
 */
export function walidujOs(x: unknown): DaneOsi {
  if (!jestObiektem(x) || !Array.isArray(x.kubelki)) throw new BladFormatu('oś czasu');
  let pominiete = 0;
  const kubelki: Kubelek[] = [];
  for (const k of x.kubelki) {
    const od = jestObiektem(k) ? czasMs(k.od) : null;
    const doCzasu = jestObiektem(k) ? czasMs(k.do) : null;
    if (!jestObiektem(k) || od === null || doCzasu === null) { pominiete++; continue; }
    const lukaRetencji = k.luka_retencji === true;
    const lukaZrodel = teksty(k.luka_zrodel);
    const surowa = k.liczba;
    let liczba = typeof surowa === 'number' && Number.isInteger(surowa) && surowa >= 0 ? surowa : null;
    if (liczba === 0 && (lukaRetencji || lukaZrodel.length > 0)) liczba = null;
    const wPrzegladzie = typeof k.w_przegladzie === 'number' && k.w_przegladzie >= 0 ? k.w_przegladzie : 0;
    kubelki.push({ od, do: doCzasu, liczba, wPrzegladzie, lukaRetencji, lukaZrodel });
  }
  const krok = x.krok === 'dzien' || x.krok === 'godzina' ? x.krok : null;
  return { krok, kubelki, brakDanych: walidujBraki(x.brak_danych), lukaRetencji: x.luka_retencji === true || kubelki.some(k => k.lukaRetencji), pominiete };
}

// ---------------------------------------------------------------- słupki histogramu

/**
 * liczba: mamy dane bez luk; czesciowy: liczba znana, ale część źródeł albo wpisów nie jest w danych („co najmniej”);
 * brak: luka bez liczby; nieznany: serwer nie zwrócił tego przedziału; ladowanie: oś jeszcze się wczytuje (bez rysowania luk).
 */
export type StanSlupka = 'liczba' | 'czesciowy' | 'brak' | 'nieznany' | 'ladowanie';
export interface Slupek extends Przedzial { moment: number; liczba: number | null; stan: StanSlupka; zrodla: string[]; lukaRetencji: boolean }
export const kreskowany = (s: Slupek): boolean => s.stan === 'brak' || s.stan === 'nieznany' || s.stan === 'czesciowy';

/** `blad` = os/ nie odpowiedziała: każdy przedział to „nieznany” (kreskowanie), nigdy pusta oś udająca zera. */
export function scalSlupki(lista: Przedzial[], dane: DaneOsi | undefined, teraz: number, blad: boolean = false): Slupek[] {
  const poOd = new Map((dane?.kubelki ?? []).map(k => [k.od, k]));
  return lista.map(p => {
    const moment = momentPrzedzialu(p, teraz);
    if (!dane) return { ...p, moment, liczba: null, stan: blad ? 'nieznany' : 'ladowanie', zrodla: [], lukaRetencji: false };
    const k = poOd.get(p.od);
    if (!k) return { ...p, moment, liczba: null, stan: 'nieznany', zrodla: [], lukaRetencji: false };
    const luka = k.lukaRetencji || k.lukaZrodel.length > 0;
    const stan: StanSlupka = k.liczba === null ? 'brak' : luka ? 'czesciowy' : 'liczba';
    return { ...p, moment, liczba: k.liczba, stan, zrodla: k.lukaZrodel, lukaRetencji: k.lukaRetencji };
  });
}

/** Wysokości słupków 0..1 (względem największej znanej liczby); luka bez liczby ma pełną wysokość kreskowania, nie zero. */
export function wysokosci(slupki: Slupek[]): number[] {
  const maks = Math.max(1, ...slupki.map(s => s.liczba ?? 0));
  return slupki.map(s => (s.stan === 'brak' || s.stan === 'nieznany' ? 1 : s.liczba ? Math.max(0.06, s.liczba / maks) : 0));
}

// ---------------------------------------------------------------- teksty

const odmiana = (n: number, [jeden, kilka, wiele]: [string, string, string]): string => {
  const o = n % 10, d = n % 100;
  if (n === 1) return `1 ${jeden}`;
  return `${n} ${o >= 2 && o <= 4 && !(d >= 12 && d <= 14) ? kilka : wiele}`;
};
export const ileDni = (n: number) => odmiana(n, ['dzień', 'dni', 'dni']);
export const ileGodzin = (n: number) => odmiana(n, ['godzina', 'godziny', 'godzin']);

const formatDnia = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', timeZone: STREFA });
const formatDniaRok = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric', timeZone: STREFA });
const formatKrotki = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'short', timeZone: STREFA });
const formatGodziny = new Intl.DateTimeFormat('pl-PL', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: STREFA });

/** „dziś”, „wczoraj”, „18 listopada” (z rokiem, gdy inny niż bieżący). */
export function nazwaDnia(ms: number, teraz: number): string {
  const d = poczatekDnia(ms), dzis = poczatekDnia(teraz);
  if (d === dzis) return 'dziś';
  if (d === poprzedniDzien(dzis)) return 'wczoraj';
  return czesci(ms).r === czesci(teraz).r ? formatDnia.format(ms) : formatDniaRok.format(ms);
}
export const godzinaMinuta = (ms: number): string => formatGodziny.format(ms);

/** „18 listopada, godz. 23:59”, „dziś, godz. 14:59”. */
export const opisMomentu = (ms: number, teraz: number): string => `${nazwaDnia(ms, teraz)}, godz. ${godzinaMinuta(ms)}`;

/** Etykieta stanu, zawsze widoczna: TODAY = dane na żywo (z godziną ostatniego odświeżenia), PRZESZŁOŚĆ = moment archiwum. */
export function etykietaStanu(stan: StanOsi, teraz: number, odswiezono?: number | null): string {
  if (stan.tryb === 'przeszlosc' && stan.na !== null) return `Stan na ${opisMomentu(stan.na, teraz)}`;
  return odswiezono ? `Stan na teraz, odświeżone o ${godzinaMinuta(odswiezono)}` : 'Stan na teraz';
}

/** Okno komunikatów w zdaniu: TODAY „z ostatnich 24 godzin”, PRZESZŁOŚĆ „z 24 godzin przed tą chwilą”. */
export function opisOkna(okres: '1h' | '24h' | '7d', archiwum: boolean): string {
  const ile = { '1h': archiwum ? 'godziny' : 'ostatniej godziny', '24h': archiwum ? '24 godzin' : 'ostatnich 24 godzin', '7d': archiwum ? '7 dni' : 'ostatnich 7 dni' }[okres];
  return archiwum ? `Komunikaty z ${ile} przed tą chwilą.` : `Komunikaty z ${ile}.`;
}

/** Opis przedziału: „18 listopada” albo „18 listopada, 14:00-15:00”. */
export function opisPrzedzialu(p: Przedzial, krok: Krok, teraz: number): string {
  if (krok === 'dzien') return nazwaDnia(p.od, teraz);
  return `${nazwaDnia(p.od, teraz)}, ${godzinaMinuta(p.od)}-${p.do > teraz ? 'teraz' : godzinaMinuta(p.do)}`;
}

/** Opis słupka dla czytników i dymka: nigdy „0” przy luce; przy luce częściowej „co najmniej”. */
export function opisSlupka(s: Slupek, krok: Krok, teraz: number): string {
  const kiedy = opisPrzedzialu(s, krok, teraz);
  switch (s.stan) {
    case 'ladowanie': return `${kiedy}: wczytujemy`;
    case 'brak': case 'nieznany': return `${kiedy}: brak w naszych danych`;
    case 'czesciowy': return `${kiedy}: co najmniej ${liczbaKomunikatow(s.liczba ?? 0)}, dane niepełne`;
    default: return `${kiedy}: ${liczbaKomunikatow(s.liczba ?? 0)}`;
  }
}

export interface PodpisOsi { tekst: string; /** Procent szerokości osi. */ pozycja: number; wyrownanie: 'start' | 'srodek' | 'koniec' }

/**
 * Podpisy pod osią. Oś dni: 4 dni rozłożone równo, pod środkiem słupka (pierwszy przy lewej, ostatni przy prawej krawędzi).
 * Oś godzin: pełne godziny co 6 (0:00, 6:00, 12:00, 18:00) przy początku przedziału.
 */
export function podpisyOsi(lista: Przedzial[], krok: Krok, teraz: number): PodpisOsi[] {
  const n = lista.length;
  if (!n) return [];
  if (krok === 'godzina') {
    return lista.map((p, i) => ({ p, i })).filter(({ p }) => czesci(p.od).g % 6 === 0 && czesci(p.od).min === 0)
      .map(({ p, i }) => ({ tekst: godzinaMinuta(p.od), pozycja: (i / n) * 100, wyrownanie: 'start' as const }));
  }
  const indeksy = [...new Set([0, Math.round((n - 1) / 3), Math.round((2 * (n - 1)) / 3), n - 1])];
  return indeksy.map(i => ({
    tekst: i === n - 1 && lista[i].do > teraz ? 'dziś' : formatKrotki.format(lista[i].od),
    pozycja: i === 0 ? 0 : i === n - 1 ? 100 : ((i + 0.5) / n) * 100,
    wyrownanie: i === 0 ? 'start' as const : i === n - 1 ? 'koniec' as const : 'srodek' as const,
  }));
}

/**
 * Podpis kreskowania (jedna linia): ile przedziałów bez pełnych danych i dlaczego (źródła bez odpowiedzi, retencja).
 * `nazwa` zamienia slug źródła na nazwę z warstwy/. Pusty tekst, gdy luk nie ma.
 */
export function opisLuk(slupki: Slupek[], krok: Krok, nazwa: (slug: string) => string = s => s): string {
  const luki = slupki.filter(kreskowany);
  if (!luki.length) return '';
  const ile = krok === 'dzien' ? ileDni(luki.length) : ileGodzin(luki.length);
  const zrodla = [...new Set(luki.flatMap(s => s.zrodla))].map(nazwa);
  const powody: string[] = [];
  if (zrodla.length) powody.push(`nie odpowiadało: ${zrodla.slice(0, 2).join(', ')}${zrodla.length > 2 ? ` i ${zrodla.length - 2} inne` : ''}`);
  if (luki.some(s => s.lukaRetencji)) powody.push('część starszych wpisów usunięto zgodnie z zasadami przechowywania');
  if (luki.some(s => s.stan === 'nieznany')) powody.push('serwer nie podał liczby');
  return `Kreskowane: brak w naszych danych, nie zero (${ile})${powody.length ? `: ${powody.join('; ')}` : ''}.`;
}

/** „1 źródło”, „2 źródła”, „5 źródeł”. */
export const ileZrodel = (n: number) => odmiana(n, ['źródło', 'źródła', 'źródeł']);

/**
 * Luki stanu na moment w jednej krótkiej linii baneru (policzalne, bez nazw: te są w szczegółach). Pusty tekst, gdy luk nie ma.
 * Przykład: „Dane niepełne: 1 źródło bez odpowiedzi, 2 komunikaty bez wersji z tej chwili.”
 */
export function opisBrakowKrotko(braki: BrakDanych[], bezHistorii: number): string {
  const czesci: string[] = [];
  const zrodla = new Set(braki.filter(b => b.powod === 'luka_pobierania').flatMap(b => b.zrodla)).size;
  if (zrodla) czesci.push(`${ileZrodel(zrodla)} bez odpowiedzi`);
  if (bezHistorii > 0) czesci.push(`${liczbaKomunikatow(bezHistorii)} bez wersji z tej chwili`);
  else if (braki.some(b => b.powod === 'historia_niepelna')) czesci.push('część komunikatów bez wersji z tej chwili');
  if (braki.some(b => b.powod === 'luka_retencji')) czesci.push('część starszych wpisów usunięta');
  return czesci.length ? `Dane niepełne: ${czesci.join(', ')}.` : '';
}

/** Krótki podpis luk osi pod histogramem (pełny opis: opisLuk, w szczegółach). */
export function opisLukKrotko(slupki: Slupek[], krok: Krok): string {
  const n = slupki.filter(kreskowany).length;
  if (!n) return 'Słupki: liczba komunikatów, nie poziom zagrożenia.';
  return `Kreskowane = brak w naszych danych, nie zero (${krok === 'dzien' ? ileDni(n) : ileGodzin(n)}).`;
}

/** Krótki opis luk stanu na moment (baner archiwum): źródła bez odpowiedzi, wpisy bez wersji z tamtej chwili, retencja. */
export function opisBrakowNa(braki: BrakDanych[], bezHistorii: number, nazwa: (slug: string) => string = s => s): string {
  const czesci: string[] = [];
  const zrodla = [...new Set(braki.filter(b => b.powod === 'luka_pobierania').flatMap(b => b.zrodla))].map(nazwa);
  if (zrodla.length) czesci.push(`w tej chwili nie odpowiadało: ${zrodla.slice(0, 2).join(', ')}${zrodla.length > 2 ? ` i ${zrodla.length - 2} inne` : ''}`);
  if (bezHistorii > 0 || braki.some(b => b.powod === 'historia_niepelna')) {
    czesci.push(bezHistorii > 0 ? `${liczbaKomunikatow(bezHistorii)} bez wersji z tej chwili (nie pokazujemy)` : 'część komunikatów bez wersji z tej chwili');
  }
  if (braki.some(b => b.powod === 'luka_retencji')) czesci.push('część starszych wpisów usunięto zgodnie z zasadami przechowywania');
  return czesci.length ? `Dane niepełne: ${czesci.join('; ')}.` : '';
}

// ---------------------------------------------------------------- odpowiedź wpisy/?na=

export interface StronaNa { wyniki: Wpis[]; nastepna: boolean; pominiete: number; bezHistorii: number; na: string | null; lukaRetencji: boolean; brakDanych: BrakDanych[] }

/**
 * Strona wpisy/?na= po walidacji: rekord `brak_danych: true` (wersji z tamtej chwili nie znamy albo nie wolno jej pokazać) liczymy
 * osobno jako `bezHistorii` (nie jako zły format) i nie pokazujemy go na mapie. Zła struktura strony to wyjątek.
 */
export function walidujStroneNa(x: unknown): StronaNa {
  if (!jestObiektem(x) || !Array.isArray(x.results) || !('next' in x) || !(x.next === null || typeof x.next === 'string')) throw new BladFormatu('strona wyników');
  const wyniki: Wpis[] = [];
  let pominiete = 0, bezHistorii = 0;
  for (const r of x.results) {
    if (jestObiektem(r) && r.brak_danych === true) { bezHistorii++; continue; }
    const w = walidujWpis(r);
    if (w === null) pominiete++; else wyniki.push(w);
  }
  return {
    wyniki, nastepna: typeof x.next === 'string', pominiete, bezHistorii,
    na: typeof x.na === 'string' ? x.na : null, lukaRetencji: x.luka_retencji === true, brakDanych: walidujBraki(x.brak_danych),
  };
}

// ---------------------------------------------------------------- dane próbne

/** Okno próbnej luki źródła (dni wstecz od dziś: od 6 do 4) i próg próbnej retencji (starsze niż 25 dni). */
const PROBNA_LUKA = { odDni: 6, doDni: 4, zrodlo: 'wczk-lubuskie' };
const PROBNA_RETENCJA_DNI = 25;

/** Próbna odpowiedź os/ w formacie API (przechodzi przez walidujOs): liczby z próbnych wpisów, jedna luka źródła i retencja. */
export function probnaOs(od: number, doCzasu: number, krok: Krok, teraz: number, wpisy: Pick<Wpis, 'opublikowano_at' | 'pewnosc_lokalizacji' | 'klasa'>[]): unknown {
  const lukaOd = teraz - PROBNA_LUKA.odDni * DOBA, lukaDo = teraz - PROBNA_LUKA.doDni * DOBA;
  const prog = teraz - PROBNA_RETENCJA_DNI * DOBA;
  const policzalne = wpisy.filter(w => w.klasa === 'zwykly' && w.pewnosc_lokalizacji >= 0.8).map(w => Date.parse(w.opublikowano_at));
  const kubelki = przedzialy(od, Math.min(doCzasu, teraz), krok).map(p => {
    const lukaZrodel = p.od < lukaDo && p.do > lukaOd ? [PROBNA_LUKA.zrodlo] : [];
    const lukaRetencji = p.od < prog;
    const n = policzalne.filter(t => t >= p.od && t < p.do).length;
    return { od: new Date(p.od).toISOString(), do: new Date(p.do).toISOString(), liczba: n === 0 && (lukaRetencji || lukaZrodel.length) ? null : n, w_przegladzie: 0, luka_retencji: lukaRetencji, luka_zrodel: lukaZrodel };
  });
  return { krok, kubelki, luka_retencji: kubelki.some(k => k.luka_retencji), brak_danych: [] };
}

/** Próbne braki stanu na moment: luka źródła, gdy moment wypada w próbnym oknie luki. */
export function probneBrakiNa(na: number, teraz: number): BrakDanych[] {
  const lukaOd = teraz - PROBNA_LUKA.odDni * DOBA, lukaDo = teraz - PROBNA_LUKA.doDni * DOBA;
  return na >= lukaOd && na < lukaDo ? [{ powod: 'luka_pobierania', zrodla: [PROBNA_LUKA.zrodlo], od: lukaOd, do: na }] : [];
}
