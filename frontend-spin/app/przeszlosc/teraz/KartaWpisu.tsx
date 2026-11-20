import { useEffect, useRef, useState } from 'react';
import type { Warstwa, WidokWpisu } from './typy';
import { czasPobrania, czasPublikacji, dataIGodzina, host } from './czas';
import { adresZrodla } from './link';
import { etykietaDokladnosci, opisMiejsca } from './teryt';
import { nazwaZrodla } from './model';
import { kopiujDoSchowka } from './schowek';
import { metaStatusu, metaWarstwy } from './warstwy';
import { EtykietaStatusu, IkonaWarstwy } from './Ikony';
import type { DaneZrodel } from './zrodla';
import { metaLacza, znajdzZrodlo } from './zrodla';
import { ZrodloBadge } from './ZrodloBadge';
import { StanZrodlaWpisu } from './ZdrowieZrodla';

/**
 * Karta wpisu (boczny panel na komputerze, dolny arkusz na telefonie): tytuł, źródło, dwie godziny (publikacja u źródła
 * i pobranie), status, odnośnik do oryginału, oznaczenie „przygotowane automatycznie”, miejsce z dokładnością, kopiowanie linku.
 * Godziny podajemy zawsze jako dwie osobne informacje: pobranie nie jest chwilą wydarzenia. Gdy źródło podało tylko datę,
 * pokazujemy samą datę (bez fikcyjnej północy); brak czasu pobrania to „brak danych”. Podpis źródła (`atrybucja` z API,
 * np. IMGW o przetworzeniu danych) jest osobnym wierszem (recenzja PR #38, P1-5 i P1-6).
 * Wiersz „Łącze i stan źródła” (gdy podano `zrodla`): rodzaj łącza z opisem oraz zdrowie źródła; luka albo błąd to „brak w naszych danych”.
 */
export interface KartaWpisuProps {
  widok: WidokWpisu;
  warstwy: Warstwa[] | undefined;
  /** Stan źródeł (łącze, zdrowie); pominięty = bez wiersza „Łącze i stan źródła”. */
  zrodla?: DaneZrodel;
  /** Zwraca adres do skopiowania (liczony w chwili kliknięcia, bo zależy od adresu strony). */
  adres: () => string;
  onZamknij: () => void;
}

export function KartaWpisu({ widok, warstwy, zrodla, adres, onZamknij }: KartaWpisuProps) {
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
      {zrodla && <div><dt>Łącze i stan źródła</dt><dd className="tz-karta__lacze">
        {!zrodla.ladowanie && <>
          <ZrodloBadge rodzaj={znajdzZrodlo(zrodla, wpis.zrodlo)?.rodzaj_lacza} />
          <small>{metaLacza(znajdzZrodlo(zrodla, wpis.zrodlo)?.rodzaj_lacza).opis}</small>
        </>}
        <StanZrodlaWpisu zrodla={zrodla} slug={wpis.zrodlo} />
      </dd></div>}
      <div><dt>Opublikowano u źródła</dt><dd>{czasPublikacji(wpis)}{meta.uwagaCzas && <small>{meta.uwagaCzas}</small>}</dd></div>
      <div><dt>Pobrano przez nas</dt><dd>{czasPobrania(wpis.pobrano_at)}</dd></div>
      <div><dt>Miejsce</dt><dd>{opisMiejsca(wpis)}<small>Dokładność: {etykietaDokladnosci(wpis.dokladnosc)}</small></dd></div>
      {wpis.atrybucja && <div><dt>Podpis źródła</dt><dd className="tz-karta__atrybucja">{wpis.atrybucja}</dd></div>}
    </dl>

    <p className="tz-karta__oryginal">
      {adresZrodla(wpis.link)
        ? <a className="tz-przycisk tz-przycisk--glowny" href={adresZrodla(wpis.link) as string} target="_blank" rel="noopener noreferrer">
          Otwórz oryginał u źródła{host(wpis.link) ? ` (${host(wpis.link)})` : ''}<span className="tz-sr"> (otwiera się w nowej karcie)</span>
        </a>
        : <span className="tz-brak-linku">Źródło nie podało poprawnego odnośnika do oryginału.</span>}
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
        <ul>{inne.slice(0, 6).map(w => <li key={w.id}><span>{czasPublikacji(w)}</span> {w.tytul}</li>)}</ul>
      </>}
    </section>}
  </article>;
}
