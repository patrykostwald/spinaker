"use client";

/**
 * Witryna NavMenu / NavCategories (docs/UI_KIT_PLAN.md → «Компоненты» NavMenu,
 * «Оживление каждого элемента → Меню и шапка»).
 * Szapka na pełną szerokość z gniazdami brand/search/cta, pasek kategorii, i ta sama
 * szapka wewnątrz ramki 375px (container query, nie zmiana okna) pokazująca panel mobilny.
 */

import { useState } from "react";
import { NavMenu, NavCategories, type NavItem } from "../../NavMenu";
import { ThemeToggle } from "../../ThemeToggle";
import { Button } from "../../Button";
import { SearchField } from "../../SearchField";

export const meta = {
  id: "nawigacja",
  title: "Nawigacja",
  lead: "NavMenu: przejeżdżający wskaźnik aktywnego punktu, kromka po przewinięciu, panel rozwijany poniżej 768px. Plus pasek kategorii.",
};

const NAV_ITEMS: NavItem[] = [
  { label: "Strona główna", href: "/", current: true },
  { label: "Baza", href: "/#baza" },
  { label: "Wątki", href: "/thread" },
  { label: "Osoby publiczne", href: "/osoby-publiczne" },
  {
    label: "Redakcja",
    href: "/editor",
    items: [
      { label: "Warsztat nitek", href: "/editor" },
      { label: "Katalog źródeł", href: "/editor/sources" },
      { label: "Panel redakcyjny X", href: "/editor/political" },
    ],
  },
  { label: "Źródła", href: "/zrodla" },
  { label: "O nas", href: "/o-nas" },
];

const CATEGORY_ITEMS = [
  { label: "Wszystko", href: "/search", current: true },
  { label: "Polska", href: "/search?kategoria=polska" },
  { label: "Świat", href: "/search?kategoria=swiat" },
  { label: "Gospodarka", href: "/search?kategoria=gospodarka" },
  { label: "Prawo i instytucje", href: "/search?kategoria=prawo" },
  { label: "Sejm", href: "/search?kategoria=sejm" },
  { label: "Nauka i zdrowie", href: "/search?kategoria=nauka" },
  { label: "Fact-checki", href: "/search?kategoria=factchecki" },
];

function Wordmark() {
  return (
    <span className="sc-t-title-s" style={{ display: "inline-flex", alignItems: "baseline", gap: 2 }}>
      spin<span style={{ color: "var(--sc-accent)" }}>.</span>clinic
    </span>
  );
}

function NavCta() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--sc-s-3)" }}>
      <ThemeToggle />
      <Button href="/konto" variant="secondary" size="sm">
        Zaloguj
      </Button>
    </div>
  );
}

function FullWidthDemo({ theme }: { theme: "dark" | "light" }) {
  const [query, setQuery] = useState("");
  return (
    <div className="sc-root" data-sc-theme={theme} style={{ borderRadius: "var(--sc-r-xl)", overflow: "hidden", boxShadow: "var(--sc-ring)" }}>
      <div style={{ padding: "var(--sc-s-3) var(--sc-s-4) 0" }}>
        <p className="sc-t-caption sc-text-3" style={{ margin: 0 }}>{theme === "dark" ? "Noc" : "Dzień"}</p>
      </div>
      <NavMenu
        items={NAV_ITEMS}
        brand={<Wordmark />}
        search={<SearchField value={query} onChange={setQuery} placeholder="Szukaj w bazie…" />}
        cta={<NavCta />}
        sticky={false}
      />
      <NavCategories items={CATEGORY_ITEMS} />
      <div style={{ height: 160, background: "var(--sc-bg)" }} aria-hidden="true" />
    </div>
  );
}

function MobileFrame({ theme }: { theme: "dark" | "light" }) {
  const [query, setQuery] = useState("");
  return (
    <div className="sc-root" data-sc-theme={theme} style={{ width: 375, border: "1px solid var(--sc-line)", borderRadius: "var(--sc-r-xl)", overflow: "hidden" }}>
      <p className="sc-t-caption sc-text-3" style={{ margin: 0, padding: "var(--sc-s-3) var(--sc-s-4) 0" }}>
        {theme === "dark" ? "Noc" : "Dzień"} · 375px
      </p>
      <NavMenu
        items={NAV_ITEMS}
        brand={<Wordmark />}
        search={<SearchField value={query} onChange={setQuery} placeholder="Szukaj…" />}
        cta={<NavCta />}
        sticky={false}
      />
      <div style={{ height: 120, background: "var(--sc-bg)" }} aria-hidden="true" />
    </div>
  );
}

export function Section() {
  return (
    <div>
      <h3 className="sc-t-title-m sc-section__sub">Pełna szerokość + pasek kategorii</h3>
      <div style={{ display: "grid", gap: "var(--sc-s-5)" }}>
        <FullWidthDemo theme="dark" />
        <FullWidthDemo theme="light" />
      </div>

      <h3 className="sc-t-title-m sc-section__sub">Ramka 375px — panel mobilny (rozwiń przyciskiem menu)</h3>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-3)" }}>
        Próg 768px liczony jest od szerokości samej szapki (container query), nie okna przeglądarki —
        dlatego panel mobilny widać tu bez zmniejszania okna.
      </p>
      <div style={{ display: "flex", gap: "var(--sc-s-5)", flexWrap: "wrap" }}>
        <MobileFrame theme="dark" />
        <MobileFrame theme="light" />
      </div>
    </div>
  );
}
