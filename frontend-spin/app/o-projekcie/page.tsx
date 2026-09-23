import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "O nas — spin.clinic",
  description: "Czym jest spin.clinic dzisiaj i jak rozwija się w kolejnych fazach.",
};

export default function AboutPage() {
  return (
    <article className="method-page mvp-about">
      <header className="method-hero">
        <p className="method-kicker">O NAS</p>
        <h1>spin.clinic dzisiaj</h1>
        <p className="method-lead">Jesteśmy na etapie fazy 1 — agregatora wiadomości z bazy. Konta, własne paski redakcyjne i Dr Spin opisujemy niżej jako kierunek rozwoju, nie jako aktywne funkcje.</p>
      </header>

      <section aria-labelledby="jak-dzialamy-title">
        <h2 id="jak-dzialamy-title">Jak działamy</h2>
        <p>Zbieramy legalnie dostępne publikacje z zatwierdzonych źródeł i porządkujemy je w czytelne paski materiałów. Każdy box zachowuje swoje źródło, datę i link do oryginału — nic nie publikujemy pod własnym nazwiskiem.</p>
        <p>Sekcja „Twoje paski” pozwala przefiltrować materiały po haśle, kategorii lub źródle bez zakładania konta. Ustawienia takiego paska zapisujemy wyłącznie lokalnie, w Twojej przeglądarce.</p>
      </section>

      <section aria-labelledby="zasady-title">
        <h2 id="zasady-title">Nasze zasady</h2>
        <ul>
          <li>Pokazujemy, skąd pochodzi każdy materiał — źródło, data i odnośnik do oryginału są zawsze widoczne.</li>
          <li>Oznaczamy typ materiału (artykuł, wywiad, reportaż, śledztwo, dokument urzędowy, reklama, film).</li>
          <li>Przy braku danych pokazujemy pusty box z samą etykietą — nie wymyślamy tytułów ani źródeł.</li>
          <li>Nie zbieramy kont ani danych osobowych na tym etapie: personalizacja działa lokalnie, w przeglądarce.</li>
        </ul>
      </section>

      <section aria-labelledby="fazy-title">
        <h2 id="fazy-title">Trzy fazy</h2>
        <ol className="mvp-about-phases">
          <li><strong>Faza 1 — Agregator wiadomości.</strong> <span>Treść do uzupełnienia.</span></li>
          <li><strong>Faza 2 — Konta i własne paski.</strong> <span>Treść do uzupełnienia.</span></li>
          <li><strong>Faza 3 — Dr Spin.</strong> <span>Treść do uzupełnienia.</span></li>
        </ol>
      </section>

      <section aria-labelledby="co-dalej-title">
        <h2 id="co-dalej-title">Co dalej</h2>
        <p>Kolejne fazy opisujemy tu jako kierunek rozwoju — na stronie nie znajdziesz jeszcze logowania, kont ani publicznych pasków użytkowników. Wracaj tu, gdy zechcesz sprawdzić, co się zmieniło.</p>
        <Link href="/" className="text-primary">← Wróć do strony głównej</Link>
      </section>
    </article>
  );
}
