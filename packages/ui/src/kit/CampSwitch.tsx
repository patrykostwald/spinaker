"use client";

/**
 * CampSwitch — JEDEN przełącznik strony (Rządzący / Opozycja) dla całego serwisu (Aspekt 3 / S4).
 * Zastępuje trzy różne style (karty `sc-reader-switch`, zakładki `sc-scan-s-tabs` na stronie głównej).
 * `mode="pressed"` (domyślnie): grupa przycisków z `aria-pressed`.
 * `mode="tabs"`: zakładki (`role="tab"`, strzałki/Home/End) sterujące panelem `panelId`.
 * Na telefonie to jedyny wybór strony — cele min. 44 px, widoczny fokus.
 */

import { CAMPS, CAMP_LABELS, type Camp } from "../lib/clinic";

export type CampSwitchProps = {
  value: Camp | null;
  onChange: (camp: Camp) => void;
  label: string;
  mode?: "pressed" | "tabs";
  /** Id panelu sterowanego w trybie `tabs` (aria-controls). */
  panelId?: string;
  /** Prefiks id zakładek w trybie `tabs`. */
  idPrefix?: string;
  className?: string;
};

export function CampSwitch({ value, onChange, label, mode = "pressed", panelId, idPrefix = "camp-tab", className }: CampSwitchProps) {
  const cls = className ? `sc-camp-switch ${className}` : "sc-camp-switch";
  if (mode === "tabs") {
    return (
      <div className={cls} role="tablist" aria-label={label}>
        {CAMPS.map((camp, index) => (
          <button key={camp} type="button" role="tab" id={`${idPrefix}-${camp}`} aria-selected={value === camp} aria-controls={panelId} tabIndex={value === camp ? 0 : -1}
            onClick={() => onChange(camp)}
            onKeyDown={event => {
              if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
              event.preventDefault();
              const next = event.key === "Home" ? CAMPS[0] : event.key === "End" ? CAMPS[CAMPS.length - 1] : CAMPS[(index + 1) % CAMPS.length];
              onChange(next);
              document.getElementById(`${idPrefix}-${next}`)?.focus();
            }}>{CAMP_LABELS[camp]}</button>
        ))}
      </div>
    );
  }
  return (
    <div className={cls} role="group" aria-label={label}>
      {CAMPS.map(camp => <button key={camp} type="button" aria-pressed={value === camp} onClick={() => onChange(camp)}>{CAMP_LABELS[camp]}</button>)}
    </div>
  );
}
