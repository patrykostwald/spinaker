"use client";
import { useEffect, useMemo, useState } from 'react';
import { Loading } from '@spin-clinic/ui/kit';

/**
 * przeszłość.today, tydzień 1 (właściciel 5.10): drzewo powiązań tematu z danych spin.clinic.
 * Kolumny według rodzaju, najechanie lub dotknięcie podświetla powiązane elementy; pod spodem oś czasu.
 */
type Node = { id: string; kind: string; label: string; date?: string | null; url?: string; sub?: string; role?: string; camp?: string; intensity?: number; links: number };
type Edge = { source: string; target: string; label: string };
type Graph = { topic: string; terms: string[]; nodes: Node[]; edges: Edge[]; counts: Record<string, number> };

const COLUMNS: [string, string][] = [['person', 'Osoby'], ['organisation', 'Spółki i fundacje (KRS)'], ['record', 'Sejm'],
  ['statement', 'Wpisy na X'], ['diagnosis', 'Diagnozy Dr. Spina'], ['media', 'Media']];
const SUB: Record<string, string> = { print: 'druk', ballot: 'głosowanie', voting: 'głosowanie', consultation: 'konsultacje', lobby_activity: 'lobbing', lobby_document: 'lobbing', financial_document: 'finanse', financial_row: 'finanse' };
const EXAMPLES = ['CPK', 'ceny energii', 'Turów', 'KPO'];

export function TopicTree() {
  const [query, setQuery] = useState('');
  const [data, setData] = useState<Graph | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'error' | 'off'>('idle');
  const [focus, setFocus] = useState<string | null>(null);

  async function load(q: string) {
    setState('loading'); setFocus(null);
    try {
      const response = await fetch(`/api/przeszlosc/temat/?q=${encodeURIComponent(q)}`);
      if (response.status === 404) { setState('off'); return; }
      if (!response.ok) throw new Error();
      setData(await response.json()); setState('idle');
      window.history.replaceState(null, '', `?q=${encodeURIComponent(q)}`);
    } catch { setState('error'); }
  }
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('q');
    if (q) { setQuery(q); void load(q); }
  }, []);

  const linked = useMemo(() => {
    if (!data || !focus) return null;
    const ids = new Set([focus]);
    for (const e of data.edges) { if (e.source === focus) ids.add(e.target); if (e.target === focus) ids.add(e.source); }
    return ids;
  }, [data, focus]);
  const timeline = useMemo(() => (data?.nodes ?? []).filter(n => n.date).sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '')).slice(0, 40), [data]);

  return <main className="sc-pt">
    <header className="sc-pt__head">
      <p className="sc-pt__k">przeszłość.today · podgląd na danych spin.clinic</p>
      <h1>Kto, co i kiedy w jednym temacie</h1>
      <p>Wpisz temat. Pokażemy osoby publiczne, ich spółki i fundacje z KRS, dokumenty Sejmu, wpisy na X z diagnozami Dr. Spina i artykuły. Każde powiązanie ma źródło.</p>
      <form onSubmit={event => { event.preventDefault(); if (query.trim().length >= 3) void load(query.trim()); }} className="sc-pt__search">
        <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Np. CPK, lotnisko" aria-label="Temat" />
        <button type="submit">Pokaż</button>
      </form>
      <p className="sc-pt__ex">Przykłady: {EXAMPLES.map(e => <button key={e} type="button" onClick={() => { setQuery(e); void load(e); }}>{e}</button>)}</p>
    </header>

    {state === 'loading' && <Loading label="Ładowanie tematu" />}
    {state === 'off' && <p className="sc-pt__msg">Podgląd jest jeszcze wyłączony na serwerze.</p>}
    {state === 'error' && <p className="sc-pt__msg" role="alert">Nie udało się pobrać tematu. Spróbuj ponownie.</p>}
    {state === 'idle' && data && <>
      <p className="sc-pt__sum">{data.nodes.length ? `${data.nodes.length} elementów, ${data.edges.length} powiązań. Najedź na element, aby zobaczyć, z czym się łączy.` : 'Nic nie znaleźliśmy. Spróbuj innego słowa.'}</p>
      <div className="sc-pt__cols" onMouseLeave={() => setFocus(null)}>
        {COLUMNS.map(([kind, title]) => {
          const rows = data.nodes.filter(n => n.kind === kind);
          if (!rows.length) return null;
          return <section key={kind} className="sc-pt__col" aria-label={title}>
            <h2>{title} <small>{rows.length}</small></h2>
            <ul>{rows.slice(0, 25).map(n => <li key={n.id} data-dim={linked && !linked.has(n.id) ? '' : undefined} data-on={focus === n.id ? '' : undefined}
              onMouseEnter={() => setFocus(n.id)} onClick={() => setFocus(focus === n.id ? null : n.id)}>
              <span className="sc-pt__label">{n.label}</span>
              <span className="sc-pt__meta">{[n.role, n.kind === 'record' && n.sub ? SUB[n.sub] ?? n.sub : n.sub, n.date, n.intensity != null ? `spin ${n.intensity}/100` : '', n.links ? `${n.links} powiąz.` : ''].filter(Boolean).join(' · ')}</span>
              {n.url && <a href={n.url} target="_blank" rel="noopener noreferrer" onClick={event => event.stopPropagation()}>źródło →</a>}
            </li>)}</ul>
          </section>;
        })}
      </div>
      {timeline.length > 0 && <section className="sc-pt__time" aria-label="Oś czasu">
        <h2>Oś czasu</h2>
        <ol>{timeline.map(n => <li key={n.id} data-kind={n.kind}><time>{n.date}</time><span>{COLUMNS.find(c => c[0] === n.kind)?.[1]}</span><b>{n.label}</b></li>)}</ol>
      </section>}
    </>}
  </main>;
}
