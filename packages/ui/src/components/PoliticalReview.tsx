'use client';
import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiWrite, getMe } from '../lib/api';
import { formatDateTimePl } from '../lib/utils';
import type { Paginated } from '../types';
import { ThreadEditor } from './ThreadEditor';
import { Button } from '../kit';

type Camp = 'government' | 'opposition' | 'public';

type XPost = {
  id: number; account: number; account_handle: string; account_display_name: string;
  post_id: string; url: string; text: string; published_at: string;
  camp_at_collection: Camp; available: boolean;
};

type ProposedItem = { post: number; evidence_for: string[]; evidence_against: string[]; uncertainty: string };

type XDraft = {
  id: number; camp: Camp; day: string; title: string; posts: number[]; origin: string;
  proposed_items: ProposedItem[]; notes: string;
  status: 'pending_review' | 'approved' | 'rejected';
  reviewed_by: number | null; reviewed_at: string | null; created_at: string;
};

type EvidenceDraft = { evidenceFor: string; evidenceAgainst: string; uncertainty: string };

const VIEWS = [
  { key: 'government' as const, label: 'Przekaz obozu rządzącego',
    description: 'Posty z kont potwierdzonych jako obóz rządzący. Widok pokazuje wyłącznie już zapisane posty.' },
  { key: 'opposition' as const, label: 'Przekaz opozycji',
    description: 'Posty z kont potwierdzonych jako opozycja. Widok pokazuje wyłącznie już zapisane posty.' },
  { key: 'candidates' as const, label: 'Kandydaci Dr. Spina',
    description: 'Redaktor samodzielnie wskazuje posty z dowolnego obozu do jednej propozycji.' },
];
type ViewKey = typeof VIEWS[number]['key'];

const STATUS_LABELS: Record<XDraft['status'], string> = {
  pending_review: 'Do przeglądu', approved: 'Zatwierdzony szkic (bez publikacji)', rejected: 'Odrzucony',
};

const input = 'sc-political__input';
const textarea = input;
const button = 'sc-political__button';
const primaryButton = 'sc-political__primary';

function splitLines(value: string): string[] {
  return value.split('\n').map(line => line.trim()).filter(Boolean);
}

function postsPath(view: ViewKey, camp: Camp | 'all', search: string) {
  const params = new URLSearchParams({ available: 'true' });
  if (view !== 'candidates') params.set('camp', view);
  else if (camp !== 'all') params.set('camp', camp);
  if (search.trim()) params.set('q', search.trim());
  return `/api/staff/political/posts/?${params}`;
}

function draftsPath(view: ViewKey) {
  const params = new URLSearchParams();
  if (view !== 'candidates') params.set('camp', view);
  return `/api/staff/political/drafts/?${params}`;
}

export function PoliticalReview() {
  const cache = useQueryClient();
  const me = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false });
  const isReviewer = Boolean(me.data?.can_publish);

  const [view, setView] = useState<ViewKey>('government');
  const [search, setSearch] = useState('');
  const [candidateCampFilter, setCandidateCampFilter] = useState<Camp | 'all'>('all');
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [perPost, setPerPost] = useState<Record<number, EvidenceDraft>>({});
  const [title, setTitle] = useState('');
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState('');
  const [candidateCamp, setCandidateCamp] = useState<Camp>('government');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const status = useQuery({ queryKey: ['political-status'],
    queryFn: () => apiFetch<{ draft_rules: string; publishing: string }>('/api/staff/political/status/'), enabled: isReviewer });
  const posts = useQuery({ queryKey: ['political-posts', view, candidateCampFilter, search],
    queryFn: () => apiFetch<Paginated<XPost>>(postsPath(view, candidateCampFilter, search)), enabled: isReviewer });
  const drafts = useQuery({ queryKey: ['political-drafts', view],
    queryFn: () => apiFetch<Paginated<XDraft>>(draftsPath(view)), enabled: isReviewer });

  const rows = posts.data?.results ?? [];
  const selectedPosts = useMemo(() => selectedIds
    .map(id => rows.find(row => row.id === id))
    .filter((row): row is XPost => Boolean(row)), [selectedIds, rows]);

  function toggleSelected(post: XPost) {
    setError('');
    setSelectedIds(ids => {
      if (ids.includes(post.id)) return ids.filter(id => id !== post.id);
      if (ids.length >= 15) { setError('Możesz wybrać maksymalnie 15 postów do jednej propozycji.'); return ids; }
      return [...ids, post.id];
    });
  }

  function evidenceFor(id: number): EvidenceDraft {
    return perPost[id] ?? { evidenceFor: '', evidenceAgainst: '', uncertainty: '' };
  }

  function updateEvidence(id: number, patch: Partial<EvidenceDraft>) {
    setPerPost(map => ({ ...map, [id]: { ...evidenceFor(id), ...patch } }));
  }

  function resetForm() {
    setSelectedIds([]); setPerPost({}); setTitle(''); setNotes('');
  }

  async function submitDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(''); setNotice('');
    if (!title.trim()) { setError('Podaj tytuł propozycji.'); return; }
    if (!selectedPosts.length) { setError('Wybierz co najmniej jeden post źródłowy z listy powyżej.'); return; }
    setBusy(true);
    try {
      const camp = view === 'candidates' ? candidateCamp : view;
      const proposed_items = selectedPosts.map(post => {
        const draft = evidenceFor(post.id);
        return { post: post.id, evidence_for: splitLines(draft.evidenceFor),
          evidence_against: splitLines(draft.evidenceAgainst), uncertainty: draft.uncertainty.trim() };
      });
      const path = view === 'candidates' ? '/api/staff/political/drafts/candidates/' : '/api/staff/political/drafts/';
      const created = await apiWrite<XDraft>(path,
        { camp, day, title: title.trim(), posts: selectedPosts.map(post => post.id), notes, proposed_items });
      setNotice(`Zapisano propozycję „${created.title}” — status: ${STATUS_LABELS[created.status]}. `
        + 'To wyłącznie materiał do przeglądu zespołu; nic nie zostało opublikowane.');
      resetForm();
      await cache.invalidateQueries({ queryKey: ['political-drafts', view] });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Nie udało się zapisać propozycji.');
    } finally { setBusy(false); }
  }

  if (me.isPending) return <p role="status">Sprawdzam dostęp…</p>;
  if (me.isError) return <div role="alert"><p>Nie udało się sprawdzić dostępu.</p>
    <button onClick={() => me.refetch()} className={button}>Spróbuj ponownie</button></div>;
  if (!me.data?.authenticated) return <ThreadEditor />;
  if (!isReviewer) return <section className="sc-political-access">
    <h1 className="sc-t-title-l">Panel przeglądu X</h1>
    <p className="sc-political-gap">Ten panel jest dostępny wyłącznie dla administratora / redaktora. Twoje konto nie ma tych uprawnień.</p>
  </section>;

  const activeView = VIEWS.find(item => item.key === view)!;

  return <div className="sc-political">
    <header className="sc-political__head"><p className="sc-t-caption">PANEL PRZEGLĄDU X</p>
      <h1 className="sc-t-title-l">Propozycje z już zapisanych postów X</h1>
      <p className="sc-political-copy">Panel wyłącznie przegląda materiał już pobrany i zapisany jako
        PoliticalPost. Nie łączy się z płatnym API X, nie publikuje nitek, nie pisze oskarżeń i nie ocenia prawdziwości
        postów. Zatwierdzenie propozycji w tym panelu nadal niczego nie publikuje — to osobna decyzja zespołu.</p>
    </header>

    {status.data?.draft_rules && <details className="sc-political-rules">
      <summary className="sc-political-rules-summary">Zasady przygotowania propozycji (DRAFT_RULES)</summary>
      <p className="sc-political-post-text">{status.data.draft_rules}</p>
    </details>}

    <div className="sc-political-tabs">
      {VIEWS.map(item => <button key={item.key} type="button" disabled={busy}
        onClick={() => { setView(item.key); setSelectedIds([]); setPerPost({}); setError(''); setNotice(''); }}
        className={item.key === view ? primaryButton : button}>{item.label}</button>)}
    </div>
    <p className="sc-political-copy">{activeView.description}</p>

    {error && <p role="alert" className="sc-political-message sc-political-message-error">{error}</p>}
    {notice && <p role="status" className="sc-political-message">{notice}</p>}

    <section className="sc-political-section">
      <h2 className="sc-t-title-m">1. Wybierz posty źródłowe</h2>
      <div className="sc-political-filters">
        <label className="sc-political-field">Szukaj po treści lub koncie<input type="search" value={search}
          onChange={event => setSearch(event.target.value)} placeholder="np. nazwa konta lub fraza z posta" className={input} /></label>
        {view === 'candidates' && <label className="sc-political-field">Obóz<select value={candidateCampFilter}
          onChange={event => setCandidateCampFilter(event.target.value as Camp | 'all')} className={input}>
          <option value="all">Wszystkie grupy</option><option value="government">Obóz rządzący</option><option value="opposition">Opozycja</option><option value="public">Instytucje publiczne</option>
        </select></label>}
      </div>
      {posts.isPending ? <p role="status">Ładuję zapisane posty…</p>
        : posts.isError ? <div role="alert"><p>Nie udało się pobrać postów.</p>
            <button className={button} onClick={() => posts.refetch()}>Spróbuj ponownie</button></div>
        : <div className="sc-political-list">
            {rows.map(post => <article key={post.id} className="sc-political-post">
              <input type="checkbox" className="sc-political-gap" checked={selectedIds.includes(post.id)} onChange={() => toggleSelected(post)} />
              <div className="sc-political-post-body">
                <div className="sc-political-post-meta">
                  <span>@{post.account_handle}{post.account_display_name ? ` · ${post.account_display_name}` : ''}</span>
                  <span>{post.camp_at_collection === 'government' ? 'obóz rządzący' : post.camp_at_collection === 'opposition' ? 'opozycja' : 'instytucja publiczna'}</span>
                  <span>{formatDateTimePl(post.published_at)}</span>
                </div>
                <p className="sc-political-post-text">{post.text || '(treść wycofana przez wydawcę)'}</p>
                <a href={post.url} target="_blank" rel="noopener noreferrer" className="sc-political-link">{post.url}</a>
              </div>
            </article>)}
            {!rows.length && <p className="sc-political-empty">Brak zapisanych postów pasujących do filtrów.</p>}
          </div>}
    </section>

    <form onSubmit={submitDraft} className="sc-political-form">
      <h2 className="sc-t-title-m">2. Przygotuj propozycję do przeglądu ({selectedPosts.length}/15 postów)</h2>
      <div className="sc-political-fields">
        <label className="sc-political-field">Tytuł propozycji<input required maxLength={250} value={title}
          onChange={event => setTitle(event.target.value)} className={input} disabled={busy} /></label>
        <label className="sc-political-field">Dzień<input required type="date" value={day}
          onChange={event => setDay(event.target.value)} className={input} disabled={busy} /></label>
        {view === 'candidates' && <label className="sc-political-field">Obóz propozycji (klasyfikacja redaktora)<select
          value={candidateCamp} onChange={event => setCandidateCamp(event.target.value as Camp)} className={input} disabled={busy}>
          <option value="government">Obóz rządzący</option><option value="opposition">Opozycja</option>
        </select></label>}
        <label className="sc-political-field sc-political-field--wide">Uwagi · opcjonalnie<textarea rows={2} maxLength={5000} value={notes}
          onChange={event => setNotes(event.target.value)} className={textarea} disabled={busy} /></label>
      </div>

      {selectedPosts.length > 0 && <div className="sc-political-stack">
        {selectedPosts.map(post => { const evidence = evidenceFor(post.id); return (
          <div key={post.id} className="sc-political-evidence">
            <div className="sc-political-evidence-head">
              <span>@{post.account_handle} · {formatDateTimePl(post.published_at)}</span>
              <button type="button" disabled={busy} className={button} onClick={() => toggleSelected(post)}>Usuń z propozycji</button>
            </div>
            <p className="sc-political-post-text">„{post.text}”</p>
            <a href={post.url} target="_blank" rel="noopener noreferrer" className="sc-political-link">{post.url}</a>
            <div className="sc-political-evidence-fields">
              <label className="sc-political-field sc-political-field--small">Materiały za · po jednym w linii<textarea rows={3} maxLength={5000}
                value={evidence.evidenceFor} onChange={event => updateEvidence(post.id, { evidenceFor: event.target.value })}
                className={textarea} disabled={busy} placeholder="Adres lub krótki opis materiału potwierdzającego" /></label>
              <label className="sc-political-field sc-political-field--small">Materiały przeciw · po jednym w linii<textarea rows={3} maxLength={5000}
                value={evidence.evidenceAgainst} onChange={event => updateEvidence(post.id, { evidenceAgainst: event.target.value })}
                className={textarea} disabled={busy} placeholder="Adres lub krótki opis materiału przeczącego" /></label>
              <label className="sc-political-field sc-political-field--small">Niepewność / czego nie potwierdzono<textarea rows={3} maxLength={2000}
                value={evidence.uncertainty} onChange={event => updateEvidence(post.id, { uncertainty: event.target.value })}
                className={textarea} disabled={busy} placeholder="Co pozostaje niepotwierdzone lub sporne" /></label>
            </div>
          </div>); })}
      </div>}

      <div className="sc-political-actions">
        <button type="submit" disabled={busy} className={primaryButton}>{busy ? 'Zapisuję…' : 'Zapisz jako propozycję do przeglądu'}</button>
        <button type="button" disabled={busy || !selectedPosts.length} className={button} onClick={resetForm}>Wyczyść wybór</button>
        <p className="sc-political-copy">Zapis tworzy wyłącznie szkic ze statusem „Do przeglądu”. Nie publikuje nitki i nie ocenia prawdziwości postów.</p>
      </div>
    </form>

    <section className="sc-political-section">
      <h2 className="sc-t-title-m">Ostatnie propozycje w tym widoku</h2>
      {drafts.isPending ? <p role="status">Ładuję listę propozycji…</p>
        : drafts.isError ? <p role="alert">Nie udało się pobrać listy propozycji.</p>
        : <div className="sc-political-list">
            {drafts.data?.results.map(item => <article key={item.id} className="sc-political-draft">
              <div className="sc-political-draft-head">
                <span className="sc-political-draft-title">{item.title}</span>
                <span className="sc-political-copy">{STATUS_LABELS[item.status]}</span>
              </div>
              <p className="sc-political-copy">{item.day} · {item.camp === 'government' ? 'obóz rządzący' : 'opozycja'} ·
                {' '}{item.posts.length} {item.posts.length === 1 ? 'post' : 'postów'} · {item.origin === 'ai_proposal' ? 'propozycja AI' : 'wybór zespołu'}</p>
            </article>)}
            {!drafts.data?.results.length && <p className="sc-political-empty">Brak propozycji w tym widoku.</p>}
          </div>}
    </section>
  </div>;
}


