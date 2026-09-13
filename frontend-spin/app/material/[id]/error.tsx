"use client";
export default function MaterialError({ reset }: { reset: () => void }) {
  return <div role="alert" className="space-y-4"><h1 className="text-xl font-semibold">Materiał jest chwilowo niedostępny.</h1><p>Nie udało się połączyć z archiwum.</p><button className="quiet-button" onClick={reset}>Spróbuj ponownie</button></div>;
}
