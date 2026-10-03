"use client";

import { useQuery } from '@tanstack/react-query';
import { useFeature } from '../../lib/features';
import { getCommunityThreads } from '../../lib/community';
import { ThreadStrip } from '../../components/community/ThreadStrip';
import { ThreadFeed } from '../../components/community/ThreadFeed';
import { Button } from '../Button';
import { useAccount } from '../../lib/account';

export function HomeThreads() {
  const enabled = useFeature('THREADS_ENABLED');
  const accounts = useFeature('ACCOUNTS_ENABLED');
  const account = useAccount();
  const daily = useQuery({ queryKey: ['community-threads', 'ai-new'],
    queryFn: () => getCommunityThreads(1, '', '', { featured: '1' }), enabled, staleTime: 60_000, retry: false });
  const spin = daily.data?.results[0];
  if (!enabled) return null;
  return <section id="tropy" className="sc-home-section sc-home-thread-feed" aria-labelledby="home-threads-title">
    {spin && <section aria-label="Spin dnia"><h2 className="sc-t-title-s">Spin dnia</h2><ThreadStrip key={spin.id} thread={spin} initiallyExpanded /></section>}
    <header className="sc-home-thread-feed__head">
      <h2 id="home-threads-title" className="sc-t-title-l sc-home-section__title">Tropy</h2>
      <Button href={accounts ? '/konto/tropy/nowa' : '/tropy'} variant="secondary" size="sm">{accounts ? 'Ułóż swój trop' : 'Wszystkie tropy'}</Button>
    </header>
    <p className="sc-t-body-s sc-text-2">Materiały ułożone w łańcuch: boks, powiązanie, boks. Dr. Spin rozkłada każdą diagnozę, a Ty możesz ułożyć własny trop.</p>
    <ThreadFeed initialSort="hot" limit={8} exclude={spin?.id} />
    {accounts && <Button href="/tropy" variant="quiet" size="sm">Wszystkie tropy</Button>}
    {accounts && account.data?.authenticated && <p><a href="/konto/tropy/nowa">Ułóż swój trop: wybierz diagnozę i dodaj kontekst</a></p>}
  </section>;
}
