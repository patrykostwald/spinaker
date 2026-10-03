"use client";

import { useEffect, useRef } from 'react';
import { flushSync } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { getCommunityThread } from '../../lib/community';
import { ThreadStrip } from './ThreadStrip';

/** Płynne przenikanie przy otwieraniu i zamykaniu pełnego ekranu (View Transitions); bez wsparcia albo przy ograniczonym ruchu - od razu. */
export function viewTransition(update: () => void) {
  const doc = document as Document & { startViewTransition?: (callback: () => void) => unknown };
  if (!doc.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { update(); return; }
  doc.startViewTransition(() => flushSync(update));
}

/**
 * Trop na cały ekran: paski nawigacji znikają (html[data-immersive]), adres zmienia się na /tropy/ID,
 * więc link można skopiować. Wyjście: ✕, Esc albo „wstecz” w przeglądarce lub telefonie.
 */
export function ThreadOverlay({ id, onClose }: { id: number; onClose: () => void }) {
  const query = useQuery({ queryKey: ['community-thread', String(id)], queryFn: () => getCommunityThread(id), retry: false });
  const close = useRef<HTMLButtonElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const root = document.documentElement;
    const back = document.activeElement as HTMLElement | null;
    root.dataset.immersive = '1';
    // Raz na otwarcie (React w trybie deweloperskim uruchamia efekt dwa razy).
    if (window.location.pathname !== `/tropy/${id}`) window.history.pushState({ ...window.history.state, scTrop: id }, '', `/tropy/${id}`);
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
  }, [id]);

  const thread = query.data;
  return <div className="sc-trop-overlay" role="dialog" aria-modal="true" aria-label={thread ? `Trop: ${thread.title}` : 'Trop'}>
    <div className="sc-trop-overlay__bar">
      <span className="sc-trop-overlay__who">{thread ? (thread.is_ai ? 'Dr. Spin (AI)' : thread.display_name || `@${thread.author}`) : ''}</span>
      <button ref={close} type="button" className="sc-trop-overlay__close" aria-label="Zamknij trop" onClick={() => window.history.back()}>✕</button>
    </div>
    <div className="sc-trop-overlay__body">
      {query.isPending && <div className="sc-social-skeleton" aria-label="Ładowanie tropu" />}
      {query.isError && <p role="alert">Nie udało się pobrać tropu. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p>}
      {thread && <>
        {thread.description && <p className="sc-trop-overlay__desc">{thread.description}</p>}
        <ThreadStrip thread={thread} items={thread.items} full />
      </>}
    </div>
  </div>;
}
