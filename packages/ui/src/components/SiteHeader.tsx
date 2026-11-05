"use client";

import { Suspense, useEffect, useId, useState, type FormEvent } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button, NavMenu, SearchField } from "../kit";
import { useAccount } from "../lib/account";
import type { SiteConfig } from "../types";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { useFeature } from "../lib/features";
import { isSiteNavigationCurrent, siteNavigation } from "../lib/siteNavigation";

/** Na /search pole pokazuje bieżące zapytanie `q`; poza wyszukiwarką startuje puste. */
function HeaderSearch() {
  return <Suspense fallback={<HeaderSearchForm query="" />}><HeaderSearchFromUrl /></Suspense>;
}

function HeaderSearchFromUrl() {
  const params = useSearchParams();
  const pathname = usePathname();
  return <HeaderSearchForm query={pathname === "/search" ? params.get("q") ?? "" : ""} />;
}

function HeaderSearchForm({ query }: { query: string }) {
  const [value, setValue] = useState(query);
  useEffect(() => setValue(query), [query]);
  const id = useId();
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (value.trim()) router.push(`/search?q=${encodeURIComponent(value.trim())}`);
  }

  // Skrót „/”: przenosi do wyszukiwarki, o ile fokus nie jest w polu tekstowym (F11). Na wąskich ekranach, gdzie pole jest ukryte, otwiera /search.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey || event.defaultPrevented) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])") || document.querySelector("dialog[open]")) return;
      event.preventDefault();
      const input = document.getElementById(id) as HTMLInputElement | null;
      if (input && input.getClientRects().length) { input.focus(); input.select(); } else router.push("/search");
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [id, router]);

  return (
    <form className="sc-nav-search" role="search" onSubmit={submit}>
      <SearchField id={id} label="Szukaj materiałów (skrót: /)" value={value} onChange={setValue} maxLength={200} placeholder="Szukaj materiałów… (naciśnij /)" />
    </form>
  );
}

export function SiteHeader({ site }: { site: SiteConfig }) {
  const ACCOUNTS_ENABLED = useFeature('ACCOUNTS_ENABLED');
  const pathname = usePathname();
  const account = useAccount();
  const [first, ...rest] = site.name.split(".");
  const second = rest.join(".");
  return (
    <NavMenu
      layout="centered"
      items={siteNavigation.primary.map(section => ({
        ...section,
        current: isSiteNavigationCurrent(pathname, section.href),
      }))}
      desktopMore={false}
      moreItems={siteNavigation.more.map(item => ({ ...item, current: isSiteNavigationCurrent(pathname, item.href) }))}
      brand={
        <div className="sc-nav-brand">
          <Link href="/" className="sc-wordmark">{first}<span aria-hidden="true">.</span>{second}</Link>
          <span className="sc-beta">BETA</span>
        </div>
      }
      search={<HeaderSearch />}
      mobileAction={<Link className="sc-nav-mobile-search" href="/search" aria-label="Szukaj materiałów">Szukaj</Link>}
      cta={<div className="sc-nav-cta"><ThemeSwitcher compact /><Link className="sc-nav-support" href={siteNavigation.support.href}>{siteNavigation.support.label}</Link>{ACCOUNTS_ENABLED && <Button href="/konto" variant="quiet" size="sm">{account.data?.authenticated ? "Moje konto" : "Zaloguj"}</Button>}</div>}
    />
  );
}
