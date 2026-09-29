"use client";

import { ClinicNav } from "./ClinicNav";
import { SearchField } from "../../kit/SearchField";
import { Button } from "../../kit/Button";
import { SectionHeader } from "../../kit/SectionHeader";
import Link from "next/link";
import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { CAMPS, getClinicInterviews, getClinicMessages, type Interview } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { useDebouncedValue } from "../../lib/useDebouncedValue";
import { MessageBox } from "./ClinicExtras";
import { InterviewScanner } from "./InterviewScanner";
import { IntensityMeter, VerdictTag } from "./SpinParts";

function guestLabel(interview: Interview) {
  // Afiliacja wyłącznie z zapisanego opisu gościa, nigdy z dopasowania nazwiska.
  const party = interview.guest_role.match(/(?:^|[\s,(])(KO|PiS|PSL|Polska 2050|Konfederacja|Lewica|Razem|PO|Nowa Lewica|Nowa Nadzieja|Suwerenna Polska)(?=$|[\s,).])/i)?.[1];
  return `${interview.guest_name}${party || interview.guest_role ? `, ${party || interview.guest_role}` : ""}`;
}

function InterviewScores({ interview }: { interview: Interview }) {
  return <><div className="sc-clinic-archives__columns">
    <section><h3>Wypowiedzi gościa</h3><p>{guestLabel(interview)}</p>
      <p className="sc-spin-card__verdict"><VerdictTag verdict={interview.guest.verdict} label={interview.guest.verdict_label} /><IntensityMeter value={interview.guest.intensity} /></p>
      <p className="sc-t-caption">Ocena technik perswazji w wypowiedziach gościa.</p>
    </section>
    <section><h3>Pytania i reakcje prowadzącego</h3><p>{interview.host_name}</p>
      {interview.host.verdict ? <p className="sc-spin-card__verdict"><VerdictTag verdict={interview.host.verdict} label={interview.host.verdict_label ?? ""} />{interview.host.intensity == null ? <span>Brak odpowiedzi</span> : <IntensityMeter value={interview.host.intensity} />}</p>
        : <p className="sc-interview__noverdict">Brak oceny warsztatu w tym wywiadzie.</p>}
      <p className="sc-t-caption">Ocena sposobu zadawania pytań i reakcji na odpowiedzi.</p>
    </section>
  </div><p className="sc-archive-interview-summary">{interview.summary}</p></>;
}

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
    <SectionHeader variant="page" title="Archiwum wywiadów" subtitle="Analizy wypowiedzi gości oraz pytań i reakcji prowadzących — z cytatami i odwołaniami do nagrania." />
    <div className="sc-clinic-archives__filters">
      <div><p className="sc-archive-search-label">Szukaj gościa, prowadzącego lub tytułu</p><SearchField label="Szukaj gościa, prowadzącego lub tytułu" value={search} onChange={setSearch} /></div>
      <label>Kanał<select value={channel} onChange={event => setChannel(event.target.value)}>
        <option value="">Wszystkie kanały</option>
        {Array.from(new Set([...(first?.channels ?? []), ...(channel ? [channel] : [])])).map(name => <option key={name} value={name}>{name}</option>)}
      </select></label>
    </div>
    {first ? <p role="status">Liczba wywiadów{q || channel ? " spełniających filtry" : ""}: {first.count.toLocaleString("pl-PL")}</p> : null}
    {query.isPending ? <p role="status">Wczytywanie wywiadów…</p> : null}
    {query.isError ? <p role="alert">Nie udało się wczytać wywiadów. <Button type="button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</Button></p> : null}
    {first && !rows.length ? <p>Brak wywiadów spełniających wybrane kryteria.</p> : null}
    <div className="sc-clinic-archives__list">{rows.map(interview => <article className="sc-clinic-archives__card" key={interview.id}>
      <p><time dateTime={interview.day}>{formatDatePl(interview.day)}</time> · {interview.channel}</p>
      <h2><Link href={`/klinika/wywiady/${interview.id}`}>{interview.title || interview.headline}</Link></h2>
      <InterviewScores interview={interview} />
      <Link href={`/klinika/wywiady/${interview.id}`}>Czytaj analizę →</Link>
    </article>)}</div>
    {query.hasNextPage ? <Button className="sc-archive-more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Wczytywanie…" : "Pokaż więcej"}</Button> : null}
  </section>;
}

export function ClinicInterviewPage({ interview }: { interview: Interview }) {
  return <section className="sc-clinic-archives">
    <ClinicNav />
    <SectionHeader variant="page" longTitle title={interview.title || interview.headline} />
    <InterviewScanner interview={interview} />
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
    {query.isPending ? <p role="status">Wczytywanie przekazów…</p> : null}
    {query.isError ? <p role="alert">Nie udało się wczytać przekazów. <Button type="button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</Button></p> : null}
    {first && !rows.length ? <p>Nie ma jeszcze opublikowanych przekazów.</p> : null}
    <div className="sc-clinic-archives__list">{rows.map(row => <section className="sc-clinic-archives__day" key={row.day} aria-labelledby={`day-${row.day}`}>
      <h2 id={`day-${row.day}`}><time dateTime={row.day}>{formatDatePl(row.day)}</time></h2>
      <div className="sc-clinic-archives__columns">{CAMPS.map(camp => <MessageBox key={camp} camp={camp} message={row[camp]} emptyText="Brak zatwierdzonego przekazu tego dnia." />)}</div>
    </section>)}</div>
    {query.hasNextPage ? <Button className="sc-archive-more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Wczytywanie…" : "Pokaż wcześniejsze dni"}</Button> : null}
  </section>;
}
