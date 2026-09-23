"use client";

/**
 * ThemeToggle (docs/UI_KIT_PLAN.md → «Компоненты» ThemeToggle, «Оживление каждого
 * элемента → Смена темы»). Trzy stany: Noc / Dzień / Auto, zbudowane na `Segmented` (R1) —
 * stan jest czytelny bez koloru (etykieta tekstowa + przejeżdżający wskaźnik).
 *
 * Zapisuje WYŁĄCZNIE `document.documentElement.dataset.theme` i `style.colorScheme`.
 * Nigdy localStorage, nigdy PATCH /api/account/profile/ — to mechanizm żywego
 * `ThemeSwitcher.tsx`, którego na tym etapie nie ruszamy. `auto` jest uczciwe: śledzi
 * `matchMedia('(prefers-color-scheme: dark)')` i nasłuchuje jej zmian na żywo.
 */

import { useEffect, useState } from "react";
import { Segmented } from "./Segmented";

export type ThemeToggleMode = "night" | "day" | "auto";

export type ThemeToggleProps = {
  className?: string;
};

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function resolveTheme(mode: ThemeToggleMode): "dark" | "light" {
  if (mode === "auto") return systemPrefersDark() ? "dark" : "light";
  return mode === "night" ? "dark" : "light";
}

/**
 * Klasa `sc-theme-transition` (kit.css, blok R0) daje ~300ms płynne przejście koloru na
 * `<html>`; ta sama reguła CSS już wyłącza je przy `prefers-reduced-motion` i
 * `prefers-contrast: more`, więc tu nie trzeba tego osobno sprawdzać.
 */
function applyTheme(theme: "dark" | "light") {
  const root = document.documentElement;
  root.classList.add("sc-theme-transition");
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  window.setTimeout(() => root.classList.remove("sc-theme-transition"), 300);
}

const OPTIONS = [
  { value: "night", label: "Noc" },
  { value: "day", label: "Dzień" },
  { value: "auto", label: "Auto" },
];

export function ThemeToggle({ className }: ThemeToggleProps) {
  const [mode, setMode] = useState<ThemeToggleMode>("night");

  // Synchronizacja startowego zaznaczenia z tym, co strona już pokazuje — bez zapisu do DOM.
  useEffect(() => {
    setMode(document.documentElement.dataset.theme === "light" ? "day" : "night");
  }, []);

  function choose(next: string) {
    const nextMode = next as ThemeToggleMode;
    setMode(nextMode);
    applyTheme(resolveTheme(nextMode));
  }

  // Nasłuch preferencji systemowej — tylko póki tryb auto jest aktywny.
  useEffect(() => {
    if (mode !== "auto" || typeof window === "undefined") return;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme(resolveTheme("auto"));
    mediaQuery.addEventListener("change", onChange);
    return () => mediaQuery.removeEventListener("change", onChange);
  }, [mode]);

  return (
    <Segmented
      name="sc-theme-toggle"
      label="Motyw"
      value={mode}
      onChange={choose}
      options={OPTIONS}
      className={className}
    />
  );
}
