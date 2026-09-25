"use client";

import { useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import { apiWrite } from '../lib/api';
import { categoryLabel, formatDateTimePl } from '../lib/utils';
import {
  REACTION_LABELS,
  isUnavailable,
  personalKeys,
  removeThreadFavorite,
  setArticleFavorite,
  splitKeywords,
  useArticleFavorites,
  useOwnerId,
  usePersonalThreads,
  useRecentHistory,
  useSavedTopics,
  useThreadFavorites,
} from '../lib/personal';
import { AccountDialog } from './AccountDialog';
import { Button } from '../kit';

const SECTIONS = [
  { id: 'moje-nitki', label: 'Moje nitki kontekstowe' },
  { id: 'ulubione-materialy', label: 'Ulubione materiały' },
  { id: 'ulubione-nitki', label: 'Ulubione nitki Dr. Spina' },
  { id: 'paski', label: 'Moje paski tematów' },
  { id: 'aktywnosc', label: 'Ostatnia aktywność' },
];

function plural(count: number, one: string, few: string, many: string) {
  const tens = count % 100;
  const units = count % 10;
  if (count === 1) return one;
  if (units >= 2 && units <= 4 && (tens < 12 || tens > 14)) return few;
  return many;
}

/** Spokojny ekran dla osób niezalogowanych — korzysta z istniejącego okna logowania. */
export function SignedOutPanel({ title = 'Twoje prywatne miejsce do pracy z materiałami' }: { title?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="sc-account sc-account-signed-out" aria-labelledby="acc-signed-out">
      <p className="sc-account-kicker">MOJE KONTO</p>
      <h1 id="acc-signed-out">{title}</h1>
      <p>Po zalogowaniu możesz układać własne nitki kontekstowe, zapisywać materiały i nitki Dr. Spina oraz wracać do swoich pasków tematów.</p>
      <ul className="sc-account-points">
        <li>Twoje nitki widzisz tylko Ty. Nie są publikowane i nie są nitkami Dr. Spina.</li>
        <li>Reakcje „Przydatne / Nieprzydatne” dotyczą konkretnego materiału lub nitki — nie osób.</li>
        <li>Korzystanie z Bazy nie wymaga konta.</li>
      </ul>
      <div className="sc-info-page__actions">
        <Button type="button" variant="primary" onClick={() => setOpen(true)}>Zaloguj się lub załóż konto</Button>
        <Button href="/search" variant="secondary">Przeglądaj Bazę</Button>
      </div>
      {open && <AccountDialog open={open} onClose={() => setOpen(false)} />}
    </section>
  );
}

function Section({ id, title, count, action, children }: { id: string; title: string; count?: number; action?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} className="sc-account-section" aria-labelledby={`${id}-title`}>
      <header>
        <h2 id={`${id}-title`}>{title}{typeof count === 'number' && <span>{count}</span>}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}

/** Ładowanie, brak endpointu na serwerze (pusty stan bez udawania zapisu) albo błąd z ponowieniem. */
function QueryState({ query, unavailableText }: { query: { isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown }; unavailableText: string }) {
  if (query.isPending) return <p role="status" className="sc-account-empty">Ładuję…</p>;
  if (query.isError && isUnavailable(query.error)) return <p className="sc-account-empty sc-account-unavailable">{unavailableText}</p>;
  if (query.isError) return <p role="alert" className="sc-account-empty">Nie udało się pobrać danych. <Button type="button" variant="quiet" size="sm" onClick={() => query.refetch()}>Ponów</Button></p>;
  return null;
}

function ThreadsSection() {
  const threads = usePersonalThreads();
  const rows = threads.data?.results ?? [];
  return (
    <Section id="moje-nitki" title="Moje nitki kontekstowe" count={threads.isSuccess ? rows.length : undefined}
      action={threads.isError && isUnavailable(threads.error) ? null : <Button href="/konto/nitki/nowa" variant="quiet" size="sm" className="sc-account-new">+ Nowa nitka</Button>}>
      <p className="sc-account-private"><span>PRYWATNE</span> Nitki widzisz tylko Ty. Nie są publikowane, nie są nitkami Dr. Spina i nie układa ich AI.</p>
      <QueryState query={threads} unavailableText="Prywatne nitki są w trakcie udostępniania w interfejsie MVP. Nic nie zostało zapisane." />
      {threads.isSuccess && !rows.length && (
        <div className="sc-account-empty">
          <p>Nie masz jeszcze żadnej nitki.</p>
          <p>Zacznij od tytułu, dodaj hasła i materiały z Bazy, a potem ustaw ich kolejność.</p>
        </div>
      )}
      {rows.length > 0 && (
        <ul className="sc-account-rows">
          {rows.map(thread => (
            <li key={thread.id}>
              <div>
                <Link href={`/konto/nitki/${thread.id}`} className="sc-account-title">{thread.title}</Link>
                {thread.description && <p className="sc-account-desc">{thread.description}</p>}
                <p className="sc-account-meta">
                  {thread.articles.length} {plural(thread.articles.length, 'materiał', 'materiały', 'materiałów')}
                  {splitKeywords(thread.query).length > 0 && ` · hasła: ${splitKeywords(thread.query).join(', ')}`}
                  {' · '}zmieniono <time dateTime={thread.updated_at}>{formatDateTimePl(thread.updated_at)}</time>
                </p>
              </div>
              <Button href={`/konto/nitki/${thread.id}`} variant="quiet" size="sm">Otwórz<span className="sr-only"> nitkę {thread.title}</span></Button>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function ArticleFavoritesSection() {
  const { ownerId } = useOwnerId();
  const favorites = useArticleFavorites();
  const cache = useQueryClient();
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const rows = favorites.data?.results ?? [];
  async function remove(articleId: number) {
    if (!ownerId) return;
    setPendingId(articleId); setError('');
    try { await setArticleFavorite(cache, ownerId, articleId, false); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Nie udało się usunąć materiału z ulubionych.'); }
    finally { setPendingId(null); }
  }
  return (
    <Section id="ulubione-materialy" title="Ulubione materiały" count={favorites.isSuccess ? rows.length : undefined}>
      <QueryState query={favorites} unavailableText="Ulubione materiały są w trakcie udostępniania w interfejsie MVP." />
      {favorites.isSuccess && !rows.length && <p className="sc-account-empty">Zapisz materiał znakiem ♡ w jego boxie albo w oknie materiału.</p>}
      {error && <p role="alert" className="sc-account-error">{error}</p>}
      {rows.length > 0 && (
        <ul className="sc-account-rows">
          {rows.map(row => (
            <li key={row.id}>
              <div>
                <p className="sc-account-meta"><span className="sc-account-tag">{categoryLabel(row.article.category)}</span> {row.article.published_date ? formatDateTimePl(row.article.published_date) : 'data publikacji nieznana'}</p>
                <Link href={`/material/${row.article.id}`} className="sc-account-title">{row.article.title}</Link>
                <p className="sc-account-links">
                  <Link href={`/material/${row.article.id}`}>Materiał i kontekst</Link>
                  <a href={row.article.url} target="_blank" rel="noopener noreferrer">Oryginał ↗</a>
                </p>
              </div>
              <Button type="button" variant="quiet" size="sm" disabled={pendingId === row.article.id} onClick={() => remove(row.article.id)}>
                Usuń<span className="sr-only"> z ulubionych: {row.article.title}</span>
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function ThreadFavoritesSection() {
  const { ownerId } = useOwnerId();
  const favorites = useThreadFavorites();
  const cache = useQueryClient();
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const rows = favorites.data?.results ?? [];
  async function remove(threadId: number) {
    if (!ownerId) return;
    setPendingId(threadId); setError('');
    try { await removeThreadFavorite(cache, ownerId, threadId); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Nie udało się usunąć nitki z ulubionych.'); }
    finally { setPendingId(null); }
  }
  return (
    <Section id="ulubione-nitki" title="Ulubione nitki Dr. Spina" count={favorites.isSuccess ? rows.length : undefined}>
      <QueryState query={favorites} unavailableText="Ulubione nitki są w trakcie udostępniania w interfejsie MVP." />
      {favorites.isSuccess && !rows.length && <p className="sc-account-empty">Zapisz opublikowaną nitkę kontekstową przyciskiem ♡ Zapisz na jej stronie.</p>}
      {error && <p role="alert" className="sc-account-error">{error}</p>}
      {rows.length > 0 && (
        <ul className="sc-account-rows">
          {rows.map(row => (
            <li key={row.id}>
              <div>
                <p className="sc-account-meta"><span className="sc-account-tag">DR SPIN</span> zapisano <time dateTime={row.created_at}>{formatDateTimePl(row.created_at)}</time></p>
                <Link href={`/thread/${row.thread.slug}`} className="sc-account-title">{row.thread.title}</Link>
              </div>
              <Button type="button" variant="quiet" size="sm" disabled={pendingId === row.thread.id} onClick={() => remove(row.thread.id)}>
                Usuń<span className="sr-only"> z ulubionych: {row.thread.title}</span>
              </Button>
            </li>
          ))}
        </ul>
      )}
      {favorites.data?.next_page && <p className="sc-account-more"><Link href="/profile">Wszystkie ulubione nitki w profilu →</Link></p>}
    </Section>
  );
}

function TopicsSection() {
  const { ownerId } = useOwnerId();
  const topics = useSavedTopics();
  const cache = useQueryClient();
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const rows = [...(topics.data?.topics ?? [])].sort((a, b) => a.position - b.position);
  async function remove(id: number) {
    setPending(true); setError('');
    try { await apiWrite(`/api/account/topics/${id}/`, {}, 'DELETE'); await cache.invalidateQueries({ queryKey: personalKeys.topics(ownerId) }); setConfirmId(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Nie udało się usunąć paska.'); }
    finally { setPending(false); }
  }
  return (
    <Section id="paski" title="Moje paski tematów" count={topics.isSuccess ? rows.length : undefined}
      action={<Button href="/profile" variant="quiet" size="sm">Dodaj lub edytuj w profilu</Button>}>
      <QueryState query={topics} unavailableText="Paski tematów na koncie są w trakcie udostępniania w interfejsie MVP." />
      {topics.isSuccess && !rows.length && <p className="sc-account-empty">Pasek to zapisany widok Bazy: hasło, kategorie lub źródła. Możesz mieć do {topics.data.max_topics} pasków.</p>}
      {error && <p role="alert" className="sc-account-error">{error}</p>}
      {rows.length > 0 && (
        <ul className="sc-account-rows">
          {rows.map(topic => (
            <li key={topic.id}>
              <div>
                <p className="sc-account-title">{topic.label}</p>
                <p className="sc-account-meta">
                  {[topic.query && `hasło: ${topic.query}`, topic.categories.length && `${topic.categories.length} ${plural(topic.categories.length, 'kategoria', 'kategorie', 'kategorii')}`, topic.source_ids.length && `${topic.source_ids.length} ${plural(topic.source_ids.length, 'źródło', 'źródła', 'źródeł')}`].filter(Boolean).join(' · ') || 'wszystkie materiały'}
                </p>
              </div>
              {confirmId === topic.id ? (
                <span className="sc-account-confirm">
                  <Button type="button" variant="quiet" size="sm" disabled={pending} onClick={() => remove(topic.id)}>Potwierdź usunięcie</Button>
                  <Button type="button" variant="quiet" size="sm" onClick={() => setConfirmId(null)}>Anuluj</Button>
                </span>
              ) : (
                <Button type="button" variant="quiet" size="sm" onClick={() => setConfirmId(topic.id)}>Usuń<span className="sr-only"> pasek {topic.label}</span></Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

type ActivityItem = { key: string; at: string; kind: string; text: ReactNode };

function ActivitySection() {
  const history = useRecentHistory();
  const threads = usePersonalThreads();
  const articleFavorites = useArticleFavorites();
  const threadFavorites = useThreadFavorites();
  const items: ActivityItem[] = [
    ...(history.data?.results ?? []).map(row => ({
      key: `o-${row.id}`, at: row.created_at, kind: 'REAKCJA',
      text: <>{REACTION_LABELS[row.polarity]}{row.body ? ` · „${row.body}”` : ''} — <Link href={`/material/${row.article_id}`}>materiał #{row.article_id}</Link></>,
    })),
    ...(threads.data?.results ?? []).map(row => ({
      key: `t-${row.id}`, at: row.updated_at, kind: 'MOJA NITKA',
      text: <>Zmieniono nitkę <Link href={`/konto/nitki/${row.id}`}>{row.title}</Link></>,
    })),
    ...(articleFavorites.data?.results ?? []).map(row => ({
      key: `a-${row.id}`, at: row.created_at, kind: 'ULUBIONE',
      text: <>Zapisano materiał <Link href={`/material/${row.article.id}`}>{row.article.title}</Link></>,
    })),
    ...(threadFavorites.data?.results ?? []).map(row => ({
      key: `f-${row.id}`, at: row.created_at, kind: 'ULUBIONE',
      text: <>Zapisano nitkę Dr. Spina <Link href={`/thread/${row.thread.slug}`}>{row.thread.title}</Link></>,
    })),
  ].sort((a, b) => b.at.localeCompare(a.at)).slice(0, 10);
  const loading = [history, threads, articleFavorites, threadFavorites].some(query => query.isPending);
  return (
    <Section id="aktywnosc" title="Ostatnia aktywność">
      <p className="sc-account-private"><span>PRYWATNE</span> Zbiorcza historia jest domyślnie prywatna. Komentarze pod materiałami są publiczne.</p>
      {loading && !items.length && <p role="status" className="sc-account-empty">Ładuję…</p>}
      {!loading && !items.length && <p className="sc-account-empty">Tu pojawią się Twoje reakcje, zapisane materiały i zmiany w nitkach.</p>}
      {items.length > 0 && (
        <ol className="sc-account-activity">
          {items.map(item => (
            <li key={item.key}>
              <time dateTime={item.at}>{formatDateTimePl(item.at)}</time>
              <span className="sc-account-tag">{item.kind}</span>
              <p>{item.text}</p>
            </li>
          ))}
        </ol>
      )}
      <p className="sc-account-more"><Link href="/profile">Pełna historia i ustawienia prywatności →</Link></p>
    </Section>
  );
}

export function MojeKonto() {
  const { account, ownerId } = useOwnerId();
  if (account.isPending) return <p role="status" className="sc-account-empty">Sprawdzam, czy jesteś zalogowany…</p>;
  if (!ownerId) return <SignedOutPanel />;
  const user = account.data!.user!;
  return (
    <div className="sc-account">
      <header className="sc-account-head">
        <p className="sc-account-kicker">MOJE KONTO</p>
        <h1>@{user.username}</h1>
        <p>Twoje nitki, ulubione i paski są prywatne. Publiczne są tylko komentarze, które dodasz pod materiałami.</p>
        <nav className="sc-account-toc" aria-label="Sekcje konta">
          {SECTIONS.map(section => <a key={section.id} href={`#${section.id}`}>{section.label}</a>)}
          <Link href="/profile">Ustawienia i prywatność</Link>
        </nav>
      </header>
      <ThreadsSection />
      <ArticleFavoritesSection />
      <ThreadFavoritesSection />
      <TopicsSection />
      <ActivitySection />
    </div>
  );
}
