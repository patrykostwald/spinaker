"use client";

import { useRef, useState } from "react";
import type { ThreadItem } from "../types";
import { formatDatePl } from "../lib/utils";
import { Button } from "../kit/Button";
import { NewsCard } from "../kit/NewsCard";

/** Oś nitki korzysta z tej samej karty co reszta serwisu, więc klik zawsze otwiera portal. */
export function HorizontalTimeline({ items, anchorFirst = false }: { items: ThreadItem[]; anchorFirst?: boolean }) {
  const scroller = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const ordered = [...items].sort((a, b) => a.position - b.position);
  const scrollTo = (index: number) => {
    const next = Math.max(0, Math.min(ordered.length - 1, index));
    (scroller.current?.children[next] as HTMLElement | undefined)?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", inline: "start", block: "nearest" });
    setActive(next);
  };
  if (!ordered.length) return <p className="sc-t-body sc-text-2">Brak dostępnych materiałów w tym wątku.</p>;
  return <section className="sc-thread-timeline" aria-label="Oś czasu materiałów">
    <header className="sc-thread-timeline__head"><p className="sc-t-meta sc-text-2">{anchorFirst ? "Wydarzenie główne, dalej kontekst od najstarszego źródła" : "Od najstarszego źródła"} · {ordered.length} materiałów</p><div className="sc-thread-timeline__controls" aria-label="Sterowanie osią czasu"><Button shape="rounded" variant="secondary" size="sm" aria-label="Poprzedni materiał" disabled={active === 0} onClick={() => scrollTo(active - 1)}>←</Button><span className="sc-t-meta" aria-live="polite">{active + 1} / {ordered.length}</span><Button shape="rounded" variant="secondary" size="sm" aria-label="Następny materiał" disabled={active === ordered.length - 1} onClick={() => scrollTo(active + 1)}>→</Button></div></header>
    <div ref={scroller} tabIndex={0} className="sc-thread-timeline__track sc-strip-bleed" onKeyDown={(event) => { if (event.key === "ArrowRight" || event.key === "ArrowLeft") { event.preventDefault(); scrollTo(active + (event.key === "ArrowRight" ? 1 : -1)); } }} onScroll={(event) => { const left = event.currentTarget.getBoundingClientRect().left; let nearest = 0; let distance = Infinity; Array.from(event.currentTarget.children).forEach((child, index) => { const nextDistance = Math.abs((child as HTMLElement).getBoundingClientRect().left - left); if (nextDistance < distance) { distance = nextDistance; nearest = index; } }); setActive(nearest); }}>
      {ordered.map((item, index) => <article className="sc-thread-timeline__item" key={item.id}><p className="sc-thread-timeline__date sc-t-meta"><span aria-hidden="true" />{anchorFirst && index === 0 ? "Wydarzenie główne" : formatDatePl(item.article.published_date)}</p>{item.is_sponsored ? <p className="sc-thread-timeline__sponsored sc-t-caption">{item.sponsorship_label || "Nitka sponsorowana"}</p> : null}{item.article.reference_only ? <div className="sc-thread-timeline__reference"><p className="sc-t-caption">Post · odnośnik X</p><p className="sc-t-body sc-text-2">Treść i dostępność posta nie zostały sprawdzone. Materiał wskazał autor nitki.</p><a className="sc-thread-timeline__source" href={item.article.url} target="_blank" rel="noopener noreferrer">Otwórz post na X ↗</a>{item.editorial_note ? <p className="sc-t-body"><strong>Komentarz autora: </strong>{item.editorial_note}</p> : null}</div> : <><NewsCard article={item.article} size="compact" showDescription />{item.editorial_note ? <p className="sc-thread-timeline__note sc-t-body"><strong>Komentarz autora: </strong>{item.editorial_note}</p> : null}</>}</article>)}
    </div>
    <div className="sc-thread-timeline__dots" aria-label="Pozycje osi czasu">{ordered.map((item, index) => <button key={item.id} type="button" aria-label={`Przejdź do materiału ${index + 1}`} aria-current={active === index ? "step" : undefined} onClick={() => scrollTo(index)}><span /></button>)}</div>
  </section>;
}

