"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Button } from "../../kit";
import { Dialog } from "../Dialog";
import { REPORT_REASONS, getCommunityThread, getCommunityThreads, reportCommunityThread, type CommunityThreadSummary, type ThreadElement } from "../../lib/community";
import { useAccount } from "../../lib/account";
import { categoryLabel, formatDatePl, formatDateTimePl } from "../../lib/utils";
import { OpinionsPanel } from "../OpinionsPanel";

/** Jeden element nitki: materiał z Bazy (z linkiem do kontekstu) albo link spoza Bazy — wyraźnie oznaczony. */
export function ElementRow({ element, index }: { element: ThreadElement; index: number }) {
  return (
    <li className="sc-thread-el" data-kind={element.kind}>
      <span className="sc-thread-el__index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
      <div className="sc-thread-el__body">
        <p className="sc-thread-el__meta">
          {element.kind === "article" ? <>
            <span className="sc-thread-el__tag">{categoryLabel(element.category)}</span>
            {element.source_name}{element.published_date ? ` · ${formatDatePl(element.published_date)}` : ""}
          </> : <>
            <span className="sc-thread-el__tag sc-thread-el__tag--outside" title="Materiał spoza naszej Bazy — dodany przez czytelnika">spoza Bazy</span>
            {element.domain}{element.title_origin === "reader" ? " · tytuł przepisany przez autora nitki" : ""}
          </>}
        </p>
        <p className="sc-thread-el__title">
          <a href={element.url} target="_blank" rel="noopener noreferrer">{element.title} ↗</a>
        </p>
        {element.kind === "article" && <p className="sc-thread-el__links"><Link href={`/material/${element.id}`}>Kontekst materiału</Link></p>}
        {element.note && <p className="sc-thread-el__note">{element.note}</p>}
      </div>
    </li>
  );
}

function ThreadCardLink({ thread }: { thread: CommunityThreadSummary }) {
  return (
    <li className="sc-community-card">
      <p className="sc-community-card__meta">@{thread.author}{thread.published_at ? ` · ${formatDatePl(thread.published_at)}` : ""} · {thread.items_count} elementów</p>
      <h2><Link href={`/nitki/${thread.id}`}>{thread.title}</Link></h2>
      {thread.description && <p className="sc-community-card__desc">{thread.description}</p>}
      {thread.preview && thread.preview.length > 0 && (
        <ol className="sc-community-card__preview">{thread.preview.map(item => (
          <li key={`${item.kind}-${item.id}`}>{item.kind === "link" ? <span className="sc-thread-el__tag sc-thread-el__tag--outside">spoza Bazy</span> : null}{item.title}</li>
        ))}</ol>
      )}
      <p className="sc-community-card__foot"><span>Przydatna {thread.opinions.positive} · Nieprzydatna {thread.opinions.negative}</span><Link href={`/nitki/${thread.id}`}>Otwórz nitkę →</Link></p>
    </li>
  );
}

export function CommunityThreadsPage() {
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const query = useInfiniteQuery({
    queryKey: ["community-threads", term],
    queryFn: ({ pageParam }) => getCommunityThreads(pageParam, term),
    initialPageParam: 1,
    getNextPageParam: last => last.next_page ?? undefined,
  });
  const threads = query.data?.pages.flatMap(page => page.results) ?? [];
  return (
    <div className="sc-community">
      <header className="sc-community__head">
        <p className="sc-clinic-kicker">Nitki czytelników</p>
        <h1>Sprawy ułożone przez czytelników</h1>
        <p className="sc-clinic-lead">
          Nitka kontekstowa to jeden materiał na początku, a za nim — w kolejności — to, co go dopełnia, potwierdza albo podważa. Każdy może ułożyć
          swoją z materiałów z naszej Bazy albo dodać źródło przez link.
        </p>
        <div className="sc-community__actions">
          <Button href="/konto/nitki/nowa" variant="primary">Ułóż swoją nitkę</Button>
          <form role="search" className="sc-community__search" onSubmit={(event: FormEvent) => { event.preventDefault(); setTerm(search.trim()); }}>
            <input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Szukaj w tytułach nitek…" aria-label="Szukaj nitek" />
            <Button type="submit" variant="quiet" size="sm">Szukaj</Button>
          </form>
        </div>
      </header>
      {query.isLoading && <p className="sc-clinic-empty">Ładowanie nitek…</p>}
      {query.isError && <p role="alert" className="sc-clinic-empty">Nie udało się pobrać nitek.</p>}
      {query.isSuccess && !threads.length && (
        <p className="sc-clinic-empty">{term ? `Brak nitek dla „${term}”.` : "Nie ma jeszcze publicznych nitek. Ułóż pierwszą — wystarczą dwa materiały."}</p>
      )}
      {threads.length > 0 && <ul className="sc-community__list">{threads.map(thread => <ThreadCardLink key={thread.id} thread={thread} />)}</ul>}
      {query.hasNextPage && <Button variant="quiet" loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>Pokaż więcej</Button>}
      <aside className="sc-clinic-roadmap">
        Linki spoza Bazy zapisujemy bez treści i zdjęć — tylko tytuł, adres i nazwę strony; czytelnik trafia do oryginału. Ten sam link w wielu nitkach
        to jeden box. Nitki możesz zgłosić do moderacji.
      </aside>
    </div>
  );
}

function ReportButton({ threadId }: { threadId: number }) {
  const account = useAccount();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("spam");
  const [details, setDetails] = useState("");
  const [status, setStatus] = useState("");
  if (!account.data?.authenticated) return null;
  async function send(event: FormEvent) {
    event.preventDefault();
    try {
      const result = await reportCommunityThread(threadId, reason, details.trim());
      setStatus(result.status === "received" ? "Dziękujemy — zgłoszenie trafiło do zespołu." : "Ta nitka jest już przez Ciebie zgłoszona.");
      setOpen(false);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Nie udało się wysłać zgłoszenia."); }
  }
  return <>
    {status ? <span className="sc-community__status" role="status">{status}</span> : <Button variant="quiet" size="sm" onClick={() => setOpen(true)}>Zgłoś nitkę</Button>}
    <Dialog open={open} onClose={() => setOpen(false)} title="Zgłoś nitkę do moderacji">
      <form className="sc-community-report" onSubmit={send}>
        <label>Powód<select value={reason} onChange={event => setReason(event.target.value)}>{REPORT_REASONS.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label>Szczegóły (opcjonalnie)<textarea rows={3} maxLength={500} value={details} onChange={event => setDetails(event.target.value)} /></label>
        <Button type="submit" variant="primary">Wyślij zgłoszenie</Button>
      </form>
    </Dialog>
  </>;
}

export function CommunityThreadPage({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["community-thread", id], queryFn: () => getCommunityThread(id) });
  if (query.isLoading) return <div className="sc-community"><p className="sc-clinic-empty">Ładowanie nitki…</p></div>;
  if (!query.data) return <div className="sc-community"><p className="sc-clinic-empty">Nie znaleziono nitki — mogła zostać usunięta albo nie jest publiczna. <Link href="/nitki">Wszystkie nitki</Link></p></div>;
  const thread = query.data;
  return (
    <div className="sc-community sc-community--detail">
      <p><Link href="/nitki" className="sc-spin-detail__back">← Nitki czytelników</Link></p>
      <header className="sc-community__head">
        <p className="sc-clinic-kicker">Nitka czytelnika · @{thread.author}</p>
        <h1>{thread.title}</h1>
        {thread.description && <p className="sc-clinic-lead">{thread.description}</p>}
        <p className="sc-community-card__meta">
          {thread.published_at ? `Opublikowana ${formatDateTimePl(thread.published_at)}` : ""} · {thread.items_count} elementów · kolejność ustalił autor
        </p>
        <div className="sc-community__actions">
          {thread.is_owner && <Button href={`/konto/nitki/${thread.id}`} variant="quiet" size="sm">Edytuj swoją nitkę</Button>}
          <ReportButton threadId={thread.id} />
        </div>
      </header>
      <ol className="sc-thread-els" aria-label="Elementy nitki w kolejności">{thread.items.map((item, index) => <ElementRow key={`${item.kind}-${item.id}`} element={item} index={index} />)}</ol>
      <OpinionsPanel endpoint={`/api/community/threads/${thread.id}/opinions/`} labels={{
        kicker: "REAKCJE CZYTELNIKÓW",
        question: "Czy ta nitka była przydatna?",
        positive: "Przydatna",
        negative: "Nieprzydatna",
        signedOut: "Zaloguj się, aby ocenić nitkę i dodać komentarz.",
      }} />
    </div>
  );
}
