"use client";

import type { CSSProperties } from "react";
import { clampSpin, spinZone } from "../lib/spinScale";

export type SpinMeterModel = { label: string; value: number | null | undefined };

/** Podpisy ocen modeli w dwóch piętrach: gdy dolne piętro jest zajęte w promieniu `gap` punktów skali, podpis idzie wyżej. */
function placeLabels(marks: Array<{ label: string; value: number }>, gap = 10) {
  let low = -Infinity, high = -Infinity;
  return [...marks].sort((a, b) => a.value - b.value).map(model => {
    if (model.value - low >= gap || model.value - high < gap) { low = model.value; return { model, lift: false }; }
    high = model.value; return { model, lift: true };
  });
}

/**
 * Miara siły spinu v3 (jedna w całym serwisie).
 * - `bare` (listy, strona główna): sama liczba w kolorze strefy, bez etykiety i bez paska.
 * - domyślnie (szczegół diagnozy): etykieta, liczba i jedna cienka linia wypełniona tonem siły od lewej do kreski znacznika;
 *   opcjonalnie krótkie neutralne kreski ocen modeli z inicjałem na tej samej linii.
 * Kolor nigdy nie jest jedynym nośnikiem: liczba jest zawsze widoczna i czytana przez czytnik ekranu.
 */
export function SpinMeter({ value, bare = false, label = "Siła spinu", size = "sm", models, legend, className }: {
  value: number; bare?: boolean; label?: string; size?: "sm" | "md" | "lg"; models?: SpinMeterModel[]; legend?: string; className?: string;
}) {
  const v = clampSpin(value);
  const zone = spinZone(v);
  const marks = (models ?? []).filter((model): model is { label: string; value: number } => typeof model.value === "number");
  return <div className={["sc-v3-meter", className].filter(Boolean).join(" ")} data-zone={zone} data-size={size}
    data-bare={bare || undefined} data-models={marks.length ? "" : undefined}
    role="img" aria-label={`${label}: ${v} na 100`}>
    {!bare && <p className="sc-v3-meter__lbl" aria-hidden="true">{label}</p>}
    <p className="sc-v3-meter__num" aria-hidden="true"><b>{v}</b><small>/100</small></p>
    {!bare && <div className="sc-v3-meter__line" aria-hidden="true" style={{ "--v": v / 100 } as CSSProperties}>
      <span className="sc-v3-meter__fill" />
      {placeLabels(marks).map(({ model, lift }) => <span key={model.label} className="sc-v3-meter__mt" style={{ left: `${clampSpin(model.value)}%` }} title={`${model.label}: ${clampSpin(model.value)}`}><i style={lift ? { bottom: 26 } : undefined}>{model.label}</i></span>)}
      <span className="sc-v3-meter__tick" style={{ left: `${v}%` }} />
    </div>}
    {!bare && legend && <p className="sc-v3-meter__leg">{legend}</p>}
  </div>;
}
