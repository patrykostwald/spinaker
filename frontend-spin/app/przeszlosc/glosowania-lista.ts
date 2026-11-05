/**
 * Funkcje czyste listy głosowań Sejmu i sieci powiązań (przeszłość.today, port v3, 13.10.2026).
 * Bez Reacta i bez DOM: testowane w tests/119-przeszlosc-v3-lista.test.cjs. Kontrakt: gust/spin/port/API-v3.md, sekcje 3 i 4.
 */

/** Adres z danych zewnętrznych: tylko http(s) albo ścieżka w serwisie (bez //); inaczej null (nie renderujemy odnośnika). */
export function safeUrl(u: unknown): string | null {
  if (typeof u !== 'string') return null;
  const s = u.trim();
  if (/^https?:\/\/[^\s]+$/i.test(s)) return s;
  return /^\/(?!\/)[^\s]*$/.test(s) ? s : null;
}

/* ---------------------------------------------------------------- lista głosowań (sekcja 3) */

export type VoteOutcome = 'przyjete' | 'odrzucone' | 'nieustalone';
export type ClubVotes = { club: string; votes: Record<string, number> } | null;
export type VoteListRow = {
  id: string; term: number; sitting: number; number: number; title: string; motion: string; date: string | null; kind: string;
  result: { yes?: number; no?: number; abstain?: number; notParticipating?: number } | null;
  majority: { type: string; votes: number } | null; outcome: VoteOutcome | string; url: string; club_votes?: ClubVotes;
};
export type VotesListResponse = {
  results: VoteListRow[]; total: number; page: number; pages: number; per_page: number;
  filter: { kadencja: number | null; klub: string | null; od: string | null; do: string | null; wynik: string | null; q: string };
  clubs: string[];
  coverage: { scope: string; complete: boolean; description: string; total_votings: number; terms: { term: number; votings: number; first: string | null; last: string | null }[] };
};

export type VoteFilters = { q: string; klub: string; wynik: '' | VoteOutcome; od: string; do: string };
export const EMPTY_FILTERS: VoteFilters = { q: '', klub: '', wynik: '', od: '', do: '' };
export const MIN_QUERY = 3;
export const MAX_QUERY = 120;
export const PER_PAGE = 20;
const OUTCOMES: VoteOutcome[] = ['przyjete', 'odrzucone', 'nieustalone'];
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
const validDay = (v: string) => ISO_DAY.test(v) && !Number.isNaN(Date.parse(`${v}T00:00:00Z`));

/** Zapytanie do API: tylko poprawne, niepuste parametry; q krótsze niż 3 znaki jest pomijane (API zwróciłoby 400). */
export function buildVotesQuery(f: VoteFilters, page = 1, perPage = PER_PAGE): string {
  const p = new URLSearchParams();
  const q = f.q.trim().slice(0, MAX_QUERY);
  if (q.length >= MIN_QUERY) p.set('q', q);
  if (f.klub.trim()) p.set('klub', f.klub.trim());
  if ((OUTCOMES as string[]).includes(f.wynik)) p.set('wynik', f.wynik);
  let od = validDay(f.od) ? f.od : '', do_ = validDay(f.do) ? f.do : '';
  if (od && do_ && od > do_) [od, do_] = [do_, od]; // API odrzuca od > do (400)
  if (od) p.set('od', od);
  if (do_) p.set('do', do_);
  p.set('strona', String(Math.max(1, Math.floor(page) || 1)));
  p.set('na_strone', String(Math.min(50, Math.max(1, Math.floor(perPage) || PER_PAGE))));
  return p.toString();
}

/** Filtry z adresu strony (?q=&klub=&wynik=&od=&do=) - bezpiecznie, nieznane wartości są odrzucane. */
export function parseFilters(search: string): VoteFilters {
  const p = new URLSearchParams(search);
  const wynik = p.get('wynik') ?? '';
  const od = p.get('od') ?? '', do_ = p.get('do') ?? '';
  return {
    q: (p.get('q') ?? '').slice(0, MAX_QUERY), klub: (p.get('klub') ?? '').slice(0, 40),
    wynik: (OUTCOMES as string[]).includes(wynik) ? (wynik as VoteOutcome) : '',
    od: validDay(od) ? od : '', do: validDay(do_) ? do_ : '',
  };
}

/** Odwrotność parseFilters: krótki adres do udostępnienia; puste filtry = pusty tekst. */
export function filtersToSearch(f: VoteFilters): string {
  const p = new URLSearchParams();
  if (f.q.trim().length >= MIN_QUERY) p.set('q', f.q.trim());
  if (f.klub) p.set('klub', f.klub);
  if (f.wynik) p.set('wynik', f.wynik);
  if (f.od) p.set('od', f.od);
  if (f.do) p.set('do', f.do);
  const s = p.toString();
  return s ? `?${s}` : '';
}

export const hasFilters = (f: VoteFilters) => Boolean(f.q.trim() || f.klub || f.wynik || f.od || f.do);
export const queryTooShort = (q: string) => q.trim().length > 0 && q.trim().length < MIN_QUERY;

export const OUTCOME_LABEL: Record<string, string> = { przyjete: 'przyjęte', odrzucone: 'odrzucone', nieustalone: 'wynik nieustalony' };
export const outcomeLabel = (o: string) => OUTCOME_LABEL[o] ?? 'wynik nieustalony';

/* Sortowanie po stronie klienta: API zwraca kolejność data malejąco, numer malejąco i nie sortuje inaczej.
   Sortowanie obejmuje wczytane wiersze (strony pobrane do tej pory), nie całą bazę - interfejs mówi o tym wprost. */
export type SortKey = 'date' | 'result';
export type SortDir = 'desc' | 'asc';
const yes = (r: VoteListRow) => r.result?.yes ?? -1;
const no = (r: VoteListRow) => r.result?.no ?? -1;
export function sortRows(rows: VoteListRow[], key: SortKey, dir: SortDir): VoteListRow[] {
  const sign = dir === 'asc' ? 1 : -1;
  const cmp = (a: VoteListRow, b: VoteListRow) => {
    if (key === 'result') {
      // wynik ogółem: liczba głosów "za", przy remisie "przeciw"; brak liczb zawsze na końcu
      const missingA = a.result == null, missingB = b.result == null;
      if (missingA !== missingB) return missingA ? 1 : -1;
      const d = yes(a) - yes(b) || no(a) - no(b);
      if (d) return sign * d;
    }
    const byDate = (a.date ?? '').localeCompare(b.date ?? '');
    if (byDate) return sign * byDate;
    return sign * ((a.sitting - b.sitting) || (a.number - b.number));
  };
  return rows.map((r, i) => [r, i] as const).sort((a, b) => cmp(a[0], b[0]) || a[1] - b[1]).map(x => x[0]);
}

/** Dołącza kolejną stronę bez dublowania głosowań (id kadencja/posiedzenie/numer). */
export function mergeRows(prev: VoteListRow[], next: VoteListRow[]): VoteListRow[] {
  const seen = new Set(prev.map(r => r.id));
  return [...prev, ...next.filter(r => !seen.has(r.id))];
}

const CAST = ['za', 'przeciw', 'wstrzymał się'];
/** Głos klubu: dominujący głos oddany (za, przeciw, wstrzymał się; nieobecni nie są głosem) i liczby słowem. */
export function clubSummary(cv: ClubVotes | undefined): { word: string; split: boolean; counts: string; parts: { key: string; n: number; label: string }[] } | null {
  if (!cv || !cv.votes) return null;
  const entries = Object.entries(cv.votes).filter(([, n]) => n > 0);
  if (!entries.length) return null;
  const cast = entries.filter(([k]) => CAST.includes(k)).sort((a, b) => b[1] - a[1]);
  const word = cast[0]?.[0] ?? entries.sort((a, b) => b[1] - a[1])[0][0];
  const order = [...CAST, 'nieobecny'];
  const rank = (k: string) => order.includes(k) ? order.indexOf(k) : order.length;
  const parts = [...entries].sort((a, b) => rank(a[0]) - rank(b[0]) || b[1] - a[1]).map(([k, n]) => ({ key: k, n, label: k === 'nieobecny' ? 'nieob.' : k }));
  const counts = parts.map(p => `${p.n} ${p.label}`).join(', ');
  return { word, split: cast.length > 1, counts, parts };
}

/** 2026-09-26 -> 26.09.2026 (stała szerokość w tabeli). */
export const shortDay = (d: string | null | undefined) => d ? d.slice(0, 10).split('-').reverse().join('.') : '';

/* ---------------------------------------------------------------- CSV z widocznych wierszy */

/** Komórka CSV: cudzysłowy podwojone, białe znaki zwinięte, ochrona przed formułami arkusza (=, +, -, @ na początku). */
export function csvCell(v: unknown): string {
  let s = String(v ?? '').replace(/\s+/g, ' ').trim();
  if (/^[=+\-@]/.test(s)) s = `'${s}`;
  return `"${s.replace(/"/g, '""')}"`;
}

export function votesToCsv(rows: VoteListRow[], opts: { klub?: string; stamp: string; total?: number; description?: string }): string {
  const head = ['data', 'kadencja', 'posiedzenie', 'numer', 'tytul', 'wniosek', 'za', 'przeciw', 'wstrzymalo_sie', 'nieobecni', 'wynik_ogolem',
    ...(opts.klub ? [`glos_klubu_${opts.klub}`, `liczby_klubu_${opts.klub}`] : []), 'zrodlo'];
  const lines = [head.map(csvCell).join(';')];
  for (const r of rows) {
    const c = clubSummary(r.club_votes);
    lines.push([r.date ?? '', r.term, r.sitting, r.number, r.title, r.motion, r.result?.yes ?? '', r.result?.no ?? '', r.result?.abstain ?? '',
      r.result?.notParticipating ?? '', outcomeLabel(r.outcome),
      ...(opts.klub ? [c ? c.word : 'brak w naszych danych', c ? c.counts : ''] : []), r.url].map(csvCell).join(';'));
  }
  const scope = `Wiersze: ${rows.length}${opts.total ? ` z ${opts.total} spełniających filtry` : ''}. ${opts.description ?? 'To nie jest pełne archiwum głosowań Sejmu.'}`;
  lines.push('', csvCell(`Źródło: przeszłość.today, głosowania Sejmu (api.sejm.gov.pl, sejm.gov.pl), pobrano ${opts.stamp}. ${scope}`));
  return '﻿' + lines.join('\r\n');
}

/* ---------------------------------------------------------------- sieć powiązań (sekcja 4) */

export type NetNode = { id: string; kind: string; label: string; role?: string | null; club?: string | null; slug?: string | null; root?: boolean };
export type NetEvidence = { kind: string; label: string; url: string };
export type NetEdge = { source: string; target: string; kind: string; weight: number; label: string; evidence: NetEvidence[] };
export type NetResponse = {
  person: { id: number; slug: string; name: string; role: string }; nodes: NetNode[]; edges: NetEdge[];
  coverage: { people: number; krs: number; votes_window: number; votes_available: boolean }; note: string;
};

/** Kolejność grup: najpierw udokumentowane (współwystępowanie, głosowania), na końcu kontekst KRS. */
export const GROUP_ORDER = ['wspolwystepowanie', 'glosowania', 'krs'] as const;
export const GROUP_TITLE: Record<string, string> = { wspolwystepowanie: 'Współwystępowanie', glosowania: 'Zgodność głosów', krs: 'Kontekst KRS' };
/** Linia ciągła = udokumentowane; kreskowana = kontekst (KRS nie jest dowodem związku). */
export const isContext = (kind: string) => kind === 'krs';

export type NetRow = { key: string; edge: NetEdge; node: NetNode; href: string | null; weightText: string; labelText: string };
export type NetGroup = { kind: string; title: string; rows: NetRow[] };

const plural = (n: number, one: string, few: string, many: string) => n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many;
export const edgeKey = (e: NetEdge) => `${e.source}>${e.target}>${e.kind}`;

/** Adres profilu węzła: slug, a dla "figure:<id>" sam numer; węzły spoza rejestru ("mp:...") bez odnośnika. */
export function nodeHref(n: NetNode): string | null {
  if (n.slug && /^[1-9]\d{0,9}(-[a-z0-9-]{1,120})?$/.test(n.slug)) return `/przeszlosc/osoba/${n.slug}`;
  const m = /^figure:([1-9]\d{0,9})$/.exec(n.id);
  return m ? `/przeszlosc/osoba/${m[1]}` : null;
}

/** Waga z jednostką zależną od rodzaju krawędzi (punkty, podmioty, procent zgodności). */
export function weightText(e: NetEdge): string {
  const w = Number.isFinite(e.weight) ? e.weight : 0;
  const num = w.toLocaleString('pl-PL', { maximumFractionDigits: 1 });
  if (e.kind === 'glosowania') return `${num}%`;
  if (e.kind === 'krs') return `${num} ${plural(w, 'podmiot', 'podmioty', 'podmiotów')}`;
  return `${num} ${plural(w, 'punkt', 'punkty', 'punktów')}`;
}

/** Etykieta pod nazwiskiem w rysunku: liczbę procentów pokazuje kolumna wagi, więc z etykiety głosowań jest zdjęta (lista tekstowa ma pełną). */
export function displayLabel(e: NetEdge): string {
  if (e.kind !== 'glosowania') return e.label;
  return e.label.replace(/\s*\d+(?:[.,]\d+)?\s*%/, '').replace(/\s{2,}/g, ' ').trim() || e.label;
}

/** Krawędzie od korzenia pogrupowane i uporządkowane: waga malejąco, potem nazwisko; krawędzie spoza grafu (brak węzła) pomijane. */
export function groupEdges(net: Pick<NetResponse, 'nodes' | 'edges'>): NetGroup[] {
  const nodes = new Map(net.nodes.map(n => [n.id, n]));
  const root = net.nodes.find(n => n.root)?.id;
  const out: NetGroup[] = [];
  for (const kind of GROUP_ORDER) {
    const rows: NetRow[] = [];
    for (const e of net.edges) {
      if (e.kind !== kind) continue;
      const other = e.source === root ? e.target : e.target === root ? e.source : null;
      const node = other ? nodes.get(other) : undefined;
      if (!node) continue;
      rows.push({ key: edgeKey(e), edge: e, node, href: nodeHref(node), weightText: weightText(e), labelText: displayLabel(e) });
    }
    rows.sort((a, b) => b.edge.weight - a.edge.weight || a.node.label.localeCompare(b.node.label, 'pl'));
    if (rows.length) out.push({ kind, title: GROUP_TITLE[kind], rows });
  }
  return out;
}

/** Ile wierszy każdej grupy pokazać w rysunku, gdy lista jest zwinięta; reszta jest w liście tekstowej i po rozwinięciu. */
export const NET_PREVIEW = 6;
export function visibleGroups(groups: NetGroup[], all: boolean, limit = NET_PREVIEW): NetGroup[] {
  return all ? groups : groups.map(g => ({ ...g, rows: g.rows.slice(0, limit) }));
}
export const netTotal = (groups: NetGroup[]) => groups.reduce((n, g) => n + g.rows.length, 0);
