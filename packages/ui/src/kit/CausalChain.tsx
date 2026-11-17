"use client";

import type { CSSProperties } from "react";

/**
 * „Dr Spin wyjaśnia” - ciąg przyczynowo-skutkowy przekazu (prototyp spin-v3): Fakt → Interpretacja → Spin → Wniosek.
 *
 * Dane: pole `causal_chain` przekazu dnia (kontrakt `gust/spin/port/API-v3.md`, seria 2). Backend wysyła je tylko dla łańcuchów
 * zatwierdzonych przez człowieka i przy włączonej fladze `CAUSAL_CHAIN_ENABLED`; w ciszy wyborczej zawsze `null`.
 * Front pokazuje łańcuch wyłącznie, gdy (1) flaga `NEXT_PUBLIC_CAUSAL_CHAIN=true` (domyślnie wyłączona), (2) łańcuch ma
 * `approved_at` i (3) przechodzi walidację: 3-5 kroków, każdy fakt ze źródłem. Dane demonstracyjne tylko w `/ui-kit` („Demo, fikcja”).
 */
export type CausalStepKind = "fakt" | "interpretacja" | "spin" | "wniosek";
export type CausalStep = {
  kind: CausalStepKind;
  text: string;
  /** fakt: nazwa i data źródła (wymagane), spin: technika */
  source?: { name: string; url?: string; date?: string };
  technique?: string;
  /** fakt bez źródła w materiałach zdegradowany przez backend do interpretacji */
  degraded?: boolean;
};
/** Łańcuch z API (MessageCausalChain w lib/clinic.ts) - tylko pola potrzebne do decyzji o pokazaniu. */
export type CausalChainData = { approved_at: string | null; steps: CausalStep[]; notice?: string; model?: string } | null | undefined;

const KIND_LABEL: Record<CausalStepKind, string> = { fakt: "Fakt", interpretacja: "Interpretacja", spin: "Spin", wniosek: "Wniosek" };
const KINDS = new Set<string>(Object.keys(KIND_LABEL));

export const CAUSAL_CHAIN_ENABLED = process.env.NEXT_PUBLIC_CAUSAL_CHAIN === "true";

/** Łańcuch nadaje się do pokazania: 3-5 kroków znanego rodzaju, niepusty tekst, każdy fakt ze źródłem (brak źródła = krok niedozwolony). */
export function isCausalChainValid(steps: CausalStep[] | null | undefined): steps is CausalStep[] {
  return Array.isArray(steps) && steps.length >= 3 && steps.length <= 5
    && steps.every(step => KINDS.has(step?.kind) && typeof step.text === "string" && step.text.trim() !== "" && (step.kind !== "fakt" || Boolean(step.source?.name?.trim())));
}

/** Kroki zatwierdzonego łańcucha z API albo null (brak klucza, null, brak zatwierdzenia, nieprawidłowe kroki). */
export function approvedChainSteps(chain: CausalChainData): CausalStep[] | null {
  if (!chain || !chain.approved_at) return null;
  return isCausalChainValid(chain.steps) ? chain.steps : null;
}

function stepMeta(step: CausalStep): string | null {
  if (step.kind === "fakt" && step.source) return `Źródło: ${step.source.name}${step.source.date ? `, ${step.source.date}` : ""}`;
  if (step.kind === "interpretacja") return step.degraded ? "Interpretacja Dr Spina - brak źródła w materiałach" : "Interpretacja Dr Spina, nie fakt";
  if (step.kind === "spin" && step.technique) return `Technika: ${step.technique}`;
  if (step.kind === "wniosek") return "Co z tego wynika";
  return null;
}

/** Bezpieczny odnośnik źródła: tylko http(s). */
const safeUrl = (url?: string) => (url && /^https?:\/\//i.test(url) ? url : null);

export function CausalChain({ steps, force = false, draw }: { steps: CausalStep[] | null | undefined; force?: boolean; draw?: "off" | "on" }) {
  if (!(CAUSAL_CHAIN_ENABLED || force) || !isCausalChainValid(steps)) return null;
  return <ol className="sc-v3-steps" data-draw={draw} aria-label="Ciąg przyczyn: od faktu do wniosku">
    {steps.map((step, index) => {
      const meta = stepMeta(step);
      const href = step.kind === "fakt" ? safeUrl(step.source?.url) : null;
      return <li key={index} data-k={step.kind} style={{ "--d": index } as CSSProperties}>
        <span className="sc-v3-step__n" aria-hidden="true">{index + 1}</span>
        <div className="sc-v3-step__top"><span className="sc-v3-step__k">{KIND_LABEL[step.kind]}</span>
          {meta && (href
            ? <a className="sc-v3-step__m sc-v3-step__src" href={href} target="_blank" rel="noopener noreferrer">{meta}<span className="sc-v3-sr"> (otwiera źródło w nowym oknie)</span></a>
            : <span className="sc-v3-step__m">{meta}</span>)}
        </div>
        <p className="sc-v3-step__p">{step.text}</p>
      </li>;
    })}
  </ol>;
}
