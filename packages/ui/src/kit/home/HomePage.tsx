"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { HomeThreads } from "./HomeThreads";
import { HomeSpinTeaser } from "./HomeSpinTeaser";
import { HomeSupport } from "./HomeSupport";
import { SpinExplainer } from "../SpinExplainer";
import { NewsletterSignup } from "../../components/NewsletterSignup";
import { useFeature } from "../../lib/features";
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
  const threads = useFeature("THREADS_ENABLED");
  const q = params.get("q") ?? "";
  // Baza nie stoi już na głównej (właściciel 3.10): stare linki z ?q= prowadzą do wyszukiwarki.
  useEffect(() => {
    if (q) router.replace(`/search?q=${encodeURIComponent(q)}`);
  }, [q, router]);


  return (
    <>
      <div className="sc-home">
        <h1 className="sc-sr-only">Diagnozy Dr. Spina i spinki</h1>
        <DemoBanner />
        {/* Właściciel 3.10: pierwsze, co widzi czytelnik, to nitki; Klinika pod nimi; Baza, Wiadomości i Twoje wiadomości
            nie stoją na głównej (Baza i wyszukiwanie zostają pod własnym adresem). */}
        {/* Zabezpieczenie (5.10): przy wyłączonych spinkach główna nigdy nie jest pusta - pokazuje objaśnienie spinu, Klinikę i newsletter. */}
        {threads ? <HomeThreads /> : <><SpinExplainer id="czym-jest-spin" collapsible /><HomeSpinTeaser /><HomeSupport /><NewsletterSignup source="home" /></>}
      </div>
    </>
  );
}
