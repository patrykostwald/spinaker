"use client";

import { useEffect, useId, useState, type FormEvent } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button, NavMenu, SearchField } from "../kit";
import { useAccount } from "../lib/account";
import type { SiteConfig } from "../types";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { ACCOUNTS_ENABLED, THREADS_ENABLED } from "../lib/features";

function HeaderSearch() {
  const [value, setValue] = useState("");
  const id = useId();
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (value.trim()) router.push(`/search?q=${encodeURIComponent(value.trim())}`);
  }

  return (
    <form className="sc-nav-search" role="search" onSubmit={submit}>
      <SearchField id={id} label="Szukaj w bazie materiałów" value={value} onChange={setValue} maxLength={200} placeholder="Szukaj w bazie…" />
    </form>
  );
}

/** Data i godzina obok wyszukiwarki (zastępuje osobny wiersz z datą nad stroną główną). */
function HeaderClock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const timer = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  if (!now) return <span className="sc-nav-clock" aria-hidden="true" />;
  const day = now.toLocaleDateString("pl-PL", { weekday: "short", day: "numeric", month: "short" });
  const time = now.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  return <time className="sc-nav-clock" dateTime={now.toISOString()}><span>{day}</span> {time}</time>;
}

/**
 * Rząd szapki: spin.clinic BETA · Źródła · [szukaj] · Klinika · godzina · motyw · O nas.
 * Źródła (strona główna z Bazą) stoją w liście po lewej; Klinika i O nas w prawym slocie — w panelu
 * mobilnym wszystkie są na liście (mobileOnly). Nitki wrócą w fazie II (THREADS_ENABLED).
 */
const SECTIONS: Array<{ label: string; href: string; mobileOnly?: boolean }> = [
  { label: "Źródła", href: "/" },
  { label: "Klinika", href: "/klinika", mobileOnly: true },
  ...(THREADS_ENABLED ? [{ label: "Nitki", href: "/nitki" }] : []),
  { label: "O nas", href: "/o-nas", mobileOnly: true },
];

export function SiteHeader({ site }: { site: SiteConfig }) {
  const pathname = usePathname();
  const account = useAccount();
  const [first, ...rest] = site.name.split(".");
  const second = rest.join(".");
  // Szapka: po lewej wordmark z dopiskiem BETA i trzy części serwisu, pole szukania na środku, po prawej
  // „O nas” · motyw · konto (te same odstępy). Źródła są w globalnej stopce, nie w szapce.

  return (
    <NavMenu
      layout="centered"
      items={SECTIONS.map(section => ({
        ...section,
        current: section.href === "/" ? pathname === "/" : pathname.startsWith(section.href),
      }))}
      brand={
        <div className="sc-nav-brand">
          <Link href="/" className="sc-wordmark">{first}<span aria-hidden="true">.</span>{second}</Link>
          <span className="sc-beta">BETA</span>
        </div>
      }
      search={<HeaderSearch />}
      cta={<div className="sc-nav-cta">
        <Link href="/klinika" className="sc-navmenu__link sc-nav-cta__link" aria-current={pathname.startsWith("/klinika") ? "page" : undefined}>Klinika</Link>
        <HeaderClock /><ThemeSwitcher compact />
        <Link href="/o-nas" className="sc-navmenu__link sc-nav-cta__link" aria-current={pathname === "/o-nas" ? "page" : undefined}>O nas</Link>
        {ACCOUNTS_ENABLED && <Button href="/konto" variant="quiet" size="sm">{account.data?.authenticated ? "Moje konto" : "Zaloguj"}</Button>}</div>}
    />
  );
}
