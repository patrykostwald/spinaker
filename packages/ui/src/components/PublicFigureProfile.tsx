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
import { DEMO_FIGURE_MATERIALS, DEMO_FIGURE_SOURCES, DEMO_FIGURE_TOPICS, type FigureMaterial } from '../lib/publicFigureDemo';
import type { Article } from '../types';
import { AccountDialog } from './AccountDialog';
import { ArticleFavoriteButton } from './ArticleFavoriteButton';
import { voteLabel } from './VotingDetails';

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

/** Link zewnętrzny tylko dla adresów http(s). W demo — tekst oznaczony jako nieaktywny. */
function SourceLink({ href, demo, children }: { href: string | null | undefined; demo?: boolean; children: ReactNode }) {
  if (!isHttp(href)) return null;
  if (demo) return <span className="mvp-pf-inactive" title="Demo — link nieaktywny">{children} <small>(demo)</small></span>;
  return <a href={href} target="_blank" rel="noopener noreferrer">{children} <span aria-hidden="true">↗</span><span className="sr-only"> (otwiera się w nowej karcie)</span></a>;
}

function Neutral({ children }: { children: ReactNode }) {
  return <p className="mvp-pf-neutral">{children}</p>;
}

/* ——— Nagłówek profilu ——— */

function FigureHeader({ figure, demo, titleId, materialsTotal }: { figure: PublicFigureDetail; demo?: boolean; titleId: string; materialsTotal: number | null }) {
  const { ownerId } = useOwnerId();
  const [loginOpen, setLoginOpen] = useState(false);
  const x = verifiedXAccount(figure);
  const organisations = figure.organisations.length;
  return (
    <header className="mvp-pf-head">
      <p className="mvp-pf-kicker">OSOBA PUBLICZNA · {ROLE_CATEGORY_LABELS[figure.role_category] ?? 'rola publiczna'}</p>
      <h1 id={titleId} tabIndex={-1}>{figure.name}</h1>
      <p className="mvp-pf-role">
        <span className={`mvp-pf-status is-${figure.status}`}>{figure.status === 'current' ? 'Aktualna funkcja' : 'Była funkcja'}</span>
        {figure.role_title}{figure.organisation && <> · {figure.organisation}</>}
      </p>
      <p className="mvp-pf-links">
        <SourceLink href={figure.evidence_url} demo={demo}>Źródło funkcji</SourceLink>
        <SourceLink href={figure.official_profile_url} demo={demo}>Oficjalny profil</SourceLink>
        {figure.source_checked_at && <span>sprawdzono <time dateTime={figure.source_checked_at}>{formatDay(figure.source_checked_at)}</time></span>}
      </p>
      {x && (
        <p className="mvp-pf-x">
          <span className="mvp-pf-tag">KONTO X</span>
          <SourceLink href={x.url} demo={demo}>@{x.handle}</SourceLink>
          <span>potwierdzone przez redakcję i oficjalne API X</span>
          <SourceLink href={x.evidence_url} demo={demo}>link z oficjalnego profilu</SourceLink>
          {x.posts_collected > 0 && <span>{x.posts_collected} {plural(x.posts_collected, 'wpis', 'wpisy', 'wpisów')} w Bazie</span>}
        </p>
      )}
      <nav className="mvp-pf-summary" aria-label="Sekcje profilu">
        <a href="#glosowania"><span>Głosowania</span><strong>{figure.votes.available ? figure.votes.results.length : '—'}</strong></a>
        <a href="#relacje"><span>Potwierdzone relacje</span><strong>{organisations}</strong></a>
        <a href="#materialy"><span>Materiały w Bazie</span><strong>{materialsTotal ?? '…'}</strong></a>
      </nav>
      <p className="mvp-pf-favnote">
        {ownerId
          ? 'Zapisywanie profili do ulubionych jest w trakcie udostępniania. Materiały z tego profilu możesz już zapisywać znakiem ♡.'
          : <>Zapisywanie materiałów do ulubionych wymaga konta. <button type="button" className="mvp-pf-textbutton" onClick={() => setLoginOpen(true)}>Zaloguj się</button></>}
      </p>
      {loginOpen && <AccountDialog open={loginOpen} onClose={() => setLoginOpen(false)} />}
    </header>
  );
}

/* ——— Głosowania ——— */

function ShortTopic({ topic }: { topic: string }) {
  if (topic.length <= 110) return <>{topic}</>;
  return (
    <details className="mvp-pf-topic">
      <summary>{topic.slice(0, 100).replace(/\s+\S*$/, '')}… <span className="mvp-pf-more">pełny opis</span></summary>
      <p>{topic}</p>
    </details>
  );
}

function VoteRow({ vote, demo }: { vote: PublicFigureVote; demo?: boolean }) {
  return (
    <tr>
      <td data-label="Data">{vote.date ? <time dateTime={vote.date}>{formatDay(vote.date)}</time> : 'brak daty'}</td>
      <th scope="row" data-label="Temat"><ShortTopic topic={vote.topic} /></th>
      <td data-label="Głos"><span className={`mvp-pf-vote is-${vote.vote.toLowerCase()}`}>{voteLabel(vote.vote)}</span></td>
      <td data-label="Źródło"><SourceLink href={vote.article_url} demo={demo}>{vote.source || 'Oficjalny zapis'}</SourceLink></td>
    </tr>
  );
}

function VotesSection({ figure, demo }: { figure: PublicFigureDetail; demo?: boolean }) {
  const votes = figure.votes;
  return (
    <section id="glosowania" className="mvp-pf-section" aria-labelledby="pf-votes">
      <header>
        <h2 id="pf-votes">Głosowania w Sejmie</h2>
        {votes.available && <p>Ostatnie {votes.results.length} {plural(votes.results.length, 'głosowanie', 'głosowania', 'głosowań')} z oficjalnego zapisu · <SourceLink href={votes.source_url} demo={demo}>profil w Sejmie</SourceLink></p>}
      </header>
      {!votes.available ? (
        <Neutral>{votes.reason || 'Brak jeszcze ręcznie potwierdzonego połączenia z mandatem poselskim.'} Nie oznacza to, że głosowań nie było — redakcja łączy profil z oficjalnym wpisem ręcznie, nie po nazwisku.</Neutral>
      ) : votes.results.length === 0 ? (
        <Neutral>Oficjalny zapis nie zawiera jeszcze głosowań dla tego mandatu w naszej Bazie.</Neutral>
      ) : (
        <table className="mvp-pf-votes">
          <caption className="sr-only">Głosowania: data, temat, głos i oficjalne źródło</caption>
          <thead><tr><th scope="col">Data</th><th scope="col">Temat</th><th scope="col">Głos</th><th scope="col">Źródło</th></tr></thead>
          <tbody>{votes.results.map((vote, index) => <VoteRow key={`${vote.article_url}-${index}`} vote={vote} demo={demo} />)}</tbody>
        </table>
      )}
      <p className="mvp-pf-hint">Pokazujemy głos z oficjalnego zapisu, bez komentarza i bez oceny.</p>
    </section>
  );
}

/* ——— Relacje z podmiotami ——— */

function OrganisationRow({ relation, demo }: { relation: PublicFigureOrganisation; demo?: boolean }) {
  return (
    <li className="mvp-pf-org">
      <div className="mvp-pf-org-main">
        <SourceLink href={relation.official_register_url} demo={demo}><strong>{relation.name}</strong></SourceLink>
        <span className="mvp-pf-verified"><span aria-hidden="true">✓</span> potwierdzone w źródle publicznym</span>
      </div>
      <dl>
        <div><dt>Publiczna rola</dt><dd>{relation.public_role}</dd></div>
        <div><dt>Relacja</dt><dd><span className={`mvp-pf-relation is-${relation.relation_status}`}>{relation.relation_status === 'current' ? 'obecna' : 'historyczna'}</span></dd></div>
        <div><dt>Źródło</dt><dd className="mvp-pf-org-links"><SourceLink href={relation.evidence_url} demo={demo}>Dowód publiczny</SourceLink></dd></div>
      </dl>
    </li>
  );
}

function OrganisationsSection({ figure, demo }: { figure: PublicFigureDetail; demo?: boolean }) {
  const kinds = ORGANISATION_KIND_ORDER.filter(kind => kind !== 'other' || figure.organisations.some(item => item.kind === 'other'));
  return (
    <section id="relacje" className="mvp-pf-section" aria-labelledby="pf-orgs">
      <header>
        <h2 id="pf-orgs">Relacje z podmiotami</h2>
        <p>Wyłącznie relacje potwierdzone przez redakcję w publicznym źródle. Relacja opisuje publiczną funkcję, nie ocenia osoby.</p>
      </header>
      {kinds.map(kind => {
        const rows = figure.organisations.filter(item => item.kind === kind);
        return (
          <section key={kind} className="mvp-pf-group" aria-labelledby={`pf-org-${kind}`}>
            <h3 id={`pf-org-${kind}`}>{ORGANISATION_KIND_LABELS[kind].plural} <span>{rows.length}</span></h3>
            {rows.length ? (
              <ul>{rows.map(relation => <OrganisationRow key={`${relation.id}-${relation.public_role}-${relation.relation_status}`} relation={relation} demo={demo} />)}</ul>
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
  return { id: article.id, title: article.title, url: article.url, category: article.category, published_date: article.published_date, source_id: article.source.id, source_name: article.source.name, topics: article.tags };
}

function MaterialsView({ name, demo, counts, items, total, status, filters, setFilters, sources, topics, hasMore, loadMore, loadingMore }: {
  name: string; demo?: boolean; counts: Partial<Record<MaterialGroupKey, number>>; items: FigureMaterial[]; total: number | null;
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
    <section id="materialy" className="mvp-pf-section" aria-labelledby="pf-materials">
      <header>
        <h2 id="pf-materials">Materiały w Bazie</h2>
        <p>Wyniki wyszukiwania hasła „{name}” w Bazie. To wyszukiwanie tekstowe, nie potwierdzone powiązanie — materiał może dotyczyć innej osoby o tym samym nazwisku.</p>
      </header>

      <div className="mvp-pf-types" role="group" aria-label="Typ materiału — kliknij, aby filtrować">
        <button type="button" aria-pressed={filters.group === ''} onClick={() => set({ group: '' })}><span>Wszystkie</span><strong>{total ?? '…'}</strong></button>
        {MATERIAL_GROUPS.map(group => (
          <button key={group.key} type="button" aria-pressed={filters.group === group.key} onClick={() => set({ group: filters.group === group.key ? '' : group.key })}>
            <span>{group.label}</span><strong>{counts[group.key] ?? '…'}</strong>
          </button>
        ))}
      </div>

      <div className="mvp-pf-filters">
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

      {status === 'loading' && <p role="status" className="mvp-pf-hint">Szukam materiałów w Bazie…</p>}
      {status === 'unavailable' && <Neutral>Baza nie jest teraz dostępna. Spróbuj ponownie później.</Neutral>}
      {status === 'error' && <p role="alert" className="mvp-pf-hint">Nie udało się pobrać materiałów.</p>}
      {status === 'ready' && !items.length && <Neutral>Brak materiałów dla wybranych filtrów.</Neutral>}

      {days.length > 0 && (
        <ol className="mvp-pf-days" aria-label="Materiały według dni publikacji">
          {days.map(day => (
            <li key={day.key}>
              <h3><time dateTime={day.key}>{day.label}</time> <span>{day.items.length}</span></h3>
              <ul>
                {day.items.map(item => {
                  const group = groupOfCategory(item.category);
                  return (
                    <li key={item.id} className="mvp-pf-mat">
                      <p className="mvp-pf-mat-meta">
                        <span className="mvp-pf-tag">{group ? GROUP_TAGS[group] : 'INNE'}</span>
                        {item.published_date && <time dateTime={item.published_date}>{hourFormat.format(new Date(item.published_date))}</time>}
                        <span>{item.source_name}</span>
                      </p>
                      {demo ? <strong className="mvp-pf-mat-title">{item.title}</strong> : <Link href={`/material/${item.id}`} className="mvp-pf-mat-title">{item.title}</Link>}
                      <p className="mvp-pf-mat-links">
                        {demo ? <span className="mvp-pf-inactive">Materiał i kontekst <small>(demo)</small></span> : <Link href={`/material/${item.id}`}>Materiał i kontekst</Link>}
                        <SourceLink href={item.url} demo={demo}>Oryginał</SourceLink>
                      </p>
                      {!demo && ownerId && <span className="mvp-pf-mat-fav"><ArticleFavoriteButton articleId={item.id} title={item.title} compact /></span>}
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ol>
      )}
      {hasMore && <button type="button" className="load-news-button" disabled={loadingMore} onClick={loadMore}>{loadingMore ? 'Ładuję…' : 'Wcześniejsze materiały ↓'}</button>}
      {filters.order === 'asc' && hasMore && <p className="mvp-pf-hint">Kolejność od najstarszych dotyczy wczytanych materiałów.</p>}
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

function DemoMaterials({ name }: { name: string }) {
  const [filters, setFilters] = useState<MaterialFilters>({ group: '', source: '', topic: '', order: 'desc' });
  const scoped = DEMO_FIGURE_MATERIALS.filter(item => (!filters.source || item.source_id === filters.source) && (!filters.topic || item.topics?.includes(filters.topic)));
  const counts = Object.fromEntries(MATERIAL_GROUPS.map(group => [group.key, scoped.filter(item => groupOfCategory(item.category) === group.key).length])) as Partial<Record<MaterialGroupKey, number>>;
  const items = scoped.filter(item => !filters.group || groupOfCategory(item.category) === filters.group);
  return <MaterialsView name={name} demo counts={counts} items={items} total={scoped.length} status="ready" filters={filters} setFilters={setFilters}
    sources={DEMO_FIGURE_SOURCES} topics={DEMO_FIGURE_TOPICS} hasMore={false} loadMore={() => undefined} loadingMore={false} />;
}

/** Łączna liczba materiałów do nagłówka — ta sama pamięć podręczna co liczniki sekcji. */
function useMaterialsTotal(name: string, demo?: boolean) {
  const queries = useQueries({
    queries: MATERIAL_GROUPS.map(group => ({
      queryKey: ['figure-material-count', name, group.key, '', ''],
      queryFn: () => getNewsFeed({ query: name, match: 'words', categories: [...group.categories], pageSize: 1 }),
      staleTime: 60_000,
      enabled: !demo,
    })),
  });
  if (demo) return DEMO_FIGURE_MATERIALS.length;
  return queries.every(query => query.isSuccess) ? queries.reduce((sum, query) => sum + (query.data?.total ?? 0), 0) : null;
}

/* ——— Profil ——— */

export function PublicFigureProfile({ figure, demo = false, titleId = 'pf-title' }: { figure: PublicFigureDetail; demo?: boolean; titleId?: string }) {
  const materialsTotal = useMaterialsTotal(figure.name, demo);
  return (
    <article className="mvp-pf" aria-labelledby={titleId}>
      {demo && (
        <p className="mvp-pf-demo" role="note">
          <strong>DEMO</strong>
          <span>Osoba, podmioty, głosowania i materiały są fikcyjne. Kształt danych odpowiada odpowiedzi GET /api/public-figures/:id/. Materiały demonstracyjne są lokalne — w prawdziwym profilu pochodzą z wyszukiwania w Bazie.</span>
        </p>
      )}
      <FigureHeader figure={figure} demo={demo} titleId={titleId} materialsTotal={materialsTotal} />
      <VotesSection figure={figure} demo={demo} />
      <OrganisationsSection figure={figure} demo={demo} />
      {demo ? <DemoMaterials name={figure.name} /> : <LiveMaterials name={figure.name} />}
      <p className="mvp-pf-disclaimer">
        Profil pokazuje wyłącznie dane publiczne: funkcję, oficjalne głosowania i potwierdzone relacje. Nie zawiera adresów, numerów PESEL, dat urodzenia ani danych rodzinnych. Nie wystawiamy ocen osób ani automatycznych wniosków.
      </p>
    </article>
  );
}
