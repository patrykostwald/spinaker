"use client";

import { Fragment, useEffect, useId, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import type { CommunityThreadSummary, ThreadElement } from '../../lib/community';
import { ago, Avatar, SocialIcon, ClampedText, type Counts } from './SocialPrimitives';
import { SocialReport, ThreadSocial } from './ThreadSocial';
import { formatDatePl, categoryLabel } from '../../lib/utils';
import { XPostCard } from './XPostCard';
import { FocusView, focusRef, SpinkaClip, StepRate, useThreadSteps, type FocusStep } from './ThreadSteps';
import { setReactionMood, sumCounts } from '../../lib/mood';
import { spinkaCsv, spinkaMarkdown } from '../../lib/spinkaExport';
import { RepinPanel } from './RepinPanel';

/** Rodzaj boksu do koloru (kwadraciki w wierszu, pasek z boku karty). */
const kindOf = (item: ThreadElement) => item.box_type ?? (item.kind === 'link' ? 'link' : 'article');
const plural = (n: number, one: string, few: string, many: string) => n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many;
/** Druga strona boksu (na zmianę z tekstem): zdjęcie, jeśli źródło na nie pozwala, inaczej znak rodzaju i krótka etykieta. */
function BoxFace({ item }: { item: ThreadElement }) {
  return <>
    {item.image_url && <span className="sc-box-face sc-box-face--img" aria-hidden="true"><img src={item.image_url} alt="" loading="lazy" /></span>}
    {item.note && <span className="sc-box-face sc-box-face--note" data-only={!item.image_url || undefined}><span>{item.note}</span></span>}
  </>;
}
const ratingsWord = (n: number) => n === 1 ? 'ocena' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 'oceny' : 'ocen';

const TYPES = { post: 'Wpis na X', claim: 'Twierdzenie', source: 'Źródło', technique: 'Technika', diagnosis: 'Diagnoza', message: 'Przekaz dnia', print: 'Druk sejmowy', amendment: 'Poprawka', consultation: 'Postulat organizacji', registry: 'Wpis w rejestrze', declaration: 'Zgłoszenie w uzasadnieniu', summary: 'Podsumowanie Dr. Spina' };

/**
 * Jeden tor w głównej, na liście i w pełnej nitce. Powiązanie należy do następnego boksu.
 * `variant="row"`: wiersz wspólnej listy (ThreadFeed) - rozwija się po chwili najechania albo stuknięciu,
 * otwarty jest tylko jeden naraz (stan trzyma lista), pod spodem 3 najtrafniejsze komentarze i „Odpowiedz”.
 */
export function ThreadStrip({ thread, items = thread.preview ?? [], full = false, initiallyExpanded = false, variant = 'card', open, onOpenChange, offset = 0, onFullscreen, badge }: {
  thread: CommunityThreadSummary; items?: ThreadElement[]; full?: boolean; initiallyExpanded?: boolean;
  variant?: 'card' | 'row'; open?: boolean; onOpenChange?: (open: boolean) => void; offset?: number; onFullscreen?: () => void; badge?: string;
}) {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [commentCount, setCommentCount] = useState<number | null>(null);
  const [showComments, setShowComments] = useState(full);
  const [repinning, setRepinning] = useState(false);
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
  const [focus, setFocus] = useState<FocusStep | null>(null);
  const [picked, setPicked] = useState<FocusStep | null>(null);
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
  const steps = useThreadSteps(thread.id, expanded);
  // reakcje na każdą spinkę: kwadrat w kolorze przeważającej reakcji, szary bez reakcji
  const clips = thread.clips ?? Array.from({ length: Math.max(0, thread.items_count - 1) }, () => ({ positive: 0, doubt: 0, negative: 0 }));
  const dominant = (c: { positive: number; doubt: number; negative: number }) => {
    const top = Math.max(c.positive, c.doubt, c.negative);
    return !top ? 'none' : c.positive === top ? 'positive' : c.doubt === top ? 'doubt' : 'negative';
  };
  const clipsLabel = `${clips.length} ${plural(clips.length, 'spinka', 'spinki', 'spinek')}: ${clips.filter(c => dominant(c) === 'positive').length} trafnych, ${clips.filter(c => dominant(c) === 'negative').length} nietrafnych`;
  const score = steps.data?.score ?? thread.score;
  const slots = ordered.flatMap((_, index) => expanded && index > 0 ? [index, index] : [index]);

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
  const hoverProps = variant === 'row' && !full && !onFullscreen ? {
    onMouseEnter: () => { if (window.matchMedia('(hover: hover)').matches && !expanded) hover.current = setTimeout(() => setExpanded(true), 450); },
    onMouseLeave: () => clearTimeout(hover.current),
  } : {};
  // wiersz listy otwiera spinkę kliknięciem w dowolne miejsce (właściciel 3.10); link do profilu autora działa osobno
  const enter = row && onFullscreen ? {
    onClick: (event: React.MouseEvent) => { if (!(event.target as HTMLElement).closest('a')) onFullscreen(); },
    // najechanie na spinkę na liście: tło lekko przyjmuje proporcje jej reakcji (poza otwartą spinką)
    onMouseEnter: (event: React.MouseEvent) => { if (!(event.currentTarget as HTMLElement).closest('.sc-trop-overlay')) setReactionMood(sumCounts(clips)); },
    onMouseLeave: (event: React.MouseEvent) => { if (!(event.currentTarget as HTMLElement).closest('.sc-trop-overlay')) setReactionMood(null); },
  } : {};
  return <article className={`sc-thread-strip${expanded ? ' is-expanded' : ''}${variant === 'row' ? ' sc-thread-strip--row' : ''}`} {...hoverProps} {...enter}>
    <div className="sc-thread-strip__frame">
    {row ? <header className="sc-trow">
      {/* Wiersz listy (właściciel 3.10): z lewej autor, tytuł i kwadraty reakcji (jeden na spinkę), w środku miniatury boksów,
          z prawej najlepszy komentarz. Kliknięcie wchodzi w spinkę: otwiera się na całym obszarze treści z komentarzami. */}
      <Avatar name={thread.is_ai ? 'Dr. Spin' : thread.display_name || thread.author} ai={thread.is_ai} size={36} />
      <h2 className="sc-trow__h"><button type="button" className="sc-trow__main" aria-expanded={expanded} aria-controls={`${uid}-track`} onClick={onFullscreen ? undefined : toggle}>
        {/* obok awatara: czas publikacji nad nazwą autora, dalej tytuł (właściciel 3.10) */}
        <span className="sc-trow__by"><span className="sc-trow__when">{thread.published_at && <time dateTime={thread.published_at}>{ago(thread.published_at)}</time>}{badge && <span className="sc-trow__badge">{badge}</span>}</span>
          <span className="sc-trow__who"><b>{thread.is_ai ? 'Dr. Spin' : thread.display_name || `@${thread.author}`}</b>{thread.is_ai && <span className="sc-trow__ai">AI</span>}</span></span>
        <span className="sc-trow__title" title={thread.title}>{thread.title}</span>
        {thread.description && !thread.signal_kind && !thread.narrative && <span className="sc-trow__desc">{thread.description}</span>}
      </button></h2>
      <span className="sc-trow__boxes">
        {/* miniatura spinki (właściciel 3.10): kwadraty boksów i zatrzaski między nimi, każdy w kolorze przeważającej reakcji;
            bez reakcji boksy są szare, a zatrzaski niebieskie */}
        <span className="sc-trow__chain" role="img" aria-label={clipsLabel}>{Array.from({ length: Math.min(thread.items_count, 8) }, (_, i) => <Fragment key={i}>
          {i > 0 && <i className="sc-trow__link" data-r={clips[i - 1] ? dominant(clips[i - 1]) : undefined} />}
          <i className="sc-trow__sq" data-r={thread.boxes?.[i] ? dominant(thread.boxes[i]) : undefined} /></Fragment>)}</span>
        <span className="sc-trow__facts">{thread.items_count} {plural(thread.items_count, 'boks', 'boksy', 'boksów')}{thread.sources_count ? ` · ${thread.sources_count} ${plural(thread.sources_count, 'źródło', 'źródła', 'źródeł')}` : ''}</span>
      </span>
      {/* bez komentarza w wierszu (właściciel 3.10): tytuł w dwóch wierszach i opis jak na Wykopie, łańcuch przy licznikach */}
      <span className="sc-trow__side">
        {Boolean(thread.repins?.length) && <span className="sc-trow__repins" title="Przepięcia tej spinki" aria-label={`Przepięcia: ${thread.repins!.length}`}><SpinkaClip />{thread.repins!.length}</span>}
        <button type="button" className="sc-thread-comment-count" aria-label={`Komentarze: ${commentCount ?? thread.comments_count ?? 0}`} onClick={onFullscreen ? undefined : () => { if (!expanded) toggle(); setShowComments(!showComments); }}><SocialIcon kind="comment" />{commentCount ?? thread.comments_count ?? 0}</button>
      </span>
    </header> : full ? <header className="sc-thread-strip__head sc-thread-strip__head--full">
      {/* otwarta spinka: jeden wiersz „Autor: tytuł”, z prawej data i komentarze; „Zgłoś” jest w pasku akcji (właściciel 3.10) */}
      <h2 className="sc-fullhead"><span className="sc-fullhead__who">{thread.is_ai ? 'Dr. Spin (AI)' : <Link href={`/profile/${encodeURIComponent(thread.author)}`}>{thread.display_name || `@${thread.author}`}</Link>}:</span> {thread.title}</h2>
      {thread.published_at && <time className="sc-fullhead__time" dateTime={thread.published_at} title={new Date(thread.published_at).toLocaleString('pl-PL')}>{ago(thread.published_at)}</time>}
      <button type="button" className="sc-thread-comment-count" aria-label={`Komentarze: ${commentCount ?? thread.comments_count ?? 0}`} onClick={() => setShowComments(!showComments)}><SocialIcon kind="comment" />{commentCount ?? thread.comments_count ?? 0}</button>
    </header> : <header className="sc-thread-strip__head">
      {full ? <div className="sc-thread-strip__title"><ClampedText><h2>{thread.title}</h2></ClampedText></div> : <h2><button type="button" aria-expanded={expanded} aria-controls={`${uid}-track`} onClick={toggle} title={thread.title}>
        <span>{thread.title}</span><span className="sc-thread-strip__chev" aria-hidden="true" data-open={expanded || undefined}>⌄</span>
      </button></h2>}
      <span className="sc-thread-strip__author" title={thread.author}>{thread.is_ai ? 'Dr. Spin (AI)' : <Link href={`/profile/${encodeURIComponent(thread.author)}`}>{thread.display_name || `@${thread.author}`}</Link>} {thread.x_profile && <a href={thread.x_profile} target="_blank" rel="noopener noreferrer" aria-label="Połączone konto X">𝕏</a>}</span>
      <button type="button" className="sc-thread-comment-count" aria-label={`Komentarze: ${commentCount ?? thread.comments_count ?? 0}`} onClick={() => setShowComments(!showComments)}><SocialIcon kind="comment" />{commentCount ?? thread.comments_count ?? 0}</button>
      <SocialReport threadId={thread.id} />
      {onFullscreen && <button type="button" className="sc-thread-strip__full" aria-label={`Otwórz spinkę na cały ekran: ${thread.title}`} title="Na cały ekran" onClick={onFullscreen}>⤢</button>}
    </header>}
    {thread.admission?.mode === 'first' && <p className="sc-thread-admission">W izbie przyjęć: przejdzie na główną po pierwszym komentarzu albo reakcji.</p>}
    {thread.admission && thread.admission.mode !== 'first' && <p className="sc-thread-admission" aria-label="Postęp w izbie przyjęć">
      <span className="sc-thread-admission__bar" aria-hidden="true"><span style={{ width: `${Math.min(100, 100 * thread.admission.positive / thread.admission.needed)}%` }} /></span>
      {thread.admission.open ? `${thread.admission.positive}/${thread.admission.needed} ✓ do głównej · zostało ${thread.admission.days_left} ${thread.admission.days_left === 1 ? 'dzień' : 'dni'}` : 'Czas w izbie minął'}
    </p>}
    {focus ? <FocusView key={`${focus.kind}-${focus.index}`} threadId={thread.id} items={ordered} start={focus} steps={steps} onClose={() => { setFocus(null); setPicked(null); }} onStep={setPicked} /> : <div className="sc-thread-strip__rail">
    {expanded && canPrev && <button type="button" className="sc-thread-strip__arrow sc-thread-strip__arrow--prev" aria-label="Poprzednie boksy" onClick={() => slide(-1)}>‹</button>}
    {expanded && canNext && <button type="button" className="sc-thread-strip__arrow sc-thread-strip__arrow--next" aria-label="Kolejne boksy" onClick={() => slide(1)}>›</button>}
    <ol id={`${uid}-track`} ref={track} className="sc-thread-strip__track" tabIndex={0} aria-label={`Boksy spinki: ${thread.title}`}
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
        {expanded && index > 0 && <li className={`sc-joint${openJoint === index ? ' is-open' : ''}`}>
          {/* Spinka (właściciel 3.10): kreska z zawijasem spinająca następny boks, w kolorze reakcji. Kliknięta rozsuwa się
              z lekkim zygzakiem, a nad nią pojawia się boks z wyjaśnieniem autora i oceną; „Otwórz” pokazuje ją na całym obszarze. */}
          <button type="button" className="sc-joint__dot" aria-expanded={openJoint === index}
            onMouseEnter={() => { if (window.matchMedia('(hover: hover)').matches) { clearTimeout(hover.current); hover.current = setTimeout(() => setOpenJoint(index), 320); } }}
            onMouseLeave={() => clearTimeout(hover.current)}
            aria-label={`Spinka ${index}: łączy boks ${index} i ${index + 1}${steps.find(item.item_id, 'context')?.mine ? ' (ocenione)' : ''}`}
            data-done={steps.find(item.item_id, 'context')?.mine || undefined} onClick={() => setOpenJoint(openJoint === index ? null : index)}>
            <SpinkaClip counts={steps.find(item.item_id, 'context')?.counts} id={`clip-${thread.id}-${index}`} open={openJoint === index} />
          </button>
          <div className="sc-joint__pop" hidden={openJoint !== index}>
            <span className="sc-joint__label">Spinka {index}</span>
            <p>{item.link_note || 'Autor nie opisał tej spinki.'}</p>
            <span className="sc-joint__actions">
              {item.item_id && <StepRate step={steps.find(item.item_id, 'context')} canRate={steps.canRate} label={`spinka ${index}`}
                onRate={polarity => void steps.rate(item.item_id!, 'context', polarity)} />}
              <button type="button" className="sc-joint__more" onClick={() => setFocus({ kind: 'clip', index })}>Otwórz →</button>
            </span>
          </div>
        </li>}
        <motion.li layout="position" transition={{ duration: reduced ? 0 : .3, ease: [.2, .8, .2, 1] }} className={`sc-thread-strip__box${highlight === index + 1 ? ' is-highlighted' : ''}`} data-box={index + 1} data-type={kindOf(item)}
          style={{ ['--i' as string]: index }} onClick={event => { if (expanded && !(event.target as HTMLElement).closest('a, button')) setFocus({ kind: 'box', index }); }}>
          {item.note && !expanded && <span className="sc-thread-strip__lead" title={item.note}>{item.note}</span>}
          {expanded && <BoxFace item={item} />}
          {expanded && <span className="sc-rframe" aria-hidden="true" />}
          {item.box_type === 'post' ? <XPostCard item={item} /> :
          <button type="button" className="sc-thread-strip__select" onClick={() => { if (!expanded) toggle(); else setFocus({ kind: 'box', index }); setSelected(index); }}
            aria-pressed={expanded && selected === index}
            aria-label={`${expanded ? 'Pokaż opis boksu' : 'Rozwiń spinkę od boksu'} ${index + 1}: ${item.title}`}>
            <span className="sc-thread-strip__type"><span aria-hidden="true">{item.box_type === 'claim' ? '✓' : '↗'}</span> {item.box_type ? TYPES[item.box_type] : item.kind === 'article' ? categoryLabel(item.category) : 'Link'}</span>
            <strong title={item.title}>{item.title}</strong>
            {item.body && <span className="sc-thread-strip__excerpt">{item.body}</span>}
            <span className="sc-thread-strip__source">{item.source_name || (item.kind === 'link' ? item.domain : '')}
              {item.published_date && <time dateTime={item.published_date}> · {formatDatePl(item.published_date)}</time>}</span>
          </button>}
        </motion.li>
      </Fragment>)}
    </ol>
    </div>}
    {/* W zwiniętym wierszu jest tylko „78% trafnych”; szczegóły ✓ ? ✕ po rozwinięciu (werdykt 1810). */}
    {/* Ocena tropu = średnia reakcji na kroki; całości nie ocenia się osobno (właściciel 3.10). */}
    </div>
    <nav className="sc-thread-continuations" aria-label="Części spinki">{thread.continues && <Link href={`/spinki/${thread.continues}`}>← Poprzednia część</Link>}{thread.continuations?.map(id => <Link key={id} href={`/spinki/${id}`}>Ciąg dalszy →</Link>)}</nav>
    {(variant !== 'row' || expanded) && <ThreadSocial id={thread.id} title={thread.title} ai={thread.is_ai} showComments={showComments} setShowComments={setShowComments}
      expanded={expanded} preview={variant === 'row'}
      draft={draft} setDraft={setDraft} focusBox={focusBox} boxCount={ordered.length} onCounts={setCounts} onCommentCount={setCommentCount}
      filter={picked ? focusRef(picked) : undefined} onClearFilter={() => { setFocus(null); setPicked(null); }}
      tools={full ? <ExportTools thread={thread} items={ordered} onRepin={() => { setRepinning(true); setShowComments(false); }} /> : undefined} />}
    {/* przepięcie zastępuje sekcję komentarzy; pod spodem lista przepięć tej spinki */}
    {full && repinning && <RepinPanel thread={thread} items={ordered} onClose={() => { setRepinning(false); setShowComments(true); }} />}
    {full && (thread.repin_of || Boolean(thread.repins?.length)) && <nav className="sc-repins" aria-label="Przepięcia">
      {thread.repin_of && <Link href={`/spinki/${thread.repin_of}`}>Przepięcie innej spinki: zobacz oryginał →</Link>}
      {thread.repins?.map((id, index) => <Link key={id} href={`/spinki/${id}`}>Przepięcie {index + 1} →</Link>)}
    </nav>}
    {!full && expanded && <div className="sc-thread-strip__foot">
      <Link className="sc-thread-strip__open" href={`/spinki/${thread.id}`} onClick={event => { if (onFullscreen && !event.metaKey && !event.ctrlKey) { event.preventDefault(); onFullscreen(); } }}>Otwórz całą spinkę →</Link>
      <span className="sc-thread-strip__tools">{row && <SocialReport threadId={thread.id} />}{row && onFullscreen && <button type="button" className="sc-thread-strip__full" aria-label={`Otwórz spinkę na cały ekran: ${thread.title}`} title="Na cały ekran" onClick={onFullscreen}>⤢</button>}
        <button type="button" className="sc-thread-strip__collapse" onClick={toggle}>Zwiń spinkę <span aria-hidden="true">⌃</span></button></span>
    </div>}
  </article>;
}

/**
 * Narzędzia otwartej spinki (Konsylium 3.10, decyzja właściciela): kontraspinka, czyli ten sam materiał ułożony
 * po swojemu, oraz kopiowanie i eksport dla dziennikarzy i badaczy.
 */
function ExportTools({ thread, items, onRepin }: { thread: CommunityThreadSummary; items: ThreadElement[]; onRepin: () => void }) {
  const [copied, setCopied] = useState(false);
  const meta = { id: thread.id, title: thread.title, author: thread.is_ai ? 'Dr. Spin (AI)' : thread.display_name || `@${thread.author}` };
  async function copy() {
    const text = spinkaMarkdown(meta, items, window.location.origin);
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1600); }
    catch { window.prompt('Skopiuj spinkę:', text); }
  }
  function download() {
    const blob = new Blob(['\uFEFF' + spinkaCsv(meta, items, window.location.origin)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `spinka-${thread.id}.csv`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <>
    <button type="button" className="sc-thread-social-actions__tool" onClick={onRepin}>Przepnij spinkę</button>
    <button type="button" className="sc-thread-social-actions__tool" onClick={() => void copy()}>{copied ? 'Skopiowano' : 'Kopiuj'}</button>
    {/* „Pobierz CSV” wyłączone na razie (właściciel 3.10); włączenie: odkomentować */}
    {false && <button type="button" className="sc-thread-social-actions__tool" onClick={download}>Pobierz CSV</button>}
  </>;
}
