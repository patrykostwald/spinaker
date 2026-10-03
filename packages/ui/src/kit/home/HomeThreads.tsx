"use client";

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFeature } from '../../lib/features';
import { getCommunityThreads } from '../../lib/community';
import { ThreadStrip } from '../../components/community/ThreadStrip';
import { ThreadFeed } from '../../components/community/ThreadFeed';
import { ThreadOverlay, viewTransition } from '../../components/community/ThreadOverlay';

export function HomeThreads() {
  const enabled = useFeature('THREADS_ENABLED');
  const daily = useQuery({ queryKey: ['community-threads', 'ai-new'],
    queryFn: () => getCommunityThreads(1, '', '', { featured: '1' }), enabled, staleTime: 60_000, retry: false });
  const spin = daily.data?.results[0];
  const [full, setFull] = useState(false);
  if (!enabled) return null;
  // Główna to same tropy (właściciel 3.10): spin dnia jako pierwszy, wyróżniony wiersz, pod nim lista;
  // kategorie, kolejność i „Ułóż swój trop” są w pasku nad treścią (SectionBar).
  return <section id="tropy" className="sc-home-thread-feed" aria-label="Tropy">
    {spin && <div className="sc-spin-of-day"><ThreadStrip key={spin.id} thread={spin} variant="row" badge="Spin dnia" onFullscreen={() => viewTransition(() => setFull(true))} />{full && <ThreadOverlay id={spin.id} onClose={() => viewTransition(() => setFull(false))} />}</div>}
    <ThreadFeed initialSort="hot" exclude={spin?.id} />
  </section>;
}
