import { useCallback, useSyncExternalStore } from 'react';

/**
 * Warstwa „Wpływ na narrację” (właściciel 8.10): przeszłość.today bada PRZESZŁOŚĆ na publicznych i płatnych danych;
 * diagnozy i siła spinu ze spin.clinic są tylko DODATKOWĄ, opcjonalną warstwą (domyślnie wyłączoną), którą później
 * dołączy wielkie drzewo powiązań. Jeden stan na całą stronę, zapamiętany w localStorage; ?narracja=1 włącza, ?narracja=0 wyłącza.
 */
export const NARRATIVE_KEY = 'px-narracja';
export const NARRATIVE_PARAM = 'narracja';
export const NARRATIVE_LABEL = 'Wpływ na narrację';
export const NARRATIVE_CAPTION = 'Warstwa: wpływ na narrację (dane spin.clinic)';

/** Adres ma pierwszeństwo przed zapamiętanym wyborem; bez żadnego z nich warstwa jest wyłączona. */
export function resolveNarrative(search: string, stored: string | null): boolean {
  const q = new URLSearchParams(search).get(NARRATIVE_PARAM);
  if (q === '1' || q === 'true') return true;
  if (q === '0' || q === 'false') return false;
  return stored === '1';
}

/** Zapytanie adresu po przełączeniu: ?narracja=1 przy włączonej, bez parametru przy wyłączonej; reszta zostaje. */
export function narrativeSearch(search: string, on: boolean): string {
  const p = new URLSearchParams(search);
  if (on) p.set(NARRATIVE_PARAM, '1'); else p.delete(NARRATIVE_PARAM);
  const s = p.toString();
  return s ? `?${s}` : '';
}

type GraphLike = { nodes: { id: string; kind: string }[]; edges: { source: string; target: string; label: string }[]; counts: Record<string, number> };
/** Graf bez diagnoz: węzły i krawędzie typu diagnosis, licznik diagnoz. Reszta (eksport, filtry, KRS) bez zmian. */
export function stripDiagnoses<G extends GraphLike>(graph: G): G {
  const drop = new Set(graph.nodes.filter(n => n.kind === 'diagnosis').map(n => n.id));
  if (!drop.size && !('diagnosis' in graph.counts)) return graph;
  const counts = { ...graph.counts }; delete counts.diagnosis; delete counts.diagnoses;
  return { ...graph, nodes: graph.nodes.filter(n => !drop.has(n.id)),
    edges: graph.edges.filter(e => !drop.has(e.source) && !drop.has(e.target) && e.label !== 'diagnoza Dr. Spina'), counts };
}

export type NarrativeEnv = { search: () => string; read: () => string | null; write: (v: string) => void; replaceSearch: (s: string) => void };
/** Sklep stanu bez Reacta (testowalny): jedna prawda dla wszystkich komponentów strony. */
export function createNarrativeStore(env: NarrativeEnv) {
  let state = false, ready = false;
  const listeners = new Set<() => void>();
  const init = () => { if (ready) return; ready = true; try { state = resolveNarrative(env.search(), env.read()); } catch { state = false; } };
  return {
    get: () => { init(); return state; },
    subscribe: (cb: () => void) => { init(); listeners.add(cb); return () => { listeners.delete(cb); }; },
    set: (on: boolean) => {
      init(); if (on === state) return; state = on;
      try { env.write(on ? '1' : '0'); } catch { /* tryb prywatny: stan żyje do odświeżenia */ }
      try { env.replaceSearch(narrativeSearch(env.search(), on)); } catch { /* adres bez zmian */ }
      listeners.forEach(l => l());
    },
  };
}

const browserStore = typeof window === 'undefined' ? null : createNarrativeStore({
  search: () => window.location.search,
  read: () => window.localStorage.getItem(NARRATIVE_KEY),
  write: v => window.localStorage.setItem(NARRATIVE_KEY, v),
  replaceSearch: s => window.history.replaceState(window.history.state, '', `${window.location.pathname}${s}${window.location.hash}`),
});
const off = () => false;
const none = () => () => undefined;

/** [włączona, ustaw]. Na serwerze i przy pierwszym renderze zawsze false (bez migotania diagnoz). */
export function useNarrativeLayer(): [boolean, (on: boolean) => void] {
  const on = useSyncExternalStore(browserStore ? browserStore.subscribe : none, browserStore ? browserStore.get : off, off);
  const set = useCallback((v: boolean) => browserStore?.set(v), []);
  return [on, set];
}
