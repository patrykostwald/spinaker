"use client";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { nb, plural, reduced } from './ui';
import './siec.css';
import {
  groupEdges, isContext, netTotal, safeUrl, visibleGroups,
  type NetGroup, type NetResponse,
} from './glosowania-lista';

/**
 * Sieć powiązań w aktach osoby (przeszłość.today, port v3, 13.10.2026): GET /api/przeszlosc/osoba/<ident>/powiazania/
 * (gust/spin/port/API-v3.md, sekcja 4). Osoba po lewej, grupy węzłów po prawej w stałych odstępach, przewody SVG liczone z DOM.
 * Linia ciągła = udokumentowane (współwystępowanie, głosowania), kreskowana = kontekst KRS (nie dowód związku). Neutralne linie,
 * akcent sepii tylko na podświetlonej ścieżce. Na telefonie osoba nad listą. Przewody to rysunek (aria-hidden); pełna lista tekstowa
 * z wagami i dowodami jest w <details>. Ładowanie dopiero po zbliżeniu sekcji do okna; reduced-motion = stan końcowy bez rysowania.
 */
type Status = 'wait' | 'loading' | 'ok' | 'locked' | 'none' | 'error';
export type NetAvailability = 'ok' | 'none';
type Wires = { w: number; h: number; x0: number; y0: number; above: boolean; paths: { key: string; d: string; ctx: boolean }[] };
const NO_WIRES: Wires = { w: 0, h: 0, x0: 0, y0: 0, above: false, paths: [] };

export function Siec({ ident, onAvailability }: { ident: string | number; onAvailability?: (a: NetAvailability) => void }) {
  const [status, setStatus] = useState<Status>('wait');
  const [net, setNet] = useState<NetResponse | null>(null);
  const [all, setAll] = useState(false);
  const [lit, setLit] = useState<string | null>(null);
  const [wires, setWires] = useState<Wires>(NO_WIRES);
  const [drawn, setDrawn] = useState(false);
  const host = useRef<HTMLElement>(null);
  const fig = useRef<HTMLDivElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const wiresBox = useRef<HTMLDivElement>(null);
  const rows = useRef(new Map<string, HTMLElement>());

  const load = useCallback(async () => {
    setStatus('loading');
    try {
      const r = await fetch(`/api/przeszlosc/osoba/${encodeURIComponent(String(ident))}/powiazania/`);
      if (r.status === 404) { setStatus('none'); onAvailability?.('none'); return; }
      if (r.status === 403) { setStatus('locked'); onAvailability?.('ok'); return; }
      if (!r.ok) throw new Error(String(r.status));
      const d: NetResponse = await r.json();
      setNet(d); setStatus('ok'); onAvailability?.('ok');
    } catch { setStatus('error'); }
  }, [ident, onAvailability]);

  // leniwie: pobranie dopiero, gdy sekcja zbliży się do okna (bez IntersectionObserver - od razu)
  useEffect(() => {
    const el = host.current;
    if (!el || status !== 'wait') return;
    if (!('IntersectionObserver' in window)) { void load(); return; }
    const io = new IntersectionObserver(en => { if (en.some(e => e.isIntersecting)) { io.disconnect(); void load(); } }, { rootMargin: '500px 0px' });
    io.observe(el);
    return () => io.disconnect();
  }, [status, load]);

  const groups = useMemo<NetGroup[]>(() => net ? groupEdges(net) : [], [net]);
  const total = netTotal(groups);
  const shown = useMemo(() => visibleGroups(groups, all), [groups, all]);
  const shownCount = netTotal(shown);
  const rootNode = net?.nodes.find(n => n.root);

  // przewody liczone z położenia wierszy (DOM), przy zmianie rozmiaru, czcionek i rozwinięcia
  const measure = useCallback(() => {
    const W = wiresBox.current?.getBoundingClientRect(), S = root.current?.getBoundingClientRect();
    if (!W || !S || !W.width) return;
    const above = S.bottom <= W.top + 1;
    const x0 = above ? 3 : 0;
    const y0 = above ? 0 : S.top + S.height / 2 - W.top;
    const paths = [...rows.current.entries()].filter(([, el]) => el.isConnected).map(([key, el]) => {
      const R = el.getBoundingClientRect(), y = R.top + R.height / 2 - W.top, c = W.width * .55;
      const d = above ? `M${x0} 0 C${x0} ${y} ${x0} ${y} ${W.width} ${y}` : `M0 ${y0} C${c} ${y0} ${W.width - c} ${y} ${W.width} ${y}`;
      return { key, d, ctx: el.dataset.ctx === '1' };
    });
    setWires({ w: W.width, h: W.height, x0, y0, above, paths });
  }, []);
  useLayoutEffect(() => {
    if (status !== 'ok') return;
    measure();
    const ro = 'ResizeObserver' in window && fig.current ? new ResizeObserver(() => measure()) : null;
    if (ro && fig.current) ro.observe(fig.current);
    window.addEventListener('resize', measure);
    void document.fonts?.ready.then(measure);
    return () => { ro?.disconnect(); window.removeEventListener('resize', measure); };
  }, [status, shown, measure]);
  // rysowanie przewodów raz po pomiarze; reduced-motion = od razu stan końcowy
  useEffect(() => {
    if (!wires.paths.length || drawn) return;
    if (reduced()) { setDrawn(true); return; }
    const id = requestAnimationFrame(() => setDrawn(true));
    return () => cancelAnimationFrame(id);
  }, [wires.paths.length, drawn]);

  if (status === 'none') return null;
  const note = net?.note;
  const cov = net?.coverage;
  const covText = cov ? [
    `${cov.people} ${plural(cov.people, 'osoba', 'osoby', 'osób')} ze wspólnymi dokumentami lub tematami`,
    `${cov.krs} ${plural(cov.krs, 'osoba', 'osoby', 'osób')} z tych samych podmiotów w KRS`,
    cov.votes_available ? `zgodność głosów z ostatnich ${cov.votes_window} głosowań` : 'zgodność głosów: brak w naszych danych (dotyczy posłów z oficjalnym identyfikatorem Sejmu)',
  ].join(' · ') : '';

  const hot = (key: string | null) => ({
    onMouseEnter: () => setLit(key), onMouseLeave: () => setLit(null),
    onFocus: () => setLit(key), onBlur: (e: React.FocusEvent) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setLit(null); },
  });

  return <section className="px-sec pt-net" id="pp-siec" aria-labelledby="pp-siec-h" ref={host} aria-busy={status === 'loading' || undefined}>
    <div className="px-dn__head"><h2 id="pp-siec-h" className="px-h2">Sieć powiązań</h2>
      {note ? <p className="px-note">{nb(note)}</p> : <p className="px-note">{nb('Współwystępowanie oznacza wspólny dokument albo temat w źródle; nie jest dowodem współpracy. Każda pozycja prowadzi do źródła.')}</p>}</div>

    {(status === 'wait' || status === 'loading') && <p className="pt-net__wait" role="status">Wczytuję powiązania<span aria-hidden="true">_</span></p>}
    {status === 'locked' && <p className="px-note">{nb('Sieć powiązań jest w pilotażu przeszłość.today.')} <a href="/przeszlosc/pilot">Pilotaż</a></p>}
    {status === 'error' && <p className="px-note" role="alert">{nb('Nie udało się pobrać powiązań.')} <button type="button" className="px-quiet" onClick={() => void load()}>Spróbuj ponownie</button></p>}

    {status === 'ok' && net && <>
      {groups.length === 0
        ? <p className="px-note">{nb(`Brak w naszych danych: powiązań tej osoby (zakres: wspólne dokumenty i tematy, podmioty KRS, zgodność głosów; stan z bieżącego profilu).`)}</p>
        : <>
          <div className="pt-net__fig" ref={fig} data-lit={lit ? 1 : undefined} data-in={drawn ? 1 : undefined} data-above={wires.above ? 1 : undefined}>
            <div className="pt-net__root" ref={root}>
              <b>{rootNode?.label ?? net.person.name}</b>
              <span>{rootNode?.role || net.person.role}</span>
            </div>
            <div className="pt-net__wires" ref={wiresBox} aria-hidden="true">
              <svg viewBox={`0 0 ${wires.w || 1} ${wires.h || 1}`} focusable="false">
                {wires.paths.length > 0 && <circle cx={wires.x0} cy={wires.y0} r="3" />}
                {wires.paths.map(p => <path key={p.key} d={p.d} data-ctx={p.ctx ? 1 : undefined} data-on={lit === p.key ? 1 : undefined} />)}
              </svg>
            </div>
            <div className="pt-net__nodes">
              {shown.map(g => <div key={g.kind} className="pt-net__group">
                <h3 className="pt-net__gh">{g.title}<small>{groups.find(x => x.kind === g.kind)?.rows.length}</small></h3>
                <ol>{g.rows.map(r => <li key={r.key} data-ctx={isContext(r.edge.kind) ? 1 : undefined} data-on={lit === r.key ? 1 : undefined}
                  ref={el => { if (el) rows.current.set(r.key, el); else rows.current.delete(r.key); }}
                  onClick={() => setLit(l => l === r.key ? null : r.key)} {...hot(r.key)}>
                  {r.href ? <a className="pt-net__nm" href={r.href}><b>{r.node.label}</b>{r.node.club && <i>{r.node.club}</i>}</a>
                    : <span className="pt-net__nm"><b>{r.node.label}</b>{r.node.club && <i>{r.node.club}</i>}</span>}
                  <em>{r.weightText}</em>
                  <span className="pt-net__why">{r.labelText}</span>
                </li>)}</ol>
              </div>)}
            </div>
          </div>
          <div className="pt-net__bar">
            <p className="pt-net__leg">
              <span><i aria-hidden="true" />udokumentowane w źródle</span>
              <span><i aria-hidden="true" data-ctx="1" />kontekst KRS, nie dowód związku</span>
            </p>
            {total > shownCount || all ? <button type="button" className="px-more" aria-expanded={all} onClick={() => setAll(!all)}>
              {all ? 'Pokaż mniej' : `Pokaż wszystkie powiązania (${total})`}</button> : null}
          </div>
          {covText && <p className="px-note pt-net__cov">Zakres: {covText}.</p>}

          <details className="pt-net__txt">
            <summary>Lista tekstowa z wagami i dowodami ({total})</summary>
            <div className="pt-net__list">{groups.map(g => <section key={g.kind} aria-label={g.title}>
              <h3>{g.title}</h3>
              <ul>{g.rows.map(r => <li key={r.key} {...hot(r.key)}>
                <p>{r.href ? <a href={r.href}>{r.node.label}</a> : <b>{r.node.label}</b>}
                  {r.node.club ? `, ${r.node.club}` : ''}{r.node.role ? ` (${r.node.role})` : ''}: {r.edge.label}, waga {r.weightText}
                  {isContext(r.edge.kind) ? ' (kontekst, nie dowód związku)' : ''}</p>
                {r.edge.evidence.length > 0 ? <ul className="pt-net__ev">{r.edge.evidence.map((e, i) => {
                  const href = safeUrl(e.url);
                  return <li key={i}><span>{e.kind}</span>{href ? <a href={href} target={href.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">{e.label}</a> : e.label}</li>;
                })}</ul> : <p className="pt-net__noev">Dowody: brak w naszych danych dla tego powiązania (zakres: bieżący profil osoby).</p>}
              </li>)}</ul>
            </section>)}</div>
          </details>
        </>}
    </>}
  </section>;
}
