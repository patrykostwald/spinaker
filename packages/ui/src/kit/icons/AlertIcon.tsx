"use client";

import { motion } from "framer-motion";
import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";
import { useMotionTokens } from "../motion/useMotionTokens";

/** Błąd, ostrzeżenie. Pojawia się przez scale .8 → 1 przy każdym zamontowaniu. */
export function AlertIcon({ size = 24, className, title }: IconProps) {
  const { t, scale } = useMotionTokens();
  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={iconStroke(size)}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      initial={{ opacity: 0, scale: scale(0.8) }}
      animate={{ opacity: 1, scale: scale(1) }}
      transition={t("ui")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M12 3.5 21 19H3z" />
      <path d="M12 10v4" />
      <line x1="12" y1="16.6" x2="12" y2="16.61" />
    </motion.svg>
  );
}
