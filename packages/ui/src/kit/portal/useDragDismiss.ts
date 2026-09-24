"use client";

import {
  animate,
  useDragControls,
  useMotionValue,
  useTransform,
  type DragControls,
  type MotionValue,
  type PanInfo,
  type ValueAnimationTransition,
} from "framer-motion";
import { useCallback, type PointerEvent as ReactPointerEvent } from "react";
import { shouldDismiss } from "../motion/physics";
import { useMotionTokens } from "../motion/useMotionTokens";

export type DragDismissOptions = {
  /** Высота поверхности в px — знаменатель порога закрытия (`DISTANCE_COMMIT` из physics.ts). */
  height: number;
  /** Решение принято: закрыть. Вызывающий сам проигрывает выход, например
   * `responsive(springs.portalOut, velocity)` — эта длительность остаётся на его стороне. */
  onDismiss: (velocity: number) => void;
};

export type DragDismissDragProps = {
  drag: "y" | false;
  dragDirectionLock: true;
  dragConstraints: { top: number };
  dragElastic: { top: number };
  dragMomentum: false;
  dragListener: false;
  dragControls: DragControls;
  onDragEnd: (event: PointerEvent | MouseEvent | TouchEvent, info: PanInfo) => void;
};

export type DragDismiss = {
  /** Смещение поверхности по Y. */
  y: MotionValue<number>;
  /** Прозрачность затемнения: 1→0 на первых 60% высоты. */
  scrimOpacity: MotionValue<number>;
  /** Масштаб поверхности: 1→.92 на всей высоте. */
  surfaceScale: MotionValue<number>;
  /** Радиус скругления поверхности: 0→28 на первых 160px. */
  surfaceRadius: MotionValue<number>;
  dragControls: DragControls;
  /** Готовый набор пропсов для motion-элемента поверхности. */
  dragProps: DragDismissDragProps;
  /**
   * Стартует жест ТОЛЬКО если внутренний скроллер уже наверху — иначе попытка
   * прокрутить содержимое вверх закрывала бы оверлей вместо прокрутки.
   */
  startIfAtTop: (event: ReactPointerEvent, scrollerEl: HTMLElement | null) => void;
};

/**
 * Закрытие полноэкранной поверхности перетаскиванием вниз (Apple, «Designing Fluid
 * Interfaces»). Прозрачность фона, масштаб и радиус меняются ВО ВРЕМЯ жеста через
 * `useTransform` — на композиторе, без единого React-рендера. Решение «закрыть/вернуть»
 * принимает `shouldDismiss` по знаку скорости, а не по достигнутой позиции. Возврат —
 * пружина `settle` с ПЕРЕДАЧЕЙ реальной скорости отпускания.
 */
export function useDragDismiss({ height, onDismiss }: DragDismissOptions): DragDismiss {
  const m = useMotionTokens();
  const y = useMotionValue(0);
  const dragControls = useDragControls();

  const scrimOpacity = useTransform(y, [0, Math.max(height * 0.6, 1)], [1, 0]);
  const surfaceScale = useTransform(y, [0, Math.max(height, 1)], [1, 0.92]);
  const surfaceRadius = useTransform(y, [0, 160], [0, 28]);

  const onDragEnd = useCallback(
    (_event: PointerEvent | MouseEvent | TouchEvent, info: PanInfo) => {
      if (shouldDismiss(info.offset.y, info.velocity.y, height)) {
        onDismiss(info.velocity.y);
        return;
      }
      // Передача скорости: пружина по MotionValue принимает начальную скорость (в отличие
      // от layout-анимации выхода, куда скорость по осям не вложить — см. план, «Портал»).
      animate(y, 0, { ...m.t("settle"), velocity: info.velocity.y } as ValueAnimationTransition<number>);
    },
    [height, m, onDismiss, y],
  );

  const startIfAtTop = useCallback(
    (event: ReactPointerEvent, scrollerEl: HTMLElement | null) => {
      if (scrollerEl && scrollerEl.scrollTop > 0) return;
      dragControls.start(event);
    },
    [dragControls],
  );

  return {
    y,
    scrimOpacity,
    surfaceScale,
    surfaceRadius,
    dragControls,
    dragProps: {
      drag: m.gestures ? "y" : false,
      dragDirectionLock: true,
      dragConstraints: { top: 0 },
      dragElastic: { top: 0.08 },
      dragMomentum: false,
      dragListener: false,
      dragControls,
      onDragEnd,
    },
    startIfAtTop,
  };
}
