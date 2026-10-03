"use client";

import { useQuery } from '@tanstack/react-query';
import { useFeature } from '../../lib/features';
import { getCommunityThreads } from '../../lib/community';
import { ThreadStrip } from '../../components/community/ThreadStrip';
import { Button } from '../Button';
import { useAccount } from '../../lib/account';

export function HomeThreads() {
  const enabled = useFeature('THREADS_ENABLED');
  const accounts = useFeature('ACCOUNTS_ENABLED');
  const account = useAccount();
  const query = useQuery({ queryKey: ['community-threads', 'hot'],
    queryFn: () => getCommunityThreads(1, '', '', { sort: 'hot' }), enabled, staleTime: 60_000, retry: false });
  const daily = useQuery({ queryKey: ['community-threads', 'ai-new'],
    queryFn: () => getCommunityThreads(1, '', '', { featured: '1' }), enabled, staleTime: 60_000, retry: false });
  const spin = daily.data?.results[0];
  if (!enabled) return null;
  return <section id="nitki" className="sc-home-section sc-home-thread-feed" aria-labelledby="home-threads-title">
    {spin && <section aria-label="Spin dnia"><h2 className="sc-t-title-s">Spin dnia</h2><ThreadStrip key={spin.id} thread={spin} initiallyExpanded /></section>}
    <header className="sc-home-thread-feed__head">
      <h2 id="home-threads-title" className="sc-t-title-l sc-home-section__title">Nitki</h2>
      <Button href={accounts ? '/konto/nitki/nowa' : '/nitki'} variant="secondary" size="sm">{accounts ? 'Ułóż swoją nitkę' : 'Wszystkie nitki'}</Button>
    </header>
    <p className="sc-t-body-s sc-text-2">Materiały ułożone w łańcuch: boks, powiązanie, boks. Dr. Spin rozkłada każdą diagnozę, a Ty możesz ułożyć własną nitkę.</p>
    <p className="sc-t-caption sc-text-3">Najgorętsze - reakcje z ostatnich 7 dni, przy remisie najnowsze nitki.</p>
    {query.isPending && <div className="sc-social-skeleton" aria-label="Ładowanie nitek" />}
    {query.isError && <p role="alert">Nie udało się pobrać nitek. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p>}
    {query.isSuccess && !query.data.results.length && <p>Pierwsze nitki pojawią się po publikacji diagnoz.</p>}
    <ul className="sc-community__list">{query.data?.results.filter(thread => thread.id !== spin?.id).slice(0, 6).map(thread => <li key={thread.id}><ThreadStrip thread={thread} /></li>)}</ul>
    {accounts && <Button href="/nitki" variant="quiet" size="sm">Wszystkie nitki</Button>}
    {accounts && account.data?.authenticated && <p><a href="/konto/nitki/nowa">Ułóż swoją nitkę: wybierz diagnozę i dodaj kontekst</a></p>}
  </section>;
}
