import type { Metadata } from 'next';
import { TesterLogin } from './TesterLogin';

export const metadata: Metadata = {
  title: 'Logowanie testera',
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
};

/** Wejście do podglądu fazy 2 loginem i hasłem testera (zamiast tajnego linku). */
export default function TesterLoginPage() {
  return <section className="sc-preview-page">
    <p className="sc-preview-eyebrow">spin.clinic · podgląd fazy 2</p>
    <h1>Logowanie testera</h1>
    <p>Zaloguj się danymi, które dostałeś od zespołu spin.clinic. Po zalogowaniu zobaczysz nowe funkcje na tym urządzeniu przez 30 dni.</p>
    <TesterLogin />
  </section>;
}
