"use client";

import { LayoutGroup, motion } from "framer-motion";
import { useMotionTokens } from "./motion/useMotionTokens";

export interface SegmentedOption {
  value: string;
  label: string;
}

export interface SegmentedProps {
  name: string;
  value: string;
  onChange: (value: string) => void;
  options: SegmentedOption[];
  disabled?: boolean;
  label: string;
  className?: string;
}

/**
 * Segmentowany przełącznik (docs/UI_KIT_PLAN.md → «Селекторы, флажки и переключатели»).
 * Wskaźnik przejeżdża wspólnym `layoutId`, cały kontrol skaluje się do .98 przy naciśnięciu.
 */
export function Segmented({ name, value, onChange, options, disabled = false, label, className }: SegmentedProps) {
  const { t, scale } = useMotionTokens();
  return (
    <div
      className={["sc-segmented", className].filter(Boolean).join(" ")}
      role="radiogroup"
      aria-label={label}
      data-disabled={disabled || undefined}
    >
      <LayoutGroup id={`sc-segmented-${name}`}>
        {options.map((opt) => {
          const active = value === opt.value;
          return (
            <motion.button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={active}
              className="sc-segmented__item"
              data-active={active || undefined}
              disabled={disabled}
              whileTap={disabled ? undefined : { scale: scale(0.98) }}
              transition={t("press")}
              onClick={() => onChange(opt.value)}
            >
              {active && <motion.span layoutId={`sc-segmented-indicator-${name}`} className="sc-segmented__indicator" transition={t("move")} />}
              <span className="sc-segmented__label sc-t-meta">{opt.label}</span>
            </motion.button>
          );
        })}
      </LayoutGroup>
    </div>
  );
}
