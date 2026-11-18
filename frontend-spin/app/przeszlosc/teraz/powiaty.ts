import type { Okres, Wpis } from './typy';
import { OKRES_DOMYSLNY } from './warstwy';
import { POWIATY, dopelniaczWojewodztwa, powiatOKodzie, type PowiatTeryt } from './slownik';
import { wojewodztwoOKodzie } from './teryt';

/**
 * „Mój powiat”: logika bez Reacta. Wyszukiwanie powiatu i miasta na prawach powiatu (także w odmienionej formie:
 * „Krakowie”, „przemyskiego”, „Białej Podlaskiej”), dopasowanie wpisów po kodzie TERYT, parametr `powiaty` w adresie
 * i link do udostępnienia zestawu.
 */
export const MAKS_POWIATOW = 5;
export const PARAMETR_POWIATY = 'powiaty';

/** Małe litery, bez polskich znaków, tylko litery i cyfry rozdzielone spacją („Jastrzębie-Zdrój” to „jastrzebie zdroj”). */
export const normalizuj = (s: string): string =>
  s.toLowerCase().replace(/ł/g, 'l').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();

/** Słowa, które użytkownik może wpisać obok nazwy, a które nie są jej częścią. */
const POMIJANE = new Set(['powiat', 'powiatu', 'powiatem', 'powiecie', 'pow', 'miasto', 'miasta', 'miastem', 'm', 'st', 'na', 'prawach', 'w', 'we', 'woj', 'wojewodztwo']);

/** Rdzeń bez końcowych samogłosek (z odmiany zostaje początek słowa); krótkie słowa zostają w całości. */
const rdzen = (slowo: string): string => {
  const r = slowo.replace(/[aeiouy]+$/, '');
  return r.length >= 3 ? r : slowo;
};

const NAJDLUZSZA_KONCOWKA = 4;

/** 0: wpisany początek słowa (autouzupełnianie), 1: odmieniona forma słowa, null: brak dopasowania. */
function dopasujSlowo(zapytanie: string, slowo: string): 0 | 1 | null {
  if (slowo.startsWith(zapytanie)) return 0;
  const r = rdzen(slowo);
  if (zapytanie.startsWith(r) && zapytanie.length - r.length <= NAJDLUZSZA_KONCOWKA) return 1;
  return null;
}

const kolator = new Intl.Collator('pl');

interface Indeks { powiat: PowiatTeryt; slowa: string[]; pelna: string }
const INDEKS: Indeks[] = POWIATY.map(powiat => {
  const pelna = normalizuj(powiat.nazwa);
  return { powiat, slowa: [...pelna.split(' '), powiat.kod], pelna };
});

/** Powiaty pasujące do wpisanego tekstu, najlepsze pierwsze; puste zapytanie lub same słowa pomijane dają pustą listę. */
export function szukajPowiatow(tekst: string, opcje: { limit?: number; pomin?: readonly string[] } = {}): PowiatTeryt[] {
  const limit = opcje.limit ?? 8;
  const pomin = new Set(opcje.pomin ?? []);
  const slowa = normalizuj(tekst).split(' ').filter(s => s && !POMIJANE.has(s));
  if (!slowa.length) return [];
  const wspolne = slowa.join(' ');
  const wyniki: { powiat: PowiatTeryt; punkty: number }[] = [];
  for (const { powiat, slowa: nazwa, pelna } of INDEKS) {
    if (pomin.has(powiat.kod)) continue;
    let punkty = 0;
    let wszystkie = true;
    for (const [i, s] of slowa.entries()) {
      let najlepszy: number | null = null;
      for (const [j, n] of nazwa.entries()) {
        const d = dopasujSlowo(s, n);
        if (d === null) continue;
        // kolejność słów w nazwie ma znaczenie tylko jako drobny bonus
        const ocena = d * 2 + (i === j ? 0 : 1);
        if (najlepszy === null || ocena < najlepszy) najlepszy = ocena;
      }
      if (najlepszy === null) { wszystkie = false; break; }
      punkty += najlepszy;
    }
    if (!wszystkie) continue;
    if (wspolne === pelna) punkty -= 20;
    else if (pelna.startsWith(wspolne)) punkty -= 5;
    wyniki.push({ powiat, punkty });
  }
  wyniki.sort((a, b) => a.punkty - b.punkty || kolator.compare(a.powiat.nazwa, b.powiat.nazwa) || a.powiat.kod.localeCompare(b.powiat.kod));
  return wyniki.slice(0, limit).map(w => w.powiat);
}

/** Jak wpis dotyczy powiatu: dokładnie powiat, gmina w tym powiecie albo całe województwo. */
export type Zakres = 'powiat' | 'gmina' | 'wojewodztwo';
const WAGA: Record<Zakres, number> = { powiat: 3, gmina: 2, wojewodztwo: 1 };

/** Najwęższy zakres, w jakim wpis dotyczy powiatu (po kodach TERYT wpisu), albo null, gdy go nie dotyczy. */
export function zakresDlaPowiatu(wpis: Pick<Wpis, 'teryt'>, kodPowiatu: string): Zakres | null {
  let wynik: Zakres | null = null;
  for (const k of wpis.teryt) {
    let z: Zakres | null = null;
    if (k === kodPowiatu) z = 'powiat';
    else if (k.length > 4 && k.startsWith(kodPowiatu)) z = 'gmina';
    else if (k.length === 2 && kodPowiatu.startsWith(k)) z = 'wojewodztwo';
    if (z && (wynik === null || WAGA[z] > WAGA[wynik])) wynik = z;
  }
  return wynik;
}

export function zakresTekstem(zakres: Zakres, kodPowiatu: string): string {
  if (zakres === 'powiat') return 'dotyczy tego powiatu';
  if (zakres === 'gmina') return 'dotyczy gminy w tym powiecie';
  const woj = wojewodztwoOKodzie(kodPowiatu)?.nazwa;
  return woj ? `dotyczy całego województwa ${dopelniaczWojewodztwa(woj)}` : 'dotyczy całego województwa';
}

/** Kody województw (2 cyfry) wybranych powiatów, bez powtórzeń: tyle zapytań do API trzeba wysłać. */
export const kodyWojewodztw = (powiaty: readonly string[]): string[] => [...new Set(powiaty.map(k => k.slice(0, 2)))].sort();

/** Poprawne kody: 4 cyfry znane słownikowi, bez powtórzeń, najwyżej MAKS_POWIATOW (kolejność zachowana). */
export const oczyscKody = (kody: readonly unknown[]): string[] => {
  const wynik: string[] = [];
  for (const k of kody) {
    if (typeof k === 'string' && /^[0-9]{4}$/.test(k) && powiatOKodzie(k) && !wynik.includes(k)) wynik.push(k);
    if (wynik.length >= MAKS_POWIATOW) break;
  }
  return wynik;
};

type Wejscie = Record<string, string | string[] | undefined> | URLSearchParams;

/** Parametr `powiaty=1814,0663` z adresu; nieznane kody i nadmiar są pomijane. */
export function parsujPowiaty(wejscie: Wejscie): string[] {
  const surowy = wejscie instanceof URLSearchParams ? wejscie.get(PARAMETR_POWIATY) ?? undefined : wejscie[PARAMETR_POWIATY];
  const tekst = Array.isArray(surowy) ? surowy[0] : surowy;
  return tekst ? oczyscKody(tekst.split(',').map(s => s.trim())) : [];
}

/** Ustawia (albo usuwa) parametr `powiaty` w ciągu zapytania, resztę zostawia. */
export function zapytanieZPowiatami(zapytanie: string, kody: readonly string[]): string {
  const q = new URLSearchParams(zapytanie);
  q.delete(PARAMETR_POWIATY);
  if (kody.length) q.set(PARAMETR_POWIATY, kody.join(','));
  const tekst = q.toString();
  return tekst ? `?${tekst}` : '';
}

/** Adres do udostępnienia zestawu: tylko widok „Mój powiat”, zestaw powiatów i okres (bez reszty ustawień mapy). */
export function adresZestawu(origin: string, sciezka: string, kody: readonly string[], okres: Okres, probne: boolean): string {
  const q = new URLSearchParams();
  q.set('widok', 'powiat');
  if (kody.length) q.set(PARAMETR_POWIATY, kody.join(','));
  if (okres !== OKRES_DOMYSLNY) q.set('okres', okres);
  if (probne) q.set('probne', '1');
  return `${origin}${sciezka}?${q.toString()}`;
}

/** „1 komunikat”, „2 komunikaty”, „5 komunikatów”, „22 komunikaty”. */
export function liczbaKomunikatow(n: number): string {
  const ostatnie = n % 10;
  const dwie = n % 100;
  if (n === 1) return '1 komunikat';
  if (ostatnie >= 2 && ostatnie <= 4 && !(dwie >= 12 && dwie <= 14)) return `${n} komunikaty`;
  return `${n} komunikatów`;
}
