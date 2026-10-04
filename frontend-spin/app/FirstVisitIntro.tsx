"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

/** Pierwsza wizyta na głównej (właściciel 5.10): minutowy film „Jak działa przekaz → spin.clinic” na całym ekranie.
 *  Raz na przeglądarkę, zawsze z „Pomiń”; nie zasłania linków prowadzących wprost do diagnozy czy spinki. */
const SEEN = "sc-intro-seen";

export function FirstVisitIntro() {
  const pathname = usePathname() || "/";
  const [open, setOpen] = useState(false);
  useEffect(() => {
    // film tylko na spin.clinic; przeszlosc.today (ta sama aplikacja) ma własną stronę główną
    if (pathname !== "/" || window.location.hostname.endsWith("przeszlosc.today") || navigator.webdriver || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    try { if (!localStorage.getItem(SEEN)) setOpen(true); } catch { /* bez pamięci przeglądarki nie pokazujemy */ }
  }, [pathname]);
  useEffect(() => {
    if (!open) return;
    const close = () => { try { localStorage.setItem(SEEN, String(Date.now())); } catch { /* jw. */ } setOpen(false); };
    const onMessage = (event: MessageEvent) => { if (event.origin === window.location.origin && event.data?.type === "sc-film-end") close(); };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    window.addEventListener("message", onMessage); window.addEventListener("keydown", onKey);
    document.documentElement.style.overflow = "hidden";
    (window as unknown as { __scIntroClose?: () => void }).__scIntroClose = close;
    return () => { window.removeEventListener("message", onMessage); window.removeEventListener("keydown", onKey); document.documentElement.style.overflow = ""; };
  }, [open]);
  if (!open) return null;
  return <div className="sc-intro" role="dialog" aria-modal="true" aria-label="Jak działa spin.clinic">
    <iframe className="sc-intro__film" src="/jak-dziala/index.html" title="Jak działa spin.clinic - animacja, ok. 60 s" />
    <button type="button" className="sc-intro__skip" onClick={() => (window as unknown as { __scIntroClose?: () => void }).__scIntroClose?.()}>Pomiń</button>
  </div>;
}
