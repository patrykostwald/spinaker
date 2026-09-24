"use client";

import { useId, useMemo, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useInfiniteQuery, useQueries, useQuery } from '@tanstack/react-query';
import { getNewsFeed, getPortalConfig, type CategoryOption } from '../lib/portal';
import { useOwnerId } from '../lib/personal';
import {
  ALL_GROUP_CATEGORIES,
  MATERIAL_GROUPS,
  ORGANISATION_KIND_LABELS,
  ORGANISATION_KIND_ORDER,
  ROLE_CATEGORY_LABELS,
  groupOfCategory,
  verifiedXAccount,
  type MaterialGroupKey,
  type PublicFigureDetail,
  type PublicFigureOrganisation,
  type PublicFigureVote,
} from '../lib/publicFigures';
import type { Article } from '../types';
import { AccountDialog } from './AccountDialog';
import { ArticleFavoriteButton } from './ArticleFavoriteButton';
import { voteLabel } from './VotingDetails';
import { Button, MorphIndicator } from '../kit';

type FigureMaterial = Pick<Article, 'id' | 'title' | 'url' | 'category' | 'published_date'> & {
  source_id: number;
  source_name: string;
  topics: string[];
};

const TIME_ZONE = 'Europe/Warsaw';
const dayFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' });
const dateFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, day: 'numeric', month: 'short', year: 'numeric' });
const hourFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: TIME_ZONE, hour: '2-digit', minute: '2-digit', hour12: false });
const dayKeyFormat = new Intl.DateTimeFormat('sv-SE', { timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' });

const GROUP_TAGS: Record<MaterialGroupKey, string> = {
  artykuly: 'ARTYKUŁ', reportaze: 'REPORTAŻ', wywiady: 'WYWIAD', dokumenty: 'DOKUMENT', filmy: 'FILM', posty: 'POST', komunikaty: 'KOMUNIKAT',
};

const formatDay = (iso: string | null) => (iso ? dateFormat.format(new Date(iso)) : 'data nieustalona');
const isHttp = (url: string | null | undefined): url is string => Boolean(url && /^https?:\/\//i.test(url));

function plural(count: number, one: string, few: string, many: string) {
  const tens = count % 100;
  const units = count % 10;
  if (count === 1) return one;
  if (units >= 2 && units <= 4 && (tens < 12 || tens > 14)) return few;
  return many;
}

/** Link zewnętrzny wyłącznie dla adresów http(s). */
function SourceLink({ href, children }: { href: string | null | undefined; children: ReactNode }) {
  if (!isHttp(href)) return null;
  return <a href={href} target="_blank" rel="noopener noreferrer">{children} <span aria-hidden="true">↗</span><span className="sr-only"> (otwiera się w nowej karcie)</span></a>;
}

function Neutral({ children }: { children: ReactNode }) {
  return <p className="sc-public-figure-neutral">{children}</p>;
}

/* ——— Nagłówek profilu ——— */

function FigureHeader({ figure, titleId, materialsTotal, onSelect }: { figure: PublicFigureDetail; titleId: string; materialsTotal: number | null; onSelect: (tab: 'votes' | 'relations' | 'materials') => void }) {
  const { ownerId } = useOwnerId();
  const [loginOpen, setLoginOpen] = useState(false);
  const x = verifiedXAccount(figure);
  const organisations = figure.organisations.length;
  return (
    <header className="sc-public-figure-head">
      <p className="sc-public-figure-kicker">OSOBA PUBLICZNA · {ROLE_CATEGORY_LABELS[figure.role_category] ?? 'rola publiczna'}</p>
      <h1 id={titleId} tabIndex={-1}>{figure.name}</h1>
      <p className="sc-public-figure-role">
        <span className={`sc-public-figure-status is-${figure.status}`}>{figure.status === 'current' ? 'Aktualna funkcja' : 'Była funkcja'}</span>
        {figure.role_title}{figure.organisation && <> · {figure.organisation}</>}
      </p>
      <p className="sc-public-figure-links">
        <SourceLink href={figure.evidence_url}>Źródło funkcji</SourceLink>
        <SourceLink href={figure.official_profile_url}>Oficjalny profil</SourceLink>
        {figure.source_checked_at && <span>sprawdzono <time dateTime={figure.source_checked_at}>{formatDay(figure.source_checked_at)}</time></span>}
      </p>
      {x && (
        <p className="sc-public-figure-x">
          <span className="sc-public-figure-tag">KONTO X</span>
          <SourceLink href={x.url}>@{x.handle}</SourceLink>
          <span>potwierdzone przez redakcję i oficjalne API X</span>
          <SourceLink href={x.evidence_url}>link z oficjalnego profilu</SourceLink>
          {x.posts_collected > 0 && <span>{x.posts_collected} {plural(x.posts_collected, 'wpis', 'wpisy', 'wpisów')} w Bazie</span>}
        </p>
      )}
      <nav className="sc-public-figure-summary" aria-label="Sekcje profilu">
        <button type="button" onClick={() => onSelect('votes')}><span>Głosowania</span><strong>{figure.votes.available ? figure.votes.results.length : '—'}</strong></button>
        <button type="button" onClick={() => onSelect('relations')}><span>Potwierdzone relacje</span><strong>{organisations}</strong></button>
        <button type="button" onClick={() => onSelect('materials')}><span>Materiały w Bazie</span><strong>{materialsTotal ?? '…'}</strong></button>
      </nav>
      <p className="sc-public-figure-favnote">
        {ownerId
          ? 'Zapisywanie profili do ulubionych jest w trakcie udostępniania. Materiały z tego profilu możesz już zapisywać znakiem ♡.'
          : <>Zapisywanie materiałów do ulubionych wymaga konta. <button type="button" className="sc-public-figure-textbutton" onClick={() => setLoginOpen(true)}>Zaloguj się</button></>}
      </p>
      {loginOpen && <AccountDialog open={loginOpen} onClose={() => setLoginOpen(false)} />}
    </header>
  );
}

/* ——— Głosowania ——— */

function ShortTopic({ topic }: { topic: string }) {
  if (topic.length <= 110) return <>{topic}</>;
  return (
    <details className="sc-public-figure-topic">
      <summary>{topic.slice(0, 100).replace(/\s+\S*$/, '')}… <span className="sc-public-figure-more">pełny opis</span></summary>
      <p>{topic}</p>
    </details>
  );
}

function VoteRow({ vote }: { vote: PublicFigureVote }) {
  return (
    <tr>
      <td data-label="Data">{vote.date ? <time dateTime={vote.date}>{formatDay(vote.date)}</time> : 'brak daty'}</td>
      <th scope="row" data-label="Temat"><ShortTopic topic={vote.topic} /></th>
      <td data-label="Głos"><span className={`sc-public-figure-vote is-${vote.vote.toLowerCase()}`}>{voteLabel(vote.vote)}</span></td>
      <td data-label="Źródło"><SourceLink href={vote.article_url}>{vote.source || 'Oficjalny zapis'}</SourceLink></td>
    </tr>
  );
}

function VotesSection({ figure }: { figure: PublicFigureDetail }) {
  const votes = figure.votes;
  return (
    <section id="glosowania" className="sc-public-figure-section" aria-labelledby="pf-votes">
      <header>
        <h2 id="pf-votes">Głosowania w Sejmie</h2>
        {votes.available && <p>Ostatnie {votes.results.length} {plural(votes.results.length, 'głosowanie', 'głosowania', 'głosowań')} z oficjalnego zapisu · <SourceLink href={votes.source_url}>profil w Sejmie</SourceLink></p>}
      </header>
      {!votes.available ? (
        <Neutral>{votes.reason || 'Brak jeszcze ręcznie potwierdzonego połączenia z mandatem poselskim.'} Nie oznacza to, że głosowań nie było — redakcja łączy profil z oficjalnym wpisem ręcznie, nie po nazwisku.</Neutral>
      ) : votes.results.length === 0 ? (
        <Neutral>Oficjalny zapis nie zawiera jeszcze głosowań dla tego mandatu w naszej Bazie.</Neutral>
      ) : (
        <table className="sc-public-figure-votes">
          <caption className="sr-only">Głosowania: data, temat, głos i oficjalne źródło</caption>
          <thead><tr><th scope="col">Data</th><th scope="col">Temat</th><th scope="col">Głos</th><th scope="col">Źródło</th></tr></thead>
          <tbody>{votes.results.map((vote, index) => <VoteRow key={`${vote.article_url}-${index}`} vote={vote} />)}</tbody>
        </table>
      )}
      <p className="sc-public-figure-hint">Pokazujemy głos z oficjalnego zapisu, bez komentarza i bez oceny.</p>
    </section>
  );
}

/* ——— Wpisy z potwierdzonego konta X ——— */

function XPostsSection({ figure }: { figure: PublicFigureDetail }) {
  const posts = figure.x_posts;
  const shown = posts?.results.slice(0, 20) ?? [];
  return (
    <section id="wpisy-x" className="sc-public-figure-section" aria-labelledby="pf-x-posts">
      <header>
        <h2 id="pf-x-posts">Wpisy z potwierdzonego konta X</h2>
        <p>Pokazujemy wyłącznie materiały zapisane z konta potwierdzonego na oficjalnym profilu. To nie jest wyszukiwanie po nazwisku ani ocena treści.</p>
      </header>
      {!posts?.available ? (
        <Neutral>Brak potwierdzonego konta X lub wpisów pobranych do Bazy.</Neutral>
      ) : !shown.length ? (
        <Neutral>Potwierdzone konto nie ma jeszcze dostępnych wpisów w Bazie.</Neutral>
      ) : (
        <ul className="sc-public-figure-xposts">
          {shown.map(post => (
            <li key={post.id}>
              <p className="sc-public-figure-mat-meta"><span className="sc-public-figure-tag">POST X</span><time dateTime={post.published_at}>{formatDay(post.published_at)} · {hourFormat.format(new Date(post.published_at))}</time></p>
              <p className="sc-public-figure-xpost-text">{post.text.length > 320 ? `${post.text.slice(0, 320).replace(/\s+\S*$/, '')}…` : post.text}</p>
              <p className="sc-public-figure-mat-links"><SourceLink href={post.url}>Otwórz wpis</SourceLink></p>
            </li>
          ))}
        </ul>
      )}
      {posts?.results && posts.results.length > shown.length && <p className="sc-public-figure-hint">Pokazano 20 najnowszych wpisów z {posts.results.length} dostępnych.</p>}
    </section>
  );
}

/* ——— Relacje z podmiotami ——— */

function OrganisationRow({ relation }: { relation: PublicFigureOrganisation }) {
  return (
    <li className="sc-public-figure-org">
      <div className="sc-public-figure-org-main">
        <SourceLink href={relation.official_register_url}><strong>{relation.name}</strong></SourceLink>
        <span className="sc-public-figure-verified"><span aria-hidden="true">✓</span> potwierdzone w źródle publicznym</span>
      </div>
      <dl>
        <div><dt>Publiczna rola</dt><dd>{relation.public_role}</dd></div>
        <div><dt>Relacja</dt><dd><span className={`sc-public-figure-relation is-${relation.relation_status}`}>{relation.relation_status === 'current' ? 'obecna' : 'historyczna'}</span></dd></div>
        <div><dt>Źródło</dt><dd className="sc-public-figure-org-links"><SourceLink href={relation.evidence_url}>Dowód publiczny</SourceLink></dd></div>
      </dl>
    </li>
  );
}

function OrganisationsSection({ figure }: { figure: PublicFigureDetail }) {
  const kinds = ORGANISATION_KIND_ORDER.filter(kind => kind !== 'other' || figure.organisations.some(item => item.kind === 'other'));
  return (
    <section id="relacje" className="sc-public-figure-section" aria-labelledby="pf-orgs">
      <header>
        <h2 id="pf-orgs">Relacje z podmiotami</h2>
        <p>Wyłącznie relacje potwierdzone przez redakcję w publicznym źródle. Relacja opisuje publiczną funkcję, nie ocenia osoby.</p>
      </header>
      {kinds.map(kind => {
        const rows = figure.organisations.filter(item => item.kind === kind);
        return (
          <section key={kind} className="sc-public-figure-group" aria-labelledby={`pf-org-${kind}`}>
            <h3 id={`pf-org-${kind}`}>{ORGANISATION_KIND_LABELS[kind].plural} <span>{rows.length}</span></h3>
            {rows.length ? (
              <ul>{rows.map(relation => <OrganisationRow key={`${relation.id}-${relation.public_role}-${relation.relation_status}`} relation={relation} />)}</ul>
            ) : (
              <Neutral>Brak jeszcze ręcznie potwierdzonego połączenia. Nie oznacza to braku relacji — pokazujemy tylko wpisy sprawdzone w publicznym źródle.</Neutral>
            )}
          </section>
        );
      })}
    </section>
  );
}

/* ——— Materiały z Bazy ——— */

type MaterialFilters = { group: MaterialGroupKey | ''; source: number | ''; topic: string; order: 'desc' | 'asc' };

function toFigureMaterial(article: Article): FigureMaterial {
  return { id: article.id, title: article.title, url: article.url, category: article.category, published_date: article.published_date, source_id: article.source.id, source_name: article.source.name, topics: article.tags ?? [] };
}

function MaterialsView({ name, counts, items, total, status, filters, setFilters, sources, topics, hasMore, loadMore, loadingMore }: {
  name: string; counts: Partial<Record<MaterialGroupKey, number>>; items: FigureMaterial[]; total: number | null;
  status: 'loading' | 'error' | 'unavailable' | 'ready'; filters: MaterialFilters; setFilters: (next: MaterialFilters) => void;
  sources: Array<{ id: number; name: string }>; topics: CategoryOption[]; hasMore: boolean; loadMore: () => void; loadingMore: boolean;
}) {
  const uid = useId();
  const { ownerId } = useOwnerId();
  const sorted = [...items].sort((a, b) => {
    const left = a.published_date ? new Date(a.published_date).getTime() : 0;
    const right = b.published_date ? new Date(b.published_date).getTime() : 0;
    return filters.order === 'desc' ? right - left : left - right;
  });
  const days: Array<{ key: string; label: string; items: FigureMaterial[] }> = [];
  for (const item of sorted) {
    const key = item.published_date ? dayKeyFormat.format(new Date(item.published_date)) : 'brak';
    const last = days[days.length - 1];
    if (last?.key === key) last.items.push(item);
    else days.push({ key, label: item.published_date ? dayFormat.format(new Date(item.published_date)) : 'Data publikacji nieustalona', items: [item] });
  }
  const set = (patch: Partial<MaterialFilters>) => setFilters({ ...filters, ...patch });

  return (
    <section id="materialy" className="sc-public-figure-section" aria-labelledby="pf-materials">
      <header>
        <h2 id="pf-materials">Materiały w Bazie</h2>
        <p>Wyniki wyszukiwania hasła „{name}” w Bazie. To wyszukiwanie tekstowe, nie potwierdzone powiązanie — materiał może dotyczyć innej osoby o tym samym nazwisku.</p>
      </header>

      <div className="sc-public-figure-types" role="group" aria-label="Typ materiału — kliknij, aby filtrować">
        <button type="button" aria-pressed={filters.group === ''} onClick={() => set({ group: '' })}><span>Wszystkie</span><strong>{total ?? '…'}</strong></button>
        {MATERIAL_GROUPS.map(group => (
          <button key={group.key} type="button" aria-pressed={filters.group === group.key} onClick={() => set({ group: filters.group === group.key ? '' : group.key })}>
            <span>{group.label}</span><strong>{counts[group.key] ?? '…'}</strong>
          </button>
        ))}
      </div>

      <div className="sc-public-figure-filters">
        <label htmlFor={`${uid}-source`}>Źródło
          <select id={`${uid}-source`} value={filters.source} onChange={event => set({ source: event.target.value ? Number(event.target.value) : '' })}>
            <option value="">Wszystkie źródła</option>
            {sources.map(source => <option key={source.id} value={source.id}>{source.name}</option>)}
          </select>
        </label>
        <label htmlFor={`${uid}-topic`}>Kategoria
          <select id={`${uid}-topic`} value={filters.topic} onChange={event => set({ topic: event.target.value })}>
            <option value="">Wszystkie kategorie</option>
            {topics.map(topic => <option key={topic.value} value={topic.value}>{topic.label}</option>)}
          </select>
        </label>
        <label htmlFor={`${uid}-order`}>Kolejność
          <select id={`${uid}-order`} value={filters.order} onChange={event => set({ order: event.target.value as MaterialFilters['order'] })}>
            <option value="desc">Od najnowszych</option>
            <option value="asc">Od najstarszych</option>
          </select>
        </label>
      </div>

      {status === 'loading' && <p role="status" className="sc-public-figure-hint">Szukam materiałów w Bazie…</p>}
      {status === 'unavailable' && <Neutral>Baza nie jest teraz dostępna. Spróbuj ponownie później.</Neutral>}
      {status === 'error' && <p role="alert" className="sc-public-figure-hint">Nie udało się pobrać materiałów.</p>}
      {status === 'ready' && !items.length && <Neutral>Brak materiałów dla wybranych filtrów.</Neutral>}

      {days.length > 0 && (
        <ol className="sc-public-figure-days" aria-label="Materiały według dni publikacji">
          {days.map(day => (
            <li key={day.key}>
              <h3><time dateTime={day.key}>{day.label}</time> <span>{day.items.length}</span></h3>
              <ul>
                {day.items.map(item => {
                  const group = groupOfCategory(item.category);
                  return (
                    <li key={item.id} className="sc-public-figure-mat">
                      <p className="sc-public-figure-mat-meta">
                        <span className="sc-public-figure-tag">{group ? GROUP_TAGS[group] : 'INNE'}</span>
                        {item.published_date && <time dateTime={item.published_date}>{hourFormat.format(new Date(item.published_date))}</time>}
                        <span>{item.source_name}</span>
                      </p>
                      <Link href={`/material/${item.id}`} className="sc-public-figure-mat-title">{item.title}</Link>
                      <p className="sc-public-figure-mat-links">
                        <Link href={`/material/${item.id}`}>Materiał i kontekst</Link>
                        <SourceLink href={item.url}>Oryginał</SourceLink>
                      </p>
                      {ownerId && <span className="sc-public-figure-mat-fav"><ArticleFavoriteButton articleId={item.id} title={item.title} compact /></span>}
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ol>
      )}
      {hasMore && <Button type="button" variant="secondary" loading={loadingMore} disabled={loadingMore} onClick={loadMore}>Wcześniejsze materiały ↓</Button>}
      {filters.order === 'asc' && hasMore && <p className="sc-public-figure-hint">Kolejność od najstarszych dotyczy wczytanych materiałów.</p>}
    </section>
  );
}

function LiveMaterials({ name }: { name: string }) {
  const [filters, setFilters] = useState<MaterialFilters>({ group: '', source: '', topic: '', order: 'desc' });
  const config = useQuery({ queryKey: ['mvp-portal-config'], queryFn: getPortalConfig, staleTime: 60_000 });
  const categories = filters.group ? [...MATERIAL_GROUPS.find(group => group.key === filters.group)!.categories] : ALL_GROUP_CATEGORIES;
  const base = { query: name, match: 'words' as const, topics: filters.topic ? [filters.topic] : [], sources: filters.source ? [filters.source] : [] };
  const feed = useInfiniteQuery({
    queryKey: ['figure-materials', name, filters.group, filters.source, filters.topic],
    initialPageParam: 1,
    queryFn: ({ pageParam }) => getNewsFeed({ ...base, categories, page: pageParam, pageSize: 20 }),
    getNextPageParam: last => last.next_page ?? undefined,
  });
  const countQueries = useQueries({
    queries: MATERIAL_GROUPS.map(group => ({
      queryKey: ['figure-material-count', name, group.key, filters.source, filters.topic],
      queryFn: () => getNewsFeed({ ...base, categories: [...group.categories], pageSize: 1 }),
      staleTime: 60_000,
    })),
  });
  const counts = Object.fromEntries(MATERIAL_GROUPS.map((group, index) => [group.key, countQueries[index].data?.total])) as Partial<Record<MaterialGroupKey, number>>;
  const total = countQueries.every(query => query.isSuccess) ? countQueries.reduce((sum, query) => sum + (query.data?.total ?? 0), 0) : null;
  const items = useMemo(() => (feed.data?.pages ?? []).flatMap(page => page.results).map(toFigureMaterial), [feed.data]);
  const status = feed.isPending ? 'loading' : feed.isError ? 'error' : 'ready';
  return <MaterialsView name={name} counts={counts} items={items} total={total} status={status} filters={filters} setFilters={setFilters}
    sources={(config.data?.sources ?? []).map(source => ({ id: source.id, name: source.name }))} topics={config.data?.topics ?? []}
    hasMore={Boolean(feed.hasNextPage)} loadMore={() => feed.fetchNextPage()} loadingMore={feed.isFetchingNextPage} />;
}

/** Łączna liczba materiałów do nagłówka — ta sama pamięć podręczna co liczniki sekcji. */
function useMaterialsTotal(name: string) {
  const queries = useQueries({
    queries: MATERIAL_GROUPS.map(group => ({
      queryKey: ['figure-material-count', name, group.key, '', ''],
      queryFn: () => getNewsFeed({ query: name, match: 'words', categories: [...group.categories], pageSize: 1 }),
      staleTime: 60_000,
    })),
  });
  return queries.every(query => query.isSuccess) ? queries.reduce((sum, query) => sum + (query.data?.total ?? 0), 0) : null;
}

/* ——— Profil ——— */

export function PublicFigureProfile({ figure, titleId = 'pf-title' }: { figure: PublicFigureDetail; titleId?: string }) {
  const materialsTotal = useMaterialsTotal(figure.name);
  const [tab, setTab] = useState<'votes' | 'relations' | 'materials' | 'x'>('votes');
  const tabs = [
    { id: 'votes' as const, label: 'Głosowania' },
    { id: 'relations' as const, label: 'Relacje' },
    { id: 'materials' as const, label: 'Materiały' },
    { id: 'x' as const, label: 'Wpisy X' },
  ];
  return (
    <article className="sc-public-figure" aria-labelledby={titleId}>
      <FigureHeader figure={figure} titleId={titleId} materialsTotal={materialsTotal} onSelect={setTab} />
      <nav className="sc-public-figure-tabs" role="tablist" aria-label="Dane profilu">
        {tabs.map(item => <button key={item.id} id={`pf-tab-${item.id}`} type="button" role="tab" aria-selected={tab === item.id} aria-controls={`pf-panel-${item.id}`} onClick={() => setTab(item.id)}>{tab === item.id && <MorphIndicator id="public-figure-tabs" active variant="underline" />}{item.label}</button>)}
      </nav>
      <div id={`pf-panel-${tab}`} role="tabpanel" aria-labelledby={`pf-tab-${tab}`} tabIndex={0}>
        {tab === 'votes' && <VotesSection figure={figure} />}
        {tab === 'x' && <XPostsSection figure={figure} />}
        {tab === 'relations' && <OrganisationsSection figure={figure} />}
        {tab === 'materials' && <LiveMaterials name={figure.name} />}
      </div>
      <p className="sc-public-figure-disclaimer">
        Profil pokazuje wyłącznie dane publiczne: funkcję, oficjalne głosowania i potwierdzone relacje. Nie zawiera adresów, numerów PESEL, dat urodzenia ani danych rodzinnych. Nie wystawiamy ocen osób ani automatycznych wniosków.
      </p>
    </article>
  );
}
