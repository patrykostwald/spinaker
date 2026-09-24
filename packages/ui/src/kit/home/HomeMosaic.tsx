"use client";

/**
 * „Wszystkie źródła” (TOP 10) — wzór: mozaika „Don't Miss” + lista „Top Stories”.
 * Po lewej: jeden `large` + cztery `medium` (2×2); po prawej: pięć `mini` z numerami 1–5.
 * Filtry z dawnego paska (dropdown źródeł `multi`, pole hasła) siedzą w nagłówku sekcji;
 * temat przychodzi z paska tematów pod szapką.
 */

import { useMemo, useState } from "react";
import { Button } from "../Button";
import { Dropdown } from "../Dropdown";
import { NewsCard } from "../NewsCard";
import { SearchField } from "../SearchField";
import type { Article, Source } from "../../types";
import { useHomeFeed } from "./data";
import { EmptySlot } from "./Strip";

const EMPTY_TYPES = ["Artykuł", "Wywiad", "Reportaż", "Śledztwo", "Dokument urzędowy", "Reklama", "Film", "Fact-check", "Podcast", "Komunikat"];

export function HomeMosaic({ sources, topic, onArticles }: { sources: Source[]; topic: string | null; onArticles?: (articles: Article[]) => void }) {
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const numericSources = sourceIds.map(Number);

  const feed = useHomeFeed(
    "top10",
    { mode: "latest", topics: topic ? [topic] : [], sources: numericSources, query, pageSize: 10 },
    { refetchInterval: 30_000 },
  );
  const articles = useMemo(() => feed.data?.results ?? [], [feed.data]);
  useMemo(() => onArticles?.(articles), [articles, onArticles]);

  const slots = Array.from({ length: 10 }, (_, i) => articles[i] ?? null);
  const selectedSources = sources.filter((source) => numericSources.includes(source.id));

  const cell = (index: number, size: "large" | "medium") => {
    const article = slots[index];
    return article ? (
      <NewsCard key={article.id} article={article} size={size} headingLevel={3} />
    ) : (
      <EmptySlot key={`empty-${index}`} index={index + 1} label={EMPTY_TYPES[index % EMPTY_TYPES.length]} />
    );
  };

  return (
    <section id="zrodla-top" className="sc-home-section sc-home-mosaic" aria-label="Wszystkie źródła">
      <header className="sc-home-section__head">
        <div>
          <h2 className="sc-t-title-l sc-home-section__title">Wszystkie źródła</h2>
          <p className="sc-t-body-s sc-text-2">
            Najnowsze materiały z {selectedSources.length ? selectedSources.map((s) => s.name).join(" · ") : "wszystkich aktywnych źródeł"}
            {query ? ` · „${query}”` : ""}
          </p>
        </div>
        <div className="sc-home-section__actions">
          <Dropdown
            label={selectedSources.length ? `Źródła (${selectedSources.length})` : "Wszystkie źródła"}
            ariaLabel="Filtruj źródła"
            mode="multi"
            presentation="auto"
            align="end"
            items={sources.map((source) => ({ value: String(source.id), label: source.name }))}
            value={sourceIds}
            onChange={(value) => setSourceIds(value as string[])}
            footer={
              sourceIds.length ? (
                <Button variant="quiet" size="sm" onClick={() => setSourceIds([])}>
                  Wyczyść
                </Button>
              ) : (
                <span className="sc-t-caption sc-text-3">{sources.length ? `${sources.length} źródeł` : "Lista źródeł nie jest jeszcze dostępna."}</span>
              )
            }
          />
          <SearchField value={query} onChange={setQuery} placeholder="Szukaj hasła…" label="Szukaj hasła w najnowszych materiałach" className="sc-home-mosaic__search" />
          <Button href="/#baza" variant="quiet" size="sm">
            Zobacz wszystko
          </Button>
        </div>
      </header>

      <div className="sc-home-mosaic__grid">
        <div className="sc-home-mosaic__hero">{cell(0, "large")}</div>
        <div className="sc-home-mosaic__tiles">{[1, 2, 3, 4].map((i) => cell(i, "medium"))}</div>
        <aside className="sc-home-mosaic__list" aria-label="Materiały 6–10">
          <header className="sc-home-lead__panel-head">
            <h3 className="sc-t-title-s">Kolejne materiały</h3>
          </header>
          <ol className="sc-home-ranked" role="list">
            {[5, 6, 7, 8, 9].map((i) => (
              <li key={slots[i]?.id ?? `empty-${i}`} className="sc-home-ranked__item">
                <span className="sc-home-ranked__num sc-t-title-l" aria-hidden="true">
                  {i + 1}
                </span>
                {slots[i] ? <NewsCard article={slots[i]!} size="mini" headingLevel={4} showCategory={false} /> : <EmptySlot index={i + 1} label={EMPTY_TYPES[i]} />}
              </li>
            ))}
          </ol>
        </aside>
      </div>
      {feed.isError ? (
        <p className="sc-home-caption sc-t-meta sc-text-2">
          Nie udało się odświeżyć materiałów.{" "}
          <button type="button" className="sc-home-linkbtn" onClick={() => feed.refetch()}>
            Ponów
          </button>
        </p>
      ) : null}
    </section>
  );
}
