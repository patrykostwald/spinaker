"use client";

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import {
  CONTEXT_ROLE_LABELS,
  CONTEXT_TYPE_LABELS,
  DEMO_CONTEXT_BOXES,
  DEMO_CONTEXT_EVENT,
  DEMO_THREAD_EXAMPLE,
  type ContextBox,
  type ContextEvent,
} from '../lib/boxKontekstuDemo';

type Position = 'earlier' | 'open' | 'later';
type TimelineFilter = 'all' | 'earlier' | 'primary' | 'later';

const POSITION_LABELS: Record<Position, string> = { earlier: 'WCZEŚNIEJ', open: 'OTWARTY BOX', later: 'PÓŹNIEJ' };
const FILTERS: Array<{ value: TimelineFilter; label: string }> = [
  { value: 'all', label: 'Wszystkie' },
  { value: 'earlier', label: 'Wcześniejsze' },
  { value: 'primary', label: 'Źródła pierwotne' },
  { value: 'later', label: 'Późniejsze' },
];

const TIME_ZONE = 'Europe/Warsaw';
const dayFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, weekday: 'short', day: 'numeric', month: 'long' });
const shortDateFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, day: '2-digit', month: '2-digit' });
const hourFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, hour: '2-digit', minute: '2-digit', hour12: false });
const fullFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });

const time = (box: ContextBox) => new Date(box.publishedAt).getTime();
const dayKey = (box: ContextBox) => shortDateFormat.format(new Date(box.publishedAt));
const stamp = (box: ContextBox) => `${shortDateFormat.format(new Date(box.publishedAt))} · ${hourFormat.format(new Date(box.publishedAt))}`;
const isAd = (box: ContextBox) => box.type === 'reklama';

function pluralMaterials(count: number) {
  const tens = count % 100;
  const units = count % 10;
  if (count === 1) return 'materiał';
  if (units >= 2 && units <= 4 && (tens < 12 || tens > 14)) return 'materiały';
  return 'materiałów';
}

function positionOf(box: ContextBox, open: ContextBox): Position {
  if (box.id === open.id) return 'open';
  return time(box) < time(open) ? 'earlier' : 'later';
}

function relativeDistance(box: ContextBox, open: ContextBox) {
  const minutes = Math.round(Math.abs(time(box) - time(open)) / 60_000);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const parts = [days ? `${days} d` : '', hours ? `${hours} h` : '', !days && !hours ? `${minutes % 60} min` : ''].filter(Boolean);
  return parts.join(' ');
}

function TypeBadge({ box }: { box: ContextBox }) {
  return <span className={`mvp-ctx-type${isAd(box) ? ' is-ad' : ''}`}>{CONTEXT_TYPE_LABELS[box.type]}</span>;
}

export function BoxKontekstu({ boxes = DEMO_CONTEXT_BOXES, event = DEMO_CONTEXT_EVENT, exampleThread = DEMO_THREAD_EXAMPLE, demo = true }: {
  boxes?: ContextBox[];
  event?: ContextEvent;
  exampleThread?: string[];
  demo?: boolean;
}) {
  const uid = useId();
  const ids = { title: `${uid}-title`, panel: `${uid}-panel`, panelTitle: `${uid}-panel-title`, hint: `${uid}-hint`, thread: `${uid}-thread` };
  const chronology = useMemo(() => [...boxes].sort((a, b) => time(a) - time(b)), [boxes]);
  const byId = useMemo(() => new Map(boxes.map(box => [box.id, box])), [boxes]);

  const [openId, setOpenId] = useState<string | null>(null);
  const [filter, setFilter] = useState<TimelineFilter>('all');
  const [focusId, setFocusId] = useState<string | null>(null);
  const [thread, setThread] = useState<string[]>([]);
  const [announcement, setAnnouncement] = useState('');

  const sourceButtons = useRef(new Map<string, HTMLButtonElement>());
  const nodeButtons = useRef(new Map<string, HTMLButtonElement>());
  const panelTitle = useRef<HTMLHeadingElement>(null);
  const detail = useRef<HTMLDivElement>(null);
  const threadTitle = useRef<HTMLHeadingElement>(null);
  const focusPanelOnOpen = useRef(false);

  const open = openId ? byId.get(openId) ?? null : null;

  useEffect(() => {
    if (open && focusPanelOnOpen.current) {
      focusPanelOnOpen.current = false;
      panelTitle.current?.focus();
    }
  }, [open]);

  const visible = open
    ? chronology.filter(box => box.id === open.id || filter === 'all' || (filter === 'primary' ? box.primary : positionOf(box, open) === filter))
    : [];
  const rovingId = visible.some(box => box.id === focusId) ? focusId : open?.id ?? null;
  const counts = open
    ? {
        earlier: chronology.filter(box => positionOf(box, open) === 'earlier').length,
        later: chronology.filter(box => positionOf(box, open) === 'later').length,
        primary: chronology.filter(box => box.primary && box.id !== open.id).length,
      }
    : null;

  function announce(message: string) {
    setAnnouncement(message);
  }

  function showContext(id: string) {
    if (openId === id) {
      closeContext();
      return;
    }
    focusPanelOnOpen.current = true;
    setOpenId(id);
    setFocusId(id);
    setFilter('all');
  }

  function closeContext() {
    const previous = openId;
    setOpenId(null);
    announce('Kontekst zwinięty.');
    if (previous) window.requestAnimationFrame(() => sourceButtons.current.get(previous)?.focus());
  }

  function navigateTo(box: ContextBox) {
    if (box.id === openId) {
      detail.current?.focus();
      return;
    }
    setOpenId(box.id);
    setFocusId(box.id);
    announce(`Otwarty box: ${CONTEXT_TYPE_LABELS[box.type]}, ${box.source}, ${stamp(box)}.`);
  }

  function onTimelineKey(event: KeyboardEvent<HTMLOListElement>) {
    const moves: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (!(event.key in moves) && event.key !== 'Home' && event.key !== 'End') return;
    event.preventDefault();
    const index = Math.max(0, visible.findIndex(box => box.id === rovingId));
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? visible.length - 1 : Math.min(visible.length - 1, Math.max(0, index + moves[event.key]));
    const target = visible[next];
    if (!target) return;
    setFocusId(target.id);
    nodeButtons.current.get(target.id)?.focus();
  }

  function toggleThread(box: ContextBox) {
    const present = thread.includes(box.id);
    setThread(current => (present ? current.filter(id => id !== box.id) : [...current, box.id]));
    announce(present ? `Usunięto z nitki: ${box.title}.` : `Dodano do nitki jako materiał ${thread.length + 1}: ${box.title}.`);
  }

  function moveInThread(id: string, direction: -1 | 1) {
    const index = thread.indexOf(id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= thread.length) return;
    const next = [...thread];
    [next[index], next[target]] = [next[target], next[index]];
    setThread(next);
    announce(`Przesunięto na pozycję ${target + 1} z ${thread.length}.`);
  }

  function removeFromThread(id: string) {
    const box = byId.get(id);
    setThread(current => current.filter(item => item !== id));
    announce(`Usunięto z nitki: ${box?.title ?? 'materiał'}.`);
    threadTitle.current?.focus();
  }

  function sortThread() {
    if (thread.length < 2) return;
    setThread(current => [...current].sort((a, b) => time(byId.get(a)!) - time(byId.get(b)!)));
    announce('Nitka ułożona według daty publikacji.');
  }

  function fillExample() {
    const next = exampleThread.filter(id => byId.has(id));
    setThread(next);
    announce(`Wczytano przykładową nitkę: ${next.length} ${pluralMaterials(next.length)}.`);
  }

  function clearThread() {
    setThread([]);
    announce('Nitka wyczyszczona.');
  }

  const threadBoxes = thread.map(id => byId.get(id)).filter((box): box is ContextBox => Boolean(box));
  const adsInThread = threadBoxes.filter(isAd).length;

  return (
    <section className="mvp-section mvp-ctx" aria-labelledby={ids.title}>
      <header className="mvp-strip-heading">
        <div>
          <p className="mvp-editorial-kicker">SPIN.CLINIC · KONTEKST</p>
          <h2 id={ids.title}>Box kontekstu</h2>
        </div>
        <p>Box nie jest opinią. Jest punktem wejścia do materiału.</p>
      </header>

      {demo && (
        <p className="mvp-ctx-demo-note" role="note">
          <strong>DEMO</strong>
          <span>Dane przykładowe zapisane lokalnie w komponencie. {event.note} Widok nie wysyła żądań do API.</span>
        </p>
      )}

      <div className="mvp-ctx-event">
        <span className="mvp-ctx-label">WYDARZENIE</span>
        <strong>{event.title}</strong>
        <small>{event.place}</small>
      </div>

      <h3 className="mvp-ctx-subheading">
        Boxy źródłowe <span>{boxes.length} {pluralMaterials(boxes.length)} · wybierz box, aby zobaczyć oś czasu</span>
      </h3>
      <ul className="mvp-ctx-sources" aria-label="Boxy źródłowe">
        {chronology.map(box => {
          const isOpen = box.id === openId;
          const inThread = thread.includes(box.id);
          return (
            <li key={box.id}>
              <article className={`mvp-ctx-box${isOpen ? ' is-open' : ''}${isAd(box) ? ' is-ad' : ''}`}>
                <p className="mvp-ctx-meta">
                  <TypeBadge box={box} />
                  <time dateTime={box.publishedAt}>{stamp(box)}</time>
                </p>
                <p className="mvp-ctx-box-source">{box.source}</p>
                <h4 className="mvp-ctx-box-title">{box.title}</h4>
                {isAd(box) && <p className="mvp-ctx-ad-note">Materiał reklamowy · oznaczony</p>}
                <div className="mvp-ctx-box-actions">
                  <button
                    type="button"
                    ref={node => { if (node) sourceButtons.current.set(box.id, node); else sourceButtons.current.delete(box.id); }}
                    className="mvp-ctx-open"
                    aria-expanded={isOpen}
                    aria-controls={isOpen ? ids.panel : undefined}
                    onClick={() => showContext(box.id)}
                  >
                    {isOpen ? 'Zwiń kontekst' : 'Pokaż kontekst'}<span className="sr-only">: {box.title}</span>
                  </button>
                  <button type="button" className="mvp-ctx-add" aria-pressed={inThread} onClick={() => toggleThread(box)}>
                    {inThread ? '✓ W nitce' : '+ Do nitki'}<span className="sr-only">: {box.title}</span>
                  </button>
                </div>
              </article>
            </li>
          );
        })}
      </ul>

      {open && counts && (
        <section
          id={ids.panel}
          className="mvp-ctx-panel"
          aria-labelledby={ids.panelTitle}
          onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); closeContext(); } }}
        >
          <header className="mvp-ctx-panel-head">
            <div>
              <p className="mvp-ctx-label">OŚ CZASU ZDARZENIA</p>
              <h3 id={ids.panelTitle} ref={panelTitle} tabIndex={-1}>{open.title}</h3>
              <p className="mvp-ctx-counts">
                {counts.earlier} wcześniej · {counts.primary} źródła pierwotne · {counts.later} później
              </p>
            </div>
            <button type="button" className="quiet-button" onClick={closeContext}>
              Zwiń <span aria-hidden="true">✕</span><span className="sr-only"> kontekst i wróć do boxa</span>
            </button>
          </header>

          <div className="mvp-ctx-filters" role="group" aria-label="Pokaż na osi czasu">
            {FILTERS.map(option => (
              <button
                key={option.value}
                type="button"
                className={`mvp-pill${filter === option.value ? ' is-active' : ''}`}
                aria-pressed={filter === option.value}
                onClick={() => setFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>

          <p id={ids.hint} className="sr-only">
            Strzałki przenoszą między materiałami na osi. Enter otwiera wybrany box w kontekście. Escape zwija kontekst.
          </p>
          <ol className="mvp-ctx-timeline" aria-label="Materiały w kolejności publikacji" aria-describedby={ids.hint} onKeyDown={onTimelineKey}>
            {visible.map((box, index) => {
              const position = positionOf(box, open);
              const newDay = index === 0 || dayKey(visible[index - 1]) !== dayKey(box);
              const distance = position === 'open' ? '' : `${relativeDistance(box, open)} ${position === 'earlier' ? 'wcześniej' : 'później'}`;
              const label = [
                position === 'open' ? 'Otwarty box' : distance,
                `${CONTEXT_TYPE_LABELS[box.type]}, ${box.source}, ${fullFormat.format(new Date(box.publishedAt))}`,
                box.title,
                `Relacja: ${CONTEXT_ROLE_LABELS[box.role]}`,
                box.primary ? 'Źródło pierwotne' : '',
                isAd(box) ? 'Materiał reklamowy' : '',
              ].filter(Boolean).join('. ');
              return (
                <li
                  key={box.id}
                  className={`mvp-ctx-node is-${position}${box.primary ? ' is-primary' : ''}${isAd(box) ? ' is-ad' : ''}`}
                >
                  <span className="mvp-ctx-node-day" aria-hidden="true">{newDay ? dayFormat.format(new Date(box.publishedAt)) : ''}</span>
                  <span className="mvp-ctx-node-axis" aria-hidden="true"><i /></span>
                  <button
                    type="button"
                    ref={node => { if (node) nodeButtons.current.set(box.id, node); else nodeButtons.current.delete(box.id); }}
                    className="mvp-ctx-node-box"
                    tabIndex={box.id === rovingId ? 0 : -1}
                    aria-current={position === 'open' ? 'true' : undefined}
                    aria-label={label}
                    onFocus={() => setFocusId(box.id)}
                    onClick={() => navigateTo(box)}
                  >
                    <span className="mvp-ctx-node-pos">
                      {POSITION_LABELS[position]}
                      {distance && <small>{distance}</small>}
                    </span>
                    <span className="mvp-ctx-meta">
                      <TypeBadge box={box} />
                      <time dateTime={box.publishedAt}>{hourFormat.format(new Date(box.publishedAt))}</time>
                    </span>
                    <span className="mvp-ctx-node-source">{box.source}</span>
                    <strong>{box.title}</strong>
                    <span className="mvp-ctx-node-role">
                      {box.primary && <i className="mvp-ctx-primary-mark" aria-hidden="true" />}
                      {CONTEXT_ROLE_LABELS[box.role]}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>

          <div className="mvp-ctx-detail" ref={detail} tabIndex={-1} aria-label={`Szczegóły otwartego boxa: ${open.title}`}>
            <div className="mvp-ctx-detail-main">
              <p className="mvp-ctx-meta"><TypeBadge box={open} /><span>{open.source}</span></p>
              <p className="mvp-ctx-detail-summary">{open.summary}</p>
              {isAd(open) && <p className="mvp-ctx-ad-note">Materiał reklamowy — oznaczony przez wydawcę. Nie jest materiałem informacyjnym.</p>}
              <button type="button" className="mvp-ctx-add" aria-pressed={thread.includes(open.id)} onClick={() => toggleThread(open)}>
                {thread.includes(open.id) ? '✓ W mojej nitce — usuń' : '+ Dodaj do mojej nitki'}
              </button>
            </div>
            <dl className="mvp-ctx-facts">
              <div><dt>Źródło</dt><dd>{open.source}</dd></div>
              {open.author && <div><dt>Autor</dt><dd>{open.author}</dd></div>}
              <div><dt>Publikacja</dt><dd><time dateTime={open.publishedAt}>{fullFormat.format(new Date(open.publishedAt))}</time></dd></div>
              <div><dt>Pozyskanie</dt><dd>{open.acquisition}</dd></div>
              <div><dt>Relacja do wydarzenia</dt><dd>{CONTEXT_ROLE_LABELS[open.role]}{open.primary && open.role !== 'zrodlo-pierwotne' ? ' · źródło pierwotne' : ''}</dd></div>
              <div><dt>Link do oryginału</dt><dd>{demo ? 'w demo nieaktywny' : 'otwórz źródło'}</dd></div>
            </dl>
          </div>
          <p className="mvp-ctx-method">Relacje zapisała redakcja na podstawie dat, źródeł i treści metadanych. Oś jest mapą do samodzielnego porównania, nie werdyktem.</p>
        </section>
      )}

      <section className="mvp-ctx-thread-wrap" aria-labelledby={ids.thread}>
        <header className="mvp-ctx-thread-head">
          <div>
            <h3 id={ids.thread} ref={threadTitle} tabIndex={-1}>Moja nitka kontekstowa</h3>
            <p>
              {threadBoxes.length
                ? `${threadBoxes.length} ${pluralMaterials(threadBoxes.length)}${adsInThread ? ` · w tym ${adsInThread} ${adsInThread === 1 ? 'oznaczona reklama' : 'oznaczone reklamy'}` : ''} · zapisany widok, nie publikacja`
                : 'Zapisany widok, nie publikacja. Źródło pozostaje jedno — nitka tylko odwołuje się do boxów.'}
            </p>
          </div>
          <div className="mvp-ctx-thread-tools">
            <button type="button" className="quiet-button" aria-disabled={threadBoxes.length < 2} onClick={sortThread}>Ułóż chronologicznie</button>
            <button type="button" className="quiet-button" onClick={fillExample}>Wczytaj przykład</button>
            <button type="button" className="quiet-button" aria-disabled={!threadBoxes.length} onClick={clearThread}>Wyczyść</button>
          </div>
        </header>

        {threadBoxes.length === 0 ? (
          <p className="mvp-ctx-thread-empty">Nitka jest pusta. Dodaj box przyciskiem „+ Do nitki” albo wczytaj przykład.</p>
        ) : (
          <ol className="mvp-ctx-thread" aria-label="Materiały w mojej nitce">
            {threadBoxes.map((box, index) => (
              <li key={box.id} className={`mvp-ctx-thread-item${isAd(box) ? ' is-ad' : ''}`}>
                <span className="mvp-ctx-thread-index" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                <div className="mvp-ctx-thread-copy">
                  <p className="mvp-ctx-meta"><TypeBadge box={box} /><time dateTime={box.publishedAt}>{stamp(box)}</time></p>
                  <strong>{box.title}</strong>
                  <small>{box.source}{isAd(box) ? ' · materiał reklamowy' : ''}</small>
                </div>
                <div className="mvp-ctx-thread-actions">
                  <button type="button" aria-label={`Przesuń wcześniej: ${box.title}`} aria-disabled={index === 0} onClick={() => moveInThread(box.id, -1)}>
                    <span className="mvp-ctx-arrow-h" aria-hidden="true">←</span><span className="mvp-ctx-arrow-v" aria-hidden="true">↑</span>
                  </button>
                  <button type="button" aria-label={`Przesuń dalej: ${box.title}`} aria-disabled={index === threadBoxes.length - 1} onClick={() => moveInThread(box.id, 1)}>
                    <span className="mvp-ctx-arrow-h" aria-hidden="true">→</span><span className="mvp-ctx-arrow-v" aria-hidden="true">↓</span>
                  </button>
                  <button type="button" aria-label={`Usuń z nitki: ${box.title}`} onClick={() => removeFromThread(box.id)}>
                    <span aria-hidden="true">✕</span>
                  </button>
                </div>
              </li>
            ))}
          </ol>
        )}
        <p className="mvp-ctx-legend">
          Nitka może łączyć: artykuł · wywiad · reportaż · dokument · film · post · komunikat · <span className="mvp-ctx-type is-ad">REKLAMA</span> — reklama jest zawsze oznaczona.
        </p>
      </section>

      <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
      <p className="mvp-ctx-disclaimer">
        To nie jest automatyczna ocena ani mechanizm publikacji. Widok zestawia daty, źródła i relacje; wnioski należą do czytelnika.
      </p>
    </section>
  );
}
