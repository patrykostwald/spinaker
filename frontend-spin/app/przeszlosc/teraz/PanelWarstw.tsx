import type { Okres, Warstwa } from './typy';
import type { WierszStanu } from './model';
import { aktywna } from './model';
import { KOLEJNOSC_STATUSOW, metaStatusu, metaWarstwy } from './warstwy';
import { WOJEWODZTWA } from './teryt';
import { EtykietaStatusu, IkonaOstrzezenia, IkonaWarstwy } from './Ikony';
import { WyborOkresu } from './WyborOkresu';
import type { DaneZrodel } from './zrodla';
import { LegendaSkadIJak, PanelZrodel, ZrodlaWarstwy } from './PanelZrodel';

/**
 * Panel warstw: filtry (czas, województwo), przełączniki warstw z kolorem, ikoną, liczbą wpisów i świeżością, legenda.
 * Zdania o świeżości pochodzą z API (stan/): „ostatnie pobranie: 14:32”, „komunikatów: 3” (ostatnie 24 godziny).
 * Warstwy bez żadnego publicznego źródła są osobno, wyłączone: nie udają, że coś pokazują. Warstwy wyłączone przez redakcję
 * (`wylaczona`) nie dochodzą tu wcale (TerazPage przekazuje tylko dostępne).
 * Filtr województwa jest przybliżony (prostokąty, nie granice), co jest napisane pod polem.
 * Łącze i zdrowie źródeł (GET zrodla/): etykiety przy warstwach, panel „Źródła i ich stan” i sekcja legendy „Skąd i jak”.
 */
export interface PanelWarstwProps {
  warstwy: Warstwa[];
  wiersze: Map<string, WierszStanu>;
  wlaczone: Set<string>;
  naMapie: Record<string, number>;
  okres: Okres;
  woj: string | null;
  ladowanie: boolean;
  /** Stan źródeł (łącze, zdrowie); pominięty = bez znaczników łącza i zdrowia. */
  zrodla?: DaneZrodel;
  onPrzelacz: (kod: string) => void;
  onWszystkie: (wlacz: boolean) => void;
  onOkres: (o: Okres) => void;
  onWoj: (kod: string | null) => void;
  onZamknij: () => void;
}

export function PanelWarstw(p: PanelWarstwProps) {
  const dzialajace = p.warstwy.filter(aktywna);
  const przygotowywane = p.warstwy.filter(w => !aktywna(w));
  return <div className="tz-panel__tresc">
    <div className="tz-panel__gora">
      <h2 className="tz-panel__tytul" id="tz-panel-tytul" tabIndex={-1}>Warstwy i filtry</h2>
      <button type="button" className="tz-przycisk tz-panel__zamknij" onClick={p.onZamknij} aria-label="Zamknij panel warstw">Zamknij</button>
    </div>

    <div className="tz-filtr">
      <p className="tz-filtr__etykieta" id="tz-okres-etykieta">Czas (okres, z którego pokazujemy komunikaty)</p>
      <WyborOkresu okres={p.okres} onOkres={p.onOkres} nazwa="tz-okres-panel" opisanePrzez="tz-okres-etykieta" klasa="tz-segmenty" />
    </div>

    <div className="tz-filtr">
      <label htmlFor="tz-woj">Województwo</label>
      <select id="tz-woj" value={p.woj ?? ''} aria-describedby="tz-woj-uwaga" onChange={e => p.onWoj(e.target.value || null)}>
        <option value="">Cała Polska</option>
        {WOJEWODZTWA.map(w => <option key={w.kod} value={w.kod}>{w.nazwa}</option>)}
      </select>
      <p id="tz-woj-uwaga" className="tz-filtr__uwaga">
        {p.woj
          ? 'Filtr przybliżony: komunikaty bez kodu TERYT pokazujemy, gdy ich zasięg choćby częściowo wchodzi w prostokąt województwa, więc przy granicy mogą trafić się komunikaty z sąsiedniego.'
          : 'Po wybraniu województwa filtr jest przybliżony (prostokąt, nie granica).'}
      </p>
    </div>

    <div className="tz-panel__naglowek">
      <h3>Warstwy</h3>
      <span className="tz-panel__akcje">
        <button type="button" onClick={() => p.onWszystkie(true)}>Wszystkie</button>
        <button type="button" onClick={() => p.onWszystkie(false)}>Żadna</button>
      </span>
    </div>

    {p.ladowanie && !p.warstwy.length && <p className="tz-panel__komunikat" role="status">Wczytujemy warstwy…</p>}
    {!p.ladowanie && !p.warstwy.length && <p className="tz-panel__komunikat" role="status">Nie udało się wczytać listy warstw.</p>}

    <ul className="tz-warstwy">
      {dzialajace.map(w => {
        const meta = metaWarstwy(w.warstwa);
        const wiersz = p.wiersze.get(w.warstwa);
        const wl = p.wlaczone.has(w.warstwa);
        const ostrzega = !!wiersz?.komunikat;
        return <li key={w.warstwa} className="tz-warstwa" data-wl={wl ? '' : undefined}>
          <label className="tz-warstwa__glowna">
            <input type="checkbox" role="switch" checked={wl} onChange={() => p.onPrzelacz(w.warstwa)} />
            <span className="tz-przelacznik__tor" aria-hidden="true"><span /></span>
            <IkonaWarstwy kod={w.warstwa} />
            <span className="tz-warstwa__nazwa" title={w.nazwa}>{w.nazwa}<span className="tz-sr"> ({meta.opis})</span></span>
            <span className="tz-warstwa__licznik" title="Komunikaty na mapie przy bieżących filtrach">{p.naMapie[w.warstwa] ?? 0}<span className="tz-sr"> na mapie</span></span>
          </label>
          <p className="tz-warstwa__opis" title={meta.opis}>{meta.opis}</p>
          <p className="tz-warstwa__stan" title={wiersz ? `${wiersz.ostatniePobranie} · ${wiersz.komunikaty}` : undefined}>{wiersz ? `${wiersz.ostatniePobranie} · ${wiersz.komunikaty}` : 'stan niedostępny'}</p>
          {ostrzega && <p className="tz-warstwa__ostrz"><IkonaOstrzezenia rozmiar={14} /><span><strong>Możliwa luka w danych.</strong> {wiersz?.komunikat}.</span></p>}
          {p.zrodla && <ZrodlaWarstwy dane={p.zrodla} slugi={w.zrodla.map(z => z.slug)} />}
        </li>;
      })}
    </ul>

    {p.zrodla && <PanelZrodel dane={p.zrodla} />}

    {przygotowywane.length > 0 && <details className="tz-przygotowanie">
      <summary>Warstwy w przygotowaniu ({przygotowywane.length})</summary>
      <p>Bez publicznego źródła nie pokazują nic. Brak komunikatów z takiej warstwy nie znaczy, że nic się nie dzieje.</p>
      <ul>{przygotowywane.map(w => <li key={w.warstwa}><IkonaWarstwy kod={w.warstwa} />{w.nazwa}</li>)}</ul>
    </details>}

    <details className="tz-legenda" open>
      <summary>Legenda</summary>
      <p className="tz-legenda__lead">Kolor i symbol wskazują warstwę, kształt znacznika wskazuje status.</p>
      <ul>
        {KOLEJNOSC_STATUSOW.map(s => <li key={s}><EtykietaStatusu status={s} /><span>{metaStatusu(s).opis}</span></li>)}
      </ul>
      <p className="tz-legenda__lead">Obszar bez punktu to prostokąt: linia ciągła (komunikat, potwierdzone), przerywana (zgłoszone, ocena), kropkowana (odwołane, bez zdarzenia). Liczba w kółku to grupa znaczników, kliknij, aby przybliżyć.</p>
      <LegendaSkadIJak />
    </details>
  </div>;
}
