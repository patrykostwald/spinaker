"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Button } from "../../kit";
import { getCommunityThread, getCommunityThreads, type ThreadElement } from "../../lib/community";
import { categoryLabel, formatDatePl, formatDateTimePl } from "../../lib/utils";

import { AccountDataState } from '../AccountPhase2';
import { useFeature } from '../../lib/features';
import { isUnavailable } from '../../lib/personal';
import { ThreadStrip } from './ThreadStrip';
import { ClampedText } from './SocialPrimitives';
import { useAccount } from '../../lib/account';

/** Jeden element nitki: materiał z Bazy (z linkiem do kontekstu) albo link spoza Bazy - wyraźnie oznaczony. */
export function ElementRow({ element, index }: { element: ThreadElement; index: number }) {
  if (element.kind === 'link' && element.hidden) return <li className="sc-thread-el">Link ukryty przez zespół po zgłoszeniu.</li>;
  return (
    <li className="sc-thread-step">
      {index > 0 && <div className="sc-thread-connector">
        <span className="sc-thread-connector__arrow" aria-hidden="true">↓</span>
        {element.link_note && <p><span className="sr-only">Powiązanie z poprzednim: </span>{element.link_note}</p>}
      </div>}
      <div className="sc-thread-el" data-kind={element.kind}>
      <span className="sc-thread-el__index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
      <div className="sc-thread-el__body">
        <p className="sc-thread-el__meta">
          {element.kind === "article" ? <>
            <span className="sc-thread-el__tag">{categoryLabel(element.category)}</span>
            {element.source_name}{element.published_date ? ` · ${formatDatePl(element.published_date)}` : ""}
          </> : <>
            <span className="sc-thread-el__tag sc-thread-el__tag--outside" title="Materiał spoza naszej Bazy - dodany przez czytelnika">spoza Bazy</span>
            {element.domain}{element.title_origin === "reader" ? " · tytuł przepisany przez autora nitki" : ""}
          </>}
        </p>
        <p className="sc-thread-el__title">
          <a href={element.url} title={element.title} target="_blank" rel="noopener noreferrer">{element.title} ↗</a>
        </p>
        {element.kind === "article" && <p className="sc-thread-el__links"><Link href={`/material/${element.id}`}>Kontekst materiału</Link></p>}
        {element.note && <p className="sc-thread-el__note">{element.note}</p>}
      </div>
      </div>
    </li>
  );
}

export function CommunityThreadsPage({ context = {} }: { context?: { article_id?: number; figure_id?: number; url?: string } }) {
  const account = useAccount();
  const ACCOUNTS_ENABLED = useFeature('ACCOUNTS_ENABLED');
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [sort, setSort] = useState<'new' | 'best' | 'comments'>('best');
  const contextActive = Boolean(context.article_id || context.figure_id || context.url);
  const query = useInfiniteQuery({
    queryKey: ["community-threads", term, sort, context],
    queryFn: ({ pageParam }) => getCommunityThreads(pageParam, term, '', { sort, ...context }),
    retry: false,
    initialPageParam: 1,
    getNextPageParam: last => last.next_page ?? undefined,
  });
  const threads = query.data?.pages.flatMap(page => contextActive && !page.context_filtered ? [] : page.results) ?? [];
  return (
    <div className="sc-community sc-f2">
      <header className="sc-community__head">
        <p className="sc-clinic-kicker">Nitki</p>
        <h1>Diagnozy i materiały ułożone w nitki</h1>
        <p className="sc-clinic-lead">
          Nitka kontekstowa to jeden materiał na początku, a za nim - w kolejności - to, co go dopełnia, potwierdza albo podważa. Każdy może ułożyć
          swoją z materiałów z naszej Bazy albo dodać źródło przez link.
        </p>
        <div className="sc-community__actions">
          {ACCOUNTS_ENABLED && <Button href="/konto/nitki/nowa" variant="primary">Ułóż swoją nitkę</Button>}
          <form role="search" className="sc-community__search" onSubmit={(event: FormEvent) => { event.preventDefault(); setTerm(search.trim()); }}>
            <input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Szukaj w tytułach nitek…" aria-label="Szukaj nitek" />
            <Button type="submit" variant="quiet" size="sm">Szukaj</Button>
          </form>
        </div>
        <div className="sc-f2-filters"><label>Kolejność<select value={sort} onChange={event => setSort(event.target.value as 'new' | 'best' | 'comments')}><option value="best">Najlepiej oceniane</option><option value="new">Najnowsze nitki</option><option value="comments">Najnowsze komentarze</option></select></label>
        </div>
        {sort === 'best' && <p>Według liczby opinii „Zgadzam się”; przy remisie od najnowszej publikacji.</p>}
        {contextActive && <p>Pokazujemy nitki zawierające wybrany materiał lub potwierdzone powiązanie. <Link href="/nitki">Pokaż wszystkie</Link></p>}
      </header>
      <AccountDataState query={query} empty="Publiczne nitki będą dostępne wkrótce." />
      {query.isSuccess && !threads.length && (
        <p className="sc-clinic-empty">{term ? `Brak nitek dla „${term}”.` : "Nie ma jeszcze publicznych nitek. Ułóż pierwszą - wystarczą dwa materiały."}</p>
      )}
      {threads.length > 0 && <ul className="sc-community__list">{threads.map(thread => <li key={thread.id}><ThreadStrip thread={thread} /></li>)}</ul>}
      {query.hasNextPage && <Button variant="quiet" loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>Pokaż więcej</Button>}
      {ACCOUNTS_ENABLED && account.data?.authenticated && <p><Link href="/konto/nitki/nowa">Ułóż swoją nitkę: wybierz diagnozę i dodaj kontekst</Link></p>}
      <aside className="sc-clinic-roadmap">
        Link prowadzi do oryginału. Dla publicznych wpisów z X pokazujemy także krótki tekst, autora i datę. Nitki możesz zgłosić do moderacji.
      </aside>
    </div>
  );
}

export function CommunityThreadPage({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["community-thread", id], queryFn: () => getCommunityThread(id), retry: false });
  if (query.isLoading) return <div className="sc-community"><div className="sc-social-skeleton" aria-label="Ładowanie nitki" /></div>;
  if (query.isError && !isUnavailable(query.error)) return <div className="sc-community"><AccountDataState query={query} /></div>;
  if (!query.data) return <div className="sc-community"><p className="sc-clinic-empty">Nie znaleziono nitki - mogła zostać usunięta albo nie jest publiczna. <Link href="/nitki">Wszystkie nitki</Link></p></div>;
  const thread = query.data;
  return (
    <div className="sc-community sc-community--detail sc-f2">
      <p><Link href="/nitki" className="sc-spin-detail__back">← Nitki czytelników</Link></p>
      <header className="sc-community__head">
        <p className="sc-clinic-kicker">{thread.is_ai ? 'Dr. Spin (AI)' : <>Nitka czytelnika · <Link href={`/profile/${encodeURIComponent(thread.author)}`}>{thread.display_name || `@${thread.author}`}</Link> {thread.x_profile && <a href={thread.x_profile} target="_blank" rel="noopener noreferrer" aria-label="Połączone konto X">𝕏</a>}</>}</p>
        <ClampedText><h1>{thread.title}</h1></ClampedText>
        {thread.description && <ClampedText>{thread.description}</ClampedText>}
        <p className="sc-community-card__meta">
          {thread.published_at ? `Opublikowana ${formatDateTimePl(thread.published_at)}` : ""} · {thread.items_count} elementów · kolejność ustalił autor
        </p>
      </header>
      <ThreadStrip thread={thread} items={thread.items} full />
    </div>
  );
}
