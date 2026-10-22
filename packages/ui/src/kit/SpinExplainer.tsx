"use client";

import { useId, useState } from "react";
import { GlitchWord } from "./GlitchWord";

/**
 * Czym jest spin (właściciel 3.10.2026): wielu czytelników nie wie, co to spin ani spin doktor. Trzy równe boksy:
 * spin, spin doktor, spin.clinic. Ta sama treść na stronie głównej i w „O nas”; teksty przychodzą z zewnątrz (tłumaczenia).
 */
export type SpinExplainerText = { kicker: string; title: string; items: { name: string; text: string }[] };

export const SPIN_EXPLAINER_PL: SpinExplainerText = {
  kicker: "Czym jest spin",
  title: "Politycy mają spin doktorów. Ty masz spin.clinic.",
  items: [
    { name: "Spin", text: "Fakty podane tak, by działały na czyjąś korzyść: dobór słów, pominięcia, emocje. Nie zawsze kłamstwo, zawsze kierunek." },
    { name: "Spin doktor", text: "Doradca, który układa przekaz polityka: co powiedzieć, jak to ująć i co przemilczeć. Są po obu stronach sceny." },
    { name: "spin.clinic", text: "Strażnik po Twojej stronie: Konsylium AI rozkłada przekaz na techniki i sprawdza twierdzenia. Jedna miara dla wszystkich." },
  ],
};

const hard = (text: string) => text.replace(/(^|\s)([aiouwzAIOUWZ])\s+/g, '$1$2 ');
function split(text: string): [string, string] {
  const at = text.slice(0, -1).lastIndexOf('. ');
  return at > 0 ? [hard(text.slice(0, at + 1)), hard(text.slice(at + 2))] : [hard(text), ''];
}

export function SpinExplainer({ text = SPIN_EXPLAINER_PL, headingLevel = 2, id, collapsible = false }: { text?: SpinExplainerText; headingLevel?: 2 | 3; id?: string; collapsible?: boolean }) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const uid = useId();
  const [open, setOpen] = useState(!collapsible);
  const grid = <ul className="sc-spin-explainer__grid" id={`${uid}-grid`} hidden={!open}>{text.items.map((item, index) => (
    <li key={item.name} data-step={index + 1}><strong>{item.name}</strong>
      {/* opis i puenta osobno: puenta (ostatnie zdanie) zawsze w swoim wierszu przy dole boksu, twarde spacje po jednoliterowych wyrazach (właściciel 4.10) */}
      {(() => { const parts = split(item.text); return <><p>{parts[0]}</p>{parts[1] ? <p className="sc-spin-explainer__punch">{parts[1]}</p> : null}</>; })()}</li>
  ))}</ul>;
  // Strona główna (właściciel 3.10): tytuł „Jak działa przekaz” z przeskakującymi literami, obok szare „Czym jest spin?”,
  // które rozsuwa trzy boksy; reszta strony przesuwa się w dół.
  if (collapsible) return <section className="sc-spin-explainer" data-collapsible="" id={id} aria-labelledby={`${id ?? "spin-explainer"}-title`}>
    <div className="sc-spin-explainer__head">
      <Heading className="sc-spin-explainer__title sc-spin-explainer__title--big" id={`${id ?? "spin-explainer"}-title`}>Jak działa <GlitchWord word="przekaz" /></Heading>
      <button type="button" className="sc-spin-explainer__toggle" aria-expanded={open} aria-controls={`${uid}-grid`} onClick={() => setOpen(value => !value)}>{text.kicker}?</button>
    </div>
    {grid}
  </section>;
  return <section className="sc-spin-explainer" id={id} aria-labelledby={`${id ?? "spin-explainer"}-title`}>
    <p className="sc-spin-explainer__kicker">{text.kicker}</p>
    <Heading className="sc-spin-explainer__title" id={`${id ?? "spin-explainer"}-title`}>{text.title}</Heading>
    {grid}
  </section>;
}
