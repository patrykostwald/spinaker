'use client';

import { Button, InfoPage } from '@spin-clinic/ui/kit';

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <InfoPage
    eyebrow="BŁĄD"
    title="Coś poszło nie tak po naszej stronie."
    lead="Nie udało się wyświetlić tej strony. Spróbuj ponownie za chwilę; jeśli błąd wraca, wróć na stronę główną."
    actions={<>
      <Button variant="primary" onClick={() => reset()}>Spróbuj ponownie</Button>
      <Button href="/" variant="secondary">Strona główna</Button>
    </>}
  >{null}</InfoPage>;
}
