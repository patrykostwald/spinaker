"use client";

import { motion } from "framer-motion";
import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";
import { useMotionTokens } from "../motion/useMotionTokens";

export interface EyeIconProps extends IconProps {
  /** Prywatność profilu. true (domyślnie) — oko otwarte; false — przekreślone (eye-off). */
  visible?: boolean;
}

/** Morfing przez dorysowanie/zmazanie przekreślenia (pathLength), a nie podmianę ikony. */
export function EyeIcon({ size = 24, className, title, visible = true }: EyeIconProps) {
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
      strokeLinejoin="round"
      className={className}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <motion.circle
        cx="12"
        cy="12"
        r="3"
        initial={false}
        animate={{ scale: visible ? 1 : 0.6, opacity: visible ? 1 : 0.4 }}
        style={{ transformOrigin: "12px 12px" }}
        transition={t("ui")}
      />
      <motion.line
        x1="4"
        y1="20"
        x2="20"
        y2="4"
        initial={false}
        animate={{ pathLength: visible ? 0 : 1, opacity: visible ? 0 : 1 }}
        transition={t("ui")}
      />
    </svg>
  );
}
