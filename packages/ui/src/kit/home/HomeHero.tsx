"use client";

/**
 * Pas powitalny: ilustracja autorska (`/illustrations/<motyw>/<pora>.png`) jako niskie tło, a na niej
 * jedno zdanie o trzech częściach serwisu, linki i „Wesprzyj nas”. Zastępuje wysoki baner, który
 * spychał wiadomości pod linię przewijania. Pas jest stały — nie da się go ukryć.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "../Button";
import { THREADS_ENABLED } from "../../lib/features";

type DayPeriod = "morning" | "afternoon" | "evening";
type ThemeName = "dark" | "light";

function currentPeriod(): DayPeriod {
  const hour = new Date().getHours();
  if (hour >= 6 && hour < 12) return "morning";
  if (hour >= 12 && hour < 18) return "afternoon";
  return "evening";
}

function readTheme(): ThemeName {
  const theme = document.documentElement.dataset.theme;
  return theme === "light" || theme === "pastel" ? "light" : "dark";
}

export function HomeHero() {
  const [period, setPeriod] = useState<DayPeriod>("morning");
  const [theme, setTheme] = useState<ThemeName>("dark");

  useEffect(() => {
    setPeriod(currentPeriod());
    setTheme(readTheme());
    // Dawny przycisk „ukryj” zapisywał to na urządzeniu — sprzątamy, pas wraca u wszystkich.
    try { localStorage.removeItem("sc-home-intro"); } catch {}
    const observer = new MutationObserver(() => setTheme(readTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return (
    <section className="sc-home-intro" aria-label="Czym jest spin.clinic">
      {/* eslint-disable-next-line @next/next/no-img-element -- ilustracja z /public, bez optymalizacji (images.unoptimized) */}
      <img className="sc-home-intro__art" src={`/illustrations/${theme}/${period}.png`} alt="" />
      <div className="sc-home-intro__content">
        <p className="sc-home-intro__title">
          Wiadomości ze źródłami. <span>Diagnozy spinu polityków.</span>
        </p>
        <p className="sc-home-intro__links">
          <Link href="/klinika">Klinika spinu →</Link>
          {THREADS_ENABLED && <Link href="/nitki">Nitki →</Link>}
          <Link href="/o-nas">Jak to działa</Link>
        </p>
      </div>
      <div className="sc-home-intro__actions">
        <Button href="/wsparcie" variant="primary" size="sm">Wesprzyj nas</Button>
      </div>
    </section>
  );
}
