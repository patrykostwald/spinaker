import type { Bbox, KodWarstwy, Stan, Strona, Warstwa, Wpis, Zdarzenie, Zrodlo } from '../typy';
import { godzina } from '../czas';

/**
 * DANE PRZYKŁADOWE trybu próbnego (?probne=1 albo NEXT_PUBLIC_TERAZ_PROBNE=1). To nie są prawdziwe komunikaty:
 * treści i miejsca są zmyślone na potrzeby podglądu wyglądu i zachowania mapy. Format jest identyczny z odpowiedziami
 * API (backend/teraz/api.py), czasy liczone względem „teraz”, żeby filtry 1 godz., 24 godz. i 7 dni działały.
 */

const MIN = 60_000;
const iso = (teraz: number, minutTemu: number) => new Date(teraz - minutTemu * MIN).toISOString();

interface Opis { kod: KodWarstwy; nazwa: string; wylaczona?: boolean; zrodla: { slug: string; nazwa: string; instytucja: string; co_s: number; pobranieMin: number; sukcesMin: number; liczba24h: number; blad?: boolean }[] }

const OPISY: Opis[] = [
  { kod: 'rcb', nazwa: 'Alert RCB', zrodla: [{ slug: 'rcb-gov-pl', nazwa: 'Alert RCB na gov.pl', instytucja: 'Rządowe Centrum Bezpieczeństwa', co_s: 60, pobranieMin: 1, sukcesMin: 1, liczba24h: 3 }] },
  { kod: 'imgw_meteo', nazwa: 'Ostrzeżenia meteorologiczne', zrodla: [{ slug: 'imgw-meteo', nazwa: 'Ostrzeżenia meteorologiczne IMGW', instytucja: 'Instytut Meteorologii i Gospodarki Wodnej', co_s: 600, pobranieMin: 4, sukcesMin: 4, liczba24h: 2 }] },
  // świeża luka: ostatni udany odczyt sprzed 12 minut przy źródle odpytywanym co 5 minut
  { kod: 'imgw_hydro', nazwa: 'Ostrzeżenia hydrologiczne', zrodla: [{ slug: 'imgw-hydro', nazwa: 'Ostrzeżenia hydrologiczne IMGW', instytucja: 'Instytut Meteorologii i Gospodarki Wodnej', co_s: 300, pobranieMin: 2, sukcesMin: 12, liczba24h: 0, blad: true }] },
  { kod: 'powietrze', nazwa: 'Jakość powietrza', zrodla: [{ slug: 'gios-powietrze', nazwa: 'Jakość powietrza GIOŚ', instytucja: 'Główny Inspektorat Ochrony Środowiska', co_s: 3600, pobranieMin: 31, sukcesMin: 31, liczba24h: 0 }] },
  { kod: 'pozary', nazwa: 'Pożary', zrodla: [{ slug: 'nasa-firms', nazwa: 'Źródła ciepła NASA FIRMS (VIIRS)', instytucja: 'NASA', co_s: 900, pobranieMin: 9, sukcesMin: 9, liczba24h: 6 }] },
  { kod: 'wstrzasy', nazwa: 'Wstrząsy', zrodla: [{ slug: 'emsc', nazwa: 'Wstrząsy EMSC', instytucja: 'Euro-Mediterranean Seismological Centre', co_s: 180, pobranieMin: 2, sukcesMin: 2, liczba24h: 2 }] },
  { kod: 'katastrofy', nazwa: 'Katastrofy', zrodla: [] },
  { kod: 'policja', nazwa: 'Policja', zrodla: [] },
  { kod: 'psp', nazwa: 'Państwowa Straż Pożarna', zrodla: [] },
  { kod: 'sg', nazwa: 'Straż Graniczna', zrodla: [] },
  { kod: 'wojsko', nazwa: 'Wojsko', zrodla: [] },
  { kod: 'drogi', nazwa: 'Drogi', zrodla: [] },
  { kod: 'kolej', nazwa: 'Kolej', zrodla: [] },
  { kod: 'przestrzen', nazwa: 'Przestrzeń powietrzna', zrodla: [] },
  { kod: 'energetyka', nazwa: 'Energetyka', zrodla: [] },
  { kod: 'cyber', nazwa: 'Cyberbezpieczeństwo', zrodla: [{ slug: 'cert-polska', nazwa: 'Ostrzeżenia CERT Polska', instytucja: 'CERT Polska (NASK)', co_s: 1800, pobranieMin: 14, sukcesMin: 14, liczba24h: 1 }] },
  // wyłączona przez redakcję (WylacznikKategorii): nie pokazuje się nigdzie, także w „warstwach w przygotowaniu”
  { kod: 'media', nazwa: 'Media', wylaczona: true, zrodla: [] },
  { kod: 'urzedy', nazwa: 'Urzędy', zrodla: [] },
];

export function probneWarstwy(teraz: number = Date.now()): Warstwa[] {
  return OPISY.map(o => {
    const zrodla: Zrodlo[] = o.zrodla.map(z => ({
      slug: z.slug, nazwa: z.nazwa, instytucja: z.instytucja, czestotliwosc_s: z.co_s,
      ostatnie_pobranie_at: iso(teraz, z.pobranieMin), ostatni_sukces_at: iso(teraz, z.sukcesMin),
      liczba_wpisow_24h: z.liczba24h, luka: z.co_s <= 300 && z.sukcesMin > 5, blad: !!z.blad,
    }));
    const pobrania = zrodla.map(z => z.ostatnie_pobranie_at).filter((x): x is string => !!x).sort();
    const sukcesy = zrodla.map(z => z.ostatni_sukces_at).filter((x): x is string => !!x).sort();
    return {
      warstwa: o.kod, nazwa: o.nazwa, wylaczona: !!o.wylaczona, zrodla,
      ostatnie_pobranie_at: pobrania.length ? pobrania[pobrania.length - 1] : null,
      ostatni_sukces_at: sukcesy.length ? sukcesy[sukcesy.length - 1] : null,
      liczba_wpisow_24h: zrodla.reduce((s, z) => s + z.liczba_wpisow_24h, 0),
      luka: zrodla.some(z => z.luka), blad: zrodla.some(z => z.blad),
    };
  });
}

/** Odtwarza zdania linii stanu tak, jak składa je backend (StanView). */
export function probneStan(teraz: number = Date.now()): Stan {
  return {
    informacja: 'To nie jest strona urzędowa',
    warstwy: probneWarstwy(teraz).map(w => ({
      warstwa: w.warstwa,
      ostatnie_pobranie: w.ostatnie_pobranie_at ? `ostatnie pobranie: ${godzina(w.ostatnie_pobranie_at)}` : 'brak w naszych danych',
      komunikaty: `komunikatów z 24 h: ${w.liczba_wpisow_24h}`,
      komunikat: w.luka || w.blad || !w.zrodla.length ? 'nie mamy pewności, sprawdź Alert RCB i 112' : '',
    })),
    pominiete: 0,
  };
}

const wpis = (teraz: number, d: Partial<Wpis> & Pick<Wpis, 'id' | 'zrodlo' | 'warstwa' | 'tytul' | 'link'> & { publMin: number; pobrMin: number }): Wpis => {
  const { publMin, pobrMin, ...reszta } = d;
  const teryt = reszta.teryt ?? [];
  return {
    tresc: '', klasa: 'zwykly', szerokosc: null, dlugosc: null, bbox: null, dokladnosc: 'brak', pewnosc_lokalizacji: 0,
    atrybucja: '', miejsce: '', czas_zrodlowy_at: null, dokladna_godzina_publikacji: true, zasieg: teryt.length ? 'obszar' : 'brak',
    ...reszta, teryt, opublikowano_at: iso(teraz, publMin), pobrano_at: iso(teraz, pobrMin),
  };
};

/** Podpis IMGW-PIB z rejestru źródeł (backend/teraz/migrations/0004_rejestr_zrodel.py): z informacją o przetworzeniu danych. */
export const ATRYBUCJA_IMGW = 'Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej - Państwowy Instytut Badawczy. '
  + 'Dane Instytutu Meteorologii i Gospodarki Wodnej - Państwowego Instytutu Badawczego zostały przetworzone.';

/** Powiaty z alertu RCB z 10.11.2026 (próbka backend/teraz/tests/fixtures): część województwa lubelskiego, bez Lublina. */
export const POWIATY_ALERTU_RCB_1011 = ['włodawski', 'łęczyński', 'świdnicki', 'Chełm', 'chełmski', 'krasnostawski', 'łukowski',
  'Biała Podlaska', 'bialski', 'rycki', 'radzyński', 'parczewski', 'lubartowski'];

/** Źródła ciepła w jednym miejscu: pokazują grupowanie znaczników przy oddaleniu. */
const POZARY: [number, number, number][] = [[50.93, 22.88, 0.7], [50.95, 22.93, 0.7], [50.91, 22.91, 0.6], [50.97, 22.86, 0.7], [50.9, 22.84, 0.6], [53.12, 22.31, 0.5]];

export function probneWpisy(teraz: number = Date.now()): Wpis[] {
  const wpisy: Wpis[] = [
    wpis(teraz, {
      id: 9001, zrodlo: 'rcb-gov-pl', warstwa: 'rcb', publMin: 22, pobrMin: 20,
      tytul: 'Przykład: zagrożenie z powietrza w powiatach przemyskim, lubaczowskim i jarosławskim',
      tresc: 'Przykładowy komunikat do podglądu wyglądu. Treść nie jest prawdziwym komunikatem służb.',
      link: 'https://www.gov.pl/web/rcb', teryt: ['1813', '1809', '1804'], dokladnosc: 'powiat',
    }),
    wpis(teraz, {
      id: 9002, zrodlo: 'rcb-gov-pl', warstwa: 'rcb', publMin: 1500, pobrMin: 1498,
      tytul: 'Przykład: odwołanie zagrożenia z powietrza w powiecie hrubieszowskim',
      tresc: 'Przykładowe odwołanie, wpis starszy niż 24 godziny.',
      link: 'https://www.gov.pl/web/rcb', teryt: ['0604'], dokladnosc: 'powiat',
    }),
    wpis(teraz, {
      id: 9003, zrodlo: 'rcb-gov-pl', warstwa: 'rcb', publMin: 140, pobrMin: 138,
      tytul: 'Przykład: ostrzeżenie przed silnym wiatrem w województwie lubelskim',
      tresc: 'Przykładowy komunikat o zasięgu województwa. Bez granic na mapie pokazujemy go na liście.',
      link: 'https://www.gov.pl/web/rcb', teryt: ['06'], dokladnosc: 'wojewodztwo',
    }),
    wpis(teraz, {
      id: 9004, zrodlo: 'imgw-meteo', warstwa: 'imgw_meteo', publMin: 55, pobrMin: 52,
      tytul: 'Przykład: ostrzeżenie 2. stopnia, silny wiatr w Krakowie i Tarnowie',
      tresc: 'Przykładowe ostrzeżenie. Prawdziwe ostrzeżenia IMGW są na stronie źródła.',
      link: 'https://meteo.imgw.pl/', teryt: ['1261', '1263'], dokladnosc: 'powiat', pewnosc_lokalizacji: 1, atrybucja: ATRYBUCJA_IMGW,
    }),
    wpis(teraz, {
      id: 9006, zrodlo: 'rcb-gov-pl', warstwa: 'rcb', publMin: 200, pobrMin: 190,
      tytul: 'Przykład: Alert RCB, zagrożenie z powietrza w części województwa lubelskiego',
      tresc: `Przykład na wzór alertu z 10.11: Alert RCB wysłany do odbiorców na terenie części województwa lubelskiego - powiaty: ${POWIATY_ALERTU_RCB_1011.join(', ')}.`,
      link: 'https://www.gov.pl/web/rcb', teryt: ['06'], dokladnosc: 'wojewodztwo', pewnosc_lokalizacji: 0.5, zasieg: 'przyblizony',
      // `miejsce` w formacie parsera v6: nazwa województwa, jednostki i zakres tego województwa (lista)
      miejsce: ['lubelskiego', ...POWIATY_ALERTU_RCB_1011.map(nazwa => `lubelskie: ${nazwa}`), 'zakres: lubelskie: lista'].join('\n'), dokladna_godzina_publikacji: false,
      // podpis z rejestru źródeł (0004_rejestr_zrodel.py); bez „o godz.”, bo źródło podało tylko datę
      atrybucja: 'Źródło: RCB, gov.pl, opublikowano na gov.pl',
    }),
    wpis(teraz, {
      id: 9005, zrodlo: 'imgw-meteo', warstwa: 'imgw_meteo', publMin: 300, pobrMin: 298,
      tytul: 'Przykład: ostrzeżenie 1. stopnia, intensywne opady w Małopolsce',
      tresc: 'Przykładowe ostrzeżenie z prostokątnym zasięgiem.',
      link: 'https://meteo.imgw.pl/', bbox: [19.0, 49.2, 21.2, 50.45] as Bbox, dokladnosc: 'wojewodztwo',
    }),
    ...POZARY.map(([lat, lon, pewnosc], i) => wpis(teraz, {
      id: 9010 + i, zrodlo: 'nasa-firms', warstwa: 'pozary', publMin: 35 + i * 4, pobrMin: 9,
      tytul: 'Przykład: wykryto źródło ciepła (satelita VIIRS)',
      tresc: 'Odczyt z satelity, niepotwierdzony przez straż pożarną. To może być pożar, ale też źródło przemysłowe.',
      link: 'https://firms.modaps.eosdis.nasa.gov/', szerokosc: lat, dlugosc: lon, dokladnosc: 'punkt', pewnosc_lokalizacji: pewnosc,
    })),
    wpis(teraz, {
      id: 9020, zrodlo: 'emsc', warstwa: 'wstrzasy', publMin: 95, pobrMin: 92,
      tytul: 'Przykład: wstrząs o magnitudzie 3,2, okolice Lubina',
      tresc: 'Przykładowy odczyt sejsmiczny.', link: 'https://www.emsc-csem.org/',
      szerokosc: 51.5, dlugosc: 16.1, dokladnosc: 'punkt', pewnosc_lokalizacji: 0.8,
    }),
    wpis(teraz, {
      id: 9021, zrodlo: 'emsc', warstwa: 'wstrzasy', publMin: 2900, pobrMin: 2897,
      tytul: 'Przykład: wstrząs o magnitudzie 2,6, okolice Bytomia',
      tresc: 'Przykładowy odczyt sejsmiczny sprzed ponad doby.', link: 'https://www.emsc-csem.org/',
      szerokosc: 50.35, dlugosc: 18.9, dokladnosc: 'punkt', pewnosc_lokalizacji: 0.8,
    }),
    wpis(teraz, {
      id: 9030, zrodlo: 'cert-polska', warstwa: 'cyber', publMin: 410, pobrMin: 405,
      tytul: 'Przykład: ostrzeżenie o fali fałszywych wiadomości SMS',
      tresc: 'Przykładowy komunikat bez miejsca: dotyczy całego kraju.', link: 'https://cert.pl/', dokladnosc: 'kraj',
    }),
  ];
  return wpisy.sort((a, b) => Date.parse(b.opublikowano_at) - Date.parse(a.opublikowano_at));
}

export function probneZdarzenia(teraz: number = Date.now()): Zdarzenie[] {
  const wpisy = probneWpisy(teraz);
  const wybierz = (...ids: number[]) => wpisy.filter(w => ids.includes(w.id)).sort((a, b) => Date.parse(a.opublikowano_at) - Date.parse(b.opublikowano_at));
  const zdarzenie = (id: number, status: Zdarzenie['status'], tytul: string, ids: number[]): Zdarzenie => {
    const lista = wybierz(...ids);
    return {
      id, status, tytul_roboczy: tytul, pierwszy_wpis_at: lista[0].opublikowano_at, ostatni_wpis_at: lista[lista.length - 1].opublikowano_at,
      przygotowane_automatycznie: true, zweryfikowal: null, zweryfikowano_at: null, wpisy: lista, odrzucone_wpisy: 0,
    };
  };
  return [
    zdarzenie(8001, 'komunikat_oficjalny', 'Przykład: zagrożenie z powietrza, Podkarpacie', [9001]),
    zdarzenie(8002, 'komunikat_oficjalny', 'Przykład: silny wiatr, Małopolska', [9004, 9005]),
    zdarzenie(8003, 'zgloszone', 'Przykład: źródła ciepła z satelity, Lubelszczyzna', [9010, 9011, 9012, 9013, 9014]),
    zdarzenie(8004, 'zgloszone', 'Przykład: źródło ciepła z satelity, Podlasie', [9015]),
    zdarzenie(8005, 'odwolane', 'Przykład: odwołanie zagrożenia z powietrza, Lubelszczyzna', [9002]),
    // wpisy 9003, 9006, 9020, 9021 i 9030 nie mają zdarzenia: pokazują „Komunikat bez zdarzenia”
  ];
}

export interface FiltryProbne { od?: string; do?: string; teryt?: string; bbox?: Bbox; warstwa?: string }

/** Odtwarza filtry wpisy/ z backendu (od, do, teryt jako prefiks, bbox, warstwa) na danych próbnych. */
export function filtrujProbneWpisy(wpisy: Wpis[], f: FiltryProbne): Wpis[] {
  return wpisy.filter(w => {
    if (f.warstwa && w.warstwa !== f.warstwa) return false;
    if (f.od && Date.parse(w.opublikowano_at) < Date.parse(f.od)) return false;
    if (f.do && Date.parse(w.opublikowano_at) > Date.parse(f.do)) return false;
    if (f.teryt && !w.teryt.some(k => k.startsWith(f.teryt as string))) return false;
    if (f.bbox) {
      const [z, p, e, n] = f.bbox;
      const wPunkcie = w.dlugosc !== null && w.szerokosc !== null && w.dlugosc >= z && w.dlugosc <= e && w.szerokosc >= p && w.szerokosc <= n;
      const wProstokacie = w.bbox !== null && w.bbox[0] <= e && w.bbox[2] >= z && w.bbox[1] <= n && w.bbox[3] >= p;
      if (!wPunkcie && !wProstokacie) return false;
    }
    return true;
  });
}

export const stronaProbna = <T,>(wyniki: T[]): Strona<T> => ({ count: wyniki.length, next: null, previous: null, results: wyniki });
