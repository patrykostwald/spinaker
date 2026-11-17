"use client";

import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiWrite } from '../lib/api';
import { emailVerified, TERMS_VERSION, useAccount } from '../lib/account';
import { accountMessage } from '../lib/accountPhase2';
import { AccountDataState, VerifyEmailNotice } from './AccountPhase2';
import { getNewsFeed } from '../lib/portal';
import { searchClinicSpins } from '../lib/clinic';
import { formatDateTimePl } from '../lib/utils';
import { MAX_THREAD_ARTICLES, THREAD_LIMITS, deletePersonalThread, personalKeys, savePersonalThread,
  useArticleFavorites, useOwnerId, type PersonalArticleRef, type PersonalContextThread } from '../lib/personal';
import { getCommunityThread, resolveLink, type ThreadElement } from '../lib/community';
import { Button } from '../kit';
import { CharacterCount } from './community/SocialPrimitives';
import { SignedOutPanel } from './MojeKonto';
import { XPostCard } from './community/XPostCard';
import { Loading } from "../kit/Loading";
import { Glyph } from './community/ThreadSteps';
import { READER_KINDS, THREAD_KINDS, type ThreadKind } from '../lib/threadKind';

type Box = { key: string; material: ThreadElement | null; note: string; link_note: string };
type Draft = { kind: ThreadKind; title: string; items: Box[]; isPublic: boolean };
// wyjaśnienie autora = „tytuł” boksu; może być długie (właściciel 3.10)
const NOTE_LIMIT = 4000;
const LINK_NOTE_LIMIT = 200;
const MIN_PUBLIC_ITEMS = 2;
const blankBox = (key: string): Box => ({ key, material: null, note: '', link_note: '' });
const initialDraft = (): Draft => ({ kind: 'kontekst', title: '', items: [blankBox('first')], isPublic: false });
const serialize = (draft: Draft) => JSON.stringify(draft);
const withoutFirstLink = (items: Box[]) => items.map((item, index) => index === 0 ? { ...item, link_note: '' } : item);

function articleElement(article: PersonalArticleRef): ThreadElement {
  return { ...article, kind: 'article', source_name: article.source_name ?? '', note: '', link_note: '', position: 0 };
}

function fromThread(thread: PersonalContextThread): Draft {
  const elements = thread.elements ?? thread.articles.map(articleElement);
  const items = [...elements].sort((a, b) => a.position - b.position).map(element => ({
    key: `${element.kind}:${element.id}`, material: element, note: element.note ?? '', link_note: element.link_note ?? '',
  }));
  const kind = READER_KINDS.includes(thread.kind as ThreadKind) ? thread.kind as ThreadKind : 'kontekst';
  return { kind, title: thread.title, isPublic: Boolean(thread.is_public), items: items.length ? withoutFirstLink(items) : [blankBox('first')] };
}

function domain(url: string) {
  try { const parsed = new URL(url); return ['https:', 'http:'].includes(parsed.protocol) ? parsed.hostname : ''; }
  catch { return ''; }
}

/** A native modal keeps the page inert and restores focus on close. */
function PublishDialog({ onClose, children, footer }: { onClose: () => void; children: ReactNode; footer: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current!;
    const trigger = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = 'hidden';
    return () => { dialog.close(); document.body.style.overflow = overflow; trigger?.focus(); };
  }, []);
  return <dialog ref={ref} className="sc-f2-editor-dialog" aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <div className="sc-f2-dialog-panel">
      <header><h2 id={titleId}>Publikacja spinki</h2><Button type="button" variant="ghost" onClick={onClose}>Zamknij</Button></header>
      <div className="sc-f2-dialog-body">{children}</div>
      <footer>{footer}</footer>
    </div>
  </dialog>;
}

function MaterialPicker({ selected, onSelect }: { selected: Set<string>; onSelect: (element: ThreadElement) => void }) {
  const searchId = useId();
  const [mode, setMode] = useState<'base' | 'spin' | 'link'>('base');
  const [search, setSearch] = useState('');
  const [term, setTerm] = useState('');
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [needsTitle, setNeedsTitle] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const favorites = useArticleFavorites();
  const results = useQuery({ queryKey: ['personal-thread-search', term],
    queryFn: () => getNewsFeed({ query: term, match: 'words', pageSize: 8 }), enabled: mode === 'base' && term.length > 1, staleTime: 30_000 });
  // Diagnoza jako boks (właściciel 3.10): wyszukiwanie w opublikowanych diagnozach, boks to link do karty diagnozy
  const spins = useQuery({ queryKey: ['personal-thread-spins', term],
    queryFn: () => searchClinicSpins({ q: term }), enabled: mode === 'spin', staleTime: 30_000 });
  async function addLink(target = url.trim(), label = title.trim()) {
    if (pending) return;
    setPending(true); setMessage('');
    try {
      const result = await resolveLink(target, label);
      if ('needsTitle' in result) { setNeedsTitle(true); setMessage(result.message); return; }
      if (selected.has(`${result.item.kind}:${result.item.id}`)) { setMessage('Ten materiał jest już w spince.'); return; }
      onSelect({ ...result.item, note: '', link_note: '', position: 0 } as ThreadElement);
    } catch (reason) { setMessage(accountMessage(reason)); }
    finally { setPending(false); }
  }
  const candidates = (rows: PersonalArticleRef[]) => <ul className="sc-simple-thread__results">{rows.map(article => (
    <li key={article.id}><span title={article.title}>{article.title}</span>
      <Button type="button" variant="quiet" size="sm" disabled={selected.has(`article:${article.id}`)} onClick={() => onSelect(articleElement(article))}>
        {selected.has(`article:${article.id}`) ? 'Dodano' : 'Wybierz'}<span className="sr-only">: {article.title}</span>
      </Button></li>
  ))}</ul>;
  return <div className="sc-simple-thread__picker">
    <fieldset disabled={pending}><legend>Co dodajesz?</legend><div className="sc-simple-thread__actions">
      <Button type="button" variant={mode === 'base' ? 'primary' : 'quiet'} aria-pressed={mode === 'base'} onClick={() => setMode('base')}>Z bazy</Button>
      <Button type="button" variant={mode === 'spin' ? 'primary' : 'quiet'} aria-pressed={mode === 'spin'} onClick={() => setMode('spin')}>Diagnoza</Button>
      <Button type="button" variant={mode === 'link' ? 'primary' : 'quiet'} aria-pressed={mode === 'link'} onClick={() => setMode('link')}>Link / zdjęcie / film</Button>
    </div></fieldset>
    {mode === 'base' ? <>
      <label htmlFor={searchId} className="sr-only">Szukaj materiału w bazie</label><div className="sc-simple-thread__actions">
        <input id={searchId} type="search" value={search} placeholder="Szukaj w bazie: tytuł, hasło, osoba" onChange={event => setSearch(event.target.value)}
          onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); setTerm(search.trim()); } }} />
        <Button type="button" variant="quiet" disabled={search.trim().length < 2} onClick={() => setTerm(search.trim())}>Szukaj</Button>
      </div>
      {results.isFetching && <p role="status">Szukam w bazie…</p>}
      {results.isError && <p role="alert">Nie udało się przeszukać bazy. <button type="button" onClick={() => results.refetch()}>Spróbuj ponownie</button></p>}
      {results.isSuccess && !results.data.results.length && <p role="status">Brak materiałów dla „{term}”.</p>}
      {results.data && candidates(results.data.results.map(article => ({ ...article, source_name: article.source?.name })))}
      {Boolean(favorites.data?.results.length) && <details><summary>Z ulubionych materiałów</summary>{candidates(favorites.data!.results.map(row => row.article))}</details>}
    </> : mode === 'spin' ? <>
      <label htmlFor={searchId} className="sr-only">Szukaj diagnozy wpisu albo spinu</label><div className="sc-simple-thread__actions">
        <input id={searchId} type="search" value={search} placeholder="Szukaj diagnozy: polityk, temat (puste: najnowsze)" onChange={event => setSearch(event.target.value)}
          onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); setTerm(search.trim()); } }} />
        <Button type="button" variant="quiet" onClick={() => setTerm(search.trim())}>Szukaj</Button>
      </div>
      {spins.isFetching && <p role="status">Szukam diagnoz…</p>}
      {spins.isError && <p role="alert">Nie udało się przeszukać diagnoz. <button type="button" onClick={() => spins.refetch()}>Spróbuj ponownie</button></p>}
      {spins.isSuccess && !spins.data.results.length && <p role="status">Brak diagnoz dla „{term}”.</p>}
      {spins.data && <ul className="sc-simple-thread__results">{spins.data.results.slice(0, 8).map(spin => (
        <li key={spin.id}><span title={spin.headline}>{spin.headline} · {spin.intensity}/100</span>
          <Button type="button" variant="quiet" size="sm" onClick={() => void addLink(`https://spin.clinic/klinika/${spin.id}`, `Diagnoza: ${spin.headline}`)}>
            Wybierz<span className="sr-only">: {spin.headline}</span>
          </Button></li>
      ))}</ul>}
      {message && <p role="status">{message}</p>}
    </> : <>
      <label>Adres URL<input type="url" inputMode="url" maxLength={1024} value={url} placeholder="https://" disabled={pending}
        onChange={event => { setUrl(event.target.value); setNeedsTitle(false); setMessage(''); }}
        onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); if (domain(url)) void addLink(); } }} /></label>
      <p className="sc-simple-thread__domain">{domain(url) ? `Domena: ${domain(url)}` : 'Wklej adres strony, zdjęcia lub filmu, np. z YouTube, X albo Instagrama.'}</p>
      <small>Zdjęcia i filmy dodajesz przez URL. Materiał otworzy się na stronie źródła.</small>
      {needsTitle && <label>Tytuł materiału<input value={title} maxLength={300} disabled={pending} onChange={event => setTitle(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); if (title.trim()) void addLink(); } }} /></label>}
      <Button type="button" variant="quiet" loading={pending} disabled={pending || !domain(url) || (needsTitle && !title.trim())} onClick={() => void addLink()}>Dodaj link</Button>
      {message && <p role="status">{message}</p>}
    </>}
  </div>;
}

/** Wybór rodzaju spinki: grupa przełączników (strzałki zmieniają wybór), cele co najmniej 44 px (prawo Fittsa). */
function KindPicker({ value, locked, onChange }: { value: ThreadKind; locked: boolean; onChange: (kind: ThreadKind) => void }) {
  const legend = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  function key(event: React.KeyboardEvent, index: number) {
    const step = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + READER_KINDS.length) % READER_KINDS.length;
    onChange(READER_KINDS[next]); refs.current[next]?.focus();
  }
  return <fieldset className="sc-kind-pick" disabled={locked}>
    <legend id={legend}>Jaką spinkę układasz?</legend>
    <div className="sc-kind-pick__grid" role="radiogroup" aria-labelledby={legend}>
      {READER_KINDS.map((kind, index) => <button key={kind} ref={node => { refs.current[index] = node; }} type="button" role="radio" className="sc-kind-pick__opt"
        aria-checked={value === kind} tabIndex={value === kind ? 0 : -1} onClick={() => onChange(kind)} onKeyDown={event => key(event, index)}>
        <Glyph name={THREAD_KINDS[kind].glyph} size={24} /><b>{THREAD_KINDS[kind].label}</b><small>{THREAD_KINDS[kind].hint}</small>
      </button>)}
    </div>
    <p className="sc-kind-pick__note">{locked ? 'Rodzaj opublikowanej spinki jest stały.' : 'Rodzaj zmienisz do chwili publikacji. Widać go nad tytułem.'}</p>
  </fieldset>;
}

export function MojaNitkaEditor({ threadId, counterTo }: { threadId?: number; counterTo?: number }) {
  const { account, ownerId } = useOwnerId();
  if (account.isPending) return <p role="status" className="sc-account-empty">Sprawdzam logowanie…</p>;
  if (account.isError) return <div className="sc-account"><AccountDataState query={account} empty="Konta będą dostępne wkrótce." /></div>;
  if (!ownerId) return <SignedOutPanel title="Zaloguj się, aby ułożyć własną spinkę" />;
  return <Editor key={`${ownerId}:${threadId ?? 'new'}:${counterTo ?? ''}`} ownerId={ownerId} threadId={threadId} counterTo={threadId ? undefined : counterTo} />;
}

function Editor({ ownerId, threadId, counterTo }: { ownerId: number; threadId?: number; counterTo?: number }) {
  const uid = useId();
  const router = useRouter();
  const cache = useQueryClient();
  const account = useAccount();
  const thread = useQuery({ queryKey: personalKeys.thread(ownerId, threadId ?? 0),
    queryFn: () => apiFetch<PersonalContextThread>(`/api/account/context-threads/${threadId}/`), enabled: Boolean(threadId), retry: false });
  const [draft, setDraft] = useState<Draft>(initialDraft);
  const [saved, setSaved] = useState(() => serialize(initialDraft()));
  const [initialized, setInitialized] = useState(!threadId);
  const [activeId, setActiveId] = useState(threadId);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [publishOpen, setPublishOpen] = useState(false);
  const [terms, setTerms] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const saving = useRef(false);
  const failedSnapshot = useRef('');
  const nextKey = useRef(0);
  const headings = useRef(new Map<string, HTMLHeadingElement>());
  const focusKey = useRef<string | null>(null);
  const dirty = serialize(draft) !== saved;
  const complete = draft.items.every(item => item.material);
  const emptyDraft = draft.items.length === 1 && !draft.items[0].material && !draft.items[0].note && !draft.items[0].link_note;
  const selected = new Set(draft.items.flatMap(item => item.material ? [`${item.material.kind}:${item.material.id}`] : []));

  // kontraspinka: te same materiały co w spince, którą czytelnik chce ułożyć po swojemu (bez cudzych wyjaśnień)
  const counter = useQuery({ queryKey: ['community-thread', String(counterTo)], queryFn: () => getCommunityThread(counterTo!), enabled: Boolean(counterTo), retry: false });
  const counterDone = useRef(false);
  useEffect(() => {
    if (!counter.data || counterDone.current) return;
    counterDone.current = true;
    const items = [...counter.data.items].sort((a, b) => a.position - b.position)
      .slice(0, MAX_THREAD_ARTICLES).map(element => ({ key: `${element.kind}:${element.id}`, material: { ...element, note: '', link_note: '' }, note: '', link_note: '' }));
    setDraft(current => ({ ...current, title: `Kontraspinka: ${counter.data!.title}`.slice(0, THREAD_LIMITS.title), items: items.length ? items : current.items }));
  }, [counter.data]);
  useEffect(() => {
    if (thread.data && !initialized) { const next = fromThread(thread.data); setDraft(next); setSaved(serialize(next)); setInitialized(true); }
  }, [thread.data, initialized]);
  useEffect(() => {
    if (focusKey.current) { headings.current.get(focusKey.current)?.focus(); focusKey.current = null; }
  }, [draft.items]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    const link = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest?.('a');
      if (!anchor || anchor.target === '_blank' || event.ctrlKey || event.metaKey || anchor.getAttribute('href')?.startsWith('#')) return;
      if (!window.confirm('Masz niezapisane zmiany. Opuścić edytor?')) { event.preventDefault(); event.stopPropagation(); }
    };
    window.addEventListener('beforeunload', warn); document.addEventListener('click', link, true);
    return () => { window.removeEventListener('beforeunload', warn); document.removeEventListener('click', link, true); };
  }, [dirty]);
  useEffect(() => {
    if (!initialized || !dirty || !draft.title.trim() || (!complete && !emptyDraft) || draft.isPublic || pending || failedSnapshot.current === serialize(draft)) return;
    const timer = window.setTimeout(() => { void persist(false, true); }, 1200);
    return () => window.clearTimeout(timer);
  }, [draft, dirty, initialized, pending, activeId, complete, emptyDraft]);

  function updateBox(key: string, patch: Partial<Box>) {
    setDraft(current => ({ ...current, items: withoutFirstLink(current.items.map(item => item.key === key ? { ...item, ...patch } : item)) }));
    setNotice('');
  }
  function addBox() {
    if (draft.items.length >= MAX_THREAD_ARTICLES || !complete) return;
    const key = `new:${++nextKey.current}`;
    focusKey.current = key;
    setDraft(current => ({ ...current, items: [...current.items, blankBox(key)] }));
  }
  function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= draft.items.length) return;
    const items = [...draft.items];
    [items[index], items[target]] = [items[target], items[index]];
    focusKey.current = items[target].key;
    setDraft(current => ({ ...current, items: withoutFirstLink(items) }));
    setNotice(`Przesunięto boks na pozycję ${target + 1}. Sprawdź powiązania.`);
  }
  function removeBox(key: string) {
    const index = draft.items.findIndex(item => item.key === key);
    const remaining = draft.items.filter(item => item.key !== key);
    const items = remaining.length ? withoutFirstLink(remaining) : [blankBox(`new:${++nextKey.current}`)];
    focusKey.current = items[Math.min(index, items.length - 1)].key;
    setDraft(current => ({ ...current, items }));
    setNotice('Usunięto boks. Sprawdź powiązania.');
  }
  async function persist(makePublic: boolean, automatic = false) {
    if (saving.current) return;
    if (!draft.title.trim()) { setError('Podaj tytuł spinki.'); return; }
    if (!complete && (makePublic || !emptyDraft)) { setError('Wybierz materiał w każdym boksie albo usuń pusty boks.'); return; }
    if (makePublic && thread.data?.hidden_at) { setError('Spinka jest ukryta przez zespół po zgłoszeniu.'); return; }
    if (makePublic && (!publishOpen || !terms || !emailVerified(account.data))) { setError('Potwierdź e-mail i Zasady w oknie publikacji.'); return; }
    if (makePublic && draft.items.length < MIN_PUBLIC_ITEMS) { setError('Do publikacji dodaj co najmniej dwa materiały.'); return; }
    const snapshot = { ...draft, isPublic: makePublic };
    saving.current = true; setPending(true); setError(''); setNotice('');
    try {
      if (makePublic) await apiWrite('/api/account/me/', { accepted_terms_version: TERMS_VERSION }, 'PATCH');
      const previous = thread.data;
      const result = await savePersonalThread({ kind: draft.kind, title: draft.title.trim(),
        description: previous?.description ?? '', query: previous?.query ?? '', categories: previous?.categories ?? [],
        topics: previous?.topics ?? [], source_ids: previous?.source_ids ?? [],
        items: draft.items.filter(item => item.material).map((item, index) => ({
          ...(item.material!.kind === 'article' ? { article_id: item.material!.id } : { link_id: item.material!.id }),
          note: item.note.trim(), link_note: index ? item.link_note.trim() : '',
        })), is_public: makePublic }, activeId);
      setSaved(serialize(snapshot));
      setDraft(current => ({ ...current, isPublic: makePublic }));
      setActiveId(result.id);
      if (makePublic) setPublishOpen(false);
      cache.setQueryData(personalKeys.thread(ownerId, result.id), result);
      await cache.invalidateQueries({ queryKey: personalKeys.threads(ownerId) });
      if (makePublic) {
        await cache.invalidateQueries({ queryKey: ['community-threads'] });
        await cache.invalidateQueries({ queryKey: ['community-thread', String(result.id)] });
      }
      setNotice(`Zapisano ${formatDateTimePl(result.updated_at)}. ${!result.is_public ? 'Szkic jest prywatny.' : result.admitted_at ? 'Spinka jest publiczna.' : 'Spinka jest w izbie przyjęć: trafi na główną listę po pierwszym komentarzu lub reakcji innej osoby.'}`);
      if (!activeId) window.history.replaceState(window.history.state, '', `/konto/spinki/${result.id}`);
      return result.id;
    } catch (reason) { if (automatic) failedSnapshot.current = serialize(draft); setError(accountMessage(reason)); }
    finally { saving.current = false; setPending(false); }
  }
  async function continueThread() {
    if (dirty || !activeId) { setError('Zapisz spinkę przed ułożeniem kontynuacji.'); return; }
    const last = draft.items.at(-1)?.material;
    if (!last || pending) return;
    setPending(true); setError('');
    try {
      const next = await savePersonalThread({ title: ('Kontynuacja: ' + draft.title).slice(0, 65), description: '', query: '', categories: [], source_ids: [], continues: activeId,
        items: [{ ...(last.kind === 'article' ? { article_id: last.id } : { link_id: last.id }), note: draft.items.at(-1)?.note ?? '', link_note: '' }], is_public: false });
      router.push(`/konto/spinki/${next.id}`);
    } catch (e) { setError(accountMessage(e)); } finally { setPending(false); }
  }
  async function removeThread() {
    if (!activeId || saving.current) return;
    saving.current = true; setPending(true); setError('');
    try { await deletePersonalThread(activeId); await cache.invalidateQueries({ queryKey: personalKeys.threads(ownerId) }); router.push('/konto#moje-tropy'); }
    catch (reason) { setError(accountMessage(reason)); saving.current = false; setPending(false); }
  }
  function submit(event: FormEvent) { event.preventDefault(); setError(''); setPublishOpen(true); }
  if (threadId && thread.isPending) return <p role="status" className="sc-account-empty"><Loading label="Ładuję spinka" /></p>;
  if (threadId && thread.isError) return <div className="sc-account"><AccountDataState query={thread} empty="Nie znaleziono spinki." /></div>;

  return <form className="sc-account sc-simple-thread" onSubmit={submit} noValidate aria-label="Kreator spinki">
    {/* na starcie rodzaj spinki (właściciel 6.10): duże przyciski z ikoną i jednym zdaniem, domyślnie kontekst;
        można zmienić do publikacji, potem rodzaj jest częścią spinki */}
    <KindPicker value={draft.kind} locked={draft.isPublic} onChange={kind => setDraft(current => ({ ...current, kind }))} />
    <label className="sc-simple-thread__title">Tytuł spinki
      <input value={draft.title} maxLength={THREAD_LIMITS.title} required placeholder="O czym chcesz opowiedzieć?"
        onChange={event => setDraft(current => ({ ...current, title: event.target.value }))} />
      <CharacterCount text={draft.title} limit={THREAD_LIMITS.title} />
    </label>
    <ol className="sc-simple-thread__boxes" aria-label="Boksy spinki">
      {draft.items.map((item, index) => <li key={item.key} className="sc-simple-thread__box">
        <header><h2 tabIndex={-1} ref={node => { if (node) headings.current.set(item.key, node); else headings.current.delete(item.key); }}>Boks {index + 1}</h2>
          <div className="sc-simple-thread__actions">
            <button type="button" aria-label={`Przesuń boks ${index + 1} w górę`} disabled={index === 0} onClick={() => move(index, -1)}>↑</button>
            <button type="button" aria-label={`Przesuń boks ${index + 1} w dół`} disabled={index === draft.items.length - 1} onClick={() => move(index, 1)}>↓</button>
            <button type="button" aria-label={`Usuń boks ${index + 1}`} onClick={() => removeBox(item.key)}>Usuń</button>
          </div>
        </header>
        {index > 0 && <label>Powiązanie z poprzednim
          <textarea rows={2} maxLength={LINK_NOTE_LIMIT} value={item.link_note} aria-describedby={`${uid}-${item.key}-link-count`}
            placeholder="Dlaczego ten materiał łączy się z poprzednim?" onChange={event => updateBox(item.key, { link_note: event.target.value })} />
          <small className="sc-social-count" data-near={item.link_note.length >= LINK_NOTE_LIMIT * .9} id={`${uid}-${item.key}-link-count`}>{item.link_note.length}/{LINK_NOTE_LIMIT} · Opcjonalne. Pomóż czytelnikom połączyć materiały.</small>
        </label>}
        {item.material ? <div className="sc-simple-thread__material">
          {item.material.box_type === 'post' ? <XPostCard item={item.material} /> : <>
          <p className="sc-simple-thread__domain">{item.material.kind === 'article' ? 'Z bazy' : 'Spoza bazy'} · {domain(item.material.url)}</p>
          <p className="sc-simple-thread__material-title"><a href={item.material.url} title={item.material.title} target="_blank" rel="noopener noreferrer">{item.material.title}</a></p>
          </>}
          <button type="button" onClick={() => updateBox(item.key, { material: null })}>Zmień materiał</button>
        </div> : <MaterialPicker selected={selected} onSelect={material => { focusKey.current = item.key; updateBox(item.key, { material }); }} />}
        {item.material && <label>Komentarz
          <textarea rows={4} maxLength={NOTE_LIMIT} value={item.note} placeholder="Twoje wyjaśnienie: dlaczego ten materiał jest w spince? To będzie tytuł boksu. Możesz napisać krótko albo dłużej."
            aria-describedby={`${uid}-${item.key}-note-count`} onChange={event => updateBox(item.key, { note: event.target.value })} />
          <small className="sc-social-count" data-near={item.note.length >= NOTE_LIMIT * .9} id={`${uid}-${item.key}-note-count`}>{item.note.length}/{NOTE_LIMIT}</small>
        </label>}
      </li>)}
    </ol>
    <div className="sc-simple-thread__actions">
      {draft.items.length >= MAX_THREAD_ARTICLES ? <div><p>To maksimum jednej spinki. Możesz ułożyć kolejną i połączyć ją z tą.</p><Button type="button" variant="quiet" disabled={pending || !complete || dirty || !activeId} onClick={continueThread}>Ułóż kontynuację</Button>{dirty && <small>Zapisz zmiany, aby ułożyć kontynuację.</small>}</div> : <Button type="button" variant="quiet" disabled={!complete} onClick={addBox}>Dodaj kolejny</Button>}
      <Button type="submit" variant="primary" disabled={pending}>{draft.isPublic ? 'Zapisz zmiany' : 'Opublikuj'}</Button>
    </div>
    <small>{draft.items.length}/{MAX_THREAD_ARTICLES} boksów. Do publikacji potrzebujesz co najmniej dwóch materiałów.</small>
    {thread.data?.hidden_at && <p role="alert">Spinka jest ukryta przez zespół po zgłoszeniu.</p>}
    {error && <p role="alert" className="sc-account-error">{error}</p>}
    <p role="status">{pending ? 'Zapisuję…' : notice || (dirty ? 'Masz niezapisane zmiany.' : activeId ? 'Wszystkie zmiany zapisane.' : 'Szkic zapisuje się automatycznie po wpisaniu tytułu.')}</p>
    <div className="sc-simple-thread__actions">
      {!draft.isPublic && <Button type="button" variant="ghost" disabled={pending} onClick={() => persist(false)}>Zapisz szkic</Button>}
      {draft.isPublic && activeId && <Link href={`/spinki/${activeId}`}>Otwórz spinkę</Link>}
      <Link href="/konto#moje-tropy">Moje konto</Link>
      {activeId && (confirmDelete ? <>
        <Button type="button" variant="quiet" disabled={pending} onClick={removeThread}>Potwierdź usunięcie spinki</Button>
        <Button type="button" variant="ghost" onClick={() => setConfirmDelete(false)}>Anuluj</Button>
      </> : <Button type="button" variant="ghost" disabled={pending} onClick={() => setConfirmDelete(true)}>Usuń spinkę</Button>)}
    </div>
    {publishOpen && <PublishDialog onClose={() => { if (!pending) setPublishOpen(false); }} footer={<>
      <Button type="button" variant="ghost" disabled={pending} onClick={() => setPublishOpen(false)}>Anuluj</Button>
      <Button type="button" variant="primary" loading={pending}
        disabled={pending || !complete || !draft.title.trim() || !terms || !emailVerified(account.data) || draft.items.length < MIN_PUBLIC_ITEMS || Boolean(thread.data?.hidden_at)}
        onClick={() => persist(true)}>{draft.isPublic ? 'Zapisz zmiany' : 'Opublikuj spinkę'}</Button>
    </>}>
      <p>„{draft.title}” · {draft.items.length} boksów. Tytuł, komentarze i powiązania będą publiczne pod nazwą @{account.data?.user?.username}.</p>
      <VerifyEmailNotice />
      <label className="sc-f2-check"><input type="checkbox" checked={terms} onChange={event => setTerms(event.target.checked)} /><span>Potwierdzam <Link href="/zasady-korzystania" target="_blank">Zasady korzystania</Link> (wersja {TERMS_VERSION}). Nie publikuję danych prywatnych ani treści naruszających prawa innych.</span></label>
      {!draft.title.trim() && <p>Podaj tytuł spinki.</p>}
      {!complete && <p>Wybierz materiał w każdym boksie albo usuń pusty boks.</p>}
      {draft.items.length < MIN_PUBLIC_ITEMS && <p>Do publikacji dodaj co najmniej dwa materiały.</p>}
      {error && <p role="alert">{error}</p>}
    </PublishDialog>}
  </form>;
}
