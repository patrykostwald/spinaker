"use client";

import { useEffect, useRef, useState } from "react";
import { TYPE_TOKENS } from "../../tokens";
import { POLISH_LONG_WORDS, POLISH_SPECIMEN } from "../fixtures";

export const meta = {
  id: "typografia",
  title: "Typografia",
  lead: "Montserrat, latin-ext. Obie wersje kolorystyczne obok siebie — kompensacji optycznej wagi nie da się ocenić z pamięci.",
};

const SAMPLES: Record<(typeof TYPE_TOKENS)[number], string> = {
  display: "Zażółć gęślą jaźń",
  "title-l": "Tytuł dużej karty: sprawiedliwości i województwo",
  "title-m": "Tytuł średniej karty z długim słowem Rzeczpospolita",
  "title-s": "Tytuł kompaktowej karty w dwóch wierszach",
  "title-xs": "Tytuł miniatury",
  body: POLISH_SPECIMEN,
  "body-s": POLISH_SPECIMEN,
  meta: "Dziennik Przykładowy · 23.09.2026 14:05 · 1 234 materiały",
  caption: "Artykuł · Głosowanie · Dokument urzędowy",
};

function Specimen({ theme }: { theme: "dark" | "light" }) {
  const ref = useRef<HTMLDivElement>(null);
  const [info, setInfo] = useState<Record<string, string>>({});
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const next: Record<string, string> = {};
    node.querySelectorAll<HTMLElement>("[data-token]").forEach((el) => {
      const s = getComputedStyle(el);
      next[el.dataset.token!] = `${s.fontSize} / ${s.lineHeight} · ${s.letterSpacing} · ${s.fontWeight} · ${s.fontFamily.split(",")[0].replace(/["']/g, "")}`;
    });
    setInfo(next);
  }, []);
  return (
    <div ref={ref} className="sc-specimen__theme sc-root" data-sc-theme={theme}>
      <p className="sc-t-caption">{theme === "dark" ? "Noc" : "Dzień"} · ąćęłńóśźż ĄĆĘŁŃÓŚŹŻ</p>
      {TYPE_TOKENS.map((t) => (
        <div key={t} className="sc-specimen__row">
          <span className={`sc-t-${t}`} data-token={t}>{SAMPLES[t]}</span>
          <code>{t} · {info[t] ?? "…"}</code>
        </div>
      ))}
    </div>
  );
}

export function Section() {
  return (
    <div>
      <div className="sc-specimen">
        <Specimen theme="dark" />
        <Specimen theme="light" />
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Długie polskie słowa w wąskiej karcie (184px)</h3>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-4)" }}>
        Montserrat jest szerszy niż IBM Plex Sans. Jeśli przenoszenie jest złe, poprawiamy stopień nagłówka karty, nie szerokość karty.
      </p>
      <div className="sc-narrow">
        <div className="sc-t-title-xs">{POLISH_LONG_WORDS}</div>
        <div className="sc-t-meta sc-text-2" style={{ marginTop: 8 }}>Biuletyn Makiety Regionalnej i Przykładowej · 01.09.26</div>
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Cyfry o stałej szerokości</h3>
      <div className="sc-t-meta" style={{ display: "grid", gap: 2, maxWidth: 260 }}>
        <span>11:11 · 1 111 materiałów</span>
        <span>08:08 · 8 888 materiałów</span>
        <span>00:00 · 0 000 materiałów</span>
      </div>
    </div>
  );
}
