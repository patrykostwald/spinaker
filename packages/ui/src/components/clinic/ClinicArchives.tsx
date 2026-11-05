"use client";

import { ClinicNav } from "./ClinicNav";
import { SearchField } from "../../kit/SearchField";
import { Button } from "../../kit/Button";
import { Breadcrumbs } from "../../kit/Breadcrumbs";
import { SectionHeader } from "../../kit/SectionHeader";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { rememberClinicVisit } from "../../lib/clinicHistory";
import { useInfiniteQuery } from "@tanstack/react-query";
import { getClinicInterviews, getClinicMessages, type Interview } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { useDebouncedValue } from "../../lib/useDebouncedValue";
import { MessageCampSwitch, MessageDayContent, useMessageCamp } from "./MessageDetail";
import { InterviewScanner, InterviewResults, InterviewScope } from "./InterviewScanner";
import { AiNotice, INTERVIEW_PUBLICATION_MODEL } from "./AiNotice";
import { CorrectionForm } from "../CorrectionForm";
import { modelFullName } from "../../lib/models";
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
    <InterviewScope />
    {/* Karta: z lewej teksty i przycisk na dole, z prawej gość i prowadzący w wierszach (uwagi recenzenta UX, 30.09) */}
    <div className="sc-clinic-archives__list">{rows.map(interview => <article className="sc-clinic-archives__card sc-iv-card" key={interview.id}>
      <div className="sc-iv-card__text">
        <p><time dateTime={interview.day}>{formatDatePl(interview.day)}</time> · {interview.channel}</p>
        <h2><Link href={`/klinika/wywiady/${interview.id}`}>{interview.headline || "Analiza wywiadu"}</Link></h2>
        <p className="sc-interview-recording-title"><span>Tytuł nagrania:</span> {interview.title}</p>
        <p className="sc-archive-interview-summary">{interview.summary}</p>
        <Link className="sc-iv-card__cta" href={`/klinika/wywiady/${interview.id}`}>Czytaj analizę →</Link>
      </div>
      <InterviewResults interview={interview} />
    </article>)}</div>
    {query.hasNextPage ? <Button className="sc-archive-more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Wczytywanie…" : "Pokaż więcej"}</Button> : null}
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
    <AiNotice models={interview.model.split("+").map(part => modelFullName(part.trim())).join(" · ")}
      publication={interview.auto_published ? { mode: "auto", at: interview.diagnosed_at } : null} explain={INTERVIEW_PUBLICATION_MODEL}
      note="To nie jest rozstrzygnięcie redakcji: AI ocenia osobno wypowiedzi gościa i pytania prowadzącego, a transkrypcja może zawierać błędy. Dla wywiadów nie zapisujemy, ile modeli odpowiedziało." />
    <div className="sc-dg-actionbar"><CorrectionForm kind="interview" targetId={interview.id} type="correction" label="Sprostowanie / odpowiedź" /><CorrectionForm kind="interview" targetId={interview.id} type="error" label="Zgłoś błąd" /></div>
    <InterviewScanner interview={interview} full />
  </section>;
}

export function ClinicMessageArchive() {
  const { camp, select } = useMessageCamp();
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
    <Breadcrumbs items={[{ label: "Główna", href: "/" }, { label: "Klinika", href: "/klinika" }, { label: "Przekazy" }]} />
    <SectionHeader variant="page" title="Archiwum przekazów" subtitle="Podsumowania tematów i sposobów argumentacji w przeanalizowanych wpisach rządzących i opozycji." />
    {first ? <p>Liczba dni: {first.count.toLocaleString("pl-PL")}</p> : null}
    {query.isPending ? <p role="status">Wczytywanie przekazów…</p> : null}
    {query.isError ? <p role="alert">Nie udało się wczytać przekazów. <Button type="button" onClick={() => void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())}>Spróbuj ponownie</Button></p> : null}
    {first && !rows.length ? <p>Nie ma jeszcze opublikowanych przekazów.</p> : null}
    <MessageCampSwitch camp={camp} select={select} />
    <div className="sc-clinic-archives__list">{rows.map(row => <section className="sc-clinic-archives__day" key={row.day} aria-labelledby={`day-${row.day}`}>
      <h2 id={`day-${row.day}`}><time dateTime={row.day}>{formatDatePl(row.day)}</time></h2>
      <MessageDayContent data={row} camp={camp} />
      <Link href={`/klinika/przekazy/${row.day}`}>Pełny przekaz i źródła →</Link>
    </section>)}</div>
    {query.hasNextPage ? <Button className="sc-archive-more" type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Wczytywanie…" : "Pokaż wcześniejsze dni"}</Button> : null}
  </section>;
}
