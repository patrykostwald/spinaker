"use client";

/** Sekcje pozostają widoczne również przed przewinięciem i bez animacji. */

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { useMotionTokens } from "../motion/useMotionTokens";

export function HomeReveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const m = useMotionTokens();
  return (
    <motion.div
      className={className}
      initial={false}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -8% 0px" }}
      transition={m.t("ui", { delay: m.reduced ? 0 : delay })}
    >
      {children}
    </motion.div>
  );
}
