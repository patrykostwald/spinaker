"use client";

/**
 * Uproszczona strona główna — PODGLĄD pod /nowa-glowna (propozycja 28.09.2026, obecna główna bez zmian).
 * Zasada: najpierw pokazać, potem opisać. Pięć elementów: pas powitalny z jednym zdaniem → Spin dnia w skrócie
 * (wpis → ocena → dwie techniki → pełna diagnoza) → Wywiady (zwinięte) → Najnowsze → Twoje wiadomości → newsletter.
 * Pasek najnowszych, kategorie, pełna Baza, zaproszenie dla dziennikarzy i przekazy dnia — w Klinice, Bazie i O nas.
 */

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getClinicPage, type SpinDetailData } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { AiTag, IntensityMeter, VerdictTag } from "../../components/clinic/SpinParts";
import { InterviewBox } from "../../components/clinic/ClinicExtras";
import { NewsletterSignup } from "../../components/NewsletterSignup";
import { HomeHero } from "./HomeHero";
import { HomeLead } from "./HomeLead";
import { HomeThreads } from "./HomeThreads";
import { collapseSimilar } from "./collapseSimilar";
import { useHomeConfig, useHomeFeed } from "./data";

function SpinOfDayCompact({ spin }: { spin: SpinDetailData }) {
  const party = spin.author.party?.short;
  const techniques = (spin.techniques ?? []).filter((item) => item.name).slice(0, 2);
  return (
    <section className="sc-simple-spin" aria-labelledby="simple-spin-title">
      <header className="sc-simple-spin__head">
        <p className="sc-t-caption sc-text-3 sc-home-kicker">Spin dnia · Dr. Spin <AiTag /></p>
        <Link href="/klinika" className="sc-simple-spin__all">Wszystkie diagnozy w Klinice →</Link>
      </header>
      <div className="sc-simple-spin__grid">
        <figure className="sc-simple-spin__post">
          <figcaption>
            <strong>{spin.author.name}</strong>
            <span>{[party, spin.post.published_at ? formatDatePl(spin.post.published_at) : ""].filter(Boolean).join(" · ")}</span>
          </figcaption>
          <blockquote>{spin.post.text}</blockquote>
        </figure>
        <div className="sc-simple-spin__diagnosis">
          <p className="sc-spin-card__verdict"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><IntensityMeter value={spin.intensity} /></p>
          <h2 id="simple-spin-title" className="sc-t-title-m">{spin.headline}</h2>
          {techniques.length ? (
            <ul className="sc-simple-spin__techniques">
              {techniques.map((item) => (
                <li key={item.name}><strong>{item.name}</strong>{item.quote ? <span>„{item.quote}”</span> : null}</li>
              ))}
            </ul>
          ) : <p className="sc-text-2">{spin.summary}</p>}
          <Link href={`/klinika/${spin.id}`} className="sc-simple-spin__cta">Pełna diagnoza ze źródłami →</Link>
        </div>
      </div>
    </section>
  );
}

function useLead() {
  const day = useHomeFeed("day-top", { mode: "top", sources: [], pageSize: 13, diverse: true }, { refetchInterval: 120_000 });
  const dayArticles = useMemo(() => day.data?.results ?? [], [day.data]);
  const dayEmpty = day.isSuccess && dayArticles.length === 0;
  const fallback = useHomeFeed("day-latest", { mode: "latest", sources: [], pageSize: 40, diverse: true }, { enabled: dayEmpty });
  const articles = dayEmpty ? (fallback.data?.results ?? []).slice(0, 13) : dayArticles;
  const collapsed = useMemo(() => collapseSimilar(articles), [articles]);
  return { main: collapsed[0]?.article ?? null, related: collapsed.slice(1, 9), fallback: dayEmpty };
}

export function HomePageSimple() {
  const clinic = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, staleTime: 5 * 60_000 });
  const config = useHomeConfig();
  const lead = useLead();
  const data = clinic.data;
  const spin = data?.spin_of_day ?? data?.latest_spin ?? null;
  return (
    <div className="sc-home sc-home-simple">
      <h1 className="sc-sr-only">spin.clinic — wiadomości ze źródłami i diagnozy spinu polityków</h1>
      <p className="sc-simple-preview" role="status">Podgląd nowej strony głównej — obecna wersja: <Link href="/">spin.clinic</Link></p>
      <HomeHero />
      {spin ? <SpinOfDayCompact spin={spin} /> : null}
      {data?.interview ? (
        <section className="sc-simple-interviews" aria-label="Wywiady">
          <InterviewBox interview={data.interview} kicker="Wywiady" />
          {data.interview_second ? <InterviewBox interview={data.interview_second} kicker="Wywiady" /> : null}
        </section>
      ) : null}
      <HomeLead main={lead.main} related={lead.related} fallback={lead.fallback} dateLabel="" emptyNote={null} />
      <HomeThreads sources={config.data?.sources ?? []} />
      <p className="sc-simple-links">
        <Link href="/#baza">Przeszukaj Bazę materiałów →</Link>
        <Link href="/klinika">Przekazy dnia obu stron →</Link>
        <Link href="/o-nas#nitka-kontekstowa">Dla dziennikarzy: autoryzowane nitki →</Link>
      </p>
      <NewsletterSignup source="home" />
    </div>
  );
}
