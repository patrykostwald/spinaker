"use client";

/**
 * Pojawienie sekcji przy przewijaniu: `opacity 0→1`, `y rise→0`, raz, przez `whileInView`
 * (IntersectionObserver framera — nie nasłuch scrolla; docs/UI_KIT_PLAN.md → «Переходы между
 * секциями»). Przy zredukowanym ruchu zostaje samo zanikanie (rise = 0).
 */

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { useMotionTokens } from "../motion/useMotionTokens";

export function HomeReveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const m = useMotionTokens();
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: m.rise }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -8% 0px" }}
      transition={m.t("ui", { delay: m.reduced ? 0 : delay })}
    >
      {children}
    </motion.div>
  );
}
