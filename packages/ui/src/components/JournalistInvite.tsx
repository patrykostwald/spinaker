import Link from "next/link";

const CONTACT = "kontakt@spin.clinic";

/** Zaproszenie dla dziennikarzy do prowadzenia autoryzowanych nitek kontekstowych (strona główna, między Twoimi wiadomościami a Bazą). */
export function JournalistInvite() {
  return (
    <aside className="sc-clinic-journalists" aria-labelledby="journalists-title">
      <div>
        <p className="sc-clinic-kicker">Dla dziennikarzy</p>
        <h3 id="journalists-title">Prowadzisz temat? Poprowadź tu autoryzowaną nitkę.</h3>
        <p>
          Dr. Spin pokazuje, jak zbudowany jest przekaz. Ty wiesz, co wydarzyło się naprawdę. Zapraszamy dziennikarzy do prowadzenia nitek
          kontekstowych pod własnym nazwiskiem: jedna teza na początku, a za nią dokumenty, dane i materiały, które ją potwierdzają, dopełniają
          albo podważają — z Twoim podpisem i linkiem do redakcji. <Link href="/o-nas#nitka-kontekstowa">Zobacz, jak wygląda nitka kontekstowa</Link>.
        </p>
      </div>
      <a className="sc-onas-mail sc-clinic-journalists__cta" href={`mailto:${CONTACT}?subject=${encodeURIComponent("Autoryzowana nitka w spin.clinic")}`}>Napisz: {CONTACT}</a>
    </aside>
  );
}
