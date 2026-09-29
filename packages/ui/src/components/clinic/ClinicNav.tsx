"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useState } from "react";

const pages = [
  ["/klinika", "Przegląd"], ["/klinika/diagnozy", "Diagnozy"],
  ["/klinika/wskazniki", "Wskaźniki"], ["/klinika/wywiady", "Wywiady"],
  ["/klinika/przekazy", "Przekazy"], ["/raport", "Raporty"],
] as const;

export function ClinicNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const id = useId();
  return <nav className="sc-clinic-nav" aria-label="Nawigacja Kliniki">
    <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>W Klinice <span aria-hidden="true">⌄</span></button>
    <div id={id} data-open={open}>{pages.map(([href, label]) => <Link key={href} href={href}
      aria-current={(href === "/klinika" ? pathname === href : (pathname.startsWith(href) || (href === "/klinika/diagnozy" && /^\/klinika\/\d+(?:\/|$)/.test(pathname)))) ? "page" : undefined}
      onClick={() => setOpen(false)}>{label}</Link>)}</div>
  </nav>;
}
