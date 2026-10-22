'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { PETLE_FIXTURE } from './petleFixture';
import type { Loop, LoopCategory, LoopState, LoopsSnapshot } from './petleFixture';

export type { Loop, LoopCategory, LoopState, LoopsSnapshot } from './petleFixture';

// Pętle jako koła zębate (właściciel 6.10): kręci się = zdrowa, zwalnia = uwaga, stoi = problem, szara = uśpiona.
const STATE: Record<LoopState, string> = { ok: 'Działa', warn: 'Zwalnia', bad: 'Stoi', idle: 'Uśpiona' };
const SUMMARY: Record<LoopState, string> = { ok: 'działa', warn: 'zwalnia', bad: 'stoi', idle: 'uśpione' };
const SEVERITY: Record<LoopState, number> = { bad: 0, warn: 1, ok: 2, idle: 3 };
const STATES: LoopState[] = ['bad', 'warn', 'ok', 'idle'];
const COLS = 3;

// Zarys koła: 10 zębów (trapezy), otwór w piaście przez evenodd.
const TEETH = 10;
const GEAR = (() => {
  const R = 47, r = 38, hole = 12, pitch = (2 * Math.PI) / TEETH, base = pitch * 0.56, top = pitch * 0.3;
  const pt = (rad: number, a: number) => `${(rad * Math.sin(a)).toFixed(2)} ${(-rad * Math.cos(a)).toFixed(2)}`;
  let d = `M${pt(r, -pitch / 2)}`;
  for (let i = 0; i < TEETH; i++) {
    const c = i * pitch;
    d += ` A${r} ${r} 0 0 1 ${pt(r, c - base / 2)} L${pt(R, c - top / 2)} A${R} ${R} 0 0 1 ${pt(R, c + top / 2)} L${pt(r, c + base / 2)} A${r} ${r} 0 0 1 ${pt(r, c + pitch / 2)}`;
  }
  return `${d} Z M${hole} 0 A${hole} ${hole} 0 1 0 ${-hole} 0 A${hole} ${hole} 0 1 0 ${hole} 0 Z`;
})();
// Znak stanu w piaście (nie obraca się; przy ograniczonym ruchu niesie stan razem z kolorem i podpisem).
const GLYPH: Record<LoopState, string> = { ok: 'M-5 0.5l3.2 3.2L5-3.5', warn: 'M0-5.5v6.2M0 4.6v0.4', bad: 'M-4-4l8 8M4-4l-8 8', idle: 'M-2.6-4.5v9M2.6-4.5v9' };

function Gear({ state, reverse, phase }: { state: LoopState; reverse: boolean; phase: boolean }) {
  return <svg className="sc-petle__gear" viewBox="-50 -50 100 100" aria-hidden="true" data-reverse={reverse || undefined}>
    <g className="sc-petle__spin"><g transform={phase ? `rotate(${180 / TEETH})` : undefined}>
      <path className="sc-petle__body" d={GEAR} fillRule="evenodd" />
      <circle className="sc-petle__ring" r="25" />
      {[0, 60, 120, 180, 240, 300].map(a => <circle key={a} className="sc-petle__bolt" r="2.6" cx={18 * Math.sin(a * Math.PI / 180)} cy={-18 * Math.cos(a * Math.PI / 180)} />)}
    </g></g>
    <path className="sc-petle__glyph" d={GLYPH[state]} />
  </svg>;
}

const zone = { timeZone: 'Europe/Warsaw' } as const;
const when = (value: string | null) => {
  if (!value || Number.isNaN(Date.parse(value))) return 'nigdy';
  const date = new Date(value);
  const day = (d: Date) => d.toLocaleDateString('pl-PL', zone);
  const hour = date.toLocaleTimeString('pl-PL', { ...zone, hour: '2-digit', minute: '2-digit' });
  const shift = (n: number) => day(new Date(Date.now() + n * 86400000));
  const label = day(date) === shift(0) ? 'dziś' : day(date) === shift(-1) ? 'wczoraj' : date.toLocaleDateString('pl-PL', { ...zone, day: 'numeric', month: 'numeric' });
  return `${label} ${hour}`;
};
const cadence = (h: number) => !Number.isFinite(h) || h <= 0 ? 'na żądanie' : h < 1 ? `co ${Math.round(h * 60)} min`
  : h % 24 === 0 ? (h === 24 ? 'raz dziennie' : h === 168 ? 'raz w tygodniu' : `co ${h / 24} dni`) : `co ${h.toLocaleString('pl-PL')} h`;
const num = (n: number) => (Number.isFinite(n) ? n : 0).toLocaleString('pl-PL');
const figures = (l: Loop) => `24 h: ${num(l.outputs_24h)}${l.pending ? ` · czeka ${num(l.pending)}` : ''}`;
const worst = (loops: Loop[]) => [...loops].sort((a, b) => SEVERITY[a.state] - SEVERITY[b.state])[0];

function GearTile({ loop, index, selected, onSelect }: { loop: Loop; index: number; selected: boolean; onSelect: () => void }) {
  // Szachownica kierunków: sąsiednie koła w rzędzie i w kolumnie kręcą się w przeciwne strony (jak zazębione).
  const odd = (Math.floor(index / COLS) + (index % COLS)) % 2 === 1;
  const problem = loop.state === 'bad';
  return <button type="button" className="sc-petle__tile" data-state={loop.state} aria-pressed={selected} onClick={onSelect}
    aria-label={`${loop.label}: ${STATE[loop.state]}. ${problem ? loop.reason : figures(loop)}`}>
    <Gear state={loop.state} reverse={odd} phase={odd} />
    <strong title={loop.label}>{loop.label}</strong>
    <span className="sc-petle__state">{STATE[loop.state]}</span>
    <small title={problem ? loop.reason : undefined}>{problem ? loop.reason : figures(loop)}</small>
  </button>;
}

function CategoryCard({ category, selected, onSelect }: { category: LoopCategory; selected: string | null; onSelect: (key: string) => void }) {
  const loops = category.loops || [];
  const n = (s: LoopState) => loops.filter(l => l.state === s).length;
  const total = loops.reduce((sum, l) => sum + (l.outputs_24h || 0), 0);
  const waiting = loops.reduce((sum, l) => sum + (l.pending || 0), 0);
  return <section className="sc-petle__card" aria-labelledby={`petle-${category.key}`} data-state={loops.length ? worst(loops).state : 'idle'}>
    <header><h2 id={`petle-${category.key}`}>{category.label}</h2>
      <span className="sc-petle__tags">{n('bad') > 0 && <em data-state="bad">{n('bad')} stoi</em>}{n('warn') > 0 && <em data-state="warn">{n('warn')} zwalnia</em>}
        {!n('bad') && !n('warn') && <em>{loops.length ? 'w porządku' : 'brak pętli'}</em>}</span></header>
    <div className="sc-petle__gears">{loops.map((loop, i) => <GearTile key={loop.key} loop={loop} index={i}
      selected={selected === `${category.key}/${loop.key}`} onSelect={() => onSelect(`${category.key}/${loop.key}`)} />)}</div>
    <footer><span>{loops.length} {loops.length === 1 ? 'pętla' : loops.length < 5 && loops.length > 1 ? 'pętle' : 'pętli'}</span><span>24 h: {num(total)} · czeka: {num(waiting)}</span></footer>
  </section>;
}

function Detail({ loop, category }: { loop: Loop | undefined; category: string }) {
  if (!loop) return <div className="sc-petle__detail" aria-live="polite"><p className="sc-petle__hint">Kliknij koło, aby zobaczyć powód, odbiorcę i rytm pętli.</p></div>;
  return <div className="sc-petle__detail" data-state={loop.state} aria-live="polite">
    <header><span className="sc-petle__eyebrow">{category}</span><strong>{loop.label}</strong><b data-state={loop.state}>{STATE[loop.state]}</b></header>
    <p>{loop.reason || 'Brak opisu stanu.'}</p>
    <dl>
      <div><dt>Ostatni bieg</dt><dd>{when(loop.last_run)}</dd></div>
      <div><dt><span className="sc-petle__wide">Wyniki </span>24 h / 7 dni</dt><dd>{num(loop.outputs_24h)} / {num(loop.outputs_7d)}</dd></div>
      <div><dt>Czeka</dt><dd>{num(loop.pending)}</dd></div>
      <div><dt>Rytm</dt><dd>{cadence(loop.cadence_h)}</dd></div>
      <div className="sc-petle__consumer"><dt>Odbiorca</dt><dd title={loop.consumer}>{loop.consumer || 'brak'}</dd></div>
    </dl>
  </div>;
}

export function PetlePanel() {
  const [data, setData] = useState<LoopsSnapshot | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'forbidden' | 'missing' | 'error'>('loading');
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const active = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    if (active.current) return;
    const controller = new AbortController(); active.current = controller; setBusy(true);
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      // Podgląd lokalny: /panel/petle?podglad=1 w trybie deweloperskim pokazuje dane przykładowe.
      if (process.env.NODE_ENV !== 'production' && new URLSearchParams(window.location.search).has('podglad')) {
        setData(PETLE_FIXTURE); setStatus('ready'); return;
      }
      const response = await fetch('/api/staff/petle/', { credentials: 'include', cache: 'no-store', signal: controller.signal,
        headers: { Accept: 'application/json', 'X-Frontend-Domain': process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' } });
      if (response.status === 401 || response.status === 403) { setStatus('forbidden'); setData(null); return; }
      if (response.status === 404) { setStatus('missing'); setData(null); return; }
      if (!response.ok) throw new Error('bad status');
      const snapshot: LoopsSnapshot = await response.json();
      if (!Array.isArray(snapshot.categories)) throw new Error('bad shape');
      setData(snapshot); setStatus('ready');
    } catch { setStatus(current => current === 'ready' ? 'ready' : 'error'); }
    finally { clearTimeout(timeout); if (active.current === controller) { active.current = null; setBusy(false); } }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => { if (document.visibilityState === 'visible') void refresh(); }, 60000);
    return () => { clearInterval(timer); active.current?.abort(); active.current = null; };
  }, [refresh]);

  const categories = data?.categories || [];
  const all = categories.flatMap(c => (c.loops || []).map(loop => ({ id: `${c.key}/${loop.key}`, loop, category: c.label })));
  const summary = data?.summary || { ok: 0, warn: 0, bad: 0, idle: 0 };
  // Domyślnie pokazujemy najgorszą pętlę: problem widać od razu (Von Restorff).
  const first = [...all].sort((a, b) => SEVERITY[a.loop.state] - SEVERITY[b.loop.state])[0];
  const current = all.find(item => item.id === selected) || (first && first.loop.state !== 'ok' && first.loop.state !== 'idle' ? first : undefined);
  const problems = (summary.bad || 0) + (summary.warn || 0);

  return <div className="sc-command-panel sc-command-v2 sc-petle">
    <header className="sc-command-header"><div><span className="sc-command-eyebrow"><Link href="/panel">Panel dowodzenia</Link> · operacje</span><h1>Pętle</h1></div>
      <button type="button" className="sc-command-refresh" onClick={() => void refresh()} disabled={busy}>{busy ? 'Odświeżanie…' : '↻ Odśwież'}</button></header>
    {status === 'forbidden' ? <div className="sc-command-banner"><p>Widok pętli jest dostępny wyłącznie dla zalogowanego personelu.</p><Link href="/editor">Przejdź do logowania →</Link></div> : <>
      <p className="sc-petle__summary" role="status" data-problems={problems > 0 || undefined}>
        {status === 'loading' && !data ? <span>Pobieranie stanu pętli…</span>
          : status === 'missing' ? <span>Stan pętli nie jest jeszcze dostępny - serwer nie ma tego widoku.</span>
          : status === 'error' && !data ? <span data-state="bad">Brak połączenia z serwerem - spróbuj odświeżyć.</span>
          : <>{STATES.map(s => <span key={s} data-state={s} data-zero={!summary[s] || undefined}><i aria-hidden="true" />{num(summary[s] || 0)} {SUMMARY[s]}</span>)}
            <time dateTime={data?.generated_at}>stan: {when(data?.generated_at || null)}</time></>}
      </p>
      {data && <Detail loop={current?.loop} category={current?.category || ''} />}
      {data && (categories.length ? <div className="sc-petle__grid">{categories.map(category => <CategoryCard key={category.key} category={category}
        selected={current?.id || null} onSelect={id => setSelected(id)} />)}</div>
        : <p className="sc-command-note">Brak pętli do pokazania.</p>)}
    </>}
  </div>;
}
