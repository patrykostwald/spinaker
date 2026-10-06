"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getThreadBox, getThreadSteps, rateThreadStep, type StepPart, type StepsData, type ThreadElement } from '../../lib/community';
import { apiFetch, apiWrite } from '../../lib/api';
import { useAccount, emailVerified } from '../../lib/account';
import { useFeature } from '../../lib/features';
import { Avatar, ago, SocialIcon, RATINGS } from './SocialPrimitives';
import { setReactionMood, sumCounts } from '../../lib/mood';
import { formatDatePl } from '../../lib/utils';
import { clipColor } from '../../lib/clipColor';
import { AccountDialog } from '../AccountDialog';

const LABELS = { positive: 'Trafne', doubt: 'Wątpliwe', negative: 'Nietrafne' } as const;
/** Rodzaje boksów po polsku (wspólne dla paska spinki i widoku jednego elementu). */
export const BOX_TYPES = { post: 'Wpis na X', claim: 'Sprawdzenie', source: 'Źródło', technique: 'Chwyt', diagnosis: 'Diagnoza', message: 'Przekaz dnia', print: 'Druk sejmowy', amendment: 'Poprawka', consultation: 'Postulat organizacji', registry: 'Wpis w rejestrze', declaration: 'Zgłoszenie w uzasadnieniu', summary: 'Podsumowanie Dr. Spina' } as const;
/** Ikony kierunku A (właściciel 6.10): rodzaje boksów i połączeń jedną kreską. */
const GLYPHS: Record<string, string> = {
  diag: '<path d="M3 12h4l2.2-5 4.6 10 2.2-5H21"/>', post: '<path d="M4.5 5.5h15v10.5H10l-5.5 4z"/>',
  hook: '<path d="M15.5 3v10a5 5 0 0 1-10 0v-2.5l3 3"/>', check: '<circle cx="10.5" cy="10.5" r="6"/><path d="M20 20l-5-5"/><path d="M8 10.5l2 2 3.2-3.5"/>',
  doc: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 16h5"/>', sejm: '<path d="M4 20h16M5 10h14M12 4l8 6H4zM7 10v8M12 10v8M17 10v8"/>',
  from: '<circle cx="5.5" cy="12" r="2.2"/><path d="M8 12h11M15 8l4 4-4 4"/>', how: '<path d="M4 20l9-9"/><path d="M15 3.5l1.3 3.2 3.2 1.3-3.2 1.3L15 12.5l-1.3-3.2L10.5 8l3.2-1.3z"/>',
  ask: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.4 2.4c-.6.3-1 .8-1 1.5v.6"/><path d="M12 17v.01"/>',
  because: '<path d="M5 12h14M14 7l5 5-5 5"/>', but: '<path d="M3 12h7l4-5h7M10 12l4 5h7"/>', not: '<path d="M5 9h14M5 15h14M16 5L8 19"/>',
  pin: '<path d="M2.5 9.5h15a3 3 0 0 1 0 6h-11a1.5 1.5 0 0 1 0-3h12"/>',
};
export const TYPE_GLYPH: Record<string, string> = { diagnosis: 'diag', summary: 'diag', post: 'post', message: 'post', technique: 'hook', claim: 'check', source: 'doc', consultation: 'doc', registry: 'doc', declaration: 'doc', print: 'sejm', amendment: 'sejm' };
export const LINK_GLYPH: Record<string, string> = { wynika_z: 'from', jak: 'how', czy_na_pewno: 'ask', bo: 'because', ale: 'but', przeczy: 'not' };
export const LINK_WORDS: Record<string, string> = { bo: 'bo', ale: 'ale', czy_na_pewno: 'czy na pewno?', przeczy: 'przeczy', wynika_z: 'wynika z', jak: 'jak?' };
export function Glyph({ name, size = 16 }: { name: string; size?: number }) {
  return <svg className="sc-glyph" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" dangerouslySetInnerHTML={{ __html: GLYPHS[name] ?? GLYPHS.doc }} />;
}
/** Tytuł boksu bez przedrostka stanu („Niezweryfikowane: …”, „Diagnoza: …”); stan idzie do małej etykiety po prawej. */
export function splitTitle(item: ThreadElement): { tag: string; title: string; spin?: number } {
  const s = /^Spin (\d{1,3})\/100:\s+(.+)$/.exec(item.title);
  if (s) return { tag: `Spin ${s[1]}/100`, title: s[2], spin: Number(s[1]) };
  const m = /^(Niezweryfikowane|Zweryfikowane|Potwierdzone|Fałsz|Fałszywe|Prawda|Częściowo prawdziwe|Manipulacja|Diagnoza):\s+(.+)$/.exec(item.title);
  const tag = item.box_type === 'diagnosis' && item.intensity != null ? `Spin ${item.intensity}/100` : m && m[1] !== 'Diagnoza' ? m[1] : '';
  return { tag, title: m ? m[2] : item.title, spin: item.box_type === 'diagnosis' && item.intensity != null ? item.intensity : undefined };
}

/** Podpis odnośnika zależny od tego, dokąd prowadzi (panel designu 6.10: „Otwórz źródło” przy diagnozie mylił). */
export function linkLabel(item: ThreadElement): string {
  if (item.box_type === 'diagnosis' || item.url.startsWith('/klinika')) return 'Otwórz diagnozę →';
  if (item.box_type === 'post' || /(^|\.)(x|twitter)\.com\//.test(item.url)) return 'Otwórz wpis na X ↗';
  return item.url.startsWith('/') ? 'Otwórz →' : 'Otwórz źródło ↗';
}

/**
 * Trop ocenia się krok po kroku (właściciel 3.10): każdy boks i każde powiązanie dostaje ✓ ? ✕,
 * a wynik tropu to średnia wszystkich reakcji (backend news/thread_steps.py).
 */
export function useThreadSteps(threadId: number, enabled: boolean) {
  const cache = useQueryClient();
  const account = useAccount();
  const accounts = useFeature('ACCOUNTS_ENABLED');
  const canRate = Boolean(accounts && account.data?.authenticated && emailVerified(account.data));
  const query = useQuery({ queryKey: ['thread-steps', threadId, account.data?.user?.id], queryFn: () => getThreadSteps(threadId), enabled, retry: false, staleTime: 30_000 });
  const find = (itemId: number | undefined, part: StepPart) => query.data?.steps.find(step => step.item_id === itemId && step.part === part);
  async function rate(itemId: number, part: StepPart, polarity: string) {
    const data = await rateThreadStep(threadId, itemId, part, polarity);
    cache.setQueryData(['thread-steps', threadId, account.data?.user?.id], data);
    void cache.invalidateQueries({ queryKey: ['community-threads'] });
  }
  return { data: query.data as StepsData | undefined, find, rate, canRate };
}

export function StepRate({ step, onRate, canRate, label, withLabels = false }: {
  step?: { counts: Record<string, number>; mine: string | null }; onRate: (polarity: string) => void; canRate: boolean; label: string;
  /** Wersja z podpisami (strefa „Oceń” pod kartą): ten sam przycisk i ta sama obsługa, tylko ze słowem obok znaku. */
  withLabels?: boolean;
}) {
  // zawsze klikalne (właściciel 5.10): bez konta kliknięcie zaprasza do logowania lub założenia konta
  const [invite, setInvite] = useState(false);
  return <span className={`sc-step-rate${withLabels ? ' sc-step-rate--labels' : ''}`} role="group" aria-label={`Oceń: ${label}`}>
    {RATINGS.map(key => <button key={key} type="button" data-rating={key} aria-pressed={step?.mine === key} aria-label={`${LABELS[key]} (${step?.counts[key] ?? 0})`}
      title={canRate ? `${LABELS[key]}: ${step?.counts[key] ?? 0}` : `${LABELS[key]}: załóż konto, aby oceniać`}
      onClick={event => { event.stopPropagation(); if (canRate) onRate(key); else setInvite(true); }}>
      <SocialIcon kind={key} />{withLabels && <span>{LABELS[key]}</span>}</button>)}
    <AccountDialog open={invite} onClose={() => setInvite(false)} reason="rate" />
  </span>;
}

/** Postęp przejścia tropu i wynik całości. */
export function StepProgress({ data, canRate }: { data?: StepsData; canRate: boolean }) {
  if (!data) return null;
  const { done, total } = data.progress;
  const share = total ? done / total : 0;
  return <p className="sc-step-progress" aria-label={canRate ? `Przejście spinki: ${done} z ${total} kroków` : 'Zaloguj się, aby przejść spinkę'}>
    <span className="sc-step-progress__bar" aria-hidden="true"><span style={{ width: `${100 * share}%` }} /></span>
  </p>;
}


type Counts3 = { positive: number; doubt: number; negative: number };

/**
 * Spinka (właściciel 3.10): kreska z zawijasem w górę, która „spina” następny boks.
 * Kolor = reakcje czytelników (zielony ✓, żółty ?, czerwony ✕ w proporcji); bez reakcji - szara.
 */
export function SpinkaClip({ counts, open = false, neutral = false }: { counts?: Counts3; id?: string; open?: boolean; neutral?: boolean }) {
  // kolor = głos autora (✓) + weryfikacja innych, płynna skala i nasycenie (lib/clipColor, właściciel 4.10)
  const color = neutral ? 'var(--sc-ctx)' : clipColor(counts);
  // zatrzask (właściciel 3.10): linia od boksu do boksu, pośrodku dwa zazębione ogniwa = spięcie dwóch materiałów.
  // Rozwinięta: ogniwa płynnie rozprostowują się w jedną prostą linię; po zwinięciu znów zaczepiają się w zatrzask.
  return <span className={`sc-clip sc-clasp${open ? ' is-open' : ''}`} style={{ color }} aria-hidden="true">
    <i className="sc-clasp__line" /><span className="sc-clasp__knot"><i /><i /></span><i className="sc-clasp__line" />
  </span>;
}

export type FocusStep = { kind: 'box' | 'clip'; index: number };

/** Element wybrany w spince: odnośnik w komentarzach (@b1, @s1) i jego nazwa do nagłówka komentarzy. */
export type FocusRef = { ref: string; label: string; pattern: RegExp };

export function focusRef(step: FocusStep): FocusRef {
  return step.kind === 'box'
    ? { ref: `@b${step.index + 1}`, label: `boks ${step.index + 1}`, pattern: new RegExp(String.raw`@(?:boks\s*|b)${step.index + 1}(?!\d)`, 'i') }
    : { ref: `@s${step.index}`, label: `spinka ${step.index}`, pattern: new RegExp(String.raw`@(?:spinka\s*|s)${step.index}(?!\d)`, 'i') };
}

/**
 * Wybrany boks albo spinka (właściciel 3.10): widok się nie przeskakuje. Karta zastępuje łańcuch u góry otwartej spinki
 * (z lewej miniatura, z prawej tekst), po bokach strzałki, licznik i mini-łańcuch z podświetlonym elementem.
 * Komentarze zostają na dole w tym samym miejscu, tylko zawężone do tego elementu (onStep przekazuje odnośnik).
 */
/** Obrazek boksu; boks diagnozy bez obrazka dostaje kartę diagnozy (właściciel 5.10: pierwszy boks zmienia się w miniaturę). */
export function boxImage(item: ThreadElement): string {
  if (item.image_url) return item.image_url;
  const id = item.box_type === 'diagnosis' ? (item.diagnosis_id ?? Number(/\/klinika\/(\d+)/.exec(item.url)?.[1] ?? NaN)) : NaN;
  return Number.isFinite(id) ? `/api/clinic/spins/${id}/card.png` : '';
}
/** Rodzaj treści boksu (werdykt panelu agentów 5.10, pomysł właściciela): po polsku, nie kodami. */
export function contentTag(item: ThreadElement): 'LINK' | 'FILM' | 'ZDJĘCIE' | 'TEKST' {
  const url = item.url || '';
  if (/youtube\.com|youtu\.be|vimeo\.com|tiktok\.com|\.mp4($|\?)/i.test(url)) return 'FILM';
  if (/\.(jpe?g|png|webp|gif)($|\?)/i.test(url)) return 'ZDJĘCIE';
  if (!url) return 'TEKST';
  return 'LINK';
}

/** Rodzaj boksu małą literą do zdań („chwyt”, „wpis na X”). */
const typeLower = (item: ThreadElement) => { const word: string = item.box_type ? BOX_TYPES[item.box_type as keyof typeof BOX_TYPES] : 'materiał'; return word.charAt(0).toLowerCase() + word.slice(1); };

/** Mały boks w lewym polu połączenia: rodzaj, numer i tytuł (zamiast pustego prostokąta, właściciel 6.10). */
function MiniBox({ item, n }: { item: ThreadElement; n: number }) {
  return <span className="sc-pick__mini">
    <span className="sc-pick__mini-k"><Glyph name={TYPE_GLYPH[item.box_type ?? ''] ?? 'doc'} size={14} />Boks&nbsp;{n}</span>
    <b>{splitTitle(item).title}</b>
  </span>;
}

/** Lewe pole wybranego połączenia: dwa spięte boksy jako małe karty, między nimi znak połączenia w kolorze reakcji. */
function JointPreview({ from, to, index, counts }: { from: ThreadElement; to: ThreadElement; index: number; counts?: Counts3 }) {
  return <span className="sc-pick__pairviz" aria-hidden="true">
    <MiniBox item={from} n={index} />
    <span className="sc-pick__pairjoint" style={{ color: clipColor(counts) }}>
      <i /><span className="sc-rel"><Glyph name={LINK_GLYPH[to.link_kind ?? ''] ?? 'pin'} size={16} />{LINK_WORDS[to.link_kind ?? ''] ?? 'połączenie'}</span><i />
    </span>
    <MiniBox item={to} n={index + 1} />
  </span>;
}

/**
 * Strefa pod mini-paskiem (właściciel 6.10): dwie linie wyjaśnienia dla nowego czytelnika i jedno wezwanie „Oceń”.
 * Ta sama obsługa i ten sam stan co ✕ ? ✓ w stopce karty (StepRate i steps.rate), więc obie oceny zawsze się zgadzają.
 * Stała wysokość: przejście między boksami i połączeniami nic nie przesuwa.
 */
function StepGuide({ why, current, canRate, label, noun, onRate }: {
  why: string; current?: { counts: Record<string, number>; mine: string | null }; canRate: boolean; label: string; noun: string; onRate?: (polarity: string) => void;
}) {
  const [choosing, setChoosing] = useState(false);
  const [invite, setInvite] = useState(false);
  const mine = current?.mine as keyof typeof LABELS | null | undefined;
  return <div className="sc-pick__guide">
    <p className="sc-pick__lead">
      <span className="sc-pick__lead-long">Spinka to łańcuch boksów: każdy boks to dowód, każde połączenie to krok, którym wpis prowadzi czytelnika.</span>
      <span className="sc-pick__lead-short">Spinka: boksy to dowody, połączenia to kroki.</span>
    </p>
    <p className="sc-pick__why" title={why}>{why}</p>
    <div className="sc-pick__cta">
      {onRate && (choosing ? <StepRate step={current} canRate={canRate} label={label} withLabels onRate={polarity => { onRate(polarity); setChoosing(false); }} />
        : mine ? <p className="sc-pick__mine" data-rating={mine}>Twoja ocena: <b><SocialIcon kind={mine} />{LABELS[mine].toLowerCase()}</b>
            <span aria-hidden="true">·</span><button type="button" onClick={() => setChoosing(true)} aria-label={`Zmień ocenę: ${label}`}>zmień</button></p>
        : <button type="button" className="sc-pick__rate-btn" onClick={() => canRate ? setChoosing(true) : setInvite(true)}>Oceń {noun}</button>)}
      <AccountDialog open={invite} onClose={() => setInvite(false)} reason="rate" />
    </div>
  </div>;
}

export function FocusView({ threadId, items, start, steps, onClose, onStep, rateMode = false }: {
  threadId: number; items: ThreadElement[]; start: FocusStep; steps: ReturnType<typeof useThreadSteps>; onClose: () => void; onStep: (step: FocusStep) => void;
  /** Ocena krok po kroku (właściciel 6.10): po każdej reakcji karta sama przechodzi do następnego elementu, na końcu podziękowanie. */
  rateMode?: boolean;
}) {
  const sequence = useMemo(() => items.flatMap((_, i): FocusStep[] => i === 0 ? [{ kind: 'box', index: 0 }] : [{ kind: 'clip', index: i }, { kind: 'box', index: i }]), [items]);
  const [at, setAt] = useState(() => Math.max(0, sequence.findIndex(step => step.kind === start.kind && step.index === start.index)));
  const step = sequence[at];
  const item = items[step.index];
  const [finished, setFinished] = useState(false);
  const chain = useRef<HTMLElement>(null);
  // mini-pasek: bieżący element zawsze widoczny na środku (na telefonie pasek bywa szerszy niż ekran)
  useEffect(() => { const nav = chain.current, cur = nav?.querySelector<HTMLElement>('[aria-current]');
    if (nav && cur && nav.scrollWidth > nav.clientWidth) nav.scrollTo({ left: cur.offsetLeft - nav.clientWidth / 2 + cur.offsetWidth / 2, behavior: 'smooth' }); }, [at]);
  const box = useQuery({ queryKey: ['thread-box', threadId, item.item_id], queryFn: () => getThreadBox(threadId, item.item_id!), enabled: step.kind === 'box' && Boolean(item.item_id), retry: false });
  useEffect(() => { onStep(step); }, [at]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.target as HTMLElement | null)?.closest?.('input, textarea')) return;
      if (event.key === 'Escape') { event.stopImmediatePropagation(); onClose(); }
      if (event.key === 'ArrowRight') setAt(value => Math.min(sequence.length - 1, value + 1));
      if (event.key === 'ArrowLeft') setAt(value => Math.max(0, value - 1));
    };
    window.addEventListener('keydown', key, true);
    return () => window.removeEventListener('keydown', key, true);
  }, [onClose, sequence.length]);
  const card = useRef<HTMLElement>(null);
  const first = useRef(true);
  // fokus na karcie bez przewijania strony (nagłówek spinki zostaje na swoim miejscu)
  useEffect(() => { if (!first.current) card.current?.focus({ preventScroll: true }); first.current = false; }, [at]);
  const clipStep = step.kind === 'clip' ? steps.find(item.item_id, 'context') : undefined;
  const boxStep = step.kind === 'box' ? steps.find(item.item_id, 'box') : undefined;
  // tło w kolorach reakcji wybranego elementu; po wyjściu: całej spinki
  const whole = sumCounts(steps.data?.steps.map(row => row.counts));
  const current = clipStep ?? boxStep;
  useEffect(() => { setReactionMood(current ? sumCounts([current.counts]) ?? whole : whole); }, [current, whole]);
  useEffect(() => () => setReactionMood(sumCounts(steps.data?.steps.map(row => row.counts))), []); // eslint-disable-line react-hooks/exhaustive-deps
  const dominant = (counts?: { positive: number; doubt: number; negative: number }) => {
    const top = counts ? Math.max(counts.positive, counts.doubt, counts.negative) : 0;
    return !counts || !top ? undefined : counts.positive === top ? 'positive' : counts.doubt === top ? 'doubt' : 'negative';
  };
  const source = [item.source_name || (item.kind === 'link' ? item.domain : ''), item.published_date ? formatDatePl(item.published_date) : ''].filter(Boolean).join(' · ');
  const kind = item.box_type ?? item.kind;
  const image = boxImage(item);
  const typeWord = item.box_type ? BOX_TYPES[item.box_type as keyof typeof BOX_TYPES] : '';
  // bez obrazka rodzaj stoi w lewym polu, więc nad tytułem tylko źródło i data (bez powtórzeń)
  const kicker = (image ? [typeWord, source] : [source]).filter(Boolean).join(' · ');
  // wyjaśnienie autora tylko, gdy mówi coś innego niż opis i tytuł (panel designu 6.10)
  const note = item.note && item.note.trim() !== (item.body ?? '').trim() && item.note.trim() !== item.title.trim() ? item.note : '';
  const external = !item.url.startsWith('/');
  // jedna obsługa oceny dla stopki karty i strefy „Oceń” (stan wspólny w useThreadSteps)
  const rateCurrent = item.item_id ? (polarity: string) => { void steps.rate(item.item_id!, step.kind === 'box' ? 'box' : 'context', polarity);
    if (rateMode) window.setTimeout(() => { if (at < sequence.length - 1) setAt(at + 1); else setFinished(true); }, 450); } : undefined;
  const rateLabel = step.kind === 'box' ? `boks ${step.index + 1}` : `połączenie ${step.index}`;
  // druga linia wyjaśnienia: z czego wynika ten krok (dane, które API już zwraca: rodzaj i tytuł boksu docelowego)
  const why = step.kind === 'clip'
    ? `To połączenie (boks\u00a0${step.index} → boks\u00a0${step.index + 1}) wynika z:\u00a0${typeLower(item)} „${splitTitle(item).title}”`
    : `Ten boks (${step.index + 1}\u00a0z\u00a0${items.length}) ${step.index === 0 ? 'otwiera spinkę' : 'to dowód'}: ${typeLower(item)}${source ? `, ${source}` : ''}`;
  return <section className="sc-pick" aria-label={step.kind === 'box' ? `Boks ${step.index + 1}: ${item.title}` : `Połączenie ${step.index} → ${step.index + 1}`}>
    <header className="sc-pick__bar">
      <span />
      <span className="sc-pick__count" aria-live="polite">{step.kind === 'box' ? `Boks ${step.index + 1} z ${items.length}` : `Połączenie ${step.index} z ${items.length - 1}`}</span>
    </header>
    <div className="sc-pick__stage">
      {/* łatwy powrót po lewej, na wysokości karty; dalsza droga po prawej jaśniejsza (właściciel 4.10) */}
      <button type="button" className="sc-pick__home" onClick={onClose}>← Cała spinka</button>
      <button type="button" className="sc-pick__arrow" disabled={at === 0} onClick={() => setAt(at - 1)} aria-label="Poprzedni element">‹</button>
      <article className="sc-pick__card" key={at} data-kind={step.kind} ref={card} tabIndex={-1}>
        {/* lewe pole zawsze treść (zdjęcie, karta diagnozy, podgląd linku), prawe zawsze tytuł i opis (właściciel 5.10, 3 głosy na tak) */}
        <div className="sc-pick__media" data-type={kind} data-card={image.includes('/card.png') || undefined}>
          {step.kind === 'clip' ? <JointPreview from={items[step.index - 1]} to={item} index={step.index} counts={clipStep?.counts} />
            : image ? <img src={image} alt="" />
            : <span className="sc-pick__preview" aria-hidden="true"><Glyph name={TYPE_GLYPH[item.box_type ?? ''] ?? 'doc'} size={44} /><b>{(item.source_name || (item.kind === 'link' ? item.domain : '') || 'źródło').replace(/^www\./, '')}</b></span>}
          {step.kind === 'box' && <span className="sc-type-tag">{contentTag(item)}</span>}
        </div>
        <div className="sc-pick__text">
          {step.kind === 'box' ? <>
            <p className="sc-pick__type"><span><Glyph name={TYPE_GLYPH[item.box_type ?? ''] ?? 'doc'} />{typeWord || 'Materiał'}</span>{splitTitle(item).tag && <em>{splitTitle(item).tag}</em>}</p>
            {source && <p className="sc-pick__kicker">{source}</p>}
            <h2>{splitTitle(item).title}</h2>
            {item.body && <p className="sc-pick__body">{item.body}</p>}
            {note && <p className="sc-pick__note"><span>Wyjaśnienie autora</span>{note}</p>}
            {step.index > 0 && <p className="sc-pick__ctx"><span className="sc-rel"><Glyph name={LINK_GLYPH[item.link_kind ?? ''] ?? 'pin'} size={14} />{LINK_WORDS[item.link_kind ?? ''] ?? 'połączenie'}</span>
              <span>z boksem {step.index}: {item.link_note || 'autor nie opisał połączenia.'}</span></p>}
            {Boolean(box.data?.other_threads.length) && <p className="sc-pick__web"><span>W innych spinkach:</span> {box.data!.other_threads.map((row, i) => <Fragment key={row.id}>{i > 0 && ', '}<Link href={`/spinki/${row.id}`}>{row.title}</Link></Fragment>)}</p>}
          </> : <>
            <p className="sc-pick__kicker">Łączy boks {step.index} i {step.index + 1}</p>
            <p className="sc-pick__pair"><span>{items[step.index - 1].title}</span><b aria-hidden="true">→</b><span>{item.title}</span></p>
            <p className="sc-pick__body">{item.link_note || 'Autor nie opisał tego połączenia. Oceń, czy z pierwszego materiału wynika drugi.'}</p>
          </>}
          {/* stopka karty przy dolnej krawędzi (panel designu 6.10): z lewej odnośnik, z prawej ocena z pytaniem */}
          <footer className="sc-pick__foot">
            {step.kind === 'box' ? <a className="sc-pick__source" href={item.url} target={external ? '_blank' : undefined} rel="noopener noreferrer">{linkLabel(item)}</a> : <span />}
            {item.item_id && <span className="sc-pick__rate"><span className="sc-pick__ask">{step.kind === 'box' ? 'Trafny boks?' : 'Trafne połączenie?'}</span>
              <StepRate step={current} canRate={steps.canRate} label={rateLabel} onRate={rateCurrent!} /></span>}
          </footer>
        </div>
      </article>
      <button type="button" className="sc-pick__arrow" disabled={at === sequence.length - 1} onClick={() => setAt(at + 1)} aria-label="Następny element">›</button>
    </div>
    {rateMode && <p className="sc-pick__progress" aria-live="polite">{finished ? <>Dziękujemy, oceniłeś całą spinkę. <button type="button" onClick={onClose}>Wróć do spinki</button></>
      : <>Krok <b>{at + 1} z {sequence.length}</b> · {step.kind === 'box' ? 'boks' : 'połączenie'}</>}</p>}
    <nav className="sc-pick__chain" ref={chain} aria-label="Elementy spinki">
      {sequence.map((row, i) => <button key={i} type="button" className={row.kind === 'box' ? 'sc-trow__sq' : 'sc-trow__link'} aria-current={i === at || undefined}
        style={row.kind === 'clip' ? { background: clipColor(steps.find(items[row.index].item_id, 'context')?.counts) } : undefined}
        data-r={dominant(steps.find(items[row.index].item_id, row.kind === 'box' ? 'box' : 'context')?.counts)}
        aria-label={row.kind === 'box' ? `Boks ${row.index + 1}` : `Połączenie ${row.index} → ${row.index + 1}`} onClick={() => setAt(i)}>
        {row.kind === 'box' && <Glyph name={TYPE_GLYPH[items[row.index].box_type ?? ''] ?? 'doc'} size={14} />}</button>)}
    </nav>
    <StepGuide key={at} why={why} current={current} canRate={steps.canRate} label={rateLabel} noun={step.kind === 'box' ? 'boks' : 'połączenie'} onRate={rateCurrent} />
  </section>;
}
