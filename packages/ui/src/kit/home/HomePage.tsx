"use client";

/**
 * Strona główna na kicie — odchudzona do rdzenia (decyzja właściciela 5.11.2026):
 * Hero → „Od czego zacząć" → Dr. Spin (diagnozy wpisów obu stron + przekazy dnia) → Wsparcie → Newsletter.
 * Usunięte: ogólny feed „Wiadomości", „Twoje wiadomości" (nitki), Baza, „Nitka Dr. Spina”.
 * Dane publiczne i agregacja mediów żyją na przeszłość.today — tu zostaje unikalna wartość: diagnozy.
 * Portal, szapka i stopka są globalne (`app/providers.tsx`, `app/layout.tsx`).
 */

import { HomeHero } from "./HomeHero";
import { HomeStart } from "./HomeStart";
import { HomeSpinTeaser } from "./HomeSpinTeaser";
import { HomeSupport } from "./HomeSupport";
import { NewsletterSignup } from "../../components/NewsletterSignup";
import { useDemoMode } from "./data";

function DemoBanner() {
  const demo = useDemoMode();
  if (!demo) return null;
  return (
    <p className="sc-home-demo sc-t-meta" role="status">
      <strong>Dane demonstracyjne.</strong> Backend jest niedostępny — materiały poniżej są FIKCYJNE i służą tylko do pracy nad układem.
    </p>
  );
}

export function HomePage() {
  return (
    <div className="sc-home">
      {/* A6/D8: jedyny <h1> strony głównej to tytuł w HomeHero. */}
      <DemoBanner />
      <HomeHero />
      <HomeStart />
      <HomeSpinTeaser />
      <HomeSupport />
      <NewsletterSignup source="home" />
    </div>
  );
}
