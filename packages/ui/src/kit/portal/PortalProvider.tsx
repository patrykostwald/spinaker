"use client";

/**
 * PortalProvider — stan i API portalu (docs/UI_KIT_PLAN.md → «Портал», «Контракты»).
 *
 * DWA konteksty celowo: `PortalApiContext` niesie WYŁĄCZNIE stabilne funkcje (referencje
 * nie zmieniają się między renderami), więc karta, która tylko WYWOŁUJE `open`/`preview`,
 * nigdy nie renderuje się ponownie z powodu zmiany stanu portalu. `PortalEngineContext`
 * (state) niesie to, co faktycznie się zmienia — subskrybują go tylko PortalLayer/
 * useHoverExpand i ewentualne odczyty `active`/`previewing`.
 *
 * Właściciel `layoutId="sc-card-${id}"` — uwaga (odstępstwo, patrz raport R5): kontrakt
 * z wave 0 zakłada, że NewsCard sama zdejmuje/nosi layoutId. R3 nigdy tego nie
 * zaimplementował (żaden layoutId w NewsCard.tsx), a jedyna dozwolona zmiana w tym pliku
 * to opcjonalny prop `onPreview`. PortalLayer/MaterialSurface NIE używają więc layoutId
 * do morfingu — odtwarzają ciągłość przez jawny zrzut `getBoundingClientRect()` w chwili
 * `open()`/`preview()` (patrz PortalLayer.tsx, MaterialSurface.tsx).
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import type { Article } from "../../types";
import { CARD_SPEC, type CardSize } from "../tokens";

export type PortalHistoryMode = "none" | "query" | "path";

type Phase = "idle" | "previewing" | "open";

export type FlightOrigin = {
  rect: DOMRect;
  radius: number;
  size: CardSize;
  /**
   * Czy `open()` zastał żywy klon stopnia B dla TEGO materiału. Gdy `true`, klon i
   * powierzchnia dzielą prawdziwy `layoutId="sc-card-${id}"` — framer-motion sam liczy
   * projekcję (owner: „one living element”, «Sześcien живой»). Gdy `false` (klik zanim
   * dojrzało 400ms, albo otwarcie bez podglądu wcale), nie ma poprzedniego elementu z tym
   * `layoutId`, więc `MaterialSurface` używa zapasowej ręcznej animacji od `fromRect`.
   */
  viaClone: boolean;
};

export type PortalExit = {
  kind: "card" | "offscreen" | "unmounted";
  rect: DOMRect;
  radius: number;
  /** Zamrożone w chwili `close()` — bezpieczniejsze niż osobny `originRef` czytany później. */
  focusEl: HTMLElement | null;
  /** id materiału, którego dotyczy powrót — do świeżego dogrania fokusu w `onExitComplete`. */
  articleId: number | null;
};

type EngineState = {
  phase: Phase;
  article: Article | null;
  originEl: HTMLElement | null;
  flight: FlightOrigin | null;
  exit: PortalExit | null;
};

export type PortalApi = {
  open: (article: Article, originEl?: HTMLElement | null) => void;
  close: () => void;
  preview: (article: Article, originEl: HTMLElement) => void;
  endPreview: () => void;
  originRef: RefObject<HTMLElement | null>;
  historyMode: PortalHistoryMode;
};

export type PortalStateValue = {
  active: Article | null;
  previewing: Article | null;
  isActive: (id: number) => boolean;
  isPreviewing: (id: number) => boolean;
};

/** Pełny stan silnika — używa go PortalLayer/useHoverExpand; nie jest częścią minimalnego `usePortal()`. */
export type PortalEngineValue = PortalStateValue & {
  phase: Phase;
  originEl: HTMLElement | null;
  flight: FlightOrigin | null;
  exit: PortalExit | null;
  clearExit: () => void;
  markSettled: () => void;
  settled: boolean;
};

const PortalApiContext = createContext<PortalApi | null>(null);
const PortalEngineContext = createContext<PortalEngineValue | null>(null);

const SIZES: readonly CardSize[] = ["mini", "compact", "medium", "large"];

function readSize(el: HTMLElement | null | undefined): CardSize {
  const size = el?.dataset.size;
  return (SIZES as readonly string[]).includes(size ?? "") ? (size as CardSize) : "compact";
}

function findOriginEl(id: number): HTMLElement | null {
  if (typeof document === "undefined") return null;
  return document.querySelector<HTMLElement>(`[data-material-id="${id}"]`);
}

function findCloneEl(id: number): HTMLElement | null {
  if (typeof document === "undefined") return null;
  return document.querySelector<HTMLElement>(`[data-portal-clone="${id}"]`);
}

/**
 * `useModalA11y.restoreFocus` woła `originEl.focus()` wprost (plik R4, poza zasięgiem edycji).
 * Korzeń `NewsCard` to `<article>` — ZAWSZE wolimy fokusowalne DZIECKO (prawdziwy link
 * tytułu), nawet jeśli sam korzeń też technicznie pasuje do selektora: framer-motion dopisuje
 * mu `tabindex="0"` samo (gesty `whileTap`/`whileHover`), więc `el.matches(...)` na korzeniu
 * dawałoby fałszywe pierwszeństwo PRZED zajrzeniem do środka — złapaliśmy to dopiero w
 * przeglądarce (fokus lądował na `<article>`, nie na linku, mimo że link istniał).
 */
function focusTarget(el: HTMLElement | null): HTMLElement | null {
  if (!el) return null;
  return el.querySelector<HTMLElement>('a[href], button, [tabindex]') ?? el;
}

/**
 * Zapasowa, ODPORNA NA NIEAKTUALNOŚĆ wersja `focusTarget`: zamiast ufać zapamiętanej
 * referencji DOM (mogła się zdezaktualizować między `open()` a `close()`, np. przez
 * przemontowanie karty przy zmianie filtrów), szuka na świeżo po `data-material-id`
 * w chwili faktycznego przywracania fokusu (PortalLayer, `onExitComplete`).
 */
export function focusTargetById(id: number): HTMLElement | null {
  if (typeof document === "undefined") return null;
  const el = document.querySelector<HTMLElement>(`[data-material-id="${id}"]`);
  return focusTarget(el);
}

const EMPTY_STATE: EngineState = { phase: "idle", article: null, originEl: null, flight: null, exit: null };

export function PortalProvider({
  children,
  historyMode = "none",
}: {
  children: ReactNode;
  historyMode?: PortalHistoryMode;
}) {
  const [state, setState] = useState<EngineState>(EMPTY_STATE);
  const [settled, setSettled] = useState(false);
  const originRef = useRef<HTMLElement | null>(null);

  const preview = useCallback((article: Article, originEl: HTMLElement) => {
    originRef.current = focusTarget(originEl);
    setState((prev) => {
      if (prev.phase === "open") return prev; // pełny ekran już otwarty — podgląd go nie przerywa
      const size = readSize(originEl);
      return {
        phase: "previewing",
        article,
        originEl,
        flight: { rect: originEl.getBoundingClientRect(), radius: CARD_SPEC[size].radius, size, viaClone: false },
        exit: null,
      };
    });
  }, []);

  const endPreview = useCallback(() => {
    setState((prev) => (prev.phase === "previewing" ? EMPTY_STATE : prev));
  }, []);

  // JEDNO wywołanie setState — NIGDY startTransition (docs/UI_KIT_PLAN.md → «Портал»):
  // inaczej ciągłość „klik kontynuuje bieżący rozmiar” rozjechałaby się na dwa commity.
  const open = useCallback((article: Article, originEl?: HTMLElement | null) => {
    setState((prev) => {
      const continuingSameClone = prev.phase === "previewing" && prev.article?.id === article.id;
      const liveClone = continuingSameClone ? findCloneEl(article.id) : null;
      // `prev.originEl` jest wiarygodny TYLKO gdy kontynuujemy TEN SAM materiał — w innym
      // wypadku należałby do zupełnie innej karty (np. wciąż aktywny podgląd sąsiada).
      const resolvedOrigin = originEl ?? (continuingSameClone ? prev.originEl : null) ?? findOriginEl(article.id);
      const rectSource: Element | null = liveClone ?? resolvedOrigin;
      const size = readSize(resolvedOrigin ?? undefined);
      if (resolvedOrigin) originRef.current = focusTarget(resolvedOrigin);
      return {
        phase: "open",
        article,
        originEl: resolvedOrigin,
        flight: rectSource
          ? { rect: rectSource.getBoundingClientRect(), radius: CARD_SPEC[size].radius, size, viaClone: !!liveClone }
          : null,
        exit: null,
      };
    });
    setSettled(false);
  }, []);

  // `phase` wraca do "idle" OD RAZU (nie czeka na koniec animacji): to właśnie ten przełącznik
  // każe PortalLayer przestać renderować dziecko AnimatePresence i uruchomić jego `exit` —
  // sama WIZUALNA obecność powierzchni podczas zamykania żyje dalej w LOKALNYM stanie
  // PortalLayer (`displayed`), niezależnie od tego silnika. `exit` zostaje wypełniony, żeby
  // PortalLayer znał cel animacji wyjścia (jeden z trzech przypadków powrotu).
  const close = useCallback(() => {
    setState((prev) => {
      if (prev.phase !== "open") return prev;
      const el = prev.originEl;
      const fallbackRadius = prev.flight?.radius ?? 18;
      let exit: PortalExit;
      if (el && document.contains(el)) {
        const rect = el.getBoundingClientRect();
        const inViewport = rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth;
        if (!inViewport) {
          // Мгновенная прокрутка к карточке в ТОМ ЖЕ такте — useScrollLock уже погасил
          // scroll-behavior:smooth на время оверлея (frontend-spin/app/globals.css:11).
          el.scrollIntoView({ behavior: "auto", block: "center" });
        }
        const settledRect = el.getBoundingClientRect();
        exit = {
          kind: inViewport ? "card" : "offscreen",
          rect: settledRect,
          radius: fallbackRadius,
          focusEl: focusTarget(el),
          articleId: prev.article?.id ?? null,
        };
      } else {
        // Карточка размонтирована — цели нет, схлопываемся к центру запомненного прямоугольника.
        const rememberedRect = prev.flight?.rect ?? new DOMRect(window.innerWidth / 2, window.innerHeight / 2, 0, 0);
        exit = { kind: "unmounted", rect: rememberedRect, radius: fallbackRadius, focusEl: null, articleId: null };
      }
      return { phase: "idle", article: null, originEl: null, flight: null, exit };
    });
  }, []);

  /** Wywoływane w `onExitComplete` PortalLayer — dopiero wtedy naprawdę „nie ma nic otwartego”. */
  const clearExit = useCallback(() => {
    setState((prev) => (prev.exit ? { ...prev, exit: null } : prev));
    setSettled(false);
  }, []);

  const markSettled = useCallback(() => setSettled(true), []);

  const api = useMemo<PortalApi>(
    () => ({ open, close, preview, endPreview, originRef, historyMode }),
    [open, close, preview, endPreview, historyMode],
  );

  const isActive = useCallback((id: number) => state.phase === "open" && state.article?.id === id, [state.phase, state.article]);
  const isPreviewing = useCallback(
    (id: number) => state.phase === "previewing" && state.article?.id === id,
    [state.phase, state.article],
  );

  const engineValue = useMemo<PortalEngineValue>(
    () => ({
      active: state.phase === "open" ? state.article : null,
      previewing: state.phase === "previewing" ? state.article : null,
      isActive,
      isPreviewing,
      phase: state.phase,
      originEl: state.originEl,
      flight: state.flight,
      exit: state.exit,
      clearExit,
      markSettled,
      settled,
    }),
    [state, isActive, isPreviewing, clearExit, markSettled, settled],
  );

  return (
    <PortalApiContext.Provider value={api}>
      <PortalEngineContext.Provider value={engineValue}>{children}</PortalEngineContext.Provider>
    </PortalApiContext.Provider>
  );
}

export function usePortalApi(): PortalApi {
  const ctx = useContext(PortalApiContext);
  if (!ctx) throw new Error("usePortalApi must be used within <PortalProvider>");
  return ctx;
}

export function usePortalState(): PortalStateValue {
  const ctx = useContext(PortalEngineContext);
  if (!ctx) throw new Error("usePortalState must be used within <PortalProvider>");
  return ctx;
}

/** Pełny silnik — tylko PortalLayer/useHoverExpand (potrzebują `flight`/`exit`/`originEl`/`phase`). */
export function usePortalEngine(): PortalEngineValue {
  const ctx = useContext(PortalEngineContext);
  if (!ctx) throw new Error("usePortalEngine must be used within <PortalProvider>");
  return ctx;
}

/** Połączony hook wg brzmienia kontraktu: `usePortal(): { active, isActive, open, close, originRef }`. */
export function usePortal() {
  const api = usePortalApi();
  const state = usePortalState();
  return { ...state, ...api };
}
