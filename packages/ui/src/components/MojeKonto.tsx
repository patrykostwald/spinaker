"use client";

import { useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiWrite } from '../lib/api';
import { categoryLabel, formatDateTimePl } from '../lib/utils';
import {
  isUnavailable,
  personalKeys,
  removeThreadFavorite,
  setArticleFavorite,
  useArticleFavorites,
  useOwnerId,
  usePersonalThreads,
  useSavedTopics,
  useThreadFavorites,
} from '../lib/personal';
import { AccountDialog } from './AccountDialog';
import { THREADS_ENABLED } from '../lib/features';
import { Button } from '../kit';

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
      <p>Po zalogowaniu możesz zapisywać materiały, oceniać diagnozy w Klinice, komentować i wracać do swoich pasków.</p>
      <ul className="sc-account-points">
        {THREADS_ENABLED && <li>Nitki możesz zostawić prywatne albo opublikować w sekcji Nitki — decydujesz przy każdej.</li>}
        <li>Reakcje dotyczą materiału, diagnozy albo nitki — nie osób. Komentarz zawsze idzie z reakcją.</li>
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
    <Section id="ulubione-materialy" title="Materiały" count={favorites.isSuccess ? rows.length : undefined}>
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
    <Section id="ulubione-nitki" title="Nitki Dr. Spina" count={favorites.isSuccess ? rows.length : undefined}>
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
    <Section id="paski-tematow" title="Paski tematów na koncie" count={topics.isSuccess ? rows.length : undefined}
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

type Reaction = {
  kind: 'material' | 'drspin' | 'clinic' | 'community';
  id: number;
  polarity: 'positive' | 'negative';
  body: string;
  created_at: string;
  target: { title: string; href: string };
};
type Reactions = { results: Reaction[]; counts: Record<Reaction['kind'], number>; comments: number };

const REACTION_KINDS: Array<{ value: Reaction['kind'] | 'all'; label: string }> = [
  { value: 'all', label: 'Wszystko' },
  { value: 'material', label: 'Materiały' },
  { value: 'clinic', label: 'Klinika' },
  { value: 'community', label: 'Nitki czytelników' },
  { value: 'drspin', label: 'Dr. Spin' },
];
const KIND_LABEL: Record<Reaction['kind'], string> = { material: 'MATERIAŁ', clinic: 'KLINIKA', community: 'NITKA', drspin: 'DR. SPIN' };
const POLARITY_LABEL: Record<Reaction['kind'], [string, string]> = {
  material: ['Przydatny', 'Nieprzydatny'],
  clinic: ['Trafna diagnoza', 'Nietrafna diagnoza'],
  community: ['Przydatna', 'Nieprzydatna'],
  drspin: ['Przydatna', 'Nieprzydatna'],
};

function useMyReactions() {
  const { ownerId } = useOwnerId();
  return useQuery({ queryKey: ['my-reactions', ownerId], queryFn: () => apiFetch<Reactions>('/api/account/reactions/'), enabled: Boolean(ownerId) });
}

function threadStatus(thread: { is_public?: boolean; hidden_at?: string | null }) {
  if (thread.hidden_at) return { label: 'UKRYTA', tone: 'hidden', hint: 'ukryta przez zespół po zgłoszeniu' };
  if (thread.is_public) return { label: 'PUBLICZNA', tone: 'public', hint: 'widoczna w sekcji Nitki' };
  return { label: 'PRYWATNA', tone: 'private', hint: 'widzisz ją tylko Ty' };
}

function ThreadsSection() {
  const threads = usePersonalThreads();
  const rows = threads.data?.results ?? [];
  const publicCount = rows.filter(row => row.is_public && !row.hidden_at).length;
  return (
    <Section id="moje-nitki" title="Moje nitki kontekstowe" count={threads.isSuccess ? rows.length : undefined}
      action={<Button href="/konto/nitki/nowa" variant="primary" size="sm">+ Nowa nitka</Button>}>
      <p className="sc-account-hint">Nitka to jeden materiał na początku i to, co go dopełnia — z Bazy albo dodane przez link. Prywatną widzisz tylko Ty; publiczna trafia do sekcji <Link href="/nitki">Nitki</Link>{publicCount ? ` (masz ${publicCount} ${plural(publicCount, 'publiczną', 'publiczne', 'publicznych')})` : ''}.</p>
      <QueryState query={threads} unavailableText="Nitki są chwilowo niedostępne." />
      {threads.isSuccess && !rows.length && (
        <div className="sc-account-emptycard">
          <p><strong>Nie masz jeszcze żadnej nitki.</strong></p>
          <p>Zacznij od materiału otwierającego, dodaj to, co go wyjaśnia, i ustaw kolejność. Możesz ją zostawić prywatną albo opublikować.</p>
          <Button href="/konto/nitki/nowa" variant="primary" size="sm">Ułóż pierwszą nitkę</Button>
        </div>
      )}
      {rows.length > 0 && (
        <ul className="sc-account-cards">
          {rows.map(thread => {
            const status = threadStatus(thread);
            const count = thread.elements?.length ?? thread.articles.length;
            return (
              <li key={thread.id} className="sc-account-card">
                <p className="sc-account-card__meta"><span className="sc-account-status" data-tone={status.tone}>{status.label}</span>{status.hint}</p>
                <Link href={`/konto/nitki/${thread.id}`} className="sc-account-card__title">{thread.title}</Link>
                {thread.description && <p className="sc-account-desc">{thread.description}</p>}
                <p className="sc-account-meta">
                  {count} {plural(count, 'element', 'elementy', 'elementów')} · zmieniono <time dateTime={thread.updated_at}>{formatDateTimePl(thread.updated_at)}</time>
                </p>
                <p className="sc-account-card__actions">
                  <Link href={`/konto/nitki/${thread.id}`}>Edytuj</Link>
                  {thread.is_public && !thread.hidden_at && <Link href={`/nitki/${thread.id}`}>Zobacz publicznie ↗</Link>}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

function StripsSection() {
  return (
    <section id="paski" className="sc-account-section" aria-labelledby="paski-title">
      <header><h2 id="paski-title">Moje paski</h2></header>
      <div className="sc-account-duo">
        <div className="sc-account-emptycard">
          <p><strong>Nitki newsowe na stronie głównej</strong></p>
          <p>Do pięciu pasków najnowszych materiałów według hasła, kategorii albo źródła. Zapisują się na tym urządzeniu — działają także bez konta.</p>
          <Button href="/#nitki" variant="quiet" size="sm">Ustaw paski na stronie głównej →</Button>
        </div>
        <TopicsSection />
      </div>
    </section>
  );
}

function ReactionsSection() {
  const reactions = useMyReactions();
  const [kind, setKind] = useState<Reaction['kind'] | 'all'>('all');
  const rows = (reactions.data?.results ?? []).filter(row => kind === 'all' || row.kind === kind);
  return (
    <Section id="reakcje" title="Reakcje i komentarze" count={reactions.isSuccess ? reactions.data.results.length : undefined}>
      <p className="sc-account-hint">Twoje oceny i komentarze w całym serwisie. Komentarze są publiczne pod materiałem, diagnozą albo nitką; zbiorcza lista — tylko dla Ciebie, chyba że włączysz publiczną aktywność w ustawieniach.</p>
      <div className="sc-account-filter" role="group" aria-label="Filtruj reakcje">
        {REACTION_KINDS.map(option => (
          <button key={option.value} type="button" aria-pressed={kind === option.value} onClick={() => setKind(option.value)}>
            {option.label}{option.value !== 'all' && reactions.data ? ` ${reactions.data.counts[option.value]}` : ''}
          </button>
        ))}
      </div>
      <QueryState query={reactions} unavailableText="Lista reakcji jest chwilowo niedostępna." />
      {reactions.isSuccess && !rows.length && <p className="sc-account-empty">Brak reakcji w tej części. Oceniaj materiały, diagnozy i nitki — trafią tutaj.</p>}
      {rows.length > 0 && (
        <ol className="sc-account-activity">
          {rows.slice(0, 50).map(row => (
            <li key={`${row.kind}-${row.id}`}>
              <time dateTime={row.created_at}>{formatDateTimePl(row.created_at)}</time>
              <span className="sc-account-tag">{KIND_LABEL[row.kind]}</span>
              <p>
                <span className="sc-account-polarity" data-polarity={row.polarity}>{POLARITY_LABEL[row.kind][row.polarity === 'positive' ? 0 : 1]}</span>
                {' — '}<Link href={row.target.href}>{row.target.title}</Link>
                {row.body && <span className="sc-account-comment">„{row.body}”</span>}
              </p>
            </li>
          ))}
        </ol>
      )}
    </Section>
  );
}

function Overview() {
  const threads = usePersonalThreads();
  const articles = useArticleFavorites();
  const drspin = useThreadFavorites();
  const reactions = useMyReactions();
  const threadRows = threads.data?.results ?? [];
  const tiles = [
    ...(!THREADS_ENABLED ? [] : [{ href: '#moje-nitki', label: 'Moje nitki', value: threads.isSuccess ? threadRows.length : null, note: threads.isSuccess ? (() => { const n = threadRows.filter(row => row.is_public && !row.hidden_at).length; return `${n} ${plural(n, 'publiczna', 'publiczne', 'publicznych')}`; })() : '' }]),
    { href: '#ulubione', label: 'Ulubione', value: articles.isSuccess && drspin.isSuccess ? (articles.data.results.length + drspin.data.results.length) : null, note: 'materiały i nitki Dr. Spina' },
    { href: '#reakcje', label: 'Reakcje', value: reactions.isSuccess ? reactions.data.results.length : null, note: reactions.isSuccess ? `${reactions.data.comments} z komentarzem` : '' },
  ];
  return (
    <section className="sc-account-overview" aria-label="Przegląd konta">
      {tiles.map(tile => (
        <a key={tile.href} href={tile.href} className="sc-account-tile">
          <span className="sc-account-tile__label">{tile.label}</span>
          <strong className="sc-account-tile__value">{tile.value ?? '—'}</strong>
          <span className="sc-account-tile__note">{tile.note}</span>
        </a>
      ))}
      <div className="sc-account-tile sc-account-tile--actions">
        <span className="sc-account-tile__label">Na skróty</span>
        {THREADS_ENABLED && <Link href="/konto/nitki/nowa">+ Nowa nitka</Link>}
        <Link href="/klinika">Klinika spinu</Link>
        {THREADS_ENABLED ? <Link href="/nitki">Nitki czytelników</Link> : <Link href="/">Wiadomości</Link>}
      </div>
    </section>
  );
}

const NAV = [
  { id: 'moje-nitki', label: 'Moje nitki' },
  { id: 'ulubione', label: 'Ulubione' },
  { id: 'paski', label: 'Paski' },
  { id: 'reakcje', label: 'Reakcje i komentarze' },
];

export function MojeKonto() {
  const { account, ownerId } = useOwnerId();
  if (account.isPending) return <p role="status" className="sc-account-empty">Sprawdzam, czy jesteś zalogowany…</p>;
  if (!ownerId) return <SignedOutPanel />;
  const user = account.data!.user!;
  return (
    <div className="sc-account sc-account-dashboard">
      <header className="sc-account-head">
        <p className="sc-account-kicker">MOJE KONTO</p>
        <h1>@{user.username}</h1>
        <p>{THREADS_ENABLED ? 'Twoje nitki, ulubione, paski, reakcje i komentarze — w jednym miejscu.' : 'Twoje ulubione, paski, reakcje i komentarze — w jednym miejscu.'}</p>
      </header>
      <Overview />
      <div className="sc-account-layout">
        <nav className="sc-account-sidenav" aria-label="Sekcje konta">
          {NAV.filter(item => THREADS_ENABLED || item.id !== 'moje-nitki').map(item => <a key={item.id} href={`#${item.id}`}>{item.label}</a>)}
          <Link href="/profile">Ustawienia i prywatność</Link>
        </nav>
        <div className="sc-account-content">
          {THREADS_ENABLED && <ThreadsSection />}
          <section id="ulubione" className="sc-account-section" aria-labelledby="ulubione-title">
            <header><h2 id="ulubione-title">Ulubione</h2></header>
            <div className="sc-account-duo">
              <ArticleFavoritesSection />
              <ThreadFavoritesSection />
            </div>
          </section>
          <StripsSection />
          <ReactionsSection />
        </div>
      </div>
    </div>
  );
}
