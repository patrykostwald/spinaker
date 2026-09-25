"use client";

/**
 * Jaśniejsze okienko z treścią do skopiowania (jak blok kodu w odpowiedzi czatu AI): etykieta,
 * przycisk „Kopiuj” i treść. `mode="diagram"` — tekst o stałej szerokości, bez łamania linii
 * (schematy rysowane znakami); `mode="text"` — zwykły akapit do wklejenia (np. opis projektu).
 */

import { useRef, useState, type RefObject } from "react";

export function CopyBlock({ label, text, mode = "diagram", caption }: { label: string; text: string; mode?: "diagram" | "text"; caption?: string }) {
  const [state, setState] = useState<"idle" | "copied" | "manual">("idle");
  const contentRef = useRef<HTMLPreElement | HTMLParagraphElement | null>(null);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      // Brak dostępu do schowka (np. HTTP bez zgody przeglądarki): zaznaczamy treść do ręcznego skopiowania.
      const node = contentRef.current;
      if (node) {
        const range = document.createRange();
        range.selectNodeContents(node);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      }
      setState("manual");
    }
    window.setTimeout(() => setState("idle"), 2200);
  }

  return (
    <figure className="sc-onas-copy" data-mode={mode}>
      <div className="sc-onas-copy__bar">
        <span className="sc-onas-copy__label">{label}</span>
        <button type="button" className="sc-onas-copy__button" onClick={copy} aria-live="polite">
          {state === "copied" ? "Skopiowano" : state === "manual" ? "Zaznaczono — Ctrl+C" : "Kopiuj"}
        </button>
      </div>
      {mode === "diagram" ? (
        <pre ref={contentRef as RefObject<HTMLPreElement>} className="sc-onas-copy__pre" tabIndex={0} aria-label={caption ?? label}>
          {text}
        </pre>
      ) : (
        <p ref={contentRef as RefObject<HTMLParagraphElement>} className="sc-onas-copy__text">
          {text}
        </p>
      )}
      {caption ? <figcaption className="sc-onas-copy__caption">{caption}</figcaption> : null}
    </figure>
  );
}
