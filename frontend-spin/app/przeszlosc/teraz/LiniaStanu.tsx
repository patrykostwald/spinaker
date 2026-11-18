import { useEffect, useRef, useState } from 'react';
import type { PodsumowanieStanu } from './model';
import { godzina } from './czas';
import { NIEPEWNOSC, ZDANIE_STALE } from './warstwy';
import { IkonaOstrzezenia } from './Ikony';

/**
 * Linia stanu u góry. Zawsze widoczne, bez dotykania: stałe zdanie „To nie jest strona urzędowa...” i ostrzeżenie o luce
 * albo braku połączenia (zdania z API dosłownie; przy braku połączenia „nie mamy pewności, sprawdź Alert RCB i 112”).
 * Zwinięte do jednej linii z rozwinięciem: oznaczenie „Dane przykładowe” i stan źródeł (szczegóły każdej warstwy
 * rozwijają się jako nakładka, więc mapa pod spodem się nie przesuwa). Nigdy „spokojnie” ani „bezpiecznie”: brak
 * komunikatów nie jest informacją o braku zagrożenia.
 * Czytniki ekranu: luka w danych jest zapowiadana uprzejmie (role status), brak połączenia natychmiast (role alert);
 * odświeżanie godziny pobrania nie jest zapowiadane.
 * Cała sekcja stoi nad przewijaną treścią (siatka .tz), a arkusze panelu i karty zaczynają się pod nią, więc stałe zdanie
 * nie wychodzi poza ekran ani nie jest przykrywane. Czas odświeżenia stanu źródeł (stan/) i komunikatów (wpisy/) to dwie osobne informacje.
 */
export interface LiniaStanuProps {
  probne: boolean;
  podsumowanie: PodsumowanieStanu | null;
  online: boolean;
  /** Zapytanie o stan albo o wpisy zakończyło się błędem. */
  blad: boolean;
  /** Czas ostatniego udanego odświeżenia wpisów (ms) albo null, gdy jeszcze nic nie przyszło. */
  odswiezonoWpisy: number | null;
  /** Czas ostatniego udanego odświeżenia stanu źródeł (stan/, ms) albo null. */
  odswiezonoStan: number | null;
  ladowanie: boolean;
}

const MAKS_OSTRZEZEN = 3;

export function LiniaStanu({ probne, podsumowanie, online, blad, odswiezonoWpisy, odswiezonoStan, ladowanie }: LiniaStanuProps) {
  const [otwarta, setOtwarta] = useState(false);
  const przycisk = useRef<HTMLButtonElement>(null);
  const brakPolaczenia = !online || blad;
  const rcb = podsumowanie?.wiersze.find(w => w.warstwa === 'rcb' && w.aktywna);
  const pierwsza = rcb ?? podsumowanie?.wiersze.find(w => w.aktywna);
  const ostrzezenia = podsumowanie?.ostrzezenia ?? [];
  const godzinaWpisow = odswiezonoWpisy ? godzina(new Date(odswiezonoWpisy).toISOString()) : '';
  const godzinaStanu = odswiezonoStan ? godzina(new Date(odswiezonoStan).toISOString()) : '';

  // Esc zamyka rozwinięcie i wraca na przycisk (nie zamyka przy tym karty ani panelu)
  useEffect(() => {
    if (!otwarta) return;
    const klawisz = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      e.stopImmediatePropagation();
      setOtwarta(false);
      przycisk.current?.focus();
    };
    window.addEventListener('keydown', klawisz, true);
    return () => window.removeEventListener('keydown', klawisz, true);
  }, [otwarta]);

  // widoczne zawsze: ostrzeżenie o luce albo o braku połączenia
  let alarm: React.ReactNode = null;
  if (brakPolaczenia) {
    alarm = <>
      <strong>{online ? 'Brak połączenia z serwerem' : 'Brak połączenia z internetem'}: {NIEPEWNOSC}.</strong>
      {godzinaWpisow && <> Ostatnie komunikaty pobraliśmy o godz. {godzinaWpisow}.</>}
    </>;
  }
  let luka: React.ReactNode = null;
  if (!brakPolaczenia && podsumowanie && (ostrzezenia.length || podsumowanie.niepelne)) {
    luka = <>
      {podsumowanie.niepelne && <span className="tz-stan__zdanie"><strong>Stan części źródeł ma nieznany format:</strong> {NIEPEWNOSC}. </span>}
      {ostrzezenia.slice(0, MAKS_OSTRZEZEN).map(o => <span key={o.warstwa} className="tz-stan__zdanie"><strong>{o.nazwa}:</strong> {o.komunikat}. </span>)}
      {ostrzezenia.length > MAKS_OSTRZEZEN && <span className="tz-stan__zdanie">Jeszcze {ostrzezenia.length - MAKS_OSTRZEZEN} warstw z tą samą uwagą (szczegóły po rozwinięciu stanu).</span>}
    </>;
  }

  // jedna linia zwinięta: oznaczenie próbne i stan źródeł
  let stan: string;
  if (brakPolaczenia) stan = godzinaWpisow ? `ostatnie komunikaty z godz. ${godzinaWpisow}` : 'brak danych';
  else if (!podsumowanie) stan = ladowanie ? 'sprawdzamy stan źródeł…' : `stan źródeł niedostępny: ${NIEPEWNOSC}`;
  else if (pierwsza) stan = `${pierwsza.nazwa}: ${pierwsza.ostatniePobranie}, ${pierwsza.komunikaty}`;
  // wiersze odrzucone przez walidator: nie wiemy, czy źródła działają, więc nie piszemy „brak aktywnych źródeł”
  else stan = podsumowanie.niepelne ? `stan źródeł niepełny: ${NIEPEWNOSC}` : 'brak aktywnych źródeł';

  return <section className="tz-stan" aria-label="Stan danych" data-poziom={alarm || luka ? 'ostrzezenie' : 'ok'}>
    <p className="tz-stan__stale">{ZDANIE_STALE}</p>

    <div role="alert" className="tz-stan__alarm">
      {alarm && <p className="tz-stan__ostrz"><span className="tz-stan__ik"><IkonaOstrzezenia /></span><span>{alarm}</span></p>}
    </div>
    <div role="status" className="tz-stan__alarm">
      {luka && <p className="tz-stan__ostrz"><span className="tz-stan__ik"><IkonaOstrzezenia /></span><span>{luka}</span></p>}
    </div>

    <button ref={przycisk} type="button" className="tz-stan__przelacznik" aria-expanded={otwarta} aria-controls="tz-stan-szczegoly" onClick={() => setOtwarta(v => !v)}>
      <span className="tz-stan__jedna">
        {probne && <><strong className="tz-stan__probne-etykieta">Dane przykładowe</strong><span aria-hidden="true"> · </span></>}
        <span>{stan}</span>
      </span>
      <span className="tz-stan__rozwin">{otwarta ? 'Zwiń' : 'Szczegóły'}</span>
    </button>

    <div id="tz-stan-szczegoly" className="tz-stan__szczegoly" hidden={!otwarta}>
      {probne && <p className="tz-stan__probne" role="note"><strong>Dane przykładowe.</strong> To nie są prawdziwe komunikaty, tylko podgląd wyglądu strony.</p>}
      {podsumowanie
        ? <>
          <p className="tz-stan__info">{podsumowanie.informacja}.</p>
          <p className="tz-stan__czasy">
            <span>Stan źródeł odświeżono: {godzinaStanu ? `o godz. ${godzinaStanu}` : 'jeszcze nie'}.</span>{' '}
            <span>Komunikaty odświeżono: {godzinaWpisow ? `o godz. ${godzinaWpisow}` : 'jeszcze nie'}.</span>
          </p>
          <ul>
            {podsumowanie.wiersze.map(w => <li key={w.warstwa} data-aktywna={w.aktywna ? '' : undefined}>
              <strong>{w.nazwa}</strong>
              <span>{w.aktywna ? `${w.ostatniePobranie}, ${w.komunikaty}` : 'brak źródeł, warstwa w przygotowaniu'}</span>
              {w.komunikat && <em>{w.komunikat}</em>}
            </li>)}
          </ul>
        </>
        : <p className="tz-stan__info">Stan źródeł jeszcze się nie wczytał.</p>}
      <button type="button" className="tz-przycisk tz-stan__zamknij" onClick={() => { setOtwarta(false); przycisk.current?.focus(); }}>Zwiń stan</button>
    </div>
  </section>;
}
