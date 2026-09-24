"use client";

/**
 * Strona główna na kicie (etap 2, krok 1). Struktura wg referencji właściciela (USA Today, 24.09),
 * treść — nasza: pasek górny (data · temat dnia) → szapka → pasek tematów → ilustracja autorska →
 * rząd czterech najnowszych → hero (materiał tematu dnia + oś czasu) → „Wszystkie źródła”
 * (mozaika + lista 1–5) → Dr Spin → Przekaz dnia → Baza → pas „Twój przegląd” → stopka.
 * Portal (`PortalProvider` w trybie `path`), szapka i stopka są globalne — `app/providers.tsx`
 * i `app/layout.tsx`; klik w kartę otwiera materiał morfingiem i wpisuje `/material/<id>`.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Article } from "../../types";
import { HomeBand } from "./HomeBand";
import { HomeBaza, type StripDraft } from "./HomeBaza";
import { HomeCategoryBar } from "./HomeCategoryBar";
import { HomeDrSpin } from "./HomeDrSpin";
import { HomeHero } from "./HomeHero";
import { HomeLead, rowTime, type LeadRow } from "./HomeLead";
import { HomeMosaic } from "./HomeMosaic";
import { HomePrzekazDnia } from "./HomePrzekazDnia";
import { HomeTicker } from "./HomeTicker";
import { useDemoMode, useDrSpinThread, useHomeConfig, useHomeFeed, useTopicOfDay } from "./data";

function DemoBanner() {
  const demo = useDemoMode();
  if (!demo) return null;
  return (
    <p className="sc-home-demo sc-t-meta" role="status">
      <strong>Dane demonstracyjne.</strong> Backend jest niedostępny — materiały poniżej są FIKCYJNE i służą tylko do pracy nad układem.
    </p>
  );
}

function TopBar({ topicLabel }: { topicLabel: string | null }) {
  const [date, setDate] = useState("");
  useEffect(() => {
    setDate(new Intl.DateTimeFormat("pl-PL", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date()));
  }, []);
  return (
    <div className="sc-home-topbar sc-t-meta">
      <span className="sc-home-topbar__date" suppressHydrationWarning>
        {date}
      </span>
      {topicLabel ? (
        <span className="sc-home-topbar__topic">
          <span className="sc-text-3">Temat dnia:</span> {topicLabel}
        </span>
      ) : null}
    </div>
  );
}

export function HomePage() {
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const config = useHomeConfig();
  const drSpin = useDrSpinThread();
  const topic = useTopicOfDay();
  const [activeTopic, setActiveTopic] = useState<string | null>(null);
  const [latest, setLatest] = useState<Article[]>([]);
  const [stripDraft, setStripDraft] = useState<StripDraft | null>(null);
  const bazaRef = useRef<HTMLElement | null>(null);

  const topicQuery = topic.data?.mode === "automatic" ? topic.data.query : null;
  const topicFeed = useHomeFeed("topic-of-day", { query: topicQuery ?? "", match: "words", pageSize: 40 }, { enabled: Boolean(topicQuery) });
  const topicArticles = useMemo(() => topicFeed.data?.results ?? [], [topicFeed.data]);
  const topicReady = Boolean(topicQuery) && topicArticles.length >= 3;

  useEffect(() => {
    if (q) bazaRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
  }, [q]);

  const onArticles = useCallback((articles: Article[]) => setLatest(articles), []);

  const categories = config.data?.categories ?? [];
  const sources = config.data?.sources ?? [];
  const topSources = config.data?.top_sources ?? [];

  // Hero: temat dnia (materiał + oś czasu godzin) albo — bez tematu — najnowsze materiały.
  const leadMain = topicReady ? topicArticles[0] : latest[0] ?? null;
  const leadRows: LeadRow[] = (topicReady ? topicArticles.slice(1, 6) : latest.slice(1, 6)).map((article) => ({ article, time: rowTime(article) }));
  const thread = useMemo(
    () =>
      topicReady
        ? [...topicArticles]
            .filter((a) => a.published_date)
            .sort((a, b) => new Date(a.published_date!).getTime() - new Date(b.published_date!).getTime())
            .slice(0, 12)
        : [],
    [topicReady, topicArticles],
  );

  return (
    <>
      <div className="sc-home">
        <h1 className="sc-sr-only">Wiadomości i ich kontekst</h1>
        <TopBar topicLabel={topicReady ? topic.data?.label ?? null : null} />
        <HomeCategoryBar value={activeTopic} onChange={setActiveTopic} />
        <DemoBanner />
        <HomeHero />
        <HomeTicker articles={latest.slice(0, 4)} />
        <HomeLead
          main={leadMain}
          eyebrow={topicReady ? "Temat dnia" : "Najnowszy materiał"}
          panelTitle={topicReady ? "Oś czasu tematu" : "Najnowsze"}
          rows={leadRows}
          panelHref="/#baza"
          thread={thread}
        />
        <HomeMosaic sources={sources.length ? sources : topSources} topic={activeTopic} onArticles={onArticles} />
        <HomeDrSpin thread={drSpin.data ?? null} />
        <HomePrzekazDnia government={config.data?.editorial.government ?? null} opposition={config.data?.editorial.opposition ?? null} />
        <HomeBaza ref={bazaRef} categories={categories} sources={sources} initialQuery={q} stripDraft={stripDraft} />
        <HomeBand
          onCreate={(query) => {
            setStripDraft({ query, nonce: Date.now() });
            bazaRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
          }}
        />
      </div>
    </>
  );
}
