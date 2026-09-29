export type SiteNavigationItem = { label: string; href: string };

const links = {
  home: { label: "Główna", href: "/" },
  clinic: { label: "Klinika", href: "/klinika" },
  council: { label: "Konsylium AI", href: "/konsylium" },
  about: { label: "O nas", href: "/o-nas" },
  press: { label: "Dla redakcji", href: "/dla-redakcji" },
  methodology: { label: "Metodologia", href: "/metodologia" },
  charter: { label: "Karta Konsylium", href: "/konsylium/karta" },
  people: { label: "Osoby publiczne", href: "/osoby-publiczne" },
  sources: { label: "Źródła", href: "/zrodla" },
  newsletter: { label: "Newsletter", href: "/newsletter" },
  contact: { label: "Kontakt", href: "/o-nas#kontakt" },
  support: { label: "Wesprzyj", href: "/wsparcie" },
  terms: { label: "Zasady korzystania", href: "/zasady-korzystania" },
  privacy: { label: "Prywatność i cookies", href: "/polityka-prywatnosci" },
} satisfies Record<string, SiteNavigationItem>;

export const siteNavigation = {
  primary: [links.home, links.clinic, links.council, links.about],
  more: [links.press, links.methodology, links.charter, links.people, links.sources, links.newsletter, links.contact],
  support: links.support,
  footer: [
    { title: "Czytaj", links: [links.home, links.clinic, links.people, links.sources, links.newsletter] },
    { title: "Jak pracujemy", links: [links.council, links.methodology, links.charter] },
    { title: "Projekt i kontakt", links: [links.about, links.press, links.contact, { label: "X @spinclinic", href: "https://x.com/spinclinic" }] },
    { title: "Dokumenty prawne", links: [links.terms, links.privacy] },
  ],
};

export const clinicNavigation: SiteNavigationItem[] = [
  { href: "/klinika", label: "Przegląd" },
  { href: "/klinika/diagnozy", label: "Diagnozy" },
  { href: "/klinika/wskazniki", label: "Dane i wykresy" },
  { href: "/klinika/wywiady", label: "Wywiady" },
  { href: "/klinika/przekazy", label: "Przekazy" },
  { href: "/klinika/raporty", label: "Raporty" },
];

export function isClinicNavigationCurrent(pathname: string, href: string) {
  if (href === "/klinika") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`)
    || (href === "/klinika/diagnozy" && /^\/klinika\/\d+(?:\/|$)/.test(pathname))
    || (href === "/klinika/raporty" && (pathname === "/raport" || pathname.startsWith("/raport/")));
}

export function isSiteNavigationCurrent(pathname: string, href: string) {
  if (href.includes("#")) return false;
  if (href === "/") return pathname === "/";
  if (href === "/klinika") return pathname.startsWith("/klinika") || pathname.startsWith("/raport");
  if (href === "/konsylium") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}
