"use client";

import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { getNewsFeed, getPortalConfig } from '../lib/portal';
import { categoryLabel, formatDateTimePl } from '../lib/utils';
import {
  MAX_THREAD_ARTICLES,
  THREAD_LIMITS,
  deletePersonalThread,
  isUnavailable,
  joinKeywords,
  personalKeys,
  savePersonalThread,
  splitKeywords,
  useArticleFavorites,
  useOwnerId,
  type PersonalArticleRef,
  type PersonalContextThread,
} from '../lib/personal';
import { resolveLink, type ThreadElement } from '../lib/community';
import type { Article } from '../types';
import { Button } from '../kit';
import { SignedOutPanel } from './MojeKonto';

/** Element nitki w edytorze: materiał z Bazy albo link spoza Bazy, zawsze z (opcjonalną) notatką. */
type EditorItem = {
  key: string;
  kind: 'article' | 'link';
  id: number;
  title: string;
  url: string;
  category?: string;
  published_date?: string | null;
  source_name?: string;
  domain?: string;
  note: string;
};
type Draft = { title: string; description: string; keywords: string[]; categories: string[]; sourceIds: number[]; items: EditorItem[]; isPublic: boolean };
const EMPTY: Draft = { title: '', description: '', keywords: [], categories: [], sourceIds: [], items: [], isPublic: false };
const NOTE_LIMIT = 280;
const MIN_PUBLIC_ITEMS = 2;

function fromElement(element: ThreadElement): EditorItem {
  return element.kind === 'article'
    ? { key: `a:${element.id}`, kind: 'article', id: element.id, title: element.title, url: element.url, category: element.category, published_date: element.published_date, source_name: element.source_name, note: element.note }
    : { key: `l:${element.id}`, kind: 'link', id: element.id, title: element.title, url: element.url, domain: element.domain, note: element.note };
}

function articleItem(article: PersonalArticleRef): EditorItem {
  return { key: `a:${article.id}`, kind: 'article', id: article.id, title: article.title, url: article.url, category: article.category, published_date: article.published_date, source_name: article.source_name, note: '' };
}

function fromThread(thread: PersonalContextThread): Draft {
  const items = thread.elements
    ? [...thread.elements].sort((a, b) => a.position - b.position).map(fromElement)
    : [...thread.articles].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)).map(articleItem);
  return {
    title: thread.title,
    description: thread.description,
    keywords: splitKeywords(thread.query),
    categories: thread.categories,
    sourceIds: thread.source_ids,
    items,
    isPublic: Boolean(thread.is_public),
  };
}

function toRef(article: Article): PersonalArticleRef {
  return { id: article.id, title: article.title, url: article.url, category: article.category, published_date: article.published_date, source_name: article.source?.name };
}

const serialize = (draft: Draft) => JSON.stringify({ ...draft, items: draft.items.map(item => [item.key, item.note]) });

export function MojaNitkaEditor({ threadId }: { threadId?: number }) {
  const { account, ownerId } = useOwnerId();
  if (account.isPending) return <p role="status" className="sc-account-empty">Sprawdzam, czy jesteś zalogowany…</p>;
  if (!ownerId) return <SignedOutPanel title="Zaloguj się, aby ułożyć własną nitkę" />;
  return <Editor key={threadId ?? 'new'} ownerId={ownerId} threadId={threadId} />;
}

function Editor({ ownerId, threadId }: { ownerId: number; threadId?: number }) {
  const uid = useId();
  const router = useRouter();
  const cache = useQueryClient();
  const thread = useQuery({
    queryKey: personalKeys.thread(ownerId, threadId ?? 0),
    queryFn: () => apiFetch<PersonalContextThread>(`/api/account/context-threads/${threadId}/`),
    enabled: Boolean(threadId),
    retry: false,
  });
  const config = useQuery({ queryKey: ['mvp-portal-config'], queryFn: getPortalConfig, staleTime: 60_000 });
  const favorites = useArticleFavorites();

  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [saved, setSaved] = useState(serialize(EMPTY));
  const [initialized, setInitialized] = useState(!threadId);
  const [keywordInput, setKeywordInput] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [search, setSearch] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [announcement, setAnnouncement] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkTitle, setLinkTitle] = useState('');
  const [linkNeedsTitle, setLinkNeedsTitle] = useState(false);
  const [linkPending, setLinkPending] = useState(false);
  const [linkMessage, setLinkMessage] = useState('');
  const focusAfterMove = useRef<string | null>(null);
  const controls = useRef(new Map<string, HTMLButtonElement>());

  useEffect(() => {
    if (thread.data && !initialized) {
      const next = fromThread(thread.data);
      setDraft(next);
      setSaved(serialize(next));
      setInitialized(true);
    }
  }, [thread.data, initialized]);

  useEffect(() => {
    if (focusAfterMove.current) {
      controls.current.get(focusAfterMove.current)?.focus();
      focusAfterMove.current = null;
    }
  }, [draft.items]);

  const results = useQuery({
    queryKey: ['personal-thread-search', searchTerm],
    queryFn: () => getNewsFeed({ query: searchTerm, match: 'words', pageSize: 8 }),
    enabled: searchTerm.length > 1,
    staleTime: 30_000,
  });

  const dirty = serialize(draft) !== saved;
  const query = joinKeywords(draft.keywords);
  const selectedIds = useMemo(() => new Set(draft.items.filter(item => item.kind === 'article').map(item => item.id)), [draft.items]);
  const sources = config.data?.sources ?? [];
  const visibleSources = sources.filter(source => source.name.toLocaleLowerCase('pl').includes(sourceFilter.toLocaleLowerCase('pl'))).slice(0, 60);

  function update(patch: Partial<Draft>) { setDraft(current => ({ ...current, ...patch })); setNotice(''); }

  function addKeyword() {
    const values = keywordInput.split(',').map(item => item.trim()).filter(Boolean);
    const next = [...draft.keywords];
    for (const value of values) if (!next.some(item => item.toLocaleLowerCase('pl') === value.toLocaleLowerCase('pl'))) next.push(value);
    if (joinKeywords(next).length > THREAD_LIMITS.query) { setError(`Hasła mogą mieć łącznie najwyżej ${THREAD_LIMITS.query} znaków.`); return; }
    setError('');
    update({ keywords: next });
    setKeywordInput('');
  }

  function onKeywordKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') { event.preventDefault(); addKeyword(); }
  }

  function toggle<T>(list: T[], value: T) { return list.includes(value) ? list.filter(item => item !== value) : [...list, value]; }

  function addItem(item: EditorItem) {
    if (draft.items.some(current => current.key === item.key)) { setLinkMessage('Ten materiał jest już w nitce.'); return; }
    if (draft.items.length >= MAX_THREAD_ARTICLES) { setError(`Nitka może mieć najwyżej ${MAX_THREAD_ARTICLES} elementów.`); return; }
    update({ items: [...draft.items, item] });
    setAnnouncement(`Dodano na pozycji ${draft.items.length + 1}: ${item.title}`);
  }

  function addArticle(article: PersonalArticleRef) {
    if (!selectedIds.has(article.id)) addItem(articleItem(article));
  }

  async function addLink() {
    const url = linkUrl.trim();
    if (!url) return;
    setLinkPending(true); setLinkMessage(''); setError('');
    try {
      const result = await resolveLink(url, linkTitle.trim());
      if ('needsTitle' in result) { setLinkNeedsTitle(true); setLinkMessage(result.message); return; }
      addItem(fromElement({ ...result.item, note: '', position: 0 } as ThreadElement));
      setLinkMessage(result.status === 'in_base'
        ? 'Ten materiał jest już w naszej Bazie — dodaliśmy istniejący box.'
        : result.status === 'existing_link' ? 'Ktoś już dodał ten link — użyliśmy tego samego boxa.' : 'Dodano link spoza Bazy.');
      setLinkUrl(''); setLinkTitle(''); setLinkNeedsTitle(false);
    } catch (reason) {
      setLinkMessage(reason instanceof Error ? reason.message : 'Nie udało się dodać linku.');
    } finally { setLinkPending(false); }
  }

  function setNote(key: string, note: string) {
    update({ items: draft.items.map(item => (item.key === key ? { ...item, note } : item)) });
  }

  function move(key: string, direction: -1 | 1) {
    const index = draft.items.findIndex(item => item.key === key);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= draft.items.length) return;
    const next = [...draft.items];
    [next[index], next[target]] = [next[target], next[index]];
    focusAfterMove.current = `${key}:${direction}`;
    update({ items: next });
    setAnnouncement(`Przesunięto na pozycję ${target + 1} z ${next.length}.`);
  }

  function remove(key: string) {
    const index = draft.items.findIndex(item => item.key === key);
    const next = draft.items.filter(item => item.key !== key);
    const neighbour = next[Math.min(index, next.length - 1)];
    focusAfterMove.current = neighbour ? `${neighbour.key}:remove` : null;
    update({ items: next });
    setAnnouncement('Usunięto element z nitki. Zmiana zostanie zapisana po kliknięciu „Zapisz nitkę”.');
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.title.trim()) { setError('Podaj tytuł nitki.'); return; }
    if (draft.isPublic && draft.items.length < MIN_PUBLIC_ITEMS) { setError(`Opublikować można nitkę z co najmniej ${MIN_PUBLIC_ITEMS} elementami.`); return; }
    setPending(true); setError(''); setNotice('');
    try {
      const result = await savePersonalThread({
        title: draft.title.trim(),
        description: draft.description.trim(),
        query,
        categories: draft.categories,
        source_ids: draft.sourceIds,
        items: draft.items.map(item => (item.kind === 'article' ? { article_id: item.id, note: item.note.trim() } : { link_id: item.id, note: item.note.trim() })),
        is_public: draft.isPublic,
      }, threadId);
      const next = fromThread(result);
      setDraft(next);
      setSaved(serialize(next));
      cache.setQueryData(personalKeys.thread(ownerId, result.id), result);
      await cache.invalidateQueries({ queryKey: personalKeys.threads(ownerId) });
      setNotice(`Zapisano ${formatDateTimePl(result.updated_at)}. ${result.is_public ? 'Nitka jest publiczna w sekcji Nitki.' : 'Nitka pozostaje prywatna.'}`);
      if (!threadId) router.replace(`/konto/nitki/${result.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Nie udało się zapisać nitki. Nic nie zostało zmienione.');
    } finally { setPending(false); }
  }

  async function removeThread() {
    if (!threadId) return;
    setPending(true); setError('');
    try {
      await deletePersonalThread(threadId);
      await cache.invalidateQueries({ queryKey: personalKeys.threads(ownerId) });
      router.push('/konto#moje-nitki');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Nie udało się usunąć nitki.'); setPending(false); }
  }

  if (threadId && thread.isPending) return <p role="status" className="sc-account-empty">Ładuję nitkę…</p>;
  if (threadId && thread.isError) {
    return (
      <section className="sc-account">
        <p className="sc-account-kicker">MOJA NITKA KONTEKSTOWA</p>
        <h1>{isUnavailable(thread.error) ? 'Nie znaleziono nitki' : 'Nie udało się pobrać nitki'}</h1>
        <p className="sc-account-empty">{isUnavailable(thread.error) ? 'Ta nitka nie istnieje albo została usunięta.' : 'Spróbuj ponownie za chwilę.'}</p>
        <Button href="/konto" variant="quiet" size="sm">← Moje konto</Button>
      </section>
    );
  }

  const selectedSources = sources.filter(source => draft.sourceIds.includes(source.id));

  return (
    <form className="sc-account sc-account-editor" onSubmit={save} aria-labelledby={`${uid}-title`}>
      <header className="sc-account-head">
        <Link href="/konto#moje-nitki" className="sc-account-back">← Moje konto</Link>
        <p className="sc-account-kicker">MOJA NITKA KONTEKSTOWA</p>
        <h1 id={`${uid}-title`}>{threadId ? draft.title || 'Nitka bez tytułu' : 'Nowa nitka'}</h1>
        {draft.isPublic
          ? <p className="sc-account-private is-public"><span>PUBLICZNA</span> Po zapisaniu nitka jest widoczna w sekcji <Link href="/nitki">Nitki</Link> pod Twoją nazwą użytkownika{threadId ? <> · <Link href={`/nitki/${threadId}`}>zobacz publiczną wersję</Link></> : null}.</p>
          : <p className="sc-account-private"><span>PRYWATNA</span> Widzisz ją tylko Ty. Nie układa jej AI — kolejność ustalasz sam. Możesz ją opublikować w sekcji Nitki.</p>}
        {thread.data?.hidden_at && <p className="sc-account-error">Zespół ukrył tę nitkę po zgłoszeniu. Napisz na admin@spin.clinic, jeśli uważasz, że to pomyłka.</p>}
      </header>

      <section className="sc-account-section" aria-labelledby={`${uid}-basics`}>
        <header><h2 id={`${uid}-basics`}>Opis</h2></header>
        <div className="sc-account-fields">
          <label><span className="sc-account-label-row">Tytuł <span className="sc-account-req">(wymagany)</span></span>
            <input value={draft.title} maxLength={THREAD_LIMITS.title} required onChange={event => update({ title: event.target.value })} />
            <small>{draft.title.length}/{THREAD_LIMITS.title}</small>
          </label>
          <label><span className="sc-account-label-row">Opis <span>(opcjonalnie)</span></span>
            <textarea rows={3} value={draft.description} maxLength={THREAD_LIMITS.description} onChange={event => update({ description: event.target.value })} />
            <small>{draft.description.length}/{THREAD_LIMITS.description} · {draft.isPublic ? 'Widoczny dla czytelników pod tytułem.' : 'Notatka dla Ciebie, np. co chcesz porównać.'}</small>
          </label>
        </div>
      </section>

      <section className="sc-account-section" aria-labelledby={`${uid}-materials`}>
        <header><h2 id={`${uid}-materials`}>Elementy nitki <span>{draft.items.length}</span></h2></header>
        {draft.items.length === 0 ? (
          <p className="sc-account-empty">Nitka nie ma jeszcze elementów. Pierwszy to materiał otwierający — ten, od którego zaczyna się sprawa. Znajdź go poniżej w Bazie albo dodaj przez link.</p>
        ) : (
          <ol className="sc-account-items" aria-label="Kolejność elementów w nitce">
            {draft.items.map((item, index) => (
              <li key={item.key}>
                <span className="sc-account-index" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                <div className="sc-account-item-copy">
                  <p className="sc-account-meta">
                    {item.kind === 'article' ? <>
                      <span className="sc-account-tag">{categoryLabel(item.category ?? '')}</span>
                      {item.published_date ? formatDateTimePl(item.published_date) : 'data publikacji nieznana'}
                      {item.source_name && ` · ${item.source_name}`}
                    </> : <>
                      <span className="sc-account-tag is-outside">spoza Bazy</span>{item.domain}
                    </>}
                    {index === 0 && <span className="sc-account-tag">materiał otwierający</span>}
                  </p>
                  <strong>{item.title}</strong>
                  <p className="sc-account-links">
                    <a href={item.url} target="_blank" rel="noopener noreferrer">Otwórz materiał ↗<span className="sr-only"> (oryginał, nowa karta)</span></a>
                    {item.kind === 'article' && <Link href={`/material/${item.id}`}>Kontekst materiału</Link>}
                  </p>
                  <label className="sc-account-note">Notatka (opcjonalnie)
                    <textarea rows={2} maxLength={NOTE_LIMIT} value={item.note} onChange={event => setNote(item.key, event.target.value)} placeholder="Dlaczego ten materiał jest w nitce?" />
                    <small>{item.note.length}/{NOTE_LIMIT}</small>
                  </label>
                </div>
                <div className="sc-account-item-actions">
                  <button type="button" ref={node => { if (node) controls.current.set(`${item.key}:-1`, node); }} aria-label={`Przesuń wcześniej: ${item.title}`} aria-disabled={index === 0} onClick={() => move(item.key, -1)}>↑</button>
                  <button type="button" ref={node => { if (node) controls.current.set(`${item.key}:1`, node); }} aria-label={`Przesuń dalej: ${item.title}`} aria-disabled={index === draft.items.length - 1} onClick={() => move(item.key, 1)}>↓</button>
                  <button type="button" ref={node => { if (node) controls.current.set(`${item.key}:remove`, node); }} aria-label={`Usuń z nitki: ${item.title}`} onClick={() => remove(item.key)}>✕</button>
                </div>
              </li>
            ))}
          </ol>
        )}

        <div className="sc-account-finder">
          <div className="sc-account-field">
            <label htmlFor={`${uid}-search`}>Dodaj materiał z Bazy</label>
            <div className="sc-account-inline">
              <input id={`${uid}-search`} type="search" value={search} onChange={event => setSearch(event.target.value)}
                onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); setSearchTerm(search.trim()); } }} placeholder="Tytuł, hasło, osoba…" />
              <Button type="button" variant="quiet" size="sm" onClick={() => setSearchTerm(search.trim())} disabled={search.trim().length < 2}>Szukaj</Button>
              {draft.keywords.length > 0 && <Button type="button" variant="quiet" size="sm" onClick={() => { setSearch(draft.keywords.join(' ')); setSearchTerm(draft.keywords.join(' ')); }}>Szukaj po hasłach nitki</Button>}
            </div>
          </div>
          {results.isFetching && <p role="status" className="sc-account-hint">Szukam w Bazie…</p>}
          {results.isError && <p role="alert" className="sc-account-hint">Nie udało się przeszukać Bazy.</p>}
          {results.isSuccess && !results.data.results.length && <p className="sc-account-hint">Brak materiałów dla „{searchTerm}”.</p>}
          {results.isSuccess && results.data.results.length > 0 && (
            <ul className="sc-account-candidates" aria-label="Wyniki wyszukiwania">
              {results.data.results.map(article => (
                <li key={article.id}>
                  <div>
                    <p className="sc-account-meta"><span className="sc-account-tag">{categoryLabel(article.category)}</span> {article.source?.name} · {formatDateTimePl(article.published_date, article.date_precision)}</p>
                    <strong>{article.title}</strong>
                  </div>
                  <Button type="button" variant="quiet" size="sm" disabled={selectedIds.has(article.id)} onClick={() => addArticle(toRef(article))}>
                    {selectedIds.has(article.id) ? 'W nitce' : 'Dodaj'}<span className="sr-only">: {article.title}</span>
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {(favorites.data?.results.length ?? 0) > 0 && (
            <details className="sc-account-from-favorites">
              <summary>Dodaj z ulubionych materiałów ({favorites.data!.results.length})</summary>
              <ul className="sc-account-candidates">
                {favorites.data!.results.map(row => (
                  <li key={row.id}>
                    <div>
                      <p className="sc-account-meta"><span className="sc-account-tag">{categoryLabel(row.article.category)}</span> {row.article.published_date ? formatDateTimePl(row.article.published_date) : ''}</p>
                      <strong>{row.article.title}</strong>
                    </div>
                    <Button type="button" variant="quiet" size="sm" disabled={selectedIds.has(row.article.id)} onClick={() => addArticle(row.article)}>
                      {selectedIds.has(row.article.id) ? 'W nitce' : 'Dodaj'}<span className="sr-only">: {row.article.title}</span>
                    </Button>
                  </li>
                ))}
              </ul>
            </details>
          )}

          <div className="sc-account-field sc-account-linkadd">
            <label htmlFor={`${uid}-link`}>Dodaj materiał przez link</label>
            <div className="sc-account-inline">
              <input id={`${uid}-link`} type="url" inputMode="url" value={linkUrl} maxLength={1024} placeholder="https://…"
                onChange={event => { setLinkUrl(event.target.value); setLinkNeedsTitle(false); setLinkMessage(''); }}
                onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); addLink(); } }} />
              <Button type="button" variant="quiet" size="sm" loading={linkPending} disabled={!linkUrl.trim() || linkPending || (linkNeedsTitle && !linkTitle.trim())} onClick={addLink}>Dodaj link</Button>
            </div>
            {linkNeedsTitle && (
              <label className="sc-account-sublabel">Tytuł materiału — przepisz go ze strony źródła
                <input value={linkTitle} maxLength={300} onChange={event => setLinkTitle(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); addLink(); } }} />
              </label>
            )}
            <small>Jeśli materiał jest już w Bazie, podepniemy istniejący box. Z linków spoza Bazy zapisujemy tylko tytuł, adres i nazwę strony — bez treści i zdjęć.</small>
            {linkMessage && <p role="status" className="sc-account-hint">{linkMessage}</p>}
          </div>
        </div>
      </section>

      <details className="sc-account-section sc-account-filters">
        <summary><h2>Hasła, kategorie i źródła <span>(opcjonalnie — pomagają szukać w Bazie)</span></h2></summary>
        <div className="sc-account-fields">
          <div className="sc-account-field">
            <label htmlFor={`${uid}-keyword`}>Hasła</label>
            <div className="sc-account-inline">
              <input id={`${uid}-keyword`} value={keywordInput} onChange={event => setKeywordInput(event.target.value)} onKeyDown={onKeywordKey} placeholder="np. most miejski" aria-describedby={`${uid}-keyword-help`} />
              <Button type="button" variant="quiet" size="sm" onClick={addKeyword} disabled={!keywordInput.trim()}>Dodaj hasło</Button>
            </div>
            <small id={`${uid}-keyword-help`}>Enter lub przecinek dodaje hasło · {query.length}/{THREAD_LIMITS.query} znaków</small>
            {draft.keywords.length > 0 && (
              <ul className="sc-account-chips" aria-label="Wybrane hasła">
                {draft.keywords.map(keyword => (
                  <li key={keyword}>{keyword}<button type="button" aria-label={`Usuń hasło ${keyword}`} onClick={() => update({ keywords: draft.keywords.filter(item => item !== keyword) })}>×</button></li>
                ))}
              </ul>
            )}
          </div>

          <fieldset className="sc-account-field">
            <legend>Kategorie {draft.categories.length > 0 && <span>· wybrano {draft.categories.length}</span>}</legend>
            {config.isPending && <p role="status" className="sc-account-hint">Ładuję kategorie…</p>}
            {config.isError && <p className="sc-account-hint">Nie udało się pobrać listy kategorii.</p>}
            <div className="sc-account-pills">
              {(config.data?.categories ?? []).map(category => (
                <label key={category.value} className={draft.categories.includes(category.value) ? 'is-on' : ''}>
                  <input type="checkbox" checked={draft.categories.includes(category.value)} onChange={() => update({ categories: toggle(draft.categories, category.value) })} />
                  {category.label}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="sc-account-field">
            <legend>Źródła {draft.sourceIds.length > 0 && <span>· wybrano {draft.sourceIds.length}</span>}</legend>
            {selectedSources.length > 0 && (
              <ul className="sc-account-chips" aria-label="Wybrane źródła">
                {selectedSources.map(source => (
                  <li key={source.id}>{source.name}<button type="button" aria-label={`Usuń źródło ${source.name}`} onClick={() => update({ sourceIds: draft.sourceIds.filter(id => id !== source.id) })}>×</button></li>
                ))}
              </ul>
            )}
            <label className="sc-account-sublabel">Znajdź źródło
              <input type="search" value={sourceFilter} onChange={event => setSourceFilter(event.target.value)} placeholder="Nazwa źródła" />
            </label>
            <div className="sc-account-source-list">
              {visibleSources.map(source => (
                <label key={source.id}>
                  <input type="checkbox" checked={draft.sourceIds.includes(source.id)} onChange={() => update({ sourceIds: toggle(draft.sourceIds, source.id) })} />
                  {source.name}
                </label>
              ))}
              {config.isSuccess && !visibleSources.length && <p className="sc-account-hint">Brak źródeł o tej nazwie.</p>}
            </div>
          </fieldset>
        </div>
      </details>

      <div className="sc-account-savebar">
        <div role="status" aria-live="polite">
          {error ? <p className="sc-account-error">{error}</p> : notice ? <p>{notice}</p> : <p>{dirty ? 'Masz niezapisane zmiany.' : threadId ? 'Wszystkie zmiany zapisane.' : 'Nowa nitka nie jest jeszcze zapisana.'}</p>}
        </div>
        <div className="sc-account-actions">
          <label className="sc-account-publish" title={`Publiczna nitka potrzebuje co najmniej ${MIN_PUBLIC_ITEMS} elementów`}>
            <input type="checkbox" checked={draft.isPublic} onChange={event => update({ isPublic: event.target.checked })} />
            Publiczna w sekcji Nitki
          </label>
          <Button type="submit" variant="primary" disabled={pending}>{pending ? 'Zapisuję…' : 'Zapisz nitkę'}</Button>
          {threadId && (confirmDelete ? (
            <span className="sc-account-confirm">
              <Button type="button" variant="quiet" size="sm" disabled={pending} onClick={removeThread}>Potwierdź usunięcie nitki</Button>
              <Button type="button" variant="quiet" size="sm" onClick={() => setConfirmDelete(false)}>Anuluj</Button>
            </span>
          ) : (
            <Button type="button" variant="quiet" size="sm" onClick={() => setConfirmDelete(true)}>Usuń nitkę</Button>
          ))}
        </div>
      </div>
      <p className="sr-only" aria-live="polite">{announcement}</p>
    </form>
  );
}
