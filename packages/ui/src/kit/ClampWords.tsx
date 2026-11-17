"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";

/**
 * Tekst w stałym budżecie linii, skracany po całym słowie (nie w pół słowa jak -webkit-line-clamp), z pełnym tekstem
 * w `title` i dla czytnika ekranu. Element ma w CSS stałą wysokość (min-height = max-height = linie), więc długość treści
 * nigdy nie zmienia wysokości boksu (reguła stałych stref, karta Przekaz dnia 14.10.2026). Pomiar na ukrytej kopii
 * elementu o tej samej szerokości i klasach; przeliczany przy zmianie szerokości i po załadowaniu krojów.
 */
export function ClampWords({ text, lines, as = "p", className, style }: { text: string; lines: number; as?: "p" | "span" | "div"; className?: string; style?: CSSProperties }) {
  const box = useRef<HTMLElement | null>(null);
  const [cut, setCut] = useState<string | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const fit = () => {
      const parent = el.parentElement;
      if (!parent) return;
      const lh = parseFloat(getComputedStyle(el).lineHeight);
      if (!(lh > 0)) return;
      const budget = lh * lines + 1;
      const m = document.createElement(el.tagName) as HTMLElement;
      m.className = el.className;
      m.setAttribute("aria-hidden", "true");
      m.style.cssText = `position:absolute;visibility:hidden;pointer-events:none;left:0;top:0;width:${el.clientWidth}px;height:auto;min-height:0;max-height:none;margin:0;padding:0;overflow:visible;display:block;white-space:normal;-webkit-line-clamp:unset;`;
      parent.insertBefore(m, el);
      const over = (s: string) => { m.textContent = s; return m.scrollHeight > budget; };
      let out: string | null = null;
      if (over(text)) {
        const words = text.split(" ");
        const cand = (k: number) => words.slice(0, k).join(" ").replace(/[\s,;:.\-]+$/, "") + "…";
        let lo = 0, hi = words.length - 1;
        while (lo < hi) { const mid = Math.ceil((lo + hi) / 2); if (over(cand(mid))) hi = mid - 1; else lo = mid; }
        if (lo >= 1) out = cand(lo);
        else { let s = words[0] ?? ""; while (s.length > 1 && over(s + "…")) s = s.slice(0, -1); out = s + "…"; }
      }
      m.remove();
      setCut(prev => (prev === out ? prev : out));
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    const fonts = document.fonts;
    fonts?.addEventListener("loadingdone", fit);
    return () => { ro.disconnect(); fonts?.removeEventListener("loadingdone", fit); };
  }, [text, lines]);
  const Tag = as;
  return <Tag ref={box as never} className={className} style={style} title={cut ? text : undefined} data-lines={lines} data-cut={cut ? "" : undefined}>
    {cut ? <><span aria-hidden="true">{cut}</span><span className="sc-v3-sr">{text}</span></> : text}
  </Tag>;
}
