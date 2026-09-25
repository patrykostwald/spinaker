"use client";

/**
 * Strona główna na kicie. Kolejność: pasek górny (data · temat dnia) → ilustracja autorska →
 * wiersz filtrów [grupa źródeł · tematy (wyśrodkowane) · hasło] → pasek newsowy spin.clinic
 * (taśma „Top 10”, zawężana tymi filtrami) → Wiadomości dnia (`mode=top`) → Nitki użytkownika
 * (do 5 własnych pasków) → Dr. Spin → Przekaz dnia →
 * Baza (stała wysokość, przewijana w środku) → globalna stopka.
 * Grupa źródeł żyje w adresie (`?zrodla=`), bo ustawiają ją też linki w stopce; zawęża „Top 10” i Bazę.
 * Portal (`PortalProvider` w trybie `path`), szapka i stopka są globalne — `app/providers.tsx`
 * i `app/layout.tsx`; klik w kartę otwiera materiał morfingiem i wpisuje `/material/<id>`.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Dropdown } from "../Dropdown";
import { SearchField } from "../SearchField";
import { HomeBaza } from "./HomeBaza";
import { HomeCategoryBar } from "./HomeCategoryBar";
import { HomeDrSpin } from "./HomeDrSpin";
import { HomeHero } from "./HomeHero";
import { HomeLead } from "./HomeLead";
import { HomePrzekazDnia } from "./HomePrzekazDnia";
import { HomeReveal } from "./HomeReveal";
import { HomeThreads } from "./HomeThreads";
import { HomeTicker } from "./HomeTicker";
import { collapseSimilar } from "./collapseSimilar";
import { useDemoMode, useDrSpinThread, useHomeConfig, useHomeFeed } from "./data";
import { GROUP_EMPTY_HINT, SOURCE_GROUPS, SOURCE_GROUP_PARAM, activeSources, groupSources, parseSourceGroup, sourceGroupLabel, type SourceGroup } from "./sourceGroups";

function DemoBanner() {
  const demo = useDemoMode();
  if (!demo) return null;
  return (
    <p className="sc-home-demo sc-t-meta" role="status">
      <strong>Dane demonstracyjne.</strong> Backend jest niedostępny — materiały poniżej są FIKCYJNE i służą tylko do pracy nad układem.
    </p>
  );
}

function useTodayLabel(options: Intl.DateTimeFormatOptions) {
  const [label, setLabel] = useState("");
  const key = JSON.stringify(options);
  useEffect(() => {
    setLabel(new Intl.DateTimeFormat("pl-PL", JSON.parse(key)).format(new Date()));
  }, [key]);
  return label;
}

function TopBar() {
  const date = useTodayLabel({ weekday: "long", day: "numeric", month: "long", year: "numeric" });
  return (
    <div className="sc-home-topbar sc-t-meta">
      <span className="sc-home-topbar__date" suppressHydrationWarning>
        {date}
      </span>
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
  const [activeTopic, setActiveTopic] = useState<string | null>(null);
  // Grupa źródeł „Wiadomości dnia” — własny selektor w nagłówku pasa, niezależny od filtrów paska newsowego.
  const [dayGroup, setDayGroup] = useState<SourceGroup | null>(null);
  const bazaRef = useRef<HTMLElement | null>(null);

  const sources = config.data?.sources ?? [];
  const groupIds = useMemo(() => (sourceGroup ? groupSources(activeSources(sources))[sourceGroup].map((source) => source.id) : []), [sources, sourceGroup]);
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
    { mode: "latest", topics: activeTopic ? [activeTopic] : [], sources: groupIds, query: topQuery, pageSize: 20 },
    { refetchInterval: 30_000, enabled: !groupEmpty },
  );
  const latest = useMemo(() => (groupEmpty ? [] : top.data?.results ?? []), [groupEmpty, top.data]);

  // Wiadomości dnia: dzisiejsze doniesienia z wiodących źródeł (`mode=top`), niezależne od filtrów paska.
  const dayLabel = useTodayLabel({ weekday: "long", day: "numeric", month: "long" });
  const dayIds = useMemo(() => (dayGroup ? groupSources(activeSources(sources))[dayGroup].map((source) => source.id) : []), [sources, dayGroup]);
  const dayGroupEmpty = Boolean(dayGroup) && sources.length > 0 && dayIds.length === 0;
  const day = useHomeFeed("day-top", { mode: "top", sources: dayIds, pageSize: 13 }, { refetchInterval: 120_000, enabled: !dayGroupEmpty });
  const dayArticles = useMemo(() => day.data?.results ?? [], [day.data]);
  const dayEmpty = day.isSuccess && dayArticles.length === 0;
  // Dopóki wiodące media nie są aktywne (zgody), `mode=top` jest pusty — wtedy dzisiejsze doniesienia
  // aktywnych źródeł (instytucje publiczne), a gdy dziś jest ich mniej niż 3 — najnowsze materiały.
  const dayFallback = useHomeFeed("day-latest", { mode: "latest", sources: dayIds, pageSize: 40 }, { enabled: dayEmpty && !dayGroupEmpty });
  const fallbackToday = useMemo(() => {
    const today = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Warsaw" }).format(new Date());
    return (dayFallback.data?.results ?? []).filter(
      (article) => article.published_date && new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Warsaw" }).format(new Date(article.published_date)) === today,
    );
  }, [dayFallback.data]);
  const fallbackIsToday = fallbackToday.length >= 3;
  const leadArticles = dayGroupEmpty ? [] : dayEmpty ? (fallbackIsToday ? fallbackToday : dayFallback.data?.results ?? []).slice(0, 13) : dayArticles;

  useEffect(() => {
    if (q) bazaRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
  }, [q]);

  // Serie niemal identycznych doniesień jednego źródła zwinięte w jeden box („+N podobnych”).
  const leadCollapsed = useMemo(() => collapseSimilar(leadArticles), [leadArticles]);
  const leadMain = leadCollapsed[0]?.article ?? null;
  const related = leadCollapsed.slice(1, 13);

  return (
    <>
      <div className="sc-home">
        <h1 className="sc-sr-only">Wiadomości i ich kontekst</h1>
        <TopBar />
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
            <p className="sc-t-body-s sc-text-2 sc-home-top__note" role="status">Brak aktywnych źródeł w grupie „{sourceGroupLabel(sourceGroup)}”. {GROUP_EMPTY_HINT}</p>
          ) : null}
          {!groupEmpty && top.isSuccess && !latest.length && (topQuery || activeTopic) ? (
            <p className="sc-t-body-s sc-text-2 sc-home-top__note" role="status">Brak najnowszych materiałów dla tego wyboru.</p>
          ) : null}
          <HomeTicker articles={latest} loading={top.isPending && !groupEmpty} />
        </div>
        <HomeReveal>
          <HomeLead
            main={leadMain}
            related={related}
            fallback={dayEmpty && !fallbackIsToday}
            dateLabel={dayLabel}
            emptyNote={dayGroupEmpty && dayGroup ? `Brak aktywnych źródeł w grupie „${sourceGroupLabel(dayGroup)}”. ${GROUP_EMPTY_HINT}` : null}
            actions={
              <Dropdown
                label={dayGroup ? `Źródła: ${sourceGroupLabel(dayGroup)}` : "Źródła: wszystkie"}
                ariaLabel="Źródła Wiadomości dnia"
                mode="single"
                presentation="auto"
                triggerVariant="quiet"
                align="end"
                items={[{ value: "", label: "Wszystkie źródła" }, ...SOURCE_GROUPS]}
                value={dayGroup ?? ""}
                onChange={(value) => setDayGroup(parseSourceGroup(value as string))}
              />
            }
          />
        </HomeReveal>
        <HomeReveal>
          <HomeThreads sources={sources} />
        </HomeReveal>
        <HomeReveal>
          <HomeDrSpin thread={drSpin.data ?? null} />
        </HomeReveal>
        <HomePrzekazDnia government={config.data?.editorial.government ?? null} opposition={config.data?.editorial.opposition ?? null} />
        <HomeReveal>
          <HomeBaza ref={bazaRef} sources={sources} initialQuery={q} sourceGroup={sourceGroup} />
        </HomeReveal>
      </div>
    </>
  );
}
