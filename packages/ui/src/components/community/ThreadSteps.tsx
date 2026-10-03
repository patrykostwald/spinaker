"use client";

import { useEffect } from 'react';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getThreadBox, getThreadSteps, rateThreadStep, type StepPart, type StepsData } from '../../lib/community';
import { useAccount, emailVerified } from '../../lib/account';
import { useFeature } from '../../lib/features';
import { SocialIcon, RATINGS } from './SocialPrimitives';
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
  return <p className="sc-step-progress" aria-label={canRate ? `Przejście tropu: ${done} z ${total} kroków` : 'Zaloguj się, aby przejść trop'}>
    <span className="sc-step-progress__bar" aria-hidden="true"><span style={{ width: `${100 * share}%` }} /></span>
  </p>;
}

/** Okno boksu z Bazy: źródło, reakcje, powiązania obok i ten sam materiał w innych tropach (sieć kontekstów). */
export function BoxPanel({ threadId, itemId, steps, onClose }: { threadId: number; itemId: number; steps: ReturnType<typeof useThreadSteps>; onClose: () => void }) {
  const query = useQuery({ queryKey: ['thread-box', threadId, itemId], queryFn: () => getThreadBox(threadId, itemId), retry: false });
  useEffect(() => {
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [onClose]);
  const box = query.data;
  const item = box?.item;
  return <div className="sc-box-panel" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="sc-box-panel__sheet" role="dialog" aria-modal="true" aria-label={item ? `Boks ${box.position}: ${item.title}` : 'Boks'}>
      <button type="button" className="sc-box-panel__close" aria-label="Zamknij" onClick={onClose}>✕</button>
      {query.isPending && <div className="sc-social-skeleton" aria-label="Ładowanie boksu" />}
      {query.isError && <p role="alert">Nie udało się pobrać boksu.</p>}
      {item && box && <>
        <p className="sc-box-panel__kicker">Boks {box.position} · {item.source_name || (item.kind === 'link' ? item.domain : '')}{item.published_date ? ` · ${formatDatePl(item.published_date)}` : ''}</p>
        {item.image_url && <img className="sc-box-panel__img" src={item.image_url} alt="" />}
        <h3>{item.title}</h3>
        {item.body && <p className="sc-box-panel__body">{item.body}</p>}
        {item.note && <p className="sc-box-panel__note"><span>Komentarz autora tropu</span>{item.note}</p>}
        <a className="sc-box-panel__source" href={item.url} target={item.url.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">Otwórz źródło ↗</a>
        <div className="sc-box-panel__rate"><span>Twoja reakcja na ten boks</span>
          <StepRate step={steps.find(itemId, 'box')} canRate={steps.canRate} label={`boks ${box.position}`} onRate={polarity => void steps.rate(itemId, 'box', polarity)} /></div>
        {(box.context_before || box.context_after) && <div className="sc-box-panel__context">
          {box.context_before && <p><span>Powiązanie przed</span>{box.context_before}</p>}
          {box.context_after && <p><span>Powiązanie dalej</span>{box.context_after}</p>}
        </div>}
        {box.other_threads.length > 0 && <div className="sc-box-panel__web"><span>Ten materiał w innych tropach</span>
          <ul>{box.other_threads.map(row => <li key={row.id}><Link href={`/tropy/${row.id}`}>{row.title}</Link></li>)}</ul></div>}
      </>}
    </aside>
  </div>;
}
