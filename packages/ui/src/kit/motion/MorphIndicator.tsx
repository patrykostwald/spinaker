"use client";

import { motion } from "framer-motion";
import { useMotionTokens } from "./useMotionTokens";

export type MorphIndicatorProps = {
  /**
   * Общий `layoutId` группы (табы, пилюли, пункты навигации). Одинаков у ВСЕХ
   * инстансов одной группы — так framer-motion понимает, что это один и тот же
   * визуальный объект, переезжающий между позициями, а не новый на каждый рендер.
   */
  id: string;
  /** Активный элемент передаёт `true` — индикатор рендерится только у него. */
  active: boolean;
  variant?: "underline" | "pill";
  className?: string;
};

/**
 * Общий `layoutId`-индикатор для табов, пилюль и навигации. Рендерится ВНУТРИ активного
 * элемента (родитель — `position: relative`); при смене активного элемента framer-motion
 * анимирует переезд между позициями вместо «погасить-зажечь». Едет на пружине `move`.
 */
export function MorphIndicator({ id, active, variant = "underline", className }: MorphIndicatorProps) {
  const m = useMotionTokens();
  if (!active) return null;
  const variantClass = variant === "pill" ? "sc-morph-indicator--pill" : "sc-morph-indicator--underline";
  return (
    <motion.span
      layoutId={m.morph ? id : undefined}
      className={className ? `sc-morph-indicator ${variantClass} ${className}` : `sc-morph-indicator ${variantClass}`}
      transition={m.t("move")}
      aria-hidden="true"
    />
  );
}
