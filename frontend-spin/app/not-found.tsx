import type { Metadata } from 'next';
import { Button, InfoPage } from '@spin-clinic/ui/kit';

export const metadata: Metadata = { title: 'Nie znaleziono strony — spin.clinic' };

export default function NotFound() {
  return <InfoPage
    eyebrow="BŁĄD 404"
    title="Nie znaleziliśmy tej strony."
    lead="Adres mógł się zmienić albo zawiera literówkę. Wróć na stronę główną lub przejdź do Kliniki spinu, gdzie są wszystkie diagnozy."
    actions={<>
      <Button href="/" variant="primary">Strona główna</Button>
      <Button href="/klinika" variant="secondary">Klinika</Button>
    </>}
  >{null}</InfoPage>;
}
