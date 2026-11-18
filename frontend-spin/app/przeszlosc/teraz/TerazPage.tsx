'use client';
import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useStandalone } from '../ui';
import { useOnline, useStan, useWarstwy, useWpisy, useZdarzenia } from './api';
import { adresWpisu, aktywna, bezPolozenia, maObszar, maPunkt, naGeoJson, podsumujStan, posortujWarstwy, wlaczoneWarstwy, zbudujWidoki, zgodnyZRegionem } from './model';
import type { WierszStanu } from './model';
import { zbudujZapytanie, type Parametry } from './parametry';
import { WOJEWODZTWA } from './teryt';
import type { Bbox, Okres } from './typy';
import type { StanMapy } from './Mapa';
import { KartaWpisu } from './KartaWpisu';
import { LiniaStanu } from './LiniaStanu';
import { ListaWpisow } from './ListaWpisow';
import { PanelWarstw } from './PanelWarstw';
import { NIEPEWNOSC } from './warstwy';
import './teraz.css';

/**
 * Strona „Teraz” (Z6a). Układ: telefon 390 px pierwszy (mapa na pełnym ekranie, panel warstw jako wysuwany arkusz,
 * linia stanu zawsze widoczna); komputer: panel warstw z lewej, karta wpisu z prawej. Stan widoku (warstwy, okres,
 * województwo, wybrany wpis, widok) jest w adresie URL i w pamięci przeglądarki.
 * Laws of UX: Jakob (mapa jak wszędzie), Hick (jeden główny wybór: warstwy), Fitts (cele 44 px), Proximity i Common Region
 * (panel, karta), Von Restorff (jedno wyróżnienie: status), Doherty (zmiany warstw natychmiast, bez zapytania).
 */
const Mapa = dynamic(() => import('./Mapa'), {
  ssr: false,
  loading: () => <div className="tz-mapa-ladowanie" role="status">Ładowanie mapy…</div>,
});

const KLUCZ_PAMIECI = 'przeszlosc.teraz.v1';

interface Pamiec { warstwy?: string[] | null; okres?: Okres; woj?: string | null }
const czytajPamiec = (): Pamiec => {
  try { return JSON.parse(window.localStorage.getItem(KLUCZ_PAMIECI) || '{}') as Pamiec; } catch { return {}; }
};
const zapiszPamiec = (p: Pamiec) => { try { window.localStorage.setItem(KLUCZ_PAMIECI, JSON.stringify(p)); } catch { /* tryb prywatny: bez pamięci */ } };

export function TerazPage({ poczatkowy, podkladUrl, glifyUrl }: { poczatkowy: Parametry; podkladUrl: string; glifyUrl: string }) {
  useStandalone();
  const { probne } = poczatkowy;
  const [wybor, setWybor] = useState<string[] | null>(poczatkowy.warstwy);
  const [okres, setOkres] = useState<Okres>(poczatkowy.okres);
  const [woj, setWoj] = useState<string | null>(poczatkowy.woj);
  const [wybranyId, setWybranyId] = useState<number | null>(poczatkowy.wpis);
  const [widok, setWidok] = useState<'mapa' | 'lista'>(poczatkowy.widok);
  const [panel, setPanel] = useState(false);
  const [bezGranic, setBezGranic] = useState(false);
  const [mapa, setMapa] = useState<StanMapy>({ gotowa: false, podklad: podkladUrl ? 'pmtiles' : 'zapasowy' });
  const [pamiecGotowa, setPamiecGotowa] = useState(false);
  const przyciskPanelu = useRef<HTMLButtonElement>(null);

  const online = useOnline();
  const stanQ = useStan(probne);
  const warstwyQ = useWarstwy(probne);
  const wpisyQ = useWpisy(probne, okres, woj);
  const zdarzeniaQ = useZdarzenia(probne);

  // pamięć przeglądarki: tylko dla parametrów, których nie ma w adresie (adres wygrywa)
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const p = czytajPamiec();
    if (!q.has('warstwy') && Array.isArray(p.warstwy)) setWybor(p.warstwy.filter(x => typeof x === 'string'));
    if (!q.has('okres') && (p.okres === '1h' || p.okres === '24h' || p.okres === '7d')) setOkres(p.okres);
    if (!q.has('woj') && p.woj && WOJEWODZTWA.some(w => w.kod === p.woj)) setWoj(p.woj);
    setPamiecGotowa(true);
  }, []);
  useEffect(() => { if (pamiecGotowa) zapiszPamiec({ warstwy: wybor, okres, woj }); }, [pamiecGotowa, wybor, okres, woj]);
  // adres URL: replaceState (bez nowego wpisu w historii i bez ponownego renderowania serwera)
  useEffect(() => {
    if (!pamiecGotowa) return;
    const zapytanie = zbudujZapytanie({ warstwy: wybor, okres, woj, wpis: wybranyId, widok, probne }, window.location.search);
    window.history.replaceState(window.history.state, '', `${window.location.pathname}${zapytanie}`);
  }, [pamiecGotowa, wybor, okres, woj, wybranyId, widok, probne]);

  const warstwy = useMemo(() => posortujWarstwy(warstwyQ.data ?? []), [warstwyQ.data]);
  const podsumowanie = useMemo(() => podsumujStan(stanQ.data, warstwyQ.data), [stanQ.data, warstwyQ.data]);
  const wiersze = useMemo(() => new Map<string, WierszStanu>((podsumowanie?.wiersze ?? []).map(w => [w.warstwa, w])), [podsumowanie]);
  const wlaczone = useMemo(() => wlaczoneWarstwy(wybor, warstwy), [wybor, warstwy]);
  const widoki = useMemo(() => zbudujWidoki(wpisyQ.data?.wpisy ?? [], zdarzeniaQ.data ?? []), [wpisyQ.data, zdarzeniaQ.data]);
  const wRegionie = useMemo(() => widoki.filter(v => zgodnyZRegionem(v.wpis, woj)), [widoki, woj]);
  const naMapie = useMemo(() => {
    const licznik: Record<string, number> = {};
    for (const v of wRegionie) licznik[v.wpis.warstwa] = (licznik[v.wpis.warstwa] ?? 0) + 1;
    return licznik;
  }, [wRegionie]);
  const widoczne = useMemo(() => wRegionie.filter(v => wlaczone.has(v.wpis.warstwa)), [wRegionie, wlaczone]);
  const geo = useMemo(() => naGeoJson(widoczne), [widoczne]);
  const bezMiejsca = useMemo(() => widoczne.filter(v => bezPolozenia(v.wpis)), [widoczne]);
  const wybranyWidok = useMemo(() => widoki.find(v => v.wpis.id === wybranyId) ?? null, [widoki, wybranyId]);
  const polozenie = useMemo(() => {
    const w = wybranyWidok?.wpis;
    if (!w) return null;
    if (maPunkt(w)) return { srodek: [w.dlugosc as number, w.szerokosc as number] as [number, number], bbox: null };
    if (maObszar(w)) return { srodek: null, bbox: w.bbox as Bbox };
    return null;
  }, [wybranyWidok]);
  const region = useMemo(() => WOJEWODZTWA.find(w => w.kod === woj)?.bbox ?? null, [woj]);

  const przelacz = useCallback((kod: string) => {
    setWybor(stare => {
      const baza = stare === null ? [...wlaczoneWarstwy(null, warstwy)] : stare;
      const nowe = baza.includes(kod) ? baza.filter(k => k !== kod) : [...baza, kod];
      const wszystkie: string[] = warstwy.filter(aktywna).map(w => w.warstwa);
      return wszystkie.length > 0 && wszystkie.every(k => nowe.includes(k)) && nowe.every(k => wszystkie.includes(k)) ? null : nowe;
    });
  }, [warstwy]);
  const wszystkie = useCallback((wlacz: boolean) => setWybor(wlacz ? null : []), []);

  const wybierz = useCallback((id: number | null) => {
    setWybranyId(id);
    if (id !== null) setPanel(false);
  }, []);
  const zamknijKarte = useCallback(() => setWybranyId(null), []);
  const zamknijPanel = useCallback(() => { setPanel(false); window.setTimeout(() => przyciskPanelu.current?.focus(), 60); }, []);

  // Esc: najpierw karta, potem panel
  useEffect(() => {
    const klawisz = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (wybranyId !== null) setWybranyId(null);
      else if (panel) { setPanel(false); window.setTimeout(() => przyciskPanelu.current?.focus(), 60); }
    };
    window.addEventListener('keydown', klawisz);
    return () => window.removeEventListener('keydown', klawisz);
  }, [wybranyId, panel]);

  // brak WebGL albo błąd mapy: lista zamiast mapy
  useEffect(() => { if (mapa.niedostepna) setWidok('lista'); }, [mapa.niedostepna]);

  const blad = stanQ.isError || wpisyQ.isError;
  const odswiezono = wpisyQ.dataUpdatedAt || null;
  const wczytano = !wpisyQ.isPending;
  const brakWybranego = wybranyId !== null && wczytano && !wybranyWidok;
  const adres = useCallback(() => adresWpisu(window.location.origin, window.location.pathname, window.location.search, wybranyId ?? 0), [wybranyId]);

  return <div className="tz" data-widok={widok} data-panel={panel ? '' : undefined} data-karta={wybranyWidok ? '' : undefined}>
    <header className="tz-gora">
      <a className="tz-marka" href="/przeszlosc">przeszłość.today</a>
      <h1 className="tz-tytul">Teraz</h1>
      <div className="tz-widok" role="group" aria-label="Widok: mapa albo lista zamiast mapy">
        <button type="button" aria-pressed={widok === 'mapa'} onClick={() => setWidok('mapa')} disabled={mapa.niedostepna}>Mapa</button>
        <button type="button" aria-pressed={widok === 'lista'} onClick={() => setWidok('lista')}>Lista<span className="tz-sr"> zamiast mapy</span></button>
      </div>
    </header>

    <LiniaStanu probne={probne} podsumowanie={podsumowanie} online={online} blad={blad} odswiezono={odswiezono} ladowanie={stanQ.isPending} />

    <div className="tz-glowna">
      <aside id="tz-panel" className="tz-panel" aria-labelledby="tz-panel-tytul">
        <PanelWarstw warstwy={warstwy} wiersze={wiersze} wlaczone={wlaczone} naMapie={naMapie} okres={okres} woj={woj}
          ladowanie={warstwyQ.isPending} onPrzelacz={przelacz} onWszystkie={wszystkie} onOkres={setOkres} onWoj={setWoj} onZamknij={zamknijPanel} />
      </aside>

      <section className="tz-scena" aria-label={widok === 'mapa' ? 'Mapa komunikatów' : 'Lista komunikatów'}>
        {widok === 'mapa'
          ? <>
            <button type="button" className="tz-pomin" onClick={() => setWidok('lista')}>Przejdź do listy komunikatów zamiast mapy</button>
            <Mapa punkty={geo.punkty as never} obszary={geo.obszary as never} wybrany={wybranyId} polozenieWybranego={polozenie} region={region} gotowa={mapa.gotowa}
              podkladUrl={podkladUrl} glifyUrl={glifyUrl} onWybierz={wybierz} onStan={setMapa} />
            {bezMiejsca.length > 0 && <div className="tz-nakladka tz-nakladka--dol">
              <button type="button" className="tz-przycisk" aria-expanded={bezGranic} aria-controls="tz-bez-granic" onClick={() => setBezGranic(v => !v)}>
                Bez granic na mapie: {bezMiejsca.length}
              </button>
              {bezGranic && <div id="tz-bez-granic" className="tz-bez-granic">
                <p>Komunikaty dla obszarów, których granic jeszcze nie rysujemy. Miejsce podajemy słowami.</p>
                <ListaWpisow widoki={bezMiejsca} warstwy={warstwyQ.data} wybrany={wybranyId} onWybierz={wybierz} etykieta="Komunikaty bez granic na mapie" pusta="Brak." />
              </div>}
            </div>}
          </>
          : <div className="tz-lista-ramka">
            {mapa.niedostepna && <p className="tz-lista__uwaga" role="status">Ta przeglądarka nie obsługuje mapy, dlatego pokazujemy listę.</p>}
            <ListaWpisow widoki={widoczne} warstwy={warstwyQ.data} wybrany={wybranyId} onWybierz={wybierz} etykieta="Komunikaty od najnowszych"
              pusta={`Brak komunikatów w wybranym czasie i regionie. To nie znaczy, że nic się nie dzieje: ${NIEPEWNOSC}.`} />
          </div>}

        <div className="tz-nakladka tz-nakladka--gora">
          {probne && widok === 'mapa' && <p className="tz-plakietka tz-plakietka--probne">Dane przykładowe</p>}
          {widok === 'mapa' && mapa.podklad === 'zapasowy' && <p className="tz-plakietka">Podkład uproszczony: granica Polski i siatka</p>}
          {wpisyQ.isPending && <p className="tz-komunikat" role="status">Wczytujemy komunikaty…</p>}
          {wpisyQ.isError && !wpisyQ.data && <p className="tz-komunikat tz-komunikat--blad" role="alert">Nie udało się pobrać komunikatów: {NIEPEWNOSC}.</p>}
          {widok === 'mapa' && wczytano && !wpisyQ.isError && widoczne.length === 0 && <p className="tz-komunikat" role="status">
            Brak komunikatów w wybranym czasie i regionie. To nie znaczy, że nic się nie dzieje: {NIEPEWNOSC}.</p>}
          {wpisyQ.data?.uciete && <p className="tz-komunikat tz-komunikat--mala" role="status">Pokazujemy najnowsze komunikaty, starsze pominięto. Zawęź czas albo region.</p>}
          {brakWybranego && <p className="tz-komunikat tz-komunikat--blad" role="status">Tego wpisu nie ma w bieżących danych (inny okres, region albo wpis wycofany). Zmień okres w panelu warstw.</p>}
        </div>
      </section>

      {wybranyWidok && <aside className="tz-karta" aria-label="Szczegóły wpisu">
        <KartaWpisu widok={wybranyWidok} warstwy={warstwyQ.data} adres={adres} onZamknij={zamknijKarte} />
      </aside>}
    </div>

    <button ref={przyciskPanelu} type="button" className="tz-przycisk tz-fab" aria-expanded={panel} aria-controls="tz-panel" onClick={() => setPanel(v => !v)}>
      Warstwy ({wlaczone.size})
    </button>
  </div>;
}
