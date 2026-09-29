import type { Metadata } from "next";
import { Montserrat } from "next/font/google";
import { SiteHeader, SupportBar, TouchScrollGuard, siteNavigation } from "@spin-clinic/ui";
import { SiteFooter } from "@spin-clinic/ui/kit";

import "./globals.css";
// Библиотека нового визуального языка. Обязательно ПОСЛЕ globals.css — порядок каскада (docs/UI_KIT_PLAN.md).
import "@spin-clinic/ui/kit/kit.css";
import { Providers } from "./providers";
import { site } from "../lib/site";

// Montserrat includes Polish diacritics and is the shared typeface for live pages.
const montserrat = Montserrat({
  subsets: ["latin", "latin-ext"],
  variable: "--font-montserrat",
  display: "swap",
});

const TITLE = "spin.clinic — pokazujemy, jak zbudowany jest przekaz";
const DESCRIPTION = "Pokazujemy, jak zbudowany jest przekaz. Dr. Spin (AI) analizuje techniki perswazji we wpisach polityków i zestawia twierdzenia ze źródłami. Ta sama miara dla wszystkich.";

export const metadata: Metadata = {
  metadataBase: new URL(`https://${process.env.NEXT_PUBLIC_DOMAIN || "spin.clinic"}`),
  title: TITLE,
  description: DESCRIPTION,
  // Podgląd linku na X, Facebooku i w komunikatorach — obrazek public/og.png (1200×630).
  openGraph: { type: "website", siteName: "spin.clinic", locale: "pl_PL", title: TITLE, description: DESCRIPTION, images: [{ url: "/og.png", width: 1200, height: 630, alt: "spin.clinic — Klinika spinu" }] },
  twitter: { card: "summary_large_image", site: "@spinclinic", title: TITLE, description: DESCRIPTION, images: ["/og.png"] },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl" suppressHydrationWarning className={montserrat.variable}>
      <head><script dangerouslySetInnerHTML={{ __html: `(function(){try{var p=localStorage.getItem('spin-theme');if(p==='pastel'){p='light';localStorage.setItem('spin-theme',p)}var t=p==='light'||p==='dark'?p:'dark';document.documentElement.dataset.themePreference=t;document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t==='dark'?'dark':'light'}catch(e){document.documentElement.dataset.theme='dark'}})();` }} /></head>
      <body>
        <a href="#main-content" className="sr-only focus:not-sr-only focus:p-4">Przejdź do treści</a>
        <Providers>
          <SiteHeader site={site} />
          <TouchScrollGuard />
          <main id="main-content" className="sc-app-main">{children}</main>
          <SiteFooter
            brand={<strong>spin<span className="sc-wordmark__dot">.</span>clinic</strong>}
            cta={{ label: "Wesprzyj projekt", href: "/wsparcie" }}
            columns={siteNavigation.footer}
            above={<SupportBar />}
            sticky
          />
        </Providers>
        {process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN && <script defer data-domain={process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN} src="https://plausible.io/js/script.js" />}
      </body>
    </html>
  );
}
