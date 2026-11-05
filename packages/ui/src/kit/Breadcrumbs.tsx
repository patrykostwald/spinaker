"use client";

/**
 * Breadcrumbs — okruszki (Aspekt 1 / R8). `<nav aria-label="Okruszki">` + uporządkowana lista;
 * ostatnia pozycja to bieżąca strona (aria-current="page", bez linku). Dodaje JSON-LD BreadcrumbList.
 * Na telefonie CSS pokazuje tylko rodzica: „‹ Diagnozy” (długi tytuł strony nie łamie układu).
 */

import Link from "next/link";
import { useEffect, useState } from "react";

export type BreadcrumbItem = { label: string; href?: string };

export function Breadcrumbs({ items, className }: { items: BreadcrumbItem[]; className?: string }) {
  const [origin, setOrigin] = useState("");
  useEffect(() => { setOrigin(window.location.origin); }, []);
  const parentIndex = items.length - 2;
  const jsonLd = origin ? {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.label,
      ...(item.href ? { item: `${origin}${item.href}` } : {}),
    })),
  } : null;
  return (
    <nav className={className ? `sc-breadcrumbs ${className}` : "sc-breadcrumbs"} aria-label="Okruszki">
      <ol className="sc-breadcrumbs__list" role="list">
        {items.map((item, index) => {
          const current = index === items.length - 1;
          return (
            <li key={`${index}-${item.label}`} className="sc-breadcrumbs__item" data-parent={index === parentIndex || undefined} data-current={current || undefined}>
              {current || !item.href
                ? <span className="sc-breadcrumbs__text" aria-current={current ? "page" : undefined}>{item.label}</span>
                : <Link className="sc-breadcrumbs__link" href={item.href}>{item.label}</Link>}
            </li>
          );
        })}
      </ol>
      {jsonLd ? <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\u003c") }} /> : null}
    </nav>
  );
}
