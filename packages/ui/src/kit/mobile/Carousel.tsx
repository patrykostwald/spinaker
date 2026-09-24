"use client";

/**
 * Carousel — pozioma lista z przyciąganiem (docs/UI_KIT_PLAN.md → «Mobilne rozkłady»,
 * «Karuzela» w opisie stoiska). `scroll-snap-type: x mandatory`, następny slajd wygląda na 16%
 * szerokości, `touch-action: pan-x` TYLKO na scrollerze. Slajd wyśrodkowany dostaje stopień A
 * (ta sama poświata `data-lit`, co w reszcie systemu) przez `useFocalBand` w osi poziomej.
 *
 * Uwaga właściciela (23.09), którą trzeba tu uszanować: rozwinięcie karty (stopień B) NIGDY nie
 * zmienia żadnego pudełka w potoku — również w karuzeli. Dlatego ten komponent sam niczego nie
 * rozszerza: dotknięcie wyśrodkowanego slajdu woła `onPreview(article, el)`, warstwa nad stroną
 * (R5 — PortalLayer) robi resztę, a karuzela nigdy nie zmienia swojej wysokości.
 *
 * Drabina dotyku, bo telefon nie ma najechania:
 *  1. dotknięcie slajdu NIE wyśrodkowanego → przewija go do środka (staje się focalny);
 *  2. dotknięcie slajdu JUŻ wyśrodkowanego → `onPreview` (stopień B, warstwa R5);
 *  3. dotknięcie slajdu, który już ma otwarty podgląd → `onOpen` (stopień C, pełny ekran).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "../../lib/utils";
import { NewsCard, type NewsCardSize } from "../NewsCard";
import { useMotionTokens } from "../motion/useMotionTokens";
import { ChevronLeftIcon } from "../icons/ChevronLeftIcon";
import { ChevronRightIcon } from "../icons/ChevronRightIcon";
import { useFocalBand } from "./useFocalBand";
import type { Article } from "../../types";

export type CarouselProps = {
  articles: Article[];
  size?: NewsCardSize;
  ariaLabel: string;
  /** Stopień B: dotknięcie już wyśrodkowanego slajdu. Rozszerzenie rysuje R5, w warstwie nad stroną. */
  onPreview?: (article: Article, el: HTMLElement) => void;
  /** Stopień C: dotknięcie slajdu, który już ma otwarty podgląd. */
  onOpen?: (article: Article) => void;
  className?: string;
};

export function Carousel({ articles, size = "medium", ariaLabel, onPreview, onOpen, className }: CarouselProps) {
  const m = useMotionTokens();
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  // `force: true` celowo, inaczej niż domyślne użycie w siatce: tu pasmo fokalne to nie tylko
  // zamiennik najechania, ale JEDYNE źródło "który slajd jest bieżący" — napędza strzałki, licznik
  // dla czytnika ekranu i drabinę A/B/C. Na desktopie realne :hover i tak włącza tę samą poświatę
  // (ten sam atrybut `data-lit`/`.sc-hoverable`), więc podwójne źródło nie koliduje wizualnie.
  const focalId = useFocalBand(scrollerRef, { axis: "x", force: true });
  const [previewedId, setPreviewedId] = useState<number | null>(null);

  // Zmiana slajdu focalnego (przewinięcie dalej) kasuje ślad "już podglądnięty" — kolejne
  // dotknięcie nowego slajdu znów zaczyna od stopnia B, nie przeskakuje do C.
  useEffect(() => {
    setPreviewedId(null);
  }, [focalId]);

  const index = useMemo(
    () => articles.findIndex((article) => String(article.id) === focalId),
    [articles, focalId],
  );

  function scrollToArticle(id: number) {
    const el = scrollerRef.current?.querySelector<HTMLElement>(`[data-material-id="${id}"]`);
    el?.scrollIntoView({ behavior: m.reduced ? "auto" : "smooth", inline: "center", block: "nearest" });
  }

  function handleCardOpen(article: Article) {
    const isFocal = String(article.id) === focalId;
    if (!isFocal) {
      scrollToArticle(article.id);
      return;
    }
    if (previewedId === article.id) {
      onOpen?.(article);
      return;
    }
    const el = scrollerRef.current?.querySelector<HTMLElement>(`[data-material-id="${article.id}"]`);
    setPreviewedId(article.id);
    if (el) onPreview?.(article, el);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const current = index < 0 ? 0 : index;
    const next = event.key === "ArrowRight" ? Math.min(articles.length - 1, current + 1) : Math.max(0, current - 1);
    const target = articles[next];
    if (target) scrollToArticle(target.id);
  }

  return (
    <div className={cn("sc-carousel", className)}>
      <div
        ref={scrollerRef}
        className="sc-carousel__scroller"
        role="region"
        aria-roledescription="karuzela"
        aria-label={ariaLabel}
        tabIndex={0}
        onKeyDown={handleKeyDown}
      >
        {articles.map((article) => (
          <NewsCard
            key={article.id}
            article={article}
            size={size}
            className="sc-carousel__slide"
            onOpen={handleCardOpen}
          />
        ))}
      </div>

      <button
        type="button"
        className="sc-carousel__arrow sc-carousel__arrow--prev sc-hoverable"
        aria-label="Poprzedni slajd"
        disabled={index <= 0}
        onClick={() => {
          const target = articles[Math.max(0, (index < 0 ? 0 : index) - 1)];
          if (target) scrollToArticle(target.id);
        }}
      >
        <ChevronLeftIcon size={20} />
      </button>
      <button
        type="button"
        className="sc-carousel__arrow sc-carousel__arrow--next sc-hoverable"
        aria-label="Następny slajd"
        disabled={index < 0 || index >= articles.length - 1}
        onClick={() => {
          const target = articles[Math.min(articles.length - 1, (index < 0 ? 0 : index) + 1)];
          if (target) scrollToArticle(target.id);
        }}
      >
        <ChevronRightIcon size={20} />
      </button>

      <div className="sc-visually-hidden" aria-live="polite" role="status">
        {index >= 0 ? `Slajd ${index + 1} z ${articles.length}` : ""}
      </div>
    </div>
  );
}
