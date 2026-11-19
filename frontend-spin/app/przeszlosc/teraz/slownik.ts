import plik from '../../../public/teraz/teryt-powiaty.json';

/**
 * Słownik powiatów i miast na prawach powiatu (kody TERYT, 4 cyfry). Jedno źródło prawdy to statyczny plik
 * public/teraz/teryt-powiaty.json: ten sam plik jest dostępny publicznie pod /teraz/teryt-powiaty.json, a tutaj jest
 * dołączony do kodu strony, żeby nazwy były znane od pierwszego renderu (bez migotania „powiat o kodzie 1813”).
 * Dane pochodzą z Państwowego Rejestru Granic (GUGiK, jednostki administracyjne, stan z 10.11.2026), którego kody i nazwy
 * biorą się z rejestru TERYT (GUS). Pole `zweryfikowano_z_rejestrem` w pliku mówi, że lista pochodzi z oficjalnego rejestru.
 */
export interface PowiatTeryt {
  /** 4 cyfry: 2 cyfry województwa i 2 cyfry powiatu (01 do 60 ziemskie, 61 i dalej miasta na prawach powiatu). */
  kod: string;
  /** Nazwa jak w rejestrze: „przemyski” (powiat ziemski) albo „Kraków” (miasto na prawach powiatu). */
  nazwa: string;
  miasto: boolean;
  /** Kod województwa (2 cyfry). */
  woj: string;
  /** Nazwa w dopełniaczu do zdań typu „dla powiatu przemyskiego”, „dla miasta Krakowa”. */
  dopelniacz: string;
}

interface Surowy { kod: string; nazwa: string; miasto?: boolean; dopelniacz?: string }
interface PlikSlownika {
  zrodlo: string;
  data: string;
  zweryfikowano_z_rejestrem: boolean;
  wojewodztwa: { kod: string; nazwa: string }[];
  powiaty: Surowy[];
}

const dane = plik as unknown as PlikSlownika;

/** Dopełniacz powiatu ziemskiego powstaje z nazwy przymiotnikowej: „przemyski” to „przemyskiego”, „łódzki wschodni” to „łódzkiego wschodniego”. */
export const dopelniaczPowiatuZiemskiego = (nazwa: string): string => nazwa.split(' ').map(s => s.replace(/i$/, 'iego')).join(' ');

/** Dopełniacz nazwy województwa: „podkarpackie” to „podkarpackiego”, „kujawsko-pomorskie” to „kujawsko-pomorskiego”. */
export const dopelniaczWojewodztwa = (nazwa: string): string => nazwa.replace(/ie$/, 'iego');

export const SLOWNIK_META = {
  zrodlo: dane.zrodlo,
  data: dane.data,
  zweryfikowano: dane.zweryfikowano_z_rejestrem === true,
} as const;

export const WOJEWODZTWA_SLOWNIK: { kod: string; nazwa: string }[] = dane.wojewodztwa;

export const POWIATY: PowiatTeryt[] = dane.powiaty.map(p => ({
  kod: p.kod,
  nazwa: p.nazwa,
  miasto: p.miasto === true,
  woj: p.kod.slice(0, 2),
  dopelniacz: p.dopelniacz ?? dopelniaczPowiatuZiemskiego(p.nazwa),
}));

const PO_KODZIE = new Map<string, PowiatTeryt>(POWIATY.map(p => [p.kod, p]));
export const powiatOKodzie = (kod: string): PowiatTeryt | undefined => PO_KODZIE.get(kod);

const nazwaWojewodztwa = (kod2: string): string => WOJEWODZTWA_SLOWNIK.find(w => w.kod === kod2)?.nazwa ?? '';

/** „powiat przemyski” albo „Kraków (miasto na prawach powiatu)”. */
export const nazwaPowiatu = (p: PowiatTeryt): string => (p.miasto ? `${p.nazwa} (miasto na prawach powiatu)` : `powiat ${p.nazwa}`);

/** Z województwem, do list wyboru: „powiat przemyski, podkarpackie”. */
export const pelnaNazwaPowiatu = (p: PowiatTeryt): string => `${nazwaPowiatu(p)}, ${nazwaWojewodztwa(p.woj)}`;

/** Do zdań: „dla powiatu przemyskiego”, „dla miasta Krakowa”. */
export const dlaPowiatu = (p: PowiatTeryt): string => (p.miasto ? `dla miasta ${p.dopelniacz}` : `dla powiatu ${p.dopelniacz}`);
