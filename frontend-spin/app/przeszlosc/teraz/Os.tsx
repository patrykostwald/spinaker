'use client';
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { useWarstwy } from './api';
import {
  PREDKOSCI, etykietaStanu, indeksPrzedzialu, klatkaOdtwarzania, kreskowany, momentStanu, odstepOdtwarzania, opisBrakowKrotko, opisBrakowNa, opisLuk, opisLukKrotko,
  opisMomentu, opisOkna, opisSlupka, podpisyOsi, poprawnaPredkosc, przedzialyOsi, przesun, scalSlupki, startOdtwarzania, wysokosci,
} from './czasOsi';
import { useOgraniczonyRuch, useOs, type Historia, type WynikWpisowHistorii } from './useHistoria';
import type { Okres } from './typy';
import { OKRESY } from './warstwy';

/**
 * Oś czasu „Teraz” (W4): przełącznik TODAY / PRZESZŁOŚĆ, histogram liczby komunikatów (os/), suwak momentu, krok dzień / godzina
 * i odtwarzanie (bez niego przy prefers-reduced-motion). Pas stoi między linią stanu a mapą, w stałym miejscu i o stałej wysokości
 * w obu trybach (zmienia się tylko wygląd baneru). Lewa część jest wyrównana do panelu warstw, histogram do mapy.
 * Luki (liczba null, luka retencji, luka źródła) są kreskowane z podpisem; zero rysujemy tylko wtedy, gdy mamy dane.
 * Laws of UX: Jakob (suwak jak w odtwarzaczu), Hick (jeden przełącznik trybu, reszta pomocnicza), Fitts (cele 44 px),
 * Von Restorff (jedno wyróżnienie: baner archiwum), Doherty (następna klatka pobierana z wyprzedzeniem).
 */
export interface OsProps {
  historia: Historia;
  probne: boolean;
  okres: Okres;
  /** Wynik useWpisyWTrybie: godzina odświeżenia (TODAY), luki stanu na moment (PRZESZŁOŚĆ) i wczytywanie (tempo odtwarzania). */
  wpisy: { data?: WynikWpisowHistorii; dataUpdatedAt: number; isFetching?: boolean };
}

const MS_OKRESU = (okres: Okres) => OKRESY.find(o => o.id === okres)?.ms ?? 86_400_000;
const OKNO_KROTKO: Record<Okres, string> = { '1h': 'Okno 1 godz.', '24h': 'Okno 24 godz.', '7d': 'Okno 7 dni' };

function Ikona({ d }: { d: string }) {
  return <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d={d} fill="currentColor" /></svg>;
}
const IKONA_WSTECZ = 'M15.5 5.5 9 12l6.5 6.5-1.4 1.4L6.2 12l7.9-7.9z';
const IKONA_NAPRZOD = 'M8.5 5.5 15 12l-6.5 6.5 1.4 1.4 7.9-7.9-7.9-7.9z';
const IKONA_ODTWORZ = 'M8 5v14l11-7z';
const IKONA_PAUZA = 'M7 5h4v14H7zM13 5h4v14h-4z';

export function Os({ historia, probne, okres, wpisy }: OsProps) {
  const { stan, teraz, gotowa, odtwarzanie, predkosc, pokazMoment, pokazDzis, ustawOdtwarzanie } = historia;
  const archiwum = stan.tryb === 'przeszlosc' && stan.na !== null;
  const ograniczonyRuch = useOgraniczonyRuch();
  const osQ = useOs(probne, stan, teraz, gotowa);
  const warstwyQ = useWarstwy(probne);

  const nazwy = useMemo(() => {
    const m = new Map<string, string>();
    for (const w of warstwyQ.data ?? []) for (const z of w.zrodla) m.set(z.slug, z.nazwa);
    return (slug: string) => m.get(slug) ?? slug;
  }, [warstwyQ.data]);

  // poprzednia odpowiedź (keepPreviousData) tylko dla tej samej osi dni; inna oś przed odpowiedzią to stan „wczytujemy”
  const dane = osQ.data && !(osQ.isPlaceholderData && (osQ.data.krok !== stan.krok || stan.krok === 'godzina')) ? osQ.data : undefined;
  const lista = useMemo(() => (gotowa ? przedzialyOsi(stan, teraz) : []), [gotowa, stan, teraz]);
  const slupki = useMemo(() => scalSlupki(lista, dane, teraz, !!osQ.isError && !dane), [lista, dane, teraz, osQ.isError]);
  const wys = useMemo(() => wysokosci(slupki), [slupki]);
  const n = slupki.length;
  const indeks = archiwum ? indeksPrzedzialu(lista, stan.na as number) : Math.max(0, n - 1);
  const moment = momentStanu(stan, teraz);
  const poczatekOkna = moment - MS_OKRESU(okres);

  const wstecz = gotowa ? przesun(stan, -1, teraz) : moment;
  const naprzod = gotowa ? przesun(stan, 1, teraz) : moment;
  const moznaWstecz = gotowa && wstecz < moment;
  const moznaNaprzod = gotowa && archiwum && naprzod > moment;
  const jednostka = stan.krok === 'dzien' ? 'dzień' : 'godzina';

  // ---------- odtwarzanie: następna klatka dopiero po wczytaniu bieżącej (bez pustej mapy między klatkami);
  // kolejną klatkę pobiera z wyprzedzeniem useWpisyWTrybie
  const wczytuje = !!wpisy.isFetching;
  useEffect(() => { if (ograniczonyRuch && odtwarzanie) ustawOdtwarzanie(false); }, [ograniczonyRuch, odtwarzanie, ustawOdtwarzanie]);
  useEffect(() => {
    if (!odtwarzanie || !archiwum || wczytuje) return;
    const id = window.setTimeout(() => {
      const k = klatkaOdtwarzania(stan, teraz);
      pokazMoment(k.na);
      if (k.koniec) ustawOdtwarzanie(false);
    }, odstepOdtwarzania(predkosc));
    return () => window.clearTimeout(id);
  }, [odtwarzanie, archiwum, stan, teraz, wczytuje, predkosc, pokazMoment, ustawOdtwarzanie]);

  const odtworz = () => {
    if (odtwarzanie) { ustawOdtwarzanie(false); return; }
    const start = startOdtwarzania(stan, teraz);
    if (!archiwum || start !== stan.na) pokazMoment(start);
    ustawOdtwarzanie(true);
  };

  // ---------- ogłoszenia dla czytników: tylko zmiana trybu i koniec odtwarzania (suwak ogłasza się sam przez aria-valuetext)
  const [ogloszenie, setOgloszenie] = useState('');
  const poprzedniTryb = useRef<boolean | null>(null);
  const poprzednieOdtwarzanie = useRef(false);
  useEffect(() => {
    if (!gotowa) return;
    if (poprzedniTryb.current !== null && poprzedniTryb.current !== archiwum) {
      setOgloszenie(archiwum ? `Archiwum, nie bieżące dane. ${etykietaStanu(stan, teraz)}.` : 'Dane na żywo.');
    }
    poprzedniTryb.current = archiwum;
  }, [gotowa, archiwum]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (poprzednieOdtwarzanie.current && !odtwarzanie && archiwum) setOgloszenie(`Odtwarzanie zatrzymane. ${etykietaStanu(stan, teraz)}.`);
    poprzednieOdtwarzanie.current = odtwarzanie;
  }, [odtwarzanie]); // eslint-disable-line react-hooks/exhaustive-deps

  const zmienSuwak = (i: number) => {
    const s = slupki[i];
    if (!s) return;
    ustawOdtwarzanie(false);
    pokazMoment(s.moment);
  };
  // oś godzin: strzałka za krawędzią doby przechodzi do sąsiedniej doby (natywny suwak zatrzymałby się na krawędzi)
  const klawisz = (e: KeyboardEvent<HTMLInputElement>) => {
    const w = e.key === 'ArrowLeft' || e.key === 'ArrowDown';
    const p = e.key === 'ArrowRight' || e.key === 'ArrowUp';
    if ((w && indeks === 0 && moznaWstecz) || (p && indeks === n - 1 && moznaNaprzod)) {
      e.preventDefault();
      ustawOdtwarzanie(false);
      pokazMoment(w ? wstecz : naprzod);
    }
  };

  const etykieta = gotowa ? etykietaStanu(stan, teraz, wpisy.dataUpdatedAt || null) : '';
  const dodatki = archiwum ? wpisy.data : undefined;
  const brakDanych = dodatki?.brakDanych ?? [];
  const bezHistorii = dodatki?.bezHistorii ?? 0;
  // trzecia linia baneru: krótko i policzalnie (nazwy źródeł w „Szczegółach”); okno komunikatów zostaje widoczne
  const brakiKrotko = dodatki ? opisBrakowKrotko(brakDanych, bezHistorii) : '';
  const okno = brakiKrotko ? `${OKNO_KROTKO[okres]} · ${brakiKrotko}` : opisOkna(okres, archiwum);
  const bladOsi = !!osQ.isError && !dane;
  const lukiKrotko = !gotowa ? '' : bladOsi ? 'Oś niedostępna: nie wiemy, ile było komunikatów. Suwak działa.'
    : !dane ? 'Wczytujemy liczbę komunikatów.' : opisLukKrotko(slupki, stan.krok);
  const szczegoly = [
    'Słupki: liczba komunikatów z dokładnym miejscem (nie poziom zagrożenia). Kreska przy osi: mamy dane, zero komunikatów.',
    bladOsi ? 'Oś niedostępna: serwer nie podał liczby komunikatów, więc nie rysujemy zer.' : opisLuk(slupki, stan.krok, nazwy),
    dodatki ? opisBrakowNa(brakDanych, bezHistorii, nazwy) : '',
  ].filter(Boolean);
  const [otwarte, setOtwarte] = useState(false);
  useEffect(() => {
    if (!otwarte) return;
    const klawisz = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') { setOtwarte(false); document.getElementById('tz-os-szczegoly-przycisk')?.focus(); } };
    window.addEventListener('keydown', klawisz);
    return () => window.removeEventListener('keydown', klawisz);
  }, [otwarte]);
  const wybrany = slupki[indeks];
  const valuetext = !gotowa || !wybrany ? '' : `${archiwum ? `Archiwum, stan na ${opisMomentu(moment, teraz)}` : 'Na żywo'}. ${opisSlupka(wybrany, stan.krok, teraz)}`;
  // suwak zwężony o pół słupka z każdej strony: wartość i wypada nad środkiem słupka i (uchwyt i kliknięcie trafiają w to, co widać)
  const polowa = n > 1 ? 50 / n : 0;

  // kolejność w DOM = kolejność fokusu: tryb, przesuwanie, suwak, tempo, szczegóły, krok (na telefonie od góry, od lewej do prawej)
  return <section className="tz-os" data-tryb={archiwum ? 'przeszlosc' : 'dzis'} aria-label="Oś czasu: dane na żywo albo stan z wybranej chwili">
    <div className="tz-os__tryb" role="group" aria-label="Tryb danych">
      <button type="button" aria-pressed={!archiwum} onClick={pokazDzis} disabled={!gotowa}><span lang="en">TODAY</span><span className="tz-sr">: dane na żywo</span></button>
      <button type="button" aria-pressed={archiwum} onClick={() => { if (!archiwum) pokazMoment(wstecz); }} disabled={!gotowa}>PRZESZŁOŚĆ<span className="tz-sr">: stan z wybranej chwili</span></button>
    </div>

    <div className="tz-os__ruch" role="group" aria-label="Przesuwanie w czasie">
      <button type="button" onClick={() => { ustawOdtwarzanie(false); pokazMoment(wstecz); }} disabled={!moznaWstecz}
        aria-label={stan.krok === 'dzien' ? 'Poprzedni dzień' : 'Poprzednia godzina'}><Ikona d={IKONA_WSTECZ} /></button>
      {/* przy ograniczonym ruchu przycisk zostaje (stałe miejsce), ale jest wyłączony; wyjaśnienie stoi w miejscu tempa */}
      <button type="button" className="tz-os__odtworz" onClick={odtworz} disabled={!gotowa || ograniczonyRuch}
        aria-label={ograniczonyRuch ? 'Odtwarzanie wyłączone: system prosi o ograniczenie ruchu' : odtwarzanie ? 'Zatrzymaj odtwarzanie' : stan.krok === 'dzien' ? 'Odtwórz dzień po dniu' : 'Odtwórz godziny tej doby'}>
        <Ikona d={odtwarzanie ? IKONA_PAUZA : IKONA_ODTWORZ} /></button>
      <button type="button" onClick={() => { ustawOdtwarzanie(false); pokazMoment(naprzod); }} disabled={!moznaNaprzod}
        aria-label={stan.krok === 'dzien' ? 'Następny dzień' : 'Następna godzina'}><Ikona d={IKONA_NAPRZOD} /></button>
    </div>

    <div className="tz-os__stan">
      <p className="tz-os__naglowek">{archiwum ? <><span className="tz-os__znak" aria-hidden="true">!</span>Archiwum, nie bieżące dane</> : <><span className="tz-os__kropka" aria-hidden="true" />Na żywo</>}</p>
      <p className="tz-os__moment">{etykieta}</p>
      <p className="tz-os__okno">{gotowa ? okno : ''}</p>
    </div>

    <div className="tz-os__wykres">
      <div className="tz-os__slupki" aria-hidden="true">
        {slupki.map((s, i) => {
          const wOknie = s.do > poczatekOkna && s.od <= moment;
          return <span key={s.od} className="tz-os__slupek" data-stan={s.stan} data-okno={wOknie ? '' : undefined} data-wybrany={i === indeks ? '' : undefined}>
            {kreskowany(s) && <span className="tz-os__kreski" />}
            {s.liczba !== null && <span className="tz-os__liczba" style={{ height: `${Math.round(wys[i] * 100)}%` }} />}
          </span>;
        })}
      </div>
      {n > 0 && <span className="tz-os__uchwyt" data-teraz={archiwum ? undefined : ''} style={{ left: `${((indeks + 0.5) / n) * 100}%` }} aria-hidden="true" />}
      <input type="range" className="tz-os__suwak" min={0} max={Math.max(0, n - 1)} step={1} value={indeks} disabled={!n}
        style={{ left: `${polowa}%`, width: `${100 - 2 * polowa}%` }}
        aria-label={`Chwila stanu danych, krok: ${jednostka}. Strzałki przesuwają o ${jednostka === 'dzień' ? 'dzień' : 'godzinę'}, Home i End na początek i koniec osi.`}
        aria-valuetext={valuetext}
        onChange={e => zmienSuwak(Number(e.target.value))} onKeyDown={klawisz} />
      <ol className="tz-sr" aria-label={`Liczba komunikatów, ${stan.krok === 'dzien' ? 'dzień po dniu' : 'godzina po godzinie'}`}>
        {gotowa && slupki.map(s => <li key={s.od}>{opisSlupka(s, stan.krok, teraz)}</li>)}
      </ol>
    </div>

    <div className="tz-os__daty" aria-hidden="true">
      {gotowa && podpisyOsi(lista, stan.krok, teraz).map(p => <span key={`${p.tekst}-${p.pozycja}`} data-wyrownanie={p.wyrownanie} style={{ left: `${p.pozycja}%` }}>{p.tekst}</span>)}
    </div>

    <div className="tz-os__predkosc">
      {ograniczonyRuch
        ? <span className="tz-os__bez-ruchu">Bez animacji<span className="tz-sr">: odtwarzanie wyłączone, bo system prosi o ograniczenie ruchu. Przechodź strzałkami albo przyciskami.</span></span>
        : <><label className="tz-sr" htmlFor="tz-os-predkosc">Tempo odtwarzania</label>
          <select id="tz-os-predkosc" value={predkosc} disabled={!gotowa} onChange={e => { const p = Number(e.target.value); if (poprawnaPredkosc(p)) historia.ustawPredkosc(p); }}>
            {PREDKOSCI.map(p => <option key={p.id} value={p.id}>{p.etykieta}</option>)}
          </select></>}
    </div>

    <div className="tz-os__luki">
      <button type="button" id="tz-os-szczegoly-przycisk" className="tz-os__luki-przycisk" aria-expanded={otwarte} aria-controls="tz-os-szczegoly" disabled={!gotowa} onClick={() => setOtwarte(v => !v)}>
        {lukiKrotko.startsWith('Kreskowane') && <><span className="tz-os__legenda">Słupki: liczba komunikatów, nie poziom zagrożenia.</span><span className="tz-os__wzor" aria-hidden="true" /></>}
        <span className="tz-os__luki-tekst">{lukiKrotko}</span> <span className="tz-os__rozwin">{otwarte ? 'Zwiń' : 'Szczegóły'}</span>
      </button>
      <div id="tz-os-szczegoly" className="tz-os__szczegoly" hidden={!otwarte}>
        {szczegoly.map(t => <p key={t}>{t}</p>)}
        <button type="button" className="tz-przycisk" onClick={() => { setOtwarte(false); document.getElementById('tz-os-szczegoly-przycisk')?.focus(); }}>Zamknij</button>
      </div>
    </div>

    <div className="tz-os__krok" role="group" aria-label="Krok osi">
      <button type="button" aria-pressed={stan.krok === 'dzien'} onClick={() => historia.ustawKrok('dzien')} disabled={!gotowa}>Dni</button>
      <button type="button" aria-pressed={stan.krok === 'godzina'} onClick={() => historia.ustawKrok('godzina')} disabled={!gotowa}>Godziny</button>
    </div>

    <p className="tz-sr" aria-live="polite">{ogloszenie}</p>
  </section>;
}
