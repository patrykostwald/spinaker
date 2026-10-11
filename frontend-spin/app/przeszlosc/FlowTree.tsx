"use client";
import { Sprostowanie } from './Sprostowanie';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Loading } from '@spin-clinic/ui/kit';
import { Bar, Foot, Icon, nb, plural, useAccess, useStandalone } from './ui';
import { useNarrativeLayer } from './narracja';
import { CATEGORY_KEYS, NODE_H, NODE_W, edgeWidth, filterCategory, flowLayout, flowQuery, parseFlow, readFilters, safeHref, visibleFlow,
  type Category, type Filters, type FlowData, type FlowEdge, type FlowNode, type Kind } from './flow';

const TYPE: Record<Kind, string> = { person: 'Osoba publiczna', person_anon: 'Osoba fizyczna', organisation: 'Podmiot', authority: 'Organ', contract: 'Umowa / zamówienie',
  grant: 'Dotacja', property: 'Nieruchomość', document: 'Dokument', statement: 'Wpis / wystąpienie', vote: 'Głosowanie', media: 'Artykuł', diagnosis: 'Wpływ na narrację' };
const ICON: Record<Kind, string> = { person: 'person', person_anon: 'person', organisation: 'organisation', authority: 'institution', contract: 'record',
  grant: 'down', property: 'organisation', document: 'record', statement: 'statement', vote: 'vote', media: 'media', diagnosis: 'diagnosis' };
const CERTAINTY = { identifier: 'Potwierdzone identyfikatorem', manual: 'Potwierdzone ręcznie', name_only: 'Zgodność nazwy, nie liczona' };
const retrieved = (value?: string | null) => value && !Number.isNaN(Date.parse(value))
  ? new Intl.DateTimeFormat('pl-PL', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Warsaw' }).format(new Date(value)) + ' (Warszawa)' : 'Nie podano';
const CATEGORY_LABELS = ['Nieruchomości', 'Spółki', 'Dotacje', 'Zamówienia', 'Polityka', 'Orzeczenia'];
const money = (n: number | null, currency: string | null) => n === null ? 'Nie podano kwoty' : `${n.toLocaleString('pl-PL', { maximumFractionDigits: 2 })} ${currency || ''}`.trim();
type Selection = { kind: 'node' | 'edge'; id: string } | null;

export function FlowTree({ ident }: { ident: string }) {
  useStandalone();
  const access = useAccess();
  const [narrative] = useNarrativeLayer();
  const [filters, setFilters] = useState<Filters | null>(null);
  const [data, setData] = useState<FlowData | null>(null);
  const [layoutData, setLayoutData] = useState<FlowData | null>(null);
  const [state, setState] = useState('loading');
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [selection, setSelection] = useState<Selection>(null);
  const [zoom, setZoom] = useState(1);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [narrow, setNarrow] = useState(false);
  const viewport = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const timelineDomain = useRef<{ ident: string; dates: string[] }>({ ident: '', dates: [] });
  const centeredRoot = useRef('');
  useEffect(() => {
    const sync = () => setFilters(readFilters(window.location.search));
    sync(); window.addEventListener('popstate', sync); return () => window.removeEventListener('popstate', sync);
  }, []);
  useEffect(() => { const media = window.matchMedia('(max-width: 760px)'); const sync = () => setNarrow(media.matches);
    sync(); media.addEventListener('change', sync); return () => media.removeEventListener('change', sync); }, []);
  const query = filters ? flowQuery(filters, narrative) : '';
  useEffect(() => {
    if (!filters) return;
    const abort = new AbortController();
    setState('loading'); setSelection(null);
    fetch(`/api/przeszlosc/przeplyw/${encodeURIComponent(ident)}/?${query}`, { signal: abort.signal }).then(async response => {
      if (response.status === 401 || response.status === 403) { setState('locked'); return; }
      if (response.status === 404) { setState('missing'); return; }
      if (!response.ok) throw new Error('Nie udało się pobrać drzewa. Spróbuj ponownie.');
      const next = parseFlow(await response.json());
      if (abort.signal.aborted) return;
      const domainKey = `${ident}:${narrative}:${filters.unlinked}`;
      if (timelineDomain.current.ident !== domainKey) timelineDomain.current = { ident: domainKey, dates: [] };
      const safe = visibleFlow(next, { categories: null, od: '', do: '', unlinked: filters.unlinked, depth: 3 }, narrative);
      timelineDomain.current.dates = [...new Set([...timelineDomain.current.dates, ...safe.timeline.map(t => t.date)])].sort();
      setLayoutData(previous => previous?.root.id === next.root.id ? { ...next, nodes: [...next.nodes, ...previous.nodes.filter(n => !next.nodes.some(current => current.id === n.id))].slice(0, 300) } : next);
      setData(next); setState('ready'); document.title = `${next.root.label} - Drzewo przepływu - przeszłość.today`;
    }).catch(reason => { if (!abort.signal.aborted) { setError(reason instanceof Error && reason.message === 'Nieprawidłowy format danych drzewa.'
      ? reason.message : 'Nie udało się pobrać drzewa. Spróbuj ponownie.'); setState('error'); } });
    return () => abort.abort();
    // query zawiera wszystkie filtry; zmiana nieaktualnego żądania jest anulowana.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ident, query, retry]);
  const graph = useMemo(() => data && filters ? visibleFlow(data, filters, narrative) : null, [data, filters, narrative]);
  const layout = useMemo(() => flowLayout(layoutData ? visibleFlow(layoutData, { categories: null, od: '', do: '', unlinked: true, depth: 3 }, narrative).nodes : []), [layoutData, narrative]);
  const positions = useMemo(() => new Map(layout.nodes.map(p => [p.node.id, p])), [layout]);
  useEffect(() => {
    if (state !== 'ready' || !graph || centeredRoot.current === ident) return;
    const root = positions.get(graph.root.id);
    if (root && viewport.current) { viewport.current.scrollLeft = root.x + NODE_W / 2 - viewport.current.clientWidth / 2; centeredRoot.current = ident; }
  }, [state, graph, positions, ident]);
  const node = selection?.kind === 'node' ? graph?.nodes.find(n => n.id === selection.id) : undefined;
  const edge = selection?.kind === 'edge' ? graph?.edges.find(e => e.id === selection.id) : undefined;
  const selected = node || edge;
  const source = node?.source || (edge ? (data?.nodes.find(n => n.id === edge.to && n.source.key === edge.source_key)
    || data?.nodes.find(n => n.id === edge.from && n.source.key === edge.source_key) || data?.nodes.find(n => n.source.key === edge.source_key))?.source : undefined);
  const locked = state === 'locked' || access?.locked.includes('przeplyw');
  function update(patch: Partial<Filters>) {
    if (!filters) return;
    const next = { ...filters, ...patch };
    if (next.od && next.do && next.od > next.do) { if (patch.od !== undefined) next.do = next.od; else next.od = next.do; }
    const url = new URL(window.location.href);
    const params = new URLSearchParams(flowQuery(next, narrative));
    ['kategorie', 'od', 'do', 'glebokosc', 'pokaz_niepowiazane', 'cala_historia', 'narracja'].forEach(k => { url.searchParams.delete(k); if (params.has(k)) url.searchParams.set(k, params.get(k)!); });
    window.history.pushState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
    setFilters(next);
  }
  function open(kind: 'node' | 'edge', id: string) { opener.current = document.activeElement as HTMLElement; setSelection({ kind, id }); }
  function close() { setSelection(null); requestAnimationFrame(() => opener.current?.focus({ preventScroll: true })); }
  useEffect(() => { if (selected) closeButton.current?.focus({ preventScroll: true }); }, [selection, selected]);
  useEffect(() => {
    if (!selected || !narrow || !panel.current) return;
    const changed: HTMLElement[] = [];
    let branch: HTMLElement | null = panel.current;
    while (branch && branch !== document.body) {
      for (const sibling of Array.from(branch.parentElement?.children || [])) {
        if (sibling instanceof HTMLElement && sibling !== branch && !sibling.classList.contains('px-flow__scrim') && !sibling.inert) { sibling.inert = true; changed.push(sibling); }
      }
      branch = branch.parentElement;
    }
    const overflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
    return () => { changed.forEach(el => { el.inert = false; }); document.body.style.overflow = overflow; };
  }, [!!selected, narrow]);
  useEffect(() => {
    if (!selected) return;
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); close(); }
      if (event.key === 'Tab' && window.matchMedia('(max-width: 760px)').matches) {
        const items = [...(panel.current?.querySelectorAll<HTMLElement>('button, a[href]') || [])];
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);
  });
  const dates = timelineDomain.current.dates;
  const startMatch = dates.findIndex(d => d >= (filters?.od || dates[0]));
  const startIndex = startMatch < 0 ? Math.max(0, dates.length - 1) : startMatch;
  const endIndex = dates.reduce((last, d, i) => d <= (filters?.do || dates[dates.length - 1]) ? i : last, 0);
  function timelineSelect(id: string) {
    open('node', id);
    const target = document.getElementById(`flow-node-${id}`);
    target?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'instant' });
  }
  return <main className="px px-flow">
    <Bar />
    <header className="px-flow__head">
      <div><p className="px-kicker">Powiązania według dostępnych źródeł</p><h1>Drzewo przepływu <small>Etap 1</small></h1>
        <p className="px-flow__subject" title={data?.root.label}>{data?.root.label || (ident.startsWith('osoba:') ? 'Osoba publiczna' : 'Podmiot')}</p></div>
      <a className="px-quiet" href={`/przeszlosc/${ident.startsWith('osoba:') ? 'osoba' : 'spolka'}/${encodeURIComponent(ident.replace(/^(osoba|spolka):/, ''))}`}>Wróć do {ident.startsWith('osoba:') ? 'profilu' : 'spółki'} →</a>
    </header>
    <section className="px-flow__filters" aria-label="Filtry drzewa">
      <div className="px-flow__categories">{CATEGORY_KEYS.map((key, i) => {
        const category = data?.categories.find(c => c.key === key);
        const available = category?.available ?? !['nieruchomosci', 'orzeczenia'].includes(key);
        const on = filters?.categories === null || !!filters?.categories.includes(key);
        return <button key={key} type="button" aria-pressed={available && on} aria-disabled={!available} title={available ? category?.label || CATEGORY_LABELS[i] : `${CATEGORY_LABELS[i]}: wkrótce`}
          onClick={() => { if (!available || !filters) return; const current = filters.categories ?? CATEGORY_KEYS.filter(k => data?.categories.find(c => c.key === k)?.available ?? !['nieruchomosci', 'orzeczenia'].includes(k));
            update({ categories: on ? current.filter(k => k !== key) : [...current, key] }); }}>
          {CATEGORY_LABELS[i]} <span>{available ? category?.count ?? '·' : 'wkrótce'}</span></button>;
      })}</div>
      <div className="px-flow__dates"><label>Od <input type="date" value={filters?.od || ''} max={filters?.do || undefined} onChange={e => update({ od: e.target.value })} /></label>
        <label>Do <input type="date" value={filters?.do || ''} min={filters?.od || undefined} onChange={e => update({ do: e.target.value })} /></label>
        <label className="px-flow__check"><input type="checkbox" checked={filters?.unlinked || false} onChange={e => update({ unlinked: e.target.checked })} />Pokaż niepowiązane</label>
        {ident.startsWith('osoba:') && <label className="px-flow__check" title="Domyślnie tylko rekordy z okresu pełnienia funkcji. Rekordy spoza okresu to kontekst spółki, nie dowód związku z osobą."><input type="checkbox" checked={filters?.history || false} onChange={e => update({ history: e.target.checked })} />Cała historia spółki (także poza okresem funkcji)</label>}
        <button type="button" onClick={() => update({ categories: null, od: '', do: '', unlinked: false, depth: 2, history: false })}>Wyczyść filtry</button></div>
    </section>
    <div className="px-flow__workspace">
      <section className="px-flow__graph" aria-label="Drzewo powiązań i przepływów">
        <div className="px-flow__toolbar"><span role="status">{graph ? `${graph.nodes.length} ${plural(graph.nodes.length, 'węzeł', 'węzły', 'węzłów')}` : 'Drzewo'} · {state === 'loading' && data ? 'Odświeżanie danych…' : 'kierunek wskazują strzałki'}<small>Przewiń drzewo lub wybierz Dopasuj</small></span>
          <div><button type="button" aria-label="Pomniejsz drzewo" onClick={() => setZoom(z => Math.max(.1, z / 1.25))}>−</button>
            <button type="button" onClick={() => setZoom(1)} aria-label="Przywróć skalę 100 procent">{Math.round(zoom * 100)}%</button>
            <button type="button" aria-label="Powiększ drzewo" onClick={() => setZoom(z => Math.min(2, z * 1.25))}>+</button>
            <button type="button" onClick={() => { setZoom(Math.max(.01, Math.min(1, (viewport.current?.clientWidth || 820) / layout.width, (viewport.current?.clientHeight || 580) / layout.height))); viewport.current?.scrollTo(0, 0); }}>Dopasuj</button></div></div>
        <div className="px-flow__viewport" ref={viewport} tabIndex={0} aria-label="Przewijane drzewo; Tab wybiera węzły, Enter otwiera źródło" aria-busy={state === 'loading'}>
          {state === 'loading' && !data && <div className="px-flow__message"><Loading label="Ładowanie drzewa" /></div>}
          {locked && <p className="px-flow__message">{nb('Drzewo przepływu jest w pilotażu przeszłość.today.')} <a href="/przeszlosc/pilot">Pilotaż</a></p>}
          {!locked && state === 'missing' && <p className="px-flow__message">Nie znaleziono osoby ani podmiotu. <a href="/przeszlosc?tryb=osoba">Szukaj ponownie</a></p>}
          {!locked && state === 'error' && <div className="px-flow__message" role="alert"><p>{error}</p><button type="button" onClick={() => setRetry(n => n + 1)}>Spróbuj ponownie</button></div>}
          {!locked && (state === 'ready' || state === 'loading') && graph && <>
            {graph.nodes.filter(n => n.id !== graph.root.id).length === 0 && <p className="px-flow__empty">Brak powiązań w danych, które zbieramy</p>}
            <div style={{ width: layout.width * zoom, height: layout.height * zoom }}>
              <div className="px-flow__canvas" style={{ width: layout.width, height: layout.height, transform: `scale(${zoom})` }}>
                <svg width={layout.width} height={layout.height} className="px-flow__lines" aria-hidden="true">
                  <defs><marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="12" markerHeight="12" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" /></marker></defs>
                  {graph.edges.map(e => { const a = positions.get(e.from), b = positions.get(e.to); if (!a || !b) return null;
                    const down = b.y >= a.y, x1 = a.x + NODE_W / 2, x2 = b.x + NODE_W / 2, y1 = a.y + (down ? NODE_H : 0), y2 = b.y + (down ? 0 : NODE_H);
                    const mid = (y1 + y2) / 2, d = a.y === b.y ? `M${x1},${y1} C${x1},${y1 + 90} ${x2},${y2 + 90} ${x2},${y2}` : `M${x1},${y1} C${x1},${mid} ${x2},${mid} ${x2},${y2}`;
                    const label = [e.date_from, e.date_to && e.date_to !== e.date_from ? `- ${e.date_to}` : '', e.amount !== null ? money(e.amount, e.currency) : ''].filter(Boolean).join(' · ') || e.label;
                    return <g key={e.id} data-selected={edge?.id === e.id} className="px-flow__edge" onClick={() => open('edge', e.id)}>
                      <path className="px-flow__edge-hit" d={d} /><path className="px-flow__edge-line" d={d} strokeWidth={edgeWidth(e.amount)} strokeDasharray={e.certainty === 'name_only' ? '5 5' : undefined} markerEnd="url(#flow-arrow)" />
                      <text x={(x1 + x2) / 2} y={a.y === b.y ? y1 + 65 : mid - 8} textAnchor="middle">{label}</text><title>{e.label}: {label}</title></g>;
                  })}
                </svg>
                {layout.nodes.filter(p => graph.nodes.some(n => n.id === p.node.id)).map(({ node: n, x, y }) => <button type="button" id={`flow-node-${n.id}`} key={n.id}
                  className="px-flow__node" data-kind={n.kind} data-level={n.level} data-selected={node?.id === n.id} title={n.label}
                  style={{ left: x, top: y, width: NODE_W, height: NODE_H }} aria-label={`${n.label}, ${TYPE[n.kind]}, poziom ${n.level}. Otwórz źródło`}
                  aria-pressed={node?.id === n.id} onFocus={e => { if (zoom < .4) { setZoom(1); const target = e.currentTarget; requestAnimationFrame(() => target.scrollIntoView({ block: 'nearest', inline: 'center' })); } }} onClick={() => open('node', n.id)}>
                  <span className="px-flow__symbol">{n.kind === 'grant' ? <span aria-hidden="true">zł</span> : <Icon name={ICON[n.kind]} size={22} />}</span><strong>{n.short || n.label}</strong>
                  <small>{n.certainty === 'name_only' ? 'zgodność nazwy, nie liczona' : TYPE[n.kind]}</small></button>)}
              </div>
            </div>
          </>}
        </div>
      </section>
      {selected && <button type="button" className="px-flow__scrim" tabIndex={-1} aria-label="Zamknij szczegóły" onClick={close} />}
      <aside ref={panel} className="px-flow__panel" data-open={!!selected} role={narrow && selected ? 'dialog' : undefined} aria-modal={narrow && selected ? true : undefined} aria-label="Źródło i szczegóły">
        <header><h2>{selected ? 'Źródło i szczegóły' : 'Sprawdź źródło'}</h2>{selected && <button ref={closeButton} type="button" onClick={close} aria-label="Zamknij szczegóły">×</button>}</header>
        {selected ? <><div className="px-flow__panel-body"><h3>{selected.label}</h3><dl>
          <dt>Typ</dt><dd>{node ? TYPE[node.kind] : 'Powiązanie'}</dd>
          <dt>Data</dt><dd>{node ? node.date || 'Nie podano' : [edge?.date_from, edge?.date_to].filter(Boolean).join(' - ') || 'Nie podano'}</dd>
          <dt>Kwota</dt><dd>{money(selected.amount, selected.currency)}</dd><dt>Pewność powiązania</dt><dd>{CERTAINTY[selected.certainty]}</dd>
          <dt>Źródło</dt><dd>{source?.label || edge?.source_key || 'Nie podano'}</dd><dt>Licencja</dt><dd>{source?.license || 'Brak szczegółów źródła w danych'}</dd>
          <dt>Pobrano</dt><dd title={source?.retrieved_at || undefined}>{retrieved(source?.retrieved_at)}</dd>
          <dt>Adres źródła</dt><dd>{safeHref(source?.url) ? <a href={safeHref(source?.url)} target="_blank" rel="noopener noreferrer">{source?.url}</a> : 'Nie podano'}</dd>
        </dl></div><footer><Sprostowanie recordId={selected.id} label={selected.label} className="px-flow__fix" />{safeHref(node?.url || source?.url) ? <a href={safeHref(node?.url || source?.url)} target="_blank" rel="noopener noreferrer">Otwórz oryginał ↗</a> : <span>Brak odnośnika do oryginału</span>}</footer></>
          : <p>{nb('Wybierz węzeł lub linię, aby sprawdzić datę, kwotę i podstawę powiązania. Sama linia nie oznacza przepływu pieniędzy.')}</p>}
      </aside>
    </div>
    <section className="px-flow__timeline" aria-label="Oś czasu zmian">
      <h2>Oś czasu <span>{filters?.od || dates[0] || 'Od'} - {filters?.do || dates[dates.length - 1] || 'Do'}</span></h2>
      <div className="px-flow__sliders"><label>Od<input type="range" aria-label="Początek zakresu dat" aria-valuetext={dates[startIndex] || 'Brak dat'} min={0} max={Math.max(0, dates.length - 1)} value={startIndex} disabled={dates.length < 2}
        onChange={e => update({ od: dates[Number(e.target.value)], do: dates[Math.max(Number(e.target.value), endIndex)] })} /></label>
        <label>Do<input type="range" aria-label="Koniec zakresu dat" aria-valuetext={dates[endIndex] || 'Brak dat'} min={0} max={Math.max(0, dates.length - 1)} value={endIndex} disabled={dates.length < 2}
          onChange={e => update({ do: dates[Number(e.target.value)], od: dates[Math.min(Number(e.target.value), startIndex)] })} /></label></div>
      <div className="px-flow__events">{!locked && graph?.timeline.map((t, i) => <button key={`${t.node_id}-${t.date}-${i}`} type="button" data-category={filterCategory(t.category)} aria-pressed={node?.id === t.node_id}
        title={`${t.date}: ${t.label}`} onClick={() => timelineSelect(t.node_id)}><i aria-hidden="true" />{t.date}<span>{t.label}</span></button>)}
        {!graph?.timeline.length && <p>Brak zdarzeń w wybranym zakresie.</p>}</div>
    </section>
    <div className="px-flow__signals" aria-label="Sygnały" />
    {!locked && graph && <section className="px-flow__below" aria-label="Informacje o danych">
      {graph.limits.truncated && <p role="status">Pokazujemy część danych: maksymalnie {Math.min(300, graph.limits.max_nodes)} węzłów. Zawęź kategorię lub daty, aby zobaczyć więcej szczegółów.</p>}
      {graph.limits.grouped.map(group => <div key={group.id} className="px-flow__group"><button type="button" aria-expanded={expanded.includes(group.id)} onClick={() => setExpanded(old => old.includes(group.id) ? old.filter(id => id !== group.id) : [...old, group.id])}>{group.label} · {group.count} · {expanded.includes(group.id) ? 'Zwiń' : 'Rozwiń'}</button>
        {expanded.includes(group.id) && <div><p>Ta grupa obejmuje {group.count} rekordów. Pełna lista nie jest dostępna w tym widoku. Zawężenie może odsłonić kolejne powiązania.</p>
          <button type="button" onClick={() => update({ categories: [filterCategory(group.category) as Category], depth: 3 })}>Pokaż kategorię do poziomu 3</button></div>}</div>)}
      {zoom < .4 && <p>Widok całości. Wybierz węzeł klawiszem Tab, aby go powiększyć, lub skorzystaj z listy poniżej.</p>}
      <details className="px-flow__list" open={zoom < .4 ? true : undefined}><summary>Lista tekstowa węzłów i powiązań</summary><ol>{layout.nodes.filter(p => graph.nodes.some(n => n.id === p.node.id)).map(({ node: n }) => <li key={n.id}>
        <button type="button" onClick={() => open('node', n.id)}>Poziom {n.level}: {n.label} · {TYPE[n.kind]}</button>
        <ul>{graph.edges.filter(e => e.from === n.id).map(e => <li key={e.id}><button type="button" onClick={() => open('edge', e.id)}>{e.label} → {graph.nodes.find(v => v.id === e.to)?.label} · {CERTAINTY[e.certainty]}</button></li>)}</ul>
      </li>)}</ol></details>
      {graph.legal.notes.map((note, i) => <p className="px-note" key={i}>{nb(note)}</p>)}
    </section>}
    <Foot />
  </main>;
}
