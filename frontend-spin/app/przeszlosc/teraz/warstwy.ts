import type { KodWarstwy, Okres, StatusKlucz } from './typy';

/**
 * Wygląd warstw i statusów. Kolor nigdy nie jest jedynym nośnikiem: warstwa ma ikonę i nazwę (panel, karta),
 * status ma kształt znacznika i słowo (Laws of UX: Similarity, Von Restorff; WCAG 1.4.1).
 */
export interface MetaWarstwy { kolor: string; ikona: string; opis: string; uwagaCzas?: string }

/** Ścieżki ikon (siatka 24, obrys 1,7). */
export const IKONY: Record<string, string> = {
  dzwonek: 'M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0',
  wiatr: 'M9.6 4.6A2 2 0 1 1 11 8H2M12.6 19.4A2 2 0 1 0 14 16H2M17.7 7.7A2.5 2.5 0 1 1 19.5 12H2',
  kropla: 'M12 2.7l5.7 5.6a8 8 0 1 1-11.4 0z',
  chmura: 'M18 10h-1.3A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z',
  plomien: 'M12 22c4 0 7-2.7 7-7 0-3-2-5-3-7-1 2-2 3-3 3 0-3-1-6-4-9 0 5-4 7-4 12 0 4.3 3 8 7 8z',
  fala: 'M2 12h4l3-8 4 16 3-8h6',
  glob: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20',
  tarcza: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  krzyz: 'M9 3h6v6h6v6h-6v6H9v-6H3V9h6z',
  flaga: 'M4 22V4M4 4h13l-2 4 2 4H4',
  gwiazda: 'M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z',
  droga: 'M8 3L5 21M16 3l3 18M12 4v3M12 11v3M12 18v3',
  tor: 'M7 3v18M17 3v18M7 7h10M7 12h10M7 17h10',
  samolot: 'M17.8 19.2L16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z',
  blyskawica: 'M13 2L3 14h9l-1 8 10-12h-9z',
  zamek: 'M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4',
  gazeta: 'M4 4h16v16H4zM8 8h8M8 12h8M8 16h5',
  budynek: 'M3 21h18M5 21V10l7-5 7 5v11M9 21v-6h6v6',
  ostrzezenie: 'M12 3l10 18H2zM12 10v5M12 18h.01',
};

export const WARSTWY_META: Record<KodWarstwy, MetaWarstwy> = {
  rcb: { kolor: '#ff4d4f', ikona: 'dzwonek', opis: 'Alert RCB (SMS i komunikaty)',
    uwagaCzas: 'Godzina pochodzi z publikacji na stronie gov.pl, a nie z wysyłki SMS.' },
  imgw_meteo: { kolor: '#f5b301', ikona: 'wiatr', opis: 'Ostrzeżenia pogodowe IMGW' },
  imgw_hydro: { kolor: '#3b9cff', ikona: 'kropla', opis: 'Ostrzeżenia hydrologiczne IMGW' },
  powietrze: { kolor: '#2ec4b6', ikona: 'chmura', opis: 'Jakość powietrza' },
  pozary: { kolor: '#ff8a2a', ikona: 'plomien', opis: 'Źródła ciepła z satelitów (zgłoszone, niepotwierdzone)' },
  wstrzasy: { kolor: '#b36bff', ikona: 'fala', opis: 'Wstrząsy sejsmiczne' },
  katastrofy: { kolor: '#ff5fa2', ikona: 'glob', opis: 'Katastrofy i klęski' },
  policja: { kolor: '#6d7cff', ikona: 'tarcza', opis: 'Komunikaty Policji' },
  psp: { kolor: '#e11d48', ikona: 'krzyz', opis: 'Komunikaty Państwowej Straży Pożarnej' },
  sg: { kolor: '#7bc043', ikona: 'flaga', opis: 'Straż Graniczna' },
  wojsko: { kolor: '#a8a29e', ikona: 'gwiazda', opis: 'Komunikaty wojskowe' },
  drogi: { kolor: '#94a3b8', ikona: 'droga', opis: 'Utrudnienia drogowe' },
  kolej: { kolor: '#22c55e', ikona: 'tor', opis: 'Komunikaty kolejowe' },
  przestrzen: { kolor: '#06b6d4', ikona: 'samolot', opis: 'Przestrzeń powietrzna' },
  energetyka: { kolor: '#facc15', ikona: 'blyskawica', opis: 'Energetyka' },
  cyber: { kolor: '#c084fc', ikona: 'zamek', opis: 'Cyberbezpieczeństwo' },
  media: { kolor: '#cbd0d8', ikona: 'gazeta', opis: 'Media (tytuł, data, odnośnik)' },
  urzedy: { kolor: '#e0b084', ikona: 'budynek', opis: 'Komunikaty urzędów' },
};

const DOMYSLNA: MetaWarstwy = { kolor: '#cbd0d8', ikona: 'ostrzezenie', opis: 'Warstwa' };
export const metaWarstwy = (kod: string): MetaWarstwy => (WARSTWY_META as Record<string, MetaWarstwy>)[kod] ?? DOMYSLNA;

/** Kolejność na liście: najważniejsze dla bezpieczeństwa najpierw. */
export const KOLEJNOSC_WARSTW: KodWarstwy[] = [
  'rcb', 'imgw_meteo', 'imgw_hydro', 'pozary', 'wstrzasy', 'powietrze', 'katastrofy', 'psp', 'policja', 'sg',
  'wojsko', 'drogi', 'kolej', 'przestrzen', 'energetyka', 'cyber', 'urzedy', 'media',
];

export type Ksztalt = 'kolo' | 'romb' | 'kwadrat' | 'trojkat' | 'krzyzyk' | 'pierscien';
export type StylObramowania = 'ciagla' | 'przerywana' | 'kropkowana';

export interface MetaStatusu { etykieta: string; opis: string; ksztalt: Ksztalt; obramowanie: StylObramowania }

/** Status wpisu pochodzi z zdarzenia; wpis bez zdarzenia nie dostaje wyprowadzonego statusu (nie zgadujemy). */
export const STATUSY: Record<StatusKlucz, MetaStatusu> = {
  komunikat_oficjalny: { etykieta: 'Komunikat oficjalny', opis: 'Komunikat instytucji publicznej.', ksztalt: 'kolo', obramowanie: 'ciagla' },
  zgloszone: { etykieta: 'Zgłoszone', opis: 'Zgłoszenie lub odczyt, którego nie potwierdziła żadna instytucja.', ksztalt: 'romb', obramowanie: 'przerywana' },
  potwierdzone: { etykieta: 'Potwierdzone', opis: 'Potwierdzone przez co najmniej dwie instytucje.', ksztalt: 'kwadrat', obramowanie: 'ciagla' },
  ocena: { etykieta: 'Ocena', opis: 'Ocena redakcji, nie komunikat urzędowy.', ksztalt: 'trojkat', obramowanie: 'przerywana' },
  odwolane: { etykieta: 'Odwołane', opis: 'Komunikat odwołany lub wycofany.', ksztalt: 'krzyzyk', obramowanie: 'kropkowana' },
  brak: { etykieta: 'Komunikat bez zdarzenia', opis: 'Komunikat źródła, jeszcze niepowiązany ze zdarzeniem.', ksztalt: 'pierscien', obramowanie: 'kropkowana' },
};
export const metaStatusu = (s: StatusKlucz): MetaStatusu => STATUSY[s] ?? STATUSY.brak;
export const KOLEJNOSC_STATUSOW: StatusKlucz[] = ['komunikat_oficjalny', 'zgloszone', 'potwierdzone', 'ocena', 'odwolane', 'brak'];

export const OKRESY: { id: Okres; etykieta: string; ms: number }[] = [
  { id: '1h', etykieta: '1 godz.', ms: 3_600_000 },
  { id: '24h', etykieta: '24 godz.', ms: 86_400_000 },
  { id: '7d', etykieta: '7 dni', ms: 604_800_000 },
];
export const OKRES_DOMYSLNY: Okres = '24h';

/** Stałe zdania (zasady produktu): nigdy „spokojnie” ani „bezpiecznie”. */
export const ZDANIE_STALE = 'To nie jest strona urzędowa. W sytuacji zagrożenia słuchaj komunikatów RCB i dzwoń pod 112.';
export const NIEPEWNOSC = 'nie mamy pewności, sprawdź Alert RCB i 112';
