"use client";

import { useId, useState, type FormEvent } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button, NavMenu, SearchField } from "../kit";
import { useAccount } from "../lib/account";
import type { SiteConfig } from "../types";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { useFeature } from "../lib/features";
import { isSiteNavigationCurrent, siteNavigation } from "../lib/siteNavigation";

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
      <SearchField id={id} label="Szukaj materiałów" value={value} onChange={setValue} maxLength={200} placeholder="Szukaj materiałów…" />
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
