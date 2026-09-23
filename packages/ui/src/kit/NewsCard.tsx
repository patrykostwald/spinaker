"use client";

/**
 * NewsCard — karta materiału. Jeden komponent, cztery rozmiary (docs/UI_KIT_PLAN.md → «Komponenty»,
 * «Karta newsowa», «Trzy stopnie», «Stopień B»).
 *
 * Stopnie interakcji:
 *  A — najechanie/fokus: natychmiastowe podświetlenie (scale, lewitacja, poświata z .sc-hoverable).
 *  B — tylko gdy `expandable`: po 400ms zamiaru (PREVIEW_DELAY_MS) karta rośnie i odsłania dodatkowy blok
 *      (opis, pełne źródło, link do oryginału); z klawiatury — natychmiast po fokusie.
 *  C — pełny ekran: właścicielem jest R5 (portal). Ten komponent tylko wywołuje `onOpen` i wystawia
 *      `data-material-id`, żeby R5 mógł znaleźć kartę; nie robi żadnego morfingu sam.
 *
 * Rozciągnięty link: jedyny <Link> siedzi w nagłówku; jego ::after (position:absolute; inset:0)
 * rozciąga obszar klikalny na całą kartę. `action` renderuje się PO nim w drzewie DOM, więc naturalnie
 * łapie kliknięcia mimo nakładającego się pseudo-elementu (kolejność w DOM > pseudo bez z-index).
 */

import Image from "next/image";
import Link from "next/link";
import { AnimatePresence, motion, type Transition } from "framer-motion";
import {
  useEffect,
  useRef,
  useState,
  type FocusEvent,
  type MouseEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { useMotionTokens } from "./motion/useMotionTokens";
import { CARD_SPEC, HOVER_SCALE, PREVIEW_DELAY_MS, type CardSize } from "./tokens";
import { categoryLabel, cn, formatDateTimePl, formatShortDatePl, formatTimePl, materialTypeLabel } from "../lib/utils";
import type { Article } from "../types";

export type NewsCardSize = CardSize;

export type NewsCardProps = {
  article: Article;
  /** @default 'compact' */
  size?: NewsCardSize;
  /** @default `/material/${article.id}` */
  href?: string;
  /** Wywołujący jest właścicielem struktury nagłówków strony. @default 3 (h3) */
  headingLevel?: 2 | 3 | 4;
  showCategory?: boolean;
  showDescription?: boolean;
  /** Tylko `large`; `split` ma efekt dopiero od ≥900px, poniżej degraduje do `stack` samą kaskadą CSS. */
  layout?: "stack" | "split";
  priority?: boolean;
  eyebrow?: ReactNode;
  /** Renderowany POZA linkiem, jako rodzeństwo z własnym stackingiem (np. ulubione). */
  action?: ReactNode;
  /** Portal (R5) podpina się tutaj; bez tego propa link działa zwykłą nawigacją <Link>. */
  onOpen?: (article: Article) => void;
  /** Włącza stopień B w zwykłej siatce. Ленты z przycięciem robi R5 przez PortalLayer. */
  expandable?: boolean;
  className?: string;
};

type Stage = "rest" | "a" | "b";

const TITLE_CLASS: Record<NewsCardSize, string> = {
  mini: "sc-t-title-xs",
  compact: "sc-t-title-s",
  medium: "sc-t-title-m",
  large: "sc-t-title-l",
};

const IMAGE_SIZES: Record<NewsCardSize, string> = {
  mini: "64px",
  compact: "(max-width: 640px) 100vw, 360px",
  medium: "(max-width: 900px) 100vw, 420px",
  large: "100vw",
};

/** Punkt wzrostu ustalany raz przy wejściu w hover/fokus — karty przy krawędzi rosną do wewnątrz. */
function computeOrigin(el: HTMLElement): string {
  if (typeof window === "undefined") return "50% 50%";
  const rect = el.getBoundingClientRect();
  const x = rect.left < 24 ? "0%" : window.innerWidth - rect.right < 24 ? "100%" : "50%";
  const y = rect.top < 24 ? "0%" : "50%";
  return `${x} ${y}`;
}

function renderDate(article: Article, size: NewsCardSize) {
  const iso = article.published_date;
  const real = !!iso && iso !== "undated" && iso !== "unknown";
  if (real) {
    if (size === "mini") return <time dateTime={iso}>{formatTimePl(iso)}</time>;
    if (size === "compact") return <time dateTime={iso}>{formatShortDatePl(iso)}</time>;
    return <time dateTime={iso}>{formatDateTimePl(iso, article.date_precision)}</time>;
  }
  const label = size === "mini" || size === "compact" ? "Data nieustalona" : "Data publikacji nieustalona";
  return <span>{label}</span>;
}

function CardBadge({ category }: { category: string }) {
  return <span className="sc-card__badge sc-t-caption">{categoryLabel(category)}</span>;
}

function CardMedia({
  article,
  size,
  showCategory,
  priority,
  thumbScale,
  transition,
}: {
  article: Article;
  size: NewsCardSize;
  showCategory: boolean;
  priority?: boolean;
  thumbScale: number;
  transition: Transition;
}) {
  const src = article.image_url?.trim();
  return (
    <div className="sc-card__media">
      {src ? (
        <motion.div className="sc-card__media-inner" animate={{ scale: thumbScale }} transition={transition}>
          <Image src={src} alt="" fill unoptimized priority={priority} sizes={IMAGE_SIZES[size]} className="sc-card__image" />
        </motion.div>
      ) : (
        <span className="sc-card__placeholder sc-t-caption" aria-hidden="true">
          {materialTypeLabel(article.category)}
        </span>
      )}
      {size !== "mini" && showCategory ? <CardBadge category={article.category} /> : null}
    </div>
  );
}

function CardMeta({ article, size }: { article: Article; size: NewsCardSize }) {
  return (
    <p className="sc-card__meta sc-t-meta sc-text-2">
      <span className="sc-card__meta-source">{article.source.name}</span>
      {size === "large" && article.author ? <span> · {article.author}</span> : null}
      <span> · </span>
      {renderDate(article, size)}
    </p>
  );
}

export function NewsCard({
  article,
  size = "compact",
  href,
  headingLevel = 3,
  showCategory = true,
  showDescription,
  layout = "stack",
  priority,
  eyebrow,
  action,
  onOpen,
  expandable = false,
  className,
}: NewsCardProps) {
  const motionTokens = useMotionTokens();
  const cardRef = useRef<HTMLElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [stage, setStage] = useState<Stage>("rest");
  const [origin, setOrigin] = useState("50% 50%");
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    const node = cardRef.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      setEntered(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setEntered(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.1 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  const spec = CARD_SPEC[size];
  const staticDescription = showDescription ?? (size === "medium" || size === "large");
  const resolvedHref = href ?? `/material/${article.id}`;
  const Heading = `h${headingLevel}` as "h2" | "h3" | "h4";

  function clearTimer() {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function enter(el: HTMLElement) {
    setEntered(true);
    setOrigin(computeOrigin(el));
    setStage("a");
    clearTimer();
    if (expandable) {
      timerRef.current = setTimeout(() => setStage("b"), PREVIEW_DELAY_MS);
    }
  }

  function leave() {
    clearTimer();
    setStage("rest");
  }

  function handlePointerEnter(e: PointerEvent<HTMLElement>) {
    if (e.pointerType !== "mouse") return;
    enter(e.currentTarget);
  }
  function handlePointerLeave(e: PointerEvent<HTMLElement>) {
    if (e.pointerType !== "mouse") return;
    leave();
  }
  function handleFocus(e: FocusEvent<HTMLElement>) {
    setEntered(true);
    setOrigin(computeOrigin(e.currentTarget));
    clearTimer();
    setStage(expandable ? "b" : "a");
  }
  function handleBlur(e: FocusEvent<HTMLElement>) {
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    clearTimer();
    setStage("rest");
  }
  function handleLinkClick(e: MouseEvent<HTMLAnchorElement>) {
    if (!onOpen) return;
    const plainLeftClick = e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
    if (plainLeftClick) {
      e.preventDefault();
      onOpen(article);
    }
  }

  const uiTransition = motionTokens.t("ui");
  const scale = stage === "b" ? motionTokens.scale(spec.previewScale) : stage === "a" ? motionTokens.scale(HOVER_SCALE) : 1;
  const lift = stage === "rest" ? (entered ? 0 : motionTokens.rise) : motionTokens.reduced ? 0 : -spec.lift;
  const thumbScale = stage === "rest" ? 1 : motionTokens.scale(1.04);
  const expandRise = motionTokens.reduced ? 0 : 6;

  const expandItems: ReactNode[] = [];
  if (!staticDescription && article.description) {
    expandItems.push(
      <p key="desc" className="sc-card__expand-desc sc-t-body-s">
        {article.description}
      </p>,
    );
  }
  expandItems.push(
    <p key="meta" className="sc-card__expand-meta sc-t-meta sc-text-2">
      {article.source.name}
      {article.author ? ` · ${article.author}` : ""}
      {" · "}
      {formatDateTimePl(article.published_date, article.date_precision)}
    </p>,
  );
  if (article.url) {
    expandItems.push(
      <a key="src" href={article.url} target="_blank" rel="noopener noreferrer" className="sc-card__expand-link sc-t-meta">
        Źródło oryginalne ↗
      </a>,
    );
  }

  return (
    <motion.article
      ref={cardRef}
      data-size={size}
      data-stage={stage}
      data-layout={size === "large" ? layout : undefined}
      data-expandable={expandable || undefined}
      data-material-id={article.id}
      className={cn("sc-card sc-hoverable", className)}
      style={{ transformOrigin: origin, zIndex: stage === "b" ? 30 : undefined }}
      layout="position"
      animate={{ opacity: entered ? 1 : 0, scale, y: lift }}
      transition={{ default: uiTransition, layout: motionTokens.t("move") }}
      exit={{ opacity: 0, scale: motionTokens.scale(0.96), transition: motionTokens.t("collapse") }}
      whileTap={{ scale: motionTokens.scale(0.97), transition: motionTokens.t("press") }}
      onPointerEnter={handlePointerEnter}
      onPointerLeave={handlePointerLeave}
      onFocus={handleFocus}
      onBlur={handleBlur}
    >
      {eyebrow ? <span className="sc-card__eyebrow sc-t-caption">{eyebrow}</span> : null}

      <CardMedia article={article} size={size} showCategory={showCategory} priority={priority} thumbScale={thumbScale} transition={uiTransition} />

      <div className="sc-card__body">
        {size === "mini" && showCategory ? (
          <span className="sc-card__category sc-t-caption sc-text-3">{categoryLabel(article.category)}</span>
        ) : null}

        <Heading className="sc-card__title">
          <Link href={resolvedHref} className={cn("sc-card__link", TITLE_CLASS[size])} onClick={handleLinkClick}>
            {article.title}
          </Link>
        </Heading>

        {staticDescription && article.description ? (
          <p className="sc-card__description sc-t-body-s sc-text-2">{article.description}</p>
        ) : null}

        <CardMeta article={article} size={size} />

        <AnimatePresence initial={false}>
          {expandable && stage === "b" ? (
            <motion.div className="sc-card__expand">
              {expandItems.map((node, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: expandRise }}
                  animate={{ opacity: 1, y: 0, transition: { ...motionTokens.t("expand"), delay: motionTokens.reduced ? 0 : i * 0.03 } }}
                  exit={{ opacity: 0, y: 0, transition: motionTokens.t("collapse") }}
                >
                  {node}
                </motion.div>
              ))}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      {action ? <div className="sc-card__action">{action}</div> : null}
    </motion.article>
  );
}
