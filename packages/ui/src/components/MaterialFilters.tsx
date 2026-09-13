"use client";
import { useState } from 'react';
import type { Source } from '../types';
import type { CategoryOption } from '../lib/portal';

export type MaterialSelection = { categories: string[]; topics: string[]; sources: number[] };
export const emptySelection = (): MaterialSelection => ({ categories: [], topics: [], sources: [] });
export function MaterialFilters({ categories, topics, sources, value, onChange }: {
  categories: CategoryOption[]; topics: CategoryOption[]; sources: Source[];
  value: MaterialSelection; onChange: (value: MaterialSelection) => void;
}) {
  const [search, setSearch] = useState('');
  const visible = sources.filter(source => source.name.toLocaleLowerCase('pl').includes(search.toLocaleLowerCase('pl')));
  function toggle(field: 'categories' | 'topics', selected: string) {
    onChange({ ...value, [field]: value[field].includes(selected) ? value[field].filter(item => item !== selected) : [...value[field], selected] });
  }
  return <div className="material-filters"><p className="filter-note">Bez wyboru: wszystkie dostępne materiały.</p>
    <details open><summary>Typ materiału <span>{value.categories.length || 'wszystkie'}</span></summary><div className="category-options">{categories.map(category => <label key={category.value}><input type="checkbox" checked={value.categories.includes(category.value)} onChange={() => toggle('categories', category.value)} />{category.label}</label>)}</div></details>
    <details><summary>Temat <span>{value.topics.length || 'wszystkie'}</span></summary><div className="category-options">{topics.map(topic => <label key={topic.value}><input type="checkbox" checked={value.topics.includes(topic.value)} onChange={() => toggle('topics', topic.value)} />{topic.label}</label>)}</div>{!topics.length && <p className="filter-note">Lista tematów nie jest dostępna.</p>}<p className="filter-note">Według oznaczeń wydawcy. Materiały bez ustalonego tematu znajdziesz bez tego filtra.</p></details>
    <details><summary>Źródła <span>{value.sources.length || 'wszystkie'}</span></summary><label className="source-filter-search">Znajdź źródło<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Nazwa źródła" /></label><div className="source-filter-options category-options">{visible.map(source => <label key={source.id}><input type="checkbox" checked={value.sources.includes(source.id)} onChange={() => onChange({ ...value, sources: value.sources.includes(source.id) ? value.sources.filter(id => id !== source.id) : [...value.sources, source.id] })} />{source.name}</label>)}</div>{!visible.length && <p className="filter-note">Brak źródeł pasujących do nazwy.</p>}</details>
    {(value.categories.length > 0 || value.topics.length > 0 || value.sources.length > 0) && <button type="button" className="filter-reset" onClick={() => onChange(emptySelection())}>Wyczyść filtry</button>}
  </div>;
}
