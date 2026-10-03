"use client";

import { useEffect, useMemo, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getThreadBox, getThreadSteps, rateThreadStep, type StepPart, type StepsData, type ThreadElement } from '../../lib/community';
import { apiFetch, apiWrite } from '../../lib/api';
import { useAccount, emailVerified } from '../../lib/account';
import { useFeature } from '../../lib/features';
import { Avatar, ago, SocialIcon, RATINGS } from './SocialPrimitives';
import { setReactionMood, sumCounts } from '../../lib/mood';
import { formatDatePl } from '../../lib/utils';

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
  return <span className="sc-step-rate" role="group" aria-label={`Oceń: ${label}`}>
    {RATINGS.map(key => <button key={key} type="button" data-rating={key} aria-pressed={step?.mine === key} disabled={!canRate}
      title={canRate ? `${LABELS[key]}: ${step?.counts[key] ?? 0}` : 'Zaloguj się, aby oceniać'}
      onClick={event => { event.stopPropagation(); onRate(key); }}>
      <SocialIcon kind={key} /></button>)}
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
export function SpinkaClip({ counts, open = false }: { counts?: Counts3; id?: string; open?: boolean }) {
  const c = counts ?? { positive: 0, doubt: 0, negative: 0 };
  const top = Math.max(c.positive, c.doubt, c.negative);
  const color = !top ? 'var(--sc-text-3)' : c.positive === top ? 'var(--sc-positive)' : c.doubt === top ? 'var(--sc-warning)' : 'var(--sc-negative)';
  // rozsunięta: lekki zygzak w górę (wskazuje boks z wyjaśnieniem nad nią); zawsze tylko delikatny zawijas na końcu
  const d = open ? 'M2 26 H88 L100 16 L112 26 H186 C191 26 193 23 192 21 C191 19 188.5 19 188 21'
    : 'M1 22 H32 C37 22 39 19.5 38 17.5 C37 15.5 34.5 15.5 34 17.5';
  return <svg className="sc-clip" viewBox={open ? '0 0 200 40' : '0 0 44 40'} preserveAspectRatio="none" aria-hidden="true">
    <path d={d} fill="none" vectorEffect="non-scaling-stroke" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>;
}

type FocusComment = { id: number; author: string; body: string; created_at: string; author_color?: string };
export type FocusStep = { kind: 'box' | 'clip'; index: number };

/**
 * Pełny widok boksu albo spinki (właściciel 3.10): drugie kliknięcie otwiera wybrany element na całym obszarze treści.
 * Na środku boks (materiał ze źródła) albo spinka (kontekst autora + ocena), pod spodem komentarze przypisane
 * do tego miejsca (@boks N / @spinka N) i pole „Skomentuj”, które samo dodaje odniesienie.
 */
export function FocusView({ threadId, title, items, start, steps, onClose }: {
  threadId: number; title: string; items: ThreadElement[]; start: FocusStep; steps: ReturnType<typeof useThreadSteps>; onClose: () => void;
}) {
  const sequence = useMemo(() => items.flatMap((_, i): FocusStep[] => i === 0 ? [{ kind: 'box', index: 0 }] : [{ kind: 'clip', index: i }, { kind: 'box', index: i }]), [items]);
  const [at, setAt] = useState(() => Math.max(0, sequence.findIndex(step => step.kind === start.kind && step.index === start.index)));
  const step = sequence[at];
  const item = items[step.index];
  const ref = step.kind === 'box' ? `@b${step.index + 1}` : `@s${step.index}`;
  const pattern = new RegExp((step.kind === 'box' ? String.raw`@(?:boks\s*|b)` + (step.index + 1) : String.raw`@(?:spinka\s*|s)` + step.index) + String.raw`(?!\d)`, 'i');
  const cache = useQueryClient();
  const comments = useQuery({ queryKey: ['thread-comments-all', threadId], queryFn: () => apiFetch<{ results: FocusComment[] }>(`/api/community/threads/${threadId}/comments/?sort=best`), retry: false });
  const box = useQuery({ queryKey: ['thread-box', threadId, item.item_id], queryFn: () => getThreadBox(threadId, item.item_id!), enabled: step.kind === 'box' && Boolean(item.item_id), retry: false });
  const mine = (comments.data?.results ?? []).filter(row => pattern.test(row.body));
  const [draft, setDraft] = useState('');
  const [status, setStatus] = useState('');
  useEffect(() => { setDraft(''); setStatus(''); }, [at]);
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
  async function send(event: FormEvent) {
    event.preventDefault();
    try {
      await apiWrite(`/api/community/threads/${threadId}/comments/`, { body: `${ref} ${draft.trim()}` });
      setDraft(''); setStatus('Komentarz dodany.');
      void cache.invalidateQueries({ queryKey: ['thread-comments-all', threadId] });
      void cache.invalidateQueries({ queryKey: ['thread-comments', threadId] });
    } catch (error) { setStatus(error instanceof Error ? error.message : 'Nie udało się dodać komentarza.'); }
  }
  const clipStep = step.kind === 'clip' ? steps.find(item.item_id, 'context') : undefined;
  // pełny widok spinki: tło w kolorach reakcji tego połączenia; boks i wyjście: całej spinki
  const whole = sumCounts(steps.data?.steps.map(row => row.counts));
  useEffect(() => { setReactionMood(clipStep ? sumCounts([clipStep.counts]) ?? whole : whole); }, [clipStep, whole]);
  useEffect(() => () => setReactionMood(sumCounts(steps.data?.steps.map(row => row.counts))), []); // eslint-disable-line react-hooks/exhaustive-deps
  return <section className="sc-focus" role="dialog" aria-modal="true" aria-label={step.kind === 'box' ? `Boks ${step.index + 1}: ${item.title}` : `Spinka ${step.index}`}>
    <header className="sc-focus__bar">
      <button type="button" className="sc-focus__back" onClick={onClose}>← Wróć</button>
      <span className="sc-focus__title" title={title}>{title}</span>
      <nav className="sc-focus__nav" aria-label="Kolejne boksy i spinki">
        <button type="button" disabled={at === 0} onClick={() => setAt(at - 1)} aria-label="Poprzedni">‹</button>
        <span>{step.kind === 'box' ? `Boks ${step.index + 1} z ${items.length}` : `Spinka ${step.index} z ${items.length - 1}`}</span>
        <button type="button" disabled={at === sequence.length - 1} onClick={() => setAt(at + 1)} aria-label="Następny">›</button>
      </nav>
    </header>
    <div className="sc-focus__stage" key={at}>
      {step.kind === 'box' ? <article className="sc-focus__card">
        <p className="sc-focus__kicker">{[item.source_name || (item.kind === 'link' ? item.domain : ''), item.published_date ? formatDatePl(item.published_date) : ''].filter(Boolean).join(' · ')}</p>
        {item.image_url && <img className="sc-focus__img" src={item.image_url} alt="" />}
        <h2>{item.title}</h2>
        {item.body && <p className="sc-focus__body">{item.body}</p>}
        {item.note && <p className="sc-focus__note"><span>Komentarz autora spinki</span>{item.note}</p>}
        <a className="sc-focus__source" href={item.url} target={item.url.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">Otwórz źródło ↗</a>
        {Boolean(box.data?.other_threads.length) && <div className="sc-focus__web"><span>Ten materiał w innych spinkach</span>
          <ul>{box.data!.other_threads.map(row => <li key={row.id}><Link href={`/spinki/${row.id}`}>{row.title}</Link></li>)}</ul></div>}
      </article> : <article className="sc-focus__card sc-focus__card--clip">
        <SpinkaClip counts={clipStep?.counts} id={`focus-clip-${threadId}-${step.index}`} />
        <p className="sc-focus__kicker">Spinka {step.index}: łączy boks {step.index} i {step.index + 1}</p>
        <p className="sc-focus__pair"><span>{items[step.index - 1].title}</span><b aria-hidden="true">→</b><span>{item.title}</span></p>
        <p className="sc-focus__context">{item.link_note || 'Autor nie opisał tej spinki. Oceń, czy te dwa materiały naprawdę się łączą.'}</p>
        {item.item_id && <div className="sc-focus__rate"><span>Twoja ocena tej spinki</span>
          <StepRate step={clipStep} canRate={steps.canRate} label={`spinka ${step.index}`} onRate={polarity => void steps.rate(item.item_id!, 'context', polarity)} /></div>}
      </article>}
      <div className="sc-focus__comments sc-social-comments">
        <form className="sc-focus__compose" onSubmit={send}>
          <span className="sc-focus__ref">{ref}</span>
          <input value={draft} maxLength={1990} onChange={event => setDraft(event.target.value)} placeholder="Skomentuj" aria-label={`Skomentuj: ${ref}`} />
          <button disabled={!draft.trim() || !steps.canRate}>Skomentuj</button>
        </form>
        {status && <p role="status" className="sc-focus__status">{status}</p>}
        {comments.isSuccess && !mine.length && <p className="sc-focus__empty">Nikt jeszcze nie skomentował {step.kind === 'box' ? 'tego boksu' : 'tej spinki'}.</p>}
        <ol>{mine.map(row => <li key={row.id} className="sc-cmt">
          <Avatar name={row.author} />
          <div className="sc-cmt__body"><header><strong style={row.author_color ? { color: row.author_color } : undefined}>{row.author}</strong><span aria-hidden="true">·</span><time dateTime={row.created_at}>{ago(row.created_at)}</time></header>
            <div className="sc-social-text">{row.body.replace(new RegExp('^\\s*' + pattern.source, 'i'), '').trim()}</div></div>
        </li>)}</ol>
      </div>
    </div>
  </section>;
}
