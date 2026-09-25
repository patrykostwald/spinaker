"use client";

/**
 * Strona główna na kicie. Kolejność: pasek górny (data · temat dnia) → ilustracja autorska →
 * wiersz filtrów [grupa źródeł · tematy (wyśrodkowane) · hasło] → rząd czterech najnowszych
 * („Top 10”, zawężany tymi filtrami) → Temat dnia → Nitki użytkownika → Dr Spin → Przekaz dnia →
 * pas „Twój przegląd” → Baza (stała wysokość, przewijana w środku) → globalna stopka.
 * Grupa źródeł żyje w adresie (`?zrodla=`), bo ustawiają ją też linki w stopce; zawęża „Top 10” i Bazę.
 * Portal (`PortalProvider` w trybie `path`), szapka i stopka są globalne — `app/providers.tsx`
 * i `app/layout.tsx`; klik w kartę otwiera materiał morfingiem i wpisuje `/material/<id>`.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Dropdown } from "../Dropdown";
import { SearchField } from "../SearchField";
import { HomeBand } from "./HomeBand";
import { HomeBaza } from "./HomeBaza";
import { HomeCategoryBar } from "./HomeCategoryBar";
import { HomeDrSpin } from "./HomeDrSpin";
import { HomeHero } from "./HomeHero";
import { HomeLead } from "./HomeLead";
import { HomePrzekazDnia } from "./HomePrzekazDnia";
import { HomeReveal } from "./HomeReveal";
import { HomeThreads, type StripDraft } from "./HomeThreads";
import { HomeTicker } from "./HomeTicker";
import { useDemoMode, useDrSpinThread, useHomeConfig, useHomeFeed, useTopicOfDay } from "./data";
import { SOURCE_GROUPS, SOURCE_GROUP_PARAM, groupSources, parseSourceGroup, sourceGroupLabel, type SourceGroup } from "./sourceGroups";

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
  const router = useRouter();
  const pathname = usePathname();
  const q = params.get("q") ?? "";
  const sourceGroup = parseSourceGroup(params.get(SOURCE_GROUP_PARAM));
  const [keyword, setKeyword] = useState("");
  const [topQuery, setTopQuery] = useState("");
  const config = useHomeConfig();
  const drSpin = useDrSpinThread();
  const topic = useTopicOfDay();
  const [activeTopic, setActiveTopic] = useState<string | null>(null);
  const [stripDraft, setStripDraft] = useState<StripDraft | null>(null);
  const bazaRef = useRef<HTMLElement | null>(null);
  const threadsRef = useRef<HTMLElement | null>(null);

  const categories = config.data?.categories ?? [];
  const sources = config.data?.sources ?? [];
  const groupIds = useMemo(() => (sourceGroup ? groupSources(sources)[sourceGroup].map((source) => source.id) : []), [sources, sourceGroup]);
  const groupEmpty = Boolean(sourceGroup) && sources.length > 0 && groupIds.length === 0;

  // Hasło z wiersza filtrów trafia do zapytania po chwili bez pisania (bez zapytania na każdy znak).
  useEffect(() => {
    const timer = window.setTimeout(() => setTopQuery(keyword.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [keyword]);

  function setSourceGroup(next: SourceGroup | null) {
    const search = new URLSearchParams(params.toString());
    if (next) search.set(SOURCE_GROUP_PARAM, next);
    else search.delete(SOURCE_GROUP_PARAM);
    const query = search.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  // „Top 10”: najnowsze materiały, zawężane tematem, grupą źródeł i hasłem z wiersza filtrów.
  const top = useHomeFeed(
    "top10",
    { mode: "latest", topics: activeTopic ? [activeTopic] : [], sources: groupIds, query: topQuery, pageSize: 10 },
    { refetchInterval: 30_000, enabled: !groupEmpty },
  );
  const latest = useMemo(() => (groupEmpty ? [] : top.data?.results ?? []), [groupEmpty, top.data]);

  const topicQuery = topic.data?.mode === "automatic" ? topic.data.query : null;
  const topicFeed = useHomeFeed("topic-of-day", { query: topicQuery ?? "", match: "words", pageSize: 40 }, { enabled: Boolean(topicQuery) });
  const topicArticles = useMemo(() => topicFeed.data?.results ?? [], [topicFeed.data]);
  const topicReady = Boolean(topicQuery) && topicArticles.length >= 3;

  useEffect(() => {
    if (q) bazaRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
  }, [q]);

  // Temat dnia: kotwica + materiały tematu w kolejności publikacji; bez tematu — najnowsze.
  const leadMain = topicReady ? topicArticles[0] : latest[0] ?? null;
  const related = useMemo(
    () =>
      topicReady
        ? topicArticles
            .slice(1)
            .filter((a) => a.published_date)
            .sort((a, b) => new Date(a.published_date!).getTime() - new Date(b.published_date!).getTime())
            .slice(0, 12)
        : latest.slice(1, 10),
    [topicReady, topicArticles, latest],
  );

  return (
    <>
      <div className="sc-home">
        <h1 className="sc-sr-only">Wiadomości i ich kontekst</h1>
        <TopBar topicLabel={topicReady ? topic.data?.label ?? null : null} />
        <DemoBanner />
        <HomeHero />
        <div className="sc-home-top">
          <HomeCategoryBar
            value={activeTopic}
            onChange={setActiveTopic}
            start={
              <Dropdown
                label={sourceGroup ? `Źródła: ${sourceGroupLabel(sourceGroup)}` : "Źródła: wszystkie"}
                ariaLabel="Grupa źródeł"
                mode="single"
                presentation="auto"
                triggerVariant="quiet"
                items={[{ value: "", label: "Wszystkie źródła" }, ...SOURCE_GROUPS]}
                value={sourceGroup ?? ""}
                onChange={(value) => setSourceGroup(parseSourceGroup(value as string))}
              />
            }
            end={
              <form className="sc-home-catrow__search" role="search" onSubmit={(event) => event.preventDefault()}>
                <SearchField value={keyword} onChange={setKeyword} placeholder="Hasło…" label="Hasło w najnowszych materiałach" maxLength={200} />
              </form>
            }
          />
          {groupEmpty && sourceGroup ? (
            <p className="sc-t-body-s sc-text-2 sc-home-top__note" role="status">Brak aktywnych źródeł w grupie „{sourceGroupLabel(sourceGroup)}”.</p>
          ) : null}
          {!groupEmpty && top.isSuccess && !latest.length && (topQuery || activeTopic) ? (
            <p className="sc-t-body-s sc-text-2 sc-home-top__note" role="status">Brak najnowszych materiałów dla tego wyboru.</p>
          ) : null}
          <HomeTicker articles={latest.slice(0, 4)} />
        </div>
        <HomeReveal>
          <HomeLead main={leadMain} label={topicReady ? topic.data?.label ?? null : null} related={related} href="/#baza" />
        </HomeReveal>
        <HomeReveal>
          <HomeThreads ref={threadsRef} categories={categories} sources={sources} draft={stripDraft} />
        </HomeReveal>
        <HomeReveal>
          <HomeDrSpin thread={drSpin.data ?? null} />
        </HomeReveal>
        <HomePrzekazDnia government={config.data?.editorial.government ?? null} opposition={config.data?.editorial.opposition ?? null} />
        <HomeReveal>
          <HomeBand
            onCreate={(query) => {
              setStripDraft({ query, nonce: Date.now() });
              threadsRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
            }}
          />
        </HomeReveal>
        <HomeReveal>
          <HomeBaza ref={bazaRef} categories={categories} sources={sources} initialQuery={q} sourceGroup={sourceGroup} />
        </HomeReveal>
      </div>
    </>
  );
}
