import { useEffect, useRef, useState } from 'react';
import type { Warstwa, WidokWpisu } from './typy';
import { dataIGodzina, host } from './czas';
import { etykietaDokladnosci, opisMiejsca } from './teryt';
import { nazwaZrodla } from './model';
import { kopiujDoSchowka } from './schowek';
import { metaStatusu, metaWarstwy } from './warstwy';
import { EtykietaStatusu, IkonaWarstwy } from './Ikony';

/**
 * Karta wpisu (boczny panel na komputerze, dolny arkusz na telefonie): tytuł, źródło, dwie godziny (publikacja u źródła
 * i pobranie), status, odnośnik do oryginału, oznaczenie „przygotowane automatycznie”, miejsce z dokładnością, kopiowanie linku.
 * Godziny podajemy zawsze jako dwie osobne informacje: pobranie nie jest chwilą wydarzenia.
 */
export interface KartaWpisuProps {
  widok: WidokWpisu;
  warstwy: Warstwa[] | undefined;
  /** Zwraca adres do skopiowania (liczony w chwili kliknięcia, bo zależy od adresu strony). */
  adres: () => string;
  onZamknij: () => void;
}

export function KartaWpisu({ widok, warstwy, adres, onZamknij }: KartaWpisuProps) {
  const { wpis, zdarzenie, status } = widok;
  const naglowek = useRef<HTMLHeadingElement>(null);
  const [skopiowano, setSkopiowano] = useState<'tak' | 'nie' | null>(null);
  const meta = metaWarstwy(wpis.warstwa);
  const nazwaWarstwy = warstwy?.find(w => w.warstwa === wpis.warstwa)?.nazwa ?? meta.opis;
  const zrodlo = nazwaZrodla(warstwy, wpis.zrodlo);
  const inne = (zdarzenie?.wpisy ?? []).filter(w => w.id !== wpis.id);
  const automatycznie = zdarzenie ? zdarzenie.przygotowane_automatycznie : true;

  useEffect(() => { naglowek.current?.focus({ preventScroll: true }); setSkopiowano(null); }, [wpis.id]);

  const kopiuj = async () => {
    const ok = await kopiujDoSchowka(adres());
    setSkopiowano(ok ? 'tak' : 'nie');
    window.setTimeout(() => setSkopiowano(null), 4000);
  };

  return <article className="tz-karta__tresc" aria-labelledby="tz-karta-tytul">
    <div className="tz-karta__gora">
      <p className="tz-karta__warstwa"><IkonaWarstwy kod={wpis.warstwa} />{nazwaWarstwy}</p>
      <button type="button" className="tz-przycisk tz-karta__zamknij" onClick={onZamknij} aria-label="Zamknij kartę wpisu">Zamknij</button>
    </div>
    <h2 id="tz-karta-tytul" className="tz-karta__tytul" tabIndex={-1} ref={naglowek}>{wpis.tytul}</h2>
    <p className="tz-karta__znaczki">
      <EtykietaStatusu status={status} />
      {automatycznie && <span className="tz-znaczek">przygotowane automatycznie</span>}
    </p>
    <p className="tz-karta__opis-statusu">{metaStatusu(status).opis}</p>
    {wpis.tresc && <p className="tz-karta__tresc-wpisu">{wpis.tresc}</p>}

    <dl className="tz-karta__dane">
      <div><dt>Źródło</dt><dd>{zrodlo.nazwa}{zrodlo.instytucja && zrodlo.instytucja !== zrodlo.nazwa ? `, ${zrodlo.instytucja}` : ''}</dd></div>
      <div><dt>Opublikowano u źródła</dt><dd>{dataIGodzina(wpis.opublikowano_at)}{meta.uwagaCzas && <small>{meta.uwagaCzas}</small>}</dd></div>
      <div><dt>Pobrano przez nas</dt><dd>{dataIGodzina(wpis.pobrano_at)}</dd></div>
      <div><dt>Miejsce</dt><dd>{opisMiejsca(wpis)}<small>Dokładność: {etykietaDokladnosci(wpis.dokladnosc)}</small></dd></div>
    </dl>

    <p className="tz-karta__oryginal">
      <a className="tz-przycisk tz-przycisk--glowny" href={wpis.link} target="_blank" rel="noopener noreferrer">
        Otwórz oryginał u źródła{host(wpis.link) ? ` (${host(wpis.link)})` : ''}
      </a>
    </p>
    <div className="tz-karta__kopiuj">
      <button type="button" className="tz-przycisk" onClick={kopiuj}>Kopiuj link do wpisu</button>
      <span role="status" aria-live="polite">{skopiowano === 'tak' ? 'Skopiowano link.' : skopiowano === 'nie' ? 'Nie udało się skopiować, skopiuj adres z paska przeglądarki.' : ''}</span>
    </div>

    {zdarzenie && <section className="tz-karta__zdarzenie" aria-label="Zdarzenie">
      <h3>Zdarzenie</h3>
      <p>{zdarzenie.tytul_roboczy}</p>
      {zdarzenie.zweryfikowal && <p className="tz-karta__weryfikacja">Zweryfikował: {zdarzenie.zweryfikowal}{zdarzenie.zweryfikowano_at ? `, ${dataIGodzina(zdarzenie.zweryfikowano_at)}` : ''}</p>}
      {inne.length > 0 && <>
        <p className="tz-karta__podtytul">Inne komunikaty w tym zdarzeniu ({inne.length})</p>
        <ul>{inne.slice(0, 6).map(w => <li key={w.id}><span>{dataIGodzina(w.opublikowano_at)}</span> {w.tytul}</li>)}</ul>
      </>}
    </section>}
  </article>;
}
