import type { PodsumowanieStanu } from './model';
import { godzina } from './czas';
import { NIEPEWNOSC, ZDANIE_STALE } from './warstwy';
import { IkonaOstrzezenia } from './Ikony';

/**
 * Linia stanu u góry (zawsze widoczna): stałe zdanie „To nie jest strona urzędowa...”, potem stan źródeł dokładnie
 * w sformułowaniach z API (stan/). Przy braku połączenia: „nie mamy pewności, sprawdź Alert RCB i 112”.
 * Nigdy nie piszemy „spokojnie” ani „bezpiecznie”: brak komunikatów nie jest informacją o braku zagrożenia.
 */
export interface LiniaStanuProps {
  probne: boolean;
  podsumowanie: PodsumowanieStanu | null;
  online: boolean;
  /** Zapytanie o stan albo o wpisy zakończyło się błędem. */
  blad: boolean;
  /** Czas ostatniego udanego odświeżenia wpisów (ms) albo null, gdy jeszcze nic nie przyszło. */
  odswiezono: number | null;
  ladowanie: boolean;
}

const MAKS_OSTRZEZEN = 3;

export function LiniaStanu({ probne, podsumowanie, online, blad, odswiezono, ladowanie }: LiniaStanuProps) {
  const brakPolaczenia = !online || blad;
  const rcb = podsumowanie?.wiersze.find(w => w.warstwa === 'rcb' && w.aktywna);
  const pierwsza = rcb ?? podsumowanie?.wiersze.find(w => w.aktywna);
  const ostrzezenia = podsumowanie?.ostrzezenia ?? [];

  let poziom: 'ostrzezenie' | 'ok' | 'ladowanie' = 'ok';
  let tresc: React.ReactNode;
  if (brakPolaczenia) {
    poziom = 'ostrzezenie';
    tresc = <>
      <strong>{online ? 'Brak połączenia z serwerem' : 'Brak połączenia z internetem'}: {NIEPEWNOSC}.</strong>
      {odswiezono && <> Ostatnie dane z godz. {godzina(new Date(odswiezono).toISOString())}.</>}
    </>;
  } else if (!podsumowanie) {
    poziom = 'ladowanie';
    tresc = ladowanie ? 'Sprawdzamy stan źródeł…' : `Stan źródeł jest niedostępny: ${NIEPEWNOSC}.`;
  } else if (ostrzezenia.length) {
    poziom = 'ostrzezenie';
    tresc = <>
      {ostrzezenia.slice(0, MAKS_OSTRZEZEN).map(o => <span key={o.warstwa} className="tz-stan__zdanie"><strong>{o.nazwa}:</strong> {o.komunikat}. </span>)}
      {ostrzezenia.length > MAKS_OSTRZEZEN && <span className="tz-stan__zdanie">Jeszcze {ostrzezenia.length - MAKS_OSTRZEZEN} warstw z tą samą uwagą (szczegóły niżej).</span>}
    </>;
  } else {
    tresc = pierwsza ? <><strong>{pierwsza.nazwa}:</strong> {pierwsza.ostatniePobranie}, {pierwsza.komunikaty}.</> : 'Brak aktywnych źródeł.';
  }

  return <section className="tz-stan" aria-label="Stan danych" data-poziom={poziom}>
    {probne && <p className="tz-stan__probne" role="note"><strong>Dane przykładowe.</strong> To nie są prawdziwe komunikaty, tylko podgląd wyglądu strony.</p>}
    <p className="tz-stan__stale">{ZDANIE_STALE}</p>
    <p className="tz-stan__linia" role="status" aria-live="polite">
      {poziom === 'ostrzezenie' && <span className="tz-stan__ik"><IkonaOstrzezenia /></span>}
      <span>{tresc}</span>
    </p>
    {podsumowanie && <details className="tz-stan__szczegoly">
      <summary>Stan wszystkich warstw{odswiezono ? ` (odświeżono o godz. ${godzina(new Date(odswiezono).toISOString())})` : ''}</summary>
      <p className="tz-stan__info">{podsumowanie.informacja}.</p>
      <ul>
        {podsumowanie.wiersze.map(w => <li key={w.warstwa} data-aktywna={w.aktywna ? '' : undefined}>
          <strong>{w.nazwa}</strong>
          <span>{w.aktywna ? `${w.ostatniePobranie}, ${w.komunikaty}` : 'brak źródeł, warstwa w przygotowaniu'}</span>
          {w.komunikat && <em>{w.komunikat}</em>}
        </li>)}
      </ul>
    </details>}
  </section>;
}
