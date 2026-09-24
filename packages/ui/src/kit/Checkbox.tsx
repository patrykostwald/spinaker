"use client";

import { useEffect, useId, useRef, useState } from "react";
import { motion } from "framer-motion";
import { CheckIcon } from "./icons/CheckIcon";
import { MinusIcon } from "./icons/MinusIcon";
import { useMotionTokens } from "./motion/useMotionTokens";

export interface CheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Trzeci, wizualny stan — nie wpływa na wartość `checked` przekazywaną dalej. */
  indeterminate?: boolean;
  disabled?: boolean;
  error?: boolean;
  label: string;
  id?: string;
  name?: string;
  className?: string;
}

/**
 * Flażek (docs/UI_KIT_PLAN.md → «Селекторы, флажки и переключатели»).
 * Prawdziwy `<input type="checkbox">` pod spodem (dostępność), strefa dotyku 44px
 * (`.sc-checkbox__hit`, patrz kit.css), jednorazowy blik `.sc-sheen` tylko przy
 * włączeniu, ptaszek rysuje się kreską (CheckIcon), pudełko „strzela” scale 1→.92→1,
 * nieokreślone — kreska rośnie od środka (MinusIcon), błąd — jednorazowe potrząśnięcie 2px.
 */
export function Checkbox({
  checked,
  onChange,
  indeterminate = false,
  disabled = false,
  error = false,
  label,
  id,
  name,
  className,
}: CheckboxProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const inputRef = useRef<HTMLInputElement>(null);
  const { t, scale } = useMotionTokens();

  const prevChecked = useRef(checked);
  const [sheen, setSheen] = useState(false);
  const [punch, setPunch] = useState(0);
  useEffect(() => {
    if (checked && !prevChecked.current) {
      setSheen(true);
      setPunch((p) => p + 1);
      const timer = window.setTimeout(() => setSheen(false), 420);
      prevChecked.current = checked;
      return () => window.clearTimeout(timer);
    }
    prevChecked.current = checked;
    return undefined;
  }, [checked]);

  const prevError = useRef(error);
  const [shake, setShake] = useState(0);
  useEffect(() => {
    if (error && !prevError.current) setShake((s) => s + 1);
    prevError.current = error;
  }, [error]);

  useEffect(() => {
    if (inputRef.current) inputRef.current.indeterminate = indeterminate && !checked;
  }, [indeterminate, checked]);

  return (
    <label
      htmlFor={inputId}
      className={["sc-checkbox", className].filter(Boolean).join(" ")}
      data-state={checked ? "checked" : indeterminate ? "indeterminate" : "unchecked"}
      data-disabled={disabled || undefined}
      data-error={error || undefined}
    >
      <span className="sc-checkbox__hit">
        <input
          ref={inputRef}
          id={inputId}
          name={name}
          type="checkbox"
          className="sc-checkbox__input"
          checked={checked}
          disabled={disabled}
          aria-invalid={error || undefined}
          onChange={(e) => onChange(e.target.checked)}
        />
        <motion.span
          key={`shake-${shake}`}
          className="sc-checkbox__shake"
          initial={false}
          animate={shake ? { x: [0, -2, 2, -2, 0] } : { x: 0 }}
          transition={t("ui", { duration: 0.28, bounce: 0 })}
        >
          <motion.span
            key={`punch-${punch}`}
            className="sc-checkbox__box sc-sheen"
            data-sheen={sheen ? "run" : undefined}
            initial={false}
            animate={{ scale: punch ? [scale(1), scale(0.92), scale(1)] : scale(1) }}
            transition={t("press")}
          >
            {checked ? (
              <CheckIcon size={16} className="sc-checkbox__mark" />
            ) : indeterminate ? (
              <MinusIcon size={16} className="sc-checkbox__mark" />
            ) : null}
          </motion.span>
        </motion.span>
      </span>
      <span className="sc-checkbox__label sc-t-body-s">{label}</span>
    </label>
  );
}
