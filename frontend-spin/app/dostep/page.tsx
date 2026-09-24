import type { Metadata } from "next";
import { Button, InfoPage } from "@spin-clinic/ui/kit";

export const metadata: Metadata = {
  title: "Dostęp w przygotowaniu — spin.clinic",
  description: "Logowanie dla publicznych użytkowników spin.clinic jest w przygotowaniu.",
};

export default function AccessPage() {
  return (
    <InfoPage eyebrow="DOSTĘP" title="Dostęp w przygotowaniu" lead="Publiczne konta i logowanie jeszcze nie są dostępne. W obecnej fazie spin.clinic działa bez konta — możesz personalizować widok bazy przez „Twoje paski”, a ustawienia zapisujemy lokalnie w Twojej przeglądarce.">
      <section><p>Wróć na stronę główną albo sprawdź, co planujemy w kolejnych fazach.</p></section>
      <nav className="sc-info-page__actions" aria-label="Dalsze strony">
        <Button href="/" variant="secondary">Strona główna</Button>
        <Button href="/o-projekcie" variant="quiet">O projekcie</Button>
      </nav>
    </InfoPage>
  );
}
