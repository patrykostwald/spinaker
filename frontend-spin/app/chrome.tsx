"use client";

/**
 * Przełącznik obudowy strony (etap 2): trasy przeniesione już na kit dostają szapkę i główny
 * kontener kitu (`.sc-root`, pełna szerokość, Montserrat); pozostałe — dotychczasowy `SiteHeader`
 * i kontener `max-w-7xl`, dokładnie jak wcześniej. Lista `KIT_ROUTES` rośnie krok po kroku
 * (docs/STAGE2_HANDOFF_PROMPT.md), aż stary zestaw zniknie.
 */

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { SiteHeader } from "@spin-clinic/ui";
import { HomeHeader } from "@spin-clinic/ui/kit";
import type { SiteConfig } from "@spin-clinic/ui";

const KIT_ROUTES = new Set(["/"]);

export function SiteChrome({ site, children }: { site: SiteConfig; children: ReactNode }) {
  const pathname = usePathname();
  if (KIT_ROUTES.has(pathname)) {
    return (
      <div className="sc-root sc-home-main">
        <HomeHeader />
        <main id="main-content">{children}</main>
      </div>
    );
  }
  return (
    <>
      <SiteHeader site={site} />
      <main id="main-content" className="mx-auto max-w-7xl px-4 py-5">
        {children}
      </main>
    </>
  );
}
