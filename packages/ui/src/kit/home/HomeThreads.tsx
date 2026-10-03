"use client";

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFeature } from '../../lib/features';
import { getCommunityThreads } from '../../lib/community';
import { ThreadStrip } from '../../components/community/ThreadStrip';
import { ThreadFeed } from '../../components/community/ThreadFeed';
import { ThreadOverlay } from '../../components/community/ThreadOverlay';
import { Button } from '../Button';

export function HomeThreads() {
  const enabled = useFeature('THREADS_ENABLED');
  const accounts = useFeature('ACCOUNTS_ENABLED');
  const daily = useQuery({ queryKey: ['community-threads', 'ai-new'],
    queryFn: () => getCommunityThreads(1, '', '', { featured: '1' }), enabled, staleTime: 60_000, retry: false });
  const spin = daily.data?.results[0];
  const [full, setFull] = useState(false);
  if (!enabled) return null;
  return <section id="tropy" className="sc-home-section sc-home-thread-feed" aria-labelledby="home-threads-title">
    {spin && <section aria-label="Spin dnia"><h2 className="sc-t-title-s">Spin dnia</h2><ThreadStrip key={spin.id} thread={spin} variant="row" initiallyExpanded onFullscreen={() => setFull(true)} />{full && <ThreadOverlay id={spin.id} onClose={() => setFull(false)} />}</section>}
    <header className="sc-home-thread-feed__head">
      <h2 id="home-threads-title" className="sc-t-title-l sc-home-section__title">Tropy</h2>
      {accounts && <Button href="/konto/tropy/nowa" variant="secondary" size="sm">Ułóż swój trop</Button>}
    </header>
    <p className="sc-t-body-s sc-text-2">Materiały ułożone w łańcuch: boks, powiązanie, boks. Dr. Spin rozkłada każdą diagnozę, a Ty możesz ułożyć własny trop.</p>
    {/* Główna to tropy (właściciel 3.10): cała lista z „Pokaż więcej”, bez osobnego przejścia do /tropy. */}
    <ThreadFeed initialSort="hot" exclude={spin?.id} />
  </section>;
}
