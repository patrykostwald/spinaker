"use client";
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Article } from '../types';
import { NewsCard } from '../kit/NewsCard';

export function NewsStrip({ title, eyebrow, articles, onSelect, loading = false, error = false, onRetry, empty = 'Nie ma jeszcze materiałów w tym zakresie.', large = false, controls, live = false }: {
  title: string; eyebrow?: string; articles: Article[]; onSelect: (article: Article) => void;
  loading?: boolean; error?: boolean; onRetry?: () => void; empty?: string; large?: boolean; controls?: ReactNode; live?: boolean;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const hovering = useRef(false);
  const focused = useRef(false);
  const [playing, setPlaying] = useState(true);
  const automatic = live && large;
  useEffect(() => {
    if (!automatic) return;
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const respectMotion = () => { if (preference.matches) setPlaying(false); };
    respectMotion();
    preference.addEventListener('change', respectMotion);
    return () => preference.removeEventListener('change', respectMotion);
  }, [automatic]);
  useEffect(() => {
    if (!automatic || !playing || !articles.length) return;
    let frame = 0;
    let previous = 0;
    let position = scroller.current?.scrollLeft ?? 0;
    function advance(now: number) {
      const node = scroller.current;
      const elapsed = previous ? Math.min(now - previous, 64) : 0;
      previous = now;
      if (node && !document.hidden && !hovering.current && !focused.current && !document.activeElement?.closest('dialog[open]')) {
        const end = node.scrollWidth - node.clientWidth;
        if (end > 0 && node.scrollLeft >= end - 1) { setPlaying(false); return; }
        // Fractional position avoids losing the slow movement to pixel rounding.
        position = Math.max(position, node.scrollLeft) + elapsed * .018;
        node.scrollLeft = position;
      }
      frame = requestAnimationFrame(advance);
    }
    frame = requestAnimationFrame(advance);
    return () => cancelAnimationFrame(frame);
  }, [automatic, playing, articles.length]);
  function move(direction: number) {
    setPlaying(false);
    const node = scroller.current;
    if (node) node.scrollBy({ left: direction * node.clientWidth * .8, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }
  return <section className={`news-strip ${large ? 'news-strip-large' : ''}`}>
    <header className="strip-heading"><div><h2>{live && <span className="live-dot" aria-label="Aktualizowane na żywo" />}{title}</h2>{eyebrow && <p>{eyebrow}</p>}</div><div className="strip-actions">{controls}{automatic && articles.length > 0 && <button type="button" className="quiet-button" aria-label={playing ? 'Wstrzymaj przesuwanie najnowszych wiadomości' : 'Uruchom przesuwanie najnowszych wiadomości'} onClick={() => { const node = scroller.current; if (!playing && node && node.scrollLeft >= node.scrollWidth - node.clientWidth - 1) node.scrollLeft = 0; setPlaying(value => !value); }}>{playing ? 'Pauza' : 'Przesuwaj'}</button>}{articles.length > 0 && <><button className="strip-arrow" onClick={() => move(-1)} aria-label={`Przewiń w lewo: ${title}`}>←</button><button className="strip-arrow" onClick={() => move(1)} aria-label={`Przewiń w prawo: ${title}`}>→</button></>}</div></header>
    {error && <p role="status" className="strip-empty">Nie udało się odświeżyć materiałów. {onRetry && <button onClick={onRetry} className="text-primary">Spróbuj ponownie</button>}</p>}
    {loading && !articles.length ? <p role="status" className="strip-empty">Ładuję materiały ze źródeł…</p> : !articles.length && !error ? <p className="strip-empty">{empty}</p> : null}
    {articles.length > 0 && <div ref={scroller} className="news-strip-track" style={automatic && playing ? { scrollBehavior: 'auto', scrollSnapType: 'none' } : undefined} tabIndex={0} aria-label={`${title} — materiały, przewijaj poziomo`} onMouseEnter={() => { hovering.current = true; }} onMouseLeave={() => { hovering.current = false; }} onFocus={() => { focused.current = true; }} onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) focused.current = false; }} onPointerDown={() => setPlaying(false)} onWheel={() => setPlaying(false)} onKeyDown={e => { if (e.target === e.currentTarget && ['ArrowLeft', 'ArrowRight'].includes(e.key)) { e.preventDefault(); move(e.key === 'ArrowLeft' ? -1 : 1); } }}>
      {articles.map(article => (
        <div key={article.id} className="news-strip-item">
          <NewsCard
            article={article}
            size={large ? "medium" : "compact"}
            onOpen={onSelect}
            showDescription={large}
          />
        </div>
      ))}
    </div>}
  </section>;
}
