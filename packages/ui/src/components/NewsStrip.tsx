"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Article } from "../types";
import { Button, ChevronLeftIcon, ChevronRightIcon, NewsCard } from "../kit";

export function NewsStrip({ title, eyebrow, articles, onSelect, loading = false, error = false, onRetry, empty = "Nie ma jeszcze materiałów w tym zakresie.", large = false, controls, live = false }: {
  title: string; eyebrow?: string; articles: Article[]; onSelect?: (article: Article) => void;
  loading?: boolean; error?: boolean; onRetry?: () => void; empty?: string; large?: boolean; controls?: ReactNode; live?: boolean;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const hovering = useRef(false);
  const focused = useRef(false);
  const [playing, setPlaying] = useState(true);
  const automatic = live && large;

  useEffect(() => {
    if (!automatic) return;
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const respectMotion = () => { if (preference.matches) setPlaying(false); };
    respectMotion();
    preference.addEventListener("change", respectMotion);
    return () => preference.removeEventListener("change", respectMotion);
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
      if (node && !document.hidden && !hovering.current && !focused.current && !document.activeElement?.closest("dialog[open]")) {
        const end = node.scrollWidth - node.clientWidth;
        if (end > 0 && node.scrollLeft >= end - 1) { setPlaying(false); return; }
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
    if (node) node.scrollBy({ left: direction * node.clientWidth * .8, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }

  return <section className={`sc-news-strip${large ? " sc-news-strip--large" : ""}`}>
    <header className="sc-news-strip__head">
      <div><h2>{live ? <span className="sc-news-strip__live" aria-label="Aktualizowane na żywo" /> : null}{title}</h2>{eyebrow ? <p>{eyebrow}</p> : null}</div>
      <div className="sc-news-strip__actions">
        {controls}
        {automatic && articles.length > 0 ? <Button type="button" variant="quiet" size="sm" onClick={() => { const node = scroller.current; if (!playing && node && node.scrollLeft >= node.scrollWidth - node.clientWidth - 1) node.scrollLeft = 0; setPlaying(value => !value); }}>{playing ? "Pauza" : "Przesuwaj"}</Button> : null}
        {articles.length > 0 ? <>
          <Button type="button" variant="quiet" size="sm" shape="icon" aria-label={`Przewiń w lewo: ${title}`} iconStart={<ChevronLeftIcon />} onClick={() => move(-1)} />
          <Button type="button" variant="quiet" size="sm" shape="icon" aria-label={`Przewiń w prawo: ${title}`} iconStart={<ChevronRightIcon />} onClick={() => move(1)} />
        </> : null}
      </div>
    </header>
    {error ? <p role="status" className="sc-news-strip__empty">Nie udało się odświeżyć materiałów. {onRetry ? <Button type="button" size="sm" variant="quiet" onClick={onRetry}>Spróbuj ponownie</Button> : null}</p> : null}
    {loading && !articles.length ? <p role="status" className="sc-news-strip__empty">Ładuję materiały ze źródeł…</p> : !articles.length && !error ? <p className="sc-news-strip__empty">{empty}</p> : null}
    {articles.length > 0 ? <div ref={scroller} className="sc-news-strip__track sc-strip-bleed" style={automatic && playing ? { scrollBehavior: "auto", scrollSnapType: "none" } : undefined} tabIndex={0} aria-label={`${title} — materiały, przewijaj poziomo`} onMouseEnter={() => { hovering.current = true; }} onMouseLeave={() => { hovering.current = false; }} onFocus={() => { focused.current = true; }} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) focused.current = false; }} onPointerDown={() => setPlaying(false)} onWheel={() => setPlaying(false)} onKeyDown={event => { if (event.target === event.currentTarget && ["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); move(event.key === "ArrowLeft" ? -1 : 1); } }}>
      {articles.map(article => <div key={article.id} className="sc-news-strip__item"><NewsCard article={article} size={large ? "medium" : "compact"} onOpen={onSelect} showDescription={large} /></div>)}
    </div> : null}
  </section>;
}
