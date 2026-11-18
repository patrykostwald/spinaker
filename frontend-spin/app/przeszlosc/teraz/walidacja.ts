import type { Bbox, KodWarstwy, LiniaStanu, Stan, StatusZdarzenia, Warstwa, Wpis, Zasieg, Zdarzenie, Zrodlo } from './typy';

/**
 * Walidacja odpowiedzi API „Teraz” (GET /api/teraz/{warstwy,wpisy,zdarzenia,stan}/). Poprawny składniowo JSON o złej strukturze
 * nie może przerwać renderowania ani udawać pustej listy: zła struktura całej odpowiedzi to wyjątek (czyli stan „dane niedostępne”),
 * a pojedynczy rekord o złym formacie jest pomijany i liczony (`pominiete`), żeby interfejs mógł o tym powiedzieć.
 * Moduł jest czysty (bez Reacta i sieci).
 */
export class BladFormatu extends Error {
  constructor(co: string) {
    super(`Serwer odpowiedział w nieznanym formacie (${co}).`);
    this.name = 'BladFormatu';
  }
}

type Obiekt = Record<string, unknown>;
const jestObiektem = (x: unknown): x is Obiekt => typeof x === 'object' && x !== null && !Array.isArray(x);
const jestTekstem = (x: unknown): x is string => typeof x === 'string';
const jestLiczba = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const czas = (x: unknown): x is string => jestTekstem(x) && Number.isFinite(Date.parse(x));
const tekstLubNull = (x: unknown): string | null => (jestTekstem(x) ? x : null);

const STATUSY: readonly string[] = ['komunikat_oficjalny', 'zgloszone', 'potwierdzone', 'ocena', 'odwolane'];
const ZASIEGI: readonly string[] = ['obszar', 'przyblizony', 'brak'];

function bbox(x: unknown): Bbox | null {
  return Array.isArray(x) && x.length === 4 && x.every(jestLiczba) ? [x[0], x[1], x[2], x[3]] : null;
}

/** Wpis z API albo null, gdy brakuje pól potrzebnych do pokazania go uczciwie (id, warstwa, tytuł, czas publikacji). */
export function walidujWpis(x: unknown): Wpis | null {
  if (!jestObiektem(x)) return null;
  if (!jestLiczba(x.id) || !jestTekstem(x.warstwa) || !jestTekstem(x.tytul) || !czas(x.opublikowano_at)) return null;
  if (x.teryt !== undefined && !(Array.isArray(x.teryt) && x.teryt.every(jestTekstem))) return null;
  const teryt = (x.teryt as string[] | undefined) ?? [];
  // nieznany albo brakujący zasięg przy kodach liczymy jako przybliżony: nie poszerzamy zasięgu ponad źródło
  const zasieg: Zasieg = jestTekstem(x.zasieg) && ZASIEGI.includes(x.zasieg) ? (x.zasieg as Zasieg) : teryt.length ? 'przyblizony' : 'brak';
  return {
    id: x.id,
    zrodlo: jestTekstem(x.zrodlo) ? x.zrodlo : '',
    warstwa: x.warstwa as KodWarstwy,
    tytul: x.tytul,
    tresc: jestTekstem(x.tresc) ? x.tresc : '',
    link: jestTekstem(x.link) ? x.link : '',
    opublikowano_at: x.opublikowano_at,
    czas_zrodlowy_at: czas(x.czas_zrodlowy_at) ? x.czas_zrodlowy_at : null,
    // brak pola to brak pewności co do godziny: pokazujemy samą datę
    dokladna_godzina_publikacji: x.dokladna_godzina_publikacji === true,
    pobrano_at: czas(x.pobrano_at) ? x.pobrano_at : null,
    atrybucja: jestTekstem(x.atrybucja) ? x.atrybucja.trim() : '',
    miejsce: jestTekstem(x.miejsce) ? x.miejsce : '',
    klasa: jestTekstem(x.klasa) ? (x.klasa as Wpis['klasa']) : 'nieznana',
    teryt,
    szerokosc: jestLiczba(x.szerokosc) ? x.szerokosc : null,
    dlugosc: jestLiczba(x.dlugosc) ? x.dlugosc : null,
    bbox: bbox(x.bbox),
    dokladnosc: jestTekstem(x.dokladnosc) ? (x.dokladnosc as Wpis['dokladnosc']) : 'brak',
    pewnosc_lokalizacji: jestLiczba(x.pewnosc_lokalizacji) ? x.pewnosc_lokalizacji : 0,
    zasieg,
  };
}

export function walidujZdarzenie(x: unknown): Zdarzenie | null {
  if (!jestObiektem(x)) return null;
  if (!jestLiczba(x.id) || !jestTekstem(x.status) || !STATUSY.includes(x.status) || !Array.isArray(x.wpisy)) return null;
  if (!czas(x.pierwszy_wpis_at) || !czas(x.ostatni_wpis_at)) return null;
  const wpisy = x.wpisy.map(walidujWpis).filter((w): w is Wpis => w !== null);
  return {
    id: x.id,
    status: x.status as StatusZdarzenia,
    tytul_roboczy: jestTekstem(x.tytul_roboczy) ? x.tytul_roboczy : '',
    pierwszy_wpis_at: x.pierwszy_wpis_at,
    ostatni_wpis_at: x.ostatni_wpis_at,
    przygotowane_automatycznie: x.przygotowane_automatycznie !== false,
    zweryfikowal: tekstLubNull(x.zweryfikowal),
    zweryfikowano_at: tekstLubNull(x.zweryfikowano_at),
    wpisy,
    odrzucone_wpisy: x.wpisy.length - wpisy.length,
  };
}

function swiezosc(x: Obiekt) {
  return {
    ostatnie_pobranie_at: tekstLubNull(x.ostatnie_pobranie_at),
    ostatni_sukces_at: tekstLubNull(x.ostatni_sukces_at),
    liczba_wpisow_24h: jestLiczba(x.liczba_wpisow_24h) ? x.liczba_wpisow_24h : 0,
    // brak pola nie znaczy „wszystko w porządku”: niepewność liczymy na niekorzyść danych
    luka: x.luka !== false,
    blad: x.blad === true,
  };
}

function walidujZrodlo(x: unknown): Zrodlo | null {
  if (!jestObiektem(x) || !jestTekstem(x.slug) || !jestTekstem(x.nazwa)) return null;
  return { slug: x.slug, nazwa: x.nazwa, instytucja: jestTekstem(x.instytucja) ? x.instytucja : '', czestotliwosc_s: jestLiczba(x.czestotliwosc_s) ? x.czestotliwosc_s : 0, ...swiezosc(x) };
}

function walidujWarstwe(x: unknown): Warstwa | null {
  // `wylaczona` jest częścią kontraktu: warstwa bez tego pola jest pomijana (nie zgadujemy, czy redakcja ją wycofała)
  if (!jestObiektem(x) || !jestTekstem(x.warstwa) || !jestTekstem(x.nazwa) || typeof x.wylaczona !== 'boolean') return null;
  const zrodla = Array.isArray(x.zrodla) ? x.zrodla.map(walidujZrodlo).filter((z): z is Zrodlo => z !== null) : [];
  return { warstwa: x.warstwa as KodWarstwy, nazwa: x.nazwa, wylaczona: x.wylaczona, zrodla, ...swiezosc(x) };
}

/** Odpowiedź warstwy/: tablica. Warstwa o złym formacie jest pomijana; gdy żadna nie przeszła, to awaria, nie „brak warstw”. */
export function walidujWarstwy(x: unknown): Warstwa[] {
  if (!Array.isArray(x)) throw new BladFormatu('warstwy');
  const warstwy = x.map(walidujWarstwe).filter((w): w is Warstwa => w !== null);
  if (x.length > 0 && warstwy.length === 0) throw new BladFormatu('warstwy');
  return warstwy;
}

function walidujLinie(x: unknown): LiniaStanu | null {
  if (!jestObiektem(x) || !jestTekstem(x.warstwa) || !jestTekstem(x.ostatnie_pobranie) || !jestTekstem(x.komunikaty)) return null;
  return { warstwa: x.warstwa as KodWarstwy, ostatnie_pobranie: x.ostatnie_pobranie, komunikaty: x.komunikaty, komunikat: jestTekstem(x.komunikat) ? x.komunikat : '' };
}

/** Odpowiedź stan/. Odrzucone wiersze są liczone (`pominiete`): bez nich „brak aktywnych źródeł” byłby fałszywy. */
export function walidujStan(x: unknown): Stan {
  if (!jestObiektem(x) || !jestTekstem(x.informacja) || !Array.isArray(x.warstwy)) throw new BladFormatu('stan');
  const warstwy = x.warstwy.map(walidujLinie).filter((l): l is LiniaStanu => l !== null);
  return { informacja: x.informacja, warstwy, pominiete: x.warstwy.length - warstwy.length };
}

/**
 * Strona DRF: `results` musi być tablicą, a `next` jest obowiązkowy (tekst albo jawny null). Brak `next` to błąd struktury,
 * nie koniec listy: inaczej uszkodzona odpowiedź wyglądałaby na kompletną. Rekordy walidowane `waliduj`; nieprawidłowe liczone w `pominiete`.
 */
export function walidujStrone<T>(x: unknown, waliduj: (rekord: unknown) => T | null): { wyniki: T[]; nastepna: boolean; pominiete: number } {
  if (!jestObiektem(x) || !Array.isArray(x.results) || !('next' in x) || !(x.next === null || jestTekstem(x.next))) throw new BladFormatu('strona wyników');
  const wyniki: T[] = [];
  let pominiete = 0;
  for (const rekord of x.results) {
    const poprawny = waliduj(rekord);
    if (poprawny === null) pominiete++; else wyniki.push(poprawny);
  }
  return { wyniki, nastepna: jestTekstem(x.next), pominiete };
}
