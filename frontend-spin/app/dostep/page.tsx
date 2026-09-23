import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dostęp w przygotowaniu — spin.clinic",
  description: "Logowanie dla publicznych użytkowników spin.clinic jest w przygotowaniu.",
};

export default function AccessPage() {
  return (
    <article className="mvp-access-page">
      <p className="method-kicker">DOSTĘP</p>
      <h1>Dostęp w przygotowaniu</h1>
      <p>Publiczne konta i logowanie jeszcze nie są dostępne. W obecnej fazie spin.clinic działa bez konta — możesz personalizować widok bazy przez „Twoje paski”, a ustawienia zapisujemy lokalnie w Twojej przeglądarce.</p>
      <p>Wróć na stronę główną albo sprawdź, co planujemy w kolejnych fazach.</p>
      <div className="mvp-access-links">
        <Link href="/" className="text-primary">← Strona główna</Link>
        <Link href="/o-projekcie" className="text-primary">O projekcie ↗</Link>
      </div>
    </article>
  );
}
