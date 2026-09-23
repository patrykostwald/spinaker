"use client";

import { motion } from "framer-motion";
import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";
import { useMotionTokens } from "../motion/useMotionTokens";

export interface PlusIconProps extends IconProps {
  /** Dodanie do nitki / „dodaj temat”. Gdy true — obraca się o 45°, wyglądając jak krzyżyk. */
  active?: boolean;
}

export function PlusIcon({ size = 24, className, title, active = false }: PlusIconProps) {
  const { t } = useMotionTokens();
  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={iconStroke(size)}
      strokeLinecap="round"
      className={className}
      style={{ transformOrigin: "12px 12px" }}
      initial={false}
      animate={{ rotate: active ? 45 : 0 }}
      transition={t("ui")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M12 5v14M5 12h14" />
    </motion.svg>
  );
}
