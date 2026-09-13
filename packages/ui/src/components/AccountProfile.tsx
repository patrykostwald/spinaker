"use client";
import { useState } from 'react';
import Link from 'next/link';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, apiFetch, apiWrite } from '../lib/api';
import { useAccount } from '../lib/account';
import { getPortalConfig } from '../lib/portal';
import { formatDateTimePl } from '../lib/utils';
import type { Article } from '../types';
import { AccountDialog } from './AccountDialog';
import { ArticleModal } from './ArticleModal';
import { PersonalizedNews } from './PersonalizedNews';

type HistoryItem = { id: number; article_id: number; body: string; polarity: 'positive' | 'negative'; created_at: string };
type HistoryPage = { results: HistoryItem[]; next_page: number | null };
type FavoritePage = { results: { id: number; thread: { id: number; slug: string; title: string }; created_at: string }[]; next_page: number | null };
type Section = 'saved' | 'activity' | 'privacy' | 'settings';
const sections: { id: Section; label: string; description: string }[] = [
  { id: 'saved', label: 'Zapisane', description: 'Ulubione nitki i własne paski' },
  { id: 'activity', label: 'Aktywność', description: 'Twoje oceny i komentarze' },
  { id: 'privacy', label: 'Prywatność', description: 'Widoczność Twojej historii' },
  { id: 'settings', label: 'Ustawienia', description: 'Konto i dostępne możliwości' },
];

function HistoryRows({ rows }: { rows: HistoryItem[] }) {
  return <div className="profile-history">{rows.map(item => <article key={item.id}>
    <div><span className={`history-polarity opinion-${item.polarity}`}>{item.polarity === 'positive' ? 'Ocena pozytywna' : 'Ocena negatywna'}</span><time dateTime={item.created_at}>{formatDateTimePl(item.created_at)}</time></div>
    {item.body ? <p>{item.body}</p> : <p className="profile-muted">Ocena bez komentarza.</p>}
    <Link href={`/material/${item.article_id}`}>Materiał i jego kontekst ↗</Link>
  </article>)}</div>;
}

function ProfileTopics() {
  const config = useQuery({ queryKey: ['portal-config'], queryFn: getPortalConfig, staleTime: 60_000 });
  const [selected, setSelected] = useState<Article | null>(null);
  if (config.isPending) return <p role="status" className="profile-empty">Ładuję ustawienia tematów…</p>;
  if (config.isError) return <p role="alert" className="profile-empty">Nie udało się pobrać dostępnych filtrów. <button className="quiet-button" onClick={() => config.refetch()}>Ponów</button></p>;
  return <><PersonalizedNews categories={config.data.categories} topics={config.data.topics ?? []} sources={config.data.sources ?? []} onSelect={setSelected} /><ArticleModal article={selected} onClose={() => setSelected(null)} /></>;
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
  const profile = useQuery({ queryKey: ['account-profile', ownerId], queryFn: () => apiFetch<{ username: string; public_activity: boolean }>('/api/account/profile/'), enabled: Boolean(ownerId) });
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
  if (account.isPending) return <p role="status" className="profile-empty">Ładuję konto…</p>;
  if (!ownerId) return <section className="profile-page profile-signed-out"><p className="profile-kicker">TWOJE MIEJSCE W SPIN.CLINIC</p><h1>Wracaj do tego, co ważne.</h1><p>Zapisuj nitki, układaj własne paski tematów i przeglądaj swoją aktywność. Ulubione i tematy pozostają prywatne.</p><button className="profile-primary" onClick={() => setOpen(true)}>Zaloguj się</button><Link href="/">Przeglądaj wiadomości ↗</Link><AccountDialog open={open} onClose={() => setOpen(false)} /></section>;
  const user = account.data!.user!;
  const role = user.is_staff ? 'Redakcja' : user.is_journalist ? 'Dziennikarz' : 'Czytelnik';
  const current = sections.find(item => item.id === section)!;
  const historyRows = history.data?.pages.flatMap(page => page.results) ?? [];
  const favoriteRows = favorites.data?.pages.flatMap(page => page.results) ?? [];
  return <div className="profile-page">
    <header className="profile-header"><div><p className="profile-kicker">TWOJE KONTO</p><h1>@{user.username}</h1><p className="profile-role">{role}</p></div><Link href="/" className="quiet-button">Wróć do wiadomości ↗</Link></header>
    <div className="profile-workspace"><aside className="profile-sidebar"><nav aria-label="Sekcje profilu">{sections.map(item => <button key={item.id} type="button" aria-current={section === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}>{item.label}</button>)}</nav><p>Ulubione nitki i zapisane tematy widzisz tylko Ty.</p></aside>
      <div className="profile-content"><header className="profile-section-heading"><div><h2>{current.label}</h2><p>{current.description}</p></div>{(section === 'activity' || section === 'saved') && <span className="profile-status">{section === 'activity' ? (profile.isSuccess ? (profile.data.public_activity ? 'Historia publiczna' : 'Historia prywatna') : 'Sprawdzam widoczność') : 'Tylko dla Ciebie'}</span>}</header>
        {error && <p role="alert" className="profile-message profile-message-error">{error}</p>}{notice && <p role="status" className="profile-message">{notice}</p>}
        {section === 'saved' && <>
          <section className="profile-block"><h3>Ulubione nitki</h3>
            {favorites.isPending && <p role="status" className="profile-empty">Ładuję ulubione…</p>}
            {favorites.isError && <p role="alert" className="profile-empty">Nie udało się pobrać ulubionych. <button className="quiet-button" onClick={() => favorites.refetch()}>Ponów</button></p>}
            {favorites.isSuccess && !favoriteRows.length && <div className="profile-empty"><p>Twoja kolekcja zaczyna się od jednej nitki.</p><p>Zapisz opublikowaną nitkę przyciskiem serca. Znajdziesz ją tutaj po powrocie.</p><Link href="/">Znajdź nitkę ↗</Link></div>}
            <div className="favorite-list">{favoriteRows.map(item => <article key={item.id}><div><Link href={`/thread/${item.thread.slug}`}>{item.thread.title}</Link><time dateTime={item.created_at}>Zapisano {formatDateTimePl(item.created_at)}</time></div><button className="quiet-button" disabled={pending} onClick={() => removeFavorite(item.thread.id)}>Usuń z ulubionych</button></article>)}</div>
            {favorites.hasNextPage && <button disabled={favorites.isFetchingNextPage} className="load-news-button" onClick={() => favorites.fetchNextPage()}>Kolejne ulubione ↓</button>}
          </section><section className="profile-block profile-topics"><ProfileTopics /></section>
        </>}
        {section === 'activity' && <section className="profile-block"><p className="profile-explanation">Oceny i komentarze, które zostawiasz pod materiałami. Widoczność tej zbiorczej historii zmienisz w sekcji <button onClick={() => navigate('privacy')}>Prywatność</button>.</p>
          {history.isPending && <p role="status" className="profile-empty">Ładuję historię…</p>}{history.isError && <p role="alert" className="profile-empty">Nie udało się pobrać historii. <button className="quiet-button" onClick={() => history.refetch()}>Ponów</button></p>}
          {history.isSuccess && !historyRows.length && <div className="profile-empty"><p>Nie masz jeszcze zapisanych ocen ani komentarzy.</p><p>Otwórz materiał, poznaj jego kontekst i dodaj swoją ocenę.</p><Link href="/">Przejdź do wiadomości ↗</Link></div>}
          <HistoryRows rows={historyRows} />{history.hasNextPage && <button disabled={history.isFetchingNextPage} className="load-news-button" onClick={() => history.fetchNextPage()}>Wcześniejsza aktywność ↓</button>}
        </section>}
        {section === 'privacy' && <section className="profile-block profile-privacy"><h3>Widoczność historii</h3><p>Komentarze pod materiałami są publiczne. Zbiorcza historia na Twoim profilu pozostaje prywatna, dopóki jej nie udostępnisz.</p><label><input type="checkbox" checked={profile.data?.public_activity ?? false} disabled={pending || !profile.isSuccess} onChange={e => visibility(e.target.checked)} /><span>Udostępnij historię aktywności na publicznym profilu<small>Możesz wyłączyć jej widoczność w dowolnym momencie.</small></span></label>{profile.data?.public_activity && <Link href={`/profile/${encodeURIComponent(profile.data.username)}`}>Zobacz publiczny profil ↗</Link>}{profile.isError && <p role="alert">Nie udało się pobrać ustawienia prywatności. <button className="quiet-button" onClick={() => profile.refetch()}>Ponów</button></p>}<div className="profile-privacy-note"><h3>Zawsze prywatne</h3><p>Ulubione nitki i zapisane paski nie pojawiają się na publicznym profilu.</p></div></section>}
        {section === 'settings' && <section className="profile-block"><h3>Dane konta</h3><dl className="profile-details"><div><dt>Nazwa użytkownika</dt><dd>@{user.username}</dd></div><div><dt>Rola</dt><dd>{role}</dd></div><div><dt>Tworzenie nitek</dt><dd>{user.is_staff ? 'Tworzenie i publikacja redakcyjna' : user.is_journalist ? 'Własne szkice · publikacja po zatwierdzeniu redakcji' : 'Zapisane tematy, oceny i komentarze'}</dd></div></dl><div className="profile-shortcuts"><button className="quiet-button" onClick={() => navigate('privacy')}>Ustaw prywatność</button><button className="quiet-button" onClick={() => navigate('saved')}>Zarządzaj paskami</button>{user.can_edit_threads && <Link className="quiet-button" href="/editor">Otwórz warsztat ↗</Link>}</div></section>}
      </div>
    </div>
  </div>;
}

export function PublicAccountProfile({ username }: { username: string }) {
  const history = useInfiniteQuery({ queryKey: ['public-profile', username], initialPageParam: 1, queryFn: ({ pageParam }) => apiFetch<{ username: string; history: HistoryPage }>(`/api/profiles/${encodeURIComponent(username)}/activity/?page=${pageParam}`), getNextPageParam: last => last.history.next_page ?? undefined, retry: false });
  if (history.isPending) return <p role="status" className="profile-empty">Ładuję publiczną historię…</p>;
  if (history.isError) return <section className="profile-page profile-signed-out"><p className="profile-kicker">PROFIL UŻYTKOWNIKA</p><h1>Historia aktywności</h1><p>{history.error instanceof ApiError && history.error.status === 404 ? 'Ten profil nie udostępnia publicznej historii.' : 'Nie udało się pobrać publicznej historii.'}</p><Link className="quiet-button" href="/">Wróć do wiadomości ↗</Link></section>;
  const rows = history.data.pages.flatMap(page => page.history.results);
  return <section className="profile-page profile-public"><header className="profile-header"><div><p className="profile-kicker">PROFIL PUBLICZNY</p><h1>@{history.data.pages[0].username}</h1><p className="profile-role">Historia udostępniona przez użytkownika</p></div><Link className="quiet-button" href="/">Wiadomości ↗</Link></header><div className="profile-public-content"><h2>Aktywność</h2><HistoryRows rows={rows} />{!rows.length && <p className="profile-empty">Brak aktywności do wyświetlenia.</p>}{history.hasNextPage && <button className="load-news-button" disabled={history.isFetchingNextPage} onClick={() => history.fetchNextPage()}>Wcześniejsza aktywność ↓</button>}</div></section>;
}
