export type SiteNavigationItem = { label: string; href: string };

const links = {
  home: { label: "Główna", href: "/" },
  clinic: { label: "Klinika", href: "/klinika" },
  council: { label: "Konsylium AI", href: "/konsylium" },
  about: { label: "O nas", href: "/o-nas" },
  press: { label: "Dla redakcji", href: "/dla-redakcji" },
  methodology: { label: "Metodologia", href: "/metodologia" },
  corrections: { label: "Rejestr korekt", href: "/klinika/korekty" },
  charter: { label: "Karta Konsylium", href: "/konsylium/karta" },
  people: { label: "Osoby publiczne", href: "/osoby-publiczne" },
  sources: { label: "Źródła", href: "/zrodla" },
  newsletter: { label: "Newsletter", href: "/newsletter" },
  contact: { label: "Kontakt", href: "/o-nas#kontakt" },
  support: { label: "Wesprzyj", href: "/wsparcie" },
  terms: { label: "Zasady korzystania", href: "/zasady-korzystania" },
  privacy: { label: "Prywatność i cookies", href: "/polityka-prywatnosci" },
} satisfies Record<string, SiteNavigationItem>;

/** Kanały spin.clinic w mediach społecznościowych - jedno źródło dla stopki i strony O nas. */
export const socialChannels = [
  { name: "X", handle: "@spinclinic", href: "https://x.com/spinclinic", what: "Diagnozy najsilniejszych spinów i wątki z uzasadnieniem." },
  { name: "Facebook", handle: "spin.clinic", href: "https://www.facebook.com/profile.php?id=61595171420399", what: "Filmy z wybranych diagnoz i odnośniki do pełnych analiz." },
  { name: "Instagram", handle: "@spinclinic", href: "https://www.instagram.com/spinclinic/", what: "Krótkie filmy z diagnoz i satyryczny „Przekaz dnia”." },
  { name: "YouTube", handle: "@spin.clinic", href: "https://www.youtube.com/@spin.clinic", what: "Shorts: „Przekaz dnia - co usłyszało stado?” i filmy z diagnoz." },
  { name: "Bluesky", handle: "@spinclinic.bsky.social", href: "https://bsky.app/profile/spinclinic.bsky.social", what: "Karty diagnoz z linkiem do pełnej analizy." },
] as const;

export const siteNavigation = {
  // Logo prowadzi na główną; pozostałe strony są w stopce („Więcej”) i w menu telefonu.
  primary: [links.clinic, links.council, links.about],
  more: [links.press, links.methodology, links.charter, links.people, links.sources, links.newsletter, links.contact],
  support: links.support,
  footer: [
    { title: "Czytaj", links: [links.home, links.clinic, links.people, links.sources, links.newsletter] },
    { title: "Jak pracujemy", links: [links.council, links.methodology, links.corrections, links.charter] },
    { title: "Projekt i kontakt", links: [links.about, links.press, links.contact] },
    { title: "Obserwuj", links: socialChannels.map(channel => ({ label: channel.name, href: channel.href })) },
    { title: "Dokumenty prawne", links: [links.terms, links.privacy] },
  ],
};

export const clinicNavigation: SiteNavigationItem[] = [
  { href: "/klinika", label: "Przegląd" },
  { href: "/klinika/diagnozy", label: "Diagnozy" },
  { href: "/klinika/wskazniki", label: "Dane i wykresy" },
  { href: "/klinika/wywiady", label: "Wywiady" },
  { href: "/klinika/wywiady/glosowanie", label: "Głosowanie" },
  { href: "/klinika/przekazy", label: "Przekazy" },
  // Ta sama fraza (news/coordinated.py): w menu dopiero po sprawdzeniu wyników na prawdziwych danych; wcześniej podgląd dla redakcji pod adresem.
  ...(process.env.NEXT_PUBLIC_WSPOLNY_PRZEKAZ_PUBLIC === "true" ? [{ href: "/klinika/wspolny-przekaz", label: "Ta sama fraza" }] : []),
  { href: "/klinika/raporty", label: "Raporty" },
  links.corrections,
];

export function isClinicNavigationCurrent(pathname: string, href: string) {
  if (href === "/klinika/wywiady" && pathname.startsWith("/klinika/wywiady/glosowanie")) return false;
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
