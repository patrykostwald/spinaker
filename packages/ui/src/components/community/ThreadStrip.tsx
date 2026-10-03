"use client";

import { Fragment, useEffect, useId, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import type { CommunityThreadSummary, ThreadElement } from '../../lib/community';
import { ago, Avatar, RatingFrame, SocialIcon, ClampedText, type Counts } from './SocialPrimitives';
import { SocialReport, ThreadSocial } from './ThreadSocial';
import { formatDatePl, categoryLabel } from '../../lib/utils';
import { XPostCard } from './XPostCard';

/** Rodzaj boksu do koloru (kwadraciki w wierszu, pasek z boku karty). */
const kindOf = (item: ThreadElement) => item.box_type ?? (item.kind === 'link' ? 'link' : 'article');
const ratingsWord = (n: number) => n === 1 ? 'ocena' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 'oceny' : 'ocen';

const TYPES = { post: 'Wpis na X', claim: 'Twierdzenie', source: 'Źródło', technique: 'Technika', diagnosis: 'Diagnoza', message: 'Przekaz dnia', print: 'Druk sejmowy', amendment: 'Poprawka', consultation: 'Postulat organizacji', registry: 'Wpis w rejestrze', declaration: 'Zgłoszenie w uzasadnieniu', summary: 'Podsumowanie Dr. Spina' };

/**
 * Jeden tor w głównej, na liście i w pełnej nitce. Powiązanie należy do następnego boksu.
 * `variant="row"`: wiersz wspólnej listy (ThreadFeed) - rozwija się po chwili najechania albo stuknięciu,
 * otwarty jest tylko jeden naraz (stan trzyma lista), pod spodem 3 najtrafniejsze komentarze i „Odpowiedz”.
 */
export function ThreadStrip({ thread, items = thread.preview ?? [], full = false, initiallyExpanded = false, variant = 'card', open, onOpenChange, offset = 0, onFullscreen }: {
  thread: CommunityThreadSummary; items?: ThreadElement[]; full?: boolean; initiallyExpanded?: boolean;
  variant?: 'card' | 'row'; open?: boolean; onOpenChange?: (open: boolean) => void; offset?: number; onFullscreen?: () => void;
}) {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [commentCount, setCommentCount] = useState<number | null>(null);
  const [showComments, setShowComments] = useState(full);
  const [draft, setDraft] = useState('');
  const [highlight, setHighlight] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const scrollingTo = useRef<number | null>(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const [ownExpanded, setOwnExpanded] = useState(full || initiallyExpanded);
  const controlled = open !== undefined && !full;
  const expanded = controlled ? Boolean(open) : ownExpanded;
  const setExpanded = (next: boolean | ((value: boolean) => boolean)) => {
    const value = typeof next === 'function' ? next(expanded) : next;
    if (controlled) onOpenChange?.(value); else setOwnExpanded(value);
  };
  const hover = useRef<ReturnType<typeof setTimeout>>();
  const [openJoint, setOpenJoint] = useState<number | null>(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(false);
  function edges() {
    const el = track.current;
    if (!el) return;
    setCanPrev(el.scrollLeft > 4);
    setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }
  function slide(direction: 1 | -1) {
    const el = track.current;
    if (el) el.scrollBy({ left: direction * Math.max(240, el.clientWidth * .8), behavior: reduced ? 'auto' : 'smooth' });
  }
  useEffect(() => () => clearTimeout(hover.current), []);
  const [active, setActive] = useState(0);
  const [selected, setSelected] = useState(0);
  const track = useRef<HTMLOListElement>(null);
  const uid = useId();
  const reduced = useReducedMotion();
  const ordered = [...items].sort((a, b) => a.position - b.position);
  const row = variant === 'row' && !full;
  const shown = counts ?? { positive: thread.opinions.positive, doubt: thread.opinions.doubt ?? 0, negative: thread.opinions.negative };
  const total = shown.positive + shown.doubt + shown.negative;
  const slots = ordered.flatMap((item, index) => expanded && index > 0 && item.link_note ? [index, index] : [index]);

  function move(index: number) {
    const next = Math.max(0, Math.min(slots.length - 1, index));
    const el = track.current?.children[next] as HTMLElement | undefined;
    if (el && track.current) track.current.scrollTo({
      left: track.current.scrollLeft + el.getBoundingClientRect().left - track.current.getBoundingClientRect().left,
      behavior: reduced ? 'auto' : 'smooth',
    });
    setActive(next);
    setSelected(slots[next] ?? 0);
  }
  function focusBox(n: number) {
    const box = track.current?.querySelector<HTMLElement>(`[data-box="${n}"]`);
    if (!box || !track.current) return;
    scrollingTo.current = n - 1;
    setExpanded(true); setSelected(n - 1); setHighlight(n);
    requestAnimationFrame(() => {
      if (track.current) track.current.scrollTo({ left: track.current.scrollLeft + box.getBoundingClientRect().left - track.current.getBoundingClientRect().left, behavior: reduced ? 'auto' : 'smooth' });
    });
    clearTimeout(timer.current); timer.current = setTimeout(() => { setHighlight(null); scrollingTo.current = null; }, 1500);
  }
  function toggle() {
    if (full) return;
    setExpanded(value => !value);
    setActive(0);
    setSelected(0);
    track.current?.scrollTo({ left: 0, behavior: 'instant' });
  }

  useEffect(() => {
    if (!expanded) return;
    const el = track.current;
    edges();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(edges);
    if (el && observer) { observer.observe(el); Array.from(el.children).forEach(child => observer.observe(child)); }
    return () => observer?.disconnect();
  }, [expanded, items.length]);
  useEffect(() => {
    if (!full) return;
    const read = () => { const match = /^#boks-(\d+)$/.exec(window.location.hash); if (match) focusBox(Number(match[1])); };
    read(); window.addEventListener('hashchange', read);
    return () => window.removeEventListener('hashchange', read);
  }, [full]);

  // Najechanie z zamiarem (450 ms), tylko na urządzeniach z myszką; przejazd kursorem po liście niczego nie rozwija.
  const hoverProps = variant === 'row' && !full ? {
    onMouseEnter: () => { if (window.matchMedia('(hover: hover)').matches && !expanded) hover.current = setTimeout(() => setExpanded(true), 450); },
    onMouseLeave: () => clearTimeout(hover.current),
  } : {};
  return <article className={`sc-thread-strip${expanded ? ' is-expanded' : ''}${variant === 'row' ? ' sc-thread-strip--row' : ''}`} {...hoverProps}>
    <div className="sc-thread-strip__frame">
    {row ? <header className="sc-trow">
      <Avatar name={thread.is_ai ? 'Dr. Spin' : thread.display_name || thread.author} ai={thread.is_ai} size={36} />
      <h2 className="sc-trow__h"><button type="button" className="sc-trow__main" aria-expanded={expanded} aria-controls={`${uid}-track`} onClick={toggle}>
        <span className="sc-trow__by"><b>{thread.is_ai ? 'Dr. Spin' : thread.display_name || `@${thread.author}`}</b>{thread.is_ai && <span className="sc-trow__ai">AI</span>}
          {thread.published_at && <><span aria-hidden="true">·</span><time dateTime={thread.published_at}>{ago(thread.published_at)}</time></>}</span>
        <span className="sc-trow__title" title={thread.title}>{thread.title}</span>
        <span className="sc-trow__meta">
          <span className="sc-trow__chips" aria-label={`${thread.items_count} boksów`}>{Array.from({ length: Math.min(thread.items_count, 10) }, (_, i) =>
            <i key={i} data-type={ordered[i] ? kindOf(ordered[i]) : 'more'} title={ordered[i]?.box_type ? TYPES[ordered[i].box_type!] : undefined} />)}</span>
          <span className="sc-trow__score">{total ? `${Math.round(100 * shown.positive / total)}% trafnych · ${total} ${ratingsWord(total)}` : 'Jeszcze bez ocen'}</span>
        </span>
      </button></h2>
      <span className="sc-trow__side">
        <button type="button" className="sc-thread-comment-count" aria-label={`Komentarze: ${commentCount ?? thread.comments_count ?? 0}`} onClick={() => { if (!expanded) toggle(); setShowComments(!showComments); }}><SocialIcon kind="comment" />{commentCount ?? thread.comments_count ?? 0}</button>
        <button type="button" className="sc-trow__chev" data-open={expanded || undefined} aria-label={expanded ? 'Zwiń trop' : 'Rozwiń trop'} onClick={toggle}><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg></button>
      </span>
    </header> : <header className="sc-thread-strip__head">
      {full ? <div className="sc-thread-strip__title"><ClampedText><h2>{thread.title}</h2></ClampedText></div> : <h2><button type="button" aria-expanded={expanded} aria-controls={`${uid}-track`} onClick={toggle} title={thread.title}>
        <span>{thread.title}</span><span className="sc-thread-strip__chev" aria-hidden="true" data-open={expanded || undefined}>⌄</span>
      </button></h2>}
      <span className="sc-thread-strip__author" title={thread.author}>{thread.is_ai ? 'Dr. Spin (AI)' : <Link href={`/profile/${encodeURIComponent(thread.author)}`}>{thread.display_name || `@${thread.author}`}</Link>} {thread.x_profile && <a href={thread.x_profile} target="_blank" rel="noopener noreferrer" aria-label="Połączone konto X">𝕏</a>}</span>
      <button type="button" className="sc-thread-comment-count" aria-label={`Komentarze: ${commentCount ?? thread.comments_count ?? 0}`} onClick={() => setShowComments(!showComments)}><SocialIcon kind="comment" />{commentCount ?? thread.comments_count ?? 0}</button>
      <SocialReport threadId={thread.id} />
      {onFullscreen && <button type="button" className="sc-thread-strip__full" aria-label={`Otwórz trop na cały ekran: ${thread.title}`} title="Na cały ekran" onClick={onFullscreen}>⤢</button>}
    </header>}
    {thread.admission && <p className="sc-thread-admission" aria-label="Postęp w izbie przyjęć">
      <span className="sc-thread-admission__bar" aria-hidden="true"><span style={{ width: `${Math.min(100, 100 * thread.admission.positive / thread.admission.needed)}%` }} /></span>
      {thread.admission.open ? `${thread.admission.positive}/${thread.admission.needed} ✓ do głównej · zostało ${thread.admission.days_left} ${thread.admission.days_left === 1 ? 'dzień' : 'dni'}` : 'Czas w izbie minął'}
    </p>}
    <div className="sc-thread-strip__rail">
    {expanded && canPrev && <button type="button" className="sc-thread-strip__arrow sc-thread-strip__arrow--prev" aria-label="Poprzednie boksy" onClick={() => slide(-1)}>‹</button>}
    {expanded && canNext && <button type="button" className="sc-thread-strip__arrow sc-thread-strip__arrow--next" aria-label="Kolejne boksy" onClick={() => slide(1)}>›</button>}
    <ol id={`${uid}-track`} ref={track} className="sc-thread-strip__track" tabIndex={0} aria-label={`Boksy tropu: ${thread.title}`}
      onKeyDown={event => { if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); move(active + (event.key === 'ArrowRight' ? 1 : -1)); } }}
      onScroll={event => {
        const left = event.currentTarget.getBoundingClientRect().left;
        let nearest = 0, distance = Infinity;
        Array.from(event.currentTarget.children).forEach((child, index) => {
          const d = Math.abs(child.getBoundingClientRect().left - left);
          if (d < distance) { distance = d; nearest = index; }
        });
        if (event.currentTarget.scrollWidth > event.currentTarget.clientWidth &&
            event.currentTarget.scrollLeft + event.currentTarget.clientWidth >= event.currentTarget.scrollWidth - 2) nearest = slots.length - 1;
        setActive(nearest); if (scrollingTo.current === null) setSelected(slots[nearest] ?? 0);
        edges();
      }}>
      {ordered.map((item, index) => <Fragment key={`${item.position}-${item.id}`}>
        {expanded && index > 0 && item.link_note && <li className={`sc-thread-strip__joint${openJoint === index ? ' is-open' : ''}`}>
          {/* Kontekst między boksami: niebieska kropka; po zatrzymaniu kursora (albo stuknięciu) boksy się rozsuwają i widać tekst. */}
          <button type="button" className="sc-thread-strip__dot" aria-expanded={openJoint === index} aria-label={`Kontekst między boksem ${index} a ${index + 1}`}
            onClick={() => setOpenJoint(openJoint === index ? null : index)}><span aria-hidden="true" /></button>
          <span className="sc-thread-strip__context"><span className="sc-sr-only">Kontekst: </span>{item.link_note}</span>
        </li>}
        <motion.li layout="position" transition={{ duration: reduced ? 0 : .3, ease: [.2, .8, .2, 1] }} className={`sc-thread-strip__box${highlight === index + 1 ? ' is-highlighted' : ''}`} data-box={index + 1} data-type={kindOf(item)}>
          {item.note && <span className="sc-thread-strip__lead" title={item.note}>{item.note}</span>}
          {item.box_type === 'post' ? <XPostCard item={item} /> :
          <button type="button" className="sc-thread-strip__select" onClick={() => { if (!expanded) toggle(); setSelected(index); }}
            aria-pressed={expanded && selected === index}
            aria-label={`${expanded ? 'Pokaż opis boksu' : 'Rozwiń trop od boksu'} ${index + 1}: ${item.title}`}>
            <span className="sc-thread-strip__type"><span aria-hidden="true">{item.box_type === 'claim' ? '✓' : '↗'}</span> {item.box_type ? TYPES[item.box_type] : item.kind === 'article' ? categoryLabel(item.category) : 'Link'}</span>
            <strong title={item.title}>{item.title}</strong>
            {item.body && <span className="sc-thread-strip__excerpt">{item.body}</span>}
            <span className="sc-thread-strip__source">{item.source_name || (item.kind === 'link' ? item.domain : '')}
              {item.published_date && <time dateTime={item.published_date}> · {formatDatePl(item.published_date)}</time>}</span>
          </button>}
        </motion.li>
      </Fragment>)}
    </ol>
    </div>
    {/* W zwiniętym wierszu jest tylko „78% trafnych”; szczegóły ✓ ? ✕ po rozwinięciu (werdykt 1810). */}
    {(!row || expanded) && <RatingFrame counts={shown} ai={thread.is_ai} cycle={false} offset={offset} numbers />}
    </div>
    {expanded && variant !== 'row' && <p className="sc-thread-totals"><span data-rating="positive">✓</span> {counts?.positive ?? thread.opinions.positive} · <span data-rating="doubt">?</span> {counts?.doubt ?? thread.opinions.doubt ?? 0} · <span data-rating="negative">✕</span> {counts?.negative ?? thread.opinions.negative} · {commentCount ?? thread.comments_count ?? 0} komentarzy</p>}
    {(thread.narrative || thread.signal_kind) && <p className="sc-thread-totals">{thread.description}</p>}
    <nav className="sc-thread-continuations" aria-label="Części tropu">{thread.continues && <Link href={`/tropy/${thread.continues}`}>← Poprzednia część</Link>}{thread.continuations?.map(id => <Link key={id} href={`/tropy/${id}`}>Ciąg dalszy →</Link>)}</nav>
    {(variant !== 'row' || expanded) && <ThreadSocial id={thread.id} title={thread.title} ai={thread.is_ai} showComments={showComments} setShowComments={setShowComments}
      expanded={expanded} preview={variant === 'row'}
      draft={draft} setDraft={setDraft} focusBox={focusBox} boxCount={ordered.length} onCounts={setCounts} onCommentCount={setCommentCount} />}
    {!full && expanded && <div className="sc-thread-strip__foot">
      <Link className="sc-thread-strip__open" href={`/tropy/${thread.id}`} onClick={event => { if (onFullscreen && !event.metaKey && !event.ctrlKey) { event.preventDefault(); onFullscreen(); } }}>Otwórz cały trop →</Link>
      <span className="sc-thread-strip__tools">{row && <SocialReport threadId={thread.id} />}{row && onFullscreen && <button type="button" className="sc-thread-strip__full" aria-label={`Otwórz trop na cały ekran: ${thread.title}`} title="Na cały ekran" onClick={onFullscreen}>⤢</button>}
        <button type="button" className="sc-thread-strip__collapse" onClick={toggle}>Zwiń trop <span aria-hidden="true">⌃</span></button></span>
    </div>}
  </article>;
}
