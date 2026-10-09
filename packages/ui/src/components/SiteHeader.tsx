"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { SiteConfig } from "../types";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { useFeature } from "../lib/features";

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
      <Link href="/" className="sc-wordmark" aria-label={`${site.name} - strona główna`}>{first}<span aria-hidden="true">.</span>{second}</Link><span className="sc-beta">BETA</span>
      <nav className="sc-shell-desktop" aria-label="Menu główne">{items.map(item => <Link key={item.href} href={item.href} aria-current={current(item.href) ? "page" : undefined}>{item.label}</Link>)}</nav>
      <div className="sc-shell-theme"><ThemeSwitcher compact /></div>
    </div></header>
    <nav className="sc-shell-mobile" aria-label="Menu główne telefonu">{items.filter(item => item.label !== "Raporty").map((item, index) => <Link key={item.href} href={item.href} aria-current={current(item.href) ? "page" : undefined}><span aria-hidden="true">{["◎", "≡", "▷", "⌕", "○"][index]}</span>{item.mobile || item.label}</Link>)}</nav>
  </>;
}
