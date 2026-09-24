import type { Metadata } from "next";
import { Montserrat } from "next/font/google";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-serif/400.css";
import "@fontsource/ibm-plex-serif/500.css";
import "@fontsource/ibm-plex-mono/400.css";

import "./globals.css";
// Библиотека нового визуального языка. Обязательно ПОСЛЕ globals.css — порядок каскада (docs/UI_KIT_PLAN.md).
import "@spin-clinic/ui/kit/kit.css";
import { Providers } from "./providers";
import { SiteChrome } from "./chrome";
import { site } from "../lib/site";

// Montserrat только выставляет переменную --font-montserrat; body по-прежнему на IBM Plex,
// поэтому живые страницы не меняются. latin-ext обязателен для польской диакритики.
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
      <head><script dangerouslySetInnerHTML={{ __html: `(function(){try{var p=localStorage.getItem('spin-theme');var t=p==='light'||p==='pastel'||p==='dark'?p:'dark';document.documentElement.dataset.themePreference=t;document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t==='dark'?'dark':'light'}catch(e){document.documentElement.dataset.theme='dark'}})();` }} /></head>
      <body>
        <a href="#main-content" className="sr-only focus:not-sr-only focus:p-4">Przejdź do treści</a>
        <Providers>
          <SiteChrome site={site}>{children}</SiteChrome>
        </Providers>
        {process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN && <script defer data-domain={process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN} src="https://plausible.io/js/script.js" />}
      </body>
    </html>
  );
}
