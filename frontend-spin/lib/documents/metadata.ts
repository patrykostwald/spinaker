import type { Metadata } from "next";

export function englishMetadata(title: string, description: string, pl: string, en: string): Metadata {
  const fullTitle = `${title} - spin.clinic`;
  return {
    title: fullTitle,
    description,
    alternates: { canonical: en, languages: { pl, en } },
    openGraph: { type: "website", siteName: "spin.clinic", locale: "en_GB", title: fullTitle, description, url: en,
      images: [{ url: "/og.png", width: 1200, height: 630, alt: "spin.clinic" }] },
    twitter: { card: "summary_large_image", site: "@spinclinic", title: fullTitle, description, images: ["/og.png"] },
  };
}
