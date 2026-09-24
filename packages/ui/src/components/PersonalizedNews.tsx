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
import { Button, SearchField } from '../kit';

function TopicStrip({ topic, onSelect, onEdit }: { topic: SavedTopic; onSelect: (article: Article) => void; onEdit: () => void }) {
  const feed = useQuery({ queryKey: ['topic-feed', topic.id, topic.query, topic.categories.join(','), topic.topics?.join(',') ?? '', topic.source_ids.join(',')], queryFn: () => getNewsFeed({ query: topic.query, categories: topic.categories, topics: topic.topics ?? [], sources: topic.source_ids, pageSize: 15 }), refetchInterval: 30_000, refetchIntervalInBackground: false });
  return <NewsStrip title={topic.label} eyebrow="Twój temat · od najnowszych publikacji" articles={feed.data?.results ?? []} loading={feed.isPending} error={feed.isError} onRetry={() => feed.refetch()} onSelect={onSelect} empty="Brak materiałów pasujących do zapisanych ustawień. Zmień hasło lub kategorie." controls={<Button size="sm" variant="quiet" onClick={onEdit}>Zmień</Button>} />;
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
  const [label, setLabel] = useState(topic?.label ?? '');
  const [query, setQuery] = useState(topic?.query ?? '');
  return <form onSubmit={save} className="sc-saved-topic-form">
    <SearchField required name="label" value={label} onChange={setLabel} maxLength={80} label="Nazwa paska" placeholder="Mój temat" />
    <SearchField name="query" value={query} onChange={setQuery} maxLength={200} label="Hasło" placeholder="Nazwisko, wydarzenie lub zagadnienie" />
    <MaterialFilters categories={categories} topics={topics} sources={sources} value={selected} onChange={setSelected} />
    {error && <p role="alert" className="sc-saved-topic-form__error">{error}</p>}
    <div className="sc-saved-topic-form__actions"><Button type="submit" variant="primary" loading={pending}>{pending ? 'Zapisuję…' : 'Zapisz temat'}</Button>{topic && <Button type="button" disabled={pending} onClick={remove} variant="quiet">Usuń pasek</Button>}</div>
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
  return <section className="sc-saved-topics" aria-label="Twoje zapisane tematy">
    <header className="sc-saved-topics__head"><div><h2 className="sc-t-title-m">Twój kontekst</h2><p className="sc-t-body sc-text-2">Hasła, tematy, typy i źródła · do 10 własnych pasków</p></div>{ownerId ? <Button size="sm" variant="secondary" disabled={rows.length >= maximum || topics.isPending} onClick={() => setEditing(null)}>Dodaj temat{rows.length ? ` · ${rows.length}/${maximum}` : ''}</Button> : <Button size="sm" variant="secondary" onClick={() => setAccountOpen(true)}>Dopasuj do siebie</Button>}</header>
    {(!ownerId || (topics.isSuccess && !rows.length)) && <div className="sc-saved-topics__empty" aria-label="Miejsca na własne tematy">{[1, 2, 3].map(position => <Button key={position} type="button" variant="quiet" className="sc-saved-topics__placeholder" onClick={() => ownerId ? setEditing(null) : setAccountOpen(true)}>Dodaj temat</Button>)}</div>}
    {ownerId && topics.isPending && <p role="status" className="sc-saved-topics__status">Ładuję Twoje tematy…</p>}
    {topics.isError && <p role="alert" className="sc-saved-topics__status">Nie udało się pobrać tematów. <Button onClick={() => topics.refetch()} size="sm" variant="quiet">Ponów</Button></p>}
    {ownerId && rows.map(topic => <TopicStrip key={topic.id} topic={topic} onSelect={onSelect} onEdit={() => setEditing(topic)} />)}
    <AccountDialog open={accountOpen} onClose={() => setAccountOpen(false)} />
    <Dialog open={editing !== undefined && Boolean(ownerId)} onClose={() => setEditing(undefined)} title={editing ? 'Zmień swój temat' : 'Dodaj swój temat'}>{editing !== undefined && ownerId && <TopicForm key={editing?.id ?? 'new'} topic={editing} categories={categories} topics={topicOptions} sources={sources} ownerId={ownerId} onClose={() => setEditing(undefined)} />}</Dialog>
  </section>;
}
