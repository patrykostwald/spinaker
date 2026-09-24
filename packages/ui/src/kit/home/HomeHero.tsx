"use client";

/**
 * Ilustracja autorska (stary `IllustrationStrip`): ten sam obraz `/illustrations/<motyw>/<pora>.png`,
 * ta sama tabliczka „przystanek spin.clinic”, podpis i „Wesprzyj” — w promieniu 28 i tokenach kitu.
 * `pastel` z lokalnego magazynu mapuje się na zestaw `light`.
 */

import { useEffect, useState } from "react";
import { Button } from "../Button";

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

const PERIOD_LABEL: Record<DayPeriod, string> = { morning: "rano", afternoon: "po południu", evening: "wieczorem" };

export function HomeHero() {
  const [period, setPeriod] = useState<DayPeriod>("morning");
  const [theme, setTheme] = useState<ThemeName>("dark");

  useEffect(() => {
    setPeriod(currentPeriod());
    setTheme(readTheme());
    const observer = new MutationObserver(() => setTheme(readTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return (
    <section className="sc-home-hero" aria-label={`Ilustracja autorska · ${PERIOD_LABEL[period]}`}>
      <div className="sc-home-hero__frame">
        {/* eslint-disable-next-line @next/next/no-img-element -- ilustracja z /public, bez optymalizacji (images.unoptimized) */}
        <img
          className="sc-home-hero__art"
          src={`/illustrations/${theme}/${period}.png`}
          alt="Akwarelowa ilustracja polskiego krajobrazu, rysowana konturami kredek"
        />
        <span className="sc-home-hero__sign sc-chrome">
          <small className="sc-t-caption">przystanek</small>
          <span className="sc-t-title-xs">spin.clinic</span>
        </span>
        <div className="sc-home-hero__support">
          <Button href="/wsparcie" variant="primary" size="sm">
            Wesprzyj
          </Button>
        </div>
        <p className="sc-home-hero__caption sc-t-caption sc-chrome">Polska · ilustracja autorska</p>
      </div>
    </section>
  );
}
