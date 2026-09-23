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
        {/* Симметричное минималистичное сердце: две равные дуги r=5.5, зеркально вокруг x=12 (замечание владельца 24.09). */}
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
      </svg>
    </span>
  );
}
