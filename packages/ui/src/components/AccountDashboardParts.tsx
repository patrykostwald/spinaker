"use client";
import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiWrite } from '../lib/api';
import { useAccount } from '../lib/account';
import { Button } from '../kit';
import { formatDateTimePl, formatDatePl } from '../lib/utils';
import { AccountDataState } from './AccountPhase2';
import { ClampedText, RatingFrame, SocialIcon, type Counts } from './community/SocialPrimitives';
import type { PersonalContextThread } from '../lib/personal';

export type ProfileData = { id: number; username: string; bio: string; date_joined: string; public_activity: boolean;
  nick_change_available_at?: string | null; counts: { threads: number; ratings: number; comments: number } };
export type ActivityRow = { id: string; kind: 'ratings' | 'comments' | 'votes'; created_at: string; title: string;
  url: string; body?: string; polarity?: keyof Counts; won?: boolean | null; day?: string; thread_id?: number; box_references?: number[] };
export type Page<T> = { results: T[]; next_page: number | null };
export function useAccountProfile() {
  const account = useAccount();
  return useQuery({ queryKey: ['account-profile', account.data?.user?.id], enabled: !!account.data?.user,
    queryFn: () => apiFetch<ProfileData>('/api/account/profile/') });
}
export function ProfileHeading({ profile, children }: { profile: ProfileData; children?: React.ReactNode }) {
  return <header className="sc-account-identity">
    <div className="sc-account-avatar" aria-hidden="true">{profile.username[0]?.toUpperCase()}</div>
    <div><h2>@{profile.username}</h2>{profile.bio && <p>{profile.bio}</p>}
      <p className="sc-account-meta">Dołączono {formatDatePl(profile.date_joined)}</p></div>
    <dl className="sc-account-numbers">{([['threads', 'Spinki'], ['ratings', 'Oceny'], ['comments', 'Komentarze']] as const).map(([key, title]) =>
      <div key={key}><dt>{title}</dt><dd>{profile.counts[key]}</dd></div>)}</dl>
    <div className="sc-f2-actions">{children}</div>
  </header>;
}
export function EmptyState({ children, href, label }: { children: React.ReactNode; href?: string; label?: string }) {
  return <div className="sc-account-empty"><span aria-hidden="true">○</span><p>{children}</p>{href && <Button href={href} variant="secondary">{label}</Button>}</div>;
}
export function ActivityRows({ rows }: { rows: ActivityRow[] }) {
  return <ol className="sc-account-timeline">{rows.map(row => <li key={row.id}>
    <p className="sc-account-meta"><time dateTime={row.created_at}>{formatDateTimePl(row.created_at)}</time> · {row.kind === 'ratings' ? 'Ocena' : row.kind === 'votes' ? 'Głos na wywiad' : 'Komentarz'}</p>
    <Link href={row.url}>{row.title}</Link>
    {row.polarity && <p className="sc-account-rating" data-rating={row.polarity}>{({ positive: '✓ Zgadzam się', doubt: '? Mam wątpliwości', negative: '✕ Nie zgadzam się' })[row.polarity]}</p>}
    {row.body && <ClampedText>{row.body}</ClampedText>}
    {!!row.box_references?.length && <div className="sc-f2-actions">{[...new Set(row.box_references)].map(n => <Link className="sc-social-chip" key={n} href={`/spinki/${row.thread_id}#boks-${n}`}>@boks {n}</Link>)}</div>}
    {row.kind === 'votes' && <p>{row.won == null ? 'Oczekiwanie na wynik' : row.won ? 'Wywiad wybrany' : 'Wybrano inny wywiad'}{row.day && ` · ${formatDatePl(row.day)}`}</p>}
  </li>)}</ol>;
}
export function AccountActivity() {
  const account = useAccount(), [kind, setKind] = useState('all');
  const query = useInfiniteQuery({ queryKey: ['account-activity', account.data?.user?.id, kind], initialPageParam: 1,
    queryFn: ({ pageParam }) => apiFetch<Page<ActivityRow>>(`/api/account/activity/?kind=${kind}&page=${pageParam}`), getNextPageParam: last => last.next_page ?? undefined });
  const rows = query.data?.pages.flatMap(p => p.results) ?? [];
  return <section id="aktywnosc" className="sc-account-section"><header><h2>Aktywność</h2></header>
    <div className="sc-account-filter" role="group" aria-label="Rodzaj aktywności">{[['all', 'Wszystko'], ['ratings', 'Oceny'], ['comments', 'Komentarze'], ['votes', 'Głosy']].map(([id, label]) => <button key={id} aria-pressed={kind === id} onClick={() => setKind(id)}>{label}</button>)}</div>
    <AccountDataState query={query} />{query.isSuccess && !rows.length && <EmptyState href="/spinki" label="Przeglądaj spinki">Nie masz jeszcze aktywności w tej części.</EmptyState>}
    <ActivityRows rows={rows} />{query.hasNextPage && <Button disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>Pokaż więcej</Button>}
  </section>;
}
export function AccountThreads() {
  const account = useAccount();
  const [filter, setFilter] = useState('all');
  const query = useInfiniteQuery({ queryKey: ['account-threads', account.data?.user?.id, filter], initialPageParam: 1,
    queryFn: ({ pageParam }) => apiFetch<Page<PersonalContextThread>>(`/api/account/context-threads/?status=${filter}&page=${pageParam}`),
    getNextPageParam: last => last.next_page ?? undefined });
  const rows = query.data?.pages.flatMap(p => p.results) ?? [];
  return <section id="moje-tropy" className="sc-account-section"><header><h2>Moje spinki</h2><Button href="/konto/spinki/nowa" variant="primary">Ułóż spinkę</Button></header>
    <div className="sc-account-filter" role="group" aria-label="Status spinki">{[['all', 'Wszystkie'], ['draft', 'Szkice'], ['published', 'Opublikowane'], ['hidden', 'Ukryte']].map(([id, label]) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}</div>
    <AccountDataState query={query} />{query.isSuccess && !rows.length && <EmptyState href="/klinika" label="Wybierz diagnozę">Nie masz tu jeszcze spinek - ułóż pierwszą z diagnozy.</EmptyState>}
    <ul className="sc-account-thread-list">{rows.map(row => <li key={row.id}>
      <p className="sc-account-meta">{row.hidden_at ? 'Ukryta' : row.is_public ? 'Opublikowana' : 'Szkic'}</p>
      <Link href={`/konto/spinki/${row.id}`}><strong>{row.title}</strong></Link>
      {row.description && <ClampedText>{row.description}</ClampedText>}
      <p className="sc-account-meta">Zmieniono {formatDateTimePl(row.updated_at)}</p>
      <div className="sc-f2-actions"><Link href={`/konto/spinki/${row.id}`}>Edytuj</Link>{row.is_public && !row.hidden_at && <Link href={`/spinki/${row.id}`}>Zobacz spinkę</Link>}<span className="sc-account-comments-count" aria-label={`Komentarze: ${row.comments_count ?? 0}`}><SocialIcon kind="comment" /> {row.comments_count ?? 0}</span></div>
      <RatingFrame counts={row.opinions ?? { positive: 0, doubt: 0, negative: 0 }} />
    </li>)}</ul>{query.hasNextPage && <Button onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>Pokaż więcej</Button>}
  </section>;
}
type Report = { id: number; mine: boolean; target_kind: string; status: 'pending' | 'removed' | 'restored' | 'rejected'; can_appeal: boolean; appealed: boolean;
  decisions: { action: string; explanation: string; rule: string; created_at: string }[] };
export function AccountReports() {
  const account = useAccount(), cache = useQueryClient();
  const query = useInfiniteQuery({ queryKey: ['account-reports', account.data?.user?.id], initialPageParam: 1,
    queryFn: ({ pageParam }) => apiFetch<Page<Report>>(`/api/account/reports/?page=${pageParam}`), getNextPageParam: last => last.next_page ?? undefined });
  const [appeal, setAppeal] = useState<number | null>(null), [pending, setPending] = useState(false), [message, setMessage] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>, id: number) {
    event.preventDefault(); if (pending) return; setPending(true); setMessage('');
    try { await apiWrite(`/api/community/reports/${id}/`, { body: new FormData(event.currentTarget).get('body') }); setAppeal(null); await cache.invalidateQueries({ queryKey: ['account-reports'] }); setMessage('Odwołanie przyjęte.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Nie udało się wysłać odwołania.'); } finally { setPending(false); }
  }
  const rows = query.data?.pages.flatMap(p => p.results) ?? [];
  return <section id="zgloszenia" className="sc-account-section"><header><h2>Zgłoszenia</h2></header><AccountDataState query={query} />
    {query.isSuccess && !rows.length && <EmptyState>Nie masz zgłoszeń ani decyzji dotyczących Twoich treści.</EmptyState>}
    <ul className="sc-account-thread-list">{rows.map(row => <li key={row.id}>
      <h3>{row.mine ? 'Twoje zgłoszenie' : 'Decyzja dotycząca Twojej treści'} #{row.id}</h3>
      <p>{({ pending: 'W toku', removed: 'Usunięte', rejected: 'Odrzucone', restored: 'Przywrócone' })[row.status]}</p>
      {row.decisions.map((d, i) => <div key={i}><p className="sc-account-meta">{formatDateTimePl(d.created_at)} · Punkt zasad: {d.rule}</p><p>{d.explanation}</p></div>)}
      {row.can_appeal && (appeal !== row.id ? <Button onClick={() => setAppeal(row.id)}>Odwołaj się</Button> : <form onSubmit={event => submit(event, row.id)}><label>Uzasadnienie odwołania<textarea required name="body" maxLength={2000} /></label><Button type="submit" disabled={pending}>Wyślij odwołanie</Button><Button type="button" onClick={() => setAppeal(null)}>Anuluj</Button></form>)}
      {row.appealed && <p>Wykorzystano jednorazowe odwołanie.</p>}
    </li>)}</ul>{message && <p role="status">{message}</p>}{query.hasNextPage && <Button onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>Pokaż więcej</Button>}
  </section>;
}
export function ProfileEditor() {
  const profile = useAccountProfile(), cache = useQueryClient();
  const [pending, setPending] = useState(false), [message, setMessage] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (pending) return;
    const form = new FormData(event.currentTarget); setPending(true); setMessage('');
    try { await apiWrite('/api/account/profile/', { username: form.get('username'), bio: form.get('bio'), public_activity: form.get('public_activity') === 'on' }, 'PATCH');
      await Promise.all([cache.invalidateQueries({ queryKey: ['account-profile'] }), cache.invalidateQueries({ queryKey: ['account'] }), cache.invalidateQueries({ queryKey: ['public-profile'] })]); setMessage('Profil zapisany.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Nie udało się zapisać.'); } finally { setPending(false); }
  }
  return <section><h3>Profil</h3><AccountDataState query={profile} />{profile.data && <form key={JSON.stringify(profile.data)} onSubmit={submit}>
    <label>Nick<input name="username" required minLength={3} maxLength={30} pattern="[A-Za-z0-9_]{3,30}" defaultValue={profile.data.username} autoComplete="username" /></label>
    <p className="sc-account-meta">Nick możesz zmienić raz na 30 dni.{profile.data.nick_change_available_at && new Date(profile.data.nick_change_available_at) > new Date() && ` Kolejna zmiana: ${formatDatePl(profile.data.nick_change_available_at)}.`}</p>
    <label>Bio <span className="sc-account-meta">(opcjonalne, do 160 znaków)</span><textarea name="bio" maxLength={160} defaultValue={profile.data.bio} /></label>
    <label className="sc-f2-check"><input type="checkbox" name="public_activity" defaultChecked={profile.data.public_activity} />Pokaż komentarze na profilu publicznym</label>
    <p className="sc-account-meta">Komentarze pod spinkami są publiczne niezależnie od tego ustawienia.</p><Button type="submit" disabled={pending}>Zapisz profil</Button>
  </form>}{message && <p role="status">{message}</p>}</section>;
}
export function MutedSettings() {
  const account = useAccount(), cache = useQueryClient();
  const query = useQuery({ queryKey: ['account-mutes', account.data?.user?.id], queryFn: () => apiFetch<{ results: { target_id: number; target__username: string }[] }>('/api/account/mutes/') });
  const [pending, setPending] = useState(false), [message, setMessage] = useState('');
  async function unmute(id: number) { setPending(true); try { await apiWrite(`/api/account/mutes/${id}/`, {}, 'DELETE'); await cache.invalidateQueries(); } catch (error) { setMessage(error instanceof Error ? error.message : 'Nie udało się odciszyć.'); } finally { setPending(false); } }
  return <section><h3>Wyciszeni użytkownicy</h3><AccountDataState query={query} />{query.isSuccess && !query.data.results.length && <EmptyState>Nie wyciszasz żadnej osoby.</EmptyState>}
    <ul className="sc-account-rows">{query.data?.results.map(row => <li key={row.target_id}><Link href={`/profile/${encodeURIComponent(row.target__username)}`}>@{row.target__username}</Link><Button disabled={pending} onClick={() => unmute(row.target_id)}>Odcisz</Button></li>)}</ul>{message && <p role="status">{message}</p>}
  </section>;
}
