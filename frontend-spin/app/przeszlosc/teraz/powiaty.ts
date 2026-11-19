import type { Okres, Wpis } from './typy';
import { POWIATY, dopelniaczWojewodztwa, powiatOKodzie, type PowiatTeryt } from './slownik';
import { calyRegionZMiejsca, maZastrzezenia, maWylaczenia, rozbierzMiejsce, wojewodztwoOKodzie, zakresyWojewodztw, znacznikiMiejsca, type JednostkaZMiejsca } from './teryt';

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

/**
 * Jak wpis dotyczy powiatu. Kod województwa liczy się jako „całe województwo” tylko przy potwierdzonym zasięgu (`zasieg: obszar`).
 * Przy zasięgu przybliżonym (np. alert RCB do wybranych powiatów) rozstrzyga lista jednostek z pola `miejsce` (recenzja PR #38, P1-2):
 *  - `wymieniony`: nazwa powiatu jest na liście,
 *  - `mozliwy`: niejednoznaczne (np. na liście jest miasto Chełm, a nie ma powiatu chełmskiego): „sprawdź treść komunikatu”,
 *  - `bezListy`: źródło nie podało jednostek (także wpis o uogólnionym położeniu),
 *  - `wylaczony`: komunikat wprost wyłącza ten powiat („z wyłączeniem powiatu X”): „sprawdź treść”, nie „wymieniony” (R38d, P1-1).
 * Zasada: nigdy nie poszerzamy zasięgu ponad źródło, a parser jest zachowawczy: przy wyłączeniu, zaleceniu albo niejasnych
 * odbiorcach najwyżej „możliwe”; „wymieniony” i „nie ma na liście” tylko przy czystej, kompletnej liście.
 */
export type Zakres = 'powiat' | 'gmina' | 'wymieniony' | 'wojewodztwo' | 'mozliwy' | 'bezListy';
/**
 * Z6P8 (decyzja koordynatora): nigdy nie twierdzimy, że powiat NIE jest objęty komunikatem. Nie ma zakresów „nie ma na liście”
 * ani „komunikat wyłącza Twój powiat”: wewnętrzne wyniki dopasowania `pozaLista` i `wylaczony` są tu zawsze „możliwe”
 * (neutralnie: sprawdź w źródle).
 */
const naZakres = (d: DopasowanieListy): Zakres => (d === 'wymieniony' || d === 'bezListy' ? d : 'mozliwy');
const WAGA: Record<Zakres, number> = { powiat: 8, gmina: 7, wymieniony: 6, wojewodztwo: 5, mozliwy: 4, bezListy: 2 };
/** Zakresy, przy których wpis stoi na liście powiatu; `bezListy` idzie do osobnej grupy „z Twojego województwa”. */
export const ZAKRESY_POWIATU: ReadonlySet<Zakres> = new Set<Zakres>(['powiat', 'gmina', 'wymieniony', 'wojewodztwo', 'mozliwy']);

/** Słowo `q` to odmiana słowa `slowo` („krakowie” od „krakow”, „chelmskiego” od „chelmski”); samo słowo też pasuje. */
const odmianaSlowa = (q: string, slowo: string): boolean => {
  if (q === slowo) return true;
  const r = rdzen(slowo);
  return r.length >= 3 && q.startsWith(r) && q.length - r.length <= NAJDLUZSZA_KONCOWKA;
};
const odmianaNazwy = (linia: string, nazwa: string): boolean => {
  const a = linia.split(' ');
  const b = nazwa.split(' ');
  return a.length === b.length && a.every((s, i) => odmianaSlowa(s, b[i]));
};
/** Z kilku dopasowań odmiany zostają te o najdłuższym rdzeniu nazwy (suma długości rdzeni jej słów). */
const najdokladniejsze = <T extends { nazwa: string }>(kandydaci: T[]): T[] => {
  const waga = (k: T) => k.nazwa.split(' ').reduce((suma, slowo) => suma + rdzen(slowo).length, 0);
  const max = Math.max(0, ...kandydaci.map(waga));
  return kandydaci.filter(k => waga(k) === max);
};
const bezSlowPomijanych = (tekst: string): string => normalizuj(tekst).split(' ').filter(s => s && !POMIJANE.has(s)).join(' ');

/** Miasto na prawach powiatu i powiat ziemski o tej samej nazwie (Chełm i chełmski, Biała Podlaska i bialski). */
const paraMiastoPowiat = (a: PowiatTeryt, b: PowiatTeryt): boolean => {
  if (a.woj !== b.woj || a.miasto === b.miasto) return false;
  const miasto = normalizuj((a.miasto ? a : b).nazwa).split(' ')[0];
  const ziemski = normalizuj((a.miasto ? b : a).nazwa).split(' ')[0];
  return odmianaSlowa(ziemski, miasto);
};

export type DopasowanieListy = 'wymieniony' | 'mozliwy' | 'wylaczony' | 'pozaLista' | 'bezListy';

interface Kandydat { p: PowiatTeryt; nazwa: string }

/** Powiaty pewnie wskazane przez jednostki (`wymienione`) i to, czy któraś jednostka może wskazywać `powiat` (`mozliwy`). */
function trafienia(jednostki: JednostkaZMiejsca[], powiat: PowiatTeryt, kandydaci: Kandydat[], liczbaWojewodztw: number): { wymienione: Set<PowiatTeryt>; mozliwy: boolean } {
  const wymienione = new Set<PowiatTeryt>();
  let mozliwy = false;
  for (const jednostka of jednostki) {
    if (jednostka.woj && jednostka.woj !== powiat.woj) continue;
    const linia = bezSlowPomijanych(jednostka.nazwa);
    if (!linia) continue;
    const pewna = jednostka.typ !== 'gmina' && (jednostka.woj !== null || liczbaWojewodztw <= 1);
    const trafione: PowiatTeryt[] = [];
    const dokladne = kandydaci.filter(k => k.nazwa === linia);
    if (dokladne.length) trafione.push(...dokladne.map(k => k.p));
    else {
      // „chełmskim” pasuje do powiatu chełmskiego i (przez krótki rdzeń) do miasta Chełm: wygrywa dłuższe dopasowanie rdzenia
      const odmienione = najdokladniejsze(kandydaci.filter(k => odmianaNazwy(linia, k.nazwa)));
      if (odmienione.length === 1) trafione.push(odmienione[0].p);
      else if (odmienione.some(k => k.p === powiat)) mozliwy = true;
    }
    // typ jednostki: miasto nie jest powiatem ziemskim (miasto Puck to nie powiat pucki, R38d Z6P6 pkt 1); powiat ziemski o tej
    // samej nazwie to najwyżej „możliwe”
    const zgodne = jednostka.typ === 'miasto' ? trafione.filter(p => p.miasto) : trafione;
    const innego = jednostka.typ === 'miasto' ? trafione.filter(p => !p.miasto) : [];
    if (pewna) zgodne.forEach(p => wymienione.add(p));
    else if (zgodne.some(p => p === powiat || paraMiastoPowiat(p, powiat))) mozliwy = true;
    if (innego.some(p => p === powiat || paraMiastoPowiat(p, powiat))) mozliwy = true;
  }
  return { wymienione, mozliwy };
}

/**
 * Czy powiat jest na liście jednostek z `miejsce` (po jednej w linii); dopasowanie z odmianą, tylko w obrębie województwa.
 * Jednostka podpisana przez źródło innym województwem nie dotyczy tego powiatu (dolnośląski powiat świdnicki to nie lubelski).
 * „Wymieniony” wymaga pewnego związku jednostki z województwem: podpisu ze źródła albo komunikatu o jednym województwie
 * (`liczbaWojewodztw` ≤ 1). Jednostka bez województwa przy kilku województwach oraz gmina dają najwyżej „mozliwy”.
 * Znaczniki parsera (R38d): jednostka wyłączona w komunikacie daje „wylaczony”, a wyłączenie w województwie albo lista
 * z nierozpoznanym elementem zamieniają „wymieniony” i „pozaLista” na „mozliwy”.
 */
export function dopasujDoListy(miejsce: string, kodPowiatu: string, liczbaWojewodztw = 1): DopasowanieListy {
  const powiat = powiatOKodzie(kodPowiatu);
  if (!powiat) return 'bezListy';
  const jednostki = rozbierzMiejsce(miejsce);
  const znaczniki = znacznikiMiejsca(miejsce);
  if (!jednostki.length && !znaczniki.wylaczone.length && !znaczniki.ogolne && !znaczniki.nieustalone && !znaczniki.nieustaloneWoj.size) return 'bezListy';
  const kandydaci = POWIATY.filter(p => p.woj === powiat.woj).map(p => ({ p, nazwa: normalizuj(p.nazwa) }));
  const wylaczone = trafienia(znaczniki.wylaczone, powiat, kandydaci, liczbaWojewodztw);
  if (wylaczone.wymienione.has(powiat)) return 'wylaczony';
  const { wymienione, mozliwy } = trafienia(jednostki, powiat, kandydaci, liczbaWojewodztw);
  let wynik: DopasowanieListy;
  if (!jednostki.length) wynik = 'bezListy';
  else if (wymienione.has(powiat)) wynik = 'wymieniony';
  else if (mozliwy || [...wymienione].some(p => paraMiastoPowiat(p, powiat))) wynik = 'mozliwy';
  else wynik = 'pozaLista';
  // wyłączenie w tym województwie (także niepewne dopasowanie wyłączonej jednostki): najwyżej „możliwe”, nigdy „wymieniony”
  const wylaczenie = maWylaczenia(znaczniki, powiat.woj) || wylaczone.mozliwy || [...wylaczone.wymienione].some(p => paraMiastoPowiat(p, powiat));
  if (wylaczenie && wynik === 'wymieniony') wynik = 'mozliwy';
  // wyłączenie albo lista z nierozpoznanym elementem (w tym województwie albo bez znanego województwa): nie mamy prawa
  // powiedzieć „nie ma na liście”
  const nieustalone = znaczniki.nieustalone || znaczniki.nieustaloneWoj.has(powiat.woj);
  if ((wylaczenie || nieustalone) && (wynik === 'pozaLista' || wynik === 'bezListy')) wynik = 'mozliwy';
  return wynik;
}

/** Kod powiatu przy zasięgu przybliżonym: „wymieniony” tylko gdy nazwa i województwo z `miejsce` się zgadzają, inaczej „możliwe”. */
const potwierdzonyPowiat = (wpis: Partial<Pick<Wpis, 'miejsce'>>, kodPowiatu: string, liczbaWojewodztw: number): Zakres => {
  const d = dopasujDoListy(wpis.miejsce ?? '', kodPowiatu, liczbaWojewodztw);
  return d === 'wymieniony' ? d : 'mozliwy';
};

/**
 * Zakres wpisu dla powiatu z kodu województwa `woj` (R38d, Z6P6). Wpis z parsera v6 ma zakres osobno dla każdego województwa
 * (`zakres: lubelskie: lista`) i powiat dopasowujemy tylko do zakresu swojego województwa, nigdy do zbiorczego znacznika:
 *  - `cale`: „całe województwo”, chyba że komunikat wyłącza coś w tym województwie albo jego lista jest niepełna;
 *  - `czesc`: nigdy „całe” ani „nie ma na liście” (nie wiadomo, która to część), najwyżej „wymieniony” przy jednostce z listy;
 *  - `lista`: „nie ma na liście” tylko gdy lista tego województwa jest kompletna (bez znaczników i bez pominiętych elementów).
 * Wpis starszy (bez linii zakresu): dawna heurystyka (R38c, R38d).
 */
function zakresWojewodztwa(wpis: Pick<Wpis, 'teryt'> & Partial<Pick<Wpis, 'zasieg' | 'miejsce'>>, woj: string, kodPowiatu: string, liczbaWojewodztw: number): Zakres {
  const miejsce = wpis.miejsce ?? '';
  const rodzaj = zakresyWojewodztw(miejsce).get(woj);
  if (!rodzaj) {
    // zasięg przybliżony, ale to województwo źródło podało bez jednostek, a jednostki są w innych: całe (R38c, P1);
    // wyłączenie albo niepełna lista w tym województwie (R38d) cofa „całe”, także gdy źródło oznaczyło zasięg jako obszar
    const cale = wpis.zasieg === 'obszar' ? !maZastrzezenia(miejsce, woj) : calyRegionZMiejsca(miejsce, woj);
    return cale ? 'wojewodztwo' : naZakres(dopasujDoListy(miejsce, kodPowiatu, liczbaWojewodztw));
  }
  if (rodzaj === 'cale' && !maZastrzezenia(miejsce, woj)) return 'wojewodztwo';
  return dopasujDoListy(miejsce, kodPowiatu, liczbaWojewodztw) === 'wymieniony' ? 'wymieniony' : 'mozliwy';
}

/** Najwęższy zakres, w jakim wpis dotyczy powiatu (po kodach TERYT wpisu i jego zasięgu), albo null, gdy go nie dotyczy. */
export function zakresDlaPowiatu(wpis: Pick<Wpis, 'teryt'> & Partial<Pick<Wpis, 'zasieg' | 'miejsce'>>, kodPowiatu: string): Zakres | null {
  let wynik: Zakres | null = null;
  const liczbaWojewodztw = new Set(wpis.teryt.map(k => k.slice(0, 2))).size;
  for (const k of wpis.teryt) {
    let z: Zakres | null = null;
    // przy zasięgu przybliżonym kod 4-cyfrowy nie jest potwierdzeniem: potrzebna zgodność nazwy i województwa z danymi wpisu
    if (k === kodPowiatu) z = wpis.zasieg === 'przyblizony' ? potwierdzonyPowiat(wpis, kodPowiatu, liczbaWojewodztw) : 'powiat';
    else if (k.length > 4 && k.startsWith(kodPowiatu)) z = 'gmina';
    else if (k.length === 2 && kodPowiatu.startsWith(k)) z = zakresWojewodztwa(wpis, k, kodPowiatu, liczbaWojewodztw);
    if (z && (wynik === null || WAGA[z] > WAGA[wynik])) wynik = z;
  }
  return wynik;
}

export function zakresTekstem(zakres: Zakres, kodPowiatu: string): string {
  const woj = wojewodztwoOKodzie(kodPowiatu)?.nazwa;
  if (zakres === 'powiat') return 'dotyczy tego powiatu';
  if (zakres === 'gmina') return 'dotyczy gminy w tym powiecie';
  if (zakres === 'wymieniony') return 'Twój powiat jest wymieniony w komunikacie';
  if (zakres === 'mozliwy') return 'możliwe, że dotyczy Twojego powiatu: sprawdź treść komunikatu';
  if (zakres === 'bezListy') return 'Komunikat w Twoim województwie, źródło nie podaje powiatów: sprawdź treść komunikatu';
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

/**
 * Adres do udostępnienia zestawu: tylko widok „Mój powiat”, zestaw powiatów i okres (bez reszty ustawień mapy). Okres jest
 * zawsze w adresie, także domyślny: odbiorca z innym zapamiętanym okresem zobaczy to samo co nadawca.
 */
export function adresZestawu(origin: string, sciezka: string, kody: readonly string[], okres: Okres, probne: boolean): string {
  const q = new URLSearchParams();
  q.set('widok', 'powiat');
  if (kody.length) q.set(PARAMETR_POWIATY, kody.join(','));
  q.set('okres', okres);
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
