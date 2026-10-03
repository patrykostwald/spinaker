import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { verifiedPreview } from '../../lib/features';

export const metadata: Metadata = {
  title: 'Podgląd fazy 2',
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
};

export default async function PreviewPage() {
  if (!await verifiedPreview()) notFound();
  return <section className="sc-preview-page">
    <p className="sc-preview-eyebrow">spin.clinic · faza 2</p>
    <h1>Jesteś w trybie podglądu fazy 2</h1>
    <p>Sprawdź nowe funkcje i daj nam znać, co warto poprawić. Podgląd działa na tym urządzeniu przez 30 dni.</p>
    <ul>
      <li><a href="/konto">Mój spin.clinic</a> - załóż zwykłe konto, potwierdź e-mail i zajrzyj do swojego panelu.</li>
      <li><a href="/konto/spinki/nowa">Ułóż swoją spinkę</a> - połącz materiały w kontekst.</li>
      <li><a href="/spinki">Spinki czytelników</a> - przeczytaj, obserwuj i sprawdź reakcje.</li>
      <li><a href="#zainstaluj-aplikacje">Zainstaluj aplikację</a> - na Androidzie wybierz w menu przeglądarki „Zainstaluj aplikację”. Na iPhonie otwórz Safari i wybierz Udostępnij → Do ekranu początkowego → Dodaj.</li>
      <li><a href="#powiadomienia">Powiadomienia na urządzeniu</a> oraz <a href="/konto#powiadomienia">powiadomienia na koncie</a>. Na iPhonie powiadomienia wymagają zainstalowanej aplikacji. Wysyłka w tle pozostaje wyłączona, dopóki nie włączy jej właściciel.</li>
    </ul>
    <p>Co było niejasne? Co nie zadziałało? Prześlij uwagi osobie, od której masz zaproszenie - najlepiej z adresem strony i krótkim opisem kroków.</p>
    <p>Konto i opublikowane materiały są rzeczywiste. Podgląd nie daje dostępu do panelu personelu.</p>
    <a className="sc-preview-exit" href="/api/preview/off/">Wyjdź z podglądu</a>
  </section>;
}
