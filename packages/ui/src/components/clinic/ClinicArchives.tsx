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
import { formatDatePl, plural } from "../../lib/utils";
import { useDebouncedValue } from "../../lib/useDebouncedValue";
import { MessageDayContent } from "./MessageDetail";
import { InterviewScanner, InterviewResults, InterviewScope } from "./InterviewScanner";
import { Loading } from "../../kit/Loading";
import { PageHeaderV3 } from "../../kit/PageHeaderV3";
import { InterviewArchiveV3, InterviewDetailV3 } from "./InterviewsV3";
import { SideLegend } from "../../kit/SideLegend";
/** Wywiady v3 (seria 2): nowy układ w InterviewsV3.tsx; poprzednie wersje zostają jako *Legacy (powrót bez cofania poprawki). */
export function ClinicInterviewArchive() { return <InterviewArchiveV3 />; }
export function ClinicInterviewPage({ interview }: { interview: Interview }) { return <InterviewDetailV3 interview={interview} />; }

export function ClinicInterviewArchiveLegacy() {
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

export function ClinicInterviewPageLegacy({ interview }: { interview: Interview }) {
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
  // v3 (13.10.2026): dzień = para neutralnych kart Rządzący / Opozycja (bez kolorowych teł i ramek), liczby bez pasków.
  return <section className="sc-v3 sc-v3-page sc-v3-arch">
    <PageHeaderV3 nav={<ClinicNav />} kicker={<><span className="sc-v3-tag" data-tone="accent" title="Wygenerowane z udziałem AI">AI</span> Klinika · Dr. Spin (AI)</>}
      title="Archiwum przekazów" sub="Podsumowania tematów i sposobów argumentacji w przeanalizowanych wpisach rządzących i opozycji, dzień po dniu."
      actions={<SideLegend />}
      aside={first ? <dl><div><dt>{plural(first.count, "dzień w archiwum", "dni w archiwum", "dni w archiwum")}</dt><dd>{first.count.toLocaleString("pl-PL")}</dd></div></dl> : undefined} />
    {query.isPending ? <p className="sc-v3-state" role="status"><Loading label="Wczytywanie przekazów" /></p> : null}
    {query.isError ? <div className="sc-v3-state" role="alert"><p>Nie udało się wczytać przekazów.</p><button type="button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</button></div> : null}
    {first && !rows.length ? <p className="sc-v3-empty">Nie ma jeszcze opublikowanych przekazów.</p> : null}
    {rows.map(row => <section className="sc-v3-arch__day" key={row.day} aria-labelledby={`day-${row.day}`}>
      <div className="sc-v3-feed-h"><h2 id={`day-${row.day}`}><time dateTime={row.day}>{formatDatePl(row.day)}</time></h2>
        <Link className="sc-v3-lnk" href={`/klinika/przekazy/${row.day}`}>Pełny przekaz i źródła <span className="sc-v3-ar" aria-hidden="true">→</span></Link></div>
      <MessageDayContent data={row} compact />
    </section>)}
    {query.hasNextPage ? <p><Button className="sc-archive-more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? <Loading inline label="Wczytywanie" /> : "Pokaż wcześniejsze dni"}</Button></p> : null}
  </section>;
}
