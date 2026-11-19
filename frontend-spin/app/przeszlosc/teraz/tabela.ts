import type { Warstwa, WidokWpisu } from './typy';
import { BRAK_DANYCH, czasLokalny, czasPobrania, czasPublikacji, czasPublikacjiLokalny } from './czas';
import { adresZrodla } from './link';
import { nazwaZrodla } from './model';
import { normalizuj } from './powiaty';
import { opisMiejsca } from './teryt';
import { KOLEJNOSC_STATUSOW, KOLEJNOSC_WARSTW, metaStatusu, metaWarstwy } from './warstwy';

/**
 * Pełna tabela komunikatów (odpowiednik mapy dla czytników ekranu i dziennikarzy): wiersze, filtr tekstowy, sortowanie
 * i dane do eksportu CSV. Wszystko liczone na tym, co już jest publiczne i widoczne w interfejsie.
 */
export type IdKolumny = 'warstwa' | 'tytul' | 'status' | 'miejsce' | 'opublikowano' | 'pobrano' | 'zrodlo';

export const KOLUMNY: { id: IdKolumny; etykieta: string }[] = [
  { id: 'warstwa', etykieta: 'Warstwa' },
  { id: 'tytul', etykieta: 'Tytuł' },
  { id: 'status', etykieta: 'Status' },
  { id: 'miejsce', etykieta: 'Miejsce' },
  { id: 'opublikowano', etykieta: 'Opublikowano u źródła' },
  { id: 'pobrano', etykieta: 'Pobrano przez nas' },
  { id: 'zrodlo', etykieta: 'Źródło' },
];

export interface WierszTabeli {
  id: number;
  warstwa: string;
  tytul: string;
  status: string;
  miejsce: string;
  /** Czytelnie: „dziś o godz. 14:32” albo sama data, gdy źródło nie podało godziny („10 listopada (źródło podało tylko datę)”). */
  opublikowano: string;
  /** „dziś o godz. 14:32” albo „brak danych”. */
  pobrano: string;
  /** Lokalnie, sortowalnie: „2026-11-18 14:32” albo „2026-11-10” bez godziny (do CSV i atrybutu datetime). */
  opublikowanoCzas: string;
  /** „2026-11-18 14:32” albo „brak danych” (wtedy bez atrybutu datetime). */
  pobranoCzas: string;
  zrodlo: string;
  /** Podpis źródła z API (do CSV). */
  atrybucja: string;
  link: string;
  /** Wartości do sortowania. */
  klucze: Record<IdKolumny, string | number>;
  /** Tekst do filtra (bez polskich znaków i wielkich liter). */
  szukaj: string;
}

const miejsceKrotko = (opis: string): string => opis.replace(/^dotyczy: /, '');

export function wierszeTabeli(widoki: WidokWpisu[], warstwy: Warstwa[] | undefined, teraz: number = Date.now()): WierszTabeli[] {
  return widoki.map(({ wpis, status }) => {
    const nazwaWarstwy = warstwy?.find(w => w.warstwa === wpis.warstwa)?.nazwa ?? metaWarstwy(wpis.warstwa).opis;
    const zrodlo = nazwaZrodla(warstwy, wpis.zrodlo);
    const zrodloTekst = zrodlo.instytucja && zrodlo.instytucja !== zrodlo.nazwa ? `${zrodlo.nazwa}, ${zrodlo.instytucja}` : zrodlo.nazwa;
    const etykietaStatusu = metaStatusu(status).etykieta;
    const miejsce = miejsceKrotko(opisMiejsca(wpis));
    const opublikowano = czasPublikacji(wpis, teraz);
    const pobrano = czasPobrania(wpis.pobrano_at, teraz);
    const opublikowanoCzas = czasPublikacjiLokalny(wpis);
    const pobranoCzas = czasLokalny(wpis.pobrano_at) || BRAK_DANYCH;
    const miejsceWarstwy = KOLEJNOSC_WARSTW.indexOf(wpis.warstwa);
    return {
      id: wpis.id, warstwa: nazwaWarstwy, tytul: wpis.tytul, status: etykietaStatusu, miejsce, opublikowano, pobrano,
      opublikowanoCzas, pobranoCzas, zrodlo: zrodloTekst, atrybucja: wpis.atrybucja ?? '', link: adresZrodla(wpis.link) ?? '',
      klucze: {
        warstwa: miejsceWarstwy < 0 ? 999 : miejsceWarstwy,
        tytul: normalizuj(wpis.tytul),
        status: KOLEJNOSC_STATUSOW.indexOf(status),
        miejsce: normalizuj(miejsce),
        opublikowano: Date.parse(wpis.opublikowano_at) || 0,
        pobrano: (wpis.pobrano_at && Date.parse(wpis.pobrano_at)) || 0,
        zrodlo: normalizuj(zrodloTekst),
      },
      szukaj: normalizuj([nazwaWarstwy, wpis.tytul, etykietaStatusu, miejsce, opublikowano, opublikowanoCzas, pobrano, pobranoCzas, zrodloTekst].join(' ')),
    };
  });
}

/** Każde wpisane słowo musi występować w którejś kolumnie (kolejność dowolna); puste pole nie filtruje. */
export function filtrujWiersze(wiersze: WierszTabeli[], tekst: string): WierszTabeli[] {
  const slowa = normalizuj(tekst).split(' ').filter(Boolean);
  if (!slowa.length) return wiersze;
  return wiersze.filter(w => slowa.every(s => w.szukaj.includes(s)));
}

export type Kierunek = 'rosnaco' | 'malejaco';
const kolator = new Intl.Collator('pl');

/** Sortowanie stabilne: przy remisie decyduje najnowsza publikacja, potem numer wpisu. */
export function sortujWiersze(wiersze: WierszTabeli[], kolumna: IdKolumny, kierunek: Kierunek): WierszTabeli[] {
  const znak = kierunek === 'rosnaco' ? 1 : -1;
  return [...wiersze].sort((a, b) => {
    const x = a.klucze[kolumna];
    const y = b.klucze[kolumna];
    const porownanie = typeof x === 'number' && typeof y === 'number' ? x - y : kolator.compare(String(x), String(y));
    if (porownanie !== 0) return porownanie * znak;
    const czas = (b.klucze.opublikowano as number) - (a.klucze.opublikowano as number);
    return czas || a.id - b.id;
  });
}

/** Domyślny kierunek po pierwszym kliknięciu kolumny: czas od najnowszych, reszta od A do Z. */
export const kierunekPoczatkowy = (kolumna: IdKolumny): Kierunek => (kolumna === 'opublikowano' || kolumna === 'pobrano' ? 'malejaco' : 'rosnaco');

export const NAGLOWKI_CSV: string[] = [...KOLUMNY.map(k => k.etykieta), 'Podpis źródła', 'Odnośnik do oryginału'];

/**
 * Wiersze eksportu: te same kolumny co w tabeli, czas lokalny sortowalny (sama data, gdy źródło nie podało godziny; „brak danych”
 * przy nieznanym pobraniu), podpis źródła z API (P1-6) i odnośnik do oryginału na końcu.
 */
export function wierszeCsv(wiersze: WierszTabeli[]): string[][] {
  return wiersze.map(w => [w.warstwa, w.tytul, w.status, w.miejsce, w.opublikowanoCzas, w.pobranoCzas, w.zrodlo, w.atrybucja, w.link]);
}
