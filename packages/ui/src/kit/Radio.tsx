"use client";

import { useId } from "react";
import { LayoutGroup, motion } from "framer-motion";
import { useMotionTokens } from "./motion/useMotionTokens";

export interface RadioProps {
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  error?: boolean;
  label: string;
  id?: string;
  name?: string;
  value?: string;
  /** Nadawany przez RadioGroup — włącza wspólny `layoutId` kropki w obrębie grupy. */
  groupId?: string;
  className?: string;
}

/**
 * Radio (docs/UI_KIT_PLAN.md → «Селекторы, флажки и переключатели»).
 * W grupie kropka „przejeżdża” między opcjami wspólnym `layoutId` (a nie gaśnie/zapala się);
 * poza grupą — zwykłe pojawienie scale 0→1 z pружиny (ta sama `Radio`, `groupId` bez wartości).
 */
export function Radio({ checked, onChange, disabled = false, error = false, label, id, name, value, groupId, className }: RadioProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const { t } = useMotionTokens();

  return (
    <label
      htmlFor={inputId}
      className={["sc-radio", className].filter(Boolean).join(" ")}
      data-state={checked ? "checked" : "unchecked"}
      data-disabled={disabled || undefined}
      data-error={error || undefined}
    >
      <span className="sc-radio__hit">
        <input
          id={inputId}
          type="radio"
          name={name}
          value={value}
          checked={checked}
          disabled={disabled}
          className="sc-radio__input"
          aria-invalid={error || undefined}
          onChange={() => onChange()}
        />
        <span className="sc-radio__ring">
          {checked && (
            <motion.span
              layoutId={groupId ? `sc-radio-dot-${groupId}` : undefined}
              className="sc-radio__dot"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={t("move")}
            />
          )}
        </span>
      </span>
      <span className="sc-radio__label sc-t-body-s">{label}</span>
    </label>
  );
}

export interface RadioOption {
  value: string;
  label: string;
}

export interface RadioGroupProps {
  name: string;
  value: string;
  onChange: (value: string) => void;
  options: RadioOption[];
  disabled?: boolean;
  error?: boolean;
  legend: string;
  className?: string;
}

/** Grupa radio z jedną, wspólną, „przejeżdżającą” kropką (`LayoutGroup` scala layoutId tylko w obrębie grupy). */
export function RadioGroup({ name, value, onChange, options, disabled, error, legend, className }: RadioGroupProps) {
  return (
    <div className={["sc-radio-group", className].filter(Boolean).join(" ")} role="radiogroup" aria-label={legend}>
      <LayoutGroup id={`sc-radio-group-${name}`}>
        {options.map((opt) => (
          <Radio
            key={opt.value}
            groupId={name}
            name={name}
            value={opt.value}
            checked={value === opt.value}
            onChange={() => onChange(opt.value)}
            label={opt.label}
            disabled={disabled}
            error={error}
          />
        ))}
      </LayoutGroup>
    </div>
  );
}
