"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { SiteConfig } from "../types";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { useFeature } from "../lib/features";

const MOBILE_ICONS = [
  <><circle key="a" cx="12" cy="12" r="8" /><circle key="b" cx="12" cy="12" r="3" /></>,
  <><path key="a" d="M5 12a7 7 0 0 1 14 0M8.5 12a3.5 3.5 0 0 1 7 0" /><circle key="b" cx="12" cy="12" r="1" /></>,
  <><rect key="a" x="3" y="5" width="18" height="14" rx="2" /><path key="b" d="m10 9 5 3-5 3z" /></>,
  <><circle key="a" cx="11" cy="11" r="6" /><path key="b" d="m20 20-4.5-4.5" /></>,
  <><circle key="a" cx="12" cy="8" r="4" /><path key="b" d="M4 20a8 8 0 0 1 16 0" /></>,
];

export function SiteHeader({ site }: { site: SiteConfig }) {
  const THREADS_ENABLED = useFeature('THREADS_ENABLED');
  const pathname = usePathname();
  const [first, ...rest] = site.name.split(".");
  const second = rest.join(".");
  // Przy tropach górnego menu nie ma: nawigacja jest w lewym pasku (SocialNavigation).
  if (THREADS_ENABLED) return null;
  const items = [
    { href: "/klinika", label: "Klinika" },
    { href: "/klinika/przekazy", label: "Przekazy dnia", mobile: "Przekazy" },
    { href: "/klinika/wywiady", label: "Wywiady" },
    { href: "/klinika/raporty", label: "Raporty" },
    { href: "/search", label: "Szukaj" },
    { href: "/konto", label: "Konto" },
  ];
  const current = (href: string) => href === "/klinika"
    ? pathname.startsWith('/klinika') && !['/klinika/przekazy', '/klinika/wywiady', '/klinika/raporty'].some(section => pathname.startsWith(section))
    : pathname === href || pathname.startsWith(`${href}/`);
  return <>
    <header className="sc-shell-header"><div className="sc-shell-header__inner">
      <Link href="/" className="sc-wordmark" aria-label={`${site.name} - strona główna`}>{first}<span aria-hidden="true">.</span>{second}<sup className="sc-v3-beta" aria-label="wersja beta">BETA</sup></Link>
      <nav className="sc-shell-desktop" aria-label="Menu główne">{items.map(item => <Link key={item.href} href={item.href} aria-current={current(item.href) ? "page" : undefined}>{item.label}</Link>)}</nav>
      <div className="sc-shell-theme"><ThemeSwitcher compact /></div>
    </div></header>
    {/* v3: ikony liniowe zamiast znaków (◎ ≡ ▷ ⌕ ○), ten sam porządek pozycji */}
    <nav className="sc-shell-mobile" aria-label="Menu główne telefonu">{items.filter(item => item.label !== "Raporty").map((item, index) => <Link key={item.href} href={item.href} aria-current={current(item.href) ? "page" : undefined}><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{MOBILE_ICONS[index]}</svg>{item.mobile || item.label}</Link>)}</nav>
  </>;
}
