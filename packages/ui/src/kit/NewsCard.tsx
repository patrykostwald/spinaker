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
import { categoryLabel, cn, formatDateTimePl, formatShortDatePl, formatTimePl, materialKind, relativeTimePl, shortCategoryLabel, sourceDisplayName, sourceInitials } from "../lib/utils";
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
  /** Liczba zwiniętych, niemal identycznych materiałów tego samego źródła (np. seria wniosków z sesji). */
  similarCount?: number;
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
/** Zwijanie ze stopnia B: czas sprężyny `collapse` (0.26s, bounce 0) i jej odpowiednik krzywą — jedyna
 *  animacja poza `useMotionTokens().t()`, bo idzie przez Web Animations, nie przez framer (patrz leave()). */
const COLLAPSE_MS = 260;
const COLLAPSE_EASING = "cubic-bezier(0.16, 1, 0.3, 1)";

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
    // Mini/compact: czas względny („3 godz. temu”), pełna data w podpowiedzi. Zależy od „teraz”, stąd suppressHydrationWarning.
    if (size === "mini" || size === "compact") {
      return (
        <time dateTime={iso} title={formatDateTimePl(iso, article.date_precision)} suppressHydrationWarning>
          {relativeTimePl(iso) || (size === "mini" ? formatTimePl(iso) : formatShortDatePl(iso))}
        </time>
      );
    }
    return <time dateTime={iso}>{formatDateTimePl(iso, article.date_precision)}</time>;
  }
  const label = size === "mini" || size === "compact" ? "Data nieustalona" : "Data publikacji nieustalona";
  return <span>{label}</span>;
}

/** „+1 podobny”, „+3 podobne”, „+5 podobnych”, „+22 podobne”. */
function similarLabel(count: number): string {
  if (count === 1) return "podobny";
  const tens = count % 100;
  const units = count % 10;
  return units >= 2 && units <= 4 && (tens < 12 || tens > 14) ? "podobne" : "podobnych";
}

function CardBadge({ category, transition }: { category: string; transition: Transition }) {
  return (
    <motion.span className="sc-card__badge sc-t-caption" data-kind={materialKind(category)} title={categoryLabel(category)} layout="position" transition={transition}>
      <span className="sc-card__kind-dot" aria-hidden="true" />
      {shortCategoryLabel(category)}
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
        // Bez zdjęcia: tło w kolorze rodzaju materiału i inicjały źródła zamiast pustego szarego pola.
        <span className="sc-card__placeholder" data-kind={materialKind(article.category)} aria-hidden="true">
          <span className="sc-card__mono">{sourceInitials(sourceDisplayName(article.source.name))}</span>
        </span>
      )}
      {size !== "mini" && showCategory ? <CardBadge category={article.category} transition={layoutTransition} /> : null}
    </motion.div>
  );
}

function CardMeta({ article, size, full, transition }: { article: Article; size: NewsCardSize; full: boolean; transition: Transition }) {
  return (
    <motion.p className="sc-card__meta sc-t-meta sc-text-2" layout="position" transition={transition}>
      <span className="sc-card__meta-source" title={article.source.name}>{sourceDisplayName(article.source.name)}</span>
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
  similarCount,
  className,
}: NewsCardProps) {
  const motionTokens = useMotionTokens();
  const slotRef = useRef<HTMLElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const linkRef = useRef<HTMLAnchorElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lockRef = useRef<Lock | null>(null);
  const releaseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const collapseAnimRef = useRef<Animation | null>(null);
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
      collapseAnimRef.current?.cancel();
    },
    [],
  );

  // Po zwolnieniu do potoku: `commitStyles()` zostawił inline `height` (React go nie zna) — zdejmujemy.
  useLayoutEffect(() => {
    if (!lock && cardRef.current) {
      cardRef.current.style.height = "";
      cardRef.current.style.top = "";
      cardRef.current.style.left = "";
    }
  }, [lock]);

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
    stopCollapseAnim();
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

  function stopCollapseAnim() {
    if (collapseAnimRef.current) {
      collapseAnimRef.current.cancel();
      collapseAnimRef.current = null;
    }
    if (releaseTimerRef.current) {
      clearTimeout(releaseTimerRef.current);
      releaseTimerRef.current = null;
    }
  }

  function release() {
    if (collapseAnimRef.current) {
      // Utrwalamy końcowe pudełko inline, żeby między anulowaniem animacji a commitem Reacta nie
      // mignęła rozrośnięta geometria ze `style`; `height` React nie zna — czyścimy w efekcie niżej.
      try {
        collapseAnimRef.current.commitStyles();
      } catch {
        /* element już odłączony */
      }
    }
    stopCollapseAnim();
    lockRef.current = null;
    setLock(null);
    setCollapsing(false);
  }

  function leave() {
    clearTimer();
    const el = cardRef.current;
    const lock = lockRef.current;
    if (stage === "b" && el && lock && !motionTokens.reduced) {
      // Zwijanie: JAWNA animacja pudełka (top/left/width/height → spoczynek) przez Web Animations,
      // nie `layout` framera — layout mierzy tylko w commitach Reacta, więc wysokość skakała w chwili
      // odmontowania opisu (замечание владельца 24.09). Slot trzyma wysokość do końca; karta wraca
      // do potoku dopiero po `finish`, w tej samej geometrii — bez skoku.
      setCollapsing(true);
      stopCollapseAnim();
      const from = { top: `${el.offsetTop}px`, left: `${el.offsetLeft}px`, width: `${el.offsetWidth}px`, height: `${el.offsetHeight}px` };
      const to = { top: "0px", left: "0px", width: `${lock.width}px`, height: `${lock.height}px` };
      const anim = el.animate([from, to], { duration: COLLAPSE_MS, easing: COLLAPSE_EASING, fill: "forwards" });
      collapseAnimRef.current = anim;
      anim.onfinish = () => {
        if (collapseAnimRef.current === anim) release();
      };
      releaseTimerRef.current = setTimeout(release, COLLAPSE_MS + 200);
    } else {
      release();
    }
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
  // Podczas zwijania geometria ze `style` zostaje rozrośnięta — nadpisuje ją animacja WAAPI.
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
        layout={!collapsing}
        transition={expandTransition}
        onClick={handleCardClick}
        style={
          held
            ? { borderRadius: spec.radius, position: "absolute", top: lock!.top, left: lock!.left, width: lock!.targetWidth, minHeight: lock!.height }
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
            <motion.span className="sc-card__category sc-t-caption sc-text-3" data-kind={materialKind(article.category)} title={categoryLabel(article.category)} layout="position" transition={expandTransition}>
              <span className="sc-card__kind-dot" aria-hidden="true" />
              {shortCategoryLabel(article.category)}
              {similarCount ? <span className="sc-card__similar"> · +{similarCount} {similarLabel(similarCount)}</span> : null}
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
