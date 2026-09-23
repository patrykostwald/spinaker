"use client";

import { animate, useMotionValue, useMotionValueEvent, type ValueAnimationTransition } from "framer-motion";
import { useEffect, useRef } from "react";
import { useMotionTokens } from "./useMotionTokens";

export type MorphValueProps = {
  value: number;
  className?: string;
  /** Переопределение форматирования; по умолчанию `toLocaleString('pl-PL')`. */
  format?: (value: number) => string;
};

const defaultFormat = (value: number) => Math.round(value).toLocaleString("pl-PL");

/**
 * Числа и счётчики перетекают, а не перескакивают. Значение анимируется на `MotionValue`
 * (пружина `move`) и пишется в DOM напрямую через подписку — не через React-рендер на
 * каждый кадр. Под уменьшенным движением значение подставляется мгновенно.
 * `tabular-nums` — через класс `sc-t-mono`, чтобы соседние цифры не «дышали» по ширине.
 */
export function MorphValue({ value, className, format = defaultFormat }: MorphValueProps) {
  const m = useMotionTokens();
  const motionValue = useMotionValue(value);
  const nodeRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (m.reduced) {
      motionValue.set(value);
      return;
    }
    // Приведение типа: `t()` типизирован как React-проп `Transition` (framer-motion), у
    // императивного `animate()` из motion-dom чуть более узкий тип опций; формы совпадают.
    const controls = animate(motionValue, value, m.t("move") as ValueAnimationTransition<number>);
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, m.reduced]);

  useMotionValueEvent(motionValue, "change", (latest) => {
    if (nodeRef.current) nodeRef.current.textContent = format(latest);
  });

  return (
    <span ref={nodeRef} className={className ? `${className} sc-t-mono` : "sc-t-mono"}>
      {format(value)}
    </span>
  );
}
