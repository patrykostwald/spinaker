import Link from "next/link";

const STEPS = [
  { title: "Wybierz wpis polityka", text: "Zacznij od wpisu, który Dr. Spin wybrał dla każdej strony, albo przejrzyj całą bazę diagnoz.", href: "#dr-spin", cta: "Zobacz wpisy" },
  { title: "Zobacz analizę Konsylium", text: "Otwórz diagnozę: werdykt, siłę spinu, rozpoznane techniki i oceny poszczególnych modeli.", href: "/klinika/diagnozy", cta: "Przeglądaj diagnozy" },
  { title: "Sprawdź źródła", text: "Przy każdym twierdzeniu jest status i link do źródła. Tak sprawdzisz, na czym opiera się ocena.", href: "/metodologia#twierdzenia", cta: "Jak oceniamy twierdzenia" },
] as const;

/** T3 (Aspekt 4): trzy kroki dla nowego czytelnika, pod hero. */
export function HomeStart() {
  return (
    <section className="sc-home-start" aria-labelledby="home-start-title">
      <h2 id="home-start-title" className="sc-t-title-m">Od czego zacząć</h2>
      <ol className="sc-home-start__steps">
        {STEPS.map((step, index) => (
          <li key={step.title}>
            <span className="sc-home-start__n" aria-hidden="true">{index + 1}</span>
            <strong>{step.title}</strong>
            <p>{step.text}</p>
            <Link href={step.href}>{step.cta} →</Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
