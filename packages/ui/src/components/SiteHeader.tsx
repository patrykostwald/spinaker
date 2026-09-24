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
      <Button variant="primary" size="sm" type="submit">Szukaj</Button>
    </form>
  );
}

export function SiteHeader({ site }: { site: SiteConfig }) {
  const pathname = usePathname();
  const account = useAccount();
  const [first, ...rest] = site.name.split(".");
  const second = rest.join(".");
  const items = [
    { label: "Baza", href: "/search", current: pathname === "/search" },
    { label: "Źródła", href: "/zrodla", current: pathname === "/zrodla" },
    { label: "Osoby publiczne", href: "/osoby-publiczne", current: pathname.startsWith("/osoby-publiczne") },
    { label: "O nas", href: "/o-nas", current: pathname === "/o-nas" },
  ];

  return (
    <NavMenu
      items={items}
      brand={<Link href="/" className="sc-wordmark">{first}<span aria-hidden="true">.</span>{second}</Link>}
      search={<HeaderSearch />}
      cta={<><Button href="/konto" variant="quiet" size="sm">{account.data?.authenticated ? "Moje konto" : "Zaloguj"}</Button><ThemeSwitcher /></>}
    />
  );
}
