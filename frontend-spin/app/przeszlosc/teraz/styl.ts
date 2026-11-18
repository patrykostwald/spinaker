import type { StyleSpecification, LayerSpecification } from 'maplibre-gl';

/**
 * Styl podkładu mapy „Teraz”. Dwa warianty, oba bez serwerów kafelków osób trzecich:
 *  1. PMTiles (NEXT_PUBLIC_TERAZ_PODKLAD_URL): styl wektorowy pod schemat Protomaps (warstwy earth, water, landuse,
 *     roads, boundaries, places). Podpisy miejscowości tylko gdy podano szablon glifów (NEXT_PUBLIC_TERAZ_GLIFY_URL).
 *  2. Zapasowy: tło, siatka długości i szerokości oraz granica Polski z lekkiego GeoJSON (public/teraz/polska.geojson,
 *     Natural Earth, domena publiczna). Uproszczenie do ok. 1,3 tys. punktów.
 * Barwy podkładu są stonowane, żeby znaczniki warstw były najwyraźniejsze.
 */
export interface Motyw {
  tlo: string; ziemia: string; woda: string; las: string; droga: string; droga2: string; granica: string; granicaRegionu: string;
  siatka: string; obrys: string; tekst: string; tekstObrys: string; aureola: string;
}

export const MOTYW_CIEMNY: Motyw = {
  tlo: '#0e1013', ziemia: '#1a1e24', woda: '#0d1a26', las: '#18221d', droga: '#3a414b', droga2: '#2a3037', granica: '#7b8594', granicaRegionu: '#444c58',
  siatka: '#2a3037', obrys: '#8a93a1', tekst: '#c4cad3', tekstObrys: '#0e1013', aureola: '#ffffff',
};
export const MOTYW_JASNY: Motyw = {
  tlo: '#dfe3e8', ziemia: '#f1f2f4', woda: '#c7d9e8', las: '#e1eadb', droga: '#c3c8cf', droga2: '#d9dce1', granica: '#5d6673', granicaRegionu: '#a9afb8',
  siatka: '#cfd3d9', obrys: '#5d6673', tekst: '#2b3038', tekstObrys: '#f1f2f4', aureola: '#10141a',
};

const OSM_ATRYBUCJA = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">współtwórcy OpenStreetMap</a>, <a href="https://protomaps.com" target="_blank" rel="noopener noreferrer">Protomaps</a>';
export const ATRYBUCJA_NE = 'Granica Polski: <a href="https://www.naturalearthdata.com" target="_blank" rel="noopener noreferrer">Natural Earth</a> (domena publiczna)';

export function stylZPmtiles(pmtilesUrl: string, glifyUrl: string, m: Motyw): StyleSpecification {
  const z = (minzoom: number, maxzoom = 24) => ({ minzoom, maxzoom });
  const warstwy: LayerSpecification[] = [
    { id: 'tlo', type: 'background', paint: { 'background-color': m.tlo } },
    { id: 'ziemia', type: 'fill', source: 'podklad', 'source-layer': 'earth', paint: { 'fill-color': m.ziemia } },
    { id: 'lasy', type: 'fill', source: 'podklad', 'source-layer': 'landuse', filter: ['in', ['get', 'kind'], ['literal', ['forest', 'park', 'nature_reserve', 'national_park']]], paint: { 'fill-color': m.las, 'fill-opacity': 0.9 } },
    { id: 'woda', type: 'fill', source: 'podklad', 'source-layer': 'water', paint: { 'fill-color': m.woda } },
    { id: 'drogi-poboczne', type: 'line', source: 'podklad', 'source-layer': 'roads', ...z(9), filter: ['in', ['get', 'kind'], ['literal', ['medium_road', 'minor_road']]], paint: { 'line-color': m.droga2, 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.4, 14, 1.6] } },
    { id: 'drogi-glowne', type: 'line', source: 'podklad', 'source-layer': 'roads', ...z(5), filter: ['in', ['get', 'kind'], ['literal', ['highway', 'major_road']]], paint: { 'line-color': m.droga, 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 14, 2.6] } },
    { id: 'granice-regionow', type: 'line', source: 'podklad', 'source-layer': 'boundaries', filter: ['==', ['get', 'kind'], 'region'], paint: { 'line-color': m.granicaRegionu, 'line-width': 0.8, 'line-dasharray': [3, 2] } },
    { id: 'granice-panstw', type: 'line', source: 'podklad', 'source-layer': 'boundaries', filter: ['==', ['get', 'kind'], 'country'], paint: { 'line-color': m.granica, 'line-width': 1.4 } },
  ];
  if (glifyUrl) {
    warstwy.push({
      id: 'miejscowosci', type: 'symbol', source: 'podklad', 'source-layer': 'places', ...z(4),
      filter: ['==', ['get', 'kind'], 'locality'],
      layout: {
        'text-field': ['coalesce', ['get', 'name:pl'], ['get', 'name']],
        'text-font': ['Noto Sans Regular'],
        'text-size': ['interpolate', ['linear'], ['zoom'], 4, 11, 10, 14],
        'text-max-width': 8,
      },
      paint: { 'text-color': m.tekst, 'text-halo-color': m.tekstObrys, 'text-halo-width': 1.2 },
    });
  }
  return {
    version: 8,
    ...(glifyUrl ? { glyphs: glifyUrl } : {}),
    sources: { podklad: { type: 'vector', url: `pmtiles://${pmtilesUrl}`, attribution: OSM_ATRYBUCJA } },
    layers: warstwy,
  };
}

/** Siatka co 1 stopień nad Polską i okolicami (linie południków i równoleżników). */
export interface SiatkaGeoJson {
  type: 'FeatureCollection';
  features: { type: 'Feature'; properties: Record<string, never>; geometry: { type: 'LineString'; coordinates: number[][] } }[];
}
export function siatka(): SiatkaGeoJson {
  const features: SiatkaGeoJson['features'] = [];
  for (let lon = 12; lon <= 26; lon++) features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[lon, 47], [lon, 57]] } });
  for (let lat = 47; lat <= 57; lat++) features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[12, lat], [26, lat]] } });
  return { type: 'FeatureCollection', features };
}

export function stylZapasowy(m: Motyw): StyleSpecification {
  return {
    version: 8,
    sources: {
      siatka: { type: 'geojson', data: siatka() },
      polska: { type: 'geojson', data: { type: 'FeatureCollection', features: [] }, attribution: ATRYBUCJA_NE },
    },
    layers: [
      { id: 'tlo', type: 'background', paint: { 'background-color': m.tlo } },
      { id: 'siatka', type: 'line', source: 'siatka', paint: { 'line-color': m.siatka, 'line-width': 0.8 } },
      { id: 'polska-wypelnienie', type: 'fill', source: 'polska', paint: { 'fill-color': m.ziemia } },
      { id: 'polska-granica', type: 'line', source: 'polska', paint: { 'line-color': m.obrys, 'line-width': 1.4 } },
    ],
  };
}
