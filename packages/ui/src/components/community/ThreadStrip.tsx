"use client";

import { Fragment, useId, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import type { CommunityThreadSummary, ThreadElement } from '../../lib/community';
import { formatDatePl, categoryLabel } from '../../lib/utils';

const TYPES = { post: 'Wpis na X', claim: 'Twierdzenie', source: 'Źródło', technique: 'Technika', diagnosis: 'Diagnoza' };

/** Jeden tor w głównej, na liście i w pełnej nitce. Powiązanie należy do następnego boksu. */
export function ThreadStrip({ thread, items = thread.preview ?? [], full = false }: {
  thread: CommunityThreadSummary; items?: ThreadElement[]; full?: boolean;
}) {
  const [expanded, setExpanded] = useState(full);
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
  function toggle() {
    if (full) return;
    setExpanded(value => !value);
    setActive(0);
    setSelected(0);
    track.current?.scrollTo({ left: 0, behavior: 'instant' });
  }

  return <article className={`sc-thread-strip${expanded ? ' is-expanded' : ''}`}>
    <header className="sc-thread-strip__head">
      <h2>{full ? thread.title : <button type="button" aria-expanded={expanded} aria-controls={`${uid}-track ${uid}-notes`} onClick={toggle} title={thread.title}>
        <span>{thread.title}</span><span aria-hidden="true">{expanded ? '−' : '+'}</span>
      </button>}</h2>
      <span className="sc-thread-strip__author" title={thread.author}>{thread.is_ai ? 'Dr. Spin (AI)' : `@${thread.author}`}</span>
      <span>{ordered.length} boksów</span>
      <span aria-label={`Ocena: ${thread.opinions.positive} za, ${thread.opinions.negative} przeciw`}>+{thread.opinions.positive} / −{thread.opinions.negative}</span>
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
        setActive(nearest); setSelected(slots[nearest] ?? 0);
      }}>
      {ordered.map((item, index) => <Fragment key={`${item.position}-${item.id}`}>
        {expanded && index > 0 && item.link_note && <motion.li layout="position" initial={reduced ? false : { opacity: 0, scale: .95 }} animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: reduced ? 0 : .24 }} className="sc-thread-strip__link">
          <span className="sc-sr-only">Powiązanie: </span><p>{item.link_note}</p>
        </motion.li>}
        <motion.li layout="position" transition={{ duration: reduced ? 0 : .24 }} className="sc-thread-strip__box">
          <button type="button" className="sc-thread-strip__select" onClick={() => { if (!expanded) toggle(); setSelected(index); }}
            aria-pressed={expanded && selected === index}
            aria-label={`${expanded ? 'Pokaż opis boksu' : 'Rozwiń nitkę od boksu'} ${index + 1}: ${item.title}`}>
            <span className="sc-thread-strip__type"><span aria-hidden="true">{item.box_type === 'post' ? '𝕏' : item.box_type === 'claim' ? '✓' : '↗'}</span> {item.box_type ? TYPES[item.box_type] : item.kind === 'article' ? categoryLabel(item.category) : 'Link'}</span>
            <strong title={item.title}>{item.title}</strong>
            {item.body && item.box_type !== 'post' && <span className="sc-thread-strip__excerpt">{item.body}</span>}
            <span className="sc-thread-strip__source">{item.source_name || (item.kind === 'link' ? item.domain : '')}
              {item.published_date && <time dateTime={item.published_date}> · {formatDatePl(item.published_date)}</time>}</span>
          </button>
        </motion.li>
      </Fragment>)}
    </ol>
    <nav className="sc-thread-strip__position" aria-label="Pozycja w nitce">
      <button type="button" aria-label="Poprzedni element" disabled={active === 0} onClick={() => move(active - 1)}>←</button>
      <span aria-live="polite">{slots.length ? active + 1 : 0} / {slots.length}</span>
      <button type="button" aria-label="Następny element" disabled={active >= slots.length - 1} onClick={() => move(active + 1)}>→</button>
      {!full && <Link href={`/nitki/${thread.id}`}>Otwórz nitkę</Link>}
    </nav>
    <div id={`${uid}-notes`} className="sc-thread-strip__details" aria-hidden={!expanded}>
      <div>{current && <div className="sc-thread-strip__note">
        <p><strong>Boks {selected + 1}: </strong><a href={current.url} target={current.url.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">{current.title} ↗</a></p>
        {current.body && <p>{current.body}</p>}
        {current.note && <p><strong>Komentarz autora: </strong>{current.note}</p>}
      </div>}</div>
    </div>
  </article>;
}
