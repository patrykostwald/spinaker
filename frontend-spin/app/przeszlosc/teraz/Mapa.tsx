'use client';
import { useEffect, useRef } from 'react';
import type { GeoJSONSource, Map as MapaGL } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Bbox } from './typy';
import type { CechaObszaru, CechaPunktu } from './model';
import { POLSKA_BBOX } from './teryt';
import { MOTYW_CIEMNY, MOTYW_JASNY, stylZPmtiles, stylZapasowy, type Motyw } from './styl';

/**
 * Mapa „Teraz”: MapLibre GL JS + protokół PMTiles. Ten plik jest ładowany dynamicznie (next/dynamic, bez SSR) tylko na
 * stronie /teraz, więc maplibre-gl i pmtiles nie trafiają do żadnej innej strony. Znaczniki to symbole z obrazami
 * rysowanymi na żądanie (zdarzenie styleimagemissing): kształt oznacza status, kolor warstwę. Grupowanie punktów robi
 * źródło GeoJSON z cluster: true; liczby w grupach to obrazy z canvas (bez glifów, więc bez dodatkowego serwera).
 */
export type Kolekcja<C> = { type: 'FeatureCollection'; features: { type: 'Feature'; properties: C; geometry: unknown }[] };

export interface StanMapy { gotowa: boolean; podklad: 'pmtiles' | 'zapasowy'; niedostepna?: boolean }

export interface MapaProps {
  punkty: Kolekcja<CechaPunktu>;
  obszary: Kolekcja<CechaObszaru>;
  wybrany: number | null;
  /** Położenie wybranego wpisu (do przelotu, gdy wybór nie pochodzi z kliknięcia w mapę). */
  polozenieWybranego: { srodek: [number, number] | null; bbox: Bbox | null } | null;
  region: Bbox | null;
  /** Mapa i jej dane są gotowe (po zdarzeniu load): wtedy można przelecieć do wybranego wpisu z adresu URL. */
  gotowa: boolean;
  podkladUrl: string;
  glifyUrl: string;
  onWybierz: (id: number | null) => void;
  onStan: (s: StanMapy) => void;
}

const KSZTALTY = ['kolo', 'romb', 'kwadrat', 'trojkat', 'krzyzyk', 'pierscien'] as const;
const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const ROZMIAR = 44;
const BRAK_ID = -1;

function kanwa(rozmiar: number): { c: HTMLCanvasElement; x: CanvasRenderingContext2D } | null {
  const c = document.createElement('canvas');
  c.width = c.height = rozmiar;
  const x = c.getContext('2d', { willReadFrequently: true });
  return x ? { c, x } : null;
}

/** Obraz znacznika (ik-<kształt>-<kolor>) albo grupy (klaster-<liczba>); null dla nieznanych nazw. */
function rysujObraz(id: string, m: Motyw): ImageData | null {
  const grupa = /^klaster-(\d+)$/.exec(id);
  if (grupa) {
    const n = Number(grupa[1]);
    const k = kanwa(ROZMIAR + 8);
    if (!k) return null;
    const s = (ROZMIAR + 8) / 2;
    k.x.beginPath(); k.x.arc(s, s, 21, 0, Math.PI * 2);
    k.x.fillStyle = m.aureola; k.x.fill();
    k.x.lineWidth = 3; k.x.strokeStyle = m.tlo; k.x.stroke();
    k.x.fillStyle = m.tlo; k.x.font = '700 30px system-ui, sans-serif'; k.x.textAlign = 'center'; k.x.textBaseline = 'middle';
    k.x.fillText(n > 99 ? '99+' : String(n), s, s + 1);
    return k.x.getImageData(0, 0, ROZMIAR + 8, ROZMIAR + 8);
  }
  const opis = /^ik-([a-z]+)-([0-9a-f]{6})$/.exec(id);
  if (!opis || !(KSZTALTY as readonly string[]).includes(opis[1])) return null;
  const ksztalt = opis[1] as (typeof KSZTALTY)[number];
  const kolor = `#${opis[2]}`;
  const k = kanwa(ROZMIAR);
  if (!k) return null;
  const { x } = k;
  const s = ROZMIAR / 2;
  x.lineJoin = 'round'; x.lineCap = 'round';
  const sciezka = () => {
    x.beginPath();
    if (ksztalt === 'kolo' || ksztalt === 'pierscien') x.arc(s, s, 14, 0, Math.PI * 2);
    else if (ksztalt === 'romb') { x.moveTo(s, 4); x.lineTo(s + 17, s); x.lineTo(s, ROZMIAR - 4); x.lineTo(s - 17, s); x.closePath(); }
    else if (ksztalt === 'kwadrat') x.rect(9, 9, ROZMIAR - 18, ROZMIAR - 18);
    else if (ksztalt === 'trojkat') { x.moveTo(s, 6); x.lineTo(s + 17, ROZMIAR - 8); x.lineTo(s - 17, ROZMIAR - 8); x.closePath(); }
    else { x.moveTo(11, 11); x.lineTo(ROZMIAR - 11, ROZMIAR - 11); x.moveTo(ROZMIAR - 11, 11); x.lineTo(11, ROZMIAR - 11); }
  };
  if (ksztalt === 'krzyzyk') {
    sciezka(); x.lineWidth = 10; x.strokeStyle = m.aureola; x.stroke();
    sciezka(); x.lineWidth = 5; x.strokeStyle = kolor; x.stroke();
  } else if (ksztalt === 'pierscien') {
    sciezka(); x.lineWidth = 9; x.strokeStyle = m.aureola; x.stroke();
    sciezka(); x.fillStyle = m.tlo; x.fill();
    x.lineWidth = 5; x.strokeStyle = kolor; x.stroke();
  } else {
    sciezka(); x.lineWidth = 4; x.strokeStyle = m.aureola; x.stroke();
    x.fillStyle = kolor; x.fill();
  }
  return x.getImageData(0, 0, ROZMIAR, ROZMIAR);
}

const ZASIEG_KLIKNIECIA = 16;
const WARSTWY_PUNKTOW = ['klastry', 'punkty'];

export default function Mapa(p: MapaProps) {
  const kontener = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaGL | null>(null);
  const najnowsze = useRef(p);
  najnowsze.current = p;
  const ostatniKlik = useRef<number | null>(null);
  const motyw = useRef<Motyw>(MOTYW_CIEMNY);

  // utworzenie mapy (raz); zależności celowo puste: dalsze zmiany obsługują osobne efekty poniżej
  useEffect(() => {
    let anulowano = false;
    let usun: (() => void) | null = null;
    (async () => {
      try {
        const ml = await import('maplibre-gl');
        if (anulowano || !kontener.current) return;
        const { podkladUrl, glifyUrl } = najnowsze.current;
        motyw.current = document.documentElement.dataset.theme === 'light' ? MOTYW_JASNY : MOTYW_CIEMNY;
        const m = motyw.current;
        let tryb: 'pmtiles' | 'zapasowy' = 'zapasowy';
        let style = stylZapasowy(m);
        let odepnijProtokol: (() => void) | null = null;
        if (podkladUrl) {
          const { Protocol } = await import('pmtiles');
          if (anulowano || !kontener.current) return;
          const protokol = new Protocol();
          // typy pmtiles i maplibre-gl rozjeżdżają się w polu data (unknown vs AddProtocolResponseData); działanie jest zgodne z dokumentacją pmtiles
          ml.addProtocol('pmtiles', protokol.tilev4 as never);
          odepnijProtokol = () => ml.removeProtocol('pmtiles');
          style = stylZPmtiles(new URL(podkladUrl, window.location.href).href, glifyUrl, m);
          tryb = 'pmtiles';
        }
        const poczatkowy = najnowsze.current.region ?? POLSKA_BBOX;
        const mapaGL = new ml.Map({
          container: kontener.current, style, attributionControl: false, dragRotate: false, pitchWithRotate: false,
          bounds: poczatkowy, fitBoundsOptions: { padding: 12 }, minZoom: 3.5, maxZoom: 14, maxBounds: [[6, 44], [32, 58.5]],
          fadeDuration: reduced() ? 0 : 200,
        });
        mapa.current = mapaGL;
        mapaGL.touchZoomRotate.disableRotation();
        mapaGL.addControl(new ml.NavigationControl({ showCompass: false }), 'top-right');
        mapaGL.addControl(new ml.AttributionControl({ compact: window.matchMedia('(max-width: 899px)').matches, customAttribution: 'Komunikaty: instytucje wskazane w kartach wpisów' }), 'bottom-right');

        const wczytajPolske = () => {
          fetch('/teraz/polska.geojson').then(r => r.json()).then(d => {
            (mapaGL.getSource('polska') as GeoJSONSource | undefined)?.setData(d);
          }).catch(() => { /* bez granicy zostaje tło i siatka */ });
        };

        const zainstalujDane = () => {
          const n = najnowsze.current;
          if (!mapaGL.getSource('obszary')) {
            mapaGL.addSource('obszary', { type: 'geojson', data: n.obszary as never });
            mapaGL.addLayer({ id: 'obszary-wypelnienie', type: 'fill', source: 'obszary', paint: { 'fill-color': ['get', 'kolor'], 'fill-opacity': 0.16 } });
            const linie: [string, number[] | null][] = [['ciagla', null], ['przerywana', [3, 2]], ['kropkowana', [0.6, 2]]];
            for (const [styl, kreski] of linie) {
              mapaGL.addLayer({
                id: `obszary-linia-${styl}`, type: 'line', source: 'obszary', filter: ['==', ['get', 'styl'], styl],
                layout: { 'line-cap': styl === 'kropkowana' ? 'round' : 'butt' },
                paint: { 'line-color': ['get', 'kolor'], 'line-width': 2.4, ...(kreski ? { 'line-dasharray': kreski } : {}) },
              });
            }
            mapaGL.addLayer({ id: 'obszar-wybrany', type: 'line', source: 'obszary', filter: ['==', ['get', 'id'], BRAK_ID], paint: { 'line-color': m.aureola, 'line-width': 4.5 } });
          }
          if (!mapaGL.getSource('punkty')) {
            mapaGL.addSource('punkty', { type: 'geojson', data: n.punkty as never, cluster: true, clusterRadius: 42, clusterMaxZoom: 10 });
            mapaGL.addLayer({ id: 'punkt-wybrany', type: 'circle', source: 'punkty', filter: ['all', ['!', ['has', 'point_count']], ['==', ['get', 'id'], BRAK_ID]],
              paint: { 'circle-radius': 18, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 3.5, 'circle-stroke-color': m.aureola } });
            mapaGL.addLayer({ id: 'klastry', type: 'symbol', source: 'punkty', filter: ['has', 'point_count'],
              layout: { 'icon-image': ['concat', 'klaster-', ['to-string', ['min', ['get', 'point_count'], 100]]], 'icon-allow-overlap': true, 'icon-ignore-placement': true } });
            mapaGL.addLayer({ id: 'punkty', type: 'symbol', source: 'punkty', filter: ['!', ['has', 'point_count']],
              layout: { 'icon-image': ['get', 'ikona'], 'icon-allow-overlap': true, 'icon-ignore-placement': true } });
          }
          ustawWybor(najnowsze.current.wybrany);
          if (tryb === 'zapasowy') wczytajPolske();
        };

        const ustawWybor = (id: number | null) => {
          const wartosc = id ?? BRAK_ID;
          if (mapaGL.getLayer('punkt-wybrany')) mapaGL.setFilter('punkt-wybrany', ['all', ['!', ['has', 'point_count']], ['==', ['get', 'id'], wartosc]]);
          if (mapaGL.getLayer('obszar-wybrany')) mapaGL.setFilter('obszar-wybrany', ['==', ['get', 'id'], wartosc]);
        };
        // dostępne dla efektów poniżej
        (mapaGL as unknown as { _tzUstawWybor?: typeof ustawWybor })._tzUstawWybor = ustawWybor;

        mapaGL.on('styleimagemissing', e => {
          if (mapaGL.hasImage(e.id)) return;
          const obraz = rysujObraz(e.id, m);
          if (obraz) mapaGL.addImage(e.id, obraz, { pixelRatio: 2 });
        });
        mapaGL.on('style.load', zainstalujDane);
        mapaGL.on('load', () => najnowsze.current.onStan({ gotowa: true, podklad: tryb }));
        mapaGL.on('error', ev => {
          const zrodlo = (ev as unknown as { sourceId?: string }).sourceId;
          if (zrodlo === 'podklad' && tryb === 'pmtiles') {
            // podkład PMTiles nie odpowiada (zły adres, brak pliku): wracamy do prostego podkładu, dane zostają
            tryb = 'zapasowy';
            mapaGL.setStyle(stylZapasowy(m));
            najnowsze.current.onStan({ gotowa: true, podklad: 'zapasowy' });
          }
        });

        mapaGL.on('click', e => {
          const { x, y } = e.point;
          const cechy = mapaGL.queryRenderedFeatures([[x - ZASIEG_KLIKNIECIA, y - ZASIEG_KLIKNIECIA], [x + ZASIEG_KLIKNIECIA, y + ZASIEG_KLIKNIECIA]], { layers: WARSTWY_PUNKTOW.filter(l => mapaGL.getLayer(l)) });
          const grupa = cechy.find(f => f.properties && 'point_count' in f.properties);
          if (grupa) {
            const zrodlo = mapaGL.getSource('punkty') as GeoJSONSource;
            zrodlo.getClusterExpansionZoom(Number(grupa.properties.cluster_id)).then(zoom => {
              mapaGL.easeTo({ center: (grupa.geometry as unknown as { coordinates: [number, number] }).coordinates, zoom: Math.min(zoom + 0.4, 14), duration: reduced() ? 0 : 450 });
            }).catch(() => { /* grupa zniknęła po odświeżeniu danych */ });
            return;
          }
          const punkt = cechy[0];
          const obszar = punkt ? null : mapaGL.getLayer('obszary-wypelnienie') ? mapaGL.queryRenderedFeatures(e.point, { layers: ['obszary-wypelnienie'] })[0] : null;
          const id = Number((punkt ?? obszar)?.properties?.id);
          if (Number.isFinite(id) && (punkt || obszar)) { ostatniKlik.current = id; najnowsze.current.onWybierz(id); } else { ostatniKlik.current = null; najnowsze.current.onWybierz(null); }
        });
        mapaGL.on('mousemove', e => {
          const { x, y } = e.point;
          const jest = mapaGL.queryRenderedFeatures([[x - 10, y - 10], [x + 10, y + 10]], { layers: [...WARSTWY_PUNKTOW, 'obszary-wypelnienie'].filter(l => mapaGL.getLayer(l)) }).length > 0;
          mapaGL.getCanvas().style.cursor = jest ? 'pointer' : '';
        });

        // MapLibre mierzy kontener raz przy tworzeniu i pomija pierwsze zdarzenie własnego obserwatora: gdy układ strony jeszcze
        // się ustala (nagłówek, linia stanu), płótno zostaje za niskie. Własny obserwator przelicza rozmiar po każdej zmianie kontenera.
        let obserwator: ResizeObserver | null = null;
        if (typeof ResizeObserver !== 'undefined' && kontener.current) {
          obserwator = new ResizeObserver(() => { if (mapa.current) mapa.current.resize(); });
          obserwator.observe(kontener.current);
        }
        usun = () => { obserwator?.disconnect(); mapaGL.remove(); mapa.current = null; odepnijProtokol?.(); };
        if (anulowano) usun();
      } catch {
        // brak WebGL albo błąd ładowania: strona przełącza się na listę
        if (!anulowano) najnowsze.current.onStan({ gotowa: false, podklad: 'zapasowy', niedostepna: true });
      }
    })();
    return () => { anulowano = true; usun?.(); };
  }, []);

  // dane
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    (m.getSource('punkty') as GeoJSONSource | undefined)?.setData(p.punkty as never);
    (m.getSource('obszary') as GeoJSONSource | undefined)?.setData(p.obszary as never);
  }, [p.punkty, p.obszary]);

  // wybór: podświetlenie, a przelot tylko raz na wybrany wpis i tylko gdy wybór nie pochodzi z kliknięcia w mapę
  // (odświeżanie danych co 30 s nie może znowu przesuwać widoku)
  const przelecialDla = useRef<number | null>(null);
  const maPolozenie = p.polozenieWybranego !== null;
  useEffect(() => {
    const m = mapa.current as (MapaGL & { _tzUstawWybor?: (id: number | null) => void }) | null;
    if (!m) return;
    m._tzUstawWybor?.(p.wybrany);
    if (p.wybrany === null) { przelecialDla.current = null; ostatniKlik.current = null; return; }
    if (p.wybrany === przelecialDla.current) return;
    if (p.wybrany === ostatniKlik.current) { przelecialDla.current = p.wybrany; ostatniKlik.current = null; return; }
    const polozenie = najnowsze.current.polozenieWybranego;
    if (!polozenie) return;
    przelecialDla.current = p.wybrany;
    const duzy = window.matchMedia('(min-width: 900px)').matches;
    const padding = duzy ? { top: 60, bottom: 60, left: 60, right: 440 } : { top: 40, bottom: 320, left: 40, right: 40 };
    const duration = reduced() ? 0 : 600;
    if (polozenie.srodek) m.easeTo({ center: polozenie.srodek, zoom: Math.max(m.getZoom(), 11), padding, duration });
    else if (polozenie.bbox) m.fitBounds(polozenie.bbox, { padding, duration, maxZoom: 9 });
  }, [p.wybrany, maPolozenie, p.gotowa]);

  // region (filtr województwa): dopasowanie widoku
  const pierwszyRegion = useRef(true);
  useEffect(() => {
    if (pierwszyRegion.current) { pierwszyRegion.current = false; return; }
    mapa.current?.fitBounds(p.region ?? POLSKA_BBOX, { padding: 12, duration: reduced() ? 0 : 600, maxZoom: 9 });
  }, [p.region]);

  return <div ref={kontener} className="tz-mapa" role="region"
    aria-label="Mapa Polski z komunikatami. Strzałki przesuwają mapę, plus i minus zmieniają przybliżenie. Pełny odpowiednik mapy to widok Tabela, a prostszy Lista." />;
}
