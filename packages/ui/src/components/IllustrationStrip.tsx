"use client";

import { useEffect, useState } from "react";
import { Button } from "../kit";

type DayPeriod = "morning" | "afternoon" | "evening";
type ThemeName = "dark" | "light";

function currentPeriod(): DayPeriod {
  const hour = new Date().getHours();
  if (hour >= 6 && hour < 12) return "morning";
  if (hour >= 12 && hour < 18) return "afternoon";
  return "evening";
}

function readTheme(): ThemeName {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function IllustrationStrip() {
  const [period, setPeriod] = useState<DayPeriod>("morning");
  const [theme, setTheme] = useState<ThemeName>("dark");

  useEffect(() => {
    setPeriod(currentPeriod());
    setTheme(readTheme());
    const observer = new MutationObserver(() => setTheme(readTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return <section className="sc-illustration-strip" aria-label={`Ilustracja autorska · ${period} · motyw ${theme}`}>
    <div className="sc-illustration-strip__frame">
      <img src={`/illustrations/${theme}/${period}.png`} alt="Akwarelowa ilustracja polskiego krajobrazu, rysowana konturami kredek" />
      <span className="sc-illustration-strip__sign"><small>przystanek</small>spin.clinic</span>
      <Button href="/wsparcie" variant="secondary" size="sm" className="sc-illustration-strip__support">Wesprzyj</Button>
      <p>Polska · ilustracja autorska</p>
    </div>
  </section>;
}
