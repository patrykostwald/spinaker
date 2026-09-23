"use client";

/**
 * NewsCard — karta materiału. Jeden komponent, cztery rozmiary (docs/UI_KIT_PLAN.md → «Komponenty»,
 * «Karta newsowa», «Trzy stopnie», «Stopień B»).
 *
 * Budowa (R0, 24.09 — замечание владельца: «не клон, а сам элемент меняет форму»):
 *  <article.sc-card-slot>  — MIEJSCE w siatce: nigdy nie zmienia rozmiaru (na stopniu B wysokość jest
 *                            zablokowana inline), więc sąsiedzi ani sekcja nie drgną («Слой выше, а не поток»).
 *    <div.sc-card>         — sama KARTA: tło, promień, poświata, cała treść. Na stopniu B wychodzi z potoku
 *                            (position:absolute w obrębie slotu, z-index nad siatką) i ZMIENIA FORMĘ — ten sam
 *                            element, framer-motion `layout` projektuje korzeń i każde dziecko (media, tytuł,
 *                            meta) ze starego pudełka do nowego na sprężynie `expand` (bounce 0.22).
 *
 * Stopnie:
 *  A — najechanie/fokus: natychmiast (scale, lewitacja, poświata przez --sc-ring).
 *  B — po 400ms zamiaru (PREVIEW_DELAY_MS), z klawiatury natychmiast: karta rośnie w formę własną dla
 *      swojego rozmiaru (mini — szerzej, w wierszu; compact/medium — w dół; large — w miejscu), ale z tym
 *      samym zestawem treści: media → tytuł → opis → źródło · data → ulubione (serce). Uchodząc ze
 *      stopnia B wraca tą samą drogą (`collapse`, bez odbicia).
 *  C — pełny ekran: portal (R5) czyta pudełko `.sc-card` (już rozrośnięte, jeśli trwa B) i morfuje z niego
 *      powierzchnię; wewnątrz `PortalProvider` karta podpina się do portalu sama (`usePortalApiOptional`).
 *
 * Rozciągnięty link: jedyny <Link> siedzi w nagłówku; jego ::after rozciąga obszar klikalny na kartę.
 * `action`/serce renderują się PO nim w DOM, więc łapią kliknięcia mimo nakładającego się pseudo-elementu.
 */

import Image from "next/image";
import Link from "next/link";
import { AnimatePresence, motion, type Transition } from "framer-motion";
import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FocusEvent,
  type MouseEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { HeartIcon } from "./icons/HeartIcon";
import { useMotionTokens } from "./motion/useMotionTokens";
import { usePortalApiOptional } from "./portal/PortalProvider";
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
  /** Renderowany POZA linkiem, jako rodzeństwo z własnym stackingiem (np. ulubione). Zastępuje wbudowane serce. */
  action?: ReactNode;
  /** Bez tego propa: wewnątrz PortalProvider — portal; poza nim — zwykła nawigacja <Link>. */
  onOpen?: (article: Article) => void;
  /** Włącza stopień B. @default true */
  expandable?: boolean;
  className?: string;
};

type Stage = "rest" | "a" | "b";

/** Geometria stopnia B, liczona RAZ przy wejściu w hover/fokus (rozmiar slotu nie może się już zmienić). */
type Lock = { width: number; height: number; targetWidth: number; left: number; top: number };

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

const VIEWPORT_MARGIN = 16;

/**
 * Pudełko stopnia B: szerokość wg `CARD_SPEC[size].grow`, rośnie od środka, a przy krawędzi okna —
 * do wewnątrz. `offsetWidth/Height` (bez transformacji stopnia A), krawędzie okna — z rect.
 */
function computeLock(el: HTMLElement, size: NewsCardSize): Lock {
  const rect = el.getBoundingClientRect();
  const width = el.offsetWidth;
  const height = el.offsetHeight;
  const { grow } = CARD_SPEC[size];
  const vw = window.innerWidth;
  const targetWidth = Math.min(Math.round(width * grow.scale + grow.extra), vw - VIEWPORT_MARGIN * 2);
  let left = (width - targetWidth) / 2;
  if (rect.left + left < VIEWPORT_MARGIN) left = VIEWPORT_MARGIN - rect.left;
  if (rect.left + left + targetWidth > vw - VIEWPORT_MARGIN) left = vw - VIEWPORT_MARGIN - targetWidth - rect.left;
  return { width, height, targetWidth, left, top: 0 };
}

function renderDate(article: Article, size: NewsCardSize | "full") {
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

function CardBadge({ category, transition }: { category: string; transition: Transition }) {
  return (
    <motion.span className="sc-card__badge sc-t-caption" layout="position" transition={transition}>
      {categoryLabel(category)}
    </motion.span>
  );
}

function CardMedia({
  article,
  size,
  showCategory,
  priority,
  thumbScale,
  transition,
  layoutTransition,
}: {
  article: Article;
  size: NewsCardSize;
  showCategory: boolean;
  priority?: boolean;
  thumbScale: number;
  transition: Transition;
  layoutTransition: Transition;
}) {
  const src = article.image_url?.trim();
  return (
    <motion.div className="sc-card__media" layout transition={layoutTransition}>
      {src ? (
        <motion.div className="sc-card__media-inner" layout animate={{ scale: thumbScale }} transition={{ default: transition, layout: layoutTransition }}>
          <Image src={src} alt="" fill unoptimized priority={priority} sizes={IMAGE_SIZES[size]} className="sc-card__image" />
        </motion.div>
      ) : (
        <span className="sc-card__placeholder sc-t-caption" aria-hidden="true">
          {materialTypeLabel(article.category)}
        </span>
      )}
      {size !== "mini" && showCategory ? <CardBadge category={article.category} transition={layoutTransition} /> : null}
    </motion.div>
  );
}

function CardMeta({ article, size, full, transition }: { article: Article; size: NewsCardSize; full: boolean; transition: Transition }) {
  return (
    <motion.p className="sc-card__meta sc-t-meta sc-text-2" layout="position" transition={transition}>
      <span className="sc-card__meta-source">{article.source.name}</span>
      {(size === "large" || full) && article.author ? <span> · {article.author}</span> : null}
      <span> · </span>
      {renderDate(article, full ? "full" : size)}
    </motion.p>
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
  onOpen: onOpenProp,
  expandable = true, // R0: ступень B — штатное поведение, не опция (замечание владельца 23.09)
  className,
}: NewsCardProps) {
  const motionTokens = useMotionTokens();
  const slotRef = useRef<HTMLElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const linkRef = useRef<HTMLAnchorElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lockRef = useRef<Lock | null>(null);
  const releaseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [stage, setStage] = useState<Stage>("rest");
  // `lock` żyje od wejścia w hover do KOŃCA animacji zwijania: dopóki karta się kurczy, zostaje
  // absolutna w pudełku spoczynku (a slot ma zablokowaną wysokość) — inaczej wracałaby do potoku
  // z jeszcze gasnącym opisem i na ~250 ms rozpychała siatkę (замечание владельца 24.09).
  const [lock, setLock] = useState<Lock | null>(null);
  const [collapsing, setCollapsing] = useState(false);
  const [entered, setEntered] = useState(false);
  const [favourite, setFavourite] = useState(false);

  // R0 (24.09): внутри PortalProvider карточка сама открывается через портал — клик везде даёт один и
  // тот же морфинг «карточка → полный экран → карточка», без пропов в каждом месте использования.
  const portal = usePortalApiOptional();
  const onOpen = onOpenProp ?? (portal ? (a: Article) => portal.open(a, slotRef.current) : undefined);

  useEffect(() => {
    const node = slotRef.current;
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
      if (releaseTimerRef.current) clearTimeout(releaseTimerRef.current);
    },
    [],
  );

  // Pionowe wyśrodkowanie stopnia B wymaga realnej wysokości rozrośniętej karty — mierzymy ją
  // synchronicznie po pierwszym renderze B (przed malowaniem klatki; framer trzyma migawkę „przed”
  // z tego samego commitu, więc animuje wciąż od pudełka spoczynku, a nie od pozycji tymczasowej).
  useLayoutEffect(() => {
    if (stage !== "b" || !lock || !cardRef.current || !slotRef.current || lock.top !== 0) return;
    const grownHeight = cardRef.current.offsetHeight;
    if (grownHeight <= lock.height) return;
    const slotTop = slotRef.current.getBoundingClientRect().top;
    const vh = window.innerHeight;
    let top = -(grownHeight - lock.height) / 2;
    if (slotTop + top < VIEWPORT_MARGIN) top = VIEWPORT_MARGIN - slotTop;
    if (slotTop + top + grownHeight > vh - VIEWPORT_MARGIN) top = Math.max(VIEWPORT_MARGIN - slotTop, vh - VIEWPORT_MARGIN - grownHeight - slotTop);
    if (Math.abs(top) < 1) return;
    const next = { ...lock, top };
    lockRef.current = next;
    setLock(next);
  }, [stage, lock]);

  const spec = CARD_SPEC[size];
  // large: w spoczynku TYLKO tytuł nad zdjęciem — opis, meta i serce dopiero na stopniu B (замечание владельца 24.09).
  const staticDescription = showDescription ?? size === "medium";
  const staticMeta = size !== "large";
  const resolvedHref = href ?? `/material/${article.id}`;
  const Heading = `h${headingLevel}` as "h2" | "h3" | "h4";

  function clearTimer() {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function arm(el: HTMLElement) {
    setEntered(true);
    if (releaseTimerRef.current) {
      clearTimeout(releaseTimerRef.current);
      releaseTimerRef.current = null;
    }
    setCollapsing(false);
    if (!lockRef.current) {
      lockRef.current = computeLock(el, size);
      setLock(lockRef.current);
    }
  }

  function enter(el: HTMLElement) {
    arm(el);
    setStage("a");
    clearTimer();
    if (expandable) timerRef.current = setTimeout(() => setStage("b"), PREVIEW_DELAY_MS);
  }

  function release() {
    if (releaseTimerRef.current) {
      clearTimeout(releaseTimerRef.current);
      releaseTimerRef.current = null;
    }
    lockRef.current = null;
    setLock(null);
    setCollapsing(false);
  }

  function leave() {
    clearTimer();
    if (stage === "b") {
      // Zwijanie: karta zostaje absolutna, ale w pudełku spoczynku — framer animuje ją tam
      // (layout), slot nie drgnie. Zwolnienie po zakończeniu animacji (lub awaryjnie po 600 ms).
      setCollapsing(true);
      if (releaseTimerRef.current) clearTimeout(releaseTimerRef.current);
      releaseTimerRef.current = setTimeout(release, 600);
    } else {
      release();
    }
    setStage("rest");
  }

  function handleLayoutComplete() {
    if (collapsing && stage === "rest") release();
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
    arm(e.currentTarget);
    clearTimer();
    // Fokus z klawiatury to już jawny zamiar — stopień B natychmiast, bez PREVIEW_DELAY_MS.
    setStage(expandable ? "b" : "a");
  }
  function handleBlur(e: FocusEvent<HTMLElement>) {
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    leave();
  }
  function isPlainLeftClick(e: MouseEvent<HTMLElement>) {
    return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
  }
  /**
   * Klik w dowolne miejsce karty (także w media, których ::after linku nie pokrywa — .sc-card__body
   * jest pozycjonowane, żeby w `large` tekst leżał NAD absolutnym zdjęciem). Akcja/serce to własne
   * przyciski i nie otwierają nic; sam link obsługuje się w handleLinkClick.
   */
  function handleCardClick(e: MouseEvent<HTMLDivElement>) {
    const target = e.target as HTMLElement;
    if (e.defaultPrevented || target.closest(".sc-card__action") || target.closest(".sc-card__link")) return;
    if (!isPlainLeftClick(e)) return;
    if (onOpen) {
      e.preventDefault();
      onOpen(article);
      leave();
    } else {
      linkRef.current?.click();
    }
  }
  function handleLinkClick(e: MouseEvent<HTMLAnchorElement>) {
    if (!onOpen) return;
    if (isPlainLeftClick(e)) {
      e.preventDefault();
      // Portal mierzy `.sc-card` SYNCHRONICZNIE (jeszcze rozrośniętą) — powierzchnia rośnie z tego, co
      // widać; sama karta wraca do spoczynku pod przyciemnieniem, żeby po zamknięciu powierzchnia
      // wróciła do stanu SPRZED rozwinięcia (замечание владельца 24.09).
      onOpen(article);
      leave();
    }
  }

  const uiTransition = motionTokens.t("ui");
  const expandTransition = motionTokens.t(stage === "b" ? "expand" : "collapse");
  const scale = stage === "rest" ? 1 : motionTokens.scale(HOVER_SCALE);
  const lift = stage === "rest" ? (entered ? 0 : motionTokens.rise) : motionTokens.reduced ? 0 : -spec.lift;
  const thumbScale = stage === "rest" ? 1 : motionTokens.scale(1.04);
  const grown = stage === "b" && lock !== null;
  const held = grown || (collapsing && lock !== null);
  const stagger = (i: number) => motionTokens.t("expand", { delay: motionTokens.reduced ? 0 : 0.06 + i * 0.04 });

  return (
    <motion.article
      ref={slotRef}
      data-size={size}
      data-stage={stage}
      data-material-id={article.id}
      className={cn("sc-card-slot", className)}
      style={{ transformOrigin: "50% 50%", zIndex: stage === "rest" && !collapsing ? undefined : 30, height: held ? lock!.height : undefined }}
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
      <motion.div
        ref={cardRef}
        data-size={size}
        data-stage={stage}
        data-layout={size === "large" ? layout : undefined}
        data-has-action={action || grown ? "" : undefined}
        data-expandable={expandable || undefined}
        className="sc-card sc-hoverable"
        layout
        transition={expandTransition}
        onLayoutAnimationComplete={handleLayoutComplete}
        onClick={handleCardClick}
        style={
          grown
            ? { borderRadius: spec.radius, position: "absolute", top: lock.top, left: lock.left, width: lock.targetWidth }
            : held
              ? { borderRadius: spec.radius, position: "absolute", top: 0, left: 0, width: lock!.width, height: lock!.height }
              : { borderRadius: spec.radius }
        }
      >
        {eyebrow ? <span className="sc-card__eyebrow sc-t-caption">{eyebrow}</span> : null}

        <CardMedia
          article={article}
          size={size}
          showCategory={showCategory}
          priority={priority}
          thumbScale={thumbScale}
          transition={uiTransition}
          layoutTransition={expandTransition}
        />

        <div className="sc-card__body">
          {size === "mini" && showCategory ? (
            <motion.span className="sc-card__category sc-t-caption sc-text-3" layout="position" transition={expandTransition}>
              {categoryLabel(article.category)}
            </motion.span>
          ) : null}

          <motion.div layout="position" transition={expandTransition}>
            <Heading className="sc-card__title">
              <Link ref={linkRef} href={resolvedHref} className={cn("sc-card__link", TITLE_CLASS[size])} onClick={handleLinkClick}>
                {article.title}
              </Link>
            </Heading>
          </motion.div>

          {staticDescription && article.description ? (
            <motion.p className="sc-card__description sc-t-body-s sc-text-2" layout="position" transition={expandTransition}>
              {article.description}
            </motion.p>
          ) : null}

          <AnimatePresence initial={false}>
            {!staticDescription && grown && article.description ? (
              <motion.p
                key="desc"
                className="sc-card__description sc-t-body-s sc-text-2"
                initial={{ opacity: 0, y: motionTokens.rise }}
                animate={{ opacity: 1, y: 0, transition: stagger(0) }}
                exit={{ opacity: 0, transition: motionTokens.t("collapse") }}
              >
                {article.description}
              </motion.p>
            ) : null}
          </AnimatePresence>

          {staticMeta ? (
            <CardMeta article={article} size={size} full={grown} transition={expandTransition} />
          ) : (
            <AnimatePresence initial={false}>
              {grown ? (
                <motion.div
                  key="meta"
                  initial={{ opacity: 0, y: motionTokens.rise }}
                  animate={{ opacity: 1, y: 0, transition: stagger(1) }}
                  exit={{ opacity: 0, transition: motionTokens.t("collapse") }}
                >
                  <CardMeta article={article} size={size} full transition={expandTransition} />
                </motion.div>
              ) : null}
            </AnimatePresence>
          )}
        </div>

        {action ? (
          <div className="sc-card__action">{action}</div>
        ) : (
          <AnimatePresence initial={false}>
            {grown ? (
              <motion.div
                key="fav"
                className="sc-card__action"
                initial={{ opacity: 0, scale: motionTokens.scale(0.8) }}
                animate={{ opacity: 1, scale: 1, transition: stagger(staticMeta ? 1 : 2) }}
                exit={{ opacity: 0, scale: motionTokens.scale(0.8), transition: motionTokens.t("collapse") }}
              >
                <button
                  type="button"
                  className="sc-card__fav"
                  aria-label={favourite ? "Usuń z ulubionych" : "Dodaj do ulubionych"}
                  aria-pressed={favourite}
                  data-on={favourite || undefined}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setFavourite((v) => !v);
                  }}
                >
                  <HeartIcon size={20} filled={favourite} />
                </button>
              </motion.div>
            ) : null}
          </AnimatePresence>
        )}
      </motion.div>
    </motion.article>
  );
}
