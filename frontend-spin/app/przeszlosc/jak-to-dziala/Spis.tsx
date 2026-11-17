"use client";
import { useEffect, useState } from 'react';
import type { Sekcja } from './tresc';

/** Spis treści ze scroll-spy (konwencja terminala: aktywna pozycja = ">" przed i "_" po). Bez JS to zwykłe kotwice. */
export function Spis({ items }: { items: Sekcja[] }) {
  const [act, setAct] = useState(items[0]?.id ?? '');
  useEffect(() => {
    if (!('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver(entries => entries.forEach(e => { if (e.isIntersecting) setAct(e.target.id); }), { rootMargin: '-15% 0px -75% 0px' });
    items.forEach(({ id }) => { const el = document.getElementById(id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, [items]);
  return <nav className="jd-toc" aria-label="Spis treści">
    <a className="jd-skip jd-skip--toc" href="#jd-tresc">Pomiń spis treści</a>
    <p className="jd-toc__h">Spis treści</p>
    <ol>{items.map(s => <li key={s.id}><a href={`#${s.id}`} aria-current={act === s.id ? 'location' : undefined}><b>{s.numer}</b><span>{s.tytul}</span></a></li>)}</ol>
  </nav>;
}
