"use client";

/**
 * MaterialSurface — wspólne ciało overlaya portalu ORAZ (etap 2) strony `/material/[id]`
 * (docs/UI_KIT_PLAN.md → «Портал» → «Адрес»: „oba muszą renderować DOKŁADNIE ten sam
 * komponent MaterialSurface z propem mode: 'page' | 'overlay'”).
 *
 * Ciągłość „karta → pełny ekran”, DWIE ścieżki (patrz `useSharedLayout`):
 *  - Klon istnieje (zwykła ścieżka, skoro `expandable` domyślnie odsłania stopień B):
 *    powierzchnia dostaje TEN SAM `layoutId="sc-card-${id}"` co klon (useHoverExpand.tsx)
 *    i statyczne docelowe pudełko przez `style` — framer-motion SAM liczy projekcję
 *    (translate+scale+korekta promienia) od bieżącego, żywego pudełka klona. To „jeden
 *    żywy element”, o który prosi właściciel.
 *  - Klona nie było (klik zanim dojrzało 400ms/bez podglądu, albo powrót z ?podglad=):
 *    NewsCard (R3) nigdy nie niesie `layoutId` (jedyna dozwolona zmiana w jej pliku to
 *    `onPreview`), więc nie ma czego złapać — powierzchnia animuje WPROST
 *    `top/left/width/height/borderRadius` między jawnie zmierzonym `fromRect` a docelowym
 *    pudełkiem. Dla POJEDYNCZEGO elementu koszt reflow jest pomijalny (budżet wydajności
 *    w planie dotyczy siatek 200 kart, nie jednego modala).
 * Zamknięcie w OBU przypadkach wraca przez jawny `exit` (rect/radius z trzech przypadków
 * powrotu, PortalProvider.close()) — nie przez layoutId, bo po stronie oryginału znowu
 * nie ma nic, co mogłoby go „złapać”.
 */

import { motion, type Transition } from "framer-motion";
import { useEffect, useState, type Ref, type RefObject } from "react";
import { ArrowUpRightIcon } from "./icons/ArrowUpRightIcon";
import { CloseIcon } from "./icons/CloseIcon";
import { HeartIcon } from "./icons/HeartIcon";
import { ShareIcon } from "./icons/ShareIcon";
import { Button } from "./Button";
import { NewsCard } from "./NewsCard";
import { useMotionTokens } from "./motion/useMotionTokens";
import { BREAKPOINTS, RADIUS } from "./tokens";
import { categoryLabel, formatDateTimePl } from "../lib/utils";
import type { Article } from "../types";
import type { DragDismiss } from "./portal/useDragDismiss";

export type MaterialSurfaceRect = { top: number; left: number; width: number; height: number };

export type MaterialSurfaceProps = {
  mode: "overlay" | "page";
  article: Article;
  related?: Article[];
  /** overlay: krzyżyk/scrim/Escape/przeciągnięcie — wywołujący decyduje (historia). */
  onClose?: () => void;
  /** Klik w kartę „Powiązane materiały” — morfing treści + `replaceState`, powierzchnia zostaje. */
  onNavigate?: (article: Article) => void;
  surfaceRef?: Ref<HTMLDivElement>;
  scrollerRef?: RefObject<HTMLDivElement>;
  /** Dzielony identyfikator z klonem (useHoverExpand) — patrz `useSharedLayout`. */
  layoutId?: string;
  /**
   * `true`, gdy `open()` zastał żywy klon dla tego materiału: powierzchnia dostaje TEN SAM
   * `layoutId`, a top/left/width/height/border-radius idą przez zwykły `style` (statyczne
   * docelowe pudełko) — framer-motion SAM liczy projekcję od bieżącego pudełka klona.
   * `false` (klik zanim dojrzało 400ms, brak podglądu) — nie ma poprzedniego elementu z tym
   * `layoutId`, więc wracamy do ręcznej animacji `initial→animate` od `fromRect`.
   */
  useSharedLayout?: boolean;
  fromRect?: MaterialSurfaceRect | null;
  fromRadius?: number;
  exitRect?: MaterialSurfaceRect | null;
  exitRadius?: number;
  transition?: Transition;
  exitTransition?: Transition;
  onSettled?: () => void;
  dragEnabled?: boolean;
  drag?: DragDismiss;
};

function computeTargetBox() {
  if (typeof window === "undefined") return { top: 0, left: 0, width: 0, height: 0, radius: 0 };
  const w = window.innerWidth;
  const h = window.innerHeight;
  if (w < BREAKPOINTS.phone) return { top: 0, left: 0, width: w, height: h, radius: 0 };
  const insetY = h * 0.06;
  const insetX = w * 0.08;
  return { top: insetY, left: insetX, width: w - insetX * 2, height: h - insetY * 2, radius: RADIUS["2xl"] };
}

function useTargetBox() {
  const [box, setBox] = useState(computeTargetBox);
  useEffect(() => {
    function onResize() {
      setBox(computeTargetBox());
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return box;
}

export function MaterialSurface({
  mode,
  article,
  related = [],
  onClose,
  onNavigate,
  surfaceRef,
  scrollerRef,
  layoutId,
  useSharedLayout = false,
  fromRect,
  fromRadius = 0,
  exitRect,
  exitRadius = 0,
  transition,
  exitTransition,
  onSettled,
  dragEnabled,
  drag,
}: MaterialSurfaceProps) {
  const m = useMotionTokens();
  const target = useTargetBox();
  const isOverlay = mode === "overlay";
  const src = article.image_url?.trim();
  const [favourite, setFavourite] = useState(false);
  const [shared, setShared] = useState(false);

  const overlayStyle = isOverlay
    ? {
        position: "fixed" as const,
        zIndex: 91,
        overflow: "hidden" as const,
        background: "var(--sc-surface)",
        boxShadow: "var(--sc-e-3), 0 0 0 1px var(--sc-glow-ring), 0 0 56px var(--sc-glow-ring-strong)",
        y: drag?.y,
        scale: drag?.surfaceScale,
        // `useSharedLayout`: pudełko jest STATYCZNE (docelowe) — framer-motion sam liczy
        // projekcję od bieżącego pudełka klona przez dzielony `layoutId`. Bez klona (poniżej)
        // pudełko animuje `initial`/`animate` ręcznie, więc tu go nie ustawiamy.
        ...(useSharedLayout ? { top: target.top, left: target.left, width: target.width, height: target.height, borderRadius: target.radius } : {}),
      }
    : undefined;

  const initial = isOverlay
    ? useSharedLayout
      ? { opacity: 1 }
      : fromRect
        ? { top: fromRect.top, left: fromRect.left, width: fromRect.width, height: fromRect.height, borderRadius: fromRadius, opacity: 1 }
        : { opacity: 0 }
    : undefined;

  const animate = isOverlay
    ? useSharedLayout
      ? { opacity: 1, transition: { layout: transition } }
      : {
          top: target.top,
          left: target.left,
          width: target.width,
          height: target.height,
          borderRadius: target.radius,
          opacity: 1,
          transition: fromRect ? transition : m.t("fade"),
        }
    : undefined;

  // `exit` NIE zależy od `useSharedLayout` — zamknięcie zawsze wraca do zapamiętanego
  // prostokąta oryginału (trzy przypadki powrotu, PortalProvider.close()), niezależnie od
  // tego, czy powierzchnia otworzyła się przez klon, czy przez zapasową ręczną animację.
  const exit = isOverlay
    ? exitRect
      ? { top: exitRect.top, left: exitRect.left, width: exitRect.width, height: exitRect.height, borderRadius: exitRadius, opacity: 1, transition: exitTransition }
      : { opacity: 0, transition: m.t("fade") }
    : undefined;

  const content = (
    <>
      {isOverlay ? (
        <Button
          shape="icon"
          variant="ghost"
          size="md"
          aria-label="Zamknij"
          className="sc-surface__close"
          onClick={onClose}
          iconStart={<CloseIcon />}
        />
      ) : null}
      {isOverlay ? (
        <div
          className="sc-surface__handle"
          onPointerDown={(event) => drag?.startIfAtTop(event, scrollerRef?.current ?? null)}
        />
      ) : null}

      <div ref={scrollerRef} className="sc-surface__scroll">
        <div className="sc-surface__media">
          {src ? (
            // eslint-disable-next-line @next/next/no-img-element -- powierzchnia portalu: ta sama zasada co w klonie (useHoverExpand)
            <img src={src} alt="" className="sc-surface__image" />
          ) : (
            <span className="sc-surface__placeholder sc-t-caption" aria-hidden="true" />
          )}
          <span className="sc-surface__badge sc-t-caption">{categoryLabel(article.category)}</span>
        </div>

        <div className="sc-surface__body">
          <h2 className="sc-t-title-l sc-surface__title">{article.title}</h2>

          <p className="sc-t-meta sc-text-2 sc-surface__source">
            <a href={article.url} target="_blank" rel="noopener noreferrer" className="sc-surface__source-link">
              {article.source.name} <ArrowUpRightIcon size={16} />
            </a>
            {article.author ? <span> · {article.author}</span> : null}
            {" · "}
            {article.published_date && article.published_date !== "undated" && article.published_date !== "unknown" ? (
              <time dateTime={article.published_date}>{formatDateTimePl(article.published_date, article.date_precision)}</time>
            ) : (
              <span>Data publikacji nieustalona</span>
            )}
          </p>

          {article.description ? <p className="sc-t-body sc-text-2 sc-surface__description">{article.description}</p> : null}

          <div className="sc-surface__actions">
            {/* Button nie eksponuje `target`/`rel` (plik R2, poza zasięgiem edycji) — nowa karta przez window.open. */}
            <Button variant="primary" size="md" onClick={() => window.open(article.url, "_blank", "noopener,noreferrer")}>
              Otwórz źródło
            </Button>
            <Button
              shape="icon"
              variant="secondary"
              size="md"
              aria-label={favourite ? "Usuń z ulubionych" : "Dodaj do ulubionych"}
              pressed={favourite}
              onClick={() => setFavourite((v) => !v)}
              iconStart={<HeartIcon filled={favourite} />}
            />
            <Button
              shape="icon"
              variant="secondary"
              size="md"
              aria-label={shared ? "Skopiowano odnośnik" : "Udostępnij"}
              onClick={() => {
                setShared(true);
                window.setTimeout(() => setShared(false), 1600);
              }}
              iconStart={<ShareIcon />}
            />
          </div>

          {related.length > 0 ? (
            <div className="sc-surface__related">
              <h3 className="sc-t-title-s sc-surface__related-title">Powiązane materiały</h3>
              <div className="sc-surface__related-track">
                {related
                  .filter((item) => item.id !== article.id)
                  .map((item) => (
                    <NewsCard key={item.id} article={item} size="compact" onOpen={(next) => onNavigate?.(next)} />
                  ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </>
  );

  if (!isOverlay) {
    return (
      <div className="sc-surface" data-mode="page">
        {content}
      </div>
    );
  }

  return (
    <motion.div
      ref={surfaceRef}
      layoutId={layoutId}
      className="sc-surface"
      data-mode="overlay"
      data-stage="c"
      role="dialog"
      aria-modal="true"
      aria-label={article.title}
      style={overlayStyle}
      initial={initial}
      animate={animate}
      exit={exit}
      onAnimationComplete={onSettled}
      {...(dragEnabled && drag ? drag.dragProps : { drag: false as const })}
    >
      {content}
    </motion.div>
  );
}
