"use client";
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { useAccount } from '../lib/account';
import { apiFetch, apiWrite } from '../lib/api';
import { useFeature } from '../lib/features';
import type { ArticleFavoriteRow, ThreadFavoriteRow } from '../lib/personal';
import { useFollows } from '../lib/accountPhase2';
import { Button } from '../kit';
import { AccountDialog } from './AccountDialog';
import { AccountDataState, AccountOnboarding, AccountSettings, FollowedSection, NotificationsSection } from './AccountPhase2';
import { AccountActivity, AccountReports, AccountThreads, EmptyState, ProfileHeading, useAccountProfile, type Page } from './AccountDashboardParts';
import { FollowButton } from './FollowButton';

export function SignedOutPanel({ title = 'Mój spin.clinic' }: { title?: string }) {
  const [open, setOpen] = useState(false), threadsEnabled = useFeature('THREADS_ENABLED');
  return <section className="sc-account sc-account-signed-out"><h1>{title}</h1><p>{threadsEnabled ? 'Zaloguj się, aby układać spinki, oceniać i komentować.' : 'Zaloguj się, aby oceniać i komentować.'}</p>
    <Button onClick={() => setOpen(true)} variant="primary">Zaloguj się lub załóż konto</Button><AccountDialog open={open} onClose={() => setOpen(false)} />
  </section>;
}
function SavedSection() {
  const threadsEnabled = useFeature('THREADS_ENABLED'), account = useAccount(), follows = useFollows(), cache = useQueryClient();
  const articles = useInfiniteQuery({ queryKey: ['article-favorites', account.data?.user?.id, 'pages'], initialPageParam: 1,
    queryFn: ({ pageParam }) => apiFetch<Page<ArticleFavoriteRow>>(`/api/account/article-favorites/?page=${pageParam}`), getNextPageParam: last => last.next_page ?? undefined });
  const threads = useInfiniteQuery({ queryKey: ['account-favorites', account.data?.user?.id, 'pages'], initialPageParam: 1,
    queryFn: ({ pageParam }) => apiFetch<Page<ThreadFavoriteRow>>(`/api/account/favorites/?page=${pageParam}`), getNextPageParam: last => last.next_page ?? undefined, enabled: threadsEnabled });
  const articleRows = articles.data?.pages.flatMap(p => p.results) ?? [], threadRows = threadsEnabled ? threads.data?.pages.flatMap(p => p.results) ?? [] : [];
  const [pending, setPending] = useState(false), [message, setMessage] = useState('');
  const saved = threadsEnabled ? follows.data?.filter(row => row.kind === 'thread') ?? [] : [];
  async function remove(path: string) { setPending(true); try { await apiWrite(path, {}, 'DELETE'); await cache.invalidateQueries(); } catch (e) { setMessage(e instanceof Error ? e.message : 'Nie udało się usunąć.'); } finally { setPending(false); } }
  return <section className="sc-account-section"><header><h2>Zapisane</h2></header>
    <AccountDataState query={articles} />{threadsEnabled && <AccountDataState query={threads} />}
    {articles.isSuccess && (threads.isSuccess || !threadsEnabled) && follows.isSuccess && !articleRows.length && !threadRows.length && !saved.length && <EmptyState href={threadsEnabled ? "/spinki" : "/klinika"} label={threadsEnabled ? "Przeglądaj spinki" : "Przejdź do Kliniki"}>Nie masz jeszcze zapisanych treści.</EmptyState>}
    <ul className="sc-account-rows">
      {saved.map(row => <li key={`saved-${row.id}`}><Link href={row.url}>{row.label}</Link><FollowButton kind="thread" targetId={row.target_id} label={row.label} compactLabel /></li>)}
      {articleRows.map(row => <li key={`article-${row.id}`}><Link href={`/material/${row.article.id}`}>{row.article.title}</Link><Button disabled={pending} onClick={() => remove(`/api/account/article-favorites/${row.article.id}/`)}>Usuń z zapisanych</Button></li>)}
      {threadRows.map(row => <li key={`thread-${row.id}`}><Link href={`/thread/${row.thread.slug}`}>{row.thread.title}</Link><Button disabled={pending} onClick={() => remove(`/api/account/favorites/${row.thread.id}/`)}>Usuń z zapisanych</Button></li>)}
    </ul>{(articles.hasNextPage || threads.hasNextPage) && <Button disabled={articles.isFetchingNextPage || threads.isFetchingNextPage} onClick={() => { if (articles.hasNextPage) void articles.fetchNextPage(); if (threads.hasNextPage) void threads.fetchNextPage(); }}>Pokaż więcej zapisanych</Button>}{message && <p role="status">{message}</p>}
  </section>;
}
/* Sześć sekcji (Konsylium 4.10, ścieżki użytkowników): to, co robię, co obserwuję, co do mnie przychodzi, konto, dane. */
const NAV = [['moje-tropy', 'Moje spinki'], ['aktywnosc', 'Aktywność'], ['obserwowani', 'Obserwuję'], ['powiadomienia', 'Powiadomienia'], ['konto', 'Konto'], ['prywatnosc', 'Prywatność i dane']] as const;
const OLD: Record<string, string> = { ustawienia: 'konto', zgloszenia: 'aktywnosc' };
export function MojeKonto() {
  const account = useAccount(), profile = useAccountProfile(), threadsEnabled = useFeature('THREADS_ENABLED');
  const [section, setSection] = useState<string>('moje-tropy');
  useEffect(() => { const read = () => { const raw = window.location.hash.slice(1), key = OLD[raw] ?? raw; if (NAV.some(([id]) => id === key)) setSection(key); }; read(); window.addEventListener('hashchange', read); return () => window.removeEventListener('hashchange', read); }, []);
  const nav = NAV.filter(([id]) => threadsEnabled || id !== 'moje-tropy');
  const active = !threadsEnabled && section === 'moje-tropy' ? 'aktywnosc' : section;
  if (account.isPending || account.isError) return <div className="sc-account"><AccountDataState query={account} /></div>;
  if (!account.data?.user) return <SignedOutPanel />;
  function navigate(id: string) { setSection(id); window.history.replaceState(null, '', `#${id}`); }
  return <div className="sc-account sc-f2 sc-account-dashboard sc-account-086">
    <h1>Mój spin.clinic</h1><AccountDataState query={profile} />
    {profile.data && <ProfileHeading profile={profile.data}><Button variant="secondary" onClick={() => navigate('konto')}>Edytuj profil</Button><Button href={`/profile/${encodeURIComponent(profile.data.username)}`} variant="quiet">Zobacz profil publiczny</Button></ProfileHeading>}
    <AccountOnboarding key={account.data.user.id} ownerId={account.data.user.id} />
    <div className="sc-account-layout"><nav className="sc-account-sidenav" aria-label="Sekcje konta">{nav.map(([id, label]) => <a key={id} href={`#${id}`} aria-current={active === id ? 'page' : undefined} onClick={event => { event.preventDefault(); navigate(id); }}>{label}</a>)}</nav>
      <div className="sc-account-content" key={active}>
        {active === 'moje-tropy' && <AccountThreads />}{active === 'aktywnosc' && <><AccountActivity /><AccountReports /></>}
        {active === 'obserwowani' && <><FollowedSection /><SavedSection /></>}{active === 'powiadomienia' && <><NotificationsSection /><AccountSettings part="powiadomienia" /></>}
        {active === 'konto' && <AccountSettings part="konto" />}{active === 'prywatnosc' && <AccountSettings part="prywatnosc" />}
      </div>
    </div>
  </div>;
}
