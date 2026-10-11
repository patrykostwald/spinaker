"use client";
import { useMemo, useState } from 'react';
import { Icon, nb, plural, short } from './ui';

/**
 * „W mediach” (właściciel 6.10): osobna grupa artykułów w drzewie tematu i na profilu osoby. Każdy wiersz: redakcja, data,
 * tytuł w jednej linii (wielokropek); kliknięcie otwiera oryginał w nowej karcie. Przy więcej niż jednej redakcji filtr
 * z żetonów (Hick: jedna decyzja, Common Region: jedna ramka). Pokazujemy tylko metadane: treść czytasz u wydawcy.
 */
export type MediaItem = { id: string; outlet: string; date: string | null; title: string; url: string; material_type?: string; kind_label?: string; snippet?: string; changed?: string | null };

const FIRST = 8;
const materialLabel = (item: MediaItem) => item.kind_label || (item.material_type === 'reportaz' ? 'reportaż' : item.material_type) || 'news';

export function WMediach({ items, heading = 'W mediach', id = 'wm-h', automatic = false, mentionContext = 'person' }: { items: MediaItem[]; heading?: string; id?: string; automatic?: boolean; mentionContext?: 'person' | 'topic' }) {
  const [outlet, setOutlet] = useState('all');
  const [more, setMore] = useState(false);
  const outlets = useMemo(() => {
    const n = new Map<string, number>();
    for (const m of items) n.set(m.outlet || 'Media', (n.get(m.outlet || 'Media') ?? 0) + 1);
    return [...n.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'pl'));
  }, [items]);
  if (!items.length) return null;
  const rows = items.filter(m => outlet === 'all' || (m.outlet || 'Media') === outlet).sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''));
  const shown = more ? rows : rows.slice(0, FIRST);
  return <section className="px-card px-wm" aria-labelledby={id}>
    <header className="px-wm__head">
      <div className="px-wm__heading"><h3 id={id} className="px-h3">{heading}</h3><small className="px-wm__status">{automatic ? 'automatyczne' : 'potwierdzone'}</small></div>
      <p className="px-note">{items.length} {plural(items.length, 'artykuł', 'artykuły', 'artykułów')}{automatic ? ` · ${mentionContext === 'person' ? 'Artykuły, w których pada nazwisko.' : 'Artykuły ze słowami tematu.'} Dopasowanie automatyczne, możliwe pomyłki.` : ''}</p>
      {outlets.length > 1 && <div className="px-chips px-wm__chips" role="group" aria-label="Redakcja">
        <button type="button" aria-pressed={outlet === 'all'} onClick={() => { setOutlet('all'); setMore(false); }}>Wszystkie</button>
        {outlets.slice(0, 8).map(([name, n]) => <button key={name} type="button" aria-pressed={outlet === name} onClick={() => { setOutlet(outlet === name ? 'all' : name); setMore(false); }}>{name} <em>{n}</em></button>)}
      </div>}
    </header>
    <ol className="px-wm__list">{shown.map(m => <li key={m.id}>
      <a href={m.url} target="_blank" rel="noopener noreferrer" aria-label={`${m.title} (${materialLabel(m)}, typ oszacowany automatycznie; ${m.outlet || 'Media'}, ${short(m.date) || 'bez daty'}; otwiera nową kartę)`}>
        <span className="px-wm__ic"><Icon name="media" size={15} /></span>
        <b title={m.outlet || 'Media'}>{m.outlet || 'Media'}</b>
        <time dateTime={m.date ?? undefined}>{short(m.date) || '–'}</time>
        <span className={m.changed ? 'px-wm__subject px-wm__subject--changed' : 'px-wm__subject'}><small className="px-wm__kind">{materialLabel(m)}</small><span className="px-wm__title" title={m.snippet ? `${m.title}
Dopasowanie: ${m.snippet}` : m.title}>{m.title}</span>
          {m.changed && <small className="px-wm__kind px-wm__changed" title={`Tekst zmienił się po zapisaniu u nas (wykryto ${m.changed}). Przed cytowaniem sprawdź wersję w archiwum.`}>zmieniony</small>}</span>
        <i aria-hidden="true">↗</i>
      </a></li>)}</ol>
    <p className="px-card__foot px-wm__foot">
      <span>{nb('Tylko tytuł, data i odnośnik do redakcji. Treść czytasz u wydawcy. Typ oszacowany automatycznie.')}</span>
      {rows.length > FIRST && <button type="button" className="px-quiet" aria-expanded={more} onClick={() => setMore(!more)}>{more ? 'Pokaż mniej' : `Pokaż wszystkie (${rows.length})`}</button>}
    </p>
  </section>;
}
