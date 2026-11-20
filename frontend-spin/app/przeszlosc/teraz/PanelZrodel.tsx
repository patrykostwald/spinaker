import type { DaneZrodel, StanZdrowia, ZrodloPubliczne } from './zrodla';
import { KOLEJNOSC_LACZ, KOLEJNOSC_ZDROWIA, LACZA, ZDROWIE, komunikatZrodel, metaLacza, opisBraku, podsumujZrodla, stanZdrowia } from './zrodla';
import { godzina } from './czas';
import { IkonaOstrzezenia } from './Ikony';
import { ZrodloBadge } from './ZrodloBadge';
import { ZdrowieZrodla } from './ZdrowieZrodla';

/**
 * Panel źródeł: każde publiczne źródło z rodzajem łącza i stanem zdrowia. Podsumowanie w nagłówku (rozwijanie zostawia stan
 * widoczny od razu: „działa 8 z 10, 2 z problemem”). Awaria pobrania /zrodla/ jest komunikatem nad listą, nie pustą listą.
 * Wiersze zdrowych źródeł mają stałą wysokość (3 linie); wiersz z luką albo błędem jest wyższy o zdanie „brak w naszych danych”.
 */
export function PanelZrodel({ dane, teraz }: { dane: DaneZrodel; teraz?: number }) {
  const lista = dane.lista ?? [];
  const p = dane.lista ? podsumujZrodla(dane.lista) : null;
  const komunikat = komunikatZrodel(dane);
  const podsumowanie = dane.ladowanie ? 'Wczytujemy stan źródeł…'
    : p ? `działa ${p.dziala} z ${p.razem}${p.problemy ? `, ${p.problemy} z problemem` : ''}` : 'stan niedostępny';
  return <section className="tz-zrodla" aria-labelledby="tz-zrodla-tytul">
    {komunikat && <p className="tz-zrodla__komunikat"><IkonaOstrzezenia rozmiar={14} /><span>{komunikat}</span></p>}
    <details className="tz-zrodla__szczegoly">
      <summary>
        <span className="tz-zrodla__tytul" id="tz-zrodla-tytul">Źródła i ich stan</span>{' '}
        <span className="tz-zrodla__licznik" data-problem={p && p.problemy > 0 ? '' : undefined}>{podsumowanie}</span>
      </summary>
      {dane.lista && !lista.length && <p className="tz-zrodla__pusty">Serwer nie podał żadnych źródeł, więc nie wiemy, skąd pochodzą komunikaty.</p>}
      {lista.length > 0 && <>
        <ul className="tz-zrodla__lista">
          {lista.map(z => <li key={z.slug} className="tz-zrodlo" data-stan={stanZdrowia(z)}>
            <span className="tz-zrodlo__wiersz">
              <span className="tz-zrodlo__nazwa" title={z.nazwa}>{z.nazwa}</span>
              <ZrodloBadge rodzaj={z.rodzaj_lacza} />
            </span>
            <span className="tz-zrodlo__instytucja" title={z.instytucja}>{z.instytucja || 'instytucja nieznana'}</span>
            <ZdrowieZrodla zrodlo={z} pelny teraz={teraz} />
          </li>)}
        </ul>
        {dane.pobranoMs > 0 && <p className="tz-zrodla__stopka">Stan źródeł z godz. {godzina(new Date(dane.pobranoMs).toISOString())}. Odświeżamy go co minutę.</p>}
      </>}
    </details>
  </section>;
}

const WAGA_PROBLEMU = { wstrzymane: 3, blad: 2, luka: 1, dziala: 0 } as const;
const duza = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/**
 * Łącze i stan źródeł jednej warstwy w panelu warstw (po slugach źródeł z warstwy/): etykiety rodzajów łącza, jedno słowo o stanie
 * (najgorszy stan ze źródeł warstwy) i dla każdego źródła z luką albo błędem zdanie „brak w naszych danych: źródło X, od <data>”.
 * W trakcie pobierania i po awarii /zrodla/ nic nie rysuje: o awarii mówi panel źródeł (PanelZrodel), a nie zgadujemy stanu.
 */
export function ZrodlaWarstwy({ dane, slugi, teraz }: { dane: DaneZrodel; slugi: string[]; teraz?: number }) {
  if (!dane.lista || !slugi.length) return null;
  const lista = dane.lista;
  const zrodla = slugi.map(slug => lista.find(z => z.slug === slug));
  const rodzaje = [...new Set(zrodla.map(z => metaLacza(z?.rodzaj_lacza).kod))];
  const znane = zrodla.filter((z): z is ZrodloPubliczne => !!z);
  const problemy = znane.filter(z => stanZdrowia(z) !== 'dziala');
  const najgorsze = problemy.reduce<StanZdrowia | null>((g, z) => (g && WAGA_PROBLEMU[g] >= WAGA_PROBLEMU[stanZdrowia(z)] ? g : stanZdrowia(z)), null);
  const nieznane = znane.length < zrodla.length;
  return <div className="tz-warstwa__zrodla">
    <p className="tz-warstwa__lacza">
      {rodzaje.map(k => <ZrodloBadge key={k} rodzaj={k} />)}
      {najgorsze
        ? <span className="tz-zdrowie" data-stan={najgorsze}><span className="tz-sr">Stan źródła: </span><span className="tz-zdrowie__znak" aria-hidden="true">{ZDROWIE[najgorsze].znak}</span>{ZDROWIE[najgorsze].slowo}</span>
        : nieznane ? <ZdrowieZrodla zrodlo={undefined} />
          : <span className="tz-zdrowie" data-stan="dziala"><span className="tz-sr">Stan źródła: </span><span className="tz-zdrowie__znak" aria-hidden="true">{ZDROWIE.dziala.znak}</span>{ZDROWIE.dziala.slowo}</span>}
    </p>
    {problemy.map(z => <p key={z.slug} className="tz-zdrowie__brak">{duza(opisBraku(z, teraz) ?? '')}.</p>)}
  </div>;
}

/**
 * Sekcja legendy „Skąd i jak”: co znaczą etykiety łączy i stany źródeł oraz zdanie „brak w naszych danych”.
 * Wszystkie 8 rodzajów łączy jest zawsze na liście (także te, których teraz żadne źródło nie używa).
 */
export function LegendaSkadIJak() {
  return <section className="tz-skad" aria-labelledby="tz-skad-tytul">
    <h3 id="tz-skad-tytul" className="tz-skad__tytul">Skąd i jak</h3>
    <p className="tz-legenda__lead">Etykieta przy źródle mówi, jak pobieramy dane. Nie mówi nic o ważności komunikatu.</p>
    <ul className="tz-skad__lacza">
      {KOLEJNOSC_LACZ.map(k => <li key={k}><ZrodloBadge rodzaj={k} /><span>{LACZA[k].opis}</span></li>)}
    </ul>
    <p className="tz-legenda__lead">Stan źródła: znak i słowo.</p>
    <ul className="tz-skad__zdrowie">
      {KOLEJNOSC_ZDROWIA.map(s => <li key={s} data-stan={s}>
        <span className="tz-zdrowie" data-stan={s}><span className="tz-zdrowie__znak" aria-hidden="true">{ZDROWIE[s].znak}</span>{ZDROWIE[s].slowo}</span>
        <span>{ZDROWIE[s].opis}</span>
      </li>)}
    </ul>
    <p className="tz-legenda__lead">„Brak w naszych danych: źródło X, od…” znaczy, że od tej chwili nie mamy od źródła danych. To luka w naszym pobieraniu, a nie znak, że nic się nie dzieje.</p>
  </section>;
}
