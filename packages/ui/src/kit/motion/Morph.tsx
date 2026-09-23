"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { forwardRef, useMemo, type ElementType, type ReactNode } from "react";
import { useMotionTokens } from "./useMotionTokens";

export type MorphProps = {
  /** Тег или компонент-обёртка. По умолчанию `div`. */
  as?: ElementType;
  /** `true` — полный layout (размер+позиция), `'position'` — дешевле, только позиция. */
  layout?: boolean | "position";
  /**
   * Радиус скругления, px. Передаётся ИНЛАЙНОВО и ЧИСЛОМ на том же элементе, что несёт
   * `layoutId`/`layout`: морфинг — это проекция translate+scale, а не анимация width/height,
   * поэтому радиус из CSS растягивается в эллипс на промежуточных кадрах. framer-motion
   * корректирует только те радиусы, которыми владеет сам (см. docs/UI_KIT_PLAN.md → «Пружины»).
   */
  radius?: number;
  children?: ReactNode;
  className?: string;
} & Omit<HTMLMotionProps<"div">, "as" | "layout" | "children" | "className">;

/**
 * Контейнер с `layout` — плавно меняет размер и позицию при любом изменении содержимого.
 * Базовый кирпич «сплошной системы движения»: ни один компонент не меняет визуальное
 * состояние в обход примитивов движения (docs/UI_KIT_PLAN.md → «Сплошная система движения»).
 */
export const Morph = forwardRef<HTMLElement, MorphProps>(function Morph(
  { as = "div", layout = true, radius, style, transition, children, ...rest },
  ref,
) {
  const m = useMotionTokens();
  // motion.create(tag) мемоизируется на теге — иначе новый компонент на каждый рендер
  // означал бы размонтирование узла (framer-motion, «Dynamic component with a prop»).
  const Tag = useMemo(() => motion.create(as as ElementType), [as]);
  return (
    <Tag
      ref={ref}
      layout={layout}
      transition={transition ?? m.t("move")}
      style={radius === undefined ? style : { ...style, borderRadius: radius }}
      {...rest}
    >
      {children}
    </Tag>
  );
});
