"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

/** Zaproszenie do ankiety (właściciel 3.10): cienki pasek pod menu, nie wyskakujące okno.
 *  Znika po zamknięciu albo po wypełnieniu ankiety; nie pokazuje się w panelu ani na samej ankiecie. */
const CLOSED = "sc-survey-closed";
const DONE = "sc-survey-done";

export function SurveyBar() {
  const pathname = usePathname() || "/";
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (pathname.startsWith("/panel") || pathname.startsWith("/glosowanie")) return setShow(false);
    try { setShow(!localStorage.getItem(CLOSED) && !localStorage.getItem(DONE)); } catch { setShow(false); }
  }, [pathname]);
  if (!show) return null;
  const close = () => { try { localStorage.setItem(CLOSED, String(Date.now())); } catch { /* bez pamięci: zamknięcie do odświeżenia */ } setShow(false); };
  return (
    <aside className="sc-survey-bar" aria-label="Ankieta">
      <span className="sc-survey-bar__dot" aria-hidden="true" />
      <p><strong>Pomóż nam wybrać, jak pokazywać diagnozy.</strong> <span>4 pytania, około 2 minut, bez logowania.</span></p>
      <a className="sc-survey-bar__go" href="/glosowanie/index.html">Wypełnij ankietę →</a>
      <button type="button" className="sc-survey-bar__close" aria-label="Zamknij zaproszenie do ankiety" onClick={close}>×</button>
    </aside>
  );
}
