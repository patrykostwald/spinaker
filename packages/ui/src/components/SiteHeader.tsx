"use client";

import { useId, useState, type FormEvent } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button, NavMenu, SearchField } from "../kit";
import { useAccount } from "../lib/account";
import type { SiteConfig } from "../types";
import { ThemeSwitcher } from "./ThemeSwitcher";

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

export function SiteHeader({ site }: { site: SiteConfig }) {
  const pathname = usePathname();
  const account = useAccount();
  const [first, ...rest] = site.name.split(".");
  const second = rest.join(".");
  // Szapka minimalna (замечание владельца 24.09): w rzędzie tylko wordmark, szukanie, motyw i konto.
  // Sekcje serwisu są w stopce; na telefonie panel menu pokazuje je razem z akcjami.
  const items = [
    { label: "Źródła", href: "/zrodla", current: pathname === "/zrodla" },
    { label: "Osoby publiczne", href: "/osoby-publiczne", current: pathname.startsWith("/osoby-publiczne") },
    { label: "O nas", href: "/o-nas", current: pathname === "/o-nas" },
  ].filter(() => false);

  return (
    <NavMenu
      items={items}
      brand={<Link href="/" className="sc-wordmark">{first}<span aria-hidden="true">.</span>{second}</Link>}
      search={<HeaderSearch />}
      cta={<div className="sc-nav-cta"><ThemeSwitcher compact /><Button href="/konto" variant="quiet" size="sm">{account.data?.authenticated ? "Moje konto" : "Zaloguj"}</Button></div>}
    />
  );
}
