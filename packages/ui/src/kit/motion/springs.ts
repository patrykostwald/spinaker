import type { Transition } from "framer-motion";

/**
 * Каноническая таблица пружин библиотеки (docs/UI_KIT_PLAN.md → «Пружины»).
 * Только пара bounce + duration: она сохраняет характер движения на любой дистанции —
 * от нажатия кнопки до морфинга карточки 184px → 1200px. stiffness/damping/mass не используем.
 * restDelta/restSpeed выше умолчаний: иначе пружина живёт 10–20 невидимых кадров после остановки.
 */
const spring = (bounce: number, duration: number): Transition => ({
  type: "spring",
  bounce,
  duration,
  restDelta: 0.5,
  restSpeed: 2,
});

export const springs = {
  /** Наведение, подсветка, кромка, служебные переходы. Bounce 0.18 — по просьбе владельца, см. «Три ступени». */
  ui: spring(0.18, 0.26),
  /** Нажатие: должно уложиться в один кадр ввода. */
  press: spring(0, 0.16),
  /** Переезд на новое место: индикаторы, layout-перестановки. */
  move: spring(0, 0.4),
  /** Только прозрачность. */
  fade: spring(0, 0.25),
  /** Карточка → полный экран. Крошечный отскок; выше 0.15 контейнер вылезает за окно. */
  portalIn: spring(0.12, 0.42),
  /** Полный экран → карточка. Закрытие никогда не пружинит. */
  portalOut: spring(0, 0.34),
  /** Затемнение и обвязка, едущие вместе с морфингом; чуть быстрее него. */
  scrim: spring(0, 0.28),
  /** Нижний лист, шторка, захват при перетаскивании (Apple: damping 0.8, response 0.3). */
  sheet: spring(0.2, 0.3),
  /** Возврат после отпускания с реальной инерцией. */
  settle: spring(0.25, 0.38),
  /** Содержимое, раскрывающееся внутри расширения — здесь живёт «bounce» владельца. */
  expand: spring(0.22, 0.4),
  /** Сворачивание. Не отскакивает. */
  collapse: spring(0, 0.26),
  /** Замена любой пружины при prefers-reduced-motion: короткое затухание, всё ещё прерываемое. */
  reduced: spring(0, 0.18),
} as const satisfies Record<string, Transition>;

export type SpringName = keyof typeof springs;

/**
 * Длительность, зависящая от скорости отпускания: резкий бросок должен разрешаться быстрее,
 * чем ленивый толчок. Используется на выходе портала после перетаскивания.
 */
export function responsive(base: Transition, velocityPxPerSec: number): Transition {
  const v = Math.abs(velocityPxPerSec);
  const duration = Math.max(0.24, Math.min(0.46, 0.46 - v / 4000));
  return { ...base, duration };
}
