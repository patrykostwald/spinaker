/**
 * Typy kontraktu API „Teraz” (backend/teraz, serializery w api.py: WpisSerializer, ZdarzenieSerializer,
 * WarstwaSerializer, StanSerializer). Endpointy pod /api/teraz/: warstwy/, wpisy/, zdarzenia/, zdarzenia/<id>/, stan/.
 * Pola i wartości wyliczeń są dokładnie z modeli: Warstwa, Klasa, Wpis.Dokladnosc, Zdarzenie.Status.
 */

export type KodWarstwy =
  | 'rcb' | 'imgw_meteo' | 'imgw_hydro' | 'powietrze' | 'pozary' | 'wstrzasy' | 'katastrofy' | 'policja' | 'psp'
  | 'sg' | 'wojsko' | 'drogi' | 'kolej' | 'przestrzen' | 'energetyka' | 'cyber' | 'media' | 'urzedy';

export type KlasaWpisu = 'zwykly' | 'wrazliwy' | 'wojsko_granica' | 'osoba_poszukiwana' | 'infrastruktura' | 'nieznana';

export type Dokladnosc = 'punkt' | 'gmina' | 'powiat' | 'wojewodztwo' | 'kraj' | 'brak';

export type StatusZdarzenia = 'komunikat_oficjalny' | 'zgloszone' | 'potwierdzone' | 'ocena' | 'odwolane';

/** Zasięg: zachód, południe, wschód, północ (stopnie). */
export type Bbox = [number, number, number, number];

export interface Wpis {
  id: number;
  /** Slug źródła (nazwę i instytucję daje warstwy/ w polu zrodla[]). */
  zrodlo: string;
  warstwa: KodWarstwy;
  tytul: string;
  tresc: string;
  link: string;
  opublikowano_at: string;
  pobrano_at: string;
  klasa: KlasaWpisu;
  /** Kody TERYT z zachowaniem początkowych zer (2 cyfry: województwo, 4: powiat, 7: gmina). */
  teryt: string[];
  szerokosc: number | null;
  dlugosc: number | null;
  bbox: Bbox | null;
  dokladnosc: Dokladnosc;
  /** 0 do 1. */
  pewnosc_lokalizacji: number;
}

export interface Zdarzenie {
  id: number;
  status: StatusZdarzenia;
  tytul_roboczy: string;
  pierwszy_wpis_at: string;
  ostatni_wpis_at: string;
  przygotowane_automatycznie: boolean;
  /** Imię redaktora albo null. */
  zweryfikowal: string | null;
  zweryfikowano_at: string | null;
  wpisy: Wpis[];
}

export interface Swiezosc {
  ostatnie_pobranie_at: string | null;
  ostatni_sukces_at: string | null;
  liczba_wpisow_24h: number;
  luka: boolean;
  blad: boolean;
}

export interface Zrodlo extends Swiezosc {
  slug: string;
  nazwa: string;
  instytucja: string;
  czestotliwosc_s: number;
}

export interface Warstwa extends Swiezosc {
  warstwa: KodWarstwy;
  nazwa: string;
  zrodla: Zrodlo[];
}

export interface LiniaStanu {
  warstwa: KodWarstwy;
  /** Gotowe zdanie z API, np. „ostatnie pobranie: 14:32” (albo „ostatnie pobranie: brak danych”). */
  ostatnie_pobranie: string;
  /** Gotowe zdanie z API, np. „komunikatów: 3” (ostatnie 24 godziny). */
  komunikaty: string;
  /** Niepusty przy luce, błędzie albo braku źródeł: „nie mamy pewności, sprawdź Alert RCB i 112”. */
  komunikat: string;
}

export interface Stan {
  /** „To nie jest strona urzędowa”. */
  informacja: string;
  warstwy: LiniaStanu[];
}

/** Paginacja DRF (PageNumberPagination, 50 na stronę, parametr ?page=). */
export interface Strona<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type Okres = '1h' | '24h' | '7d';

/** Wpis z wyliczonym statusem i kolorem, gotowy do narysowania. */
export type StatusKlucz = StatusZdarzenia | 'brak';

export interface WidokWpisu {
  wpis: Wpis;
  status: StatusKlucz;
  zdarzenie: Zdarzenie | null;
}
