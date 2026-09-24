"use client";
import { useState } from 'react';
import Link from 'next/link';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, apiFetch, apiWrite } from '../lib/api';
import { useAccount } from '../lib/account';
import { getPortalConfig } from '../lib/portal';
import { formatDateTimePl } from '../lib/utils';
import { AccountDialog } from './AccountDialog';
import { Button, MorphList, Reveal, Switch, usePortalApi } from '../kit';
import { PersonalizedNews } from './PersonalizedNews';
import { ThemeSwitcher } from './ThemeSwitcher';

type HistoryItem = { id: number; article_id: number; body: string; polarity: 'positive' | 'negative'; created_at: string };
type HistoryPage = { results: HistoryItem[]; next_page: number | null };
type FavoritePage = { results: { id: number; thread: { id: number; slug: string; title: string }; created_at: string }[]; next_page: number | null };
type ThemePreference = 'auto' | 'dark' | 'light' | 'pastel';
type AccountProfileData = { username: string; public_activity: boolean; theme_preference: ThemePreference };
type Section = 'saved' | 'activity' | 'privacy' | 'settings';
const sections: { id: Section; label: string; description: string }[] = [
  { id: 'saved', label: 'Zapisane', description: 'Ulubione nitki i własne paski' },
  { id: 'activity', label: 'Aktywność', description: 'Twoje reakcje i komentarze' },
  { id: 'privacy', label: 'Prywatność', description: 'Widoczność Twojej historii' },
  { id: 'settings', label: 'Ustawienia', description: 'Konto i dostępne możliwości' },
];

function HistoryRows({ rows }: { rows: HistoryItem[] }) {
  return <MorphList id="account-history" as="div" itemAs="div" className="sc-account-profile-history" items={rows} getKey={item => item.id} renderItem={item => <>
    <div><span className={`history-polarity opinion-${item.polarity}`}>{item.polarity === 'positive' ? 'Przydatne' : 'Nieprzydatne'}</span><time dateTime={item.created_at}>{formatDateTimePl(item.created_at)}</time></div>
    {item.body ? <p>{item.body}</p> : <p className="sc-account-profile-muted">Reakcja bez komentarza.</p>}
    <Link href={`/material/${item.article_id}`}>Materiał i jego kontekst ↗</Link>
  </>} />;
}

function ProfileTopics() {
  const config = useQuery({ queryKey: ['portal-config'], queryFn: getPortalConfig, staleTime: 60_000 });
  const portal = usePortalApi();
  if (config.isPending) return <p role="status" className="sc-account-profile-empty">Ładuję ustawienia tematów…</p>;
  if (config.isError) return <p role="alert" className="sc-account-profile-empty">Nie udało się pobrać dostępnych filtrów. <Button size="sm" variant="quiet" onClick={() => config.refetch()}>Ponów</Button></p>;
  return <PersonalizedNews categories={config.data.categories} topics={config.data.topics ?? []} sources={config.data.sources ?? []} onSelect={portal.open} />;
}

export function AccountProfile() {
  const account = useAccount();
  const ownerId = account.data?.user?.id;
  const cache = useQueryClient();
  const [section, setSection] = useState<Section>('saved');
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const profile = useQuery({ queryKey: ['account-profile', ownerId], queryFn: () => apiFetch<AccountProfileData>('/api/account/profile/'), enabled: Boolean(ownerId) });
  const history = useInfiniteQuery({ queryKey: ['account-history', ownerId], initialPageParam: 1, queryFn: ({ pageParam }) => apiFetch<HistoryPage>(`/api/account/history/?page=${pageParam}`), getNextPageParam: last => last.next_page ?? undefined, enabled: Boolean(ownerId) && section === 'activity' });
  const favorites = useInfiniteQuery({ queryKey: ['account-favorites', ownerId], initialPageParam: 1, queryFn: ({ pageParam }) => apiFetch<FavoritePage>(`/api/account/favorites/?page=${pageParam}`), getNextPageParam: last => last.next_page ?? undefined, enabled: Boolean(ownerId) && section === 'saved' });
  function navigate(next: Section) { setSection(next); setError(''); setNotice(''); }
  async function visibility(next: boolean) {
    setPending(true); setError(''); setNotice('');
    try {
      const updated = await apiWrite('/api/account/profile/', { public_activity: next }, 'PATCH');
      cache.setQueryData(['account-profile', ownerId], updated);
      cache.removeQueries({ queryKey: ['public-profile', profile.data?.username] });
      setNotice(next ? 'Historia jest teraz widoczna na publicznym profilu.' : 'Zbiorcza historia jest teraz prywatna.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się zapisać ustawień.'); }
    finally { setPending(false); }
  }
  async function removeFavorite(threadId: number) {
    setPending(true); setError('');
    try { await apiWrite(`/api/account/favorites/${threadId}/`, {}, 'DELETE'); await Promise.all([cache.invalidateQueries({ queryKey: ['account-favorites', ownerId] }), cache.invalidateQueries({ queryKey: ['thread-favorite', ownerId, threadId] })]); }
    catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się usunąć nitki z ulubionych.'); }
    finally { setPending(false); }
  }
  if (account.isPending) return <p role="status" className="sc-account-profile-empty">Ładuję konto…</p>;
  if (!ownerId) return <section className="sc-account-profile-page sc-account-profile-signed-out"><p className="sc-account-profile-kicker">TWOJE MIEJSCE W SPIN.CLINIC</p><h1>Wracaj do tego, co ważne.</h1><p>Zapisuj nitki, układaj własne paski tematów i przeglądaj swoją aktywność. Ulubione i tematy pozostają prywatne.</p><Button variant="primary" onClick={() => setOpen(true)}>Zaloguj się</Button><Button href="/" variant="quiet">Przeglądaj wiadomości ↗</Button><AccountDialog open={open} onClose={() => setOpen(false)} /></section>;
  const user = account.data!.user!;
  const role = user.is_staff ? 'Redakcja' : user.is_journalist ? 'Dziennikarz' : 'Czytelnik';
  const current = sections.find(item => item.id === section)!;
  const historyRows = history.data?.pages.flatMap(page => page.results) ?? [];
  const favoriteRows = favorites.data?.pages.flatMap(page => page.results) ?? [];
  return <div className="sc-account-profile-page">
    <header className="sc-account-profile-header"><div><p className="sc-account-profile-kicker">TWOJE KONTO</p><h1>@{user.username}</h1><p className="sc-account-profile-role">{role}</p></div><Button href="/" variant="quiet">Wróć do wiadomości ↗</Button></header>
    <div className="sc-account-profile-workspace"><aside className="sc-account-profile-sidebar"><nav aria-label="Sekcje profilu">{sections.map(item => <Button key={item.id} type="button" variant="quiet" pressed={section === item.id} aria-current={section === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}>{item.label}</Button>)}</nav><p>Ulubione nitki i zapisane tematy widzisz tylko Ty.</p></aside>
      <div className="sc-account-profile-content"><header className="sc-account-profile-section-heading"><div><h2>{current.label}</h2><p>{current.description}</p></div>{(section === 'activity' || section === 'saved') && <span className="sc-account-profile-status">{section === 'activity' ? (profile.isSuccess ? (profile.data.public_activity ? 'Historia publiczna' : 'Historia prywatna') : 'Sprawdzam widoczność') : 'Tylko dla Ciebie'}</span>}</header>
        <Reveal when={Boolean(error)} className="sc-account-profile-message sc-account-profile-message-error"><p role="alert">{error}</p></Reveal><Reveal when={Boolean(notice)} className="sc-account-profile-message"><p role="status">{notice}</p></Reveal>
        {section === 'saved' && <>
          <section className="sc-account-profile-block"><h3>Ulubione nitki</h3>
            {favorites.isPending && <p role="status" className="sc-account-profile-empty">Ładuję ulubione…</p>}
            {favorites.isError && <p role="alert" className="sc-account-profile-empty">Nie udało się pobrać ulubionych. <Button size="sm" variant="quiet" onClick={() => favorites.refetch()}>Ponów</Button></p>}
            {favorites.isSuccess && !favoriteRows.length && <div className="sc-account-profile-empty"><p>Twoja kolekcja zaczyna się od jednej nitki.</p><p>Zapisz opublikowaną nitkę przyciskiem serca. Znajdziesz ją tutaj po powrocie.</p><Link href="/">Znajdź nitkę ↗</Link></div>}
            <MorphList id="account-favorites" as="div" itemAs="div" className="sc-account-profile-favorites" items={favoriteRows} getKey={item => item.id} renderItem={item => <><div><Link href={`/thread/${item.thread.slug}`}>{item.thread.title}</Link><time dateTime={item.created_at}>Zapisano {formatDateTimePl(item.created_at)}</time></div><Button size="sm" variant="quiet" disabled={pending} onClick={() => removeFavorite(item.thread.id)}>Usuń z ulubionych</Button></>} />
            {favorites.hasNextPage && <Button loading={favorites.isFetchingNextPage} variant="secondary" onClick={() => favorites.fetchNextPage()}>Kolejne ulubione ↓</Button>}
          </section><section className="sc-account-profile-block sc-account-profile-topics"><ProfileTopics /></section>
        </>}
        {section === 'activity' && <section className="sc-account-profile-block"><p className="sc-account-profile-explanation">Oceny i komentarze, które zostawiasz pod materiałami. Widoczność tej zbiorczej historii zmienisz w sekcji <Button size="sm" variant="quiet" onClick={() => navigate('privacy')}>Prywatność</Button>.</p>
          {history.isPending && <p role="status" className="sc-account-profile-empty">Ładuję historię…</p>}{history.isError && <p role="alert" className="sc-account-profile-empty">Nie udało się pobrać historii. <Button size="sm" variant="quiet" onClick={() => history.refetch()}>Ponów</Button></p>}
          {history.isSuccess && !historyRows.length && <div className="sc-account-profile-empty"><p>Nie masz jeszcze zapisanych reakcji ani komentarzy.</p><p>Otwórz materiał, poznaj jego kontekst i zaznacz, czy był przydatny.</p><Link href="/">Przejdź do wiadomości ↗</Link></div>}
          <HistoryRows rows={historyRows} />{history.hasNextPage && <Button loading={history.isFetchingNextPage} variant="secondary" onClick={() => history.fetchNextPage()}>Wcześniejsza aktywność ↓</Button>}
        </section>}
        {section === 'privacy' && <section className="sc-account-profile-block sc-account-profile-privacy"><h3>Widoczność historii</h3><p>Komentarze pod materiałami są publiczne. Zbiorcza historia na Twoim profilu pozostaje prywatna, dopóki jej nie udostępnisz.</p><Switch checked={profile.data?.public_activity ?? false} disabled={pending || !profile.isSuccess} onChange={visibility} label="Udostępnij historię aktywności na publicznym profilu" /> <p className="sc-account-profile-hint">Możesz wyłączyć jej widoczność w dowolnym momencie.</p>{profile.data?.public_activity && <Button href={`/profile/${encodeURIComponent(profile.data.username)}`} size="sm" variant="quiet">Zobacz publiczny profil ↗</Button>}{profile.isError && <p role="alert">Nie udało się pobrać ustawienia prywatności. <Button size="sm" variant="quiet" onClick={() => profile.refetch()}>Ponów</Button></p>}<div className="sc-account-profile-privacy-note"><h3>Zawsze prywatne</h3><p>Ulubione nitki i zapisane paski nie pojawiają się na publicznym profilu.</p></div></section>}
        {section === 'settings' && <section className="sc-account-profile-block"><h3>Dane konta</h3><dl className="sc-account-profile-details"><div><dt>Nazwa użytkownika</dt><dd>@{user.username}</dd></div><div><dt>Rola</dt><dd>{role}</dd></div><div><dt>Motyw</dt><dd><ThemeSwitcher /></dd></div><div><dt>Tworzenie nitek</dt><dd>{user.is_staff ? 'Tworzenie i publikacja redakcyjna' : user.is_journalist ? 'Własne szkice · publikacja po zatwierdzeniu redakcji' : 'Zapisane tematy, reakcje, komentarze i prywatne nitki'}</dd></div></dl><div className="sc-account-profile-shortcuts"><Button size="sm" variant="quiet" onClick={() => navigate('privacy')}>Ustaw prywatność</Button><Button size="sm" variant="quiet" onClick={() => navigate('saved')}>Zarządzaj paskami</Button>{user.can_edit_threads && <Button href="/editor" size="sm" variant="quiet">Otwórz warsztat ↗</Button>}</div></section>}
      </div>
    </div>
  </div>;
}

export function PublicAccountProfile({ username }: { username: string }) {
  const history = useInfiniteQuery({ queryKey: ['public-profile', username], initialPageParam: 1, queryFn: ({ pageParam }) => apiFetch<{ username: string; history: HistoryPage }>(`/api/profiles/${encodeURIComponent(username)}/activity/?page=${pageParam}`), getNextPageParam: last => last.history.next_page ?? undefined, retry: false });
  if (history.isPending) return <p role="status" className="sc-account-profile-empty">Ładuję publiczną historię…</p>;
  if (history.isError) return <section className="sc-account-profile-page sc-account-profile-signed-out"><p className="sc-account-profile-kicker">PROFIL UŻYTKOWNIKA</p><h1>Historia aktywności</h1><p>{history.error instanceof ApiError && history.error.status === 404 ? 'Ten profil nie udostępnia publicznej historii.' : 'Nie udało się pobrać publicznej historii.'}</p><Button href="/" variant="quiet">Wróć do wiadomości ↗</Button></section>;
  const rows = history.data.pages.flatMap(page => page.history.results);
  return <section className="sc-account-profile-page sc-account-profile-public"><header className="sc-account-profile-header"><div><p className="sc-account-profile-kicker">PROFIL PUBLICZNY</p><h1>@{history.data.pages[0].username}</h1><p className="sc-account-profile-role">Historia udostępniona przez użytkownika</p></div><Button href="/" variant="quiet">Wiadomości ↗</Button></header><div className="sc-account-profile-public-content"><h2>Aktywność</h2><HistoryRows rows={rows} />{!rows.length && <p className="sc-account-profile-empty">Brak aktywności do wyświetlenia.</p>}{history.hasNextPage && <Button loading={history.isFetchingNextPage} variant="secondary" onClick={() => history.fetchNextPage()}>Wcześniejsza aktywność ↓</Button>}</div></section>;
}



