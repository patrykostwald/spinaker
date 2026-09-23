"use client";

import { forwardRef, useEffect, useState, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getNewsFeed } from '../lib/portal';
import type { CategoryOption } from '../lib/portal';
import type { Source } from '../types';
import { MAX_PERSONAL_STRIPS, loadPersonalStrips, removePersonalStrip, savePersonalStrip, updatePersonalStrip, type PersonalStrip } from '../lib/personalStrips';
import { MaterialBox } from './MaterialBox';
import { MaterialStrip } from './MaterialStrip';

function StripForm({ initial, categories, sources, onSave, onCancel }: {
  initial?: PersonalStrip; categories: CategoryOption[]; sources: Source[];
  onSave: (strip: PersonalStrip) => void; onCancel: () => void;
}) {
  const [query, setQuery] = useState(initial?.query ?? '');
  const [category, setCategory] = useState(initial?.category ?? '');
  const [sourceId, setSourceId] = useState<number | ''>(initial?.sourceId ?? '');
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = sources.find(item => item.id === sourceId);
    const label = query.trim() || categories.find(item => item.value === category)?.label || source?.name || 'Mój pasek';
    onSave({ id: initial?.id ?? `${Date.now()}`, label, query: query.trim(), category, sourceId });
  }
  return (
    <form className="mvp-strip-form" onSubmit={submit}>
      <p className="mvp-strip-form-title">{initial ? 'EDYTUJ PASEK' : 'NOWY PASEK'}</p>
      <div className="mvp-strip-form-row">
        <details className="mvp-strip-control">
          <summary>Hasło <span>{query || 'dowolne'}</span></summary>
          <label className="sr-only" htmlFor="strip-query">Hasło lub nazwisko</label>
          <input id="strip-query" value={query} onChange={event => setQuery(event.target.value)} maxLength={200} placeholder="Wpisz hasło lub nazwisko" />
        </details>
        <details className="mvp-strip-control">
          <summary>Kategoria <span>{categories.find(item => item.value === category)?.label || 'wszystkie'}</span></summary>
          <label className="sr-only" htmlFor="strip-category">Kategoria</label>
          <select id="strip-category" value={category} onChange={event => setCategory(event.target.value)}><option value="">Wszystkie</option>{categories.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
        </details>
        <details className="mvp-strip-control">
          <summary>Źródło <span>{sources.find(item => item.id === sourceId)?.name || 'wszystkie'}</span></summary>
          <label className="sr-only" htmlFor="strip-source">Źródło</label>
          <select id="strip-source" value={sourceId} onChange={event => setSourceId(event.target.value ? Number(event.target.value) : '')}><option value="">Wszystkie</option>{sources.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        </details>
        <div className="mvp-strip-form-actions">
          <button type="submit" className="quiet-button">Pokaż materiały</button>
          <button type="button" className="quiet-button" onClick={onCancel}>Anuluj</button>
        </div>
      </div>
    </form>
  );
}

function StripRow({ strip, editing, categories, sources, onEdit, onSave, onCancelEdit, onRemove }: {
  strip: PersonalStrip; editing: boolean; categories: CategoryOption[]; sources: Source[];
  onEdit: () => void; onSave: (strip: PersonalStrip) => void; onCancelEdit: () => void; onRemove: () => void;
}) {
  const feed = useQuery({
    queryKey: ['mvp-personal-strip', strip.query, strip.category, strip.sourceId],
    queryFn: () => getNewsFeed({ query: strip.query, categories: strip.category ? [strip.category] : [], sources: strip.sourceId ? [strip.sourceId] : [], pageSize: 20 }),
  });
  const articles = feed.data?.results ?? [];
  if (editing) return <StripForm initial={strip} categories={categories} sources={sources} onSave={onSave} onCancel={onCancelEdit} />;
  return (
      <section className="mvp-section" aria-label={`Twój przegląd Bazy: ${strip.label}`}>
      <header className="mvp-strip-heading">
        <h2>{strip.label}</h2>
        <div className="mvp-strip-form-actions">
          <button type="button" className="quiet-button" onClick={onEdit}>Edytuj</button>
          <button type="button" className="quiet-button" onClick={onRemove}>Usuń pasek ✕</button>
        </div>
      </header>
      {feed.isPending && <p role="status" className="mvp-strip-empty">Ładuję materiały…</p>}
      {feed.isSuccess && !articles.length && <p className="mvp-strip-empty">Nie znaleźliśmy jeszcze materiałów pasujących do tego wyboru.</p>}
      {articles.length > 0 && <MaterialStrip label={strip.label} height="sm">{articles.map(article => <MaterialBox key={article.id} article={article} />)}</MaterialStrip>}
    </section>
  );
}

export const TwojePaski = forwardRef<HTMLDivElement, { categories: CategoryOption[]; sources: Source[]; openSignal: number }>(
  function TwojePaski({ categories, sources, openSignal }, ref) {
    const [strips, setStrips] = useState<PersonalStrip[]>([]);
    const [adding, setAdding] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);

    useEffect(() => { setStrips(loadPersonalStrips()); }, []);
    useEffect(() => { if (openSignal > 0) { setAdding(true); setEditingId(null); } }, [openSignal]);

    function create(strip: PersonalStrip) { setStrips(savePersonalStrip(strip)); setAdding(false); }
    function save(strip: PersonalStrip) { setStrips(updatePersonalStrip(strip)); setEditingId(null); }
    function remove(id: string) { setStrips(removePersonalStrip(id)); if (editingId === id) setEditingId(null); }

    const atLimit = strips.length >= MAX_PERSONAL_STRIPS;
    const openNewStrip = () => { setAdding(true); setEditingId(null); };

    return (
      <div ref={ref} className="mvp-section mvp-twoje-paski" aria-label="Twój przegląd">
        <header className="mvp-strip-heading"><div><h2>Twój przegląd</h2><p>Twój lokalnie zapisany widok materiałów z Bazy</p></div></header>
        {!strips.length && !adding && <section className="mvp-personal-example" aria-label="Przykładowy widok Bazy">
          <div className="mvp-personal-example-controls" aria-label="Dopasuj przykładowy pasek">
            <button type="button" onClick={openNewStrip}>Hasło</button>
            <button type="button" onClick={openNewStrip}>Kategoria</button>
            <button type="button" onClick={openNewStrip}>Źródło</button>
            <button type="button" className="quiet-button" onClick={openNewStrip}>+ Dodaj kolejny pasek</button>
          </div>
        </section>}
        {strips.map(strip => (
          <StripRow key={strip.id} strip={strip} editing={editingId === strip.id} categories={categories} sources={sources}
            onEdit={() => { setEditingId(strip.id); setAdding(false); }} onSave={save} onCancelEdit={() => setEditingId(null)} onRemove={() => remove(strip.id)} />
        ))}
        {adding
          ? <StripForm categories={categories} sources={sources} onSave={create} onCancel={() => setAdding(false)} />
          : atLimit ? <p className="mvp-strip-empty">Masz już {MAX_PERSONAL_STRIPS} pasków — usuń jeden, aby dodać kolejny.</p> : strips.length ? <button type="button" className="quiet-button mvp-personal-add-more" onClick={openNewStrip}>+ Dodaj kolejny pasek</button> : null}
      </div>
    );
  },
);
