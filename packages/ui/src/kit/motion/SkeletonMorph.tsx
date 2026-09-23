"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { useMotionTokens } from "./useMotionTokens";

export type SkeletonMorphProps = {
  loading: boolean;
  /** Блоки-заглушки, использующие класс `.sc-skeleton` — стоят в тех же боксах, что контент. */
  skeleton: ReactNode;
  children: ReactNode;
  className?: string;
};

/**
 * Скелет → контент: оба слоя лежат в одной ячейке CSS-грида (`.sc-skeleton-morph`), поэтому
 * раскладка не меняется — меняется только то, что видно. Переход — кросс-фейд на `fade`,
 * без масштаба и смещения (это не появление, а подмена того же места). Пульсация самих
 * блоков `.sc-skeleton` — в kit.css (период ≥1.6s, выключена при уменьшенном движении
 * глобальным килсвитчем `prefers-reduced-motion`).
 */
export function SkeletonMorph({ loading, skeleton, children, className }: SkeletonMorphProps) {
  const m = useMotionTokens();
  return (
    <div className={className ? `sc-skeleton-morph ${className}` : "sc-skeleton-morph"}>
      <AnimatePresence initial={false}>
        {loading ? (
          <motion.div
            key="skeleton"
            className="sc-skeleton-morph__layer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: m.t("fade") }}
            exit={{ opacity: 0, transition: m.t("fade") }}
          >
            {skeleton}
          </motion.div>
        ) : (
          <motion.div
            key="content"
            className="sc-skeleton-morph__layer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: m.t("fade") }}
            exit={{ opacity: 0, transition: m.t("fade") }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
