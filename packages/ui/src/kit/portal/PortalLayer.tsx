"use client";

/**
 * PortalLayer — `createPortal` w `document.body`, `AnimatePresence` zamontowany NA STAŁE
 * (dziecko warunkowe) — patrz docs/UI_KIT_PLAN.md → «Сплошная система движения» → «Портал»:
 * warunkowo zamontowany `<AnimatePresence>` to „przyczyna numer jeden” braku animacji
 * wyjścia. Renderuje powierzchnię pełnoekranową stopnia C (`MaterialSurface`) razem z
 * przyciemnieniem. Stopień B (R0, 24.09) żyje w samej NewsCard — karta zmienia formę tym samym
 * elementem, klonu w tej warstwie już nie ma.
 *
 * Trzy przypadki powrotu przy zamknięciu (docs → «Три случая возврата») są policzone
 * SYNCHRONICZNIE w `PortalProvider.close()` (scrollIntoView w tym samym takcie, zanim
 * jakikolwiek stan trafi do Reacta) — tu tylko czytamy gotowy `engine.exit`.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Article } from "../../types";
import { useMotionTokens } from "../motion/useMotionTokens";
import { responsive, springs } from "../motion/springs";
import { MaterialSurface, type MaterialSurfaceExit, type MaterialSurfaceRect } from "../MaterialSurface";
import { usePortalApi, usePortalEngine, focusTargetById } from "./PortalProvider";
import { useHistoryPortal } from "./useHistoryPortal";
import { useScrollLock } from "./useScrollLock";
import { useModalA11y } from "./useModalA11y";
import { useDragDismiss } from "./useDragDismiss";

export type PortalLayerProps = {
  /** Potrzebne `useHistoryPortal` (wczytanie `?podglad=`, Wstecz/Dalej) i nawigacji do powiązanych. */
  resolveArticle?: (id: number) => Article | null | undefined | Promise<Article | null | undefined>;
  /** Materiały «Powiązane materiały» pod aktualnie otwartym. */
  relatedFor?: (article: Article) => Article[];
};

function toRect(rect: DOMRect | null | undefined): MaterialSurfaceRect | null {
  if (!rect) return null;
  return { top: rect.top, left: rect.left, width: rect.width, height: rect.height };
}

export function PortalLayer({ resolveArticle, relatedFor }: PortalLayerProps) {
  const engine = usePortalEngine();
  const api = usePortalApi();
  const m = useMotionTokens();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const dismissVelocity = useRef<number | null>(null);

  // Materiał aktualnie WYŚWIETLANY w powierzchni — NIE to samo co `engine.article`:
  // nawigacja do powiązanego materiału wewnątrz overlaya podmienia TYLKO treść (replaceState),
  // powierzchnia zostaje tym samym zamontowanym elementem («не подмена контента, а морфинг:
  // старое тело уходит, новое приходит, поверхность остаётся»).
  const [displayed, setDisplayed] = useState<Article | null>(null);
  const prevPhaseRef = useRef(engine.phase);
  // Zrzut prostokąta startowego («flight») — liczony TYLKO raz na sesję otwarcia, nie przy
  // każdej nawigacji do powiązanego materiału (inaczej powierzchnia próbowałaby ponownie
  // "wyrosnąć z karty" za każdym kliknięciem w powiązany materiał). `useLayoutEffect`, żeby
  // rozstrzygnąć PRZED malowaniem klatki — bez migotania „brak powierzchni → jest”.
  const seedRef = useRef<{ rect: MaterialSurfaceRect; radius: number } | null>(null);

  useLayoutEffect(() => {
    const cameFromClosed = prevPhaseRef.current !== "open";
    if (engine.phase === "open" && cameFromClosed) {
      setDisplayed(engine.active);
      seedRef.current = engine.flight
        ? { rect: toRect(engine.flight.rect)!, radius: engine.flight.radius }
        : null;
    }
    if (engine.phase !== "open") {
      seedRef.current = null;
    }
    prevPhaseRef.current = engine.phase;
  }, [engine.phase, engine.active, engine.flight]);

  // `displayed !== null`, NIE `engine.phase === "open"`: `close()` zeruje fazę OD RAZU
  // (żeby AnimatePresence wykryło zniknięcie dziecka i odegrało `exit`), a lokalny stan
  // `displayed` żyje aż do `onExitComplete` — właśnie po to, żeby blokada scrolla i sama
  // powierzchnia dotrwały do końca animacji zamykania, a nie znikły od razu.
  const isOpenSession = displayed !== null;
  // A11y (`inert`) NATOMIAST wraca do `engine.phase === "open"`: `inert` musi zniknąć z
  // #main-content/header ZANIM `onExitComplete` spróbuje oddać fokus kartie — inert na
  // przodku po cichu blokuje .focus() (żaden błąd, fokus po prostu zostaje na <body>).
  // Tło staje się interaktywne odrobinę wcześniej niż kończy się animacja zamykania —
  // świadomy kompromis, powszechny wzorzec w modalach z animowanym wyjściem.
  const a11y = useModalA11y(surfaceRef, engine.phase === "open", () => requestClose());

  const dragHeight = typeof window !== "undefined" ? window.innerHeight : 800;
  const drag = useDragDismiss({
    height: dragHeight,
    onDismiss: (velocity) => {
      dismissVelocity.current = velocity;
      requestClose();
    },
  });

  const { requestClose, replaceForRelated } = useHistoryPortal({
    mode: api.historyMode,
    active: engine.active,
    onOpen: api.open,
    onClose: api.close,
    resolveArticle: resolveArticle ?? (() => null),
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isOpenSession) root.setAttribute("data-portal-open", "");
    else root.removeAttribute("data-portal-open");
    return () => root.removeAttribute("data-portal-open");
  }, [isOpenSession]);

  useScrollLock(isOpenSession);

  function handleNavigate(next: Article) {
    setDisplayed(next);
    replaceForRelated(next);
  }

  function handleSettled() {
    engine.markSettled();
    a11y.focusFirst();
  }

  // `engine.phase === "open"`, NIE `isOpenSession` — to WŁAŚNIE ten przełącznik ma
  // uruchomić `exit` AnimatePresence, kiedy `close()` zeruje fazę. `isOpenSession`
  // (lokalny `displayed`) czyści się DOPIERO w `onExitComplete`, więc oparcie tych
  // dwóch flag na nim byłoby cyklem, który nigdy się nie domyka.
  const showScrim = engine.phase === "open";
  // `displayed !== null` dodatkowo strzeże PIERWSZEGO przebiegu renderu, w którym `phase`
  // zdążył już przełączyć się na "open", a `displayed` jeszcze nie (ustawia go dopiero
  // `useLayoutEffect` wyżej) — bez tego `article={displayed!}` przekazałoby `null`.
  const showSurface = engine.phase === "open" && displayed !== null;

  const exitTransition = dismissVelocity.current !== null
    ? responsive(springs.portalOut, dismissVelocity.current)
    : m.t("portalOut");

  // R0 (24.09): cel powrotu idzie przez `custom` AnimatePresence, NIE przez prop `exit` powierzchni —
  // AnimatePresence odgrywa wyjście na elemencie z OSTATNIEGO renderu przed usunięciem, a wtedy
  // `engine.exit` był jeszcze `null` (close() ustawia fazę i cel w jednym setState). `custom`
  // jest jedyną wartością, którą AnimatePresence aktualizuje na już wychodzącym dziecku.
  const exitCustom: MaterialSurfaceExit | null = engine.exit
    ? { rect: toRect(engine.exit.rect)!, radius: engine.exit.radius, transition: exitTransition }
    : null;

  if (!mounted || typeof document === "undefined") return null;

  return createPortal(
    <>
      <AnimatePresence
        custom={exitCustom}
        onExitComplete={() => {
          if (engine.exit) {
            // Świeże dogranie po id (nie zapamiętana referencja DOM — mogła się zdezaktualizować
            // między `open()` a `close()`, patrz `focusTargetById`) jest najbardziej niezawodne.
            const byId = engine.exit.articleId !== null ? focusTargetById(engine.exit.articleId) : null;
            const focusEl = byId ?? engine.exit.focusEl;
            dismissVelocity.current = null;
            engine.clearExit();
            a11y.restoreFocus(focusEl ?? api.originRef.current);
            setDisplayed(null);
          }
        }}
      >
        {showScrim && (
          <motion.div
            key="scrim"
            className="sc-portal-scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: m.t("scrim") }}
            exit={{ opacity: 0, transition: m.t("scrim") }}
            onPointerDown={(event) => {
              if (event.target === event.currentTarget) requestClose();
            }}
          />
        )}
        {showSurface && (
          <MaterialSurface
            key="surface"
            mode="overlay"
            article={displayed!}
            related={relatedFor ? relatedFor(displayed!) : []}
            onClose={requestClose}
            onNavigate={handleNavigate}
            surfaceRef={surfaceRef}
            scrollerRef={scrollerRef}
            fromRect={seedRef.current?.rect ?? null}
            fromRadius={seedRef.current?.radius ?? 0}
            transition={m.t("portalIn")}
            onSettled={handleSettled}
            dragEnabled={engine.settled}
            drag={drag}
          />
        )}
      </AnimatePresence>
    </>,
    document.body,
  );
}
