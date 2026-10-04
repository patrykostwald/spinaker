"use client";

import { ClinicDiscussion, DiscussionCounts } from "./ClinicDiscussion";
import { ClinicNav } from "./ClinicNav";
import { SearchField } from "../../kit/SearchField";
import { Button } from "../../kit/Button";
import { SectionHeader } from "../../kit/SectionHeader";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { rememberClinicVisit } from "../../lib/clinicHistory";
import { useInfiniteQuery } from "@tanstack/react-query";
import { getClinicInterviews, getClinicMessages, type Interview } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { useDebouncedValue } from "../../lib/useDebouncedValue";
import { MessageDayContent } from "./MessageDetail";
import { InterviewScanner, InterviewResults, InterviewScope } from "./InterviewScanner";
import { Loading } from "../../kit/Loading";
export function ClinicInterviewArchive() {
  const [search, setSearch] = useState("");
  const [channel, setChannel] = useState("");
  const q = useDebouncedValue(search.trim());
  const query = useInfiniteQuery({
    queryKey: ["clinic-interviews", q, channel],
    queryFn: ({ pageParam }) => getClinicInterviews({ page: pageParam, q, channel }),
    initialPageParam: 1,
    getNextPageParam: last => last.next_page ?? undefined,
  });
  const first = query.data?.pages[0];
  const rows = query.data?.pages.flatMap(page => page.results) ?? [];
  return <section className="sc-clinic-archives">
    <ClinicNav />
    <SectionHeader variant="page" title="Archiwum wywiadów" subtitle="Analizy gości i prowadzących, z cytatami i odwołaniem do nagrania." />
    {/* Jedno pole wyszukiwania z wyborem kanału w środku zamiast trzech boksów; liczba tylko przy filtrowaniu (właściciel 3.10) */}
    <div className="sc-iv-search">
      <SearchField label="Szukaj gościa, prowadzącego lub tytułu" placeholder="Szukaj gościa, prowadzącego, tytułu…" value={search} onChange={setSearch} />
      <select aria-label="Kanał" value={channel} onChange={event => setChannel(event.target.value)}>
        <option value="">Każdy kanał</option>
        {Array.from(new Set([...(first?.channels ?? []), ...(channel ? [channel] : [])])).map(name => <option key={name} value={name}>{name}</option>)}
      </select>
    </div>
    {first && (q || channel) ? <p role="status" className="sc-iv-search__count">Znaleziono: {first.count.toLocaleString("pl-PL")}</p> : null}
    {query.isPending ? <p role="status"><Loading label="Wczytywanie wywiadów" /></p> : null}
    {query.isError ? <p role="alert">Nie udało się wczytać wywiadów. <Button type="button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</Button></p> : null}
    {first && !rows.length ? <p>Brak wywiadów spełniających wybrane kryteria.</p> : null}
    {/* Karta: z lewej teksty i przycisk na dole, z prawej gość i prowadzący w wierszach (uwagi recenzenta UX, 30.09) */}
    <div className="sc-clinic-archives__list">{rows.map(interview => <article className="sc-clinic-archives__card sc-iv-card" key={interview.id}>
      <div className="sc-iv-card__text">
        <p><time dateTime={interview.day}>{formatDatePl(interview.day)}</time> · {interview.channel}</p>
        <h2><Link href={`/klinika/wywiady/${interview.id}`}>{interview.headline || "Analiza wywiadu"}</Link></h2>
        <p className="sc-interview-recording-title"><span>Tytuł nagrania:</span> {interview.title}</p>
        <p className="sc-archive-interview-summary">{interview.summary}</p>
        <DiscussionCounts {...interview} />
        <Link className="sc-iv-card__cta" href={`/klinika/wywiady/${interview.id}`}>Czytaj analizę →</Link>
      </div>
      <InterviewResults interview={interview} />
    </article>)}</div>
    {query.hasNextPage ? <Button className="sc-archive-more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? <Loading inline label="Wczytywanie" /> : "Pokaż więcej"}</Button> : null}
    <InterviewScope />
  </section>;
}

export function ClinicInterviewPage({ interview }: { interview: Interview }) {
  const recorded = useRef<number | null>(null);
  useEffect(() => {
    if (recorded.current === interview.id) return;
    recorded.current = interview.id;
    rememberClinicVisit({ type: "interview", id: interview.id, title: interview.headline || interview.title,
      camp: null, verdict: interview.guest.verdict, intensity: interview.guest.intensity, guest: interview.guest_name });
  }, [interview]);
  return <section className="sc-clinic-archives">
    <ClinicNav />
    <SectionHeader variant="page" longTitle title={interview.headline || "Analiza wywiadu"} />
    {interview.selection_label ? <p>{interview.selection_label}</p> : null}
    <InterviewScanner interview={interview} full />
    <ClinicDiscussion kind="interviews" id={interview.id} />
  </section>;
}

export function ClinicMessageArchive() {
  const query = useInfiniteQuery({
    queryKey: ["clinic-messages"],
    queryFn: ({ pageParam }) => getClinicMessages(pageParam),
    initialPageParam: 1,
    getNextPageParam: last => last.next_page ?? undefined,
  });
  const first = query.data?.pages[0];
  const rows = query.data?.pages.flatMap(page => page.results) ?? [];
  return <section className="sc-clinic-archives">
    <ClinicNav />
    <SectionHeader variant="page" title="Archiwum przekazów" subtitle="Podsumowania tematów i sposobów argumentacji w przeanalizowanych wpisach rządzących i opozycji." />
    {first ? <p>Liczba dni: {first.count.toLocaleString("pl-PL")}</p> : null}
    {query.isPending ? <p role="status"><Loading label="Wczytywanie przekazów" /></p> : null}
    {query.isError ? <p role="alert">Nie udało się wczytać przekazów. <Button type="button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</Button></p> : null}
    {first && !rows.length ? <p>Nie ma jeszcze opublikowanych przekazów.</p> : null}
    <div className="sc-clinic-archives__list">{rows.map(row => <section className="sc-clinic-archives__day" key={row.day} aria-labelledby={`day-${row.day}`}>
      <h2 id={`day-${row.day}`}><time dateTime={row.day}>{formatDatePl(row.day)}</time></h2>
      <MessageDayContent data={row} />
      <Link href={`/klinika/przekazy/${row.day}`}>Pełny przekaz i źródła →</Link>
    </section>)}</div>
    {query.hasNextPage ? <Button className="sc-archive-more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? <Loading inline label="Wczytywanie" /> : "Pokaż wcześniejsze dni"}</Button> : null}
  </section>;
}
