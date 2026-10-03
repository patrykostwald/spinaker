"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { HomeSupport } from "./HomeSupport";
import { HomeSpinTeaser } from "./HomeSpinTeaser";
import { SpinExplainer } from "../SpinExplainer";
import { HomeThreads } from "./HomeThreads";
import { NewsletterSignup } from "../../components/NewsletterSignup";
import { useDemoMode } from "./data";

function DemoBanner() {
  const demo = useDemoMode();
  if (!demo) return null;
  return (
    <p className="sc-home-demo sc-t-meta" role="status">
      <strong>Dane demonstracyjne.</strong> Backend jest niedostępny - materiały poniżej są FIKCYJNE i służą tylko do pracy nad układem.
    </p>
  );
}

export function HomePage() {
  const params = useSearchParams();
  const router = useRouter();
  const q = params.get("q") ?? "";
  // Baza nie stoi już na głównej (właściciel 3.10): stare linki z ?q= prowadzą do wyszukiwarki.
  useEffect(() => {
    if (q) router.replace(`/search?q=${encodeURIComponent(q)}`);
  }, [q, router]);


  return (
    <>
      <div className="sc-home">
        <h1 className="sc-sr-only">Diagnozy Dr. Spina i tropy</h1>
        <DemoBanner />
        <SpinExplainer id="czym-jest-spin" collapsible />
        {/* Właściciel 3.10: pierwsze, co widzi czytelnik, to nitki; Klinika pod nimi; Baza, Wiadomości i Twoje wiadomości
            nie stoją na głównej (Baza i wyszukiwanie zostają pod własnym adresem). */}
        <HomeThreads />
        <HomeSpinTeaser />
        <HomeSupport />
        <NewsletterSignup source="home" />
      </div>
    </>
  );
}
