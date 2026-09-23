"use client";

import { motion } from "framer-motion";
import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";
import { useMotionTokens } from "../motion/useMotionTokens";

export interface CheckIconProps extends IconProps {
  /** Czy kreska ma się rysować (pathLength 0→1) przy zamontowaniu. Domyślnie true. */
  animate?: boolean;
}

/** Ptaszek — flażki, zaznaczony punkt menu. Rysuje się kreską (~0.2s), a nie pojawia całością. */
export function CheckIcon({ size = 24, className, title, animate = true }: CheckIconProps) {
  const { t, reduced } = useMotionTokens();
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
      <motion.path
        d="M5 12.5 10 17.5 19 7"
        initial={animate ? { pathLength: 0 } : false}
        animate={{ pathLength: 1 }}
        transition={animate ? t("ui", { duration: reduced ? 0.12 : 0.2, bounce: 0 }) : { duration: 0 }}
      />
    </svg>
  );
}
