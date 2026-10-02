/**
 * Czym jest spin (właściciel 3.10.2026): wielu czytelników nie wie, co to spin ani spin doktor. Trzy równe boksy:
 * spin, spin doktor, spin.clinic. Ta sama treść na stronie głównej i w „O nas”; teksty przychodzą z zewnątrz (tłumaczenia).
 */
export type SpinExplainerText = { kicker: string; title: string; items: { name: string; text: string }[] };

export const SPIN_EXPLAINER_PL: SpinExplainerText = {
  kicker: "Czym jest spin",
  title: "Politycy mają spin doktorów. Ty masz spin.clinic.",
  items: [
    { name: "Spin", text: "Takie podanie faktów, żeby wybrzmiały na czyjąś korzyść: dobór słów, pominięcia, emocje, wybrane liczby. Nie zawsze kłamstwo, zawsze kierunek." },
    { name: "Spin doktor", text: "Doradca, który układa przekaz polityka: co powiedzieć, jak to ująć i czego nie mówić. Pracują dla polityków po obu stronach sceny." },
    { name: "spin.clinic", text: "Strażnik po Twojej stronie: Konsylium AI rozkłada przekaz na techniki perswazji i sprawdza twierdzenia. Ta sama miara dla rządu i opozycji." },
  ],
};

export function SpinExplainer({ text = SPIN_EXPLAINER_PL, headingLevel = 2, id }: { text?: SpinExplainerText; headingLevel?: 2 | 3; id?: string }) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return <section className="sc-spin-explainer" id={id} aria-labelledby={`${id ?? "spin-explainer"}-title`}>
    <p className="sc-spin-explainer__kicker">{text.kicker}</p>
    <Heading className="sc-spin-explainer__title" id={`${id ?? "spin-explainer"}-title`}>{text.title}</Heading>
    <ul className="sc-spin-explainer__grid">{text.items.map((item, index) => (
      <li key={item.name} data-step={index + 1}><strong>{item.name}</strong><p>{item.text}</p></li>
    ))}</ul>
  </section>;
}
