"use client";

/**
 * MaterialSurface — wspólne ciało overlaya portalu ORAZ (etap 2) strony `/material/[id]`
 * (docs/UI_KIT_PLAN.md → «Портал» → «Адрес»: „oba muszą renderować DOKŁADNIE ten sam
 * komponent MaterialSurface z propem mode: 'page' | 'overlay'”).
 *
 * Ciągłość „karta → pełny ekran” (R0, 24.09): jedna ścieżka — jawny FLIP. `PortalProvider.open()`
 * mierzy `.sc-card` (rozrośniętą, jeśli trwa stopień B) i powierzchnia animuje WPROST
 * `top/left/width/height/borderRadius` od `fromRect` do docelowego pudełka. Dla POJEDYNCZEGO
 * elementu koszt reflow jest pomijalny. Zamknięcie wraca do celu z trzech przypadków powrotu
 * (`PortalProvider.close()`), dostarczonego przez `custom` AnimatePresence (wariant `closed`).
 */

import { motion, type Transition } from "framer-motion";
import { useEffect, useState, type ReactNode, type Ref, type RefObject } from "react";
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
/** Cel powrotu — przychodzi przez `custom` AnimatePresence w chwili zamknięcia (patrz PortalLayer). */
export type MaterialSurfaceExit = { rect: MaterialSurfaceRect; radius: number; transition: Transition };

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
  fromRect?: MaterialSurfaceRect | null;
  fromRadius?: number;
  transition?: Transition;
  onSettled?: () => void;
  dragEnabled?: boolean;
  drag?: DragDismiss;
  /** Akcje zależne od konta aplikacji, np. udostępnienie na podłączone X. */
  actionSlot?: ReactNode;
  /** Dane kontekstowe strony materiału. Powierzchnia portalu może pozostać lekka. */
  children?: ReactNode;
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
  fromRect,
  fromRadius = 0,
  transition,
  onSettled,
  dragEnabled,
  drag,
  actionSlot,
  children,
}: MaterialSurfaceProps) {
  const m = useMotionTokens();
  const target = useTargetBox();
  const isOverlay = mode === "overlay";
  const src = article.image_url?.trim();
  const [favourite, setFavourite] = useState(false);

  const overlayStyle = isOverlay
    ? {
        position: "fixed" as const,
        zIndex: 91,
        overflow: "hidden" as const,
        background: "var(--sc-surface)",
        boxShadow: "var(--sc-e-3), 0 0 0 1px var(--sc-glow-ring), 0 0 56px var(--sc-glow-ring-strong)",
        y: drag?.y,
        scale: drag?.surfaceScale,
      }
    : undefined;

  const initial = isOverlay
    ? fromRect
      ? { top: fromRect.top, left: fromRect.left, width: fromRect.width, height: fromRect.height, borderRadius: fromRadius, opacity: 1 }
      : { opacity: 0 }
    : undefined;

  const animate = isOverlay
    ? {
        top: target.top,
        left: target.left,
        width: target.width,
        height: target.height,
        borderRadius: target.radius,
        opacity: 1,
        transition: fromRect ? transition : m.t("fade"),
      }
    : undefined;

  // Wyjście jako WARIANT z `custom`: zamknięcie zawsze wraca do prostokąta oryginału (trzy przypadki
  // powrotu, PortalProvider.close()), który AnimatePresence dostarcza przez `custom` już PO usunięciu
  // dziecka — zwykły prop `exit` widziałby wartości z renderu sprzed zamknięcia (`null`).
  const variants = {
    closed: (custom: MaterialSurfaceExit | null) =>
      custom
        ? { top: custom.rect.top, left: custom.rect.left, width: custom.rect.width, height: custom.rect.height, borderRadius: custom.radius, opacity: 1, transition: custom.transition }
        : { opacity: 0, transition: m.t("fade") },
  };

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
            {actionSlot ?? <Button shape="icon" variant="secondary" size="md" aria-label="Udostępnianie wymaga podłączonego konta X" disabled iconStart={<ShareIcon />} />}
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
          {children ? <div className="sc-surface__context">{children}</div> : null}
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
      className="sc-surface"
      data-mode="overlay"
      data-stage="c"
      role="dialog"
      aria-modal="true"
      aria-label={article.title}
      style={overlayStyle}
      initial={initial}
      animate={animate}
      variants={variants}
      exit="closed"
      onAnimationComplete={onSettled}
      {...(dragEnabled && drag ? drag.dragProps : { drag: false as const })}
    >
      {content}
    </motion.div>
  );
}
