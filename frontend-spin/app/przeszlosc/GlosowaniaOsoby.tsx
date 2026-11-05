"use client";
import { useEffect, useRef, useState } from 'react';
import { nb } from './ui';
import { outcomeLabel, shortDay, type VoteKind, type VoteKindKey } from './glosowania-lista';
import './glosowania-osoby.css';

/**
 * Głosowania osoby z filtrami (dopisek właściciela 23.10): GET /api/przeszlosc/osoba/<ident>/glosowania/
 * Jedna linia filtrów (Hick: tylko rodzaje z danymi i z liczbą pozycji; puste rodzaje opisane pod spodem, nie jako przyciski),
 * potem kadencja, wynik, zgodność z klubem (tylko Sejm) i daty. Wiersze o stałej wysokości, cele 44 px (Fitts).
 */
type Row = { kind: VoteKindKey; id: string; term: number | null; date: string | null; title: string; motion: string; vote: string;
  club: string; with_club: boolean | null; outcome: string; url: string };
type Data = { kinds: VoteKind[]; terms: number[]; club_filter: boolean; club_note: string; count: number; page: number; pages: number; results: Row[] };
type F = { rodzaj: VoteKindKey; kadencja: string; wynik: string; zgodnosc: string; od: string; do: string };
const START: F = { rodzaj: 'sejm', kadencja: '', wynik: '', zgodnosc: '', od: '', do: '' };
const OUT = [['', 'Każdy wynik'], ['przyjete', 'Przyjęte'], ['odrzucone', 'Odrzucone']] as const;
const CLUB = [['', 'Każdy głos'], ['zgodnie', 'Zgodnie z klubem'], ['inaczej', 'Inaczej niż klub']] as const;

export function GlosowaniaOsoby({ ident }: { ident: string | number }) {
  const [f, setF] = useState<F>(START);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Data | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [state, setState] = useState<'wait' | 'loading' | 'ok' | 'error'>('wait');
  const host = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = host.current; if (!el) return;
    if (!('IntersectionObserver' in window)) { setState('loading'); return; }
    const io = new IntersectionObserver(en => { if (en.some(e => e.isIntersecting)) { io.disconnect(); setState(s => s === 'wait' ? 'loading' : s); } }, { rootMargin: '400px 0px' });
    io.observe(el); return () => io.disconnect();
  }, []);
  useEffect(() => {
    if (state === 'wait') return;
    const q = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]);
    q.set('strona', String(page));
    let live = true;
    fetch(`/api/przeszlosc/osoba/${encodeURIComponent(String(ident))}/glosowania/?${q}`).then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((d: Data) => { if (!live) return; setData(d); setRows(prev => page > 1 ? [...prev, ...d.results] : d.results); setState('ok'); })
      .catch(() => live && setState('error'));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f, page, ident, state === 'wait']);

  const set = (patch: Partial<F>) => { setPage(1); setF(x => ({ ...x, ...patch, ...(patch.rodzaj && patch.rodzaj !== 'sejm' ? { zgodnosc: '', kadencja: '' } : {}) })); };
  const kinds = data?.kinds ?? [];
  const shown = kinds.filter(k => k.available || k.key === f.rodzaj);
  const empty = kinds.filter(k => !k.available);
  return <section className="px-card gv" id="pp-glosowania" ref={host} aria-labelledby="gv-h">
    <h2 id="gv-h" className="px-h3">Głosowania</h2>
    {state === 'error' && <p className="px-note" role="alert">Nie udało się pobrać głosowań.</p>}
    {data && <>
      <div className="gv-filters" role="group" aria-label="Filtry głosowań">
        <div className="gv-line" role="group" aria-label="Rodzaj">
          {shown.map(k => <button key={k.key} type="button" className="gv-chip" aria-pressed={f.rodzaj === k.key} onClick={() => set({ rodzaj: k.key })}>{`${k.label} (${k.count})`}</button>)}
        </div>
        <div className="gv-line">
          {data.club_filter && data.terms.length > 1 && <label className="gv-sel">Kadencja <select value={f.kadencja} onChange={e => set({ kadencja: e.target.value })}>
            <option value="">wszystkie</option>{data.terms.map(t => <option key={t} value={t}>{t}</option>)}</select></label>}
          <label className="gv-sel">Wynik <select value={f.wynik} onChange={e => set({ wynik: e.target.value })}>{OUT.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          {data.club_filter && <label className="gv-sel">Klub <select value={f.zgodnosc} onChange={e => set({ zgodnosc: e.target.value })}>{CLUB.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>}
          <label className="gv-sel">Od <input type="date" value={f.od} max={f.do || undefined} onChange={e => set({ od: e.target.value })} /></label>
          <label className="gv-sel">Do <input type="date" value={f.do} min={f.od || undefined} onChange={e => set({ do: e.target.value })} /></label>
        </div>
        {empty.length > 0 && <p className="px-note gv-empty">{nb(empty.map(k => `${k.label} - ${k.note}`).join(' '))}</p>}
        {data.club_note && <p className="px-note gv-empty">{nb(data.club_note)}</p>}
      </div>
      <p className="gv-count" role="status">{nb(`${data.count} ${data.count === 1 ? 'głosowanie' : 'głosowań'} spełnia filtry`)}</p>
      <ul className="gv-list">{rows.map(r => <li key={r.id} className="gv-row">
        <time className="gv-date">{shortDay(r.date) || 'bez daty'}</time>
        <a className="gv-title" href={r.url} target="_blank" rel="noopener noreferrer" title={r.title}>{r.title}</a>
        <span className="gv-vote" data-v={r.vote}>{r.vote}</span>
        <span className="gv-meta">{[outcomeLabel(r.outcome), r.club ? `${r.club}${r.with_club === false ? ', inaczej niż klub' : r.with_club ? ', z klubem' : ''}` : ''].filter(Boolean).join(' · ')}</span>
      </li>)}</ul>
      {data.page < data.pages && <button type="button" className="gv-chip gv-more" onClick={() => setPage(p => p + 1)}>{`Pokaż kolejne (${data.count - rows.length})`}</button>}
    </>}
  </section>;
}
