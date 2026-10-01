import Link from "next/link";
import type { ComponentProps } from "react";
import { english } from "./english";

export type DocumentLanguage = "pl" | "en";

export function documentTranslator(lang: DocumentLanguage) {
  return (text: keyof typeof english) => lang === "en" ? english[text] : text;
}

export const documentRoutes = {
  "/o-nas": "/en/about",
  "/metodologia": "/en/methodology",
  "/konsylium": "/en/council",
  "/konsylium/karta": "/en/council/charter",
  "/dla-redakcji": "/en/press",
} as const;

/** Keep local document links in the chosen language, preserving section anchors. */
export function DocumentLink({ lang, href, children, ...props }: Omit<ComponentProps<typeof Link>, "href"> & { lang: DocumentLanguage; href: string }) {
  const [path, hash] = href.split("#");
  const translated = documentRoutes[path as keyof typeof documentRoutes];
  const target = lang === "en" && translated ? translated + (hash ? `#${hash}` : "") : href;
  return <Link {...props} href={target}>{children}{lang === "en" && path.startsWith("/") && !translated ? " (in Polish)" : null}</Link>;
}
