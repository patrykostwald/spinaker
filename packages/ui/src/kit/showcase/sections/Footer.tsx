"use client";

/**
 * Witryna SiteFooter (docs/UI_KIT_PLAN.md → «Компоненты» SiteFooter,
 * «Оживление каждого элемента → Футер»). Treść i dysklaimer — dosłownie z `PortalHome.tsx`
 * (linia ~40): to polityka redakcyjna, nie tylko wygląd.
 */

import { SiteFooter, type SiteFooterColumn } from "../../SiteFooter";

export const meta = {
  id: "stopka",
  title: "Stopka",
  lead: "Każda kolumna to własny <nav aria-label>. Siatka reaguje na własną szerokość (container query): 4 kolumny ⩾1024, 2 ⩾640, 1 poniżej.",
};

const COLUMNS: SiteFooterColumn[] = [
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
    title: "Redakcja",
    links: [
      { label: "Warsztat nitek", href: "/editor" },
      { label: "Katalog źródeł", href: "/editor/sources" },
      { label: "Panel redakcyjny X", href: "/editor/political" },
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

function Wordmark() {
  return (
    <span className="sc-t-title-m" style={{ display: "inline-flex", alignItems: "baseline", gap: 2 }}>
      spin<span style={{ color: "var(--sc-accent)" }}>.</span>clinic
    </span>
  );
}

function FooterDemo({ theme }: { theme: "dark" | "light" }) {
  return (
    <div className="sc-root" data-sc-theme={theme} style={{ background: "var(--sc-bg)", padding: "var(--sc-s-6) var(--sc-s-4) 0", borderRadius: "var(--sc-r-xl)" }}>
      <p className="sc-t-caption sc-text-3" style={{ margin: "0 0 var(--sc-s-3)" }}>{theme === "dark" ? "Noc" : "Dzień"}</p>
      <SiteFooter
        brand={<Wordmark />}
        note={
          <>
            Materiały prezentujemy w oryginalnym kontekście źródłowym.
            <br />
            Zestawienie publikacji nie jest potwierdzeniem zawartych w nich twierdzeń.
          </>
        }
        columns={COLUMNS}
        cta={{ eyebrow: "WSPARCIE PROJEKTU", label: "Wesprzyj spin.clinic", href: "/wsparcie" }}
        bottom="Sekcja demonstracyjna biblioteki UI — wszystkie dane są fikcyjne."
      />
    </div>
  );
}

export function Section() {
  return (
    <div style={{ display: "grid", gap: "var(--sc-s-5)" }}>
      <FooterDemo theme="dark" />
      <FooterDemo theme="light" />
    </div>
  );
}
