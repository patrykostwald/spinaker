"use client";
import { Bar, Foot, useStandalone } from './przeszlosc/ui';

/** Strona 404 po polsku, z marką przeszłość.today (zamiast domyślnej angielskiej strony Next.js). */
export default function NotFound() {
  useStandalone();
  return <div className="px">
    <Bar />
    <section className="px-card" aria-labelledby="nf-h">
      <h1 id="nf-h" className="px-h3">Nie ma takiej strony</h1>
      <p className="px-note">Adres jest nieprawidłowy albo strona została przeniesiona. Brak w naszych danych: strony pod tym adresem (stan na dziś).</p>
      <p className="px-note"><a href="/przeszlosc">Wróć na stronę główną</a> · <a href="/przeszlosc?tryb=osoba">Szukaj osoby</a></p>
    </section>
    <Foot />
  </div>;
}
