"use client";

/**
 * useHoverExpand — stopień B (docs/UI_KIT_PLAN.md → «Ступень B: как именно раскрывается
 * предпросмотр», uwaga właściciela «Слой выше, а не поток»: przedpodgląd ZAWSZE renderuje
 * się w warstwie NAD stroną — w siatkach I w taśmach — i nigdy nie zmienia żadnego
 * pudełka w potoku. `.material-strip` ma `overflow-x: auto; overflow-y: hidden` —
 * rosnąca kopia zostałaby obcięta, gdyby rosła w miejscu; stąd ta sama warstwa-portal,
 * co pełny ekran, tylko bez przyciemnienia, blokady scrolla i zmiany adresu.
 *
 * Wzrost jest CZYSTYM `transform: scale()` (nie width/height) wokół `transform-origin`
 * wyliczonego raz z `getBoundingClientRect()` oryginału — karty przy krawędzi rosną
 * do wewnątrz. Promień jest STAŁY przez cały stopień B (taki sam jak w spoczynku),
 * więc nie ma korekty eliptycznej do liczenia.
 *
 * Klon NIE nosi żadnego a11y-znaczenia własnego: prawdziwy, dostępny z klawiatury element
 * to oryginalna NewsCard (R3) pod spodem — klon jest `aria-hidden`, czysto wskaźnikowy
 * (`onPointerEnter/Leave`, `onClick`). Zejście wskaźnika z KLONA i z ORYGINAŁU jednocześnie
 * zwija podgląd; nasłuch na oryginale wpinamy bezpośrednio (`addEventListener`), bo
 * NewsCard (plik R3) nie eksponuje własnego propa na to zdarzenie.
 */

import { motion } from "framer-motion";
import { useEffect, useRef, type ReactNode } from "react";
import { ArrowUpRightIcon } from "../icons/ArrowUpRightIcon";
import { formatDateTimePl, materialTypeLabel } from "../../lib/utils";
import { useMotionTokens } from "../motion/useMotionTokens";
import { CARD_SPEC } from "../tokens";
import { usePortalApi, usePortalEngine } from "./PortalProvider";

/** @media (hover: hover) and (pointer: fine) — na dotyku stopnia B po najechaniu nie ma wcale. */
function hasFinePointer(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(hover: hover) and (pointer: fine)").matches;
}

/**
 * Zwraca sam WARUNKOWY element klona (albo `null`) — NIGDY własnego `<AnimatePresence>`.
 * Stały `<AnimatePresence>` żyje w `PortalLayer.tsx` i obejmuje klon + scrim + powierzchnię
 * RAZEM: gdy ten hook zwróci `null` (koniec podglądu, zejście wskaźnika), to WŁAŚNIE
 * ten wspólny, cały czas zamontowany `<AnimatePresence>` odgrywa `exit` klona — owinięcie
 * go WEWNĄTRZ hooka unmontowałoby cały kontener razem z dzieckiem i wyjście nigdy by się
 * nie odegrało (docs/UI_KIT_PLAN.md → «Ловушки движения»: „warunkowo zamontowany
 * <AnimatePresence> to przyczyna numer jeden braku animacji wyjścia”).
 */
export function useHoverExpand(): ReactNode {
  const engine = usePortalEngine();
  const api = usePortalApi();
  const m = useMotionTokens();
  const hoveringCloneRef = useRef(false);
  const hoveringOriginRef = useRef(false);

  const previewing = engine.phase === "previewing";
  const originEl = engine.originEl;

  useEffect(() => {
    if (!previewing || !originEl) return;
    function onEnter() {
      hoveringOriginRef.current = true;
    }
    function onLeave(event: PointerEvent) {
      if (event.pointerType !== "mouse") return;
      hoveringOriginRef.current = false;
      // Mikrozadanie: klon może właśnie zgłosić `pointerenter` (przejście oryginał→klon graniczą pikselowo).
      queueMicrotask(() => {
        if (!hoveringCloneRef.current && !hoveringOriginRef.current) api.endPreview();
      });
    }
    hoveringOriginRef.current = true;
    originEl.addEventListener("pointerenter", onEnter);
    originEl.addEventListener("pointerleave", onLeave);
    return () => {
      hoveringOriginRef.current = false;
      originEl.removeEventListener("pointerenter", onEnter);
      originEl.removeEventListener("pointerleave", onLeave);
    };
  }, [previewing, originEl, api]);

  if (!previewing || !engine.previewing || !engine.flight || !hasFinePointer()) return null;

  const article = engine.previewing;
  const flight = engine.flight;
  const spec = CARD_SPEC[flight.size];
  const rect = flight.rect;
  const originX = rect.left < 24 ? "0%" : window.innerWidth - rect.right < 24 ? "100%" : "50%";
  const originY = rect.top < 24 ? "0%" : "50%";
  const src = article.image_url?.trim();
  const targetScale = spec.previewScale;

  function handleClonePointerEnter() {
    hoveringCloneRef.current = true;
  }
  function handleClonePointerLeave() {
    hoveringCloneRef.current = false;
    queueMicrotask(() => {
      if (!hoveringCloneRef.current && !hoveringOriginRef.current) api.endPreview();
    });
  }
  function handleCloneClick() {
    api.open(article, engine.originEl);
  }

  return (
      <motion.div
        key={`preview-${article.id}`}
        // Prawdziwy layoutId — klik na klonie PRZEKAZUJE go powierzchni (MaterialSurface,
        // ten sam id) w TYM SAMYM commicie: framer-motion sam liczy projekcję (translate+scale
        // + korekta promienia) od bieżącego, na żywo zmierzonego pudełka klona (nawet w trakcie
        // jego własnej animacji `scale`) do naturalnego pudełka powierzchni. To właśnie
        // „jeden żywy element”, o który prosi właściciel — bez tego NewsCard (R3) nie ma
        // jak sama nosić `layoutId`, patrz komentarz w PortalProvider.tsx.
        layoutId={`sc-card-${article.id}`}
        data-portal-clone={article.id}
        data-size={flight.size}
        data-stage="b"
        className="sc-portal-preview sc-card"
        aria-hidden="true"
        style={{
          position: "fixed",
          top: rect.top,
          left: rect.left,
          width: rect.width,
          height: rect.height,
          borderRadius: flight.radius,
          transformOrigin: `${originX} ${originY}`,
          zIndex: 70,
        }}
        initial={{ scale: m.reduced ? targetScale : 1, opacity: 0 }}
        animate={{ scale: targetScale, opacity: 1 }}
        exit={{ scale: 1, opacity: m.reduced ? 0 : 1, transition: m.t("collapse") }}
        transition={m.t("expand")}
        onPointerEnter={handleClonePointerEnter}
        onPointerLeave={handleClonePointerLeave}
        onClick={handleCloneClick}
      >
        <div className="sc-card__media">
          {src ? (
            // eslint-disable-next-line @next/next/no-img-element -- klon warstwy-portalu: bez next/image (unoptimized i tak, brak potrzeby fill/sizes)
            <img src={src} alt="" className="sc-card__image" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
          ) : (
            <span className="sc-card__placeholder sc-t-caption" aria-hidden="true">
              {materialTypeLabel(article.category)}
            </span>
          )}
        </div>
        <div className="sc-card__body">
          <p className={flight.size === "large" ? "sc-t-title-l sc-card__title" : "sc-t-title-m sc-card__title"} style={{ margin: "0 0 var(--sc-s-2)" }}>
            {article.title}
          </p>
          <div className="sc-card__expand" style={{ position: "static", marginTop: 0, paddingTop: "var(--sc-s-2)" }}>
            {article.description ? (
              <motion.p
                className="sc-t-body-s sc-card__expand-desc"
                initial={{ opacity: 0, y: m.rise }}
                animate={{ opacity: 1, y: 0, transition: m.t("expand", { delay: m.reduced ? 0 : 0.03 }) }}
              >
                {article.description}
              </motion.p>
            ) : null}
            <motion.p
              className="sc-t-meta sc-text-2 sc-card__expand-meta"
              initial={{ opacity: 0, y: m.rise }}
              animate={{ opacity: 1, y: 0, transition: m.t("expand", { delay: m.reduced ? 0 : 0.06 }) }}
            >
              {article.source.name}
              {article.author ? ` · ${article.author}` : ""} · {formatDateTimePl(article.published_date, article.date_precision)}
            </motion.p>
            {article.url ? (
              <motion.a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="sc-t-meta sc-card__expand-link"
                initial={{ opacity: 0, y: m.rise }}
                animate={{ opacity: 1, y: 0, transition: m.t("expand", { delay: m.reduced ? 0 : 0.09 }) }}
                onClick={(event) => event.stopPropagation()}
              >
                Źródło oryginalne <ArrowUpRightIcon size={16} />
              </motion.a>
            ) : null}
          </div>
        </div>
      </motion.div>
  );
}
