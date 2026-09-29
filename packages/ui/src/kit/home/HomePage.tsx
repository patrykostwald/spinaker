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
import { HomeSupport } from "./HomeSupport";
import { NewsCard } from "../NewsCard";
import { EmptySlot } from "./Strip";
import { expandCategories } from "../../lib/categoryGroups";
import { HomeCategoryBar } from "./HomeCategoryBar";
import { HomeSpinTeaser } from "./HomeSpinTeaser";
import { HomeDrSpin } from "./HomeDrSpin";
import { HomeHero } from "./HomeHero";
import { HomeReveal } from "./HomeReveal";
import { HomeThreads } from "./HomeThreads";
import { NewsletterSignup } from "../../components/NewsletterSignup";
import { JournalistInvite } from "../../components/JournalistInvite";
import { collapseSimilar } from "./collapseSimilar";
import { useDemoMode, useDrSpinThread, useHomeConfig, useHomeFeed } from "./data";
import { GROUP_EMPTY_HINT, SOURCE_GROUPS, SOURCE_GROUP_PARAM, activeSources, groupSources, parseSourceGroup, sourceGroupLabel, type SourceGroup } from "./sourceGroups";

const NEWS_TYPES = [
  { value: null, label: "Wszystkie", groups: [] },
  { value: "video", label: "Wideo i TV", groups: ["film", "wywiad", "podcast"] },
  { value: "official", label: "Komunikaty urzędowe", groups: ["publiczne"] },
  { value: "articles", label: "Artykuły", groups: ["artykul", "reportaz"] },
];

function DemoBanner() {
  const demo = useDemoMode();
  if (!demo) return null;
  return (
    <p className="sc-home-demo sc-t-meta" role="status">
      <strong>Dane demonstracyjne.</strong> Backend jest niedostępny — materiały poniżej są FIKCYJNE i służą tylko do pracy nad układem.
    </p>
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
  const [activeType, setActiveType] = useState<string | null>(null);
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

  // Wiadomości: typ materiału, grupa źródeł i hasło zawężają wyniki przez API.
  const top = useHomeFeed(
    "top10",
    { mode: "latest", categories: expandCategories(NEWS_TYPES.find((type) => type.value === activeType)?.groups ?? []), sources: groupIds, query: topQuery, pageSize: 20, diverse: true },
    { refetchInterval: 30_000, enabled: !groupEmpty },
  );
  const latest = useMemo(() => (groupEmpty ? [] : top.data?.results ?? []), [groupEmpty, top.data]);
  const newsGrid = useMemo(() => collapseSimilar(latest).slice(0, 6), [latest]);

  const newsIds = useMemo(() => new Set(newsGrid.map(({ article }) => article.id)), [newsGrid]);

  useEffect(() => {
    if (q) bazaRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
  }, [q]);


  return (
    <>
      <div className="sc-home">
        <h1 className="sc-sr-only">Wiadomości i ich kontekst</h1>
        <DemoBanner />
        <HomeHero />
        {/* 1. Dr. Spin — po co tu jesteś. 2. Wiadomości — agregat z naszej Bazy do przeglądania i własnych pasków.
            3. Dla dziennikarzy. 4. Baza. 5. Newsletter (decyzja właściciela 28.09). */}
        <HomeSpinTeaser />
        <section className="sc-home-section sc-home-news" aria-labelledby="home-news-title">
          <header className="sc-home-news__head">
            <div>
              <p className="sc-t-caption sc-text-3 sc-home-kicker">Materiały ze źródeł. Każda karta prowadzi do oryginalnej publikacji.</p>
              <h2 id="home-news-title" className="sc-t-title-l sc-home-section__title">Wiadomości</h2>
            </div>
          </header>
          <HomeCategoryBar
            items={NEWS_TYPES}
            label="Typ materiału"
            value={activeType}
            onChange={setActiveType}
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
          {!groupEmpty && top.isSuccess && !latest.length ? (
            <p className="sc-t-body-s sc-text-2 sc-home-top__note" role="status">{topQuery || activeType || sourceGroup ? <>Nie znaleźliśmy pasujących materiałów. <button type="button" onClick={() => { setKeyword(""); setTopQuery(""); setActiveType(null); setSourceGroup(null); }}>Wyczyść filtry</button></> : "Nie ma jeszcze opublikowanych materiałów."}</p>
          ) : null}
          {!groupEmpty && top.isError ? <p role="alert">{top.data ? `Pokazujemy dane z ${new Date(top.dataUpdatedAt).toLocaleString("pl-PL")}. Aktualizacja jest chwilowo niedostępna.` : "Nie udało się pobrać danych."} <button type="button" onClick={() => void top.refetch()}>Spróbuj ponownie</button></p> : null}
          {/* Karty średniej wielkości — bez olbrzymiego boxu, w którym miniatury się rozmywały. */}
          <ul className="sc-home-news__grid" role="list">
            {newsGrid.map(({ article, similar }) => (
              <li key={article.id}><NewsCard article={article} size="medium" headingLevel={3} similarCount={similar} expandable={false} /></li>
            ))}
            {!groupEmpty && !newsGrid.length && top.isPending ? Array.from({ length: 3 }, (_, index) => <li key={index}><EmptySlot index={index + 1} label="Ładuję…" /></li>) : null}
          </ul>
        </section>
        <HomeReveal>
          <HomeThreads sources={sources} excludedArticleIds={newsIds} />
        </HomeReveal>
        {/* Nitka Dr. Spina — pokazuje, czym są nitki kontekstowe; z paskiem dla dziennikarzy (28.09). */}
        <HomeReveal>
          <HomeDrSpin thread={drSpin.data ?? null} />
        </HomeReveal>
        <HomeReveal>
          <HomeBaza ref={bazaRef} sources={sources} initialQuery={q} sourceGroup={sourceGroup} />
        </HomeReveal>
        <HomeSupport />
        <NewsletterSignup source="home" />
      </div>
    </>
  );
}
