"use client";

/**
 * Szapka i stopka strony głównej na kicie (etap 2). Zastępują `SiteHeader` i stopkę z `PortalHome`
 * TYLKO na trasach już przeniesionych na kit (przełącza `frontend-spin/app/chrome.tsx`).
 * Treść stopki — dosłownie ze starego `PortalHome.tsx` (dysklaimer to polityka redakcyjna).
 */

import { useEffect, useState, type FormEvent } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAccount } from "../../lib/account";
import { Button } from "../Button";
import { NavMenu, type NavItem } from "../NavMenu";
import { SearchField } from "../SearchField";
import { SiteFooter, type SiteFooterColumn } from "../SiteFooter";
import { ThemeToggle } from "../ThemeToggle";

export function Wordmark({ size = "s" }: { size?: "s" | "m" }) {
  return (
    <span className={size === "m" ? "sc-t-title-m sc-wordmark" : "sc-t-title-s sc-wordmark"}>
      spin<span className="sc-wordmark__dot">.</span>clinic
    </span>
  );
}

function HeaderSearch() {
  const [value, setValue] = useState("");
  const router = useRouter();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = value.trim();
    router.push(q ? `/?q=${encodeURIComponent(q)}#baza` : "/#baza");
  }
  return (
    <form role="search" onSubmit={submit} className="sc-home-header__search">
      <SearchField value={value} onChange={setValue} placeholder="Szukaj w bazie…" label="Szukaj w bazie materiałów" />
    </form>
  );
}

/**
 * Kit `ThemeToggle` zmienia tylko `data-theme` (zasada witryny). Na żywej stronie wybór musi
 * przeżyć odświeżenie — skrypt anty-FOUC w layout.tsx czyta `localStorage['spin-theme']`.
 * Zapisujemy więc to, co toggle ustawił; `pastel` z przeszłości mapuje się na `light`.
 */
function usePersistTheme() {
  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      const theme = root.dataset.theme === "light" || root.dataset.theme === "pastel" ? "light" : "dark";
      try {
        window.localStorage.setItem("spin-theme", theme);
      } catch {
        /* tryb prywatny */
      }
      root.dataset.themePreference = theme;
    });
    observer.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
}

export function HomeHeader() {
  const pathname = usePathname();
  const account = useAccount();
  usePersistTheme();
  const items: NavItem[] = [
    { label: "Strona główna", href: "/", current: pathname === "/" },
    { label: "Baza", href: "/#baza" },
    { label: "Źródła", href: "/zrodla", current: pathname.startsWith("/zrodla") },
    { label: "Osoby publiczne", href: "/osoby-publiczne", current: pathname.startsWith("/osoby-publiczne") },
    { label: "O nas", href: "/o-nas", current: pathname.startsWith("/o-nas") },
  ];
  const signedIn = account.data?.authenticated === true;
  return (
    <NavMenu
      items={items}
      brand={<Wordmark />}
      search={<HeaderSearch />}
      cta={
        <div className="sc-home-header__cta">
          <ThemeToggle />
          <Button href="/konto" variant={signedIn ? "quiet" : "secondary"} size="sm">
            {signedIn ? "Moje konto" : "Zaloguj"}
          </Button>
        </div>
      }
    />
  );
}

const FOOTER_COLUMNS: SiteFooterColumn[] = [
  {
    title: "Informacje o serwisie",
    links: [
      { label: "O nas", href: "/o-nas" },
      { label: "Źródła", href: "/zrodla" },
      { label: "Zasady korzystania", href: "/zasady-korzystania" },
      { label: "Prywatność i cookies", href: "/polityka-prywatnosci" },
    ],
  },
  {
    title: "Konto",
    links: [
      { label: "Moje konto", href: "/konto" },
      { label: "Ustawienia", href: "/profile" },
      { label: "Nowa nitka kontekstowa", href: "/konto/nitki/nowa" },
    ],
  },
  {
    title: "Wsparcie",
    links: [
      { label: "Wesprzyj spin.clinic", href: "/wsparcie" },
      { label: "O projekcie", href: "/o-projekcie" },
      { label: "Dostępność", href: "/dostep" },
    ],
  },
];

export function HomeFooter() {
  return (
    <SiteFooter
      brand={<Wordmark size="m" />}
      note={
        <>
          Materiały prezentujemy w oryginalnym kontekście źródłowym.
          <br />
          Zestawienie publikacji nie jest potwierdzeniem zawartych w nich twierdzeń.
        </>
      }
      columns={FOOTER_COLUMNS}
      cta={{ eyebrow: "Wsparcie projektu", label: "Wesprzyj spin.clinic", href: "/wsparcie" }}
      bottom={
        <span className="sc-home-footer__bottom">
          <span>© {new Date().getFullYear()} spin.clinic</span>
          <a href="/polityka-prywatnosci">Prywatność i cookies</a>
          <a href="/zasady-korzystania">Zasady korzystania</a>
          <a href="/dostep">Dostępność</a>
        </span>
      }
    />
  );
}
