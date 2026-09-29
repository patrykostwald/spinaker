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
    <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>Klinika: {current?.label ?? "Przegląd"} <span aria-hidden="true">⌄</span></button>
    <div id={id} data-open={open}>{clinicNavigation.map(({href, label}) => <Link key={href} href={href}
      aria-current={isClinicNavigationCurrent(pathname, href) ? "page" : undefined}
      onClick={() => setOpen(false)}>{label}</Link>)}</div>
  </nav>;
}
