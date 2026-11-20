import type { DaneZrodel, KodLacza } from './zrodla';
import { metaLacza, znajdzZrodlo } from './zrodla';

/**
 * Etykieta rodzaju łącza (X, API, MCI, RSS, scraping, WebSocket, plik, ręcznie): ikona i słowo, nigdy sama barwa
 * (WCAG 1.4.1; wygląd z prototypu A, docs/teraz-koncepcje: etykieta z ramką, 12 px). Opis po polsku jest w podpowiedzi
 * i w legendzie „Skąd i jak”; czytnik ekranu czyta „Łącze: API”.
 * Nieznany albo pusty rodzaj to etykieta „nieznane”, a nie brak etykiety: nie zgadujemy, jak pobieramy źródło.
 */
const IKONY_LACZ: Record<KodLacza, string> = {
  x: 'M5 5l14 14M19 5L5 19',
  api: 'M8 4c-2 0-3 1-3 3v2c0 1.5-1 3-2 3 1 0 2 1.5 2 3v2c0 2 1 3 3 3M16 4c2 0 3 1 3 3v2c0 1.5 1 3 2 3-1 0-2 1.5-2 3v2c0 2-1 3-3 3',
  mci: 'M4 12h5M15 12h5M9 8v8M15 8v8M9 12h6',
  rss: 'M5 19.01v.01M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16',
  scraping: 'M6 3h9l4 4v14H6zM9 12h7M9 16h7M9 8h3',
  websocket: 'M4 8h14l-3-3M20 16H6l3 3',
  plik: 'M7 3h8l4 4v14H7zM15 3v4h4',
  reczne: 'M4 20l1-4L16 5l3 3L8 19z',
  nieznane: 'M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7M12 17.5v.01',
};

export function IkonaLacza({ kod, rozmiar = 14 }: { kod: KodLacza; rozmiar?: number }) {
  return <svg className="tz-lacze__ik" viewBox="0 0 24 24" width={rozmiar} height={rozmiar} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={IKONY_LACZ[kod]} />
  </svg>;
}

export function ZrodloBadge({ rodzaj }: { rodzaj: string | null | undefined }) {
  const m = metaLacza(rodzaj);
  return <span className="tz-lacze" data-lacze={m.kod} title={`${m.etykieta}: ${m.opis}`}>
    <IkonaLacza kod={m.kod} />
    <span className="tz-sr">Łącze: </span>{m.etykieta}
  </span>;
}

/**
 * Etykieta łącza źródła wpisu (po slugu). Bez danych o źródłach (prop pominięty) albo w trakcie pierwszego pobrania nie rysuje nic;
 * po awarii pobrania stanu źródeł albo dla źródła spoza listy pokazuje „nieznane” (patrz ZrodloBadge).
 */
export function ZrodloBadgeWpisu({ zrodla, slug }: { zrodla: DaneZrodel | undefined; slug: string }) {
  if (!zrodla || zrodla.ladowanie) return null;
  return <ZrodloBadge rodzaj={znajdzZrodlo(zrodla, slug)?.rodzaj_lacza} />;
}
