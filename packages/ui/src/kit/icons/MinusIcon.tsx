"use client";

import { motion } from "framer-motion";
import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";
import { useMotionTokens } from "../motion/useMotionTokens";

export interface MinusIconProps extends IconProps {
  /** Czy kreska ma rosnąć od środka (scaleX 0→1) przy zamontowaniu. Domyślnie true. */
  animate?: boolean;
}

/** Flażek nieokreślony (indeterminate). Kreska rośnie od środka do krawędzi. */
export function MinusIcon({ size = 24, className, title, animate = true }: MinusIconProps) {
  const { t } = useMotionTokens();
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={iconStroke(size)}
      strokeLinecap="round"
      className={className}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <motion.line
        x1="5"
        y1="12"
        x2="19"
        y2="12"
        style={{ transformOrigin: "12px 12px" }}
        initial={animate ? { scaleX: 0 } : false}
        animate={{ scaleX: 1 }}
        transition={t("ui")}
      />
    </svg>
  );
}
