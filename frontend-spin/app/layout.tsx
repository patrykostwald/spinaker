import type { Metadata } from "next";
import { SiteHeader } from "@spin-clinic/ui";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-serif/400.css";
import "@fontsource/ibm-plex-serif/500.css";
import "@fontsource/ibm-plex-mono/400.css";

import "./globals.css";
import { Providers } from "./providers";
import { site } from "../lib/site";

export const metadata: Metadata = {
  title: "spin.clinic — historie w źródłach",
  description: "Przeszukuj źródła i poznawaj historie wydarzeń na osi czasu. Context before content.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: `(function(){try{var p=localStorage.getItem('spin-theme');var t=p==='light'||p==='pastel'||p==='dark'?p:'dark';document.documentElement.dataset.themePreference=t;document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t==='dark'?'dark':'light'}catch(e){document.documentElement.dataset.theme='dark'}})();` }} /></head>
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
