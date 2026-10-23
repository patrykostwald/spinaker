"use client";
import { useEffect, useMemo, useRef, useState } from 'react';
import { day, nb } from './ui';
import { money } from './DrzewoPieniedzy';
import './przeplywy.css';

/**
 * Przepływy pieniędzy v1 (sprint 23.10): skąd do kogo płyną pieniądze publiczne. GET /api/przeszlosc/przeplywy/<osoba:slug|spolka:KRS>/
 * Cztery równe boksy liczb (wartość wygranych zamówień z ogłoszeń, dotacje i 1,5%, wartość udzielonych zamówień, pozycje), wykres sankey (płatnicy po lewej, odbiorcy po prawej, jedna waluta)
 * i tabela: data, od, do, kwota, rodzaj, źródło. Kwoty do weryfikacji w tabeli z etykietą, poza sumami i wykresem.
 * Laws of UX: Common Region (jeden boks na funkcję), Similarity (te same boksy liczb), Von Restorff (akcent tylko na wstędze
 * pod kursorem), Tesler (sumy i podział walut liczy system). Telefon: wykres węższy (5 + 5 węzłów), tabela jako lista.
 */
type Party = { label: string; nip: string; url: string };
type Sum = { currency: string; total: number; count: number };
type Flow = {
  id: string; kind: string; date: string | null; from: Party; to: Party; amount: number | null; currency: string;
  amount_suspect: boolean; amount_shared?: boolean; title: string; source: { key: string; label: string; license: string; url: string };
  matched_by: string; via?: { name: string; url: string }; outside_tenure?: boolean; attribution?: string;
};
type SNode = { id: number; label: string; side: 'from' | 'to'; total: number };
type SLink = { source: number; target: number; value: number };
export type Flows = {
  subject: { kind: 'person' | 'organisation'; name: string; url: string; organisations?: { name: string; url: string; nip_missing: boolean }[]; identifiers_missing?: boolean };
  count: number; truncated: boolean; results: Flow[]; sums: { all: Sum[]; in: Sum[]; out: Sum[]; in_contracts?: Sum[]; in_grants?: Sum[] }; suspect_count: number; shared_count?: number;
  kinds: { kind: string; label: string; count: number }[];
  sankey: { currency: string | null; nodes: SNode[]; links: SLink[]; other_currencies: string[] };
  sources: { key: string; label: string; license: string }[]; note: string; generated_at: string;
  outside_tenure?: number; whole_history?: boolean; empty_reason?: string;
};

const SRC: Record<string, string> = { ted: 'TED', bzp: 'BZP', fts: 'FTS', niw: 'NIW-CRSO', mf_opp: 'MF, wykaz OPP' };
const KIND: Record<string, string> = { ted_in: 'zamówienie', ted_out: 'zamówienie', bzp: 'ogłoszenie BZP', fts: 'dotacja UE', niw: 'dotacja krajowa', mf_opp: '1,5% podatku' };
const PAGE = 25;
/** Data w jednej linii (zasada 4): 03.10.2025; sam rok bez zmian. */
const short = (d: string) => d.length === 10 ? `${d.slice(8, 10)}.${d.slice(5, 7)}.${d.slice(0, 4)}` : d;
const sumText = (s: Sum[]) => s.length ? s.map(x => money(x.total, x.currency)).join(' + ') : '-';
/** Odmiana „pozycja”: 1 pozycja, 2-4 pozycje, 5+ pozycji (12-14 pozycji). */
export const pozycji = (n: number) => `${n} ${n === 1 ? 'pozycja' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'pozycje' : 'pozycji'}`;
const outside = (suspect: number, shared: number) => !suspect && !shared ? 'wszystkie kwoty w sumach'
  : `poza sumami: ${[suspect && `${suspect} do weryfikacji`, shared && `${shared} kilku wykonawców`].filter(Boolean).join(', ')}`;

function NumBox({ label, title, sums, what }: { label: string; title: string; sums: Sum[]; what: string }) {
  const n = sums.reduce((s, x) => s + x.count, 0);
  return <div className="pt-pf__num-box" title={title}><span className="pt-pf__k">{label}</span><strong>{sumText(sums)}</strong>
    <small>{nb(n ? `${what}, ${pozycji(n)}` : 'brak pozycji z kwotą')}</small></div>;
}

function useNarrow(query = '(max-width: 760px)') {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => { const m = window.matchMedia(query); const sync = () => setNarrow(m.matches); sync(); m.addEventListener('change', sync); return () => m.removeEventListener('change', sync); }, [query]);
  return narrow;
}

const cut = (text: string, max: number) => text.length > max ? `${text.slice(0, max - 1)}…` : text;

function Sankey({ data, narrow, self }: { data: Flows['sankey']; narrow: boolean; self: Set<string> }) {
  const [lit, setLit] = useState<number | null>(null);
  const layout = useMemo(() => {
    const keep = narrow ? 5 : 8;
    // telefon: mniej węzłów - reszta w „pozostali” po tej samej stronie (suma wstęg się nie zmienia)
    const top = (side: 'from' | 'to') => new Set(data.nodes.filter(n => n.side === side).sort((a, b) => b.total - a.total).slice(0, keep).map(n => n.id));
    const keepL = top('from'), keepR = top('to');
    const label = (n: SNode) => (n.side === 'from' ? keepL : keepR).has(n.id) ? n.label : n.side === 'from' ? 'pozostali płatnicy' : 'pozostali odbiorcy';
    const pairs = new Map<string, number>();
    data.links.forEach(l => { const k = `${label(data.nodes[l.source])}\u0000${label(data.nodes[l.target])}`; pairs.set(k, (pairs.get(k) ?? 0) + l.value); });
    const totals = (i: 0 | 1) => { const m = new Map<string, number>(); pairs.forEach((v, k) => { const n = k.split('\u0000')[i]; m.set(n, (m.get(n) ?? 0) + v); }); return [...m.entries()].sort((a, b) => (a[0].startsWith('pozostali') ? 1 : 0) - (b[0].startsWith('pozostali') ? 1 : 0) || b[1] - a[1]); };
    const L = totals(0), R = totals(1);
    const W = narrow ? 320 : 960, gap = narrow ? 6 : 12, rowMin = narrow ? 14 : 30, bar = 10;
    const total = L.reduce((s, [, v]) => s + v, 0) || 1;
    const rows = Math.max(L.length, R.length);
    const H = Math.max(160, rows * (rowMin + gap) + 40);
    const scale = (H - gap * (rows + 1)) / total;
    const place = (list: [string, number][]) => { let y = gap; return new Map(list.map(([n, v]) => { const h = Math.max(4, v * scale); const r = { y, h, v }; y += h + gap; return [n, r]; })); };
    const pl = place(L), pr = place(R);
    const offL = new Map<string, number>(), offR = new Map<string, number>();
    const ribbons = [...pairs.entries()].sort((a, b) => b[1] - a[1]).map(([k, v], i) => {
      const [a, b] = k.split('\u0000'); const A = pl.get(a)!, B = pr.get(b)!;
      const h = Math.max(1.5, v * scale);
      const y1 = A.y + (offL.get(a) ?? 0) + h / 2, y2 = B.y + (offR.get(b) ?? 0) + h / 2;
      offL.set(a, (offL.get(a) ?? 0) + h); offR.set(b, (offR.get(b) ?? 0) + h);
      const x1 = bar, x2 = W - bar, mx = (x1 + x2) / 2;
      return { i, a, b, v, h, d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}` };
    });
    return { W, H, bar, pl, pr, ribbons, chars: narrow ? 17 : 44 };
  }, [data, narrow]);
  const { W, H, bar, pl, pr, ribbons, chars } = layout;
  const font = narrow ? 13 : 13;
  return <figure className="pt-pf__chart" aria-label={`Wykres przepływów w walucie ${data.currency}: płatnicy po lewej, odbiorcy po prawej`}>
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-hidden="true" preserveAspectRatio="xMidYMin meet">
      {ribbons.map(r => <path key={r.i} d={r.d} className={`pt-pf__ribbon${lit === r.i ? ' is-lit' : ''}`} strokeWidth={r.h}
        onMouseEnter={() => setLit(r.i)} onMouseLeave={() => setLit(null)}><title>{`${r.a} → ${r.b}: ${money(r.v, data.currency ?? 'PLN')}`}</title></path>)}
      {[...pl.entries()].map(([n, p]) => <g key={`l${n}`}>
        <rect x={0} y={p.y} width={bar} height={p.h} className={`pt-pf__bar${self.has(n) ? ' is-self' : ''}`} />
        {!narrow && <text x={bar + 6} y={p.y + Math.min(p.h / 2, 14) + 4} fontSize={font} className="pt-pf__label">{cut(n, chars)}<tspan className="pt-pf__num">{` ${money(p.v, data.currency ?? 'PLN')}`}</tspan></text>}
      </g>)}
      {[...pr.entries()].map(([n, p]) => <g key={`r${n}`}>
        <rect x={W - bar} y={p.y} width={bar} height={p.h} className={`pt-pf__bar${self.has(n) ? ' is-self' : ''}`} />
        {!narrow && <text x={W - bar - 6} y={p.y + Math.min(p.h / 2, 14) + 4} fontSize={font} textAnchor="end" className="pt-pf__label">{cut(n, chars)}<tspan className="pt-pf__num">{` ${money(p.v, data.currency ?? 'PLN')}`}</tspan></text>}
      </g>)}
    </svg>
    {narrow && <div className="pt-pf__legend">{([['Płatnicy', pl], ['Odbiorcy', pr]] as const).map(([t, m]) => <div key={t}>
      <span className="pt-pf__k">{t}</span>
      <ol>{[...m.entries()].map(([n, p]) => <li key={n}><span>{n}</span><span className="pt-pf__amt">{money(p.v, data.currency ?? 'PLN')}</span></li>)}</ol>
    </div>)}</div>}
    <figcaption className="px-note">{nb(`Wyróżniony słupek to badany podmiot. Szczegóły każdej wstęgi są w tabeli poniżej. Wykres w walucie ${data.currency === 'EUR' ? 'euro' : 'zł'}; płatnicy po lewej, odbiorcy po prawej, szerokość wstęgi = suma kwot.`)}
      {data.other_currencies.length ? nb(` Pozycje w innych walutach (${data.other_currencies.join(', ')}) są tylko w tabeli.`) : ''}</figcaption>
  </figure>;
}

function PartyLink({ p }: { p: Party }) {
  return p.url ? <a href={p.url}>{p.label}</a> : <span>{p.label}</span>;
}

export function Przeplywy({ ident, headingId = 'pt-pf-h' }: { ident: string; headingId?: string }) {
  const [data, setData] = useState<Flows | null>(null);
  const [state, setState] = useState<'wait' | 'loading' | 'ok' | 'none' | 'locked' | 'error'>('wait');
  const [whole, setWhole] = useState(false);
  const [page, setPage] = useState(1);
  const [kind, setKind] = useState('');
  const host = useRef<HTMLElement>(null);
  const narrow = useNarrow();

  useEffect(() => {
    const el = host.current; if (!el) return;
    const go = () => setState(s => s === 'wait' ? 'loading' : s);
    if (!('IntersectionObserver' in window)) { go(); return; }
    const io = new IntersectionObserver(en => { if (en.some(e => e.isIntersecting)) { io.disconnect(); go(); } }, { rootMargin: '500px 0px' });
    io.observe(el); return () => io.disconnect();
  }, []);
  useEffect(() => {
    if (state !== 'loading') return;
    fetch(`/api/przeszlosc/przeplywy/${encodeURIComponent(ident)}/${whole ? '?cala_historia=1' : ''}`).then(async r => {
      if (r.status === 404) { setState('none'); return; }
      if (r.status === 403) { setState('locked'); return; }
      if (!r.ok) throw new Error(String(r.status));
      setData(await r.json()); setState('ok'); setPage(1);
    }).catch(() => setState('error'));
  }, [state, ident, whole]);

  const rows = useMemo(() => (data?.results ?? []).filter(r => !kind || KIND[r.kind] === kind), [data, kind]);
  const kinds = useMemo(() => [...new Set((data?.results ?? []).map(r => KIND[r.kind]))], [data]);
  const shown = rows.slice(0, page * (narrow ? 10 : PAGE));
  const person = data?.subject.kind === 'person';
  // węzeł badanego podmiotu (albo podmiotów osoby) - jedyny akcent na wykresie (Von Restorff)
  const selfNames = useMemo(() => new Set(data ? (person ? (data.subject.organisations ?? []).map(o => o.name) : [data.subject.name]) : []), [data, person]);
  const vias = useMemo(() => new Set((data?.results ?? []).map(r => r.via?.name).filter(Boolean)), [data]);

  return <section className="px-card pt-pf" id="pp-przeplywy" ref={host} aria-labelledby={headingId}>
    <div className="pt-pf__head">
      <h2 id={headingId} className="px-h3">Przepływy pieniędzy</h2>
      <span className="pt-pf__tag">BETA</span>
    </div>
    <p className="px-note pt-pf__lead">{nb('Skąd i do kogo płyną pieniądze publiczne: zamówienia, dotacje i 1,5% podatku, z datą, kwotą i źródłem każdej pozycji.')}</p>
    {(state === 'wait' || state === 'loading') && <p className="px-note" role="status">Ładowanie przepływów…</p>}
    {state === 'none' && <p className="px-note">{nb('Brak w naszych danych: nie mamy tej osoby lub podmiotu.')}</p>}
    {state === 'locked' && <p className="px-note">{nb('Przepływy pieniędzy są w pilotażu przeszłość.today.')} <a href="/przeszlosc/pilot">Pilotaż</a></p>}
    {state === 'error' && <p className="px-note" role="alert">Nie udało się pobrać przepływów. <button type="button" className="pt-pf__btn" onClick={() => setState('loading')}>Spróbuj ponownie</button></p>}
    {data && state === 'ok' && <>
      <div className="pt-pf__nums">
        <NumBox label="Wygrane zamówienia" title="Wartość z ogłoszeń TED o udzieleniu zamówienia, nie kwota zapłacona" sums={data.sums.in_contracts ?? []} what="wartość z ogłoszeń" />
        <NumBox label="Dotacje i 1,5% podatku" title="Dotacje UE (FTS), krajowe (NIW-CRSO) i 1,5% podatku" sums={data.sums.in_grants ?? []} what="kwoty przyznane" />
        <NumBox label="Udzielone zamówienia" title="Podmiot jako zamawiający: wartość z ogłoszeń TED" sums={data.sums.out} what="wartość z ogłoszeń" />
        <div className="pt-pf__num-box"><span className="pt-pf__k">Pozycje</span><strong>{data.count}</strong><small>{nb(outside(data.suspect_count, data.shared_count ?? 0))}</small></div>
      </div>
      {person && <div className="pt-pf__opts">
        <label className="pt-pf__check"><input type="checkbox" checked={whole} onChange={e => { setWhole(e.target.checked); setState('loading'); }} /> {nb('Pokaż też spoza okresu funkcji')}</label>
        {vias.size === 1 ? <small className="px-note">{nb(`Wszystkie pozycje przez: ${[...vias][0]}.`)}</small> : null}
        {!whole && data.outside_tenure ? <small className="px-note">{nb(`Ukryte: ${data.outside_tenure} pozycji spoza okresu funkcji w KRS.`)}</small> : null}
      </div>}
      {data.count === 0 ? <p className="px-note pt-pf__empty">{nb(data.empty_reason ?? (data.subject.identifiers_missing
        ? 'Brak przepływów w naszych danych. Podmiot nie ma jeszcze NIP z odpisu KRS - uzupełniamy go w nocnej kolejce KRS.'
        : 'Brak przepływów w naszych danych: zamówień TED i BZP, dotacji FTS i NIW-CRSO ani 1,5% podatku po identyfikatorach tego podmiotu.'))}</p>
      : <>
        {data.sankey.nodes.length > 0 && <Sankey data={data.sankey} narrow={narrow} self={selfNames} />}
        <div className="pt-pf__filters" role="group" aria-label="Rodzaj pozycji">
          <button type="button" className={`pt-pf__chip${!kind ? ' is-on' : ''}`} aria-pressed={!kind} onClick={() => { setKind(''); setPage(1); }}>{`Wszystkie (${data.count})`}</button>
          {kinds.map(k => <button key={k} type="button" className={`pt-pf__chip${kind === k ? ' is-on' : ''}`} aria-pressed={kind === k} onClick={() => { setKind(k); setPage(1); }}>{`${k} (${data.results.filter(r => KIND[r.kind] === k).length})`}</button>)}
        </div>
        <div className="pt-pf__table" role="table" aria-label="Przepływy pieniędzy">
          <div className="pt-pf__row pt-pf__row--head" role="row">
            <span role="columnheader">Data</span><span role="columnheader">Od</span><span role="columnheader">Do</span>
            <span role="columnheader">Kwota</span><span role="columnheader">Rodzaj i źródło</span>
          </div>
          {shown.map(r => <div key={r.id} className="pt-pf__row" role="row">
            <span role="cell" className="pt-pf__date">{r.date ? short(r.date) : 'bez daty'}</span>
            <span role="cell" className="pt-pf__from"><span className="pt-pf__mob">od </span><PartyLink p={r.from} /></span>
            <span role="cell" className="pt-pf__to"><span className="pt-pf__mob">do </span><PartyLink p={r.to} />{r.via && person && vias.size > 1 ? <small>{nb(`przez: ${r.via.name}`)}</small> : null}</span>
            <span role="cell" className="pt-pf__amt">{money(r.amount, r.currency)}</span>
            <span role="cell" className="pt-pf__src">{r.amount_suspect ? <span className="pt-pf__tag pt-pf__tag--warn">do weryfikacji</span> : null}{r.amount_shared ? <span className="pt-pf__tag pt-pf__tag--warn" title="Kwota całego ogłoszenia z kilkoma wykonawcami - poza sumami">kilku wykonawców</span> : null}{KIND[r.kind]}{r.outside_tenure ? ', poza okresem funkcji' : ''} · <a href={r.source.url} target="_blank" rel="noopener noreferrer" title={`${r.source.label} (${r.source.license}); łączone po ${r.matched_by}`}>{SRC[r.source.key] ?? r.source.label}</a>
              {r.title ? <small title={r.title}>{cut(r.title, 90)}</small> : null}</span>
          </div>)}
        </div>
        {rows.length > shown.length && <button type="button" className="pt-pf__btn pt-pf__more" onClick={() => setPage(p => p + 1)}>{`Pokaż kolejne (${rows.length - shown.length})`}</button>}
        {data.truncated && <p className="px-note">{nb(`Pokazujemy 500 najnowszych z ${data.count} pozycji; sumy liczone ze wszystkich.`)}</p>}
      </>}
      <p className="px-note pt-pf__foot">{nb(data.note)} {nb(`Stan na ${day(data.generated_at.slice(0, 10))}.`)}</p>
    </>}
  </section>;
}
