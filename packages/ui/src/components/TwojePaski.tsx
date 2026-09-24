"use client";

import { forwardRef, useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { getNewsFeed, type CategoryOption } from "../lib/portal";
import type { Source } from "../types";
import { MAX_PERSONAL_STRIPS, loadPersonalStrips, removePersonalStrip, savePersonalStrip, updatePersonalStrip, type PersonalStrip } from "../lib/personalStrips";
import { MaterialBox } from "./MaterialBox";
import { Button, Dropdown, ReorderableStrips, SearchField } from "../kit";

function StripForm({ initial, categories, sources, onSave, onCancel }: {
  initial?: PersonalStrip; categories: CategoryOption[]; sources: Source[];
  onSave: (strip: PersonalStrip) => void; onCancel: () => void;
}) {
  const [query, setQuery] = useState(initial?.query ?? "");
  const [category, setCategory] = useState(initial?.category ?? "");
  const [sourceId, setSourceId] = useState<number | "">(initial?.sourceId ?? "");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = sources.find(item => item.id === sourceId);
    const label = query.trim() || categories.find(item => item.value === category)?.label || source?.name || "Mój pasek";
    onSave({ id: initial?.id ?? `${Date.now()}`, label, query: query.trim(), category, sourceId });
  }
  return <form className="sc-personal-strip-form" onSubmit={submit}>
    <p>{initial ? "EDYTUJ PASEK" : "NOWY PASEK"}</p>
    <SearchField label="Hasło lub nazwisko" value={query} onChange={setQuery} maxLength={200} placeholder="Wpisz hasło lub nazwisko" />
    <div className="sc-personal-strip-form__choices">
      <Dropdown label="Kategoria" ariaLabel="Wybierz kategorię" mode="single" presentation="auto" value={category} onChange={value => setCategory(value as string)} items={[{ value: "", label: "Wszystkie" }, ...categories.map(item => ({ value: item.value, label: item.label }))]} />
      <Dropdown label="Źródło" ariaLabel="Wybierz źródło" mode="single" presentation="auto" value={String(sourceId)} onChange={value => setSourceId(value ? Number(value) : "")} items={[{ value: "", label: "Wszystkie" }, ...sources.map(item => ({ value: String(item.id), label: item.name }))]} />
    </div>
    <div className="sc-personal-strip-form__actions"><Button type="submit" variant="primary">Pokaż materiały</Button><Button type="button" variant="quiet" onClick={onCancel}>Anuluj</Button></div>
  </form>;
}

function StripRow({ strip, editing, categories, sources, onEdit, onSave, onCancelEdit, onRemove }: {
  strip: PersonalStrip; editing: boolean; categories: CategoryOption[]; sources: Source[];
  onEdit: () => void; onSave: (strip: PersonalStrip) => void; onCancelEdit: () => void; onRemove: () => void;
}) {
  const feed = useQuery({
    queryKey: ["mvp-personal-strip", strip.query, strip.category, strip.sourceId],
    queryFn: () => getNewsFeed({ query: strip.query, categories: strip.category ? [strip.category] : [], sources: strip.sourceId ? [strip.sourceId] : [], pageSize: 20 }),
  });
  const articles = feed.data?.results ?? [];
  if (editing) return <StripForm initial={strip} categories={categories} sources={sources} onSave={onSave} onCancel={onCancelEdit} />;
  return <section className="sc-personal-strip" aria-label={`Twój przegląd Bazy: ${strip.label}`}>
    <header><h3>{strip.label}</h3><div><Button type="button" variant="quiet" size="sm" onClick={onEdit}>Edytuj</Button><Button type="button" variant="quiet" size="sm" onClick={onRemove}>Usuń pasek</Button></div></header>
    {feed.isPending ? <p role="status">Ładuję materiały…</p> : null}
    {feed.isSuccess && !articles.length ? <p>Nie znaleźliśmy jeszcze materiałów pasujących do tego wyboru.</p> : null}
    {articles.length ? <div className="sc-personal-strip__track sc-strip-bleed" aria-label={`${strip.label} — przewijaj poziomo`}>{articles.map(article => <MaterialBox key={article.id} article={article} />)}</div> : null}
  </section>;
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
    const reorderableStrips = strips.map(strip => ({ ...strip, title: strip.label }));

    return <section ref={ref} className="sc-personal-strips" aria-label="Twój przegląd">
      <header className="sc-personal-strips__head"><div><h2>Twój przegląd</h2><p>Twój lokalnie zapisany widok materiałów z Bazy</p></div>{!adding && !atLimit ? <Button type="button" variant="secondary" size="sm" onClick={openNewStrip}>Dodaj pasek</Button> : null}</header>
      {!strips.length && !adding ? <p className="sc-personal-strips__empty">Dodaj własny pasek, aby zachować wygodny przegląd interesującego Cię tematu.</p> : null}
      {adding ? <StripForm categories={categories} sources={sources} onSave={create} onCancel={() => setAdding(false)} /> : null}
      {strips.length ? <ReorderableStrips strips={reorderableStrips} storageKey="spinclinic-mvp-strips-order" label="Kolejność Twoich pasków" onReorder={next => setStrips(next.map(({ title: _title, ...strip }) => strip))} renderStrip={strip => <StripRow strip={strip} editing={editingId === strip.id} categories={categories} sources={sources} onEdit={() => { setEditingId(strip.id); setAdding(false); }} onSave={save} onCancelEdit={() => setEditingId(null)} onRemove={() => remove(strip.id)} />} /> : null}
      {atLimit ? <p className="sc-personal-strips__empty">Masz już {MAX_PERSONAL_STRIPS} pasków — usuń jeden, aby dodać kolejny.</p> : null}
    </section>;
  },
);
