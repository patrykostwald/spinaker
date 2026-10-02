import Link from "next/link";
import { ContextThreadStrip } from "./ContextThreadStrip";

const CONTACT = "kontakt@spin.clinic";

const STEPS = [
  ["Box otwierający", "Twój artykuł, wywiad, film albo śledztwo - to, co chcesz wypromować."],
  ["Do 14 boxów kontekstu", "Z naszej Bazy albo dodane po linku (tytuł, zdjęcie) - trafiają do Bazy."],
  ["Wątek na X jednym kliknięciem", "Tytuł i opis w pierwszym wpisie, a każdy box jako kolejna odpowiedź z linkiem do oryginału."],
];

/**
 * Zaproszenie dla dziennikarzy (strona główna, między Twoimi wiadomościami a Bazą):
 * przykładowa nitka jako pasek boxów i trzy kroki w jednej linii.
 */
export function JournalistInvite() {
  return (
    <aside className="sc-invite" aria-labelledby="journalists-title">
      <header className="sc-invite__head">
        <div>
          <p className="sc-clinic-kicker">Dla dziennikarzy i redakcji</p>
          <h3 id="journalists-title">Prowadzisz temat? Poprowadź tu autoryzowaną nitkę.</h3>
          <p>
            Dr. Spin pokazuje, jak zbudowany jest przekaz. Ty wiesz, co wydarzyło się naprawdę. Ułóż swój materiał i jego kontekst w jedną
            nitkę - pod własnym nazwiskiem, z linkiem do redakcji - i udostępnij ją na X jako gotowy wątek.{" "}
            <Link href="/dla-redakcji#nitka-kontekstowa">Więcej o nitkach</Link>
          </p>
        </div>
        <a className="sc-invite__cta" href={`mailto:${CONTACT}?subject=${encodeURIComponent("Autoryzowana nitka w spin.clinic")}`} title={CONTACT}>Napisz do nas</a>
      </header>
      <ContextThreadStrip />
      <ol className="sc-invite__steps">
        {STEPS.map(([title, text], index) => (
          <li key={title}><span>{index + 1}</span><div><strong>{title}</strong><p>{text}</p></div></li>
        ))}
      </ol>
    </aside>
  );
}
