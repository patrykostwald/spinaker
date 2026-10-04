"use client";

import { Fragment, useEffect, useMemo, useState } from 'react';
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

export function StepRate({ step, onRate, canRate, label }: {
  step?: { counts: Record<string, number>; mine: string | null }; onRate: (polarity: string) => void; canRate: boolean; label: string;
}) {
  // zawsze klikalne (właściciel 5.10): bez konta kliknięcie zaprasza do logowania lub założenia konta
  const [invite, setInvite] = useState(false);
  return <span className="sc-step-rate" role="group" aria-label={`Oceń: ${label}`}>
    {RATINGS.map(key => <button key={key} type="button" data-rating={key} aria-pressed={step?.mine === key}
      title={canRate ? `${LABELS[key]}: ${step?.counts[key] ?? 0}` : `${LABELS[key]}: załóż konto, aby oceniać`}
      onClick={event => { event.stopPropagation(); if (canRate) onRate(key); else setInvite(true); }}>
      <SocialIcon kind={key} /></button>)}
    <AccountDialog open={invite} onClose={() => setInvite(false)} />
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

export function FocusView({ threadId, items, start, steps, onClose, onStep }: {
  threadId: number; items: ThreadElement[]; start: FocusStep; steps: ReturnType<typeof useThreadSteps>; onClose: () => void; onStep: (step: FocusStep) => void;
}) {
  const sequence = useMemo(() => items.flatMap((_, i): FocusStep[] => i === 0 ? [{ kind: 'box', index: 0 }] : [{ kind: 'clip', index: i }, { kind: 'box', index: i }]), [items]);
  const [at, setAt] = useState(() => Math.max(0, sequence.findIndex(step => step.kind === start.kind && step.index === start.index)));
  const step = sequence[at];
  const item = items[step.index];
  const box = useQuery({ queryKey: ['thread-box', threadId, item.item_id], queryFn: () => getThreadBox(threadId, item.item_id!), enabled: step.kind === 'box' && Boolean(item.item_id), retry: false });
  useEffect(() => { onStep(step); }, [at]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.target as HTMLElement | null)?.closest?.('input, textarea')) return;
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowRight') setAt(value => Math.min(sequence.length - 1, value + 1));
      if (event.key === 'ArrowLeft') setAt(value => Math.max(0, value - 1));
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [onClose, sequence.length]);
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
  return <section className="sc-pick" aria-label={step.kind === 'box' ? `Boks ${step.index + 1}: ${item.title}` : `Połączenie ${step.index} → ${step.index + 1}`}>
    <header className="sc-pick__bar">
      <span />
      <span className="sc-pick__count">{step.kind === 'box' ? `Boks ${step.index + 1} z ${items.length}` : `Połączenie ${step.index} z ${items.length - 1}`}</span>
    </header>
    <div className="sc-pick__stage">
      {/* łatwy powrót po lewej, na wysokości karty; dalsza droga po prawej jaśniejsza (właściciel 4.10) */}
      <button type="button" className="sc-pick__home" onClick={onClose}>← Cała spinka</button>
      <button type="button" className="sc-pick__arrow" disabled={at === 0} onClick={() => setAt(at - 1)} aria-label="Poprzedni element">‹</button>
      <article className="sc-pick__card" key={at} data-kind={step.kind}>
        {/* lewe pole zawsze treść (zdjęcie, karta diagnozy, podgląd linku), prawe zawsze tytuł i opis (właściciel 5.10, 3 głosy na tak) */}
        <div className="sc-pick__media" data-type={kind} data-card={image.includes('/card.png') || undefined}>
          {step.kind === 'clip' ? <SpinkaClip counts={clipStep?.counts} />
            : image ? <img src={image} alt="" />
            : <a className="sc-pick__preview" href={item.url} target={item.url.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">
                <b>{(item.source_name || (item.kind === 'link' ? item.domain : '') || 'źródło').replace(/^www\./, '')}</b><span>Otwórz źródło ↗</span></a>}
          {step.kind === 'box' && <span className="sc-type-tag">{contentTag(item)}</span>}
        </div>
        <div className="sc-pick__text">
          {step.kind === 'box' ? <>
            {source && <p className="sc-pick__kicker">{source}</p>}
            <h2>{item.title}</h2>
            {item.body && <p className="sc-pick__body">{item.body}</p>}
            {item.note && <p className="sc-pick__note"><span>Wyjaśnienie autora</span>{item.note}</p>}
            <a className="sc-pick__source" href={item.url} target={item.url.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">Otwórz źródło ↗</a>
            {Boolean(box.data?.other_threads.length) && <p className="sc-pick__web"><span>W innych spinkach:</span> {box.data!.other_threads.map((row, i) => <Fragment key={row.id}>{i > 0 && ', '}<Link href={`/spinki/${row.id}`}>{row.title}</Link></Fragment>)}</p>}
          </> : <>
            <p className="sc-pick__kicker">Łączy boks {step.index} i {step.index + 1}</p>
            <p className="sc-pick__pair"><span>{items[step.index - 1].title}</span><b aria-hidden="true">→</b><span>{item.title}</span></p>
            <p className="sc-pick__body">{item.link_note || 'Autor nie opisał tego połączenia. Oceń, czy z pierwszego materiału wynika drugi.'}</p>
          </>}
        </div>
        {item.item_id && <StepRate step={current} canRate={steps.canRate} label={step.kind === 'box' ? `boks ${step.index + 1}` : `połączenie ${step.index}`}
          onRate={polarity => void steps.rate(item.item_id!, step.kind === 'box' ? 'box' : 'context', polarity)} />}
      </article>
      <button type="button" className="sc-pick__arrow" disabled={at === sequence.length - 1} onClick={() => setAt(at + 1)} aria-label="Następny element">›</button>
    </div>
    <nav className="sc-pick__chain" aria-label="Elementy spinki">
      {sequence.map((row, i) => <button key={i} type="button" className={row.kind === 'box' ? 'sc-trow__sq' : 'sc-trow__link'} aria-current={i === at || undefined}
        style={row.kind === 'clip' ? { background: clipColor(steps.find(items[row.index].item_id, 'context')?.counts) } : undefined}
        data-r={dominant(steps.find(items[row.index].item_id, row.kind === 'box' ? 'box' : 'context')?.counts)}
        aria-label={row.kind === 'box' ? `Boks ${row.index + 1}` : `Połączenie ${row.index} → ${row.index + 1}`} onClick={() => setAt(i)} />)}
    </nav>
  </section>;
}
