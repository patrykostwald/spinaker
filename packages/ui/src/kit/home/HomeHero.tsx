"use client";

/**
 * Pas powitalny: ilustracja autorska (`/illustrations/<motyw>/<pora>.webp`) jako niskie tło, a na niej
 * jedno zdanie o trzech częściach serwisu, linki i „Wspomóż projekt”. Zastępuje wysoki baner, który
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
  // Pora dnia i motyw znamy dopiero w przeglądarce — do tego czasu bez obrazka (inaczej pobieralibyśmy dwa).
  const [period, setPeriod] = useState<DayPeriod | null>(null);
  const [theme, setTheme] = useState<ThemeName | null>(null);

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
      {theme && period ? <img className="sc-home-intro__art" src={`/illustrations/${theme}/${period}.webp`} alt="" decoding="async" /> : null}
      <div className="sc-home-intro__content">
        <p className="sc-home-intro__title">
          Konsylium AI bada przekaz polityków. <span>Ty układasz własne wiadomości.</span>
        </p>
        {/* Dwa wiersze: kim jest konsylium i jaka obowiązuje je zasada (29.09, właściciel). */}
        <p className="sc-home-intro__lead">
          Modele AI kilku firm, także płatne, rozbierają każdy wpis i wywiad: techniki, manipulacje, zagrania.<br className="sc-home-intro__br" />
          Bez sympatii i antypatii — te same zasady dla rządu i opozycji, z cytatami i źródłami.
        </p>
        <p className="sc-home-intro__links">
          <a href="#dr-spin">Zobacz dzisiejsze diagnozy →</a>
          {THREADS_ENABLED && <Link href="/nitki">Nitki →</Link>}
          <Link href="/o-nas">Jak to działa</Link>
        </p>
      </div>
      <div className="sc-home-intro__actions">
        <Button href="/wsparcie" variant="primary" size="sm">Wspomóż projekt</Button>
      </div>
    </section>
  );
}
