"use client";

import { useEffect, useRef, useState } from 'react';

export type StripItem = { id: string | number; title: string; date: string | null; source: string; url: string; category: string; category_label: string; image_url?: string; kind?: string };
type Category = { id: string; label: string };
type StripName = 'youtube' | 'publiczne' | 'media';
export type StripsData = Record<StripName, StripItem[]> & { kategorie: Record<StripName, Category[]>; generated_at: string };
export const MEDIA_ENABLED = process.env.NEXT_PUBLIC_PRZESZLOSC_PASEK_MEDIA === '1';
const EMPTY: StripItem[] = [];
const CATEGORIES: Category[] = [];

export function safeOriginal(url: string): string | undefined {
  try { const parsed = new URL(url); return ['https:', 'http:'].includes(parsed.protocol) ? parsed.href : undefined; } catch { return undefined; }
}

/** Wzorzec: NewsStrip.tsx (tor, klawiatura, przyciski i reduced motion) oraz
 * HomeCategoryBar.tsx (jeden aktywny żeton). Osobna karta metadanych nie uruchamia NewsCard/diagnoz.
 * Przyszły tryb YouTube IFrame Player należy do osobnego komponentu; tutaj wyłącznie link do oryginału.
 */
export function MetadataStrip({ name, title, items, categories, state, retry }: {
  name: StripName; title: string; items: StripItem[]; categories: Category[];
  state: 'loading' | 'error' | 'ready'; retry: () => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState('all');
  useEffect(() => { try { setSelected(localStorage.getItem(`px-pasek-${name}`) || 'all'); } catch { /* pamięć opcjonalna */ } }, [name]);
  const active = categories.some(c => c.id === selected) ? selected : 'all';
  const rows = items.filter(item => (active === 'all' || item.category === active) && safeOriginal(item.url));
  function choose(value: string) {
    setSelected(value);
    try { localStorage.setItem(`px-pasek-${name}`, value); } catch { /* działa też bez localStorage */ }
    if (scroller.current) scroller.current.scrollLeft = 0;
  }
  function move(direction: number) {
    const node = scroller.current;
    node?.scrollBy({ left: direction * node.clientWidth * .8, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }
  return <section className="sc-news-strip px-strip" data-strip={name} aria-labelledby={`px-strip-${name}`}>
    <header className="sc-news-strip__head">
      <h2 id={`px-strip-${name}`}>{title}</h2>
      <div className="sc-news-strip__actions">
        <button type="button" aria-label={`Przewiń w lewo: ${title}`} disabled={!rows.length || state !== 'ready'} onClick={() => move(-1)}>←</button>
        <button type="button" aria-label={`Przewiń w prawo: ${title}`} disabled={!rows.length || state !== 'ready'} onClick={() => move(1)}>→</button>
      </div>
    </header>
    <div className="px-chips px-strip__categories" role="group" aria-label={`Kategorie: ${title}`}>
      {[{ id: 'all', label: 'Wszystko' }, ...categories].map(c => <button key={c.id} type="button" aria-pressed={active === c.id} onClick={() => choose(c.id)}>{c.label}</button>)}
    </div>
    <div className="px-strip__stage" aria-busy={state === 'loading'}>
      {state !== 'ready' || !rows.length ? <div className="px-strip__status" role="status">
        {state === 'loading' ? 'Ładowanie materiałów…' : state === 'error' ? <>Nie udało się pobrać materiałów.<button type="button" onClick={retry}>Spróbuj ponownie</button></> : 'Brak materiałów w tej kategorii.'}
      </div> : <div ref={scroller} className="sc-news-strip__track px-strip__track" tabIndex={0} role="region" aria-label={`${title} - materiały`} onKeyDown={event => {
        if (event.target === event.currentTarget && ['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); move(event.key === 'ArrowLeft' ? -1 : 1); }
      }}>
        {rows.map(item => <a key={`${item.id}:${item.url}`} className="px-strip__card" href={safeOriginal(item.url)} target="_blank" rel="noopener noreferrer" aria-label={`${item.title}, ${item.source}, ${item.date ? new Date(item.date).toLocaleDateString('pl-PL', { timeZone: 'Europe/Warsaw' }) : 'bez daty'} - otwiera nową kartę`}>
          <h3 title={item.title}>{item.title}</h3>
          {name === 'youtube' ? <div className="px-strip__image">{item.image_url && /^https:\/\/i\.ytimg\.com\//.test(item.image_url) ? <img src={item.image_url} alt="" loading="lazy" width={256} height={144} /> : <span>Film na YouTube</span>}</div> : <span className="px-strip__kind">{item.category_label || item.kind || 'Artykuł'}</span>}
          <span className="px-strip__source" title={item.source}>{item.source}</span>
          <footer><time dateTime={item.date || undefined}>{item.date ? new Date(item.date).toLocaleDateString('pl-PL', { timeZone: 'Europe/Warsaw' }) : 'Bez daty'}</time><span aria-hidden="true">Oryginał ↗</span></footer>
        </a>)}
      </div>}
    </div>
  </section>;
}

export function Paski() {
  const [data, setData] = useState<StripsData | null>(null);
  const [state, setState] = useState<'loading' | 'error' | 'ready'>('loading');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    setState('loading');
    fetch('/api/przeszlosc/paski/', { signal: abort.signal }).then(response => {
      if (!response.ok) throw new Error('paski');
      return response.json();
    }).then((result: StripsData) => { if (!abort.signal.aborted) { setData(result); setState('ready'); } })
      .catch(() => { if (!abort.signal.aborted) setState('error'); });
    return () => abort.abort();
  }, [attempt]);
  return <div className="px-strips">
    {([['youtube', 'YouTube'], ['publiczne', 'Źródła publiczne'], ...(MEDIA_ENABLED ? [['media', 'Media']] : [])] as [StripName, string][]).map(([name, title]) =>
      <MetadataStrip key={name} name={name} title={title} items={data?.[name] || EMPTY} categories={data?.kategorie[name] || CATEGORIES} state={state} retry={() => setAttempt(n => n + 1)} />)}
  </div>;
}
