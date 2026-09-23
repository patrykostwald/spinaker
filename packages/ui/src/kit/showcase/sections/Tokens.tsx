"use client";

import { useEffect, useRef, useState } from "react";
import { COLOR_TOKENS, RADIUS_TOKENS, SPACING_TOKENS } from "../../tokens";

export const meta = {
  id: "tokeny",
  title: "Tokeny",
  lead: "Wartości czytane na żywo z getComputedStyle — sekcja nie może rozjechać się z kit.css.",
};

function useComputedTokens(names: readonly string[], prefix = "--sc-") {
  const ref = useRef<HTMLDivElement>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  useEffect(() => {
    const read = () => {
      const node = ref.current;
      if (!node) return;
      const style = getComputedStyle(node);
      const next: Record<string, string> = {};
      for (const name of names) next[name] = style.getPropertyValue(`${prefix}${name}`).trim();
      setValues(next);
    };
    read();
    const observer = new MutationObserver(read);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, [names, prefix]);
  return { ref, values };
}

export function Section() {
  const colors = useComputedTokens(COLOR_TOKENS);
  return (
    <div ref={colors.ref}>
      <h3 className="sc-t-title-m sc-section__sub">Kolor</h3>
      <div className="sc-grid">
        {COLOR_TOKENS.map((name) => (
          <div key={name} className="sc-swatch">
            <div className="sc-swatch__chip" style={{ background: `var(--sc-${name})` }} />
            <span className="sc-swatch__name">--sc-{name}</span>
            <code>{colors.values[name] || "…"}</code>
          </div>
        ))}
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Promienie</h3>
      <div className="sc-ladder">
        {RADIUS_TOKENS.map((r) => (
          <div key={r} className="sc-ladder__box" style={{ borderRadius: `var(--sc-r-${r})` }}>{r}</div>
        ))}
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Odstępy</h3>
      <div className="sc-ruler">
        {SPACING_TOKENS.map((s) => (
          <div key={s}>
            <div className="sc-ruler__bar" style={{ width: `var(--sc-s-${s})` }} />
            <div className="sc-ruler__label">s-{s}</div>
          </div>
        ))}
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Wysokość</h3>
      <div className="sc-elev">
        {(["1", "2", "3", "menu"] as const).map((e) => (
          <div key={e} className="sc-elev__card" style={{ boxShadow: `var(--sc-e-${e}), var(--sc-ring)` }}>e-{e} + ring</div>
        ))}
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Próba pierścienia fokusu i poświaty</h3>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-4)" }}>
        Tab na kartę: pierścień musi być <strong>niebieski</strong>, nie bursztynowy — to dowód, że kit.css wygrywa z globalnym :focus-visible. Najedź: bursztynowa poświata za kartą.
      </p>
      <div className="sc-probe">
        <button type="button" className="sc-probe__card sc-hoverable" style={{ borderRadius: "var(--sc-r-xl)" }}>
          <span className="sc-t-title-s" style={{ display: "block" }}>Karta próbna</span>
          <span className="sc-probe__note">Tło z tokenu, cień z tokenu, pierścień z tokenu.</span>
        </button>
        <button type="button" className="sc-probe__card sc-hoverable" data-lit="true" style={{ borderRadius: "var(--sc-r-xl)" }}>
          <span className="sc-t-title-s" style={{ display: "block" }}>Poświata na stałe</span>
          <span className="sc-probe__note">data-lit=&quot;true&quot; — tak wygląda stopień A.</span>
        </button>
      </div>
    </div>
  );
}
