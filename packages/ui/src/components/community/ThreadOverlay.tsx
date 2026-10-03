"use client";

import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { getCommunityThread, getCommunityThreads } from '../../lib/community';
import { ThreadStrip } from './ThreadStrip';
import { setReactionMood, sumCounts } from '../../lib/mood';

/** Płynne przenikanie przy otwieraniu i zamykaniu pełnego ekranu (View Transitions); bez wsparcia albo przy ograniczonym ruchu - od razu. */
export function viewTransition(update: () => void) {
  const doc = document as Document & { startViewTransition?: (callback: () => void) => unknown };
  if (!doc.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { update(); return; }
  doc.startViewTransition(() => flushSync(update));
}

/**
 * Wejście w spinkę (właściciel 3.10): kliknięta na liście zajmuje cały obszar treści (na telefonie cały ekran),
 * adres zmienia się na /spinki/ID. Pod spodem komentarze, a na samym dole jedna spinka wybrana przez nas
 * (polecana, a bez niej najgorętsza). Wyjście: „Wszystkie spinki”, Esc albo „wstecz”.
 */
export function ThreadOverlay({ id: initial, onClose }: { id: number; onClose: () => void }) {
  const [id, setId] = useState(initial);
  const query = useQuery({ queryKey: ['community-thread', String(id)], queryFn: () => getCommunityThread(id), retry: false });
  const featured = useQuery({ queryKey: ['community-threads', 'next-pick'], queryFn: () => getCommunityThreads(1, '', '', { featured: '1' }), retry: false, staleTime: 60_000 });
  const hot = useQuery({ queryKey: ['community-threads', 'next-hot'], queryFn: () => getCommunityThreads(1, '', '', { sort: 'hot' }), retry: false, staleTime: 60_000 });
  const next = [...(featured.data?.results ?? []), ...(hot.data?.results ?? [])].find(row => row.id !== id);
  const body = useRef<HTMLDivElement>(null);
  function open(nextId: number) {
    setId(nextId);
    window.history.replaceState({ ...window.history.state, scTrop: nextId }, '', `/spinki/${nextId}`);
    body.current?.scrollTo({ top: 0 });
  }
  const close = useRef<HTMLButtonElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const root = document.documentElement;
    const back = document.activeElement as HTMLElement | null;
    // na komputerze spinka otwiera się w obszarze treści (pasek z lewej i kategorie zostają); na telefonie na cały ekran
    const mobile = window.matchMedia('(max-width: 767px)').matches;
    if (mobile) root.dataset.immersive = '1';
    // Raz na otwarcie (React w trybie deweloperskim uruchamia efekt dwa razy).
    if (window.location.pathname !== `/spinki/${initial}`) window.history.pushState({ ...window.history.state, scTrop: initial }, '', `/spinki/${initial}`);
    const pop = () => closeRef.current();
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') window.history.back(); };
    window.addEventListener('popstate', pop);
    window.addEventListener('keydown', key);
    close.current?.focus();
    return () => {
      delete root.dataset.immersive;
      window.removeEventListener('popstate', pop);
      window.removeEventListener('keydown', key);
      back?.focus?.();
    };
  }, [initial]);

  const thread = query.data;
  // po wejściu w spinkę tło odpowiada jej reakcjom; po wyjściu wraca do kolorów działu
  useEffect(() => { setReactionMood(sumCounts(thread?.clips)); }, [thread]);
  useEffect(() => () => setReactionMood(null), []);
  return <div className="sc-trop-overlay" role="dialog" aria-modal="true" aria-label={thread ? `Spinka: ${thread.title}` : 'Spinka'}>
    <div className="sc-trop-overlay__bar">
      <button ref={close} type="button" className="sc-trop-overlay__back" onClick={() => window.history.back()}>← Wszystkie spinki</button>
      <span className="sc-trop-overlay__who">{thread ? (thread.is_ai ? 'Dr. Spin (AI)' : thread.display_name || `@${thread.author}`) : ''}</span>
    </div>
    <div className="sc-trop-overlay__body" ref={body}>
      {query.isPending && <div className="sc-social-skeleton" aria-label="Ładowanie spinki" />}
      {query.isError && <p role="alert">Nie udało się pobrać spinki. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p>}
      {thread && <>
        {thread.description && !thread.signal_kind && !thread.narrative && <p className="sc-trop-overlay__desc">{thread.description}</p>}
        <ThreadStrip key={thread.id} thread={thread} items={thread.items} full />
        {next && <section className="sc-trop-overlay__next" aria-label="Polecana spinka">
          <p className="sc-trop-overlay__next-k">Polecana spinka</p>
          <ThreadStrip key={`next-${next.id}`} thread={next} variant="row" onFullscreen={() => open(next.id)} />
        </section>}
      </>}
    </div>
  </div>;
}
