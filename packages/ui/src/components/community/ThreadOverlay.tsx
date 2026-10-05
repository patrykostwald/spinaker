"use client";

import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { getCommunityThread, getCommunityThreads } from '../../lib/community';
import { ThreadStrip } from './ThreadStrip';
import { setReactionMood, sumCounts } from '../../lib/mood';
import { Loading } from "../../kit/Loading";

/** Płynne przenikanie przy otwieraniu i zamykaniu pełnego ekranu (View Transitions); bez wsparcia albo przy ograniczonym ruchu - od razu. */
export function viewTransition(update: () => void) {
  const doc = document as Document & { startViewTransition?: (callback: () => void) => unknown };
  if (!doc.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { update(); return; }
  doc.startViewTransition(() => flushSync(update));
}

/**
 * Wejście w spinkę (właściciel 3.10): kliknięta na liście zajmuje cały obszar treści (na telefonie cały ekran),
 * adres zmienia się na /spinki/ID. Pod spodem komentarze, a na samym dole jedna spinka wybrana przez nas
 * (polecana, a bez niej najgorętsza). Z prawej u góry „Następna spinka”: cały widok przechodzi do kolejnej spinki z listy.
 * Wyjście: „Wszystkie spinki”, Esc albo „wstecz”.
 */
export function ThreadOverlay({ id: initial, onClose, order = [] }: { id: number; onClose: () => void; order?: number[] }) {
  const [id, setId] = useState(initial);
  const query = useQuery({ queryKey: ['community-thread', String(id)], queryFn: () => getCommunityThread(id), retry: false });
  const featured = useQuery({ queryKey: ['community-threads', 'next-pick'], queryFn: () => getCommunityThreads(1, '', '', { featured: '1' }), retry: false, staleTime: 60_000 });
  const hot = useQuery({ queryKey: ['community-threads', 'next-hot'], queryFn: () => getCommunityThreads(1, '', '', { sort: 'hot' }), retry: false, staleTime: 60_000 });
  // kolejność z listy, z której weszliśmy; bez niej (np. Spin dnia) - kolejność najgorętszych
  const list = order.length ? order : (hot.data?.results ?? []).map(row => row.id);
  const at = list.indexOf(id);
  const following = at >= 0 ? list[at + 1] ?? null : list.find(other => other !== id) ?? null;
  const next = [...(featured.data?.results ?? []), ...(hot.data?.results ?? [])].find(row => row.id !== id && row.id !== following);
  const body = useRef<HTMLDivElement>(null);
  function open(nextId: number) {
    setId(nextId);
    window.history.replaceState({ ...window.history.state, scTrop: nextId }, '', `/spinki/${nextId}`);
    body.current?.scrollTo({ top: 0 });
  }
  const close = useRef<HTMLButtonElement>(null);
  // wejście prosto z linku nie ma czego cofać: wtedy „wróć” prowadzi na listę spinek, a nie poza serwis (znajomy właściciela 5.10)
  const pushed = useRef(false);
  const leave = () => { if (pushed.current) window.history.back(); else window.location.assign('/spinki'); };
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const root = document.documentElement;
    const back = document.activeElement as HTMLElement | null;
    // na komputerze spinka otwiera się w obszarze treści (pasek z lewej i kategorie zostają); na telefonie na cały ekran
    const mobile = window.matchMedia('(max-width: 767px)').matches;
    if (mobile) root.dataset.immersive = '1';
    // Raz na otwarcie (React w trybie deweloperskim uruchamia efekt dwa razy).
    if (window.location.pathname !== `/spinki/${initial}`) pushed.current = true;
    if (window.location.pathname !== `/spinki/${initial}`) window.history.pushState({ ...window.history.state, scTrop: initial }, '', `/spinki/${initial}`);
    const pop = () => closeRef.current();
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape' && !document.querySelector('.sc-trop-overlay .sc-pick')) leave(); };
    window.addEventListener('popstate', pop);
    window.addEventListener('keydown', key);
    close.current?.focus();
    const late = requestAnimationFrame(() => close.current?.focus());
    return () => {
      cancelAnimationFrame(late);
      delete root.dataset.immersive;
      window.removeEventListener('popstate', pop);
      window.removeEventListener('keydown', key);
      back?.focus?.();
    };
  }, [initial]);

  const thread = query.data;
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (thread) requestAnimationFrame(() => titleRef.current?.focus({ preventScroll: true })); }, [thread?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  // nagłówek spinki: pole opisu i wyrównanie do lewej krawędzi pierwszego boksu (właściciel 5.10)
  const [note, setNote] = useState<{ label: string; text: string; auto?: boolean } | null>(null);
  const head = useRef<HTMLElement>(null);
  useEffect(() => { setNote(null); }, [id]);
  useEffect(() => {
    const root = body.current;
    if (!root) return;
    const align = () => {
      const box = root.querySelector('.sc-thread-strip__box') as HTMLElement | null, track = root.querySelector('.sc-thread-strip__track') as HTMLElement | null;
      if (!box || !head.current) return;
      const left = box.getBoundingClientRect().left + (track?.scrollLeft ?? 0) - head.current.getBoundingClientRect().left;
      head.current.style.setProperty('--sp-left', `${Math.max(0, Math.round(left))}px`);
    };
    align();
    const observer = new ResizeObserver(align); observer.observe(root);
    const late = window.setTimeout(align, 1600);
    return () => { observer.disconnect(); clearTimeout(late); };
  }, [thread]);
  // strzałka powrotu na wysokości łańcucha boksów (właściciel 4.10)
  const [backTop, setBackTop] = useState(160);
  const [nearLeft, setNearLeft] = useState(false);
  const [moreBelow, setMoreBelow] = useState(false);
  const [moving, setMoving] = useState(false);
  const commentsBox = () => body.current?.querySelector('article > .sc-thread-social') as HTMLElement | null;
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let box: HTMLElement | null = null;
    const check = () => { if (box) setMoreBelow(box.scrollTop + box.clientHeight < box.scrollHeight - 4); };
    const onScroll = () => { check(); setMoving(true); clearTimeout(timer); timer = setTimeout(() => setMoving(false), 700); };
    const attach = () => { const next = commentsBox(); if (next && next !== box) { box?.removeEventListener('scroll', onScroll); box = next; box.addEventListener('scroll', onScroll, { passive: true }); } check(); };
    attach();
    const mo = new MutationObserver(attach); if (body.current) mo.observe(body.current, { childList: true, subtree: true });
    return () => { mo.disconnect(); box?.removeEventListener('scroll', onScroll); clearTimeout(timer); };
  }, [thread]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const root = body.current;
    if (!root) return;
    const place = () => { const track = root.querySelector('.sc-thread-strip__track, .sc-pick__stage') as HTMLElement | null;
      if (track) setBackTop(track.getBoundingClientRect().bottom - root.getBoundingClientRect().top + root.scrollTop - 20); };
    place();
    const observer = new ResizeObserver(place); observer.observe(root);
    const mo = new MutationObserver(place); mo.observe(root, { childList: true, subtree: true });
    return () => { observer.disconnect(); mo.disconnect(); };
  }, [thread]);
  // po wejściu w spinkę tło odpowiada jej reakcjom; po wyjściu wraca do kolorów działu
  useEffect(() => { setReactionMood(sumCounts(thread?.clips)); }, [thread]);
  useEffect(() => () => setReactionMood(null), []);
  return <div className="sc-trop-overlay" role="dialog" aria-modal="true" aria-label={thread ? `Spinka: ${thread.title}` : 'Spinka'}>
    <div className="sc-trop-overlay__bar">
      <button ref={close} type="button" className="sc-trop-overlay__back" onClick={leave}>← Wszystkie spinki</button>
      {/* tytuł w linii „Wszystkie spinki”, od krawędzi pierwszego boksu; pod nim cały podtytuł (właściciel 4.10) */}
      {thread && <p className="sc-trop-overlay__title" aria-hidden="true"><span>{thread.is_ai ? 'Dr. Spin (AI)' : thread.display_name || `@${thread.author}`}:</span> {thread.title}</p>}
      <span className="sc-trop-overlay__who">{thread ? (thread.is_ai ? 'Dr. Spin (AI)' : thread.display_name || `@${thread.author}`) : ''}</span>
      {following !== null && <button type="button" className="sc-trop-overlay__following" onClick={() => viewTransition(() => open(following))}>Następna spinka →</button>}
    </div>
    <div className="sc-trop-overlay__body" ref={body} data-near-left={nearLeft || undefined}
      onMouseMove={event => { const r = body.current?.getBoundingClientRect(); setNearLeft(!!r && event.clientX - Math.max(r.left, (r.left + r.right) / 2 - 590) < 220); }}
      onMouseLeave={() => setNearLeft(false)}>
      {/* powrót do listy pojawia się po najechaniu na sekcję (właściciel 4.10) */}
      <button type="button" className="sc-trop-overlay__side-back" style={{ top: backTop }} aria-label="Wróć do wszystkich spinek" title="Wszystkie spinki" onClick={leave}>‹</button>
      {query.isPending && <Loading label="Ładowanie spinki" />}
      {query.isError && <p role="alert">Nie udało się pobrać spinki. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p>}
      {thread && <>
        {/* podtytuł zawsze, także u Dr. Spina (pisze go Redaktor tytułów) */}
        <header className="sc-sp-head" ref={head}>
          <h1 className="sc-sp-title" title={thread.title} ref={titleRef} tabIndex={-1}><span>{thread.is_ai ? 'Dr. Spin (AI)' : thread.display_name || `@${thread.author}`}:</span> {thread.title}</h1>
          <p className="sc-sp-desc" aria-live={note?.auto ? 'off' : 'polite'} data-note={note ? '' : undefined}>{note ? <><b>{note.label}</b>{note.text}</> : thread.description || 'Autor nie dodał opisu tej spinki.'}</p>
        </header>
        <ThreadStrip key={thread.id} thread={thread} items={thread.items} full onNote={setNote} />
        {/* przewijanie komentarzy (właściciel 4.10): przycisk w kółku na środku linii nad „Warto też zobaczyć”,
            linia ma na niego przerwę; w czasie przewijania pod nim pojawia się mniejszy, drugi znak */}
        {moreBelow && <div className="sc-trop-overlay__scroller" data-more data-moving={moving || undefined}>
          <i /><button type="button" aria-label="Przewiń komentarze w dół" onClick={() => commentsBox()?.scrollBy({ top: (commentsBox()?.clientHeight ?? 300) * .8, behavior: 'smooth' })}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10l5 5 5-5" /></svg></button><i />
          <svg className="sc-trop-overlay__scroller-small" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 10l4 4 4-4" /></svg>
        </div>}
        {next && <section className="sc-trop-overlay__next" aria-label="Warto też zobaczyć">
          <p className="sc-trop-overlay__next-k">Warto też zobaczyć</p>
          <ThreadStrip key={`next-${next.id}`} thread={next} variant="row" onFullscreen={() => open(next.id)} />
        </section>}
      </>}
    </div>
  </div>;
}
