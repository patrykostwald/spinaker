"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useState } from "react";
import { clinicNavigation, isClinicNavigationCurrent } from "../../lib/siteNavigation";

export function ClinicNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const id = useId();
  const current = clinicNavigation.find(item => isClinicNavigationCurrent(pathname, item.href));
  return <nav className="sc-clinic-nav" aria-label="Nawigacja Kliniki">
    <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>Klinika: {current?.label ?? "Przegląd"} <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
    <div id={id} data-open={open}>{clinicNavigation.map(({href, label}) => <Link key={href} href={href}
      aria-current={isClinicNavigationCurrent(pathname, href) ? "page" : undefined}
      onClick={() => setOpen(false)}>{label}</Link>)}</div>
  </nav>;
}
