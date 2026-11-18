import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { Okres, Warstwa, WidokWpisu } from './typy';
import { dataIGodzina, host, odGodziny } from './czas';
import { adresZrodla } from './link';
import { nazwaZrodla } from './model';
import { MAKS_POWIATOW, liczbaKomunikatow, szukajPowiatow, zakresDlaPowiatu, zakresTekstem } from './powiaty';
import type { Zakres } from './powiaty';
import { dlaPowiatu, pelnaNazwaPowiatu, powiatOKodzie } from './slownik';
import { kopiujDoSchowka } from './schowek';
import { NIEPEWNOSC, metaStatusu, metaWarstwy } from './warstwy';
import { EtykietaStatusu, IkonaWarstwy } from './Ikony';
import { WyborOkresu } from './WyborOkresu';

/**
 * Widok „Mój powiat”: bez mapy, duży druk, do 5 powiatów (albo miast na prawach powiatu) zapisanych w przeglądarce.
 * Dla każdego powiatu: komunikaty z wybranego okresu, które go dotyczą po kodzie TERYT wpisu (powiat, gmina w powiecie,
 * całe województwo), z tymi samymi godzinami i statusem co karta. Brak komunikatów to „Brak w naszych danych...”,
 * nigdy „spokojnie”: brak wpisu nie jest informacją o braku zagrożenia.
 * Laws of UX: Hick (jeden główny wybór: dodaj powiat), Fitts (cele min. 48 px), Proximity i Common Region (sekcja na powiat),
 * Tesler (odmiana i literówki bierze na siebie wyszukiwarka), Jakob (pole z podpowiedziami jak w każdym wyszukiwaniu).
 */
export interface MojPowiatProps {
  powiaty: string[];
  onZmien: (kody: string[]) => void;
  okres: Okres;
  onOkres: (o: Okres) => void;
  /** Wpisy wybranych powiatów (wszystkie z województw wybranych powiatów) ze statusem ze zdarzeń. */
  widoki: WidokWpisu[];
  warstwy: Warstwa[] | undefined;
  /** Zapytanie o wpisy jeszcze bez odpowiedzi. */
  ladowanie: boolean;
  /** Zapytanie o wpisy zakończyło się błędem i nie ma żadnych danych. */
  blad: boolean;
  /** Pobraliśmy tylko najnowsze wpisy: brak wpisu dla powiatu nie jest wtedy pewny. */
  uciete: boolean;
  /** Liczba wpisów o nieznanym formacie, pominiętych przy pobraniu (wtedy „brak” też nie jest pewny). */
  pominiete: number;
  /** Któraś warstwa ma lukę w danych (zdanie o tym jest też w linii stanu u góry). */
  lukaWDanych: boolean;
  /** Początek okresu (ISO), liczony od ostatniego pobrania wpisów (stały między odświeżeniami). */
  poczatekOkresu: string;
  /** Adres zestawu do skopiowania (liczony w chwili kliknięcia). */
  adres: () => string;
}

const OPIS_OKRESU: Record<Okres, string> = { '1h': 'w ostatniej godzinie', '24h': 'w ostatnich 24 godzinach', '7d': 'w ostatnich 7 dniach' };

interface PozycjaWyboru { onDodaj: (kod: string) => void; wybrane: string[]; pelny: boolean; onKomunikat: (t: string) => void }

/** Pole z podpowiedziami (wzorzec ARIA combobox z listą): strzałki, Enter, Esc; odmiana nazw rozumiana przez wyszukiwarkę. */
function WyborPowiatu({ onDodaj, wybrane, pelny, onKomunikat }: PozycjaWyboru) {
  const baza = useId();
  const idListy = `${baza}-lista`;
  const idOpisu = `${baza}-opis`;
  const pole = useRef<HTMLInputElement>(null);
  const [tekst, setTekst] = useState('');
  const [otwarta, setOtwarta] = useState(false);
  const [aktywny, setAktywny] = useState(-1);
  const wyniki = useMemo(() => szukajPowiatow(tekst, { pomin: wybrane }), [tekst, wybrane]);
  const pokazListe = otwarta && tekst.trim().length > 0;

  const wybierz = (kod: string) => {
    onDodaj(kod);
    setTekst(''); setOtwarta(false); setAktywny(-1);
    pole.current?.focus();
  };

  const klawisz = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!wyniki.length) return;
      e.preventDefault();
      setOtwarta(true);
      setAktywny(a => e.key === 'ArrowDown' ? (a + 1) % wyniki.length : (a <= 0 ? wyniki.length - 1 : a - 1));
    } else if (e.key === 'Enter') {
      if (pokazListe && wyniki.length) { e.preventDefault(); wybierz(wyniki[aktywny >= 0 ? aktywny : 0].kod); }
    } else if (e.key === 'Escape') {
      if (pokazListe) { e.preventDefault(); e.stopPropagation(); setOtwarta(false); setAktywny(-1); }
      else if (tekst) { e.preventDefault(); e.stopPropagation(); setTekst(''); }
    }
  };

  // liczba podpowiedzi dla czytnika ekranu (uprzejmie, po zmianie wpisanego tekstu)
  useEffect(() => {
    if (!tekst.trim()) return;
    const t = window.setTimeout(() => onKomunikat(wyniki.length ? `Podpowiedzi: ${wyniki.length}. Strzałki w dół i w górę wybierają, Enter dodaje.` : 'Brak podpowiedzi. Spróbuj wpisać początek nazwy powiatu albo miasta.'), 400);
    return () => window.clearTimeout(t);
  }, [tekst, wyniki.length, onKomunikat]);

  return <div className="tz-mp-wybor">
    <label className="tz-mp-etykieta" htmlFor={`${baza}-pole`}>Dodaj powiat albo miasto na prawach powiatu</label>
    <div className="tz-mp-kontrolka">
      <input
        id={`${baza}-pole`} ref={pole} type="text" className="tz-mp-pole" role="combobox" autoComplete="off" autoCapitalize="none" spellCheck={false}
        aria-expanded={pokazListe && wyniki.length > 0} aria-controls={idListy} aria-autocomplete="list" aria-describedby={idOpisu}
        aria-activedescendant={pokazListe && aktywny >= 0 ? `${baza}-opcja-${aktywny}` : undefined}
        disabled={pelny} value={tekst} placeholder={pelny ? 'Wybrano maksimum powiatów' : 'np. Przemyśl, w Krakowie'}
        onChange={e => { setTekst(e.target.value); setOtwarta(true); setAktywny(-1); }}
        onKeyDown={klawisz} onBlur={() => setOtwarta(false)} onFocus={() => { if (tekst.trim()) setOtwarta(true); }}
      />
      <ul id={idListy} role="listbox" aria-label="Podpowiedzi powiatów" className="tz-mp-podpowiedzi" hidden={!pokazListe || !wyniki.length}>
        {wyniki.map((p, i) => <li
          key={p.kod} id={`${baza}-opcja-${i}`} role="option" aria-selected={i === aktywny} data-aktywna={i === aktywny ? '' : undefined}
          onMouseDown={e => e.preventDefault()} onClick={() => wybierz(p.kod)} onMouseMove={() => setAktywny(i)}>
          {pelnaNazwaPowiatu(p)}
        </li>)}
      </ul>
    </div>
    <p id={idOpisu} className="tz-mp-pomoc">
      {pelny ? `Wybrano ${MAKS_POWIATOW} powiatów, to maksimum. Usuń któryś, aby dodać inny.` : 'Wpisz początek nazwy, także w odmianie (w Krakowie, powiatu przemyskiego) albo kod TERYT.'}
    </p>
    {pokazListe && !wyniki.length && <p className="tz-mp-pomoc tz-mp-pomoc--brak">Nie znaleziono powiatu. Spróbuj początku nazwy albo kodu TERYT.</p>}
  </div>;
}

function Wpis({ widok, warstwy, zakres, kodPowiatu }: { widok: WidokWpisu; warstwy: Warstwa[] | undefined; zakres: Zakres; kodPowiatu: string }) {
  const { wpis, status, zdarzenie } = widok;
  const meta = metaWarstwy(wpis.warstwa);
  const nazwaWarstwy = warstwy?.find(w => w.warstwa === wpis.warstwa)?.nazwa ?? meta.opis;
  const zrodlo = nazwaZrodla(warstwy, wpis.zrodlo);
  const automatycznie = zdarzenie ? zdarzenie.przygotowane_automatycznie : true;
  return <article className="tz-mp-wpis" aria-label={wpis.tytul}>
    <p className="tz-mp-wpis__meta"><IkonaWarstwy kod={wpis.warstwa} rozmiar={18} /><span>{nazwaWarstwy}</span></p>
    <h4 className="tz-mp-wpis__tytul">{wpis.tytul}</h4>
    <p className="tz-mp-wpis__znaczki">
      <EtykietaStatusu status={status} />
      {automatycznie && <span className="tz-znaczek">przygotowane automatycznie</span>}
      {zakres !== 'powiat' && <span className="tz-znaczek tz-znaczek--zakres">{zakresTekstem(zakres, kodPowiatu)}</span>}
    </p>
    <p className="tz-mp-wpis__status">{metaStatusu(status).opis}</p>
    {wpis.tresc && <p className="tz-mp-wpis__tresc">{wpis.tresc}</p>}
    <dl className="tz-mp-wpis__dane">
      <div><dt>Opublikowano u źródła</dt><dd>{dataIGodzina(wpis.opublikowano_at)}{meta.uwagaCzas && <small>{meta.uwagaCzas}</small>}</dd></div>
      <div><dt>Pobrano przez nas</dt><dd>{dataIGodzina(wpis.pobrano_at)}</dd></div>
      <div><dt>Źródło</dt><dd>{zrodlo.nazwa}{zrodlo.instytucja && zrodlo.instytucja !== zrodlo.nazwa ? `, ${zrodlo.instytucja}` : ''}</dd></div>
    </dl>
    {adresZrodla(wpis.link)
      ? <p><a className="tz-przycisk tz-przycisk--glowny" href={adresZrodla(wpis.link) as string} target="_blank" rel="noopener noreferrer">
        Otwórz oryginał u źródła{host(wpis.link) ? ` (${host(wpis.link)})` : ''}<span className="tz-sr"> (otwiera się w nowej karcie)</span>
      </a></p>
      : <p className="tz-brak-linku">Źródło nie podało poprawnego odnośnika do oryginału.</p>}
  </article>;
}

export function MojPowiat(p: MojPowiatProps) {
  const [komunikat, setKomunikat] = useState('');
  const [skopiowano, setSkopiowano] = useState<'tak' | 'nie' | null>(null);
  const pelny = p.powiaty.length >= MAKS_POWIATOW;
  const poczatek = odGodziny(p.poczatekOkresu);

  const dodaj = (kod: string) => {
    if (p.powiaty.includes(kod) || p.powiaty.length >= MAKS_POWIATOW) return;
    const powiat = powiatOKodzie(kod);
    p.onZmien([...p.powiaty, kod]);
    setKomunikat(`Dodano: ${powiat ? pelnaNazwaPowiatu(powiat) : kod}. Wybrano ${p.powiaty.length + 1} z ${MAKS_POWIATOW}.`);
  };
  const usun = (kod: string) => {
    const powiat = powiatOKodzie(kod);
    p.onZmien(p.powiaty.filter(k => k !== kod));
    setKomunikat(`Usunięto: ${powiat ? pelnaNazwaPowiatu(powiat) : kod}.`);
    window.setTimeout(() => document.getElementById('tz-mp-pierwsze-pole')?.querySelector<HTMLInputElement>('input')?.focus(), 0);
  };
  const kopiuj = async () => {
    const ok = await kopiujDoSchowka(p.adres());
    setSkopiowano(ok ? 'tak' : 'nie');
    window.setTimeout(() => setSkopiowano(null), 4000);
  };

  const sekcje = useMemo(() => p.powiaty.map(kod => {
    const wpisy = p.widoki
      .map(v => ({ v, zakres: zakresDlaPowiatu(v.wpis, kod) }))
      .filter((x): x is { v: WidokWpisu; zakres: Zakres } => x.zakres !== null)
      .sort((a, b) => Date.parse(b.v.wpis.opublikowano_at) - Date.parse(a.v.wpis.opublikowano_at));
    return { kod, powiat: powiatOKodzie(kod), wpisy };
  }), [p.powiaty, p.widoki]);

  // sam widok jest regionem (section.tz-scena z nazwą „Mój powiat”), więc tu zwykły kontener; regiony dostają dopiero sekcje powiatów
  return <div className="tz-mp">
    <h2 id="tz-mp-tytul" className="tz-mp-tytul" tabIndex={-1}>Mój powiat</h2>
    <p className="tz-mp-lead">Wybierz do {MAKS_POWIATOW} powiatów albo miast na prawach powiatu. Pokażemy komunikaty, które ich dotyczą. Wybór zapisujemy tylko w tej przeglądarce.</p>

    <div className="tz-mp-okres">
      <p className="tz-mp-etykieta" id="tz-mp-okres-etykieta">Okres</p>
      <WyborOkresu okres={p.okres} onOkres={p.onOkres} nazwa="tz-okres-powiat" opisanePrzez="tz-mp-okres-etykieta" klasa="tz-mp-segmenty" />
    </div>

    <div id="tz-mp-pierwsze-pole"><WyborPowiatu onDodaj={dodaj} wybrane={p.powiaty} pelny={pelny} onKomunikat={setKomunikat} /></div>

    <p className="tz-sr" role="status" aria-live="polite" aria-atomic="true">{komunikat}</p>

    {p.powiaty.length > 0 && <>
      <ul className="tz-mp-wybrane" aria-label={`Wybrane powiaty: ${p.powiaty.length} z ${MAKS_POWIATOW}`}>
        {p.powiaty.map(kod => {
          const powiat = powiatOKodzie(kod);
          const nazwa = powiat ? pelnaNazwaPowiatu(powiat) : kod;
          return <li key={kod}>
            <span>{nazwa}</span>
            <button type="button" onClick={() => usun(kod)} aria-label={`Usuń: ${nazwa}`}>Usuń</button>
          </li>;
        })}
      </ul>
      <div className="tz-mp-udostepnij">
        <button type="button" className="tz-przycisk" onClick={kopiuj}>Kopiuj link do tego zestawu</button>
        <span role="status" aria-live="polite">{skopiowano === 'tak' ? 'Skopiowano link.' : skopiowano === 'nie' ? 'Nie udało się skopiować, skopiuj adres z paska przeglądarki.' : ''}</span>
      </div>
    </>}

    {p.powiaty.length === 0 && <p className="tz-mp-pusto">Nie wybrano jeszcze żadnego powiatu. Wpisz nazwę w polu powyżej.</p>}

    {sekcje.map(({ kod, powiat, wpisy }) => {
      const idNaglowka = `tz-mp-h-${kod}`;
      const nazwa = powiat ? pelnaNazwaPowiatu(powiat) : `powiat o kodzie ${kod}`;
      return <section key={kod} className="tz-mp-sekcja" aria-labelledby={idNaglowka}>
        <h3 id={idNaglowka} className="tz-mp-sekcja__tytul">{nazwa}</h3>
        {p.ladowanie && <p className="tz-mp-stan" role="status">Wczytujemy komunikaty…</p>}
        {!p.ladowanie && p.blad && <p className="tz-mp-stan tz-mp-stan--uwaga" role="alert">Nie udało się pobrać komunikatów: {NIEPEWNOSC}.</p>}
        {!p.ladowanie && !p.blad && wpisy.length > 0 && <>
          <p className="tz-mp-liczba">{liczbaKomunikatow(wpisy.length)} {OPIS_OKRESU[p.okres]}, od najnowszego.</p>
          <ul className="tz-mp-wpisy">
            {wpisy.map(({ v, zakres }) => <li key={v.wpis.id}><Wpis widok={v} warstwy={p.warstwy} zakres={zakres} kodPowiatu={kod} /></li>)}
          </ul>
        </>}
        {!p.ladowanie && !p.blad && wpisy.length === 0 && <p className="tz-mp-stan tz-mp-stan--brak" role="status">
          Brak w naszych danych {powiat ? dlaPowiatu(powiat) : `dla powiatu o kodzie ${kod}`} {poczatek}. Sprawdź Alert RCB i 112.
          {p.uciete && ' Pokazujemy tylko najnowsze komunikaty z województwa, więc mogło ich być więcej.'}
          {p.pominiete > 0 && ' Część komunikatów miała nieznany format i została pominięta.'}
          {p.lukaWDanych && ' Część źródeł ma lukę w danych (ostrzeżenie u góry strony).'}
        </p>}
      </section>;
    })}
  </div>;
}
