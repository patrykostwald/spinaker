import { CAMPS, CAMP_LABELS } from "../lib/clinic";

/**
 * Legenda kolorów stron sceny (seria 2, 13.10.2026): kolor strony jest tylko identyfikatorem (fiolet / ochra),
 * słowo strony zawsze stoi obok koloru, a dopisek mówi, że kolor nie oznacza siły spinu.
 */
export function SideLegend({ note = true, className }: { note?: boolean; className?: string }) {
  return <p className={["sc-v3-sideleg", className].filter(Boolean).join(" ")}>
    {CAMPS.map(camp => <span key={camp} data-side={camp}><i className="sc-v3-sidedot" aria-hidden="true" />{CAMP_LABELS[camp]}</span>)}
    {note ? <small>kolor oznacza stronę, nie siłę spinu</small> : null}
  </p>;
}
