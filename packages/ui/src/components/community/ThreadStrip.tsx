"use client";

import { Fragment, useEffect, useId, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import type { CommunityThreadSummary, ThreadElement } from '../../lib/community';
import { RatingFrame, SocialIcon, ClampedText, type Counts } from './SocialPrimitives';
import { SocialReport, ThreadSocial } from './ThreadSocial';
import { useFeature } from '../../lib/features';
import { formatDatePl, categoryLabel } from '../../lib/utils';
import { XPostCard } from './XPostCard';

const TYPES = { post: 'Wpis na X', claim: 'Twierdzenie', source: 'Źródło', technique: 'Technika', diagnosis: 'Diagnoza', message: 'Przekaz dnia', print: 'Druk sejmowy', amendment: 'Poprawka', consultation: 'Postulat organizacji', registry: 'Wpis w rejestrze', declaration: 'Zgłoszenie w uzasadnieniu', summary: 'Podsumowanie Dr. Spina' };

/** Jeden tor w głównej, na liście i w pełnej nitce. Powiązanie należy do następnego boksu. */
export function ThreadStrip({ thread, items = thread.preview ?? [], full = false, initiallyExpanded = false }: {
  thread: CommunityThreadSummary; items?: ThreadElement[]; full?: boolean; initiallyExpanded?: boolean;
}) {
  const accountsEnabled = useFeature('ACCOUNTS_ENABLED');
  const [counts, setCounts] = useState<Counts | null>(null);
  const [commentCount, setCommentCount] = useState<number | null>(null);
  const [showComments, setShowComments] = useState(full);
  const [draft, setDraft] = useState('');
  const [highlight, setHighlight] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const scrollingTo = useRef<number | null>(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const [expanded, setExpanded] = useState(full || initiallyExpanded);
  const [active, setActive] = useState(0);
  const [selected, setSelected] = useState(0);
  const track = useRef<HTMLOListElement>(null);
  const uid = useId();
  const reduced = useReducedMotion();
  const ordered = [...items].sort((a, b) => a.position - b.position);
  const slots = ordered.flatMap((item, index) => expanded && index > 0 && item.link_note ? [index, index] : [index]);
  const current = ordered[selected] ?? ordered[0];

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
    if (!full) return;
    const read = () => { const match = /^#boks-(\d+)$/.exec(window.location.hash); if (match) focusBox(Number(match[1])); };
    read(); window.addEventListener('hashchange', read);
    return () => window.removeEventListener('hashchange', read);
  }, [full]);

  return <article className={`sc-thread-strip${expanded ? ' is-expanded' : ''}`}>
    <div className="sc-thread-strip__frame">
    <header className="sc-thread-strip__head">
      {full ? <div className="sc-thread-strip__title"><ClampedText><h2>{thread.title}</h2></ClampedText></div> : <h2><button type="button" aria-expanded={expanded} aria-controls={`${uid}-track ${uid}-notes`} onClick={toggle} title={thread.title}>
        <span>{thread.title}</span><span aria-hidden="true">{expanded ? '−' : '+'}</span>
      </button></h2>}
      <span className="sc-thread-strip__author" title={thread.author}>{thread.is_ai ? 'Dr. Spin (AI)' : <Link href={`/profile/${encodeURIComponent(thread.author)}`}>{thread.display_name || `@${thread.author}`}</Link>} {thread.x_profile && <a href={thread.x_profile} target="_blank" rel="noopener noreferrer" aria-label="Połączone konto X">𝕏</a>}</span>
      <button type="button" className="sc-thread-comment-count" aria-label={`Komentarze: ${commentCount ?? thread.comments_count ?? 0}`} onClick={() => setShowComments(!showComments)}><SocialIcon kind="comment" />{commentCount ?? thread.comments_count ?? 0}</button>
      <SocialReport threadId={thread.id} />
    </header>
    <ol id={`${uid}-track`} ref={track} className="sc-thread-strip__track" tabIndex={0} aria-label={`Boksy nitki: ${thread.title}`}
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
      }}>
      {ordered.map((item, index) => <Fragment key={`${item.position}-${item.id}`}>
        {expanded && index > 0 && item.link_note && <motion.li layout="position" initial={reduced ? false : { opacity: 0, scale: .95 }} animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: reduced ? 0 : .3, ease: [.2, .8, .2, 1] }} className="sc-thread-strip__link">
          <span className="sc-sr-only">Powiązanie: </span><ClampedText>{item.link_note}</ClampedText>
        </motion.li>}
        <motion.li layout="position" transition={{ duration: reduced ? 0 : .3, ease: [.2, .8, .2, 1] }} className={`sc-thread-strip__box${highlight === index + 1 ? ' is-highlighted' : ''}`} data-box={index + 1}>
          {item.box_type === 'post' ? <><XPostCard item={item} /><button type="button" onClick={() => { if (!expanded) toggle(); setSelected(index); }} aria-label={`Pokaż opis boksu ${index + 1}`}>Boks {index + 1}</button></> :
          <button type="button" className="sc-thread-strip__select" onClick={() => { if (!expanded) toggle(); setSelected(index); }}
            aria-pressed={expanded && selected === index}
            aria-label={`${expanded ? 'Pokaż opis boksu' : 'Rozwiń nitkę od boksu'} ${index + 1}: ${item.title}`}>
            <span className="sc-thread-strip__type"><span aria-hidden="true">{item.box_type === 'claim' ? '✓' : '↗'}</span> {item.box_type ? TYPES[item.box_type] : item.kind === 'article' ? categoryLabel(item.category) : 'Link'}</span>
            <strong title={item.title}>{item.title}</strong>
            {item.body && <span className="sc-thread-strip__excerpt">{item.body}</span>}
            <span className="sc-thread-strip__source">{item.source_name || (item.kind === 'link' ? item.domain : '')}
              {item.published_date && <time dateTime={item.published_date}> · {formatDatePl(item.published_date)}</time>}</span>
          </button>}
        </motion.li>
      </Fragment>)}
    </ol>
    <div id={`${uid}-notes`} className="sc-thread-strip__details" aria-hidden={!expanded}>
      <div>{current && <div className="sc-thread-strip__note">
        <small aria-label="Pozycja w nitce">{selected + 1}/{ordered.length}</small>
        {current.box_type === 'post' ? <XPostCard item={current} /> : <><ClampedText><strong>Boks {selected + 1}: </strong><a href={current.url} target={current.url.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">{current.title} ↗</a></ClampedText>
        {current.body && <ClampedText>{current.body}</ClampedText>}</>}
        {current.note && <ClampedText><strong>Komentarz autora: </strong>{current.note}</ClampedText>}
        {accountsEnabled && <button type="button" onClick={() => { setDraft((draft + ` @boks ${selected + 1} `).trimStart().slice(0, 600)); setShowComments(true); }}>Odpowiedz do boksu</button>}
      </div>}</div>
    </div>
    <RatingFrame counts={counts ?? { positive: thread.opinions.positive, doubt: thread.opinions.doubt ?? 0, negative: thread.opinions.negative }} ai={thread.is_ai} />
    </div>
    {expanded && <p className="sc-thread-totals"><span data-rating="positive">✓</span> {counts?.positive ?? thread.opinions.positive} · <span data-rating="doubt">?</span> {counts?.doubt ?? thread.opinions.doubt ?? 0} · <span data-rating="negative">✕</span> {counts?.negative ?? thread.opinions.negative} · {commentCount ?? thread.comments_count ?? 0} komentarzy</p>}
    {(thread.narrative || thread.signal_kind) && <p className="sc-thread-totals">{thread.description}</p>}
    <nav className="sc-thread-continuations" aria-label="Części nitki">{thread.continues && <Link href={`/nitki/${thread.continues}`}>← Poprzednia część</Link>}{thread.continuations?.map(id => <Link key={id} href={`/nitki/${id}`}>Ciąg dalszy →</Link>)}</nav>
    <ThreadSocial id={thread.id} title={thread.title} ai={thread.is_ai} showComments={showComments} setShowComments={setShowComments}
      expanded={expanded}
      draft={draft} setDraft={setDraft} focusBox={focusBox} boxCount={ordered.length} onCounts={setCounts} onCommentCount={setCommentCount} />
    {!full && expanded && <Link href={`/nitki/${thread.id}`}>Otwórz nitkę</Link>}
  </article>;
}
