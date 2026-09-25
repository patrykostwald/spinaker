"use client";

/**
 * ThreadView — nitka w dwóch układach (замечание владельца 24.09):
 *  - `columns`: po lewej duży materiał otwierający (`large`), po prawej przewijana pionowo lista
 *    kolejnych materiałów z datami (szyna dat + karty `mini`);
 *  - `row`: jedna kolumna na całą szerokość z przewijaniem poziomym (taśma `compact` z datami).
 * Przełącznik (`Segmented`) zapamiętuje wybór na urządzeniu (`localStorage`); przejście między
 * układami to morfing tych samych kart (`layoutId` per materiał w jednej `LayoutGroup`).
 * Posty-odnośniki (`reference_only`) i komentarze autora renderują się tak samo w obu układach.
 */

import { LayoutGroup, motion } from "framer-motion";
import { useEffect, useId, useMemo, useState } from "react";
import { NewsCard, type NewsCardSize } from "./NewsCard";
import { Segmented } from "./Segmented";
import { Strip } from "./home/Strip";
import { useMotionTokens } from "./motion/useMotionTokens";
import { formatDatePl } from "../lib/utils";
import type { ThreadItem } from "../types";

export type ThreadLayout = "columns" | "row";

export type ThreadViewProps = {
  items: ThreadItem[];
  /** Pierwszy materiał to wydarzenie główne (nitka redakcyjna), nie najstarsze źródło. */
  anchorFirst?: boolean;
  /** Układ startowy, gdy nic nie zapisano. @default "columns" */
  defaultLayout?: ThreadLayout;
  /** Klucz `localStorage` — różne miejsca mogą pamiętać własny wybór. */
  storageKey?: string;
  /** Ukrywa przełącznik (np. gdy sekcja sama steruje układem). */
  layout?: ThreadLayout;
  onLayoutChange?: (layout: ThreadLayout) => void;
  /** Ile materiałów pokazać poza otwierającym (strona główna ogranicza). */
  maxItems?: number;
  className?: string;
};

const LAYOUT_OPTIONS = [
  { value: "columns", label: "Dwie kolumny" },
  { value: "row", label: "Jeden rząd" },
];

function readStored(key: string, fallback: ThreadLayout): ThreadLayout {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw === "columns" || raw === "row" ? raw : fallback;
  } catch {
    return fallback;
  }
}

function ItemNote({ item }: { item: ThreadItem }) {
  if (!item.editorial_note) return null;
  return (
    <p className="sc-thread-view__note sc-t-body-s sc-text-2">
      <strong>Komentarz autora: </strong>
      {item.editorial_note}
    </p>
  );
}

function ReferencePost({ item }: { item: ThreadItem }) {
  return (
    <div className="sc-thread-view__reference">
      <p className="sc-t-caption sc-text-3">Post · odnośnik X</p>
      <p className="sc-t-body-s sc-text-2">Treść i dostępność posta nie zostały sprawdzone. Materiał wskazał autor nitki.</p>
      <a className="sc-thread-view__source sc-t-meta" href={item.article.url} target="_blank" rel="noopener noreferrer">
        Otwórz post na X ↗
      </a>
    </div>
  );
}

function ItemCard({ item, size, headingLevel, expandable = true }: { item: ThreadItem; size: NewsCardSize; headingLevel: 2 | 3 | 4; expandable?: boolean }) {
  if (item.article.reference_only) return <ReferencePost item={item} />;
  return <NewsCard article={item.article} size={size} headingLevel={headingLevel} showDescription={size !== "mini"} expandable={expandable} />;
}

function dateLabel(item: ThreadItem, index: number, anchorFirst: boolean): string {
  if (anchorFirst && index === 0) return "Wydarzenie główne";
  return formatDatePl(item.article.published_date) || "Data nieustalona";
}

export function ThreadView({
  items,
  anchorFirst = false,
  defaultLayout = "columns",
  storageKey = "spinclinic-thread-layout",
  layout: controlled,
  onLayoutChange,
  maxItems,
  className,
}: ThreadViewProps) {
  const m = useMotionTokens();
  const groupId = useId();
  const [stored, setStored] = useState<ThreadLayout>(defaultLayout);
  useEffect(() => {
    setStored(readStored(storageKey, defaultLayout));
  }, [storageKey, defaultLayout]);
  const layout = controlled ?? stored;

  function choose(next: string) {
    const value = next as ThreadLayout;
    setStored(value);
    try {
      window.localStorage.setItem(storageKey, value);
    } catch {
      /* tryb prywatny */
    }
    onLayoutChange?.(value);
  }

  const ordered = useMemo(() => {
    const sorted = [...items].sort((a, b) => a.position - b.position);
    return maxItems ? sorted.slice(0, maxItems + 1) : sorted;
  }, [items, maxItems]);

  if (!ordered.length) return <p className="sc-t-body sc-text-2">Brak dostępnych materiałów w tym wątku.</p>;

  const [anchor, ...rest] = ordered;
  const layoutT = m.t("move");

  return (
    <LayoutGroup id={`thread-${groupId}`}>
      <section className={["sc-thread-view", className].filter(Boolean).join(" ")} data-layout={layout} aria-label="Materiały nitki">
        <header className="sc-thread-view__head">
          <p className="sc-t-meta sc-text-2">
            {anchorFirst ? "Wydarzenie główne, dalej kontekst od najstarszego źródła" : "Od najstarszego źródła"} · {ordered.length} materiałów
          </p>
          {controlled === undefined || onLayoutChange ? (
            <Segmented name={`thread-layout-${groupId}`} label="Układ nitki" value={layout} onChange={choose} options={LAYOUT_OPTIONS} />
          ) : null}
        </header>

        {layout === "columns" ? (
          <div className="sc-thread-view__columns">
            <motion.div className="sc-thread-view__anchor" layout="position" layoutId={`${groupId}-item-${anchor.id}`} transition={layoutT}>
              <p className="sc-thread-view__date sc-t-meta">{dateLabel(anchor, 0, anchorFirst)}</p>
              {anchor.is_sponsored ? <p className="sc-t-caption sc-text-3">{anchor.sponsorship_label || "Nitka sponsorowana"}</p> : null}
              {anchor.article.reference_only ? (
                <ReferencePost item={anchor} />
              ) : (
                <NewsCard article={anchor.article} size="large" headingLevel={2} eyebrow={anchorFirst ? "Wydarzenie główne" : "Początek nitki"} priority />
              )}
              <ItemNote item={anchor} />
            </motion.div>
            <div className="sc-thread-view__list-wrap">
              <ol className="sc-thread-view__list" role="list" aria-label="Kolejne materiały nitki" tabIndex={0}>
                {rest.map((item, index) => (
                  <motion.li key={item.id} className="sc-thread-view__row" layout="position" layoutId={`${groupId}-item-${item.id}`} transition={layoutT}>
                    <span className="sc-thread-view__rail" aria-hidden="true" />
                    <p className="sc-thread-view__date sc-t-meta">{dateLabel(item, index + 1, anchorFirst)}</p>
                    {item.is_sponsored ? <p className="sc-t-caption sc-text-3">{item.sponsorship_label || "Nitka sponsorowana"}</p> : null}
                    <ItemCard item={item} size="mini" headingLevel={3} />
                    <ItemNote item={item} />
                  </motion.li>
                ))}
                {!rest.length ? <li className="sc-t-body-s sc-text-2">Nitka ma na razie jeden materiał.</li> : null}
              </ol>
            </div>
          </div>
        ) : (
          <Strip label="Materiały nitki" slot="min(19rem, 82vw)" className="sc-thread-view__row-strip">
            {ordered.map((item, index) => (
              <motion.div key={item.id} className="sc-strip__slot sc-thread-view__slot" layout="position" layoutId={`${groupId}-item-${item.id}`} transition={layoutT}>
                <div className="sc-thread-view__slot-inner">
                  <p className="sc-thread-view__date sc-thread-view__date--top sc-t-meta">
                    <span className="sc-thread-view__dot" aria-hidden="true" />
                    {dateLabel(item, index, anchorFirst)}
                  </p>
                  {item.is_sponsored ? <p className="sc-t-caption sc-text-3">{item.sponsorship_label || "Nitka sponsorowana"}</p> : null}
                  {/* W taśmie bez spadu karta nie rośnie na najechanie — przycięłoby ją przewijanie. */}
                  <ItemCard item={item} size="compact" headingLevel={3} expandable={false} />
                  <ItemNote item={item} />
                </div>
              </motion.div>
            ))}
          </Strip>
        )}
      </section>
    </LayoutGroup>
  );
}
