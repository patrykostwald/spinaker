"use client";

import type { CSSProperties } from "react";

/**
 * „Dr Spin wyjaśnia” - ciąg przyczynowo-skutkowy przekazu (prototyp spin-v3): Fakt → Interpretacja → Spin → Wniosek.
 *
 * WYŁĄCZONE NA PRODUKCJI: API przekazu dnia (`/api/clinic/` → messages) nie zawiera kroków łańcucha ani źródeł faktów,
 * więc komponent renderuje się wyłącznie, gdy (1) flaga `NEXT_PUBLIC_CAUSAL_CHAIN=true` i (2) dane mają co najmniej 3 kroki,
 * a każdy krok rodzaju „fakt” ma źródło. Dane demonstracyjne istnieją tylko w witrynie UI kit (`/ui-kit`, oznaczone „Demo, fikcja”).
 * Wymagania danych (pola, bramki, źródła): zbudujmi/gust/spin/RAPORT-v3.md, sekcja „Wymagania danych dla prawdziwego przekazu dnia”.
 */
export type CausalStepKind = "fakt" | "interpretacja" | "spin" | "wniosek";
export type CausalStep = {
  kind: CausalStepKind;
  text: string;
  /** fakt: nazwa i data źródła (wymagane), spin: technika */
  source?: { name: string; url?: string; date?: string };
  technique?: string;
};

const KIND_LABEL: Record<CausalStepKind, string> = { fakt: "Fakt", interpretacja: "Interpretacja", spin: "Spin", wniosek: "Wniosek" };

export const CAUSAL_CHAIN_ENABLED = process.env.NEXT_PUBLIC_CAUSAL_CHAIN === "true";

/** Łańcuch nadaje się do pokazania: min. 3 kroki, każdy fakt ze źródłem (brak źródła = krok niedozwolony). */
export function isCausalChainValid(steps: CausalStep[] | null | undefined): steps is CausalStep[] {
  return Array.isArray(steps) && steps.length >= 3 && steps.every(step => step.text.trim() && (step.kind !== "fakt" || Boolean(step.source?.name)));
}

function stepMeta(step: CausalStep): string | null {
  if (step.kind === "fakt" && step.source) return `Źródło: ${step.source.name}${step.source.date ? `, ${step.source.date}` : ""}`;
  if (step.kind === "interpretacja") return "Interpretacja Dr Spina, nie fakt";
  if (step.kind === "spin" && step.technique) return `Technika: ${step.technique}`;
  if (step.kind === "wniosek") return "Co z tego wynika";
  return null;
}

export function CausalChain({ steps, force = false, draw }: { steps: CausalStep[] | null | undefined; force?: boolean; draw?: "off" | "on" }) {
  if (!(CAUSAL_CHAIN_ENABLED || force) || !isCausalChainValid(steps)) return null;
  return <ol className="sc-v3-steps" data-draw={draw} aria-label="Ciąg przyczyn: od faktu do wniosku">
    {steps.map((step, index) => {
      const meta = stepMeta(step);
      return <li key={index} data-k={step.kind} style={{ "--d": index } as CSSProperties}>
        <span className="sc-v3-step__n" aria-hidden="true">{index + 1}</span>
        <div className="sc-v3-step__top"><span className="sc-v3-step__k">{KIND_LABEL[step.kind]}</span>{meta && <span className="sc-v3-step__m">{meta}</span>}</div>
        <p className="sc-v3-step__p">{step.text}</p>
      </li>;
    })}
  </ol>;
}
