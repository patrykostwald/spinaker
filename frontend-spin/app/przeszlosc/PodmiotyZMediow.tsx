"use client";
import { useState } from 'react';
import { nb, plural, short } from './ui';
import './podmioty-media.css';

/**
 * „Podmioty z doniesień medialnych” (właściciel 6.11): osobne okno przy osobie. Pokazujemy kategorię doniesienia, podmiot z naszej bazy
 * (KRS) i źródło (redakcja, data, tytuł, krótki cytat). Nie opisujemy charakteru powiązania; stała notka mówi, że wzmianka nie jest
 * dowodem powiązania. Pozycje po przeglądzie zespołu (backend: news/przeszlosc_doniesienia.py).
 */
export type OrgMention = { id: number; category: string; category_label: string; unconfirmed: boolean; quote: string;
  organisation: { name: string; krs_number: string; kind: string; url: string; register_url?: string };
  source: { url: string; title: string; outlet: string; date: string | null } };
export type OrgMentions = { count: number; notice: string; by_category: Record<string, number>; results: OrgMention[] };

const FIRST = 6;

export function PodmiotyZMediow({ data, id = 'pp-om-h' }: { data?: OrgMentions; id?: string }) {
  const [category, setCategory] = useState('all');
  const [more, setMore] = useState(false);
  if (!data || !data.count) return null;
  const cats = Object.entries(data.by_category).filter(([, n]) => n > 0);
  const labels = new Map(data.results.map(r => [r.category, r.category_label]));
  const rows = data.results.filter(r => category === 'all' || r.category === category);
  const shown = more ? rows : rows.slice(0, FIRST);
  return <section className="px-card px-om" aria-labelledby={id}>
    <header className="px-om__head">
      <div className="px-om__heading"><h3 id={id} className="px-h3">Podmioty z doniesień medialnych</h3><small className="px-om__status">po przeglądzie</small></div>
      <p className="px-note">{data.count} {plural(data.count, 'doniesienie', 'doniesienia', 'doniesień')}. {nb(data.notice)}</p>
      {cats.length > 1 && <div className="px-chips px-om__chips" role="group" aria-label="Kategoria doniesienia">
        <button type="button" aria-pressed={category === 'all'} onClick={() => { setCategory('all'); setMore(false); }}>Wszystkie</button>
        {cats.map(([key, n]) => <button key={key} type="button" aria-pressed={category === key} onClick={() => { setCategory(category === key ? 'all' : key); setMore(false); }}>{labels.get(key) ?? key} <em>{n}</em></button>)}
      </div>}
    </header>
    <ol className="px-om__list">{shown.map(m => <li key={m.id}>
      <div className="px-om__top">
        <a className="px-om__org" href={m.organisation.url} title={m.organisation.name}>{m.organisation.name}</a>
        <small className="px-om__cat">{m.category_label}{m.unconfirmed ? ' · niepotwierdzone' : ''}</small>
      </div>
      {m.organisation.register_url && <a className="px-om__reg" href={m.organisation.register_url} target="_blank" rel="noopener noreferrer"
        aria-label={`Wpis w urzędowym rejestrze: ${m.organisation.name} (KRS ${m.organisation.krs_number}; otwiera się w nowej karcie)`}>KRS {m.organisation.krs_number} ↗</a>}
      <a className="px-om__src" href={m.source.url} target="_blank" rel="noopener noreferrer" title={m.source.title}
        aria-label={`${m.source.title} (${m.source.outlet || 'media'}, ${short(m.source.date) || 'bez daty'}; otwiera się w nowej karcie)`}>
        <b>{m.source.outlet || 'Media'}</b><time dateTime={m.source.date ?? undefined}>{short(m.source.date) || '–'}</time><span>{m.source.title}</span><i aria-hidden="true">↗</i>
      </a>
      <p className="px-om__quote">{m.quote ? `„${m.quote}”` : ''}</p>
    </li>)}</ol>
    <p className="px-card__foot px-om__foot">
      <span>{nb('Tylko tytuł, data, krótki cytat i odnośnik do redakcji. Treść czytasz u wydawcy.')}</span>
      {rows.length > FIRST && <button type="button" className="px-quiet" aria-expanded={more} onClick={() => setMore(!more)}>{more ? 'Pokaż mniej' : `Pokaż wszystkie (${rows.length})`}</button>}
    </p>
  </section>;
}
