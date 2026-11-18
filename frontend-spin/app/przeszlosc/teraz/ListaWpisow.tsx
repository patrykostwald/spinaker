import type { Warstwa, WidokWpisu } from './typy';
import { czasPublikacji } from './czas';
import { opisMiejsca } from './teryt';
import { nazwaZrodla } from './model';
import { metaWarstwy } from './warstwy';
import { EtykietaStatusu, IkonaWarstwy } from './Ikony';

/** Lista komunikatów (widok „lista zamiast mapy” i lista obszarów bez granic na mapie). Kolejność jak z API: od najnowszych. */
export interface ListaWpisowProps {
  widoki: WidokWpisu[];
  warstwy: Warstwa[] | undefined;
  wybrany: number | null;
  onWybierz: (id: number) => void;
  etykieta: string;
  /** Tekst, gdy lista jest pusta. */
  pusta: string;
}

export function ListaWpisow({ widoki, warstwy, wybrany, onWybierz, etykieta, pusta }: ListaWpisowProps) {
  if (!widoki.length) return <p className="tz-lista__pusta" role="status">{pusta}</p>;
  return <ol className="tz-lista" aria-label={etykieta}>
    {widoki.map(({ wpis, status }) => {
      const nazwa = warstwy?.find(w => w.warstwa === wpis.warstwa)?.nazwa ?? metaWarstwy(wpis.warstwa).opis;
      return <li key={wpis.id}>
        <button type="button" className="tz-pozycja" aria-pressed={wybrany === wpis.id} onClick={() => onWybierz(wpis.id)}>
          <IkonaWarstwy kod={wpis.warstwa} />
          <span className="tz-pozycja__glowna">
            <span className="tz-pozycja__tytul">{wpis.tytul}</span>
            <span className="tz-pozycja__meta" title={`${nazwa} · ${nazwaZrodla(warstwy, wpis.zrodlo).nazwa}`}>{nazwa} · {nazwaZrodla(warstwy, wpis.zrodlo).nazwa}</span>
            <span className="tz-pozycja__meta" title={`${czasPublikacji(wpis)} · ${opisMiejsca(wpis)}`}>{czasPublikacji(wpis)} · {opisMiejsca(wpis)}</span>
          </span>
          <EtykietaStatusu status={status} />
        </button>
      </li>;
    })}
  </ol>;
}
