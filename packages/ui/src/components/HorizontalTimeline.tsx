"use client";
import { useRef, useState } from 'react';
import type { Article, ThreadItem } from '../types';
import { ArticleCard } from './ArticleCard';
import { ArticleModal } from './ArticleModal';
import { formatDatePl } from '../lib/utils';
export function HorizontalTimeline({ items, anchorFirst = false }: { items: ThreadItem[]; anchorFirst?: boolean }) {
  const scroller = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [selected, setSelected] = useState<Article | null>(null);
  const [cardWidth, setCardWidth] = useState(260);
  const ordered = [...items].sort((a, b) => a.position - b.position);
  const scrollTo = (index: number) => {
    const next = Math.max(0, Math.min(ordered.length - 1, index));
    (scroller.current?.children[next] as HTMLElement)?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', inline: 'start', block: 'nearest' });
    setActive(next);
  };
  if (!ordered.length) return <p className="py-8 text-slate-500">Brak dostępnych materiałów w tym wątku.</p>;
  return <div>
    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500"><p>{anchorFirst ? 'Wydarzenie główne, dalej kontekst od najstarszego źródła' : 'Od najstarszego źródła'} · {ordered.length} materiałów</p><label className="flex items-center gap-2">Powiększenie<input type="range" aria-label="Powiększenie kart osi czasu" min={220} max={380} step={20} value={cardWidth} onChange={e => setCardWidth(Number(e.target.value))} className="w-24 accent-primary" /></label><div className="flex items-center gap-2"><button aria-label="Poprzedni materiał" disabled={active === 0} onClick={() => scrollTo(active - 1)} className="rounded-full border px-3 py-2 disabled:opacity-30">←</button><span>{active + 1} / {ordered.length}</span><button aria-label="Następny materiał" disabled={active === ordered.length - 1} onClick={() => scrollTo(active + 1)} className="rounded-full border px-3 py-2 disabled:opacity-30">→</button></div></div>
    <div ref={scroller} tabIndex={0} aria-label="Oś czasu materiałów. Strzałki w lewo i w prawo zmieniają pozycję."
      className="flex snap-x snap-mandatory gap-0 overflow-x-auto py-3"
      onKeyDown={e => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); scrollTo(active + (e.key === 'ArrowRight' ? 1 : -1)); } }}
      onScroll={e => {
        const container = e.currentTarget;
        const left = container.getBoundingClientRect().left;
        let nearest = 0, distance = Infinity;
        Array.from(container.children).forEach((child, index) => { const d = Math.abs(child.getBoundingClientRect().left - left); if (d < distance) { distance = d; nearest = index; } });
        setActive(nearest);
      }}>
      {ordered.map((item, index) => <div key={item.id} style={{ width: cardWidth }} className="flex shrink-0 snap-start flex-col border-r border-slate-200 px-3 last:border-r-0">
        <p className="relative mb-3 border-t-2 border-primary pt-3 text-sm font-bold text-primary"><span className="absolute -top-1.5 left-0 h-2.5 w-2.5 rounded-full bg-primary" />{anchorFirst && index === 0 ? 'Wypowiedź / wydarzenie główne' : formatDatePl(item.article.published_date)}</p>
        {item.article.reference_only ? <div className="rounded-xl border bg-white p-5">{item.is_sponsored && <p className="card-sponsorship mb-3">{item.sponsorship_label || 'Nitka sponsorowana'}</p>}<span className="text-xs font-semibold text-primary">Post · odnośnik X</span><p className="my-3 text-sm text-slate-600">Treść i dostępność posta nie zostały sprawdzone. Materiał wskazał autor nitki.</p><a href={item.article.url} target="_blank" rel="noopener noreferrer" className="break-all font-semibold text-primary">Otwórz post na X ↗</a>{item.editorial_note && <p className="mt-4 border-t pt-3 text-sm"><strong>Komentarz autora: </strong>{item.editorial_note}</p>}</div> : <ArticleCard article={item.article} note={item.editorial_note} authorName={item.author_name} authorRole={item.author_role} sponsorshipLabel={item.is_sponsored ? item.sponsorship_label || 'Nitka sponsorowana' : undefined} showNote={expanded === item.id} onSelect={() => { if (!item.editorial_note || expanded === item.id) setSelected(item.article); else setExpanded(item.id); }} />}
        {expanded === item.id && !item.article.reference_only && <button onClick={() => setSelected(item.article)} className="mt-3 text-sm font-semibold text-primary">Otwórz szczegóły źródła →</button>}
      </div>)}
    </div>
    <div className="mt-2 flex flex-wrap justify-center gap-1">{ordered.map((item, index) => <button key={item.id} aria-label={`Przejdź do materiału ${index + 1}`} aria-current={active === index ? 'step' : undefined} onClick={() => scrollTo(index)} className="grid h-8 w-8 place-items-center"><span className={`h-2.5 w-2.5 rounded-full ${active === index ? 'bg-primary' : 'bg-slate-300'}`} /></button>)}</div>
    <ArticleModal article={selected} onClose={() => setSelected(null)} />
  </div>;
}
