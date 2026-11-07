/** Kontrakt zlecenia 104. Funkcje czyste używane także przez testy offline. */
export const CATEGORY_KEYS = ['nieruchomosci', 'spolki', 'dotacje', 'zamowienia', 'polityka', 'orzeczenia'] as const;
export type Category = typeof CATEGORY_KEYS[number];
export type Kind = 'person' | 'person_anon' | 'organisation' | 'authority' | 'contract' | 'grant' | 'property' | 'document' | 'statement' | 'vote' | 'media' | 'diagnosis';
export type Certainty = 'identifier' | 'manual' | 'name_only';
export type FlowSource = { key: string; label: string; license: string; url: string; retrieved_at: string | null };
export type FlowNode = { id: string; kind: Kind; label: string; short: string; level: number; category: Category | 'media'; date: string | null; amount: number | null; currency: string | null; certainty: Certainty; source: FlowSource; url: string | null; meta: Record<string, unknown> };
export type FlowEdge = { id: string; from: string; to: string; label: string; date_from: string | null; date_to: string | null; amount: number | null; currency: string | null; source_key: string; certainty: Certainty };
export type FlowData = {
  root: { id: string; kind: 'person' | 'organisation'; label: string; url: string };
  nodes: FlowNode[]; edges: FlowEdge[];
  categories: { key: Category; label: string; count: number; available: boolean }[];
  timeline: { date: string; node_id: string; kind: string; label: string; category: string }[];
  signals: unknown[];
  limits: { max_nodes: number; max_edges: number; truncated: boolean; grouped: { id: string; label: string; count: number; category: string; kind: string }[] };
  legal: { notes: string[]; narrative: boolean }; generated_at: string;
};
export type Filters = { categories: Category[] | null; od: string; do: string; unlinked: boolean; depth: number; history?: boolean };
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const strings = (v: Record<string, unknown>, keys: string[]) => keys.every(k => typeof v[k] === 'string');
const nullableString = (v: unknown) => v === null || typeof v === 'string';
const amount = (v: unknown) => v === null || (typeof v === 'number' && Number.isFinite(v));
const kinds: Kind[] = ['person', 'person_anon', 'organisation', 'authority', 'contract', 'grant', 'property', 'document', 'statement', 'vote', 'media', 'diagnosis'];
const certainty = (v: unknown) => ['identifier', 'manual', 'name_only'].includes(String(v));
export function parseFlow(value: unknown): FlowData {
  const bad = () => { throw new Error('Nieprawidłowy format danych drzewa.'); };
  if (!object(value)) return bad();
  const { root, nodes, edges, categories, timeline, signals, limits, legal, generated_at } = value;
  if (!object(root) || !strings(root, ['id', 'label', 'url']) || !['person', 'organisation'].includes(String(root.kind)) ||
    !Array.isArray(nodes) || !Array.isArray(edges) || !Array.isArray(categories) || !Array.isArray(timeline) || !Array.isArray(signals) ||
    !object(limits) || !Array.isArray(limits.grouped) || typeof limits.truncated !== 'boolean' || typeof limits.max_nodes !== 'number' || typeof limits.max_edges !== 'number' ||
    !object(legal) || !Array.isArray(legal.notes) || !legal.notes.every(x => typeof x === 'string') || typeof legal.narrative !== 'boolean' || typeof generated_at !== 'string') return bad();
  if (!nodes.every(n => object(n) && strings(n, ['id', 'label', 'short']) && kinds.includes(n.kind as Kind) &&
    Number.isInteger(n.level) && Number(n.level) >= 0 && Number(n.level) <= 3 && [...CATEGORY_KEYS, 'media'].includes(String(n.category)) &&
    nullableString(n.date) && nullableString(n.currency) && nullableString(n.url) && amount(n.amount) && certainty(n.certainty) && object(n.meta) &&
    object(n.source) && strings(n.source, ['key', 'label', 'license', 'url']) && nullableString(n.source.retrieved_at))) return bad();
  const ids = new Set(nodes.map(n => n.id));
  if (ids.size !== nodes.length || !edges.every(e => object(e) && strings(e, ['id', 'from', 'to', 'label', 'source_key']) && ids.has(e.from) && ids.has(e.to) &&
    nullableString(e.date_from) && nullableString(e.date_to) && nullableString(e.currency) && amount(e.amount) && certainty(e.certainty))) return bad();
  if (new Set(edges.map(e => e.id)).size !== edges.length || categories.length !== 6 || new Set(categories.map(c => c.key)).size !== 6 ||
    !categories.every(c => object(c) && CATEGORY_KEYS.includes(c.key as Category) && typeof c.label === 'string' && Number.isInteger(c.count) && Number(c.count) >= 0 && typeof c.available === 'boolean') ||
    !timeline.every(t => object(t) && strings(t, ['date', 'node_id', 'kind', 'label', 'category']) && ids.has(t.node_id)) ||
    !limits.grouped.every(g => object(g) && strings(g, ['id', 'label', 'category', 'kind']) && Number.isInteger(g.count) && Number(g.count) >= 0)) return bad();
  return value as FlowData;
}
const dateValue = (v: string | null) => v && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) ? v : '';
export function readFilters(search: string): Filters {
  const p = new URLSearchParams(search);
  let od = dateValue(p.get('od')), end = dateValue(p.get('do'));
  if (od && end && od > end) [od, end] = [end, od];
  return { categories: p.has('kategorie') ? CATEGORY_KEYS.filter(k => p.get('kategorie')!.split(',').includes(k)) : null,
    od, do: end, unlinked: p.get('pokaz_niepowiazane') === '1', depth: Math.min(3, Math.max(1, Number(p.get('glebokosc')) || 2)), history: p.get('cala_historia') === '1' };
}
export function flowQuery(filters: Filters, narrative: boolean): string {
  const p = new URLSearchParams({ narracja: narrative ? '1' : '0', glebokosc: String(filters.depth) });
  if (filters.categories !== null) p.set('kategorie', filters.categories.join(','));
  if (filters.od) p.set('od', filters.od); if (filters.do) p.set('do', filters.do);
  p.set('pokaz_niepowiazane', filters.unlinked ? '1' : '0');
  if (filters.history) p.set('cala_historia', '1');
  return p.toString();
}
export const filterCategory = (category: string) => category === 'media' ? 'polityka' : category;
export function visibleFlow(data: FlowData, filters: Filters, narrative: boolean): FlowData {
  const nodes = data.nodes.filter(n => (n.kind !== 'diagnosis' || narrative) && (n.certainty !== 'name_only' || filters.unlinked) &&
    (n.id === data.root.id || ((filters.categories === null || filters.categories.includes(filterCategory(n.category) as Category)) &&
      (!n.date || ((!filters.od || n.date >= filters.od) && (!filters.do || n.date <= filters.do))))))
    .slice(0, 300).map(n => n.kind === 'person_anon' ? { ...n, label: 'osoba fizyczna', short: 'osoba fizyczna' } : n);
  const ids = new Set(nodes.map(n => n.id));
  return { ...data, nodes, edges: data.edges.filter(e => ids.has(e.from) && ids.has(e.to) && (e.certainty !== 'name_only' || filters.unlinked) &&
    (!filters.od || !(e.date_to || e.date_from) || (e.date_to || e.date_from)! >= filters.od) &&
    (!filters.do || !e.date_from || e.date_from <= filters.do)).slice(0, 600),
    timeline: data.timeline.filter(t => ids.has(t.node_id) && (!filters.od || t.date >= filters.od) && (!filters.do || t.date <= filters.do)),
    signals: narrative ? data.signals : [], limits: { ...data.limits, truncated: data.limits.truncated || data.nodes.length > 300 || data.edges.length > 600,
      grouped: data.limits.grouped.filter(g => (narrative || g.kind !== 'diagnosis') && (filters.categories === null || filters.categories.includes(filterCategory(g.category) as Category))) } };
}
export const NODE_W = 228, NODE_H = 112, LEVEL_GAP = 228;
/** Stałe sloty według level/id. Filtrowanie nie przesuwa pozostałych węzłów. */
export function flowLayout(nodes: FlowNode[]) {
  const rows = [0, 1, 2, 3].map(level => nodes.filter(n => n.level === level).sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const width = Math.max(820, ...rows.map(row => row.length * (NODE_W + 48) + 48));
  return { width, height: 936, nodes: rows.flatMap((row, level) => row.map((node, i) => ({ node,
    x: (width - row.length * (NODE_W + 48) + 48) / 2 + i * (NODE_W + 48), y: 24 + level * LEVEL_GAP }))) };
}
export const edgeWidth = (value: number | null) => value === null ? 1.5 : 1.5 + Math.min(5, Math.log10(1 + Math.abs(value)) * .55);
export function safeHref(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  if (value.startsWith('/') && !value.startsWith('//') && !value.includes('\\')) return value;
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : undefined; } catch { return undefined; }
}
