'use client';
import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useStandalone } from '../ui';
import { odKiedy, useOnline, useStan, useWarstwy, useWpisy, useWpisyPowiatow, useZdarzenia } from './api';
import { adresWpisu, aktywna, bezPolozenia, bezWylaczonych, dostepna, kodyWylaczonych, maObszar, maPunkt, naGeoJson, podsumujStan, politykaStatusu, posortujWarstwy, wlaczoneWarstwy, zbudujWidoki, zgodnyZRegionem } from './model';
import type { WierszStanu } from './model';
import { zbudujZapytanie, type Parametry, type Widok } from './parametry';
import { czytajPamiec, zapiszPamiec } from './pamiec';
import { adresZestawu, kodyWojewodztw, oczyscKody, zapytanieZPowiatami } from './powiaty';
import { WOJEWODZTWA } from './teryt';
import type { Bbox, Okres } from './typy';
import type { StanMapy } from './Mapa';
import { KartaWpisu } from './KartaWpisu';
import { KomunikatyDanych } from './KomunikatyDanych';
import { LiniaStanu } from './LiniaStanu';
import { ListaWpisow } from './ListaWpisow';
import { MojPowiat } from './MojPowiat';
import { PanelWarstw } from './PanelWarstw';
import { TabelaWpisow } from './TabelaWpisow';
import { NIEPEWNOSC, OKRESY } from './warstwy';
import './teraz.css';

/**
 * Strona „Teraz”. Układ: telefon 390 px pierwszy (mapa na pełnym ekranie, panel warstw jako wysuwany arkusz,
 * ostrzeżenia i stałe zdanie zawsze widoczne nad treścią); komputer: panel warstw z lewej, karta wpisu z prawej. Cztery widoki:
 * mapa, lista zamiast mapy, tabela (pełny odpowiednik mapy) i „Mój powiat” (bez mapy, duży druk). Stan widoku
 * (warstwy, okres, województwo, wybrany wpis, widok, powiaty) jest w adresie URL i w pamięci przeglądarki (walidowanej).
 * Warstwy wyłączone przez redakcję (`wylaczona` z warstwy/) znikają wszędzie, niezależnie od preferencji i cache.
 * Awaria danych, ich obcięcie i brak komunikatów to trzy osobne stany (KomunikatyDanych).
 * Laws of UX: Jakob (mapa jak wszędzie), Hick (jeden główny wybór: warstwy), Fitts (cele 44 px), Proximity i Common Region
 * (panel, karta), Von Restorff (jedno wyróżnienie: status), Doherty (zmiany warstw natychmiast, bez zapytania).
 */
const Mapa = dynamic(() => import('./Mapa'), {
  ssr: false,
  loading: () => <div className="tz-mapa-ladowanie" role="status">Ładowanie mapy…</div>,
});

const NAZWY_WIDOKOW: Record<Widok, string> = { mapa: 'Mapa komunikatów', lista: 'Lista komunikatów', tabela: 'Tabela komunikatów', powiat: 'Mój powiat' };

/** Telefon i wąski tablet: panel i karta są arkuszami nad treścią (od 900 px panel jest z lewej, a karta z prawej). */
const WASKI_EKRAN = '(max-width: 899.98px)';
function useWaskiEkran(): boolean {
  const [waski, setWaski] = useState(false);
  useEffect(() => {
    const m = window.matchMedia(WASKI_EKRAN);
    const ustaw = () => setWaski(m.matches);
    ustaw();
    m.addEventListener('change', ustaw);
    return () => m.removeEventListener('change', ustaw);
  }, []);
  return waski;
}

export function TerazPage({ poczatkowy, poczatkowePowiaty, podkladUrl, glifyUrl }: { poczatkowy: Parametry; poczatkowePowiaty: string[]; podkladUrl: string; glifyUrl: string }) {
  useStandalone();
  const { probne } = poczatkowy;
  const [wybor, setWybor] = useState<string[] | null>(poczatkowy.warstwy);
  const [okres, setOkres] = useState<Okres>(poczatkowy.okres);
  const [woj, setWoj] = useState<string | null>(poczatkowy.woj);
  const [wybranyId, setWybranyId] = useState<number | null>(poczatkowy.wpis);
  const [widok, setWidok] = useState<Widok>(poczatkowy.widok);
  const [powiaty, setPowiaty] = useState<string[]>(poczatkowePowiaty);
  const [panel, setPanel] = useState(false);
  const [bezGranic, setBezGranic] = useState(false);
  const [mapa, setMapa] = useState<StanMapy>({ gotowa: false, podklad: podkladUrl ? 'pmtiles' : 'zapasowy' });
  const [pamiecGotowa, setPamiecGotowa] = useState(false);
  const przyciskPanelu = useRef<HTMLButtonElement>(null);
  const fokusTabeli = useRef(false);
  const wMapie = widok !== 'powiat';
  const waski = useWaskiEkran();

  // Zapytania o wpisy startują dopiero po odczycie preferencji (pamiecGotowa), żeby nie pobierać dwa razy: najpierw z wartościami
  // z adresu, a potem z zapamiętanymi. Stan, warstwy i zdarzenia nie zależą od preferencji, więc startują od razu.
  const online = useOnline();
  const stanQ = useStan(probne);
  const warstwyQ = useWarstwy(probne);
  const wpisyQ = useWpisy(probne, okres, woj, wMapie && pamiecGotowa);
  const wojKody = useMemo(() => kodyWojewodztw(powiaty), [powiaty]);
  const powiatyQ = useWpisyPowiatow(probne, okres, wojKody, !wMapie && pamiecGotowa);
  const zdarzeniaQ = useZdarzenia(probne);

  // pamięć przeglądarki (walidowana w pamiec.ts): tylko dla parametrów, których nie ma w adresie (adres wygrywa)
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const p = czytajPamiec();
    if (!q.has('warstwy') && p.warstwy !== undefined) setWybor(p.warstwy);
    if (!q.has('okres') && p.okres) setOkres(p.okres);
    if (!q.has('woj') && p.woj) setWoj(p.woj);
    if (!q.has('powiaty') && p.powiaty) { const k = oczyscKody(p.powiaty); if (k.length) setPowiaty(k); }
    setPamiecGotowa(true);
  }, []);
  useEffect(() => { if (pamiecGotowa) zapiszPamiec({ warstwy: wybor, okres, woj }); }, [pamiecGotowa, wybor, okres, woj]);
  // adres URL: replaceState (bez nowego wpisu w historii i bez ponownego renderowania serwera)
  useEffect(() => {
    if (!pamiecGotowa) return;
    const zapytanie = zapytanieZPowiatami(zbudujZapytanie({ warstwy: wybor, okres, woj, wpis: wybranyId, widok, probne }, window.location.search), powiaty);
    window.history.replaceState(window.history.state, '', `${window.location.pathname}${zapytanie}`);
  }, [pamiecGotowa, wybor, okres, woj, wybranyId, widok, probne, powiaty]);

  // wybór powiatów zapisujemy w pamięci tylko po działaniu użytkownika: zestaw z cudzego linku nie nadpisuje jego własnego
  const zmienPowiaty = useCallback((kody: string[]) => {
    const czyste = oczyscKody(kody);
    setPowiaty(czyste);
    zapiszPamiec({ powiaty: czyste });
  }, []);

  // warstwy wyłączone przez redakcję: znikają z panelu, listy, tabeli, „Mój powiat”, karty i powiązań, także z danych w cache
  const wylaczone = useMemo(() => kodyWylaczonych(warstwyQ.data), [warstwyQ.data]);
  const warstwy = useMemo(() => posortujWarstwy((warstwyQ.data ?? []).filter(dostepna)), [warstwyQ.data]);
  const warstwyDlaNazw = useMemo(() => warstwyQ.data?.filter(dostepna), [warstwyQ.data]);
  const warstwyZnane = (warstwyQ.data?.length ?? 0) > 0;
  const podsumowanie = useMemo(() => podsumujStan(stanQ.data, warstwyQ.data), [stanQ.data, warstwyQ.data]);
  const wiersze = useMemo(() => new Map<string, WierszStanu>((podsumowanie?.wiersze ?? []).map(w => [w.warstwa, w])), [podsumowanie]);
  const wlaczone = useMemo(() => wlaczoneWarstwy(wybor, warstwyQ.data ?? []), [wybor, warstwyQ.data]);
  const polityka = useMemo(() => politykaStatusu(zdarzeniaQ.data), [zdarzeniaQ.data]);
  const zdarzenia = useMemo(() => bezWylaczonych([], zdarzeniaQ.data?.wyniki ?? [], wylaczone).zdarzenia, [zdarzeniaQ.data, wylaczone]);
  const wpisyMapy = useMemo(() => bezWylaczonych(wpisyQ.data?.wpisy ?? [], [], wylaczone).wpisy, [wpisyQ.data, wylaczone]);
  const wpisyPowiatow = useMemo(() => bezWylaczonych(powiatyQ.data?.wpisy ?? [], [], wylaczone).wpisy, [powiatyQ.data, wylaczone]);
  const widoki = useMemo(() => zbudujWidoki(wpisyMapy, zdarzenia, polityka), [wpisyMapy, zdarzenia, polityka]);
  const widokiPowiatow = useMemo(() => zbudujWidoki(wpisyPowiatow, zdarzenia, polityka), [wpisyPowiatow, zdarzenia, polityka]);
  const poczatekOkresu = useMemo(() => odKiedy(okres), [okres, powiatyQ.dataUpdatedAt]); // eslint-disable-line react-hooks/exhaustive-deps
  const wRegionie = useMemo(() => widoki.filter(v => zgodnyZRegionem(v.wpis, woj)), [widoki, woj]);
  const naMapie = useMemo(() => {
    const licznik: Record<string, number> = {};
    for (const v of wRegionie) licznik[v.wpis.warstwa] = (licznik[v.wpis.warstwa] ?? 0) + 1;
    return licznik;
  }, [wRegionie]);
  // bez listy warstw i bez wyboru użytkownika nie ma po czym filtrować: pokazujemy wszystko (pusta lista warstw nie może ukryć komunikatów)
  const bezFiltraWarstw = !warstwyZnane && wybor === null;
  const widoczne = useMemo(() => wRegionie.filter(v => bezFiltraWarstw || wlaczone.has(v.wpis.warstwa)), [wRegionie, wlaczone, bezFiltraWarstw]);
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
      const baza = stare === null ? [...wlaczoneWarstwy(null, warstwyQ.data ?? [])] : stare;
      const nowe = baza.includes(kod) ? baza.filter(k => k !== kod) : [...baza, kod];
      const wszystkie: string[] = (warstwyQ.data ?? []).filter(aktywna).map(w => w.warstwa);
      return wszystkie.length > 0 && wszystkie.every(k => nowe.includes(k)) && nowe.every(k => wszystkie.includes(k)) ? null : nowe;
    });
  }, [warstwyQ.data]);
  const wszystkie = useCallback((wlacz: boolean) => setWybor(wlacz ? null : []), []);

  // karta wpisu zabiera fokus na swój nagłówek; po zamknięciu wraca on tam, skąd karta została otwarta (wiersz tabeli, pozycja listy)
  const fokusPrzedKarta = useRef<HTMLElement | null>(null);
  const przywrocFokus = useCallback(() => { window.setTimeout(() => fokusPrzedKarta.current?.focus(), 0); }, []);
  const wybierz = useCallback((id: number | null) => {
    if (id !== null) fokusPrzedKarta.current = document.activeElement instanceof HTMLElement && document.activeElement !== document.body ? document.activeElement : null;
    setWybranyId(id);
    if (id !== null) setPanel(false);
  }, []);
  const zamknijKarte = useCallback(() => { setWybranyId(null); przywrocFokus(); }, [przywrocFokus]);
  const zamknijPanel = useCallback(() => { setPanel(false); window.setTimeout(() => przyciskPanelu.current?.focus(), 60); }, []);

  // Esc: najpierw karta, potem panel
  useEffect(() => {
    const klawisz = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (wybranyId !== null) { setWybranyId(null); przywrocFokus(); }
      else if (panel) { setPanel(false); window.setTimeout(() => przyciskPanelu.current?.focus(), 60); }
    };
    window.addEventListener('keydown', klawisz);
    return () => window.removeEventListener('keydown', klawisz);
  }, [wybranyId, panel, przywrocFokus]);

  // po otwarciu panelu (telefon) fokus idzie na jego nagłówek: panel jest w DOM przed przyciskiem „Warstwy”, więc bez tego
  // użytkownik klawiatury musiałby przejść całą stronę, żeby do niego dotrzeć
  useEffect(() => { if (panel) document.getElementById('tz-panel-tytul')?.focus(); }, [panel]);

  // przejście z mapy do tabeli z odnośnika „Przejdź do tabeli”: fokus na nagłówek tabeli
  useEffect(() => {
    if (widok === 'tabela' && fokusTabeli.current) { fokusTabeli.current = false; document.getElementById('tz-tabela-tytul')?.focus(); }
  }, [widok]);

  // brak WebGL albo błąd mapy: lista zamiast mapy
  useEffect(() => { if (mapa.niedostepna) setWidok(w => (w === 'mapa' ? 'lista' : w)); }, [mapa.niedostepna]);

  const zapytanieDanych = wMapie ? wpisyQ : powiatyQ;
  const blad = stanQ.isError || zapytanieDanych.isError;
  const odswiezonoWpisy = zapytanieDanych.dataUpdatedAt || null;
  const odswiezonoStan = stanQ.dataUpdatedAt || null;
  const wczytano = !wpisyQ.isPending;
  const wpisyNiedostepne = wpisyQ.isError && !wpisyQ.data;
  // „brak komunikatów” tylko przy udanej odpowiedzi (nie przy awarii, nie przy danych z poprzedniego zapytania)
  const udanaOdpowiedz = wpisyQ.isSuccess && !wpisyQ.isPlaceholderData;
  const brakWybranego = wMapie && wybranyId !== null && wczytano && !wpisyNiedostepne && !wybranyWidok;
  const adres = useCallback(
    () => adresWpisu(window.location.origin, window.location.pathname, { warstwy: wybor, okres, woj, wpis: null, widok, probne }, wybranyId ?? 0),
    [wybor, okres, woj, widok, probne, wybranyId],
  );
  const adresPowiatow = useCallback(() => adresZestawu(window.location.origin, window.location.pathname, powiaty, okres, probne), [powiaty, okres, probne]);
  const opisFiltrow = `${OKRESY.find(o => o.id === okres)?.etykieta ?? okres}, ${woj ? `województwo ${WOJEWODZTWA.find(w => w.kod === woj)?.nazwa ?? woj} (granice przybliżone)` : 'cała Polska'}, włączone warstwy: ${wlaczone.size}`;

  const stanWarstw = { niedostepne: warstwyQ.isError && !warstwyQ.data, nieaktualne: warstwyQ.isError && !!warstwyQ.data };
  const stanZdarzen = {
    niedostepne: zdarzeniaQ.isError && !zdarzeniaQ.data, nieaktualne: zdarzeniaQ.isError && !!zdarzeniaQ.data,
    uciete: zdarzeniaQ.data?.uciete ?? false, pominiete: zdarzeniaQ.data?.pominiete ?? 0,
  };
  // komunikaty o danych: nakładka na mapie i liście, zwykły akapit nad tabelą
  const komunikatyDanych = <KomunikatyDanych
    wpisy={{
      ladowanie: wMapie && wpisyQ.isPending && pamiecGotowa, niedostepne: wpisyNiedostepne, nieaktualne: wpisyQ.isError && !!wpisyQ.data,
      uciete: wpisyQ.data?.uciete ?? false, pominiete: wpisyQ.data?.pominiete ?? 0,
    }}
    warstwy={stanWarstw} zdarzenia={stanZdarzen} brakWybranego={brakWybranego} />;
  const tekstPustejListy = wpisyNiedostepne
    ? `Dane niedostępne, nie pokazujemy listy: ${NIEPEWNOSC}.`
    : !udanaOdpowiedz
      ? 'Wczytujemy komunikaty…'
      : `Brak komunikatów w wybranym czasie i regionie. To nie znaczy, że nic się nie dzieje: ${NIEPEWNOSC}.`;

  // arkusz (telefon) przykrywa treść: pod nim nie wolno wchodzić klawiaturą (inert). Mapa zostaje dostępna pod kartą wpisu, żeby
  // dało się dotknąć następnego znacznika; pod panelem warstw i pod kartą w innych widokach scena jest nieaktywna.
  const kartaOtwarta = !!wybranyWidok && wMapie;
  const scenaNieaktywna = waski && (panel || (kartaOtwarta && widok !== 'mapa'));
  // React 18 nie zna atrybutu inert (wartość true byłaby odrzucona), więc przekazujemy pusty tekst: w DOM trafia inert=""
  const inert = scenaNieaktywna ? { inert: '' as unknown as boolean } : {};

  return <div className="tz" data-widok={widok} data-panel={panel ? '' : undefined} data-karta={kartaOtwarta ? '' : undefined}>
    <header className="tz-gora">
      <a className="tz-marka" href="/przeszlosc"><span className="tz-marka__ik" aria-hidden="true">←</span><span className="tz-marka__tekst">przeszłość.today</span></a>
      <h1 className="tz-tytul">Teraz</h1>
      <div className="tz-widok" role="group" aria-label="Widok: mapa, lista, tabela albo mój powiat">
        <button type="button" aria-pressed={widok === 'mapa'} onClick={() => setWidok('mapa')} disabled={mapa.niedostepna}>Mapa</button>
        <button type="button" aria-pressed={widok === 'lista'} onClick={() => setWidok('lista')}>Lista<span className="tz-sr"> zamiast mapy</span></button>
        <button type="button" aria-pressed={widok === 'tabela'} onClick={() => setWidok('tabela')}>Tabela</button>
        <button type="button" aria-pressed={widok === 'powiat'} aria-label="Mój powiat" onClick={() => setWidok('powiat')}>
          <span className="tz-widok__skrot" aria-hidden="true">Powiat</span><span className="tz-widok__pelna" aria-hidden="true">Mój powiat</span>
        </button>
      </div>
    </header>

    <LiniaStanu probne={probne} podsumowanie={podsumowanie} online={online} blad={blad} odswiezonoWpisy={odswiezonoWpisy} odswiezonoStan={odswiezonoStan} ladowanie={stanQ.isPending} />

    <div className="tz-glowna">
      {wMapie && <aside id="tz-panel" className="tz-panel" aria-labelledby="tz-panel-tytul">
        <PanelWarstw warstwy={warstwy} wiersze={wiersze} wlaczone={wlaczone} naMapie={naMapie} okres={okres} woj={woj}
          ladowanie={warstwyQ.isPending} onPrzelacz={przelacz} onWszystkie={wszystkie} onOkres={setOkres} onWoj={setWoj} onZamknij={zamknijPanel} />
      </aside>}

      <section className="tz-scena" aria-label={NAZWY_WIDOKOW[widok]} {...inert}>
        {widok === 'mapa' && <>
          <button type="button" className="tz-pomin" onClick={() => { fokusTabeli.current = true; setWidok('tabela'); }}>Przejdź do tabeli komunikatów (pełny odpowiednik mapy)</button>
          <Mapa punkty={geo.punkty as never} obszary={geo.obszary as never} wybrany={wybranyId} polozenieWybranego={polozenie} region={region} gotowa={mapa.gotowa}
            podkladUrl={podkladUrl} glifyUrl={glifyUrl} onWybierz={wybierz} onStan={setMapa} />
          {bezMiejsca.length > 0 && <div className="tz-nakladka tz-nakladka--dol">
            <button type="button" className="tz-przycisk" aria-expanded={bezGranic} aria-controls="tz-bez-granic" onClick={() => setBezGranic(v => !v)}>
              Bez granic na mapie: {bezMiejsca.length}
            </button>
            {bezGranic && <div id="tz-bez-granic" className="tz-bez-granic">
              <p>Komunikaty dla obszarów, których granic jeszcze nie rysujemy. Miejsce podajemy słowami.</p>
              <ListaWpisow widoki={bezMiejsca} warstwy={warstwyDlaNazw} wybrany={wybranyId} onWybierz={wybierz} etykieta="Komunikaty bez granic na mapie" pusta="Brak." />
            </div>}
          </div>}
        </>}
        {widok === 'lista' && <div className="tz-lista-ramka">
          {mapa.niedostepna && <p className="tz-lista__uwaga" role="status">Ta przeglądarka nie obsługuje mapy, dlatego pokazujemy listę.</p>}
          <div className="tz-komunikaty-inline">{komunikatyDanych}</div>
          <ListaWpisow widoki={widoczne} warstwy={warstwyDlaNazw} wybrany={wybranyId} onWybierz={wybierz} etykieta="Komunikaty od najnowszych" pusta={tekstPustejListy} />
        </div>}
        {widok === 'tabela' && <div className="tz-ramka">
          <div className="tz-komunikaty-inline">{komunikatyDanych}</div>
          <TabelaWpisow widoki={widoczne} warstwy={warstwyDlaNazw} wybrany={wybranyId} onWybierz={wybierz} opisFiltrow={opisFiltrow} pusta={tekstPustejListy} />
        </div>}
        {widok === 'powiat' && <div className="tz-ramka tz-ramka--powiat">
          <div className="tz-komunikaty-inline">
            <KomunikatyDanych warstwy={stanWarstw} zdarzenia={stanZdarzen} />
          </div>
          <MojPowiat powiaty={powiaty} onZmien={zmienPowiaty} okres={okres} onOkres={setOkres}
            widoki={widokiPowiatow} warstwy={warstwyDlaNazw}
            ladowanie={powiatyQ.isPending} blad={powiatyQ.isError && !powiatyQ.data} uciete={powiatyQ.data?.uciete ?? false} pominiete={powiatyQ.data?.pominiete ?? 0}
            lukaWDanych={(podsumowanie?.ostrzezenia.length ?? 0) > 0} poczatekOkresu={poczatekOkresu} adres={adresPowiatow} />
        </div>}

        {widok === 'mapa' && <div className="tz-nakladka tz-nakladka--gora">
          {probne && <p className="tz-plakietka tz-plakietka--probne">Dane przykładowe</p>}
          {mapa.podklad === 'zapasowy' && <p className="tz-plakietka">Podkład uproszczony: granica Polski i siatka</p>}
          {komunikatyDanych}
          {udanaOdpowiedz && widoczne.length === 0 && <p className="tz-komunikat" role="status">
            Brak komunikatów w wybranym czasie i regionie. To nie znaczy, że nic się nie dzieje: {NIEPEWNOSC}.</p>}
        </div>}
      </section>

      {kartaOtwarta && wybranyWidok && <aside className="tz-karta" aria-label="Szczegóły wpisu">
        <KartaWpisu widok={wybranyWidok} warstwy={warstwyDlaNazw} adres={adres} onZamknij={zamknijKarte} />
      </aside>}
    </div>

    {wMapie && <button ref={przyciskPanelu} type="button" className="tz-przycisk tz-fab" aria-expanded={panel} aria-controls="tz-panel" onClick={() => setPanel(v => !v)}>
      Warstwy ({wlaczone.size})
    </button>}
  </div>;
}
