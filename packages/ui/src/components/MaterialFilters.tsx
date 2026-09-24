"use client";
import { useState } from 'react';
import type { Source } from '../types';
import type { CategoryOption } from '../lib/portal';
import { Button, Checkbox, SearchField } from '../kit';

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
  return <div className="sc-material-filters"><p className="sc-t-caption sc-text-2">Bez wyboru: wszystkie dostępne materiały.</p>
    <details open><summary>Typ materiału <span>{value.categories.length || 'wszystkie'}</span></summary><div className="sc-material-filters__options">{categories.map(category => <Checkbox key={category.value} label={category.label} checked={value.categories.includes(category.value)} onChange={() => toggle('categories', category.value)} />)}</div></details>
    <details><summary>Temat <span>{value.topics.length || 'wszystkie'}</span></summary><div className="sc-material-filters__options">{topics.map(topic => <Checkbox key={topic.value} label={topic.label} checked={value.topics.includes(topic.value)} onChange={() => toggle('topics', topic.value)} />)}</div>{!topics.length && <p className="sc-t-caption sc-text-2">Lista tematów nie jest dostępna.</p>}<p className="sc-t-caption sc-text-2">Według oznaczeń wydawcy. Materiały bez ustalonego tematu znajdziesz bez tego filtra.</p></details>
    <details><summary>Źródła <span>{value.sources.length || 'wszystkie'}</span></summary><SearchField label="Znajdź źródło" value={search} onChange={setSearch} placeholder="Nazwa źródła" /><div className="sc-material-filters__options">{visible.map(source => <Checkbox key={source.id} label={source.name} checked={value.sources.includes(source.id)} onChange={() => onChange({ ...value, sources: value.sources.includes(source.id) ? value.sources.filter(id => id !== source.id) : [...value.sources, source.id] })} />)}</div>{!visible.length && <p className="sc-t-caption sc-text-2">Brak źródeł pasujących do nazwy.</p>}</details>
    {(value.categories.length > 0 || value.topics.length > 0 || value.sources.length > 0) && <Button type="button" variant="quiet" size="sm" onClick={() => onChange(emptySelection())}>Wyczyść filtry</Button>}
  </div>;
}
