"use client";

import { motion } from "framer-motion";
import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";
import { useMotionTokens } from "../motion/useMotionTokens";

export interface MenuCloseProps extends IconProps {
  /** false — hamburger (menu); true — krzyżyk (close). Trzy kreski morfują transformem/opacity. */
  open: boolean;
}

/** Mobilna nawigacja. Morfing menu ↔ close: paski zjeżdżają się i składają w krzyż. */
export function MenuClose({ size = 24, className, title, open }: MenuCloseProps) {
  const { t } = useMotionTokens();
  const origin = { transformOrigin: "12px 12px" };
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
      <motion.line x1="5" y1="12" x2="19" y2="12" style={origin} initial={false} animate={{ y: open ? 0 : -5, rotate: open ? 45 : 0 }} transition={t("ui")} />
      <motion.line x1="5" y1="12" x2="19" y2="12" style={origin} initial={false} animate={{ opacity: open ? 0 : 1 }} transition={t("ui")} />
      <motion.line x1="5" y1="12" x2="19" y2="12" style={origin} initial={false} animate={{ y: open ? 0 : 5, rotate: open ? -45 : 0 }} transition={t("ui")} />
    </svg>
  );
}
