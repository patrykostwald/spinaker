"use client";

import { Reorder, useDragControls, type DragControls, type PanInfo, type Transition } from "framer-motion";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { useMotionTokens } from "./motion/useMotionTokens";
import { LONG_PRESS_MS } from "./tokens";
import { GripIcon } from "./icons/GripIcon";

export type ReorderableStrip = { id: string; title: string };

export type ReorderableStripsProps<T extends ReorderableStrip> = {
  strips: T[];
  /** Содержимое полосы — заглушки витрины рисует вызывающий, не `NewsCard` (её строит R3). */
  renderStrip: (strip: T) => ReactNode;
  /** Ключ `localStorage`. Порядок сохраняется НА УСТРОЙСТВЕ, не в профиле — см. план. */
  storageKey?: string;
  /** Подпись группы для скринридера. */
  label?: string;
  onReorder?: (strips: T[]) => void;
  className?: string;
};

const AUTOSCROLL_MARGIN = 96;
const AUTOSCROLL_MAX_SPEED = 16;
const LONG_PRESS_MOVE_CANCEL_PX = 10;

function readStoredOrder(storageKey: string): string[] | null {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : null;
  } catch {
    return null;
  }
}

function applyStoredOrder<T extends ReorderableStrip>(strips: T[], order: string[] | null): T[] {
  if (!order) return strips;
  const byId = new Map(strips.map((s) => [s.id, s] as const));
  const ordered = order.map((id) => byId.get(id)).filter((s): s is T => Boolean(s));
  for (const strip of strips) if (!ordered.includes(strip)) ordered.push(strip);
  return ordered.length === strips.length ? ordered : strips;
}

/** Долгое нажатие 250ms на тач-устройствах для захвата; на мыши/пере — захват немедленно. */
function useHandlePickup(dragControls: DragControls) {
  const timerRef = useRef<number | undefined>(undefined);
  const startRef = useRef<{ x: number; y: number } | null>(null);
  const pendingRef = useRef<ReactPointerEvent | null>(null);

  const cancel = useCallback(() => {
    window.clearTimeout(timerRef.current);
    timerRef.current = undefined;
    startRef.current = null;
    pendingRef.current = null;
  }, []);

  const onPointerDown = useCallback(
    (event: ReactPointerEvent) => {
      if (event.pointerType !== "touch") {
        dragControls.start(event);
        return;
      }
      startRef.current = { x: event.clientX, y: event.clientY };
      pendingRef.current = event;
      timerRef.current = window.setTimeout(() => {
        if (pendingRef.current) dragControls.start(pendingRef.current);
        cancel();
      }, LONG_PRESS_MS);
    },
    [cancel, dragControls],
  );

  const onPointerMove = useCallback(
    (event: ReactPointerEvent) => {
      if (!startRef.current) return;
      const dx = event.clientX - startRef.current.x;
      const dy = event.clientY - startRef.current.y;
      if (Math.hypot(dx, dy) > LONG_PRESS_MOVE_CANCEL_PX) cancel();
    },
    [cancel],
  );

  return { onPointerDown, onPointerMove, onPointerUp: cancel, onPointerCancel: cancel };
}

/**
 * Перетаскивание полос: `Reorder.Group`/`Reorder.Item`, захват только за ручку (жест не
 * должен отбирать горизонтальную прокрутку содержимого полосы). Мышь и перо забирают жест
 * немедленно, тач — долгим нажатием `LONG_PRESS_MS`. Клавиатура: Space — взять, ↑/↓ —
 * переместить, Space — положить, Escape — отменить; каждое перемещение объявляется через
 * `aria-live`. Порядок сохраняется в `localStorage` под `storageKey`.
 */
export function ReorderableStrips<T extends ReorderableStrip>({
  strips,
  renderStrip,
  storageKey = "sc-strips-order",
  label = "Kolejność pasków",
  onReorder,
  className,
}: ReorderableStripsProps<T>) {
  const m = useMotionTokens();
  const [order, setOrder] = useState<T[]>(strips);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const orderRef = useRef(order);
  orderRef.current = order;
  const snapshotRef = useRef<T[] | null>(null);
  const suppressNextReorder = useRef(false);
  const autoscroll = useRef({ speed: 0, raf: 0 });

  // Гидратация из localStorage один раз после монтирования — чтобы SSR и первый клиентский
  // рендер совпадали (порядок по умолчанию — это порядок `strips`).
  useEffect(() => {
    const stored = readStoredOrder(storageKey);
    if (stored) setOrder((current) => applyStoredOrder(current, stored));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  // Родитель может обновить набор полос — сохраняем пользовательский порядок там, где можно.
  useEffect(() => {
    setOrder((current) => {
      const byId = new Map(current.map((s) => [s.id, s] as const));
      return strips.map((s) => byId.get(s.id) ?? s);
    });
  }, [strips]);

  const persist = useCallback(
    (next: T[]) => {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(next.map((s) => s.id)));
      } catch {
        /* localStorage недоступен (приватный режим) — порядок просто не переживёт перезагрузку. */
      }
    },
    [storageKey],
  );

  const commitOrder = useCallback(
    (next: T[]) => {
      setOrder(next);
      persist(next);
      onReorder?.(next);
    },
    [onReorder, persist],
  );

  const handleReorder = useCallback(
    (next: T[]) => {
      if (suppressNextReorder.current) {
        suppressNextReorder.current = false;
        return;
      }
      commitOrder(next);
    },
    [commitOrder],
  );

  const stopAutoscroll = useCallback(() => {
    autoscroll.current.speed = 0;
    if (autoscroll.current.raf) {
      cancelAnimationFrame(autoscroll.current.raf);
      autoscroll.current.raf = 0;
    }
  }, []);

  const tickAutoscroll = useCallback(() => {
    if (autoscroll.current.speed !== 0) {
      window.scrollBy(0, autoscroll.current.speed);
      autoscroll.current.raf = requestAnimationFrame(tickAutoscroll);
    } else {
      autoscroll.current.raf = 0;
    }
  }, []);

  const handleDragProgress = useCallback(
    (_event: PointerEvent | MouseEvent | TouchEvent, info: PanInfo) => {
      const y = info.point.y;
      const vh = window.innerHeight;
      let speed = 0;
      if (y < AUTOSCROLL_MARGIN) {
        speed = -AUTOSCROLL_MAX_SPEED * (1 - Math.max(y, 0) / AUTOSCROLL_MARGIN);
      } else if (y > vh - AUTOSCROLL_MARGIN) {
        speed = AUTOSCROLL_MAX_SPEED * (1 - Math.max(vh - y, 0) / AUTOSCROLL_MARGIN);
      }
      autoscroll.current.speed = speed;
      if (speed !== 0 && !autoscroll.current.raf) {
        autoscroll.current.raf = requestAnimationFrame(tickAutoscroll);
      }
    },
    [tickAutoscroll],
  );

  const beginPointerDrag = useCallback((strip: T) => {
    snapshotRef.current = orderRef.current;
    setDraggingId(strip.id);
    const index = orderRef.current.findIndex((s) => s.id === strip.id);
    setAnnouncement(`${strip.title} — pozycja ${index + 1} z ${orderRef.current.length}`);
  }, []);

  const endPointerDrag = useCallback(() => {
    setDraggingId(null);
    stopAutoscroll();
  }, [stopAutoscroll]);

  // Escape во время перетаскивания мышью/пальцем — отмена, полоса возвращается на место.
  useEffect(() => {
    if (!draggingId) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      suppressNextReorder.current = true;
      if (snapshotRef.current) commitOrder(snapshotRef.current);
      setDraggingId(null);
      stopAutoscroll();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [commitOrder, draggingId, stopAutoscroll]);

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent, strip: T) => {
      if (event.key === " " || event.key === "Enter") {
        event.preventDefault();
        if (pickedId === strip.id) {
          const index = orderRef.current.findIndex((s) => s.id === strip.id);
          setAnnouncement(`${strip.title} — upuszczono, pozycja ${index + 1} z ${orderRef.current.length}`);
          setPickedId(null);
          return;
        }
        snapshotRef.current = orderRef.current;
        const index = orderRef.current.findIndex((s) => s.id === strip.id);
        setAnnouncement(
          `${strip.title} — pozycja ${index + 1} z ${orderRef.current.length}. Strzałki zmieniają miejsce, Escape anuluje.`,
        );
        setPickedId(strip.id);
        return;
      }
      if (pickedId !== strip.id) return;
      if (event.key === "ArrowUp" || event.key === "ArrowDown") {
        event.preventDefault();
        const current = orderRef.current;
        const from = current.findIndex((s) => s.id === strip.id);
        const to = event.key === "ArrowUp" ? from - 1 : from + 1;
        if (from < 0 || to < 0 || to >= current.length) return;
        const next = current.slice();
        next.splice(from, 1);
        next.splice(to, 0, strip);
        commitOrder(next);
        setAnnouncement(`${strip.title} — pozycja ${to + 1} z ${next.length}`);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        if (snapshotRef.current) commitOrder(snapshotRef.current);
        setPickedId(null);
        const index = (snapshotRef.current ?? orderRef.current).findIndex((s) => s.id === strip.id);
        setAnnouncement(`${strip.title} — anulowano, pozycja ${index + 1} z ${orderRef.current.length}`);
      }
    },
    [commitOrder, pickedId],
  );

  return (
    <div className={className ? `sc-reorder-strips ${className}` : "sc-reorder-strips"}>
      <Reorder.Group
        as="ul"
        axis="y"
        values={order}
        onReorder={handleReorder}
        className="sc-reorder-strips__list"
        aria-label={label}
      >
        {order.map((strip) => (
          <StripRow
            key={strip.id}
            strip={strip}
            dragging={draggingId}
            picked={pickedId === strip.id}
            transitionMove={m.t("move")}
            transitionSheet={m.t("sheet")}
            onBeginPointerDrag={beginPointerDrag}
            onDragProgress={handleDragProgress}
            onEndPointerDrag={endPointerDrag}
            onKeyDown={handleKeyDown}
            renderStrip={renderStrip}
          />
        ))}
      </Reorder.Group>

      <p className="sc-t-caption sc-text-2 sc-reorder-strips__note">Kolejność zapisana na tym urządzeniu.</p>
      <div aria-live="polite" className="sc-visually-hidden">
        {announcement}
      </div>
    </div>
  );
}

function StripRow<T extends ReorderableStrip>({
  strip,
  dragging,
  picked,
  transitionMove,
  transitionSheet,
  onBeginPointerDrag,
  onDragProgress,
  onEndPointerDrag,
  onKeyDown,
  renderStrip,
}: {
  strip: T;
  dragging: string | null;
  picked: boolean;
  transitionMove: Transition;
  transitionSheet: Transition;
  onBeginPointerDrag: (strip: T) => void;
  onDragProgress: (event: PointerEvent | MouseEvent | TouchEvent, info: PanInfo) => void;
  onEndPointerDrag: () => void;
  onKeyDown: (event: ReactKeyboardEvent, strip: T) => void;
  renderStrip: (strip: T) => ReactNode;
}) {
  const dragControls = useDragControls();
  const pickup = useHandlePickup(dragControls);
  const isDragging = dragging === strip.id;
  const isDimmed = dragging !== null && !isDragging;

  return (
    <Reorder.Item
      value={strip}
      dragListener={false}
      dragControls={dragControls}
      layout
      as="li"
      className="sc-strip-row"
      data-dragging={isDragging || undefined}
      onDragStart={() => onBeginPointerDrag(strip)}
      onDrag={onDragProgress}
      onDragEnd={onEndPointerDrag}
      animate={{ scale: isDragging ? 1.02 : 1, opacity: isDimmed ? 0.75 : 1 }}
      transition={{ layout: transitionMove, default: transitionSheet }}
    >
      <div className="sc-strip-row__head">
        <button
          type="button"
          className="sc-strip-handle sc-hoverable"
          aria-label={`Zmień kolejność: ${strip.title}`}
          aria-roledescription="Uchwyt do zmiany kolejności"
          data-picked={picked || undefined}
          style={{ touchAction: "none" }}
          onPointerDown={pickup.onPointerDown}
          onPointerMove={pickup.onPointerMove}
          onPointerUp={pickup.onPointerUp}
          onPointerCancel={pickup.onPointerCancel}
          onKeyDown={(event) => onKeyDown(event, strip)}
        >
          <GripIcon size={20} />
        </button>
        <h3 className="sc-t-title-s sc-strip-row__title">{strip.title}</h3>
      </div>
      <div className="sc-strip-row__body">{renderStrip(strip)}</div>
    </Reorder.Item>
  );
}
