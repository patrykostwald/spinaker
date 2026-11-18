import { useMemo, useState } from 'react';
import type { Warstwa, WidokWpisu } from './typy';
import { budujCsv, nazwaPlikuCsv } from './csv';
import { liczbaKomunikatow } from './powiaty';
import { KOLUMNY, NAGLOWKI_CSV, filtrujWiersze, kierunekPoczatkowy, sortujWiersze, wierszeCsv, wierszeTabeli } from './tabela';
import type { IdKolumny, Kierunek } from './tabela';
import { host } from './czas';
import { NIEPEWNOSC } from './warstwy';

/**
 * Pełna tabela komunikatów: ten sam zbiór co na mapie (warstwy, czas i województwo z panelu), jako zwykła tabela HTML dla
 * czytników ekranu i dziennikarzy. Sortowanie przyciskami w nagłówkach (aria-sort), filtr tekstowy, eksport widoku do CSV
 * w przeglądarce (tylko to, co jest w tabeli i już publiczne; nic nie jest wysyłane na serwer).
 */
export interface TabelaWpisowProps {
  widoki: WidokWpisu[];
  warstwy: Warstwa[] | undefined;
  wybrany: number | null;
  onWybierz: (id: number) => void;
  /** Opis bieżących filtrów do podpisu tabeli, np. „24 godz., cała Polska”. */
  opisFiltrow: string;
}

export function TabelaWpisow({ widoki, warstwy, wybrany, onWybierz, opisFiltrow }: TabelaWpisowProps) {
  const [tekst, setTekst] = useState('');
  const [sortowanie, setSortowanie] = useState<{ kolumna: IdKolumny; kierunek: Kierunek }>({ kolumna: 'opublikowano', kierunek: 'malejaco' });
  const [komunikat, setKomunikat] = useState('');

  const wszystkie = useMemo(() => wierszeTabeli(widoki, warstwy), [widoki, warstwy]);
  const wiersze = useMemo(() => sortujWiersze(filtrujWiersze(wszystkie, tekst), sortowanie.kolumna, sortowanie.kierunek), [wszystkie, tekst, sortowanie]);
  const etykietaKolumny = (id: IdKolumny) => KOLUMNY.find(k => k.id === id)?.etykieta ?? id;

  const sortuj = (kolumna: IdKolumny) => {
    const kierunek: Kierunek = sortowanie.kolumna === kolumna ? (sortowanie.kierunek === 'rosnaco' ? 'malejaco' : 'rosnaco') : kierunekPoczatkowy(kolumna);
    setSortowanie({ kolumna, kierunek });
    setKomunikat(`Posortowano według: ${etykietaKolumny(kolumna)}, ${kierunek === 'rosnaco' ? 'rosnąco' : 'malejąco'}.`);
  };

  const pobierz = () => {
    try {
      const csv = budujCsv(NAGLOWKI_CSV, wierszeCsv(wiersze));
      const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' });
      const adres = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = adres; a.download = nazwaPlikuCsv(new Date()); a.rel = 'noopener';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      window.setTimeout(() => URL.revokeObjectURL(adres), 2000);
      setKomunikat(`Pobrano plik CSV: ${liczbaKomunikatow(wiersze.length)}.`);
    } catch {
      setKomunikat('Nie udało się utworzyć pliku CSV w tej przeglądarce.');
    }
  };

  const ariaSort = (id: IdKolumny): 'ascending' | 'descending' | 'none' =>
    sortowanie.kolumna !== id ? 'none' : sortowanie.kierunek === 'rosnaco' ? 'ascending' : 'descending';

  // sam widok jest regionem (section.tz-scena z nazwą widoku), więc tu zwykły kontener: dwa landmarki o tej samej nazwie myliłyby czytnik
  return <div className="tz-tabela">
    <h2 id="tz-tabela-tytul" className="tz-tabela__tytul" tabIndex={-1}>Tabela komunikatów</h2>
    <p className="tz-tabela__opis">Pełny odpowiednik mapy: te same warstwy, czas i województwo co w panelu. Filtry: {opisFiltrow}.</p>

    <div className="tz-tabela__narzedzia">
      <div className="tz-tabela__filtr">
        <label htmlFor="tz-tabela-filtr">Filtruj tabelę</label>
        <input id="tz-tabela-filtr" type="search" value={tekst} autoComplete="off" onChange={e => setTekst(e.target.value)} placeholder="np. wiatr, Kraków, Zgłoszone" />
      </div>
      <button type="button" className="tz-przycisk" onClick={pobierz} disabled={!wiersze.length}>Pobierz widok jako CSV ({wiersze.length})</button>
    </div>
    <p className="tz-tabela__licznik">Wiersze: {wiersze.length}{wiersze.length !== wszystkie.length ? ` z ${wszystkie.length}` : ''}. Plik CSV: średnik jako separator, kodowanie UTF-8.</p>
    <p className="tz-sr" role="status" aria-live="polite" aria-atomic="true">{komunikat || `${liczbaKomunikatow(wiersze.length)} w tabeli.`}</p>

    {!wszystkie.length
      ? <p className="tz-lista__pusta" role="status">Brak komunikatów w wybranym czasie i regionie. To nie znaczy, że nic się nie dzieje: {NIEPEWNOSC}.</p>
      : <div id="tz-tabela" className="tz-tabela__przewijanie" tabIndex={0} role="region" aria-label="Tabela komunikatów (przewijana strzałkami)">
        <table className="tz-tabela__tabela">
          <caption className="tz-sr">Komunikaty ({opisFiltrow}), {liczbaKomunikatow(wiersze.length)}. Nagłówki kolumn sortują tabelę.</caption>
          <thead>
            <tr>
              {KOLUMNY.map(k => <th key={k.id} scope="col" aria-sort={ariaSort(k.id)}>
                <button type="button" className="tz-tabela__sortuj" onClick={() => sortuj(k.id)}>
                  {k.etykieta}
                  <span className="tz-tabela__strzalka" aria-hidden="true">{sortowanie.kolumna === k.id ? (sortowanie.kierunek === 'rosnaco' ? '▲' : '▼') : '↕'}</span>
                </button>
              </th>)}
            </tr>
          </thead>
          <tbody>
            {wiersze.map(w => <tr key={w.id} data-wybrany={wybrany === w.id ? '' : undefined}>
              <td>{w.warstwa}</td>
              <th scope="row">
                <button type="button" className="tz-tabela__tytul-przycisk" aria-pressed={wybrany === w.id} onClick={() => onWybierz(w.id)}>{w.tytul}</button>
              </th>
              <td>{w.status}</td>
              <td>{w.miejsce}</td>
              <td><time dateTime={w.opublikowanoCzas.replace(' ', 'T')}>{w.opublikowano}</time></td>
              <td><time dateTime={w.pobranoCzas.replace(' ', 'T')}>{w.pobrano}</time></td>
              <td>
                {w.zrodlo}
                <a className="tz-tabela__link" href={w.link} target="_blank" rel="noopener noreferrer">Oryginał{host(w.link) ? ` (${host(w.link)})` : ''}<span className="tz-sr"> (otwiera się w nowej karcie)</span></a>
              </td>
            </tr>)}
          </tbody>
        </table>
        {!wiersze.length && <p className="tz-lista__pusta" role="status">Żaden wiersz nie pasuje do filtra „{tekst}”.</p>}
      </div>}
  </div>;
}
