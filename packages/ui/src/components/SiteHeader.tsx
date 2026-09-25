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
  // Szapka: po lewej wordmark z dopiskiem BETA i „O nas”, pole szukania na środku całej szapki,
  // po prawej motyw i konto. Źródła są w globalnej stopce, nie w szapce.

  return (
    <NavMenu
      layout="centered"
      items={[]}
      brand={
        <div className="sc-nav-brand">
          <Link href="/" className="sc-wordmark">{first}<span aria-hidden="true">.</span>{second}</Link>
          <span className="sc-beta">BETA</span>
          <Link href="/o-nas" className="sc-navmenu__link sc-hoverable sc-nav-brand__about" aria-current={pathname === "/o-nas" ? "page" : undefined}>O nas</Link>
        </div>
      }
      search={<HeaderSearch />}
      cta={<div className="sc-nav-cta"><ThemeSwitcher compact /><Button href="/konto" variant="quiet" size="sm">{account.data?.authenticated ? "Moje konto" : "Zaloguj"}</Button></div>}
    />
  );
}
