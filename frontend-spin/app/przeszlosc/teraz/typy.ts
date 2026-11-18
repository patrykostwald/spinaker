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

/**
 * Jak czytać kody TERYT wpisu (pole `zasieg` z API): `obszar` = zasięg podany przez źródło, `przyblizony` = kod szerszy niż
 * źródło (np. województwo dla alertu RCB do wybranych powiatów; szczegóły tylko w `miejsce`), `brak` = bez kodów.
 * Nigdy nie poszerzamy zasięgu ponad źródło: kod przybliżony nie znaczy „całe województwo”.
 */
export type Zasieg = 'obszar' | 'przyblizony' | 'brak';

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
  /** Czas zdarzenia według źródła (np. godzina sekcji alertu RCB), gdy różni się od publikacji; null, gdy go nie ma. */
  czas_zrodlowy_at: string | null;
  /** false: źródło podało tylko datę (backend zapisuje techniczną północ), więc pokazujemy i eksportujemy samą datę. */
  dokladna_godzina_publikacji: boolean;
  /** null: brak albo niepoprawny czas pobrania („brak danych”); nigdy nie zastępujemy go czasem publikacji. */
  pobrano_at: string | null;
  /** Podpis źródła z API dla tego wpisu (np. IMGW: informacja o przetworzeniu danych); pokazywany w karcie i w CSV. */
  atrybucja: string;
  /** Miejsce słowami ze źródła (np. lista powiatów z alertu RCB, po jednej nazwie w linii). */
  miejsce: string;
  klasa: KlasaWpisu;
  /** Kody TERYT z zachowaniem początkowych zer (2 cyfry: województwo, 4: powiat, 7: gmina). */
  teryt: string[];
  szerokosc: number | null;
  dlugosc: number | null;
  bbox: Bbox | null;
  dokladnosc: Dokladnosc;
  /** 0 do 1. */
  pewnosc_lokalizacji: number;
  zasieg: Zasieg;
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
  /** Tylko po stronie klienta: powiązane wpisy odrzucone przez walidację (wtedy status części wpisów jest nieznany). */
  odrzucone_wpisy: number;
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
  /** Wyłącznik redakcji (WylacznikKategorii): wyłączona warstwa znika z całego interfejsu, także z pamięci i cache klienta. */
  wylaczona: boolean;
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
  /** Tylko po stronie klienta: wiersze stanu odrzucone przez walidację (stan źródeł jest wtedy niepewny). */
  pominiete: number;
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
export type StatusKlucz = StatusZdarzenia | 'brak' | 'niedostepny';

/** Wynik pobrania listy (wpisów, zdarzeń): `uciete` = są starsze rekordy poza limitem stron, `pominiete` = rekordy o nieznanym formacie. */
export interface WynikListy<T> { wyniki: T[]; uciete: boolean; pominiete: number }

export interface WidokWpisu {
  wpis: Wpis;
  status: StatusKlucz;
  zdarzenie: Zdarzenie | null;
}
