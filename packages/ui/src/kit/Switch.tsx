"use client";

import { useId } from "react";
import { motion } from "framer-motion";
import { useMotionTokens } from "./motion/useMotionTokens";

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  error?: boolean;
  label: string;
  id?: string;
  name?: string;
  className?: string;
}

const TRAVEL = 16; // px — szerokość toru (40) − rozmiar suwaka (20) − 2×dopełnienie (2)

/**
 * Przełącznik (docs/UI_KIT_PLAN.md → «Селекторы, флажки и переключатели»).
 * Suwak jedzie pружиną `move`, tor przechodzi kolorem (czysty CSS, patrz kit.css),
 * suwak lekko rozciąga się w kierunku ruchu i zbiera na końcu — podpowiedź kierunku.
 * Zablokowany: opacity .4, ruch zostaje, żeby stan czytał się bez koloru.
 */
export function Switch({ checked, onChange, disabled = false, error = false, label, id, name, className }: SwitchProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const { t, scale } = useMotionTokens();

  return (
    <label
      htmlFor={inputId}
      className={["sc-switch", className].filter(Boolean).join(" ")}
      data-state={checked ? "checked" : "unchecked"}
      data-disabled={disabled || undefined}
      data-error={error || undefined}
    >
      <span className="sc-switch__hit">
        <input
          id={inputId}
          name={name}
          type="checkbox"
          role="switch"
          aria-checked={checked}
          className="sc-switch__input"
          checked={checked}
          disabled={disabled}
          aria-invalid={error || undefined}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="sc-switch__track">
          <motion.span
            className="sc-switch__thumb"
            initial={false}
            animate={{ x: checked ? TRAVEL : 0, scaleX: [1, scale(1.18), 1] }}
            transition={t("move")}
          />
        </span>
      </span>
      <span className="sc-switch__label sc-t-body-s">{label}</span>
    </label>
  );
}
