import type { DaneZrodel, ZrodloPubliczne } from './zrodla';
import { ZDROWIE, komunikatZrodel, opisBledu, opisBraku, stanZdrowia, znajdzZrodlo } from './zrodla';
import { dataIGodzina } from './czas';

/**
 * Zdrowie źródła: stan (znak i słowo, nie sama barwa), ostatnie udane pobranie, kod błędu po polsku i luka.
 * Luka albo błąd to zawsze zdanie „Brak w naszych danych: źródło X, od <data>” (zrodla.ts: opisBraku), nigdy „bez komunikatów”.
 * Stan „działa” znaczy tylko, że pobieranie działa: nie mówi nic o tym, czy cokolwiek się dzieje.
 */
const duza = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export interface ZdrowieZrodlaProps {
  /** Źródło z API; brak = nie znamy jego stanu („stan nieznany”, osobny stan, nie „działa”). */
  zrodlo: ZrodloPubliczne | undefined;
  /** Pełny widok: osobne linie (ostatnie pobranie, błąd, luka). Domyślnie jedna linia: znak, słowo, czas. */
  pelny?: boolean;
  teraz?: number;
}

export function ZdrowieZrodla({ zrodlo, pelny = false, teraz }: ZdrowieZrodlaProps) {
  if (!zrodlo) {
    return <span className="tz-zdrowie" data-stan="nieznany">
      <span className="tz-zdrowie__znak" aria-hidden="true">?</span>stan źródła nieznany
    </span>;
  }
  const stan = stanZdrowia(zrodlo);
  const m = ZDROWIE[stan];
  const ostatnie = dataIGodzina(zrodlo.ostatni_sukces_at, teraz);
  const braku = opisBraku(zrodlo, teraz);
  const wiersz = <span className="tz-zdrowie" data-stan={stan}>
    <span className="tz-sr">Stan źródła: </span><span className="tz-zdrowie__znak" aria-hidden="true">{m.znak}</span>
    <span className="tz-zdrowie__slowo">{m.slowo}</span>
    {!pelny && <span className="tz-zdrowie__czas"> · ostatnie udane pobranie: {ostatnie || 'brak'}</span>}
  </span>;
  if (!pelny) return wiersz;
  return <span className="tz-zdrowie-blok" data-stan={stan}>
    {wiersz}
    <span className="tz-zdrowie__linia">Ostatnie udane pobranie: {ostatnie || 'brak, nigdy się nie udało'}.</span>
    {zrodlo.ostatni_blad && <span className="tz-zdrowie__linia">{opisBledu(zrodlo.ostatni_blad)}</span>}
    {braku && <span className="tz-zdrowie__brak">{duza(braku)}.</span>}
  </span>;
}

/**
 * Stan źródła wpisu (po slugu) we wszystkich stanach danych o źródłach: trwa pobieranie, awaria pobrania /zrodla/, źródło spoza listy
 * i stan znany. Awaria to komunikat o niedostępnym stanie, nie „brak danych” ani „działa”.
 */
export function StanZrodlaWpisu({ zrodla, slug, teraz }: { zrodla: DaneZrodel; slug: string; teraz?: number }) {
  if (zrodla.ladowanie) return <span className="tz-zdrowie" data-stan="nieznany">Wczytujemy stan źródła…</span>;
  const z = znajdzZrodlo(zrodla, slug);
  if (z) return <ZdrowieZrodla zrodlo={z} pelny teraz={teraz} />;
  return <span className="tz-zdrowie-blok" data-stan="nieznany">
    <ZdrowieZrodla zrodlo={undefined} />
    <span className="tz-zdrowie__linia">{zrodla.niedostepne ? komunikatZrodel(zrodla) : 'Tego źródła nie ma na liście źródeł, którą dostaliśmy z serwera.'}</span>
  </span>;
}

/** Znak problemu przy wpisie na liście: tylko dla źródeł z luką, błędem albo wstrzymanych (zdrowe nie dostają nic). */
export function ZnakProblemuZrodla({ zrodla, slug, teraz }: { zrodla: DaneZrodel | undefined; slug: string; teraz?: number }) {
  const z = zrodla ? znajdzZrodlo(zrodla, slug) : undefined;
  if (!z) return null;
  const stan = stanZdrowia(z);
  if (stan === 'dziala') return null;
  const m = ZDROWIE[stan];
  const brak = `${duza(opisBraku(z, teraz) ?? '')}.`;
  // pełne zdanie także dla czytnika i klawiatury (title nie działa na dotyku); widoczne jest samo słowo stanu
  return <span className="tz-zdrowie tz-zdrowie--znak" data-stan={stan} title={brak}>
    <span className="tz-sr">Stan źródła: </span><span className="tz-zdrowie__znak" aria-hidden="true">{m.znak}</span>{m.slowo}<span className="tz-sr">. {brak}</span>
  </span>;
}
