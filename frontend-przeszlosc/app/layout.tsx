import type { Metadata } from "next";
import { SiteHeader } from "@spin-clinic/ui";

import "./globals.css";
import { Providers } from "./providers";
import { site } from "../lib/site";

export const metadata: Metadata = {
  title: "przeszłość.today — kontekst osi czasu",
  description: "Archiwum kontekstu polskiej polityki i mediów.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl">
      <body>
        <a href="#main-content" className="sr-only focus:not-sr-only focus:p-4">Przejdź do treści</a>
        <Providers>
          <SiteHeader site={site} showSearch={false} />
          <main id="main-content" className="mx-auto max-w-7xl px-4 py-5">{children}</main>
        </Providers>
        {process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN && <script defer data-domain={process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN} src="https://plausible.io/js/script.js" />}
      </body>
    </html>
  );
}
