"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { HomeThreads } from "./HomeThreads";
import { ClinicOverview } from "../../components/clinic/ClinicOverview";
import { useFeature } from "../../lib/features";

export function HomePage() {
  const params = useSearchParams();
  const router = useRouter();
  const threads = useFeature("THREADS_ENABLED");
  const q = params.get("q") ?? "";
  // Baza nie stoi już na głównej (właściciel 3.10): stare linki z ?q= prowadzą do wyszukiwarki.
  useEffect(() => {
    if (q) router.replace(`/search?q=${encodeURIComponent(q)}`);
  }, [q, router]);


  return threads ? <div className="sc-home"><HomeThreads /></div> : <ClinicOverview home />;
}
