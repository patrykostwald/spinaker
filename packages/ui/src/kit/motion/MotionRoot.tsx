"use client";

import { MotionConfig } from "framer-motion";
import type { ReactNode } from "react";
import { springs } from "./springs";

/**
 * Глобальная настройка framer-motion. reducedMotion="user" — страховка: сам framer-motion
 * гасит transform и layout-анимации для тех, кто просил меньше движения, оставляя прозрачность.
 * useMotionTokens сверху добавляет спроектированную деградацию.
 * Монтируется один раз в frontend-spin/app/providers.tsx.
 */
export function MotionRoot({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user" transition={springs.ui}>
      {children}
    </MotionConfig>
  );
}
