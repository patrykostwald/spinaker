"use client";

import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react';
import {
  DEMO_COMMENTS,
  DEMO_ENTRY_IDS,
  DEMO_MATERIALS,
  DEMO_POLITICIAN,
  DEMO_REACTIONS,
  DEMO_TOPIC,
  MATERIAL_KIND_LABELS,
  SOURCE_KIND_LABELS,
  type DemoMaterial,
  type MaterialKind,
  type SourceKind,
} from '../lib/powiekszonyBoxDemo';
import { ProfilPolitykaBox } from './ProfilPolitykaBox';
import { ArticleFavoriteButton } from './ArticleFavoriteButton';
import { ArticleOpinions } from './ArticleOpinions';

type Period = 'all' | 'day' | 'three';
type Reaction = 'useful' | 'notUseful';

const KINDS: MaterialKind[] = ['artykul', 'dokument', 'post', 'film'];
const SOURCE_KINDS: SourceKind[] = ['media', 'instytucja', 'social', 'wideo'];
const PERIODS: Array<{ value: Period; label: string; days: number }> = [
  { value: 'all', label: 'Cały zakres', days: Infinity },
  { value: 'day', label: '±1 dzień od otwartego', days: 1 },
  { value: 'three', label: '±3 dni od otwartego', days: 3 },
];
const COMMENT_LIMIT = 500;

const TIME_ZONE = 'Europe/Warsaw';
const dayFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, weekday: 'short', day: 'numeric', month: 'long' });
const dayKeyFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' });
const shortDateFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, day: '2-digit', month: '2-digit' });
const hourFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, hour: '2-digit', minute: '2-digit', hour12: false });
const fullFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });

const time = (material: DemoMaterial) => new Date(material.publishedAt).getTime();
const dayKey = (material: DemoMaterial) => dayKeyFormat.format(new Date(material.publishedAt));
const stampAt = (iso: string) => `${shortDateFormat.format(new Date(iso))} · ${hourFormat.format(new Date(iso))}`;
const stamp = (material: DemoMaterial) => stampAt(material.publishedAt);

function plural(count: number, one: string, few: string, many: string) {
  const tens = count % 100;
  const units = count % 10;
  if (count === 1) return one;
  if (units >= 2 && units <= 4 && (tens < 12 || tens > 14)) return few;
  return many;
}

function distance(material: DemoMaterial, anchor: DemoMaterial) {
  if (material.id === anchor.id) return '';
  const minutes = Math.round(Math.abs(time(material) - time(anchor)) / 60_000);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const span = [days ? `${days} d` : '', hours ? `${hours} h` : '', !days && !hours ? `${minutes % 60} min` : ''].filter(Boolean).join(' ');
  return `${span} ${time(material) < time(anchor) ? 'wcześniej' : 'później'}`;
}

/* ——— Ikony: cienka linia, zawsze z etykietą tekstową obok ——— */

export function KindIcon({ kind }: { kind: MaterialKind | 'primary' }) {
  const common = { width: 14, height: 14, viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', strokeWidth: 1.2, 'aria-hidden': true, focusable: false } as const;
  switch (kind) {
    case 'artykul':
      return <svg {...common}><rect x="2.5" y="2.5" width="11" height="11" /><path d="M5 6h6M5 8.5h6M5 11h4" /></svg>;
    case 'dokument':
      return <svg {...common}><path d="M4 1.8h5.5L12.5 5v9.2H4z" /><path d="M9.5 1.8V5h3" /></svg>;
    case 'post':
      return <svg {...common}><path d="M2.5 3h11v7.5H7l-3 2.5v-2.5H2.5z" /></svg>;
    case 'film':
      return <svg {...common}><rect x="1.8" y="3" width="12.4" height="10" /><path d="M6.5 5.8v4.4L10.2 8z" /></svg>;
    default:
      return <svg {...common}><rect x="3" y="3" width="10" height="10" /><rect x="6.3" y="6.3" width="3.4" height="3.4" fill="currentColor" /></svg>;
  }
}

/* ——— Okno powiększonego boxa: natywny <dialog>, pułapka fokusu i Escape z przeglądarki ——— */

function ExpandedDialog({ open, onClose, labelledBy, children }: { open: boolean; onClose: () => void; labelledBy: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    returnFocus.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop = 0;
    document.body.style.overflow = 'hidden';
    const frame = window.requestAnimationFrame(() => document.getElementById(labelledBy)?.focus());
    return () => {
      window.cancelAnimationFrame(frame);
      if (dialog.open) dialog.close();
      document.body.style.overflow = previousOverflow;
      returnFocus.current?.focus();
    };
  }, [open, labelledBy]);
  return (
    <dialog
      ref={ref}
      className="mvp-xbox-dialog"
      aria-labelledby={labelledBy}
      onCancel={event => { event.preventDefault(); onClose(); }}
      onClick={event => { if (event.target === event.currentTarget) onClose(); }}
    >
      {open && (
        <div className="mvp-xbox-frame">
          <div className="mvp-xbox-bar">
            <span><strong>POWIĘKSZONY BOX</strong> · demo · dane fikcyjne · bez żądań do API</span>
            <button type="button" className="quiet-button" onClick={onClose}>
              Zamknij <span aria-hidden="true">✕</span><span className="sr-only"> powiększony box</span>
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

/* ——— Wybrany materiał: neutralne reakcje i komentarze ——— */

function SelectedMaterial({ material, anchor, reaction, onReact, myComment, onComment }: {
  material: DemoMaterial;
  anchor: DemoMaterial;
  reaction?: Reaction;
  onReact: (reaction: Reaction) => void;
  myComment?: string;
  onComment: (text: string) => void;
}) {
  const uid = useId();
  const [editing, setEditing] = useState(!myComment);
  const [draft, setDraft] = useState(myComment ?? '');
  const [reported, setReported] = useState<string[]>([]);
  const base = DEMO_REACTIONS[material.id] ?? { useful: 0, notUseful: 0 };
  const counts = { useful: base.useful + (reaction === 'useful' ? 1 : 0), notUseful: base.notUseful + (reaction === 'notUseful' ? 1 : 0) };
  const comments = DEMO_COMMENTS[material.id] ?? [];

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    onComment(text);
    setEditing(false);
  }

  return (
    <section className="mvp-xbox-selected" aria-labelledby={`${uid}-title`}>
      <p className="mvp-xbox-label">WYBRANY MATERIAŁ{material.id === anchor.id ? ' · otwarty w powiększeniu' : ` · ${distance(material, anchor)}`}</p>
      <div className="mvp-xbox-selected-grid">
        <div>
          <p className="mvp-xbox-meta">
            <span className="mvp-xbox-type">{material.label}</span>
            {material.primary && <span className="mvp-xbox-primary"><KindIcon kind="primary" />źródło pierwotne</span>}
          </p>
          <h3 id={`${uid}-title`}>{material.title}</h3>
          <p className="mvp-xbox-byline">{material.source} · <time dateTime={material.publishedAt}>{fullFormat.format(new Date(material.publishedAt))}</time>{material.author ? ` · ${material.author}` : ''}</p>
          <p className="mvp-xbox-desc">{material.description}</p>
          <p className="mvp-xbox-relation"><span>Podstawa powiązania:</span> {material.relation}</p>
          <p className="mvp-xbox-link">Oryginał: <span className="mvp-xbox-url">{material.url}</span> <small>(demo — link nieaktywny)</small></p>
        </div>

        {material.articleId ? (
          <div className="mvp-xbox-feedback mvp-xbox-live">
            <ArticleFavoriteButton articleId={material.articleId} title={material.title} />
            <ArticleOpinions article={{ id: material.articleId }} />
          </div>
        ) : (
        <div className="mvp-xbox-feedback">
          <p className="mvp-xbox-demo-flag">Demo: reakcje i komentarze nie są nigdzie zapisywane. Przy prawdziwym materiale zapisują się na Twoim koncie — jedna reakcja i jeden komentarz na materiał.</p>
          <div className="mvp-xbox-reactions" role="group" aria-labelledby={`${uid}-reactions`}>
            <p id={`${uid}-reactions`} className="mvp-xbox-label">CZY TEN MATERIAŁ BYŁ PRZYDATNY W ZESTAWIENIU?</p>
            <div>
              <button type="button" aria-pressed={reaction === 'useful'} onClick={() => onReact('useful')}>
                Przydatne <span className="mvp-xbox-count">{counts.useful}</span>
              </button>
              <button type="button" aria-pressed={reaction === 'notUseful'} onClick={() => onReact('notUseful')}>
                Nieprzydatne <span className="mvp-xbox-count">{counts.notUseful}</span>
              </button>
            </div>
            <small>Reakcja dotyczy przydatności materiału w tym zestawieniu. Nie ocenia osoby ani prawdziwości treści. W demo ponowne kliknięcie ją cofa.</small>
          </div>

          <div className="mvp-xbox-comments">
            <h4>Komentarze <span>{comments.length + (myComment ? 1 : 0)}</span></h4>
            {comments.length > 0 || myComment ? (
              <ol>
                {comments.map(comment => (
                  <li key={comment.id}>
                    <p><strong>{comment.author}</strong> · <time dateTime={comment.createdAt}>{stampAt(comment.createdAt)}</time></p>
                    <p>{comment.text}</p>
                    <button type="button" className="mvp-report-link" aria-pressed={reported.includes(comment.id)} onClick={() => setReported(current => current.includes(comment.id) ? current : [...current, comment.id])}>
                      {reported.includes(comment.id) ? 'Zgłoszono (demo — nie wysłano)' : 'Zgłoś komentarz'}<span className="sr-only"> użytkownika {comment.author}</span>
                    </button>
                  </li>
                ))}
                {myComment && !editing && (
                  <li className="is-mine">
                    <p><strong>Ty (demo)</strong> · zapisane tylko w tej karcie</p>
                    <p>{myComment}</p>
                    <button type="button" className="quiet-button" onClick={() => { setDraft(myComment); setEditing(true); }}>Edytuj komentarz</button>
                  </li>
                )}
              </ol>
            ) : (
              <p className="mvp-xbox-empty">Brak komentarzy do tego materiału.</p>
            )}
            {editing && (
              <form onSubmit={submit}>
                <label htmlFor={`${uid}-comment`}>{myComment ? 'Edytuj swój komentarz' : 'Twój komentarz (jeden na materiał)'}</label>
                <textarea
                  id={`${uid}-comment`}
                  value={draft}
                  maxLength={COMMENT_LIMIT}
                  rows={3}
                  aria-describedby={`${uid}-comment-help`}
                  onChange={event => setDraft(event.target.value)}
                />
                <p id={`${uid}-comment-help`} className="mvp-xbox-help">
                  {draft.length}/{COMMENT_LIMIT} znaków · W demo komentarz nie jest zapisywany ani publikowany.
                </p>
                <div className="mvp-xbox-form-actions">
                  <button type="submit" className="quiet-button" aria-disabled={!draft.trim()}>{myComment ? 'Zapisz zmiany' : 'Dodaj komentarz'}</button>
                  {myComment && <button type="button" className="quiet-button" onClick={() => setEditing(false)}>Anuluj</button>}
                </div>
              </form>
            )}
          </div>
        </div>
        )}
      </div>
    </section>
  );
}

/* ——— Powiększony box materiału ——— */

export function PowiekszonyBox({ materials = DEMO_MATERIALS, openedId, titleId }: { materials?: DemoMaterial[]; openedId: string; titleId: string }) {
  const uid = useId();
  const chronology = useMemo(() => [...materials].sort((a, b) => time(a) - time(b)), [materials]);
  const opened = chronology.find(material => material.id === openedId) ?? chronology[0];
  const related = chronology.filter(material => material.id !== opened.id);

  const [kinds, setKinds] = useState<Set<MaterialKind>>(() => new Set(KINDS));
  const [sources, setSources] = useState<Set<SourceKind>>(() => new Set(SOURCE_KINDS));
  const [period, setPeriod] = useState<Period>('all');
  const [primaryOnly, setPrimaryOnly] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selectedId, setSelectedId] = useState(opened.id);
  const [focusId, setFocusId] = useState(opened.id);
  const [reactions, setReactions] = useState<Record<string, Reaction | undefined>>({});
  const [myComments, setMyComments] = useState<Record<string, string>>({});
  const [announcement, setAnnouncement] = useState('');
  const itemButtons = useRef(new Map<string, HTMLButtonElement>());

  const periodDays = PERIODS.find(option => option.value === period)?.days ?? Infinity;
  const matches = (material: DemoMaterial) =>
    kinds.has(material.kind) &&
    sources.has(material.sourceKind) &&
    (!primaryOnly || material.primary) &&
    Math.abs(time(material) - time(opened)) <= periodDays * 86_400_000;
  const visible = chronology.filter(material => material.id === opened.id || matches(material));
  const selected = visible.find(material => material.id === selectedId) ?? opened;
  const rovingId = visible.some(material => material.id === focusId) ? focusId : selected.id;

  const rows: Array<{ key: string; items: DemoMaterial[] }> = [];
  for (const material of visible) {
    const key = dayKey(material);
    const last = rows[rows.length - 1];
    if (last?.key === key) last.items.push(material);
    else rows.push({ key, items: [material] });
  }

  const counts = {
    artykul: related.filter(material => material.kind === 'artykul').length,
    dokument: related.filter(material => material.kind === 'dokument').length,
    post: related.filter(material => material.kind === 'post').length,
    film: related.filter(material => material.kind === 'film').length,
    primary: related.filter(material => material.primary).length,
  };
  const activeFilters = (kinds.size < KINDS.length ? 1 : 0) + (sources.size < SOURCE_KINDS.length ? 1 : 0) + (period !== 'all' ? 1 : 0) + (primaryOnly ? 1 : 0);
  const hiddenRelated = related.length - visible.filter(material => material.id !== opened.id).length;

  const span = { start: time(chronology[0]), end: time(chronology[chronology.length - 1]) };
  const position = (material: DemoMaterial) => (span.end === span.start ? 50 : ((time(material) - span.start) / (span.end - span.start)) * 100);
  const selectedIndex = chronology.findIndex(material => material.id === selected.id);

  function toggleInSet<T>(set: Set<T>, value: T) {
    const next = new Set(set);
    if (next.has(value)) next.delete(value); else next.add(value);
    return next;
  }

  function soloKind(kind: MaterialKind) {
    const solo = kinds.size === 1 && kinds.has(kind);
    setKinds(solo ? new Set(KINDS) : new Set([kind]));
    setAnnouncement(solo ? 'Pokazuję wszystkie typy materiałów.' : `Filtr: tylko ${MATERIAL_KIND_LABELS[kind].plural.toLowerCase()}.`);
  }

  function resetFilters() {
    setKinds(new Set(KINDS));
    setSources(new Set(SOURCE_KINDS));
    setPeriod('all');
    setPrimaryOnly(false);
    setAnnouncement('Filtry wyczyszczone.');
  }

  function select(material: DemoMaterial) {
    setSelectedId(material.id);
    setFocusId(material.id);
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    itemButtons.current.get(material.id)?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reduced ? 'auto' : 'smooth' });
    setAnnouncement(`Wybrany materiał: ${material.label}, ${material.source}, ${stamp(material)}. Reakcje i komentarze poniżej osi.`);
  }

  function react(material: DemoMaterial, reaction: Reaction) {
    const next = reactions[material.id] === reaction ? undefined : reaction;
    setReactions(current => ({ ...current, [material.id]: next }));
    setAnnouncement(next ? `Zapisano reakcję: ${next === 'useful' ? 'przydatne' : 'nieprzydatne'}.` : 'Reakcja cofnięta.');
  }

  function onStripKey(event: KeyboardEvent<HTMLOListElement>) {
    const flat = visible;
    const index = Math.max(0, flat.findIndex(material => material.id === rovingId));
    const rowIndex = rows.findIndex(row => row.items.some(material => material.id === rovingId));
    let target: DemoMaterial | undefined;
    if (event.key === 'ArrowRight') target = flat[Math.min(flat.length - 1, index + 1)];
    else if (event.key === 'ArrowLeft') target = flat[Math.max(0, index - 1)];
    else if (event.key === 'ArrowDown') target = rows[Math.min(rows.length - 1, rowIndex + 1)]?.items[0];
    else if (event.key === 'ArrowUp') target = rows[Math.max(0, rowIndex - 1)]?.items[0];
    else if (event.key === 'Home') target = flat[0];
    else if (event.key === 'End') target = flat[flat.length - 1];
    else return;
    event.preventDefault();
    if (!target) return;
    setFocusId(target.id);
    itemButtons.current.get(target.id)?.focus();
  }

  const counters: Array<{ key: MaterialKind | 'primary'; label: string; count: number; pressed: boolean; onClick: () => void }> = [
    ...KINDS.map(kind => ({
      key: kind,
      label: MATERIAL_KIND_LABELS[kind].plural,
      count: counts[kind],
      pressed: kinds.size === 1 && kinds.has(kind),
      onClick: () => soloKind(kind),
    })),
    {
      key: 'primary' as const,
      label: 'Źródła pierwotne',
      count: counts.primary,
      pressed: primaryOnly,
      onClick: () => { setPrimaryOnly(value => !value); setAnnouncement(primaryOnly ? 'Pokazuję wszystkie źródła.' : 'Filtr: tylko źródła pierwotne.'); },
    },
  ];

  return (
    <div className="mvp-xbox">
      <header className="mvp-xbox-head">
        <p className="mvp-xbox-meta">
          <span className="mvp-xbox-type">{opened.label}</span>
          {opened.primary && <span className="mvp-xbox-primary"><KindIcon kind="primary" />źródło pierwotne</span>}
          <span>Temat: {DEMO_TOPIC.label}</span>
        </p>
        <h2 id={titleId} tabIndex={-1}>{opened.title}</h2>
        <p className="mvp-xbox-byline">{opened.source} · <time dateTime={opened.publishedAt}>{fullFormat.format(new Date(opened.publishedAt))}</time>{opened.author ? ` · ${opened.author}` : ''}</p>
        <p className="mvp-xbox-desc">{opened.description}</p>
        <p className="mvp-xbox-link">Oryginał: <span className="mvp-xbox-url">{opened.url}</span> <small>(demo — link nieaktywny)</small></p>
      </header>

      <div className="mvp-xbox-counters" role="group" aria-label="Powiązane materiały — kliknij licznik, aby filtrować">
        {counters.map(counter => (
          <button key={counter.key} type="button" aria-pressed={counter.pressed} onClick={counter.onClick}>
            <KindIcon kind={counter.key} />
            <span>{counter.label}</span>
            <strong>{counter.count}</strong>
          </button>
        ))}
      </div>

      <div className="mvp-xbox-body">
        <div className="mvp-xbox-main-head">
          <h3>Chronologia powiązań <span>{visible.length - 1} z {related.length} powiązanych{hiddenRelated ? ` · ${hiddenRelated} ukryte filtrami` : ''}</span></h3>
          <button type="button" className="mvp-xbox-filters-toggle quiet-button" aria-expanded={filtersOpen} aria-controls={`${uid}-filters`} onClick={() => setFiltersOpen(value => !value)}>
            Filtry{activeFilters ? ` (${activeFilters})` : ''}
          </button>
        </div>

        <aside id={`${uid}-filters`} className={`mvp-xbox-filters${filtersOpen ? ' is-open' : ''}`} aria-label="Filtry powiązanych materiałów">
          <fieldset>
            <legend>Typ materiału</legend>
            {KINDS.map(kind => (
              <label key={kind}>
                <input type="checkbox" checked={kinds.has(kind)} onChange={() => setKinds(current => toggleInSet(current, kind))} />
                <KindIcon kind={kind} /> {MATERIAL_KIND_LABELS[kind].plural} <small>{counts[kind]}</small>
              </label>
            ))}
          </fieldset>
          <fieldset>
            <legend>Typ źródła</legend>
            {SOURCE_KINDS.map(kind => (
              <label key={kind}>
                <input type="checkbox" checked={sources.has(kind)} onChange={() => setSources(current => toggleInSet(current, kind))} />
                {SOURCE_KIND_LABELS[kind]} <small>{related.filter(material => material.sourceKind === kind).length}</small>
              </label>
            ))}
          </fieldset>
          <fieldset>
            <legend>Okres</legend>
            {PERIODS.map(option => (
              <label key={option.value}>
                <input type="radio" name={`${uid}-period`} value={option.value} checked={period === option.value} onChange={() => setPeriod(option.value)} />
                {option.label}
              </label>
            ))}
          </fieldset>
          <fieldset>
            <legend>Pochodzenie</legend>
            <label>
              <input type="checkbox" checked={primaryOnly} onChange={() => setPrimaryOnly(value => !value)} />
              <KindIcon kind="primary" /> Tylko źródła pierwotne <small>{counts.primary}</small>
            </label>
          </fieldset>
          <button type="button" className="quiet-button" aria-disabled={!activeFilters} onClick={resetFilters}>Wyczyść filtry</button>
          <p className="mvp-xbox-filters-note">
            Powiązania są automatyczne — po haśle, tagu, osobie, instytucji, źródle i dacie, jak w Temacie dnia. Ręczną nitkę kontekstową układa wyłącznie Dr Spin.
          </p>
        </aside>
        <div className="mvp-xbox-main">
          <div className="mvp-xbox-overview">
            <div className="mvp-xbox-overview-track" aria-hidden="true">
              {chronology.map(material => (
                <i
                  key={material.id}
                  className={`${visible.includes(material) ? 'is-visible' : ''}${material.primary ? ' is-primary' : ''}${material.id === selected.id ? ' is-selected' : ''}`}
                  style={{ left: `${position(material)}%` }}
                />
              ))}
              <b style={{ left: `${position(selected)}%` }} />
            </div>
            <p className="mvp-xbox-overview-caption">
              <span>{stamp(chronology[0])}</span>
              <span>Wybrany: {stamp(selected)} · {selectedIndex + 1}. z {chronology.length} w kolejności publikacji</span>
              <span>{stamp(chronology[chronology.length - 1])}</span>
            </p>
          </div>

          <p id={`${uid}-hint`} className="sr-only">Strzałki w lewo i w prawo przenoszą między materiałami, w górę i w dół między dniami. Enter wybiera materiał.</p>
          <ol className="mvp-xbox-rows" aria-label="Materiały według dni publikacji" aria-describedby={`${uid}-hint`} onKeyDown={onStripKey}>
            {rows.map(row => {
              const first = row.items[0];
              const hasSelected = row.items.some(material => material.id === selected.id);
              const relation = row.key === dayKey(opened) ? 'dzień otwartego materiału' : time(first) < time(opened) ? 'wcześniej' : 'później';
              return (
                <li key={row.key} className={`mvp-xbox-row${hasSelected ? ' has-selected' : ''}`}>
                  <div className="mvp-xbox-row-label">
                    <span className="mvp-xbox-row-dot" aria-hidden="true" />
                    <h4>{dayFormat.format(new Date(first.publishedAt))}</h4>
                    <small>{relation} · {row.items.length} {plural(row.items.length, 'materiał', 'materiały', 'materiałów')}</small>
                  </div>
                  <ul className="mvp-xbox-strip">
                    {row.items.map(material => {
                      const isSelected = material.id === selected.id;
                      const isOpened = material.id === opened.id;
                      return (
                        <li key={material.id}>
                          <button
                            type="button"
                            ref={node => { if (node) itemButtons.current.set(material.id, node); else itemButtons.current.delete(material.id); }}
                            className={`mvp-xbox-item${isSelected ? ' is-selected' : ''}${isOpened ? ' is-opened' : ''}${material.primary ? ' is-primary' : ''}`}
                            tabIndex={material.id === rovingId ? 0 : -1}
                            aria-current={isSelected ? 'true' : undefined}
                            aria-controls={`${uid}-selected`}
                            onFocus={() => setFocusId(material.id)}
                            onClick={() => select(material)}
                          >
                            <span className="mvp-xbox-item-top">
                              <span className="mvp-xbox-type">{material.label}</span>
                              <time dateTime={material.publishedAt}>{hourFormat.format(new Date(material.publishedAt))}</time>
                            </span>
                            <span className="mvp-xbox-item-source">{material.source}</span>
                            <strong>{material.title}</strong>
                            <span className="mvp-xbox-item-rel">
                              {material.primary && <><KindIcon kind="primary" /><span className="sr-only">Źródło pierwotne. </span></>}
                              {isOpened ? 'otwarty w powiększeniu' : `${distance(material, opened)} · ${material.relation}`}
                            </span>
                            {isSelected && <span className="mvp-xbox-item-flag">WYBRANY<span className="sr-only"> materiał</span></span>}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </li>
              );
            })}
          </ol>
          {visible.length === 1 && (
            <p className="mvp-xbox-empty">
              Filtry ukryły wszystkie powiązane materiały. <button type="button" className="quiet-button" onClick={resetFilters}>Wyczyść filtry</button>
            </p>
          )}

          <div id={`${uid}-selected`}>
            <SelectedMaterial
              key={selected.id}
              material={selected}
              anchor={opened}
              reaction={reactions[selected.id]}
              onReact={reaction => react(selected, reaction)}
              myComment={myComments[selected.id]}
              onComment={text => { setMyComments(current => ({ ...current, [selected.id]: text })); setAnnouncement('Komentarz zapisany w tej karcie (demo).'); }}
            />
          </div>
        </div>

      </div>

      <p className="mvp-xbox-disclaimer">
        Powiększenie pokazuje relacje i chronologię. Nie ocenia automatycznie materiału ani osoby.
      </p>
      <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
    </div>
  );
}

/* ——— Strona demo: boxy wejściowe i okno powiększenia ——— */

type OpenTarget = { kind: 'material'; id: string } | { kind: 'profile' } | null;

export function PowiekszonyBoxDemo({ materials = DEMO_MATERIALS, entryIds = DEMO_ENTRY_IDS }: { materials?: DemoMaterial[]; entryIds?: string[] }) {
  const uid = useId();
  const titleId = `${uid}-dialog-title`;
  const [target, setTarget] = useState<OpenTarget>(null);
  const entries = entryIds.map(id => materials.find(material => material.id === id)).filter((material): material is DemoMaterial => Boolean(material));

  return (
    <section className="mvp-section mvp-xbox-demo" aria-labelledby={`${uid}-title`}>
      <header className="mvp-strip-heading">
        <div>
          <p className="mvp-editorial-kicker">SPIN.CLINIC · DEMO</p>
          <h2 id={`${uid}-title`}>Powiększony box materiału</h2>
        </div>
        <p>Relacje i chronologia zamiast werdyktu.</p>
      </header>
      <p className="mvp-xbox-demo-note" role="note">
        <strong>DEMO</strong>
        <span>Dane fikcyjne zapisane lokalnie w komponencie. {DEMO_TOPIC.note} Widok nie wysyła żądań do API.</span>
      </p>

      <ul className="mvp-xbox-principles" aria-label="Jak działają funkcje portalu">
        <li><strong>Wyszukiwarka</strong> znajduje materiały po haśle, tagu, osobie, instytucji, źródle i dacie.</li>
        <li><strong>Temat dnia</strong> pokazuje automatycznie powiązane newsy w kolejności publikacji.</li>
        <li><strong>Dr Spin</strong> jest jedynym miejscem, w którym redakcja ręcznie układa nitkę kontekstową.</li>
        <li><strong>Powiększony box</strong> pokazuje relacje i chronologię — bez automatycznej oceny.</li>
      </ul>

      <h3 className="mvp-xbox-demo-subheading">Materiały <span>kliknij box, aby go powiększyć</span></h3>
      <ul className="mvp-xbox-entries">
        {entries.map(material => (
          <li key={material.id}>
            <button type="button" className="mvp-xbox-entry" aria-haspopup="dialog" onClick={() => setTarget({ kind: 'material', id: material.id })}>
              <span className="mvp-xbox-item-top"><span className="mvp-xbox-type">{material.label}</span><time dateTime={material.publishedAt}>{stamp(material)}</time></span>
              <span className="mvp-xbox-item-source">{material.source}</span>
              <strong>{material.title}</strong>
              <span className="mvp-xbox-entry-cta" aria-hidden="true">Powiększ →</span>
              <span className="sr-only">. Otwórz powiększony box.</span>
            </button>
          </li>
        ))}
      </ul>

      <h3 className="mvp-xbox-demo-subheading">Wariant: profil polityka <span>głosowania i podmioty w rejestrach</span></h3>
      <ul className="mvp-xbox-entries">
        <li>
          <button type="button" className="mvp-xbox-entry is-profile" aria-haspopup="dialog" onClick={() => setTarget({ kind: 'profile' })}>
            <span className="mvp-xbox-item-top"><span className="mvp-xbox-type">PROFIL</span><span>{DEMO_POLITICIAN.fictionalNote}</span></span>
            <span className="mvp-xbox-item-source">{DEMO_POLITICIAN.publicRole}</span>
            <strong>{DEMO_POLITICIAN.name}</strong>
            <span className="mvp-xbox-entry-cta" aria-hidden="true">Powiększ →</span>
            <span className="sr-only">. Otwórz powiększony profil.</span>
          </button>
        </li>
      </ul>

      <ExpandedDialog open={target !== null} onClose={() => setTarget(null)} labelledBy={titleId}>
        {target?.kind === 'material' && <PowiekszonyBox key={target.id} materials={materials} openedId={target.id} titleId={titleId} />}
        {target?.kind === 'profile' && <ProfilPolitykaBox titleId={titleId} />}
      </ExpandedDialog>
    </section>
  );
}
