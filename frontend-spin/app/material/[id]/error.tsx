"use client";
import { Button } from '@spin-clinic/ui/kit';

export default function MaterialError({ reset }: { reset: () => void }) {
  return <section role="alert" className="sc-material-error"><h1 className="sc-t-title-l">Materiał jest chwilowo niedostępny.</h1><p className="sc-t-body sc-text-2">Nie udało się połączyć z archiwum.</p><Button type="button" variant="secondary" onClick={reset}>Spróbuj ponownie</Button></section>;
}
