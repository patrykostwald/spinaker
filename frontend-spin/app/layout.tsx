import type { Metadata } from "next";
import { Montserrat } from "next/font/google";
import { SiteHeader } from "@spin-clinic/ui";

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

export const metadata: Metadata = {
  title: "spin.clinic — historie w źródłach",
  description: "Przeszukuj źródła i poznawaj historie wydarzeń na osi czasu. Context before content.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl" suppressHydrationWarning className={montserrat.variable}>
      <head><script dangerouslySetInnerHTML={{ __html: `(function(){try{var p=localStorage.getItem('spin-theme');if(p==='pastel'){p='light';localStorage.setItem('spin-theme',p)}var t=p==='light'||p==='dark'?p:'dark';document.documentElement.dataset.themePreference=t;document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t==='dark'?'dark':'light'}catch(e){document.documentElement.dataset.theme='dark'}})();` }} /></head>
      <body>
        <a href="#main-content" className="sr-only focus:not-sr-only focus:p-4">Przejdź do treści</a>
        <Providers>
          <SiteHeader site={site} />
          <main id="main-content" className="mx-auto max-w-7xl px-4 py-5">{children}</main>
        </Providers>
        {process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN && <script defer data-domain={process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN} src="https://plausible.io/js/script.js" />}
      </body>
    </html>
  );
}
