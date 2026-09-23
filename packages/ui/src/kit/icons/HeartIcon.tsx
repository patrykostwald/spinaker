"use client";

import { useEffect, useRef, useState } from "react";
import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

export interface HeartIconProps extends IconProps {
  /** Ulubione. Gdy true — kontur wypełnia się kolorem, ikona „strzela” scale 1→1.25→1. */
  filled?: boolean;
}

/**
 * Ulubione. Włączenie: wypełnienie + jednorazowe „strzelenie” (`.sc-icon-heart[data-pop="run"]`
 * w kit.css) i lekka poświata — ten sam jednorazowy wzorzec co `.sc-sheen`, czysty CSS keyframe,
 * nie framer: kill-switch prefers-reduced-motion w kit.css i tak go gasi.
 */
export function HeartIcon({ size = 24, className, title, filled = false }: HeartIconProps) {
  const prev = useRef(filled);
  const [pop, setPop] = useState(false);

  useEffect(() => {
    if (filled && !prev.current) {
      setPop(true);
      const id = window.setTimeout(() => setPop(false), 320);
      prev.current = filled;
      return () => window.clearTimeout(id);
    }
    prev.current = filled;
    return undefined;
  }, [filled]);

  return (
    <span className="sc-icon-heart" data-pop={pop ? "run" : undefined}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={iconStroke(size)}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        {...iconA11yProps(title)}
      >
        {title ? <title>{title}</title> : null}
        <path d="M12 20.5s-7.5-4.6-10-9.3C.4 7.8 2 4 5.6 4c2 0 3.6 1.1 4.4 2.7C10.8 5.1 12.4 4 14.4 4 18 4 19.6 7.8 18 11.2 15.5 15.9 12 20.5 12 20.5Z" />
      </svg>
    </span>
  );
}
