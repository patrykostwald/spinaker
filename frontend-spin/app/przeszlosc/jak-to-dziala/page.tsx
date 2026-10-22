import type { Metadata } from 'next';
import { JakToDziala } from './JakToDziala';

/**
 * Strona statyczna (bez wywołań API, bez ciasteczek): renderowana przy budowie i trzymana w pamięci offline aplikacji.
 * Na domenie przeszlosc.today adres to /jak-to-dziala (middleware), canonical wskazuje właśnie ten adres.
 */
const TITLE = 'Jak to działa - przeszłość.today: źródła, łączenie osób, AI i sprostowania';
const DESCRIPTION = 'Skąd przeszłość.today bierze dane, jak łączy osoby i podmioty (tylko po identyfikatorach i dokumentach), jedna miara dla wszystkich klubów, gdzie jest AI i jak zgłosić błąd.';

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: 'https://przeszlosc.today/jak-to-dziala' },
  openGraph: { type: 'article', siteName: 'przeszłość.today', locale: 'pl_PL', title: TITLE, description: DESCRIPTION, url: 'https://przeszlosc.today/jak-to-dziala' },
  twitter: { card: 'summary', title: TITLE, description: DESCRIPTION },
};

export default function JakToDzialaRoute() {
  return <JakToDziala />;
}
