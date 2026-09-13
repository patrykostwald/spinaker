"use client";
import { useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { Article, Source } from '../types';
import { useAccount, type SavedTopic } from '../lib/account';
import { apiFetch, apiWrite } from '../lib/api';
import { getNewsFeed, type CategoryOption } from '../lib/portal';
import { AccountDialog } from './AccountDialog';
import { Dialog } from './Dialog';
import { NewsStrip } from './NewsStrip';
import { MaterialFilters, type MaterialSelection } from './MaterialFilters';

function TopicStrip({ topic, onSelect, onEdit }: { topic: SavedTopic; onSelect: (article: Article) => void; onEdit: () => void }) {
  const feed = useQuery({ queryKey: ['topic-feed', topic.id, topic.query, topic.categories.join(','), topic.topics?.join(',') ?? '', topic.source_ids.join(',')], queryFn: () => getNewsFeed({ query: topic.query, categories: topic.categories, topics: topic.topics ?? [], sources: topic.source_ids, pageSize: 15 }), refetchInterval: 30_000, refetchIntervalInBackground: false });
  return <NewsStrip title={topic.label} eyebrow="Twój temat · od najnowszych publikacji" articles={feed.data?.results ?? []} loading={feed.isPending} error={feed.isError} onRetry={() => feed.refetch()} onSelect={onSelect} empty="Brak materiałów pasujących do zapisanych ustawień. Zmień hasło lub kategorie." controls={<button className="quiet-button" onClick={onEdit}>Zmień</button>} />;
}

function TopicForm({ topic, categories, topics, sources, onClose, ownerId }: { topic: SavedTopic | null; categories: CategoryOption[]; topics: CategoryOption[]; sources: Source[]; onClose: () => void; ownerId: number }) {
  const [selected, setSelected] = useState<MaterialSelection>({ categories: topic?.categories ?? [], topics: topic?.topics ?? [], sources: topic?.source_ids ?? [] });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const cache = useQueryClient();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError('');
    const data = new FormData(event.currentTarget);
    try {
      await apiWrite(topic ? `/api/account/topics/${topic.id}/` : '/api/account/topics/', {
        label: data.get('label'), query: data.get('query'), categories: selected.categories, topics: selected.topics,
        source_ids: selected.sources, ...(topic ? { position: topic.position } : {}),
      }, topic ? 'PATCH' : 'POST');
      await cache.invalidateQueries({ queryKey: ['account-topics', ownerId] });
      onClose();
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się zapisać tematu.'); }
    finally { setPending(false); }
  }
  async function remove() {
    if (!topic) return;
    setPending(true); setError('');
    try { await apiWrite(`/api/account/topics/${topic.id}/`, {}, 'DELETE'); await cache.invalidateQueries({ queryKey: ['account-topics', ownerId] }); onClose(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się usunąć tematu.'); }
    finally { setPending(false); }
  }
  return <form onSubmit={save} className="space-y-5 p-6">
    <label className="block text-sm">Nazwa paska<input required name="label" defaultValue={topic?.label ?? ''} maxLength={80} className="mt-2 block w-full rounded border bg-transparent p-3" placeholder="Mój temat" /></label>
    <label className="block text-sm">Hasło<input name="query" defaultValue={topic?.query ?? ''} maxLength={200} className="mt-2 block w-full rounded border bg-transparent p-3" placeholder="Nazwisko, wydarzenie lub zagadnienie" /></label>
    <MaterialFilters categories={categories} topics={topics} sources={sources} value={selected} onChange={setSelected} />
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    <div className="flex items-center justify-between gap-3"><button disabled={pending} className="rounded bg-primary px-5 py-3 text-sm text-white disabled:opacity-50">{pending ? 'Zapisuję…' : 'Zapisz temat'}</button>{topic && <button type="button" disabled={pending} onClick={remove} className="text-sm text-slate-400">Usuń pasek</button>}</div>
  </form>;
}

export function PersonalizedNews({ categories, topics: topicOptions, sources, onSelect }: { categories: CategoryOption[]; topics: CategoryOption[]; sources: Source[]; onSelect: (article: Article) => void }) {
  const account = useAccount();
  const ownerId = account.data?.user?.id;
  const topics = useQuery({ queryKey: ['account-topics', ownerId], queryFn: () => apiFetch<{ topics: SavedTopic[]; max_topics: number }>('/api/account/topics/'), enabled: Boolean(ownerId) });
  const [accountOpen, setAccountOpen] = useState(false);
  const [editing, setEditing] = useState<SavedTopic | null | undefined>(undefined);
  const rows = topics.data?.topics ?? [];
  const maximum = Math.min(topics.data?.max_topics ?? 10, 10);
  return <section className="personalized-news" aria-label="Twoje zapisane tematy">
    <header className="strip-heading"><div><h2>Twój kontekst</h2><p>Hasła, tematy, typy i źródła · do 10 własnych pasków</p></div>{ownerId ? <button className="quiet-button" disabled={rows.length >= maximum || topics.isPending} onClick={() => setEditing(null)}>+ Dodaj temat{rows.length ? ` · ${rows.length}/${maximum}` : ''}</button> : <button className="quiet-button" onClick={() => setAccountOpen(true)}>Dopasuj do siebie</button>}</header>
    {(!ownerId || (topics.isSuccess && !rows.length)) && <div className="news-strip-track personal-empty-track" aria-label="Miejsca na własne tematy">{[1, 2, 3, 4, 5].map(position => <div key={position} className="news-strip-item"><button className="personal-topic-placeholder" onClick={() => ownerId ? setEditing(null) : setAccountOpen(true)}><span className="placeholder-thumbnail" aria-hidden="true" /><span>+ Dodaj temat</span></button></div>)}</div>}
    {ownerId && topics.isPending && <p role="status" className="strip-empty">Ładuję Twoje tematy…</p>}
    {topics.isError && <p role="alert" className="strip-empty">Nie udało się pobrać tematów. <button onClick={() => topics.refetch()} className="text-primary">Ponów</button></p>}
    {ownerId && rows.map(topic => <TopicStrip key={topic.id} topic={topic} onSelect={onSelect} onEdit={() => setEditing(topic)} />)}
    <AccountDialog open={accountOpen} onClose={() => setAccountOpen(false)} />
    <Dialog open={editing !== undefined && Boolean(ownerId)} onClose={() => setEditing(undefined)} title={editing ? 'Zmień swój temat' : 'Dodaj swój temat'}>{editing !== undefined && ownerId && <TopicForm key={editing?.id ?? 'new'} topic={editing} categories={categories} topics={topicOptions} sources={sources} ownerId={ownerId} onClose={() => setEditing(undefined)} />}</Dialog>
  </section>;
}
