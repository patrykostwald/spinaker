"use client";
import { useState, type FormEvent } from 'react';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiWrite } from '../lib/api';
import { useAccount } from '../lib/account';
import { useFeature } from '../lib/features';
import { REPORT_REASONS, type CommunityThreadSummary } from '../lib/community';
import { Button } from '../kit';
import { AccountDataState } from './AccountPhase2';
import { ActivityRows, EmptyState, ProfileHeading, type ActivityRow, type ProfileData, type Page } from './AccountDashboardParts';
import { ThreadStrip } from './community/ThreadStrip';
import { FollowButton } from './FollowButton';
import { Dialog } from './Dialog';
import { AccountDialog } from './AccountDialog';

type PublicProfile = ProfileData & { muted: boolean; threads: Page<CommunityThreadSummary>; comments: Page<ActivityRow> };
export function PublicSocialProfile({ username }: { username: string }) {
  const account = useAccount(), cache = useQueryClient(), threadsEnabled = useFeature('THREADS_ENABLED');
  const [chosen, setSection] = useState<'threads' | 'comments'>('threads');
  const section = threadsEnabled ? chosen : 'comments';
  const query = useInfiniteQuery({ queryKey: ['public-profile', username, account.data?.user?.id, section], initialPageParam: 1,
    queryFn: ({ pageParam }) => apiFetch<PublicProfile>(`/api/profiles/${encodeURIComponent(username)}/?page=${pageParam}`),
    getNextPageParam: last => last[section].next_page ?? undefined, retry: false });
  const [report, setReport] = useState(false), [login, setLogin] = useState(false), [pending, setPending] = useState(false), [message, setMessage] = useState('');
  const profile = query.data?.pages[0];
  async function mute() {
    if (!account.data?.user) { setLogin(true); return; } if (!profile || pending) return; setPending(true);
    try { await apiWrite(`/api/account/mutes/${profile.muted ? `${profile.id}/` : ''}`, { user_id: profile.id }, profile.muted ? 'DELETE' : 'POST'); await cache.invalidateQueries(); setMessage(profile.muted ? 'Odciszono użytkownika.' : 'Wyciszono użytkownika.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Nie udało się zapisać.'); } finally { setPending(false); }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (pending) return; const data = new FormData(event.currentTarget); setPending(true);
    try { await apiWrite(`/api/profiles/${encodeURIComponent(username)}/report/`, { reason: data.get('reason'), details: data.get('details') }); setReport(false); setMessage('Zgłoszenie przyjęte. Status znajdziesz w swoim panelu.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Nie udało się wysłać.'); } finally { setPending(false); }
  }
  return <main className="sc-account sc-f2 sc-account-086"><h1>Profil publiczny</h1><AccountDataState query={query} empty="Profil jest niedostępny." />
    {profile && <><ProfileHeading profile={profile}>{account.data?.user?.id !== profile.id && <>{threadsEnabled && <FollowButton kind="user" targetId={profile.id} label={profile.username} />}<Button disabled={pending} onClick={mute}>{profile.muted ? 'Odcisz' : 'Wycisz'}</Button><Button onClick={() => account.data?.user ? setReport(true) : setLogin(true)}>Zgłoś</Button></>}</ProfileHeading>
      {profile.muted ? <EmptyState>{threadsEnabled ? 'Wyciszono spinki i komentarze tej osoby.' : 'Wyciszono komentarze tej osoby.'}</EmptyState> : <><nav className="sc-account-filter" aria-label="Treści profilu">{threadsEnabled && <button aria-pressed={section === 'threads'} onClick={() => setSection('threads')}>Spinki</button>}{profile.public_activity && <button aria-pressed={section === 'comments'} onClick={() => setSection('comments')}>Komentarze</button>}</nav>
        {section === 'threads' ? <>{query.data?.pages.flatMap(p => p.threads.results).map(thread => <ThreadStrip key={thread.id} thread={thread} />)}{!profile.threads.results.length && <EmptyState>Nie ma jeszcze opublikowanych spinek.</EmptyState>}</> : profile.public_activity && <><ActivityRows rows={query.data?.pages.flatMap(p => p.comments.results) ?? []} />{!profile.comments.results.length && <EmptyState>Nie ma jeszcze publicznych komentarzy.</EmptyState>}</>}
        {query.hasNextPage && <Button onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>Pokaż więcej</Button>}</>}
    </>}
    {message && <p role="status">{message}</p>}<AccountDialog open={login} onClose={() => setLogin(false)} />
    <Dialog open={report} onClose={() => setReport(false)} title="Zgłoś profil"><form className="sc-account-form" onSubmit={submit}><label>Powód<select name="reason">{REPORT_REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}</select></label><label>Opis<textarea name="details" maxLength={1000} /></label><Button type="submit" disabled={pending}>Wyślij zgłoszenie</Button>{message && <p role="status">{message}</p>}</form></Dialog>
  </main>;
}
