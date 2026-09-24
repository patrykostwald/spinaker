"use client";

import { motion } from "framer-motion";
import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";
import { useMotionTokens } from "../motion/useMotionTokens";

export interface ThemeIconProps extends IconProps {
  mode: "sun" | "moon";
}

/**
 * Przełącznik motywu. Morfing jednej formy w drugą przez zestaw dwóch warstw
 * (słońce / księżyc) krzyżowo przenikających się scale+opacity+rotate — nie przez
 * interpolację `d` (system animuje wyłącznie transform i opacity).
 */
export function ThemeIcon({ size = 24, className, title, mode }: ThemeIconProps) {
  const { t } = useMotionTokens();
  const sun = mode === "sun";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={iconStroke(size)}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <motion.g
        style={{ transformOrigin: "12px 12px" }}
        initial={false}
        animate={{ opacity: sun ? 1 : 0, scale: sun ? 1 : 0.5, rotate: sun ? 0 : -90 }}
        transition={t("ui")}
      >
        <circle cx="12" cy="12" r="4.2" />
        <path d="M12 2.8v2.4M12 18.8v2.4M21.2 12h-2.4M5.2 12H2.8M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7M18.4 18.4l-1.7-1.7M7.3 7.3 5.6 5.6" />
      </motion.g>
      <motion.g
        style={{ transformOrigin: "12px 12px" }}
        initial={false}
        animate={{ opacity: sun ? 0 : 1, scale: sun ? 0.5 : 1, rotate: sun ? 90 : 0 }}
        transition={t("ui")}
      >
        <path d="M19 14.2A7.6 7.6 0 1 1 9.8 5 6 6 0 0 0 19 14.2Z" />
      </motion.g>
    </svg>
  );
}
