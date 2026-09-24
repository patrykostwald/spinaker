"use client";

import { useId, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { SearchIcon } from "./icons/SearchIcon";
import { CloseIcon } from "./icons/CloseIcon";
import { useMotionTokens } from "./motion/useMotionTokens";

export interface SearchFieldProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  disabled?: boolean;
  error?: boolean;
  /** Liczba wyników — jeśli podana, przewija się liczbą obok pola (MorphValue robi to u konsumenta). */
  resultsCount?: number;
  id?: string;
  className?: string;
  maxLength?: number;
  inputType?: "search" | "url";
  required?: boolean;
  name?: string;
}

/**
 * Pole wyszukiwania (docs/UI_KIT_PLAN.md → «Селекторы, флажки и переключатели»).
 * Pierścień fokusu i krawędź przechodzą (`fade`), ikona przebarwia się w akcent przy fokusie,
 * przycisk czyszczenia pojawia się scale .8→1. Napisane jako `input.sc-input` (specyficzność
 * 0,2,1 pod `.sc-root`) — jedyna prawdziwa pułapka kaskady dla pól tekstowych.
 */
export function SearchField({
  value,
  onChange,
  placeholder = "Szukaj…",
  label = "Szukaj",
  disabled = false,
  error = false,
  resultsCount,
  id,
  className,
  maxLength,
  inputType = "search",
  required = false,
  name,
}: SearchFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const [focused, setFocused] = useState(false);
  const { t, scale } = useMotionTokens();

  return (
    <div
      className={["sc-search", className].filter(Boolean).join(" ")}
      data-focused={focused || undefined}
      data-disabled={disabled || undefined}
      data-error={error || undefined}
    >
      <label htmlFor={inputId} className="sc-visually-hidden">
        {label}
      </label>
      <span className="sc-search__icon">
        <SearchIcon size={20} />
      </span>
      <input
        id={inputId}
        type={inputType}
        className="sc-input sc-search__input"
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        aria-invalid={error || undefined}
        maxLength={maxLength}
        required={required}
        name={name}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(e) => onChange(e.target.value)}
      />
      <AnimatePresence initial={false}>
        {value.length > 0 && (
          <motion.button
            key="clear"
            type="button"
            className="sc-search__clear"
            aria-label="Wyczyść wyszukiwanie"
            initial={{ scale: scale(0.8), opacity: 0 }}
            animate={{ scale: scale(1), opacity: 1 }}
            exit={{ scale: scale(0.8), opacity: 0 }}
            transition={t("ui")}
            onClick={() => onChange("")}
          >
            <CloseIcon size={16} />
          </motion.button>
        )}
      </AnimatePresence>
      {typeof resultsCount === "number" && (
        <span className="sc-search__count sc-t-meta sc-text-2">{resultsCount}</span>
      )}
    </div>
  );
}
